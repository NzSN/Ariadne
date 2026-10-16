//! Consume literal independently derived prefixes. No native helper is needed.
//! Deadline cases validate admitted recorded prefixes, not reproduced clocks.
use ariadne::recovery::{
    RecoveryLimits, RecoveryReceipt, RecoveryReplayError, RecoveryResult, RecoveryStop, recover,
    replay_recovery,
};
use ariadne::{
    AddressSet, AnalysisRequest, AnalyzerMetrics, ByteSource, Edge, EdgeKind, InputKind,
    Instruction, InstructionKind, Obligation, ObligationReason, Phase, analyze,
};
use serde_json::Value;
use std::collections::BTreeMap;

fn cases() -> Vec<Value> {
    let data: Value = serde_json::from_str(include_str!(
        "investigation/fixtures/frame_structure_oracle.json"
    ))
    .unwrap();
    assert_eq!(data["schema"], "ariadne.frame-structure-oracle/v1");
    data["recovery_cases"].as_array().unwrap().clone()
}

fn addresses(value: &Value) -> AddressSet {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|address| address.as_u64().unwrap())
        .collect()
}

fn instruction_kind(value: &Value) -> InstructionKind {
    match value.as_str().unwrap() {
        "ordinary" => InstructionKind::Ordinary,
        "conditional" => InstructionKind::Conditional,
        "jump" => InstructionKind::Jump,
        "indirect" => InstructionKind::Indirect,
        "call" => InstructionKind::Call,
        "return" => InstructionKind::Return,
        "stop" => InstructionKind::Stop,
        kind => panic!("unrecognized literal oracle kind {kind}"),
    }
}

fn edge_kind(value: &Value) -> EdgeKind {
    match value.as_str().unwrap() {
        "next" => EdgeKind::Next,
        "taken" => EdgeKind::Taken,
        "fallthrough" => EdgeKind::Fallthrough,
        "jump" => EdgeKind::Jump,
        "indirect" => EdgeKind::Indirect,
        "summary" => EdgeKind::Summary,
        "call" => EdgeKind::Call,
        kind => panic!("unrecognized literal oracle edge kind {kind}"),
    }
}

fn request(case: &Value) -> AnalysisRequest {
    let input = &case["input"];
    AnalysisRequest {
        snapshot_id: format!("independent-frame-structure-oracle:{}", case["name"]),
        addresses: addresses(&input["addresses"]),
        entry_points: addresses(&input["entry_points"]),
        slice_seeds: addresses(&input["slice_seeds"]),
        input_kind: InputKind::Dump,
        captured: addresses(&input["captured"]),
        decodable: addresses(&input["decodable"]),
        instructions: input["instructions"]
            .as_array()
            .unwrap()
            .iter()
            .map(|record| {
                (
                    record["address"].as_u64().unwrap(),
                    Instruction {
                        kind: instruction_kind(&record["kind"]),
                        fall: addresses(&record["fall"]),
                        targets: addresses(&record["targets"]),
                        complete: record["complete"].as_bool().unwrap(),
                        ..Instruction::default()
                    },
                )
            })
            .collect(),
        ..AnalysisRequest::default()
    }
}

fn stop(case: &Value) -> RecoveryStop {
    match case["expected"]["stop_reason"].as_str().unwrap() {
        "drained" => RecoveryStop::Drained,
        "visit_limit" => RecoveryStop::VisitLimit,
        "deadline" => RecoveryStop::Deadline,
        reason => panic!("unrecognized literal oracle stop {reason}"),
    }
}

fn assert_projection(case: &Value, result: &RecoveryResult) {
    let expected = &case["expected"];
    let name = case["name"].as_str().unwrap();
    let state = result.state();
    assert_eq!(state.phase(), Phase::Recover, "{name}");
    assert_eq!(state.visited, addresses(&expected["visited"]), "{name}");
    assert_eq!(state.decoded, addresses(&expected["decoded"]), "{name}");
    assert_eq!(state.pending, addresses(&expected["pending"]), "{name}");
    assert_eq!(
        state.edges,
        expected["edges"]
            .as_array()
            .unwrap()
            .iter()
            .map(|edge| Edge {
                src: edge["src"].as_u64().unwrap(),
                dst: edge["dst"].as_u64().unwrap(),
                kind: edge_kind(&edge["kind"]),
            })
            .collect(),
        "{name}"
    );
    assert_eq!(
        state.obligations,
        expected["obligations"]
            .as_array()
            .unwrap()
            .iter()
            .map(|obligation| Obligation {
                site: obligation["site"].as_u64().unwrap(),
                reason: match obligation["reason"].as_str().unwrap() {
                    "unavailable" => ObligationReason::Unavailable,
                    "decode-failed" => ObligationReason::DecodeFailed,
                    "indirect-targets" => ObligationReason::IndirectTargets,
                    "call-targets" => ObligationReason::CallTargets,
                    reason => panic!("unrecognized literal oracle obligation {reason}"),
                },
            })
            .collect(),
        "{name}"
    );
    assert_eq!(
        state.provenance,
        expected["provenance"]
            .as_array()
            .unwrap()
            .iter()
            .map(|record| {
                (
                    record["address"].as_u64().unwrap(),
                    match record["source"].as_str().unwrap() {
                        "captured" => ByteSource::Captured,
                        "unavailable" => ByteSource::Unavailable,
                        source => panic!("unrecognized literal oracle source {source}"),
                    },
                )
            })
            .collect::<BTreeMap<_, _>>(),
        "{name}"
    );
    let visits = expected["recovery_visits"].as_u64().unwrap();
    assert_eq!(result.receipt().visits, visits, "{name}");
    assert_eq!(
        result.metrics(),
        AnalyzerMetrics {
            actions: visits,
            ..AnalyzerMetrics::default()
        },
        "{name}: extra phase transition, dataflow or slicing work"
    );
}

