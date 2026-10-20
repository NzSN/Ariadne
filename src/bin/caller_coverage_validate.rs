//! Finite S6 qualification driver. Output contains compact full-state receipts,
//! never an inferred execution history or a replacement semantic source.
use ariadne::bap::{
    core_adapter::{NativeAnalyzer, encode_request},
    core_session::CoreConfig,
};
use ariadne::input::{FileSnapshot, FramePreparation, OpenLimits, PrepareLimits};
use ariadne::investigation::FrameRecoveryLimits;
use ariadne::*;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::error::Error;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

fn address(v: &Value) -> Result<u64, Box<dyn Error>> {
    Ok(u64::from_str_radix(
        v.as_str()
            .ok_or("address string")?
            .strip_prefix("0x")
            .ok_or("address prefix")?,
        16,
    )?)
}
fn addresses(v: &Value) -> Result<AddressSet, Box<dyn Error>> {
    v.as_array()
        .ok_or("address array")?
        .iter()
        .map(address)
        .collect()
}
fn locations(v: &Value) -> Result<LocationSet, Box<dyn Error>> {
    v.as_array()
        .ok_or("location array")?
        .iter()
        .map(|v| {
            v.as_str()
                .map(str::to_owned)
                .ok_or_else(|| "location string".into())
        })
        .collect()
}
fn request(v: &Value) -> Result<AnalysisRequest, Box<dyn Error>> {
    let mut r = AnalysisRequest {
        snapshot_id: v["snapshot"].as_str().ok_or("snapshot")?.into(),
        addresses: addresses(&v["addresses"])?,
        locations: locations(&v["locations"])?,
        entry_points: addresses(&v["entry_points"])?,
        slice_seeds: addresses(&v["slice_seeds"])?,
        input_kind: match v["input_kind"].as_str() {
            Some("dump") => InputKind::Dump,
            Some("binary") => InputKind::Binary,
            _ => return Err("input kind".into()),
        },
        captured: addresses(&v["captured"])?,
        file_backed: addresses(&v["file_backed"])?,
        trusted_fallback: addresses(&v["trusted_fallback"])?,
        decodable: addresses(&v["decodable"])?,
        ..AnalysisRequest::default()
    };
    for i in v["instructions"].as_array().ok_or("instructions")? {
        let kind = match i["kind"].as_str() {
            Some("ordinary") => InstructionKind::Ordinary,
            Some("conditional") => InstructionKind::Conditional,
            Some("jump") => InstructionKind::Jump,
            Some("indirect") => InstructionKind::Indirect,
            Some("call") => InstructionKind::Call,
            Some("return") => InstructionKind::Return,
            Some("stop") => InstructionKind::Stop,
            _ => return Err("instruction kind".into()),
        };
        let instruction = Instruction {
            kind,
            fall: addresses(&i["fall"])?,
            targets: addresses(&i["targets"])?,
            complete: i["targets_complete"].as_bool().ok_or("completeness")?,
            uses: locations(&i["uses"])?,
            may_defs: locations(&i["may_defs"])?,
            must_defs: locations(&i["must_defs"])?,
        };
        if r.instructions
            .insert(address(&i["address"])?, instruction)
            .is_some()
        {
            return Err("duplicate instruction".into());
        }
    }
    r.validate()?;
    if encode_request(&r)? != *v {
        return Err("normalized request was not exactly preserved".into());
    }
    Ok(r)
}
fn receipts(state: &AnalysisState) -> Result<Value, Box<dyn Error>> {
    let mut rows = Vec::new();
    let mut universe_hash = None;
    for (&a, set) in &state.reaching {
        if let Some((universe, words)) = set.compact_membership() {
            if universe_hash.is_none() {
                let mut hash = Sha256::new();
                for d in universe {
                    hash.update((d.loc.len() as u64).to_le_bytes());
                    hash.update(d.loc.as_bytes());
                    hash.update(d.site.to_le_bytes());
                    hash.update([if d.origin == DefinitionOrigin::Entry {
                        0
                    } else {
                        1
                    }]);
                }
                universe_hash = Some((universe.len(), format!("{:x}", hash.finalize())));
            }
            let mut hash = Sha256::new();
            for word in words {
                hash.update(word.to_le_bytes());
            }
            rows.push(json!({"address":format!("0x{a:016x}"),"count":set.len(),"membership_sha256":format!("{:x}",hash.finalize())}));
        } else {
            if !set.is_empty() {
                return Err("nonempty completion row was not compact".into());
            }
            rows.push(json!({"address":format!("0x{a:016x}"),"count":0,"membership_sha256":null}));
        }
    }
    Ok(json!({"universe":universe_hash,"rows":rows}))
}
fn compare(
    r: AnalysisRequest,
    native: NativeAnalyzer,
    out: &Path,
) -> Result<Value, Box<dyn Error>> {
    if native.request() != &r {
        return Err("native/Rust request mismatch".into());
    }
    let start = Instant::now();
    let (reference, metrics) =
        Analyzer::new(r.clone())?.finish_bounded(CompletionLimits::default())?;
    let rust_ms = start.elapsed().as_millis();
    let began = Instant::now();
    let actual = native.finish()?;
    let native_ms = began.elapsed().as_millis();
    if reference != actual {
        return Err("completed native/Rust full-state mismatch".into());
    }
    let proof = receipts(&reference.state)?;
    std::fs::write(
        out.join("full-state-membership.json"),
        serde_json::to_vec(&proof)?,
    )?;
    std::fs::write(
        out.join("normalized.json"),
        serde_json::to_vec(&encode_request(&r)?)?,
    )?;
    Ok(
        json!({"completed":true,"request_equal":true,"full_state_equal":true,"phase":format!("{:?}",actual.state.phase),
        "decoded":actual.state.decoded.len(),"edges":actual.state.edges.len(),"obligations":actual.state.obligations.len(),
        "definition_links":actual.state.reaching.values().map(DefinitionSet::len).sum::<usize>(),
        "slice":actual.state.slice,"rust_actions":metrics.actions,"rust_ms":rust_ms,"native_ms":native_ms,
        "ordinary_replay_schedule":"unchanged","completion_schedule":"reverse-postorder","membership":"full-state-membership.json"}),
    )
}
fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 3 {
        return Err("usage: caller-coverage-validate replay|dump INPUT OUTPUT".into());
    }
    let out = PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out)?;
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut core = CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join("target/qualification-native")),
    );
    core.timeout = Duration::from_secs(600);
    core.max_request_bytes = 128 * 1024 * 1024;
    if args[0] == "replay" {
        let input = std::fs::read(&args[1])?;
        let v: Value = serde_json::from_slice(&input)?;
        let r = request(v.get("normalized").unwrap_or(&v))?;
        let native = NativeAnalyzer::new(&core, "caller-s6-saved-request", r.clone())?;
        let mut result = compare(r, native, &out)?;
        result["input_sha256"] = json!(ariadne::reports::sha256(&input));
        result["capture_admission_exercised"] = json!(false);
        std::fs::write(
            out.join("summary.json"),
            serde_json::to_vec_pretty(&result)?,
        )?;
        println!("{}", result);
        return Ok(());
    }
    if args[0] != "dump" {
        return Err("unknown mode".into());
    }
    let snapshot = FileSnapshot::open_minidump(
        &args[1],
        OpenLimits {
            max_file_bytes: 2 * 1024 * 1024 * 1024,
            max_read_bytes: 32 * 1024 * 1024,
            ..Default::default()
        },
    )?;
    if snapshot.metadata().artifact_sha256
        != "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab"
    {
        return Err("original dump SHA differs".into());
    }
    let thread = snapshot
        .metadata()
        .exception
        .as_ref()
        .ok_or("missing exception")?
        .thread_id;
    let chain = snapshot.recover_thread_frames(
        thread,
        FrameRecoveryLimits {
            max_frames: 6,
            max_runtime_entries: 440520,
            max_read_bytes: 6334816,
            ..Default::default()
        },
    )?;
    snapshot.validate_thread_frames(&chain)?;
    let config = ariadne::bap::Config::from_env();
    let options = ariadne::effects::PreparationOptions::default();
    let decoder = root.join("target/ariadne-llvm-mc");
    let setup = FramePreparation {
        decoder: &decoder,
        config: &config,
        options: &options,
        limits: PrepareLimits {
            max_starts: 16384,
            max_candidates: 32768,
            max_prefix_bytes: 16384 * 15,
            max_decoder_batches: 16384,
            batch_size: 128,
        },
    };
    let guard = ariadne::bap::guard_admission::Limits {
        max_sites: 32768,
        max_edges: 131072,
        max_residue_updates: 4194304,
        max_transfer_evaluations: 67108864,
        max_closure_rounds: 32768,
        max_evidence_bytes: 64 * 1024 * 1024,
        max_elapsed_ms: 120000,
    };
    let target = ariadne::bap::target_resolution::Limits {
        max_entries: 16384,
        max_targets: 65536,
        max_read_bytes: 16 * 1024 * 1024,
        max_evidence_bytes: 128 * 1024 * 1024,
        max_values: 4096,
        max_steps: 2097152,
        max_path_steps: 512,
        max_rounds: 64,
        max_elapsed_ms: 120000,
    };
    let mut results = vec![];
    for frame in [1, 0] {
        let dir = out.join(format!("frame-{frame}"));
        std::fs::create_dir_all(&dir)?;
        let entry = chain
            .frames
            .get(frame)
            .and_then(|f| f.function_begin)
            .ok_or("missing frame entry")?;
        eprintln!("preparing frame {frame}");
        let prepared = snapshot
            .prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(
                &chain,
                frame,
                entry,
                &setup,
                guard.clone(),
                target.clone(),
            )?;
        let g = prepared.guard_admission().ok_or("guard report")?;
        let t = prepared.target_resolution().ok_or("target report")?;
        let c = prepared.composition().ok_or("composition report")?;
        std::fs::write(dir.join("guard.json"), serde_json::to_vec(g)?)?;
        std::fs::write(dir.join("target.json"), serde_json::to_vec(t)?)?;
        std::fs::write(dir.join("composition.json"), serde_json::to_vec(c)?)?;
        let native =
            NativeAnalyzer::from_capture(&core, &format!("caller-s6-frame-{frame}"), &prepared)?;
        let mut result = compare(prepared.prepared.request.clone(), native, &dir)?;
        result["frame"] = json!(frame);
        result["capture_admission_exercised"] = json!(true);
        result["guard_stop"] = json!(g.stop);
        result["barriers"] = json!(g.input.barriers);
        result["guards"] = json!(
            g.guards
                .iter()
                .map(|g| json!({"site":g.site,"verdict":g.verdict,"residual":g.residual}))
                .collect::<Vec<_>>()
        );
        results.push(result);
        std::fs::write(
            out.join("summary.json"),
            serde_json::to_vec_pretty(&results)?,
        )?;
        if frame == 1 && !g.input.barriers.is_empty() {
            return Err("S6 caller semantic-coverage barriers remain".into());
        }
    }
    println!("{}", json!(results));
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
