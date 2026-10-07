//! Evidence-bounded Windows/Linux AMD64 minidump investigator.
use ariadne::effects::PreparationOptions;
use ariadne::input::report::{ReportFormat, render};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "usage: ariadne-minidump DUMP --decoder-reference PATH --entry VA_HEX [--entry VA_HEX ...] [--seed VA_HEX ...] [--seed-exception-rip] [--max-starts N] [--stateflow-input SEMANTICS_JSON] [--explain-fault-address VA --memory-access N] [--explanation-only] [--assess-zero-address VA --memory-access N] [--assess-zero-base-offset VA --memory-access N] [--assessment-only] [--analysis-backend rust|bap] [--bap-core-dir DIR] [--bap-helper PATH] [--bap-runtime DIR] (--format text|dot|json | --output-dir NEW_DIR)"
}
fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message.into())
}
fn path_exists(path: &Path) -> io::Result<bool> {
    match fs::symlink_metadata(path) {
        Ok(_) => Ok(true),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(error),
    }
}
fn parse_va(text: &str) -> Result<u64, Box<dyn Error>> {
    let digits = text
        .strip_prefix("0x")
        .or_else(|| text.strip_prefix("0X"))
        .unwrap_or(text);
    if digits.is_empty() || !digits.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(invalid(format!("invalid hexadecimal VA: {text}")).into());
    }
    Ok(u64::from_str_radix(digits, 16)?)
}

