mod adapter;
mod fixtures;

// Compiler-owned bytes are checked by model_interface_gen check. Do not format
// or hand-edit them; the emitter includes support helpers unused by this model.
#[rustfmt::skip]
#[allow(dead_code, unused_variables)]
#[path = "../generated/AriadneReplayMirror.generated.rs"]
mod generated;

#[cfg(test)]
mod tests;

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

use mirrorrust::*;
use serde_json::json;

const ADAPTER: &str = "ariadne.machine-analysis/v1";
const TARGET: &str = "mirrorrust-v1";
const ACTIONS: [&str; 6] = [
    "Visit",
    "FinishRecovery",
    "Propagate",
    "FinishDataflow",
    "ExpandSlice",
    "FinishSlice",
];
const PAIRS: [&str; 7] = [
    "Visit->Visit",
    "Visit->FinishRecovery",
    "FinishRecovery->Propagate",
    "Propagate->Propagate",
    "Propagate->FinishDataflow",
    "FinishDataflow->ExpandSlice",
    "ExpandSlice->FinishSlice",
];

#[derive(Default)]
pub(crate) struct Evidence {
    factories: usize,
    port_drops: usize,
    observations: usize,
    completed: usize,
    fixtures: Vec<String>,
    actions: BTreeMap<String, usize>,
    pairs: BTreeMap<String, usize>,
    previous_action: Option<String>,
}

impl Evidence {
    fn record_action(&mut self, stable_action: &str) {
        *self.actions.entry(stable_action.into()).or_default() += 1;
        if let Some(previous) = self.previous_action.take() {
            *self
                .pairs
                .entry(format!("{previous}->{stable_action}"))
                .or_default() += 1;
        }
        self.previous_action = Some(stable_action.into());
    }
}

fn execute() -> Result<bool, Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() < 5 || !["good", "mutant", "wrong-digest"].contains(&args[0].as_str()) {
        return Err("usage: ariadne-mbt good|mutant|wrong-digest MIRROR SPEC LOCK TRACE...".into());
    }
    let mode = &args[0];
    let lock: serde_json::Value = serde_json::from_slice(&std::fs::read(&args[3])?)?;
    let compiled_contract: serde_json::Value = serde_json::from_str(generated::CONTRACT_JSON)?;
    if lock["semanticDigest"].as_str() != Some(generated::SEMANTIC_DIGEST)
        || lock["contract"] != compiled_contract
    {
        return Err("compiled generated binding differs from the selected interface lock".into());
    }
    let compiled_digest = SemanticDigest::from_hex(generated::SEMANTIC_DIGEST)?;
    let mut metadata = generated::model_interface();
    if mode == "wrong-digest" {
        metadata.semantic_digest = "0".repeat(64);
    }
    let requested_digest = SemanticDigest::from_hex(&metadata.semantic_digest)?;
    let digest_text = metadata.semantic_digest.clone();
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let factory_evidence = evidence.clone();
    let mut registry = CompiledAdapterRegistry::new(vec![CompiledAdapterRegistration {
        key: CompiledAdapterKey {
            // The negative-admission case needs a local registry entry for its
            // deliberately wrong pin to reach the real server's verify gate.
            semantic_digest: requested_digest,
            adapter_id: ADAPTER.into(),
            target_profile: TARGET.into(),
            state_computer_contract_version: STATE_COMPUTER_CONTRACT_VERSION.into(),
        },
        factory: Box::new(move |matched| {
            factory_evidence.borrow_mut().factories += 1;
            if matched.semantic_digest() != compiled_digest {
                return Err(BindingError::new(
                    "digest_mismatch",
                    "unexpected matched context",
                ));
            }
            generated::bind_ariadne_replay(
                adapter::Adapter::new(factory_evidence.clone()),
                matched.effective_config(),
            )?
            .into_local_binding()
        }),
    }]);
    let mut selection = CompiledAdapterSelection {
        metadata,
        adapter_id: ADAPTER.into(),
        target_profile: TARGET.into(),
        state_computer_contract_version: STATE_COMPUTER_CONTRACT_VERSION.into(),
        registry: &mut registry,
        policy: NegotiationPolicy::Require,
        fallback_factory: None,
    };
    let config = ApalacheConfig {
        spec_path: args[2].clone(),
        init_predicate: Some("Init".into()),
        next_predicate: Some("Next".into()),
        const_init: None,
        invariant: "Safety".into(),
        length_bound: 30,
        param_vars: Some("parameters".into()),
    };
    let result =
        run_client_with_traces_negotiated(&args[1], config, args[4..].to_vec(), &mut selection);
    let e = evidence.borrow();
    let coverage = ACTIONS
        .iter()
        .all(|a| e.actions.get(*a).copied().unwrap_or(0) > 0)
        && PAIRS
            .iter()
            .all(|p| e.pairs.get(*p).copied().unwrap_or(0) > 0)
        && ["Binary", "Dump", "Loop", "Closed", "Pipeline", "Calls"]
            .iter()
            .all(|fixture| e.fixtures.iter().filter(|f| f.as_str() == *fixture).count() >= 2);
    let mismatch = match &result {
        Err(Error::StepMismatch {
            action,
            expected,
            actual,
            hints,
            ..
        }) => Some(json!({
            "action": action, "expected": encode_state(expected), "actual": encode_state(actual),
            "hints": format!("{hints:?}"),
        })),
        _ => None,
    };
    let rejection = matches!(&result, Err(Error::Registration { code, .. }) if code == "interface_digest_mismatch");
    let passed = match mode.as_str() {
        "good" => {
            result.is_ok()
                && coverage
                && e.factories == 1
                && e.port_drops == 1
                && e.completed == args.len() - 4
                && e.fixtures.len() == args.len() - 4
        }
        "mutant" => mismatch.is_some() && e.factories == 1 && e.port_drops == 1,
        "wrong-digest" => rejection && e.factories == 0 && e.observations == 0 && e.port_drops == 0,
        _ => false,
    };
    println!(
        "{}",
        json!({
            "schema": "ariadne.mbt-replay/v2", "mode": mode, "gatePassed": passed,
            "modelMatched": result.is_ok(), "interfaceMatched": e.factories == 1,
            "status": if result.is_ok() {"passed"} else if mismatch.is_some() {"mismatch"} else if rejection {"rejected"} else {"failed"},
            "error": result.as_ref().err().map(ToString::to_string), "mismatch": mismatch,
            "semanticDigest": digest_text, "adapterId": ADAPTER, "targetProfile": TARGET,
            "bindingImplementation": "compiler-generated", "cleanupMechanism": "Rust Drop of generated binding port",
            "factoryCalls": e.factories, "portDrops": e.port_drops, "observationsDispatched": e.observations,
            "matchedObservations": if result.is_ok() {Some(e.observations)} else {None},
            "completedTraces": e.completed, "fixtures": e.fixtures,
            "matchedActionCounts": if result.is_ok() {Some(&e.actions)} else {None},
            "matchedPairCounts": if result.is_ok() {Some(&e.pairs)} else {None},
            "coverageSatisfied": result.is_ok() && coverage,
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
