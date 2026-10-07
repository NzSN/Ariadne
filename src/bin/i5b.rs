//! Bound, repeatable I5b binding/assessment/render measurements.
use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
use ariadne::effects::PreparationOptions;
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits, investigation::bind_zero_base_offset,
};
use ariadne::investigation::{FaultAddressQuestion, ZeroBaseOffsetLimits, assess_zero_base_offset};
use ariadne::reports::{Format, render_zero_base_offset};
use std::{
    error::Error,
    path::{Path, PathBuf},
    time::Instant,
};
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 6 {
        return Err("usage: i5b DUMP DECODER ENTRY_HEX SITE_HEX RUNS".into());
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
    let core_directory = std::env::var_os("ARIADNE_BAP_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("target/bap-core-native"));
    let native = NativeAnalyzer::from_capture(
        &CoreConfig::from_directory(core_directory),
        "i5b-measurement",
        &p,
    )?;
    let receipt = native.identity().clone();
    let manifest_sha256 = ariadne::reports::sha256(&serde_json::to_vec(&receipt["build"])?);
    // Complete the same native capture path used by the CLI before measuring
    // the existing binding + assessment + all-format rendering interval.
    let completed = native.complete()?;
    let a: &dyn ariadne::AnalysisView = &completed;
    let field = |name: &str| {
        receipt[name]
            .as_str()
            .ok_or("missing backend identity field")
    };
    let backend = field("backend")?;
    let profile = field("profile")?;
    let family = field("family")?;
    let backend_query = field("query")?;
    let helper_sha256 = receipt["build"]["helper_sha256"]
        .as_str()
        .ok_or("missing helper identity")?;
    println!(
        "artifact_sha256,run,binding_ns,assessment_ns,render_ns,total_ns,evidence,claims,conclusion,output_sha256,analysis_backend,analysis_profile,analysis_family,snapshot_id,query_id,backend_query,helper_sha256,manifest_sha256,entry,site,memory_access"
    );
    for run in 0..runs {
        let start = Instant::now();
        let bound = bind_zero_base_offset(
            &p,
            a,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
        )?;
        let binding = start.elapsed().as_nanos();
        let start = Instant::now();
        let result = assess_zero_base_offset(&bound, ZeroBaseOffsetLimits::default())?;
        let assessment = start.elapsed().as_nanos();
        let start = Instant::now();
        let mut output = String::new();
        for format in [Format::Text, Format::Json, Format::Dot] {
            output.push_str(&render_zero_base_offset(&result, format)?);
        }
        let render = start.elapsed().as_nanos();
        println!(
            "{},{run},{binding},{assessment},{render},{},{},{},{:?},{},{backend},{profile},{family},{},{},{backend_query},{helper_sha256},{manifest_sha256},0x{entry:016x},0x{site:016x},0",
            result.identity.artifact_sha256,
            binding + assessment + render,
            result.evidence.len(),
            result.claims.len(),
            result.conclusion,
            ariadne::reports::sha256(output.as_bytes()),
            result.identity.snapshot_id,
            result.identity.query_id,
        );
    }
    Ok(())
}
