//! Compare every visible transition against the frozen scanning implementation.
#[path = "../../../tests/support/scanning_engine.rs"]
mod scanning_engine;

use ariadne::Analyzer;
use ariadne::effects::PreparationOptions;
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::error::Error;
use std::path::Path;

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 4 {
        return Err("usage: compare_schedule DUMP DECODER ENTRY_HEX SEED_HEX".into());
    }
    let va = |s: &str| u64::from_str_radix(s.strip_prefix("0x").unwrap_or(s), 16);
    let snapshot = FileSnapshot::open_minidump(&args[0], OpenLimits::default())?;
    let prepared = snapshot.prepare(
        &AnalysisQuery {
            entry_points: [va(&args[2])?].into(),
            slice_seeds: [va(&args[3])?].into(),
        },
        Path::new(&args[1]),
        &PreparationOptions::default(),
        PrepareLimits::default(),
    )?;
    let mut optimized = Analyzer::new(prepared.prepared.request.clone())?;
    let mut scanning = scanning_engine::Analyzer::new(prepared.prepared.request)?;
    let mut actions = 0;
    loop {
        let advanced = optimized.step();
        assert_eq!(advanced, scanning.step(), "action {actions}: completion");
        assert_eq!(
            optimized.state(),
            scanning.state(),
            "action {actions}: full state"
        );
        if !advanced {
            break;
        }
        actions += 1;
    }
    let metrics = optimized.metrics();
    let reference = scanning.metrics();
    assert_eq!(optimized.finish(), scanning.finish(), "complete result");
    println!(
        "{{\"passed\":true,\"matched_actions\":{actions},\"incoming_evaluations\":{},\"reference_incoming_evaluations\":{},\"edge_scans\":{},\"reference_edge_scans\":{}}}",
        metrics.incoming_evaluations,
        reference.incoming_evaluations,
        metrics.edge_scans,
        reference.edge_scans
    );
    Ok(())
}
