//! Example consumer of the pure renderer; diagnostics go to stderr so stdout
//! remains a standalone text report or DOT document.
use ariadne::effects::PreparationOptions;
use ariadne::render::{Format, render};
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::path::Path;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 5 {
        return Err("usage: render_minidump DUMP DECODER ENTRY_VA_HEX SEED_VA_HEX text|dot".into());
    }
    let format = match args[4].as_str() {
        "text" => Format::Text,
        "dot" => Format::Dot,
        _ => return Err("expected text or dot".into()),
    };
    let entry = u64::from_str_radix(args[2].trim_start_matches("0x"), 16)?;
    let seed = u64::from_str_radix(args[3].trim_start_matches("0x"), 16)?;
    let snapshot = FileSnapshot::open_minidump(&args[0], OpenLimits::default())?;
    let p = snapshot.prepare(
        &AnalysisQuery {
            entry_points: [entry].into(),
            slice_seeds: [seed].into(),
        },
        Path::new(&args[1]),
        &PreparationOptions::default(),
        PrepareLimits::default(),
    )?;
    eprintln!(
        "input snapshot={} platform={:?} target={} attempted={}",
        p.snapshot.snapshot_id,
        p.snapshot.platform,
        p.prepared.identity.target,
        p.materialization.attempted.len()
    );
    for gap in &p.snapshot.gaps {
        eprintln!("input gap: {gap:?}");
    }
    for gap in &p.prepared.gaps {
        eprintln!("preparation gap: {gap:?}");
    }
    let result = ariadne::analyze(p.prepared.request)?;
    use std::io::Write;
    std::io::stdout()
        .lock()
        .write_all(render(&result, format).as_bytes())?;
    Ok(())
}
