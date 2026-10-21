//! Large-capture qualification without allocating a full expanded base report.
use ariadne::bap::target_resolution::Limits;
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::{AnalysisState, AnalysisView, CompletedAnalysis, DefinitionOrigin};
use sha2::{Digest, Sha256};
use std::{error::Error, path::PathBuf, time::Instant};

const ORIGINAL_SHA256: &str = "5fea4ca614706fe0040ed3231efee0edf9ce4004a51d902bb581025b48bade08";
fn digest(state: &AnalysisState, snapshot: &str) -> String {
    let mut hash = Sha256::new();
    hash.update(snapshot.as_bytes());
    for (&site, definitions) in &state.reaching {
        hash.update(site.to_le_bytes());
        hash.update((definitions.len() as u64).to_le_bytes());
        for d in definitions {
            hash.update((d.loc.len() as u64).to_le_bytes());
            hash.update(d.loc.as_bytes());
            hash.update(d.site.to_le_bytes());
            hash.update([u8::from(d.origin == DefinitionOrigin::Instruction)]);
        }
    }
    for e in &state.edges {
        hash.update(e.src.to_le_bytes());
        hash.update(e.dst.to_le_bytes());
        hash.update(format!("{:?}", e.kind).as_bytes());
    }
    hash.update(
        format!(
            "{:?}",
            (
                &state.obligations,
                &state.decoded,
                &state.slice,
                (
                    &state.phase,
                    &state.pending,
                    &state.visited,
                    &state.provenance
                )
            )
        )
        .as_bytes(),
    );
    format!("{:x}", hash.finalize())
}
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: target-resolution-validate ORIGINAL_DUMP NEW_OUTPUT_DIR".into());
    }
    let start = Instant::now();
    let out = PathBuf::from(&args[1]);
    std::fs::create_dir(&out)?;
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let snapshot = FileSnapshot::open_minidump(
        &args[0],
        OpenLimits {
            max_file_bytes: 2 * 1024 * 1024 * 1024,
            ..OpenLimits::default()
        },
    )?;
    if snapshot.metadata().artifact_sha256 != ORIGINAL_SHA256 {
        return Err("original dump SHA differs".into());
    }
    let p = snapshot.prepare_with_bap_target_resolution(
        &AnalysisQuery {
            entry_points: [0x7ff640079640].into(),
            slice_seeds: [0x7ff640079670].into(),
        },
        &root.join("target/ariadne-llvm-mc"),
        &ariadne::bap::Config::from_env(),
        &ariadne::effects::PreparationOptions::default(),
        PrepareLimits::default(),
        Limits::default(),
    )?;
    let prepared_ms = start.elapsed().as_millis();
    let resolution = p.target_resolution().ok_or("resolution absent")?;
    let selected = resolution
        .resolutions
        .iter()
        .find(|r| r.site == "0x00007ff64007968b")
        .ok_or("table absent")?;
    let oracle: serde_json::Value = serde_json::from_str(include_str!(
        "../../tests/bap/fixtures/target-resolution-table.json"
    ))?;
    let targets: Vec<String> = serde_json::from_value(oracle["unique_targets"].clone())?;
    if selected.targets != targets
        || selected.complete
        || resolution.memory_premise != ariadne::bap::target_resolution::MEMORY_PREMISE
    {
        return Err("captured target oracle mismatch".into());
    }
    let normalized = serde_json::to_vec_pretty(&ariadne::bap::core_adapter::encode_request(
        &p.prepared.request,
    )?)?;
    std::fs::write(out.join("normalized-request.json"), &normalized)?;
    std::fs::write(
        out.join("query-identity.json"),
        serde_json::to_vec_pretty(&serde_json::json!({
            "artifact_sha256": snapshot.metadata().artifact_sha256,
            "snapshot_id": p.prepared.request.snapshot_id,
            "entry_points": p.prepared.request.entry_points.iter().map(|a| format!("0x{a:016x}")).collect::<Vec<_>>(),
            "slice_seeds": p.prepared.request.slice_seeds.iter().map(|a| format!("0x{a:016x}")).collect::<Vec<_>>(),
            "normalized_request_sha256": ariadne::reports::sha256(&normalized),
            "diagnostic_response_timeout_ms": 60000,
            "production_cli_timing_credit": false
        }))?,
    )?;
    std::fs::write(
        out.join("target-resolution.json"),
        serde_json::to_vec_pretty(resolution)?,
    )?;
    println!(
        "prepared_ms={prepared_ms}; table targets=45; complete={}",
        selected.complete
    );
    let mut config = ariadne::bap::core_session::CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join("target/bap-core-native")),
    );
    config.timeout = std::time::Duration::from_secs(60);
    let mut records = Vec::new();
    let mut expected = None;
    for backend in ["bap", "rust"] {
        let analyzed_at = Instant::now();
        let completed = if backend == "bap" {
            ariadne::bap::core_adapter::NativeAnalyzer::from_capture(
                &config,
                "target-real-capture",
                &p,
            )?
            .complete()?
        } else {
            CompletedAnalysis::from_analyzer(ariadne::Analyzer::new(p.prepared.request.clone())?)
        };
        let analysis_ms = analyzed_at.elapsed().as_millis();
        let result = completed.state();
        let signature = digest(result, &completed.request().snapshot_id);
        if let Some(previous) = &expected {
            if *previous != signature {
                return Err("native/Rust expanded state differs".into());
            }
        } else {
            expected = Some(signature.clone());
        }
        let bound = ariadne::input::investigation::bind_investigation(&p, &completed)?;
        let explanation = ariadne::investigation::explain_fault_address(
            &bound,
            ariadne::investigation::FaultAddressQuestion {
                site: 0x7ff640079670,
                memory_access: 0,
            },
            ariadne::investigation::ExplainLimits::default(),
        )?;
        std::fs::write(
            out.join(format!("{backend}-explanation.json")),
            ariadne::reports::render_explanation(&explanation, ariadne::reports::Format::Json)?,
        )?;
        let record = serde_json::json!({"backend":backend,"prepare_ms":prepared_ms,"analysis_ms":analysis_ms,"state_sha256":signature,"decoded":result.decoded.len(),"edges":result.edges.len(),"slice":result.slice.len(),"definition_links":result.reaching.values().map(|v|v.len()).sum::<usize>(),"table_edges":result.edges.iter().filter(|e|e.src==0x7ff64007968b && e.kind==ariadne::EdgeKind::Indirect).count(),"answer":format!("{:?}",explanation.status)});
        println!("{record}");
        records.push(record);
    }
    std::fs::write(
        out.join("qualification.json"),
        serde_json::to_vec_pretty(
            &serde_json::json!({"schema":"ariadne.target-resolution-real-capture/v1","dump_sha256":snapshot.metadata().artifact_sha256,"native_rust_state_equal":true,"records":records}),
        )?,
    )?;
    Ok(())
}
