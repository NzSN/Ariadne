//! Bound, repeatable I5a binding/assessment/render measurements.
use ariadne::effects::PreparationOptions;
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits, investigation::bind_fault_context,
};
use ariadne::investigation::{AssessmentLimits, FaultAddressQuestion, assess_zero_address};
use ariadne::reports::{Format, render_zero_address};
use std::{error::Error, path::Path, time::Instant};
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: i5a DUMP DECODER ENTRY_HEX SITE_HEX RUNS".into());
    }
    let va = |s: &str| u64::from_str_radix(s.trim_start_matches("0x"), 16);
    let entry = va(&args[3])?;
    let site = va(&args[4])?;
    let runs: usize = args[5].parse()?;
    if !(1..=100).contains(&runs) {
        return Err("runs must be 1..100".into());
    }
    let snapshot = FileSnapshot::open_minidump(&args[1], OpenLimits::default())?;
    let p = snapshot.prepare(
        &AnalysisQuery {
            entry_points: [entry].into(),
            slice_seeds: [site].into(),
        },
        Path::new(&args[2]),
        &PreparationOptions::default(),
        PrepareLimits::default(),
    )?;
    let mut a = ariadne::Analyzer::new(p.prepared.request.clone())?;
    while a.step() {}
    println!(
        "artifact_sha256,run,binding_ns,assessment_ns,render_ns,total_ns,evidence,claims,conclusion,output_sha256"
    );
    for run in 0..runs {
        let start = Instant::now();
        let bound = bind_fault_context(&p, &a)?;
        let binding = start.elapsed().as_nanos();
        let start = Instant::now();
        let result = assess_zero_address(
            &bound,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
            AssessmentLimits::default(),
        )?;
        let assessment = start.elapsed().as_nanos();
        let start = Instant::now();
        let mut output = String::new();
        for format in [Format::Text, Format::Json, Format::Dot] {
            output.push_str(&render_zero_address(&result, format)?);
        }
        let render = start.elapsed().as_nanos();
        println!(
            "{},{run},{binding},{assessment},{render},{},{},{},{:?},{}",
            result.identity.artifact_sha256,
            binding + assessment + render,
            result.evidence.len(),
            result.claims.len(),
            result.conclusion,
            ariadne::reports::sha256(output.as_bytes())
        );
    }
    Ok(())
}
