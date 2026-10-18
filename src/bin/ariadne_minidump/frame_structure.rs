//! Structural frame mode, deliberately routed before completed analysis.
use super::{Args, invalid, publish_all};
use ariadne::effects::PreparationOptions;
use ariadne::input::{FileSnapshot, FramePreparation};
use ariadne::investigation::{
    BoundFrameRecovery, FrameStructureDiagnostic, FrameStructureDiagnosticKind,
    FrameStructureLimits, FrameStructureQuestion, active_frame_structure_entry,
    bind_frame_structure,
};
use ariadne::reports::frame_structure as report;
use std::error::Error;
use std::fs;
use std::io::{self, Read, Write};
use std::path::Path;

// This host input cap applies before parsing a policy; the file cannot increase
// the resources required to read and decode itself.
pub(super) const MAX_POLICY_BYTES: u64 = 64 * 1024;

pub(super) fn read_json(path: &Path, max_bytes: u64) -> Result<serde_json::Value, Box<dyn Error>> {
    let mut bytes = Vec::new();
    fs::File::open(path)?
        .take(max_bytes + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > max_bytes {
        return Err(invalid("structural policy input byte budget").into());
    }
    ariadne::reports::strict_json(&bytes)
}

pub(super) fn read_limits(path: &Path) -> Result<FrameStructureLimits, Box<dyn Error>> {
    let policy: FrameStructureLimits = serde_json::from_value(read_json(path, MAX_POLICY_BYTES)?)?;
    policy.validate()?;
    Ok(policy)
}

/// Shared guard/target option files may lower the structural host policy, but
/// cannot raise any of its bounds by declaring larger producer limits.
fn check_override<T: serde::Serialize>(
    supplied: &T,
    host: &T,
    option: &str,
) -> Result<(), Box<dyn Error>> {
    let supplied = serde_json::to_value(supplied)?;
    let host = serde_json::to_value(host)?;
    let fields = supplied
        .as_object()
        .ok_or_else(|| invalid("structural limit override must be an object"))?;
    for (field, value) in fields {
        let value = value
            .as_u64()
            .ok_or_else(|| invalid("structural limit override must be unsigned"))?;
        let cap = host
            .get(field)
            .and_then(serde_json::Value::as_u64)
            .ok_or_else(|| invalid("structural host limit field absent"))?;
        if value > cap {
            return Err(invalid(format!("{option} {field} exceeds structural host policy")).into());
        }
    }
    Ok(())
}

pub(super) fn prepare(
    args: &Args,
) -> Result<ariadne::investigation::BoundFrameStructure, Box<dyn Error>> {
    let (n, m) = args
        .structure_pair
        .ok_or_else(|| invalid("missing structural frame question"))?;
    let policy = args
        .structure_limits
        .as_ref()
        .ok_or_else(|| invalid("missing structural host policy"))?;
    policy.validate()?;
    if n >= policy.max_frames {
        return Err(invalid("structural frame selection exceeds host frame policy").into());
    }
    let mut open = policy.open_limits();
    if args.max_artifact_bytes_explicit {
        if args.max_artifact_bytes > open.max_file_bytes {
            return Err(invalid("--max-artifact-bytes exceeds structural host policy").into());
        }
        open.max_file_bytes = args.max_artifact_bytes;
    }
    let mut preparation = policy.prepare_limits();
    if args.max_starts_explicit {
        if args.limits.max_starts > preparation.max_starts {
            return Err(invalid("--max-starts exceeds structural host policy").into());
        }
        preparation.max_starts = args.limits.max_starts;
    }
    let guard = if let Some(limits) = &args.guard_admission_limits {
        check_override(limits, &policy.guard, "--guard-admission-limits")?;
        limits.clone()
    } else {
        policy.guard.clone()
    };
    let targets = if args.resolve_indirect {
        let limits = if let Some(path) = &args.target_limits {
            let limits: ariadne::bap::target_resolution::Limits =
                serde_json::from_value(read_json(path, 8192)?)?;
            limits.validate()?;
            check_override(&limits, &policy.target, "--target-resolution-limits")?;
            limits
        } else {
            policy.target.clone()
        };
        Some(limits)
    } else {
        None
    };
    // No legacy OpenLimits defaults or full-analysis backend are consulted.
    let snapshot = FileSnapshot::open_minidump(&args.dump, open)?;
    let thread = args
        .frame_thread
        .or_else(|| snapshot.metadata().exception.as_ref().map(|e| e.thread_id))
        .ok_or_else(|| invalid("--thread-id required without an exception thread"))?;
    let chain = snapshot.recover_thread_frames(thread, policy.unwind_limits())?;
    if args
        .alignment_assumptions
        .keys()
        .any(|frame| *frame >= chain.frames.len())
    {
        return Err(invalid("alignment hypothesis selects missing captured activation").into());
    }
    let mut config = ariadne::bap::Config::from_env();
    if let Some(helper) = &args.bap_helper {
        config.helper = helper.clone();
    }
    if let Some(runtime) = &args.bap_runtime {
        config.runtime = runtime.clone();
    }
    let options = PreparationOptions::default();
    let setup = FramePreparation {
        decoder: &args.decoder,
        config: &config,
        options: &options,
        limits: preparation,
    };
    let mut recoveries: Vec<(usize, BoundFrameRecovery)> = Vec::new();
    let mut diagnostics = Vec::new();
    if let Some(last) = chain.frames.len().checked_sub(1) {
        let mut highest = n.min(last);
        // A selected leaf may need an older parent's reached E8 instruction as
        // its entry witness. Retain every such auxiliary parent in the report.
        while highest < last && chain.frames[highest].function_begin.is_none() {
            highest += 1;
        }
        if m <= highest {
            for index in (m..=highest).rev() {
                let parent = recoveries
                    .iter()
                    .find(|(parent, _)| *parent == index + 1)
                    .map(|(_, recovery)| recovery);
                let entry = if let Some(entry) = chain.frames[index].function_begin {
                    entry
                } else if let Some(parent) = parent {
                    match active_frame_structure_entry(&chain, index, parent) {
                        Ok(entry) => entry,
                        Err(error) => {
                            diagnostics.push(FrameStructureDiagnostic::new(
                                index,
                                FrameStructureDiagnosticKind::MissingEntry,
                                error.to_string(),
                            ));
                            continue;
                        }
                    }
                } else {
                    diagnostics.push(FrameStructureDiagnostic::new(
                        index,
                        FrameStructureDiagnosticKind::MissingEntry,
                        "no runtime function entry or verified parent direct-call witness",
                    ));
                    continue;
                };
                let prepared = match snapshot.prepare_frame_structure(
                    &chain,
                    index,
                    entry,
                    parent,
                    &setup,
                    args.assume_windows_call_entry,
                    guard.clone(),
                    targets.clone(),
                ) {
                    Ok(prepared) => prepared,
                    Err(error) => {
                        if args.alignment_assumptions.contains_key(&index) {
                            return Err(error);
                        }
                        diagnostics.push(FrameStructureDiagnostic::from_preparation_error(
                            index,
                            error.as_ref(),
                        ));
                        continue;
                    }
                };
                // Binding failures reject invalid evidence. Only preparation
                // failures become progress diagnostics without a sealed graph.
                let bound = if let Some(sites) = args.alignment_assumptions.get(&index) {
                    snapshot.bind_frame_recovery_hypotheses(
                        &chain,
                        index,
                        &prepared,
                        &sites.iter().copied().collect::<Vec<_>>(),
                        policy,
                    )?
                } else {
                    let recovery = ariadne::recovery::recover(
                        prepared.prepared.request.clone(),
                        policy.recovery_limits(),
                    )?;
                    snapshot.bind_frame_recovery(&chain, index, &prepared, recovery, policy)?
                };
                recoveries.push((index, bound));
            }
        }
    }
    if args.alignment_assumptions.keys().any(|index| {
        !recoveries
            .iter()
            .any(|(frame, bound)| frame == index && bound.alignment_hypotheses().is_some())
    }) {
        return Err(invalid("alignment hypothesis lacks successfully bound selected frame").into());
    }
    let bound = bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: n,
            to_frame: m,
        },
        recoveries,
        diagnostics,
        policy.clone(),
    )?;
    Ok(bound)
}
pub(super) fn run(args: &Args) -> Result<(), Box<dyn Error>> {
    let bound = prepare(args)?;
    let policy = bound.limits();
    if let Some(directory) = &args.output_dir {
        let files = vec![
            ("frame-structure.json", report::render_json(&bound)?),
            ("frame-structure.txt", report::render_text(&bound)?),
            ("frame-structure.dot", report::render_dot(&bound)?),
        ];
        let bytes = files
            .iter()
            .try_fold(0usize, |total, (_, text)| total.checked_add(text.len()));
        if bytes.is_none_or(|bytes| bytes > policy.max_output_bytes) {
            return Err(invalid("structural publication byte budget").into());
        }
        publish_all(directory, &files)?;
    } else {
        let output = match args.format.as_ref().unwrap() {
            ariadne::input::report::ReportFormat::Json => report::render_json(&bound)?,
            ariadne::input::report::ReportFormat::Text => report::render_text(&bound)?,
            ariadne::input::report::ReportFormat::Dot => report::render_dot(&bound)?,
        };
        if output.len() > policy.max_output_bytes {
            return Err(invalid("structural publication byte budget").into());
        }
        io::stdout().lock().write_all(output.as_bytes())?;
    }
    Ok(())
}