struct Args {
    dump: PathBuf,
    decoder: PathBuf,
    entries: ariadne::AddressSet,
    seeds: ariadne::AddressSet,
    exception_rip_seed: bool,
    limits: PrepareLimits,
    format: Option<ReportFormat>,
    output_dir: Option<PathBuf>,
    stateflow_input: Option<PathBuf>,
    explain_site: Option<u64>,
    assess_site: Option<u64>,
    assess_offset_site: Option<u64>,
    assessment_only: bool,
    memory_access: Option<usize>,
    explanation_only: bool,
    bap_helper: Option<PathBuf>,
    bap_runtime: Option<PathBuf>,
    analysis_backend: String,
    bap_core_dir: PathBuf,
}
fn arguments() -> Result<Args, Box<dyn Error>> {
    let mut args = std::env::args_os().skip(1);
    let dump = args.next().ok_or_else(|| invalid(usage()))?;
    if dump.to_string_lossy().starts_with("--") {
        return Err(invalid(usage()).into());
    }
    let mut decoder = None;
    let mut entries = ariadne::AddressSet::new();
    let mut seeds = ariadne::AddressSet::new();
    let mut exception_rip_seed = false;
    let mut limits = PrepareLimits::default();
    let mut max_starts_set = false;
    let mut format = None;
    let mut output_dir = None;
    let mut stateflow_input = None;
    let mut explain_site = None;
    let mut assess_site = None;
    let mut assess_offset_site = None;
    let mut assessment_only = false;
    let mut memory_access = None;
    let mut explanation_only = false;
    let mut bap_helper = None;
    let mut bap_runtime = None;
    let mut analysis_backend = None;
    let mut bap_core_dir = None;
    while let Some(flag) = args.next() {
        let flag = flag
            .to_str()
            .ok_or_else(|| invalid("non-UTF-8 option name"))?;
        if flag == "--assessment-only" {
            if assessment_only {
                return Err(invalid("duplicate --assessment-only").into());
            }
            assessment_only = true;
            continue;
        }
        if flag == "--explanation-only" {
            if explanation_only {
                return Err(invalid("duplicate --explanation-only").into());
            }
            explanation_only = true;
            continue;
        }
        if flag == "--seed-exception-rip" {
            if exception_rip_seed {
                return Err(invalid("duplicate --seed-exception-rip").into());
            }
            exception_rip_seed = true;
            continue;
        }
        let value = args.next().ok_or_else(|| invalid(usage()))?;
        match flag {
            "--analysis-backend" if analysis_backend.is_none() => {
                let backend = value.to_str().ok_or_else(|| invalid("non-UTF-8 backend"))?;
                if !["rust", "bap"].contains(&backend) {
                    return Err(invalid("unknown analysis backend").into());
                }
                analysis_backend = Some(backend.to_owned());
            }
            "--bap-core-dir" if bap_core_dir.is_none() => bap_core_dir = Some(PathBuf::from(value)),
            "--decoder-reference" | "--decoder" if decoder.is_none() => {
                decoder = Some(PathBuf::from(value))
            }
            "--entry" => {
                entries.insert(parse_va(
                    value.to_str().ok_or_else(|| invalid("non-UTF-8 VA"))?,
                )?);
            }
            "--seed" => {
                seeds.insert(parse_va(
                    value.to_str().ok_or_else(|| invalid("non-UTF-8 VA"))?,
                )?);
            }
            "--max-starts" if !max_starts_set => {
                let text = value.to_str().ok_or_else(|| invalid("non-UTF-8 limit"))?;
                let count: usize = text.parse()?;
                if count == 0 {
                    return Err(invalid("--max-starts must be positive").into());
                }
                limits.max_starts = count;
                max_starts_set = true;
            }
            "--format" if format.is_none() => {
                format = Some(match value.to_str() {
                    Some("text") => ReportFormat::Text,
                    Some("dot") => ReportFormat::Dot,
                    Some("json") => ReportFormat::Json,
                    _ => return Err(invalid("--format expects text, dot or json").into()),
                });
            }
            "--output-dir" if output_dir.is_none() => output_dir = Some(PathBuf::from(value)),
            "--semantics-backend" => {
                return Err(invalid(
                    "--semantics-backend was removed; BAP is the sole minidump semantic backend",
                )
                .into());
            }
            "--bap-helper" if bap_helper.is_none() => bap_helper = Some(PathBuf::from(value)),
            "--bap-runtime" if bap_runtime.is_none() => bap_runtime = Some(PathBuf::from(value)),
            "--assess-zero-address" if assess_site.is_none() => {
                assess_site = Some(parse_va(
                    value
                        .to_str()
                        .ok_or_else(|| invalid("non-UTF8 assessment VA"))?,
                )?);
            }
            "--assess-zero-base-offset" if assess_offset_site.is_none() => {
                assess_offset_site = Some(parse_va(
                    value
                        .to_str()
                        .ok_or_else(|| invalid("non-UTF8 assessment VA"))?,
                )?);
            }
            "--explain-fault-address" if explain_site.is_none() => {
                explain_site = Some(parse_va(
                    value
                        .to_str()
                        .ok_or_else(|| invalid("non-UTF8 explanation VA"))?,
                )?);
            }
            "--memory-access" if memory_access.is_none() => {
                memory_access = Some(
                    value
                        .to_str()
                        .ok_or_else(|| invalid("non-UTF8 memory access"))?
                        .parse()?,
                );
            }
            "--stateflow-input" if stateflow_input.is_none() => {
                stateflow_input = Some(PathBuf::from(value))
            }
            _ => return Err(invalid(format!("unknown or duplicate option: {flag}")).into()),
        }
    }
    if entries.is_empty() || decoder.is_none() || format.is_some() == output_dir.is_some() {
        return Err(invalid(usage()).into());
    }
    if usize::from(explain_site.is_some())
        + usize::from(assess_site.is_some())
        + usize::from(assess_offset_site.is_some())
        > 1
    {
        return Err(invalid("choose one explanation or assessment question").into());
    }
    if (explain_site.is_some() || assess_site.is_some() || assess_offset_site.is_some())
        != memory_access.is_some()
    {
        return Err(invalid(
            "a question requires --explain-fault-address or --assess-zero-address, and --memory-access",
        )
        .into());
    }
    if explanation_only
        && (explain_site.is_none() || output_dir.is_some() || stateflow_input.is_some())
    {
        return Err(invalid(
            "--explanation-only requires an explanation with --format and no stateflow input",
        )
        .into());
    }
    if assessment_only
        && (assess_site.is_none() && assess_offset_site.is_none()
            || output_dir.is_some()
            || stateflow_input.is_some())
    {
        return Err(invalid(
            "--assessment-only requires an assessment with --format and no stateflow input",
        )
        .into());
    }
    if (assess_site.is_some() || assess_offset_site.is_some())
        && (stateflow_input.is_some()
            || explanation_only
            || (!assessment_only && output_dir.is_none()))
    {
        return Err(invalid("assessment requires --assessment-only --format or --output-dir, without stateflow/explanation").into());
    }
    Ok(Args {
        dump: PathBuf::from(dump),
        decoder: decoder.unwrap(),
        entries,
        seeds,
        exception_rip_seed,
        limits,
        format,
        output_dir,
        stateflow_input,
        explain_site,
        assess_site,
        assess_offset_site,
        assessment_only,
        memory_access,
        explanation_only,
        bap_helper,
        bap_runtime,
        analysis_backend: analysis_backend.unwrap_or_else(|| "bap".into()),
        bap_core_dir: bap_core_dir
            .or_else(|| std::env::var_os("ARIADNE_BAP_CORE_DIR").map(PathBuf::from))
            .unwrap_or_else(|| PathBuf::from("target/bap-core-native")),
    })
}

