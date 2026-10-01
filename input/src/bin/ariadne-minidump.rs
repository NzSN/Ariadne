//! Evidence-bounded Windows/Linux AMD64 minidump investigator.
use ariadne::effects::PreparationOptions;
use ariadne_input::report::{ReportFormat, render};
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::error::Error;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "usage: ariadne-minidump DUMP --decoder-reference PATH --entry VA_HEX [--entry VA_HEX ...] [--seed VA_HEX ...] [--seed-exception-rip] [--max-starts N] [--stateflow-input SEMANTICS_JSON] [--bap-helper PATH] [--bap-runtime DIR] (--format text|dot|json | --output-dir NEW_DIR)"
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
    bap_helper: Option<PathBuf>,
    bap_runtime: Option<PathBuf>,
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
    let mut bap_helper = None;
    let mut bap_runtime = None;
    while let Some(flag) = args.next() {
        let flag = flag
            .to_str()
            .ok_or_else(|| invalid("non-UTF-8 option name"))?;
        if flag == "--seed-exception-rip" {
            if exception_rip_seed {
                return Err(invalid("duplicate --seed-exception-rip").into());
            }
            exception_rip_seed = true;
            continue;
        }
        let value = args.next().ok_or_else(|| invalid(usage()))?;
        match flag {
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
            "--stateflow-input" if stateflow_input.is_none() => {
                stateflow_input = Some(PathBuf::from(value))
            }
            _ => return Err(invalid(format!("unknown or duplicate option: {flag}")).into()),
        }
    }
    if entries.is_empty() || decoder.is_none() || format.is_some() == output_dir.is_some() {
        return Err(invalid(usage()).into());
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
        bap_helper,
        bap_runtime,
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
    let query = AnalysisQuery {
        entry_points: args.entries,
        slice_seeds: args.seeds,
    };
    let options = PreparationOptions::default();
    let mut config = ariadne_bap::Config::from_env();
    if let Some(helper) = args.bap_helper {
        config.helper = helper;
    }
    if let Some(runtime) = args.bap_runtime {
        config.runtime = runtime;
    }
    let prepared =
        snapshot.prepare_with_bap(&query, &args.decoder, &config, &options, args.limits)?;
    let mut analyzer = ariadne::Analyzer::new(prepared.prepared.request.clone())?;
    while analyzer.step() {}
    let mut stateflow = if let Some(path) = args.stateflow_input {
        let bytes = fs::read(path)?;
        let semantics = ariadne_reports::decode_semantics(&bytes)?;
        let handoff = ariadne::machine_state::prepare_from_recovery(&analyzer, semantics)?;
        let state_result = ariadne::machine_state::analyze(handoff.request)?;
        Some(ariadne_reports::machine_report(
            &state_result,
            Some(&handoff.context),
            Some(&ariadne_reports::sha256(&bytes)),
        )?)
    } else {
        None
    };
    let result = analyzer.finish();
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
                ("machine-state.txt", ariadne_reports::Format::Text),
                ("machine-state.dot", ariadne_reports::Format::Dot),
                ("machine-state.json", ariadne_reports::Format::Json),
            ] {
                reports.push((name, ariadne_reports::render_report(stateflow, format)?));
            }
        }
        publish_all(&directory, &reports)?;
    } else {
        let output = if let Some(stateflow) = &stateflow {
            ariadne_reports::render_report(
                stateflow,
                match args.format.unwrap() {
                    ReportFormat::Text => ariadne_reports::Format::Text,
                    ReportFormat::Dot => ariadne_reports::Format::Dot,
                    ReportFormat::Json => ariadne_reports::Format::Json,
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
