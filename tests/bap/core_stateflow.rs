use ariadne::bap::core_session::{CoreConfig, StateflowSession};
use ariadne::bap::stateflow_adapter::{NativeStateflow, encode_request};
use ariadne::{AddressSet, Edge, EdgeKind, machine_state};
use serde_json::json;
use std::path::PathBuf;
#[path = "../../src/mbt/stage_e/fixtures_machine.rs"]
mod fixture;
fn config() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-stage2")
            }),
    )
}
#[test]
#[ignore = "requires explicitly built Stage 2 native helper"]
fn native_stateflow_matches_every_state_and_derived_observation() {
    for case in [
        "normal",
        "incomplete",
        "empty-roots",
        "equal-identities",
        "loop",
    ] {
        let mut request = fixture::request();
        match case {
            "incomplete" => request.complete_sites.clear(),
            "empty-roots" => request.entry_states.clear(),
            "equal-identities" => {
                let first = request
                    .catalogue
                    .keys()
                    .find(|id| request.catalogue[*id].status == machine_state::Status::Running)
                    .unwrap()
                    .clone();
                let other = machine_state::StateId("equal-but-distinct".into());
                request
                    .catalogue
                    .insert(other.clone(), request.catalogue[&first].clone());
                request
                    .entry_states
                    .values_mut()
                    .next()
                    .unwrap()
                    .insert(other);
            }
            "loop" => {
                let first = request.steps.iter().next().unwrap().clone();
                let edge = Edge {
                    src: first.edge.src,
                    dst: first.edge.src,
                    kind: EdgeKind::Jump,
                };
                request.structural_edges.insert(edge);
                request.steps.insert(machine_state::StateStep {
                    edge,
                    before: first.before.clone(),
                    after: first.before,
                });
            }
            _ => {}
        }
        let mut reference = machine_state::Analyzer::new(request.clone()).unwrap();
        let mut native = NativeStateflow::new(&config(), case, request).unwrap();
        let mut steps = 0;
        loop {
            assert_eq!(native.state(), reference.state(), "{case}: state {steps}");
            assert_eq!(
                native.observations(),
                &reference.observations(),
                "{case}: views {steps}"
            );
            let changed = reference.step();
            assert_eq!(native.step().unwrap(), changed);
            if !changed {
                break;
            }
            steps += 1;
            assert!(steps < 100);
        }
        let result = native.finish().unwrap();
        let expected = reference.finish();
        assert_eq!(result.state(), expected.state());
        assert_eq!(result.observations(), expected.observations());
    }
}
#[test]
#[ignore = "requires explicitly built Stage 2 native helper"]
fn native_stateflow_rejects_invalid_finite_contracts() {
    let request = fixture::request();
    let input = encode_request(&request).unwrap();
    for key in [
        "state_ids",
        "value_domain",
        "valuation",
        "state_status",
        "initial_states",
        "uses",
        "may_defs",
        "must_defs",
    ] {
        let mut bad = input.clone();
        bad[key] = json!([]);
        assert!(
            StateflowSession::start(&config(), key, &request.snapshot_id, &bad).is_err(),
            "accepted incomplete {key}"
        );
    }
    for mutation in [
        "status",
        "frame",
        "edge",
        "terminal",
        "obligation",
        "duplicate-map",
    ] {
        let mut bad = input.clone();
        match mutation {
            "status" => {
                for row in bad["state_status"].as_array_mut().unwrap() {
                    row["status"] = json!("faulted");
                }
            }
            "frame" => {
                for row in bad["may_defs"].as_array_mut().unwrap() {
                    row["locations"] = json!([]);
                }
                for row in bad["must_defs"].as_array_mut().unwrap() {
                    row["locations"] = json!([]);
                }
            }
            "edge" => bad["state_steps"][0]["kind"] = json!("call"),
            "terminal" => bad["terminal_transitions"][0]["outcome"] = json!("running"),
            "obligation" => {
                bad["adapter_obligations"] =
                    json!([{"site":"0x0000000000000001","reason":"incomplete-semantics"}])
            }
            "duplicate-map" => bad["initial_states"][1] = bad["initial_states"][0].clone(),
            _ => unreachable!(),
        }
        assert!(
            StateflowSession::start(&config(), mutation, &request.snapshot_id, &bad).is_err(),
            "accepted {mutation}"
        );
    }
}
