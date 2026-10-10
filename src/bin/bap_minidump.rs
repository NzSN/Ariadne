//! Stage timings for the sole BAP semantic backend.
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PreparationError, PrepareLimits,
    report::{ReportFormat, render},
};
use ariadne::{Analyzer, CompletedAnalysis, effects::PreparationOptions};
use std::{
    error::Error,
    path::{Path, PathBuf},
    time::Instant,
};
fn va(s: &str) -> Result<u64, Box<dyn Error>> {
    Ok(u64::from_str_radix(s.trim_start_matches("0x"), 16)?)
}
fn main() -> Result<(), Box<dyn Error>> {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let analysis_backend = if args.len() >= 2 && args[args.len() - 2] == "--analysis-backend" {
        let selected = args.pop().unwrap();
        args.pop();
        if !matches!(selected.as_str(), "rust" | "bap") {
            return Err("analysis backend must be rust or bap".into());
        }
        selected
    } else {
        "rust".into()
    };
    if args.len() != 5 && args.len() != 7 {
        return Err(
            "usage: bap_minidump DUMP DECODER_REFERENCE ENTRY SEED RUNS [HELPER RUNTIME] [--analysis-backend rust|bap]".into(),
        );
    }
    let backend = "bap";
    let runs: usize = args[4].parse()?;
    if runs == 0 {
        return Err("RUNS must be positive".into());
    }
    println!(
        "backend,artifact_sha256,run,open_ns,backend_setup_ns,prepare_ns,shutdown_ns,analysis_ns,render_ns,total_ns,runtime_validation_ns,reference_decode_ns,helper_startup_ns,lift_and_protocol_ns,projection_ns,decoded,edges,slice,obligations,output_bytes,analysis_backend,analysis_helper_sha256,output_sha256"
    );
    for run in 0..runs {
        let start = Instant::now();
        let snapshot = FileSnapshot::open_minidump(Path::new(&args[0]), OpenLimits::default())?;
        let open_ns = start.elapsed().as_nanos();
        let query = AnalysisQuery {
            entry_points: [va(&args[2])?].into(),
            slice_seeds: [va(&args[3])?].into(),
        };
        let options = PreparationOptions::default();
        let decoder = Path::new(&args[1]);
        let config = if args.len() == 7 {
            ariadne::bap::Config::new((&args[5]).into(), (&args[6]).into())
        } else {
            ariadne::bap::Config::from_env()
        };
        let mut provider = ariadne::bap::Backend::new(config, decoder)?;
        let backend_setup_ns = start.elapsed().as_nanos() - open_ns;
        let prepared = snapshot.prepare_with_preparer(
            &query,
            &options,
            PrepareLimits::default(),
            |s, c, o, t| {
                provider
                    .prepare(s, c, o, t)
                    .map_err(|e| PreparationError::Backend(e.to_string()))
            },
        )?;
        let prepare_ns = start.elapsed().as_nanos() - open_ns - backend_setup_ns;
        let metrics = provider.metrics();
        provider.finish()?;
        let shutdown_ns = start.elapsed().as_nanos() - open_ns - backend_setup_ns - prepare_ns;
        let (analyzer, analysis_helper_sha256) = if analysis_backend == "bap" {
            let directory = std::env::var_os("ARIADNE_BAP_CORE_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| {
                    Path::new(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
                });
            let core = ariadne::bap::core_session::CoreConfig::from_directory(directory);
            let native = ariadne::bap::core_adapter::NativeAnalyzer::from_capture(
                &core,
                "minidump-phase-benchmark",
                &prepared,
            )?;
            let helper = native.identity()["build"]["helper_sha256"]
                .as_str()
                .ok_or("missing native helper identity")?
                .to_owned();
            (native.complete()?, helper)
        } else {
            (
                CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone())?),
                String::new(),
            )
        };
        let result = analyzer.into_result();
        let analysis_ns =
            start.elapsed().as_nanos() - open_ns - backend_setup_ns - prepare_ns - shutdown_ns;
        let outputs = [ReportFormat::Text, ReportFormat::Dot, ReportFormat::Json]
            .into_iter()
            .map(|f| render(&prepared, &result, f, false))
            .collect::<Result<Vec<_>, _>>()?;
        let output_bytes: usize = outputs.iter().map(String::len).sum();
        let total_ns = start.elapsed().as_nanos();
        let render_ns =
            total_ns - open_ns - backend_setup_ns - prepare_ns - shutdown_ns - analysis_ns;
        println!(
            "{backend},{},{run},{open_ns},{backend_setup_ns},{prepare_ns},{shutdown_ns},{analysis_ns},{render_ns},{total_ns},{},{},{},{},{},{},{},{},{},{output_bytes},{analysis_backend},{analysis_helper_sha256},{}",
            snapshot.metadata().artifact_sha256,
            metrics.runtime_validation.as_nanos(),
            metrics.reference_decode.as_nanos(),
            metrics.helper_startup.as_nanos(),
            metrics.lift_and_protocol.as_nanos(),
            metrics.projection.as_nanos(),
            result.state.decoded.len(),
            result.state.edges.len(),
            result.state.slice.len(),
            result.state.obligations.len(),
            ariadne::reports::sha256(outputs.concat().as_bytes())
        );
        std::hint::black_box(outputs);
    }
    Ok(())
}
