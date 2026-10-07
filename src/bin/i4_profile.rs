//! Native-default I4 phase profile on the exact capture/query, without changing reports.
use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
use ariadne::effects::PreparationOptions;
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PreparationError, PrepareLimits,
    investigation::bind_investigation,
    report::{ReportFormat, render},
};
use ariadne::investigation::{ExplainLimits, FaultAddressQuestion, explain_fault_address};
use ariadne::reports::{Format, render_explanation};
use ariadne::{AnalysisView, Phase};
use std::{
    error::Error,
    path::{Path, PathBuf},
    time::Instant,
};
fn process_ticks(pid: u32) -> Result<u128, Box<dyn Error>> {
    let text = std::fs::read_to_string(format!("/proc/{pid}/stat"))?;
    let fields: Vec<_> = text
        .rsplit_once(')')
        .ok_or("invalid process stat")?
        .1
        .split_whitespace()
        .collect();
    Ok(fields[11].parse::<u128>()? + fields[12].parse::<u128>()?)
}
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: i4_profile DUMP DECODER ENTRY SITE RUNS".into());
    }
    let va = |s: &str| u64::from_str_radix(s.trim_start_matches("0x"), 16);
    let entry = va(&args[3])?;
    let site = va(&args[4])?;
    let runs: usize = args[5].parse()?;
    if !(1..=100).contains(&runs) {
        return Err("runs must be 1..100".into());
    }
    println!(
        "run,open_ns,backend_setup_ns,prepare_ns,shutdown_ns,runtime_validation_ns,reference_decode_ns,helper_startup_ns,lift_protocol_ns,projection_ns,native_init_ns,recovery_ns,dataflow_ns,slice_ns,native_finish_ns,recovery_actions,dataflow_actions,slice_actions,binding_ns,explanation_ns,explanation_render_ns,base_render_ns,total_ns,decoded,output_sha256"
    );
    for n in 0..runs {
        let total = Instant::now();
        let start = Instant::now();
        let snapshot = FileSnapshot::open_minidump(&args[1], OpenLimits::default())?;
        let open = start.elapsed().as_nanos();
        let start = Instant::now();
        let mut backend =
            ariadne::bap::Backend::new(ariadne::bap::Config::from_env(), Path::new(&args[2]))?;
        let setup = start.elapsed().as_nanos();
        let start = Instant::now();
        let p = snapshot.prepare_with_preparer(
            &AnalysisQuery {
                entry_points: [entry].into(),
                slice_seeds: [site].into(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            |s, c, o, t| {
                backend
                    .prepare(s, c, o, t)
                    .map_err(|e| PreparationError::Backend(e.to_string()))
            },
        )?;
        let prepare = start.elapsed().as_nanos();
        let metrics = backend.metrics();
        let start = Instant::now();
        backend.finish()?;
        let shutdown = start.elapsed().as_nanos();
        let start = Instant::now();
        let dir = std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("target/bap-core-native"));
        let mut native =
            NativeAnalyzer::from_capture(&CoreConfig::from_directory(dir), "i4-profile", &p)?;
        let init = start.elapsed().as_nanos();
        let mut phases = [0u128; 3];
        let mut cpu = [0u128; 3];
        let ticks: u128 = String::from_utf8(
            std::process::Command::new("getconf")
                .arg("CLK_TCK")
                .output()?
                .stdout,
        )?
        .trim()
        .parse()?;
        let mut actions = [0u64; 3];
        while native.state().phase != Phase::Done {
            let index = match native.state().phase {
                Phase::Recover => 0,
                Phase::Dataflow => 1,
                Phase::Slice => 2,
                Phase::Done => unreachable!(),
            };
            let start = Instant::now();
            let before_cpu = process_ticks(native.process_id())?;
            assert!(native.step()?);
            cpu[index] += process_ticks(native.process_id())? - before_cpu;
            phases[index] += start.elapsed().as_nanos();
            actions[index] += 1;
        }
        let start = Instant::now();
        let completed = native.complete()?;
        let finish = start.elapsed().as_nanos();
        let start = Instant::now();
        let bound = bind_investigation(&p, &completed)?;
        let binding = start.elapsed().as_nanos();
        let start = Instant::now();
        let explanation = explain_fault_address(
            &bound,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
            ExplainLimits::default(),
        )?;
        let explain = start.elapsed().as_nanos();
        let start = Instant::now();
        let mut output = String::new();
        for format in [Format::Text, Format::Json, Format::Dot] {
            output.push_str(&render_explanation(&explanation, format)?);
        }
        let erender = start.elapsed().as_nanos();
        let start = Instant::now();
        let decoded = completed.state().decoded.len();
        let result = completed.into_result();
        for format in [ReportFormat::Text, ReportFormat::Json, ReportFormat::Dot] {
            output.push_str(&render(&p, &result, format, false)?);
        }
        let base = start.elapsed().as_nanos();
        eprintln!(
            "I4-PROFILE native CPU run {n}: recovery={} ms, dataflow={} ms, slice={} ms",
            cpu[0] * 1000 / ticks,
            cpu[1] * 1000 / ticks,
            cpu[2] * 1000 / ticks
        );
        println!(
            "{n},{open},{setup},{prepare},{shutdown},{},{},{},{},{},{init},{},{},{},{finish},{},{},{},{binding},{explain},{erender},{base},{},{decoded},{}",
            metrics.runtime_validation.as_nanos(),
            metrics.reference_decode.as_nanos(),
            metrics.helper_startup.as_nanos(),
            metrics.lift_and_protocol.as_nanos(),
            metrics.projection.as_nanos(),
            phases[0],
            phases[1],
            phases[2],
            actions[0],
            actions[1],
            actions[2],
            total.elapsed().as_nanos(),
            ariadne::reports::sha256(output.as_bytes())
        );
    }
    Ok(())
}
