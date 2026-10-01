use ariadne_stage_e_mbt::{self as integration, Engine, Evidence, TARGET};
use mirrorrust::*;
use serde_json::json;
use std::cell::RefCell;
use std::rc::Rc;

fn execute() -> Result<bool, Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() < 6 {
        return Err("usage: ariadne-stage-e-mbt machine-state|llvm-ir good|wrong-digest MIRROR SPEC LOCK TRACE...".into());
    }
    let engine = match args[0].as_str() {
        "machine-state" => Engine::MachineState,
        "llvm-ir" => Engine::LLVMIR,
        _ => return Err("unknown Stage E engine".into()),
    };
    let mode = args[1].as_str();
    if !["good", "wrong-digest"].contains(&mode) {
        return Err("unknown replay mode".into());
    }
    let lock: serde_json::Value = serde_json::from_slice(&std::fs::read(&args[4])?)?;
    let mut metadata = engine.metadata();
    let contract: serde_json::Value = serde_json::from_str(engine.contract())?;
    if lock["semanticDigest"].as_str() != Some(metadata.semantic_digest.as_str())
        || lock["contract"] != contract
    {
        return Err("compiled Stage E binding differs from the selected lock".into());
    }
    let expected_states = args[5..].iter().try_fold(
        0,
        |count, path| -> Result<usize, Box<dyn std::error::Error>> {
            let trace: serde_json::Value = serde_json::from_slice(&std::fs::read(path)?)?;
            Ok(count
                + trace["states"]
                    .as_array()
                    .ok_or("trace has no states")?
                    .len())
        },
    )?;
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let mut registration = match engine {
        Engine::MachineState => integration::machine_state_registration(
            integration::fixtures_machine::request(),
            evidence.clone(),
        )?,
        Engine::LLVMIR => integration::llvm_ir_registration(
            integration::fixtures_ir::request(),
            evidence.clone(),
        )?,
    };
    if mode == "wrong-digest" {
        metadata.semantic_digest = "0".repeat(64);
        registration.key.semantic_digest = SemanticDigest::from_hex(&metadata.semantic_digest)?;
    }
    let digest = metadata.semantic_digest.clone();
    let mut registry = CompiledAdapterRegistry::new(vec![registration]);
    let mut selection = CompiledAdapterSelection {
        metadata,
        adapter_id: engine.adapter_id().into(),
        target_profile: TARGET.into(),
        state_computer_contract_version: STATE_COMPUTER_CONTRACT_VERSION.into(),
        registry: &mut registry,
        policy: NegotiationPolicy::Require,
        fallback_factory: None,
    };
    let config = ApalacheConfig {
        spec_path: args[3].clone(),
        init_predicate: Some("Init".into()),
        next_predicate: Some("Next".into()),
        const_init: None,
        invariant: "Safety".into(),
        length_bound: 30,
        param_vars: Some("parameters".into()),
    };
    let result =
        run_client_with_traces_negotiated(&args[2], config, args[5..].to_vec(), &mut selection);
    let rejected = matches!(&result, Err(NegotiatedError::Registration { code, .. }) if code == "interface_digest_mismatch");
    let e = evidence.borrow();
    let actions = match engine {
        Engine::MachineState => ["Propagate", "FinishStateflow"],
        Engine::LLVMIR => ["ExpandSlice", "FinishSlice"],
    };
    let coverage = actions
        .iter()
        .all(|action| e.actions.get(action).copied().unwrap_or_default() > 0);
    let passed = if mode == "good" {
        result.is_ok()
            && coverage
            && e.factories == 1
            && e.port_drops == 1
            && e.initializations == args.len() - 5
            && e.completed == args.len() - 5
            && e.observations == expected_states
    } else {
        rejected
            && e.factories == 0
            && e.port_drops == 0
            && e.initializations == 0
            && e.observations == 0
    };
    println!(
        "{}",
        json!({
            "schema": "ariadne.stage-e-mirrorrust-replay/v1", "engine": args[0], "mode": mode,
            "gatePassed": passed, "modelMatched": result.is_ok(), "semanticDigest": digest,
            "status": if result.is_ok() { "passed" } else if rejected { "rejected" } else { "failed" },
            "error": result.as_ref().err().map(ToString::to_string),
            "factoryCalls": e.factories, "portDrops": e.port_drops, "initializations": e.initializations,
            "observationsDispatched": e.observations,
            "matchedObservations": if result.is_ok() { Some(e.observations) } else { None },
            "completedTraces": e.completed, "coverageSatisfied": result.is_ok() && coverage,
            "matchedActions": if result.is_ok() { Some(&e.actions) } else { None },
            "scope": "existing formal fixture replay; broader Stage E acceptance remains open",
        })
    );
    Ok(passed)
}

fn main() {
    match execute() {
        Ok(true) => {}
        Ok(false) => std::process::exit(1),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
