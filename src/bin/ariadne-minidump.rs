//! Evidence-bounded Windows/Linux AMD64 minidump investigator.
use ariadne::effects::PreparationOptions;
use ariadne::input::report::{ReportFormat, render};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "usage: ariadne-minidump DUMP --decoder-reference PATH --entry VA_HEX [--entry VA_HEX ...] [--seed VA_HEX ...] [--seed-exception-rip] [--max-starts N] [--max-artifact-bytes N] [--resolve-indirect-targets [--target-resolution-limits JSON]] [--list-frame-paths N:M --path-count-bound NP [--thread-id ID] [--frame-path-limits JSON]] [--stateflow-input SEMANTICS_JSON] [--explain-fault-address VA --memory-access N] [--explanation-only] [--assess-zero-address VA --memory-access N] [--assess-zero-base-offset VA --memory-access N] [--assess-memory-provenance LOAD_VA --memory-access N] [--assessment-only] [--analysis-backend rust|bap] [--bap-core-dir DIR] [--bap-core-response-timeout-ms N] [--bap-helper PATH] [--bap-runtime DIR] (--format text|dot|json | --output-dir NEW_DIR)"
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
    resolve_indirect: bool,
    target_limits: Option<PathBuf>,
    max_artifact_bytes: usize,
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
    memory_provenance_site: Option<u64>,
    frame_pair: Option<(usize, usize)>,
    path_count_bound: Option<usize>,
    frame_thread: Option<u32>,
    frame_limits: Option<PathBuf>,
    assessment_only: bool,
    memory_access: Option<usize>,
    explanation_only: bool,
    bap_helper: Option<PathBuf>,
    bap_runtime: Option<PathBuf>,
    analysis_backend: String,
    bap_core_dir: PathBuf,
    bap_response_timeout_ms: u64,
}
fn arguments() -> Result<Args, Box<dyn Error>> {
    let mut args = std::env::args_os().skip(1);
    let dump = args.next().ok_or_else(|| invalid(usage()))?;
    if dump.to_string_lossy().starts_with("--") {
        return Err(invalid(usage()).into());
    }
    let mut resolve_indirect = false;
    let mut target_limits = None;
    let mut max_artifact_bytes = None;
    let mut bap_response_timeout_ms = None;
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
    let mut memory_provenance_site = None;
    let mut frame_pair = None;
    let mut path_count_bound = None;
    let mut frame_thread = None;
    let mut frame_limits = None;
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
        if flag == "--resolve-indirect-targets" {
            if resolve_indirect {
                return Err(invalid("duplicate --resolve-indirect-targets").into());
            }
            resolve_indirect = true;
            continue;
        }
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
            "--bap-core-response-timeout-ms" if bap_response_timeout_ms.is_none() => {
                let timeout: u64 = value
                    .to_str()
                    .ok_or_else(|| invalid("non-UTF8 response timeout"))?
                    .parse()?;
                if timeout == 0 || timeout > 60000 {
                    return Err(invalid("response timeout must be 1..60000 ms").into());
                }
                bap_response_timeout_ms = Some(timeout);
            }
            "--target-resolution-limits" if target_limits.is_none() => {
                target_limits = Some(PathBuf::from(value))
            }
            "--max-artifact-bytes" if max_artifact_bytes.is_none() => {
                let count: usize = value
                    .to_str()
                    .ok_or_else(|| invalid("non-UTF8 artifact limit"))?
                    .parse()?;
                if count == 0 || count > 2 * 1024 * 1024 * 1024 {
                    return Err(invalid("artifact limit must be positive and at most 2 GiB").into());
                }
                max_artifact_bytes = Some(count);
            }
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
            "--list-frame-paths" if frame_pair.is_none() => {
                let pair = value
                    .to_str()
                    .ok_or_else(|| invalid("non-UTF8 frame indices"))?;
                let (n, m) = pair
                    .split_once(':')
                    .ok_or_else(|| invalid("frame query requires N:M"))?;
                frame_pair = Some((parse_index(n)?, parse_index(m)?));
            }
            "--path-count-bound" if path_count_bound.is_none() => {
                path_count_bound = Some(parse_index(
                    value.to_str().ok_or_else(|| invalid("non-UTF8 NP"))?,
                )?);
            }
            "--thread-id" if frame_thread.is_none() => {
                frame_thread = Some(
                    u32::try_from(parse_index(
                        value
                            .to_str()
                            .ok_or_else(|| invalid("non-UTF8 thread id"))?,
                    )?)
                    .map_err(|_| invalid("thread id overflow"))?,
                );
            }
            "--frame-path-limits" if frame_limits.is_none() => {
                frame_limits = Some(PathBuf::from(value));
            }
            "--assess-memory-provenance" if memory_provenance_site.is_none() => {
                memory_provenance_site = Some(parse_va(
                    value
                        .to_str()
                        .ok_or_else(|| invalid("non-UTF8 memory provenance VA"))?,
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
    if (entries.is_empty() && frame_pair.is_none())
        || decoder.is_none()
        || format.is_some() == output_dir.is_some()
    {
        return Err(invalid(usage()).into());
    }
    if usize::from(explain_site.is_some())
        + usize::from(assess_site.is_some())
        + usize::from(assess_offset_site.is_some())
        + usize::from(memory_provenance_site.is_some())
        + usize::from(frame_pair.is_some())
        > 1
    {
        return Err(invalid("choose one explanation or assessment question").into());
    }
    if frame_pair.is_some() != path_count_bound.is_some()
        || (frame_pair.is_none() && (frame_thread.is_some() || frame_limits.is_some()))
    {
        return Err(invalid(
            "frame options require --list-frame-paths N:M and --path-count-bound NP",
        )
        .into());
    }
    if let Some((n, m)) = frame_pair {
        if n < m
            || path_count_bound == Some(0)
            || path_count_bound.is_some_and(|np| np > 4097)
            || n >= 64
        {
            return Err(
                invalid("invalid frame ordering/count bound or frame profile limit").into(),
            );
        }
        if !entries.is_empty()
            || !seeds.is_empty()
            || exception_rip_seed
            || stateflow_input.is_some()
            || assessment_only
            || explanation_only
            || memory_access.is_some()
        {
            return Err(invalid("frame query uses explicit per-frame roots; cannot combine with entry/seed/stateflow/other question modes").into());
        }
    }
    if (explain_site.is_some()
        || assess_site.is_some()
        || assess_offset_site.is_some()
        || memory_provenance_site.is_some())
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
        && (assess_site.is_none()
            && assess_offset_site.is_none()
            && memory_provenance_site.is_none()
            || output_dir.is_some()
            || stateflow_input.is_some())
    {
        return Err(invalid(
            "--assessment-only requires an assessment with --format and no stateflow input",
        )
        .into());
    }
    if (assess_site.is_some() || assess_offset_site.is_some() || memory_provenance_site.is_some())
        && (stateflow_input.is_some()
            || explanation_only
            || (!assessment_only && output_dir.is_none()))
    {
        return Err(invalid("assessment requires --assessment-only --format or --output-dir, without stateflow/explanation").into());
    }
    if target_limits.is_some() && !resolve_indirect {
        return Err(
            invalid("--target-resolution-limits requires --resolve-indirect-targets").into(),
        );
    }
    if resolve_indirect
        && (frame_pair.is_some() || stateflow_input.is_some() || memory_provenance_site.is_some())
    {
        return Err(invalid("target resolution cannot combine with frame-path, supplied-stateflow or memory-refinement modes in this profile").into());
    }
    Ok(Args {
        resolve_indirect,
        target_limits,
        max_artifact_bytes: max_artifact_bytes
            .unwrap_or_else(|| OpenLimits::default().max_file_bytes),
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
        memory_provenance_site,
        frame_pair,
        path_count_bound,
        frame_thread,
        frame_limits,
        assessment_only,
        memory_access,
        explanation_only,
        bap_helper,
        bap_runtime,
        analysis_backend: analysis_backend.unwrap_or_else(|| "bap".into()),
        bap_core_dir: bap_core_dir
            .or_else(|| std::env::var_os("ARIADNE_BAP_CORE_DIR").map(PathBuf::from))
            .unwrap_or_else(|| PathBuf::from("target/bap-core-native")),
        bap_response_timeout_ms: bap_response_timeout_ms.unwrap_or(10000),
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

fn parse_index(s: &str) -> Result<usize, Box<dyn Error>> {
    let value = if let Some(s) = s.strip_prefix("0x") {
        usize::from_str_radix(s, 16)
    } else {
        s.parse()
    };
    Ok(value.map_err(|_| invalid("invalid unsigned frame/count/thread number"))?)
}
fn frame_query(args: &Args, snapshot: &FileSnapshot) -> Result<(), Box<dyn Error>> {
    use ariadne::investigation::{
        FramePathLimits, FramePathQuestion, FrameRecoveryLimits, active_frame_entry,
        bind_frame_paths, list_frame_paths,
    };
    let (n, m) = args
        .frame_pair
        .ok_or_else(|| invalid("missing frame question"))?;
    let thread = args
        .frame_thread
        .or_else(|| snapshot.metadata().exception.as_ref().map(|e| e.thread_id))
        .ok_or_else(|| invalid("--thread-id required without an exception thread"))?;
    let limits = if let Some(path) = &args.frame_limits {
        if fs::metadata(path)?.len() > 8192 {
            return Err(invalid("frame limit input byte budget").into());
        }
        ariadne::reports::decode_frame_path_limits(&fs::read(path)?)?
    } else {
        FramePathLimits::default()
    };
    let chain = snapshot.recover_thread_frames(
        thread,
        FrameRecoveryLimits {
            max_frames: (n + 2).min(64),
            ..FrameRecoveryLimits::default()
        },
    )?;
    let mut config = ariadne::bap::Config::from_env();
    if let Some(helper) = &args.bap_helper {
        config.helper = helper.clone();
    }
    if let Some(runtime) = &args.bap_runtime {
        config.runtime = runtime.clone();
    }
    let options = PreparationOptions::default();
    let setup = ariadne::input::FramePreparation {
        decoder: &args.decoder,
        config: &config,
        options: &options,
        limits: args.limits.clone(),
    };
    let mut queries = Vec::new();
    if n < chain.frames.len() {
        for index in (0..=n).rev() {
            let entry = if let Some(entry) = chain.frames[index].function_begin {
                entry
            } else if let Some((parent_index, parent)) = queries.last() {
                if *parent_index != index + 1 {
                    break;
                }
                match active_frame_entry(&chain, index, parent) {
                    Ok(entry) => entry,
                    Err(_) => break,
                }
            } else if index == 0 && n == m {
                chain.frames[0].pc
            } else {
                break;
            };
            let prepared = snapshot.prepare_frame_with_bap(&chain, index, entry, &setup)?;
            let completed = if args.analysis_backend == "bap" {
                let native = ariadne::bap::core_adapter::NativeAnalyzer::from_capture(
                    &ariadne::bap::core_session::CoreConfig {
                        timeout: std::time::Duration::from_millis(args.bap_response_timeout_ms),
                        ..ariadne::bap::core_session::CoreConfig::from_directory(
                            args.bap_core_dir.clone(),
                        )
                    },
                    &format!("frame-path-{index}"),
                    &prepared,
                )?;
                native.complete()?
            } else {
                ariadne::CompletedAnalysis::from_analyzer(ariadne::Analyzer::new(
                    prepared.prepared.request.clone(),
                )?)
            };
            queries.push((
                index,
                ariadne::input::investigation::bind_investigation(&prepared, &completed)?,
            ));
        }
    }
    let bound = bind_frame_paths(chain, queries)?;
    let listing = list_frame_paths(
        &bound,
        FramePathQuestion {
            from_frame: n,
            to_frame: m,
            np: args.path_count_bound.unwrap(),
        },
        limits,
    )?;
    if let Some(directory) = &args.output_dir {
        let files = [
            ("frame-paths.txt", ariadne::reports::Format::Text),
            ("frame-paths.json", ariadne::reports::Format::Json),
            ("frame-paths.dot", ariadne::reports::Format::Dot),
        ]
        .map(|(name, format)| {
            Ok((
                name,
                ariadne::reports::render_frame_paths(&listing, format)?,
            ))
        })
        .into_iter()
        .collect::<Result<Vec<_>, Box<dyn Error>>>()?;
        publish_all(directory, &files)?;
    } else {
        let format = match args.format.as_ref().unwrap() {
            ReportFormat::Text => ariadne::reports::Format::Text,
            ReportFormat::Json => ariadne::reports::Format::Json,
            ReportFormat::Dot => ariadne::reports::Format::Dot,
        };
        io::stdout()
            .lock()
            .write_all(ariadne::reports::render_frame_paths(&listing, format)?.as_bytes())?;
    }
    Ok(())
}
fn run() -> Result<(), Box<dyn Error>> {
    let mut args = arguments()?;
    let snapshot = FileSnapshot::open_minidump(
        &args.dump,
        OpenLimits {
            max_file_bytes: args.max_artifact_bytes,
            ..OpenLimits::default()
        },
    )?;
    if args.frame_pair.is_some() {
        return frame_query(&args, &snapshot);
    }
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
    let prepared = if args.resolve_indirect {
        let target_limits = if let Some(path) = &args.target_limits {
            if fs::metadata(path)?.len() > 8192 {
                return Err(invalid("target resolution limits byte budget").into());
            }
            serde_json::from_value(ariadne::reports::strict_json(&fs::read(path)?)?)?
        } else {
            ariadne::bap::target_resolution::Limits::default()
        };
        snapshot.prepare_with_bap_target_resolution(
            &query,
            &args.decoder,
            &config,
            &options,
            args.limits,
            target_limits,
        )?
    } else if args.memory_provenance_site.is_some() {
        snapshot.prepare_with_bap_refinement(
            &query,
            &args.decoder,
            &config,
            &options,
            args.limits,
        )?
    } else {
        snapshot.prepare_with_bap(&query, &args.decoder, &config, &options, args.limits)?
    };
    let mut core_config = ariadne::bap::core_session::CoreConfig::from_directory(args.bap_core_dir);
    core_config.timeout = std::time::Duration::from_millis(args.bap_response_timeout_ms);
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
    let memory_assessment = if let Some(site) = args.memory_provenance_site {
        let bound = ariadne::input::investigation::bind_memory_refinement(&prepared, &analyzer)?;
        Some(ariadne::investigation::assess_memory_origins(
            &bound,
            ariadne::investigation::FaultAddressQuestion {
                site,
                memory_access: args.memory_access.unwrap(),
            },
            ariadne::investigation::MemoryRefinementLimits::default(),
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
        if let Some(value) = &memory_assessment {
            for (name, format) in [
                ("memory-provenance.txt", ariadne::reports::Format::Text),
                ("memory-provenance.json", ariadne::reports::Format::Json),
                ("memory-provenance.dot", ariadne::reports::Format::Dot),
            ] {
                reports.push((
                    name,
                    ariadne::reports::render_memory_provenance(value, format)?,
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
            if let Some(value) = &memory_assessment {
                ariadne::reports::render_memory_provenance(value, format)?
            } else if let Some(value) = &offset_assessment {
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
