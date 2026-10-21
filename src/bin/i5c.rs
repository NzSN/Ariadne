//! Native I5c phase measurements and unmeasured strict report authentication.
use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
use ariadne::effects::PreparationOptions;
use ariadne::input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits, investigation::bind_address_wrap,
};
use ariadne::investigation::{AddressWrapLimits, FaultAddressQuestion, assess_address_wrap};
use ariadne::reports::{Format, decode_address_wrap, render_address_wrap, sha256};
use std::{
    error::Error,
    path::{Path, PathBuf},
    time::Instant,
};

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.get(1).is_some_and(|s| s == "--validate-address-wrap") {
        if args.len() != 5 {
            return Err("usage: i5c --validate-address-wrap JSON TEXT DOT".into());
        }
        let json = std::fs::read(&args[2])?;
        // This invokes the production decoder's complete typed-ID, arithmetic,
        // claim, evidence-prefix, context and conclusion recomputation.
        let value = decode_address_wrap(&json)?;
        let mut hashes = Vec::new();
        for (path, format) in [
            (&args[3], Format::Text),
            (&args[2], Format::Json),
            (&args[4], Format::Dot),
        ] {
            let raw = std::fs::read(path)?;
            let rendered = render_address_wrap(&value, format)?;
            if raw != rendered.as_bytes() {
                return Err("report bytes differ from strict canonical rendering".into());
            }
            hashes.push(sha256(&raw));
        }
        println!(
            "{}",
            serde_json::json!({
                "schema": "ariadne.i5c-codec-result/v1",
                "assessment_sha256": sha256(&json),
                "text_sha256": hashes[0], "json_sha256": hashes[1], "dot_sha256": hashes[2],
                "scope_id": value.scope_id, "content_id": value.content_id,
                "evidence": value.evidence.len(), "claims": value.claims.len(),
                "conclusion": value.conclusion,
            })
        );
        return Ok(());
    }
    if args.len() != 6 {
        return Err("usage: i5c DUMP DECODER ENTRY_HEX SITE_HEX RUNS".into());
    }
    let va = |s: &str| u64::from_str_radix(s.trim_start_matches("0x"), 16);
    let entry = va(&args[3])?;
    let site = va(&args[4])?;
    let runs: usize = args[5].parse()?;
    if runs != 6 {
        return Err("the frozen I5c contract requires one warm-up and five measured runs".into());
    }
    let snapshot = FileSnapshot::open_minidump(&args[1], OpenLimits::default())?;
    let prepared = snapshot.prepare(
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
        "i5c-measurement",
        &prepared,
    )?;
    let receipt = native.identity().clone();
    let manifest_sha256 = sha256(&serde_json::to_vec(&receipt["build"])?);
    // Preparation and complete native recovery/dataflow are outside the timed
    // interval. Each measurement uses this exact completed AnalysisView.
    let completed = native.complete()?;
    let analysis: &dyn ariadne::AnalysisView = &completed;
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
        "artifact_sha256,run,binding_ns,assessment_ns,render_ns,total_ns,evidence,claims,conclusion,output_sha256,analysis_backend,analysis_profile,analysis_family,snapshot_id,query_id,backend_query,helper_sha256,manifest_sha256,entry,site,memory_access,max_evidence,max_claims,scope_id,content_id"
    );
    for run in 0..runs {
        let start = Instant::now();
        let bound = bind_address_wrap(
            &prepared,
            analysis,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
        )?;
        let binding = start.elapsed().as_nanos();
        let start = Instant::now();
        let result = assess_address_wrap(&bound, AddressWrapLimits::default())?;
        let assessment = start.elapsed().as_nanos();
        let start = Instant::now();
        let mut output = String::new();
        for format in [Format::Text, Format::Json, Format::Dot] {
            output.push_str(&render_address_wrap(&result, format)?);
        }
        let render = start.elapsed().as_nanos();
        println!(
            "{},{run},{binding},{assessment},{render},{},{},{},{:?},{},{backend},{profile},{family},{},{},{backend_query},{helper_sha256},{manifest_sha256},0x{entry:016x},0x{site:016x},0,{},{},{},{}",
            result.identity.artifact_sha256,
            binding + assessment + render,
            result.evidence.len(),
            result.claims.len(),
            result.conclusion,
            sha256(output.as_bytes()),
            result.identity.snapshot_id,
            result.identity.query_id,
            result.limits.max_evidence,
            result.limits.max_claims,
            result.scope_id,
            result.content_id,
        );
    }
    Ok(())
}
