//! Stage timings for the sole BAP semantic backend.
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PreparationError, PrepareLimits,
    report::{ReportFormat, render},
};
use ariadne::{Analyzer, effects::PreparationOptions};
use std::{error::Error, path::Path, time::Instant};
fn va(s: &str) -> Result<u64, Box<dyn Error>> {
    Ok(u64::from_str_radix(s.trim_start_matches("0x"), 16)?)
}
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 5 && args.len() != 7 {
        return Err(
            "usage: bap_minidump DUMP DECODER_REFERENCE ENTRY SEED RUNS [HELPER RUNTIME]".into(),
        );
    }
    let backend = "bap";
    let runs: usize = args[4].parse()?;
    if runs == 0 {
        return Err("RUNS must be positive".into());
    }
    println!(
        "backend,artifact_sha256,run,open_ns,backend_setup_ns,prepare_ns,shutdown_ns,analysis_ns,render_ns,total_ns,runtime_validation_ns,reference_decode_ns,helper_startup_ns,lift_and_protocol_ns,projection_ns,decoded,edges,slice,obligations,output_bytes"
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
        let mut analyzer = Analyzer::new(prepared.prepared.request.clone())?;
        while analyzer.step() {}
        let result = analyzer.finish();
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
            "{backend},{},{run},{open_ns},{backend_setup_ns},{prepare_ns},{shutdown_ns},{analysis_ns},{render_ns},{total_ns},{},{},{},{},{},{},{},{},{},{output_bytes}",
            snapshot.metadata().artifact_sha256,
            metrics.runtime_validation.as_nanos(),
            metrics.reference_decode.as_nanos(),
            metrics.helper_startup.as_nanos(),
            metrics.lift_and_protocol.as_nanos(),
            metrics.projection.as_nanos(),
            result.state.decoded.len(),
            result.state.edges.len(),
            result.state.slice.len(),
            result.state.obligations.len()
        );
        std::hint::black_box(outputs);
    }
    Ok(())
}