#[test]
fn independent_recovery_prefixes_match_frozen_control_facts() {
    for case in cases() {
        let input = &case["input"];
        let limits = RecoveryLimits {
            max_visits: input["max_visits"].as_u64().unwrap(),
            deadline_ms: u64::MAX,
        };
        if case["expected"]["request_status"] == "invalid_request" {
            let error = recover(request(&case), limits).unwrap_err();
            assert_eq!(
                error.field,
                case["expected"]["invalid_field"].as_str().unwrap()
            );
            continue;
        }
        if !input["deadline_before_visit"].is_null() {
            continue;
        }
        let result = recover(request(&case), limits).unwrap();
        assert_projection(&case, &result);
        assert_eq!(result.receipt().stop, stop(&case), "{}", case["name"]);
        let replayed =
            replay_recovery(request(&case), limits, *result.receipt(), limits.max_visits).unwrap();
        assert_eq!(replayed, result, "{}", case["name"]);
        if result.receipt().stop == RecoveryStop::Drained {
            let completed = analyze(request(&case)).unwrap();
            assert_eq!(result.state().visited, completed.state.visited);
            assert_eq!(result.state().decoded, completed.state.decoded);
            assert_eq!(result.state().edges, completed.state.edges);
            assert_eq!(result.state().obligations, completed.state.obligations);
            assert_eq!(result.state().provenance, completed.state.provenance);
        }
    }
}

#[test]
fn independent_deadline_receipts_replay_exact_recorded_prefixes() {
    for case in cases() {
        let checkpoint = &case["input"]["deadline_before_visit"];
        if checkpoint.is_null() {
            continue;
        }
        // A recorded visit checkpoint is not elapsed milliseconds. The positive
        // receipt supplies a consistent independent clock observation only.
        let deadline_ms = if checkpoint.as_u64().unwrap() == 0 {
            0
        } else {
            10
        };
        let limits = RecoveryLimits {
            max_visits: case["input"]["max_visits"].as_u64().unwrap(),
            deadline_ms,
        };
        let receipt = RecoveryReceipt {
            visits: case["expected"]["recovery_visits"].as_u64().unwrap(),
            elapsed_ms: deadline_ms,
            stop: stop(&case),
        };
        let replayed = replay_recovery(request(&case), limits, receipt, limits.max_visits).unwrap();
        assert_projection(&case, &replayed);
        assert_eq!(*replayed.receipt(), receipt);
    }
}

#[test]
fn independent_schedule_prefixes_follow_literal_visit_order() {
    for case in cases() {
        if case["expected"]["request_status"] == "invalid_request" {
            continue;
        }
        let order = case["expected"]["visited_order"].as_array().unwrap();
        for length in 0..=order.len() {
            let result = recover(
                request(&case),
                RecoveryLimits {
                    max_visits: length as u64,
                    deadline_ms: u64::MAX,
                },
            )
            .unwrap();
            let expected: AddressSet = order[..length]
                .iter()
                .map(|address| address.as_u64().unwrap())
                .collect();
            assert_eq!(
                result.state().visited,
                expected,
                "{}: prefix {length}",
                case["name"]
            );
        }
    }
}

#[test]
fn independent_host_replay_cap_is_not_raised_by_producer() {
    let case = cases()
        .into_iter()
        .find(|case| case["name"] == "straight-exact-budget")
        .unwrap();
    let limits = RecoveryLimits {
        max_visits: u64::MAX,
        deadline_ms: u64::MAX,
    };
    let receipt = RecoveryReceipt {
        visits: 2,
        elapsed_ms: 0,
        stop: RecoveryStop::Drained,
    };
    assert_eq!(
        replay_recovery(request(&case), limits, receipt, 1),
        Err(RecoveryReplayError::ReplayLimit)
    );
    for host in [2, 3] {
        let result = replay_recovery(request(&case), limits, receipt, host).unwrap();
        assert_projection(&case, &result);
    }
}

#[test]
fn independent_replay_rejects_forged_drain_and_visit_after_drain() {
    let case = cases()
        .into_iter()
        .find(|case| case["name"] == "straight-exact-budget")
        .unwrap();
    let limits = RecoveryLimits {
        max_visits: 3,
        deadline_ms: u64::MAX,
    };
    for (visits, stop) in [
        (1, RecoveryStop::Drained),
        (2, RecoveryStop::VisitLimit),
        (3, RecoveryStop::Drained),
    ] {
        assert!(
            matches!(
                replay_recovery(
                    request(&case),
                    limits,
                    RecoveryReceipt {
                        visits,
                        elapsed_ms: 0,
                        stop
                    },
                    3
                ),
                Err(RecoveryReplayError::InvalidReceipt(_))
            ),
            "forged receipt {visits}/{stop:?} was admitted"
        );
    }
}

#[test]
fn independent_final_unknown_guard_does_not_admit_candidate() {
    let case = cases()
        .into_iter()
        .find(|case| case["name"] == "final-unknown-guard-excludes-candidate")
        .unwrap();
    let result = recover(
        request(&case),
        RecoveryLimits {
            max_visits: 3,
            deadline_ms: u64::MAX,
        },
    )
    .unwrap();
    assert_projection(&case, &result);
    assert!(!result.state().decoded.contains(&20));
    assert!(!result.state().visited.contains(&30));
    assert!(result.state().edges.iter().all(|edge| edge.src != 20));
}