fn publish_all(directory: &Path, reports: &[(&str, String)]) -> Result<(), Box<dyn Error>> {
    if path_exists(directory)? {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            directory.display().to_string(),
        )
        .into());
    }
    let parent = directory
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let name = directory
        .file_name()
        .ok_or_else(|| invalid("output directory needs a name"))?;
    let mut staging = None;
    for suffix in 0..100 {
        let candidate = parent.join(format!(
            ".{}.ariadne-tmp-{}-{suffix}",
            name.to_string_lossy(),
            std::process::id(),
        ));
        match fs::create_dir(&candidate) {
            Ok(()) => {
                staging = Some(candidate);
                break;
            }
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(error.into()),
        }
    }
    let staging = staging.ok_or_else(|| invalid("unable to reserve temporary output directory"))?;
    let publication = (|| -> io::Result<()> {
        for (name, contents) in reports {
            let mut output = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(staging.join(name))?;
            output.write_all(contents.as_bytes())?;
            output.sync_all()?;
        }
        if path_exists(directory)? {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                directory.display().to_string(),
            ));
        }
        fs::rename(&staging, directory)
    })();
    if publication.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    publication?;
    Ok(())
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = arguments()?;
    let snapshot = FileSnapshot::open_minidump(&args.dump, OpenLimits::default())?;
    if args.exception_rip_seed {
        let rip = snapshot
            .metadata()
            .exception
            .as_ref()
            .and_then(|exception| exception.registers.get("rip"))
            .ok_or_else(|| invalid("exception context has no valid RIP"))?;
        args.seeds.insert(*rip);
    }
    if let Some(site) = args.assess_site {
        args.seeds.insert(site);
    }
    if let Some(site) = args.assess_offset_site {
        args.seeds.insert(site);
    }
    if let Some(site) = args.explain_site {
        args.seeds.insert(site);
    }
    let query = AnalysisQuery {
        entry_points: args.entries,
        slice_seeds: args.seeds,
    };
    let options = PreparationOptions::default();
    let mut config = ariadne::bap::Config::from_env();
    if let Some(helper) = args.bap_helper {
        config.helper = helper;
    }
    if let Some(runtime) = args.bap_runtime {
        config.runtime = runtime;
    }
    let prepared =
        snapshot.prepare_with_bap(&query, &args.decoder, &config, &options, args.limits)?;
    let core_config = ariadne::bap::core_session::CoreConfig::from_directory(args.bap_core_dir);
    let (analyzer, backend_identity) = if args.analysis_backend == "bap" {
        let native = ariadne::bap::core_adapter::NativeAnalyzer::from_capture(
            &core_config,
            "minidump-analysis",
            &prepared,
        )?;
        let identity = native.identity().clone();
        (native.complete()?, Some(identity))
    } else {
        (
            ariadne::CompletedAnalysis::from_analyzer(ariadne::Analyzer::new(
                prepared.prepared.request.clone(),
            )?),
            None,
        )
    };
    let explanation = if let Some(site) = args.explain_site {
        let bound = ariadne::input::investigation::bind_investigation(&prepared, &analyzer)?;
        Some(ariadne::investigation::explain_fault_address(
            &bound,
            ariadne::investigation::FaultAddressQuestion {
                site,
                memory_access: args.memory_access.unwrap(),
            },
            ariadne::investigation::ExplainLimits::default(),
        )?)
    } else {
        None
    };
    let assessment = if let Some(site) = args.assess_site {
        let bound = ariadne::input::investigation::bind_fault_context(&prepared, &analyzer)?;
        Some(ariadne::investigation::assess_zero_address(
            &bound,
            ariadne::investigation::FaultAddressQuestion {
                site,
                memory_access: args.memory_access.unwrap(),
            },
            ariadne::investigation::AssessmentLimits::default(),
        )?)
    } else {
        None
    };
    let offset_assessment = if let Some(site) = args.assess_offset_site {
        let bound = ariadne::input::investigation::bind_zero_base_offset(
            &prepared,
            &analyzer,
            ariadne::investigation::FaultAddressQuestion {
                site,
                memory_access: args.memory_access.unwrap(),
            },
        )?;
        Some(ariadne::investigation::assess_zero_base_offset(
            &bound,
            ariadne::investigation::ZeroBaseOffsetLimits::default(),
        )?)
    } else {
        None
    };
    let mut stateflow = if let Some(path) = args.stateflow_input {
        let bytes = fs::read(path)?;
        let semantics = ariadne::reports::decode_semantics(&bytes)?;
        let handoff = ariadne::machine_state::prepare_from_recovery(&analyzer, semantics)?;
        let state_result = if args.analysis_backend == "bap" {
            ariadne::bap::stateflow_adapter::NativeStateflow::new(
                &core_config,
                "minidump-stateflow",
                handoff.request,
            )?
            .finish()?
        } else {
            ariadne::machine_state::analyze(handoff.request)?
        };
        Some(ariadne::reports::machine_report(
            &state_result,
            Some(&handoff.context),
            Some(&ariadne::reports::sha256(&bytes)),
        )?)
    } else {
        None
    };
    let result = analyzer.into_result();
    let render = |p: &ariadne::input::FilePreparedAnalysis,
                  r: &ariadne::AnalysisResult,
                  f: ReportFormat,
                  seed: bool|
     -> Result<String, Box<dyn Error>> {
        let original = render(p, r, f, seed)?;
        let Some(identity) = &backend_identity else {
            return Ok(original);
        };
        Ok(match f {
            ReportFormat::Json => {
                let mut report: serde_json::Value = serde_json::from_str(&original)?;
                report["analysis_backend"] = identity.clone();
                format!("{}\n", serde_json::to_string_pretty(&report)?)
            }
            ReportFormat::Text => format!("{original}analysis backend: {identity}\n"),
            ReportFormat::Dot => format!("// analysis backend: {identity}\n{original}"),
        })
    };
    if let Some(report) = stateflow.as_mut() {
        // Keep the independently versioned minidump evidence beside the
        // stateflow result; preparation gaps cannot vanish in this output mode.
        report["minidump_report"] = serde_json::from_str(&render(
            &prepared,
            &result,
            ReportFormat::Json,
            args.exception_rip_seed,
        )?)?;
    }
    if let Some(directory) = args.output_dir {
        let mut reports = vec![
            (
                "report.txt",
                render(
                    &prepared,
                    &result,
                    ReportFormat::Text,
                    args.exception_rip_seed,
                )?,
            ),
            (
                "report.dot",
                render(
                    &prepared,
                    &result,
                    ReportFormat::Dot,
                    args.exception_rip_seed,
                )?,
            ),
            (
                "report.json",
                render(
                    &prepared,
                    &result,
                    ReportFormat::Json,
                    args.exception_rip_seed,
                )?,
            ),
        ];
        if let Some(stateflow) = &stateflow {
            for (name, format) in [
                ("machine-state.txt", ariadne::reports::Format::Text),
                ("machine-state.dot", ariadne::reports::Format::Dot),
                ("machine-state.json", ariadne::reports::Format::Json),
            ] {
                reports.push((name, ariadne::reports::render_report(stateflow, format)?));
            }
        }
        if let Some(explanation) = &explanation {
            for (name, format) in [
                ("explanation.txt", ariadne::reports::Format::Text),
                ("explanation.json", ariadne::reports::Format::Json),
                ("explanation.dot", ariadne::reports::Format::Dot),
            ] {
                reports.push((
                    name,
                    ariadne::reports::render_explanation(explanation, format)?,
                ));
            }
        }
        if let Some(value) = &assessment {
            for (name, format) in [
                (
                    "zero-address-assessment.txt",
                    ariadne::reports::Format::Text,
                ),
                (
                    "zero-address-assessment.json",
                    ariadne::reports::Format::Json,
                ),
                ("zero-address-assessment.dot", ariadne::reports::Format::Dot),
            ] {
                reports.push((name, ariadne::reports::render_zero_address(value, format)?));
            }
        }
        if let Some(value) = &offset_assessment {
            for (name, format) in [
                (
                    "zero-base-offset-assessment.txt",
                    ariadne::reports::Format::Text,
                ),
                (
                    "zero-base-offset-assessment.json",
                    ariadne::reports::Format::Json,
                ),
                (
                    "zero-base-offset-assessment.dot",
                    ariadne::reports::Format::Dot,
                ),
            ] {
                reports.push((
                    name,
                    ariadne::reports::render_zero_base_offset(value, format)?,
                ));
            }
        }
        publish_all(&directory, &reports)?;
    } else {
        let output = if args.assessment_only {
            let format = match args.format.unwrap() {
                ReportFormat::Text => ariadne::reports::Format::Text,
                ReportFormat::Json => ariadne::reports::Format::Json,
                ReportFormat::Dot => ariadne::reports::Format::Dot,
            };
            if let Some(value) = &offset_assessment {
                ariadne::reports::render_zero_base_offset(value, format)?
            } else {
                ariadne::reports::render_zero_address(assessment.as_ref().unwrap(), format)?
            }
        } else if args.explanation_only {
            ariadne::reports::render_explanation(
                explanation.as_ref().unwrap(),
                match args.format.unwrap() {
                    ReportFormat::Text => ariadne::reports::Format::Text,
                    ReportFormat::Dot => ariadne::reports::Format::Dot,
                    ReportFormat::Json => ariadne::reports::Format::Json,
                },
            )?
        } else if let Some(stateflow) = &stateflow {
            ariadne::reports::render_report(
                stateflow,
                match args.format.unwrap() {
                    ReportFormat::Text => ariadne::reports::Format::Text,
                    ReportFormat::Dot => ariadne::reports::Format::Dot,
                    ReportFormat::Json => ariadne::reports::Format::Json,
                },
            )?
        } else {
            render(
                &prepared,
                &result,
                args.format.unwrap(),
                args.exception_rip_seed,
            )?
        };
        let output =
            if let Some(explanation) = explanation.as_ref().filter(|_| !args.explanation_only) {
                match args.format.unwrap() {
                    ReportFormat::Json => {
                        let mut value: serde_json::Value = serde_json::from_str(&output)?;
                        value["investigation_explanation"] =
                            ariadne::reports::encode_explanation(explanation)?;
                        format!("{}\n", serde_json::to_string_pretty(&value)?)
                    }
                    ReportFormat::Text => format!(
                        "{output}\n{}",
                        ariadne::reports::render_explanation(
                            explanation,
                            ariadne::reports::Format::Text
                        )?
                    ),
                    ReportFormat::Dot => format!(
                        "// investigation_explanation: {}\n{output}",
                        ariadne::reports::encode_explanation(explanation)?
                    ),
                }
            } else {
                output
            };
        io::stdout().lock().write_all(output.as_bytes())?;
    }
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("ariadne-minidump: {error}");
        std::process::exit(1);
    }
}
