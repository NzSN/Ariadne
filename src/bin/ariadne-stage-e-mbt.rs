use ariadne::mbt::stage_e::{self as integration, Engine, Evidence, TARGET};
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
    if !["good", "wrong-digest", "mutant"].contains(&mode) {
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
    let mut expected_cases = Vec::new();
    let mut expected_actions = std::collections::BTreeMap::<String, usize>::new();
    let mut expected_pairs = std::collections::BTreeMap::<String, usize>::new();
    let wire = |name: &str| {
        match name {
            "init" => "Initialize",
            "propagate" => "Propagate",
            "finishStateflow" => "FinishStateflow",
            "expandSlice" => "ExpandSlice",
            "finishSlice" => "FinishSlice",
            _ => "unknown",
        }
        .to_owned()
    };
    for path in &args[5..] {
        let trace: serde_json::Value = serde_json::from_slice(&std::fs::read(path)?)?;
        let states = trace["states"].as_array().ok_or("missing states")?;
        expected_cases.push(
            states[0]["case_id"]
                .as_str()
                .ok_or("missing case ID")?
                .to_owned(),
        );
        let mut previous = None;
        for state in states {
            let action = wire(state["action_taken"].as_str().ok_or("missing action")?);
            *expected_actions.entry(action.clone()).or_default() += 1;
            if let Some(previous) = previous {
                *expected_pairs
                    .entry(format!("{previous}->{action}"))
                    .or_default() += 1;
            }
            previous = Some(action);
        }
    }
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let corpus = std::path::Path::new(&args[4])
        .parent()
        .ok_or("lock has no parent")?;
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(corpus.join("manifest.json"))?)?;
    let model_name = match engine {
        Engine::MachineState => "MachineStateReplay",
        Engine::LLVMIR => "LLVMIRReplay",
    };
    let case_ids = manifest["engines"][model_name]
        .as_array()
        .ok_or("missing engine catalogue")?;
    let mut registration = match engine {
        Engine::MachineState => {
            let requests = case_ids
                .iter()
                .map(|id| -> Result<_, Box<dyn std::error::Error>> {
                    let id = id.as_str().ok_or("invalid case ID")?;
                    Ok((
                        id.to_owned(),
                        ariadne::reports::decode_machine_request(&std::fs::read(
                            corpus.join("inputs").join(format!("{id}.json")),
                        )?)?,
                    ))
                })
                .collect::<Result<_, _>>()?;
            integration::machine_state_cases_registration(requests, evidence.clone())?
        }
        Engine::LLVMIR => {
            let requests = case_ids
                .iter()
                .map(|id| -> Result<_, Box<dyn std::error::Error>> {
                    let id = id.as_str().ok_or("invalid case ID")?;
                    Ok((
                        id.to_owned(),
                        ariadne::reports::decode_ir_request(&std::fs::read(
                            corpus.join("inputs").join(format!("{id}.json")),
                        )?)?,
                    ))
                })
                .collect::<Result<_, _>>()?;
            integration::llvm_ir_cases_registration(requests, evidence.clone())?
        }
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
    let mismatch = match &result {
        Err(NegotiatedError::Legacy(Error::StepMismatch {
            action,
            expected,
            actual,
            hints,
            ..
        })) => Some(
            json!({"action":action,"expected":encode_state(expected),"actual":encode_state(actual),"hints":format!("{hints:?}")}),
        ),
        _ => None,
    };
    let actual_actions: std::collections::BTreeMap<String, usize> =
        e.actions.iter().map(|(a, n)| (a.to_string(), *n)).collect();
    let passed = if mode == "mutant" {
        mismatch.is_some() && e.factories == 1 && e.port_drops == 1
    } else if mode == "good" {
        result.is_ok()
            && coverage
            && e.factories == 1
            && e.port_drops == 1
            && e.initializations == args.len() - 5
            && e.completed == args.len() - 5
            && e.observations == expected_states
            && e.cases == expected_cases
            && actual_actions == expected_actions
            && e.pairs == expected_pairs
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
            "status": if result.is_ok() { "passed" } else if rejected { "rejected" } else if mismatch.is_some() { "mismatch" } else { "failed" },
            "error": result.as_ref().err().map(ToString::to_string),"mismatch":mismatch,
            "factoryCalls": e.factories, "portDrops": e.port_drops, "initializations": e.initializations,
            "observationsDispatched": e.observations,
            "matchedObservations": if result.is_ok() { Some(e.observations) } else { None },
            "completedTraces": e.completed, "coverageSatisfied": result.is_ok() && coverage,
            "matchedActions": if result.is_ok() { Some(&e.actions) } else { None },
            "matchedPairs": if result.is_ok() {Some(&e.pairs)} else {None},"cases":e.cases,
            "scope": "generated finite campaign replay; supplied semantics and universal refinement are separate boundaries",
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
