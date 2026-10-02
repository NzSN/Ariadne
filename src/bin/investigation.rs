//! Timings for query binding, evidence explanation and its report rendering.
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits, investigation::bind_investigation,
};
use ariadne::investigation::{ExplainLimits, FaultAddressQuestion, explain_fault_address};
use ariadne::{Analyzer, effects::PreparationOptions};
use std::{error::Error, path::Path, time::Instant};
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 5 {
        return Err("usage: investigation DUMP DECODER_REFERENCE ENTRY SITE RUNS".into());
    }
    let va = |s: &str| u64::from_str_radix(s.trim_start_matches("0x"), 16);
    let entry = va(&args[2])?;
    let site = va(&args[3])?;
    let runs: usize = args[4].parse()?;
    if runs == 0 {
        return Err("RUNS must be positive".into());
    }
    println!(
        "run,artifact_sha256,query_id,prepare_analysis_ns,binding_ns,explanation_ns,render_ns,total_ns,claims,evidence,gaps,output_bytes"
    );
    for n in 0..runs {
        let start = Instant::now();
        let snapshot = FileSnapshot::open_minidump(&args[0], OpenLimits::default())?;
        let p = snapshot.prepare(
            &AnalysisQuery {
                entry_points: [entry].into(),
                slice_seeds: [site].into(),
            },
            Path::new(&args[1]),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )?;
        let mut a = Analyzer::new(p.prepared.request.clone())?;
        while a.step() {}
        let prep = start.elapsed().as_nanos();
        let b = bind_investigation(&p, &a)?;
        let binding = start.elapsed().as_nanos() - prep;
        let e = explain_fault_address(
            &b,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
            ExplainLimits::default(),
        )?;
        let explain = start.elapsed().as_nanos() - prep - binding;
        let reports = [
            ariadne::reports::Format::Text,
            ariadne::reports::Format::Json,
            ariadne::reports::Format::Dot,
        ]
        .into_iter()
        .map(|f| ariadne::reports::render_explanation(&e, f))
        .collect::<Result<Vec<_>, _>>()?;
        let total = start.elapsed().as_nanos();
        let render = total - prep - binding - explain;
        let bytes: usize = reports.iter().map(String::len).sum();
        println!(
            "{n},{},{},{prep},{binding},{explain},{render},{total},{},{},{},{bytes}",
            e.identity.artifact_sha256,
            e.identity.query_id,
            e.claims.len(),
            e.evidence.len(),
            e.gaps.len()
        );
        std::hint::black_box(reports);
    }
    Ok(())
}
