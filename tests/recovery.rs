use ariadne::recovery::{
    RecoveryLimits, RecoveryReceipt, RecoveryReplayError, RecoveryStop, recover, replay_recovery,
};
use ariadne::{
    AnalysisRequest, AnalyzerMetrics, ByteSource, Edge, EdgeKind, InputKind, Instruction,
    InstructionKind, Obligation, ObligationReason, Phase, analyze,
};

fn graph() -> AnalysisRequest {
    // A diamond joins a loop, alongside failed roots. The call target and slice
    // seed are present in the immutable domain but are not local roots.
    AnalysisRequest {
        snapshot_id: "recovery-control-fixture".into(),
        addresses: [10, 20, 30, 40, 50, 60, 80, 90].into(),
        locations: ["x".into()].into(),
        entry_points: [10, 50, 60].into(),
        slice_seeds: [90].into(),
        input_kind: InputKind::Dump,
        captured: [10, 20, 30, 40, 50, 80, 90].into(),
        file_backed: [10, 20, 30, 40, 50, 60, 80, 90].into(),
        decodable: [10, 20, 30, 40, 60, 80, 90].into(),
        instructions: [
            (
                10,
                Instruction {
                    kind: InstructionKind::Conditional,
                    targets: [20].into(),
                    fall: [30].into(),
                    must_defs: ["x".into()].into(),
                    may_defs: ["x".into()].into(),
                    ..Instruction::default()
                },
            ),
            (
                20,
                Instruction {
                    kind: InstructionKind::Call,
                    targets: [80].into(),
                    fall: [40].into(),
                    uses: ["x".into()].into(),
                    ..Instruction::default()
                },
            ),
            (
                30,
                Instruction {
                    kind: InstructionKind::Jump,
                    targets: [40].into(),
                    ..Instruction::default()
                },
            ),
            (
                40,
                Instruction {
                    kind: InstructionKind::Indirect,
                    targets: [10].into(),
                    ..Instruction::default()
                },
            ),
            (50, Instruction::default()),
            (60, Instruction::default()),
            (
                80,
                Instruction {
                    kind: InstructionKind::Return,
                    ..Instruction::default()
                },
            ),
            (
                90,
                Instruction {
                    kind: InstructionKind::Return,
                    ..Instruction::default()
                },
            ),
        ]
        .into(),
        ..AnalysisRequest::default()
    }
}

fn limits(max_visits: u64) -> RecoveryLimits {
    RecoveryLimits {
        max_visits,
        deadline_ms: u64::MAX,
    }
}

fn edge(src: u64, dst: u64, kind: EdgeKind) -> Edge {
    Edge { src, dst, kind }
}

fn obligations() -> Vec<Obligation> {
    vec![
        Obligation {
            site: 20,
            reason: ObligationReason::CallTargets,
        },
        Obligation {
            site: 40,
            reason: ObligationReason::IndirectTargets,
        },
        Obligation {
            site: 50,
            reason: ObligationReason::DecodeFailed,
        },
        Obligation {
            site: 60,
            reason: ObligationReason::Unavailable,
        },
    ]
}

#[test]
fn exact_hard_coded_prefixes_preserve_attempts_frontiers_and_typed_edges() {
    let visits = [10, 20, 30, 40, 50, 60];
    let pending: [&[u64]; 7] = [
        &[10, 50, 60],
        &[20, 30, 50, 60],
        &[30, 40, 50, 60],
        &[40, 50, 60],
        &[50, 60],
        &[60],
        &[],
    ];
    let edges = [
        edge(10, 20, EdgeKind::Taken),
        edge(10, 30, EdgeKind::Fallthrough),
        edge(20, 80, EdgeKind::Call),
        edge(20, 40, EdgeKind::Summary),
        edge(30, 40, EdgeKind::Jump),
        edge(40, 10, EdgeKind::Indirect),
    ];
    for prefix in 0..=visits.len() {
        let result = recover(graph(), limits(prefix as u64)).unwrap();
        let state = result.state();
        let expected_visited = visits[..prefix].iter().copied().collect();
        assert_eq!(state.phase(), Phase::Recover);
        assert_eq!(state.pending, pending[prefix].iter().copied().collect());
        assert_eq!(state.visited, expected_visited);
        assert_eq!(
            state.decoded,
            visits[..prefix.min(4)].iter().copied().collect()
        );
        assert_eq!(
            state.edges,
            edges
                .iter()
                .filter(|edge| state.decoded.contains(&edge.src))
                .copied()
                .collect()
        );
        assert_eq!(
            state.obligations,
            obligations()
                .into_iter()
                .filter(|obligation| state.visited.contains(&obligation.site))
                .collect()
        );
        for (&address, &source) in &state.provenance {
            assert_eq!(
                source,
                if state.decoded.contains(&address) {
                    ByteSource::Captured
                } else {
                    ByteSource::Unavailable
                }
            );
        }
        assert_eq!(state.provenance.len(), 8);
        assert_eq!(result.request(), &graph());
        assert_eq!(result.limits(), &limits(prefix as u64));
        assert_eq!(result.receipt().visits, prefix as u64);
        assert_eq!(
            result.receipt().stop,
            if prefix == visits.len() {
                RecoveryStop::Drained
            } else {
                RecoveryStop::VisitLimit
            }
        );
        assert_eq!(
            result.metrics(),
            AnalyzerMetrics {
                actions: prefix as u64,
                ..AnalyzerMetrics::default()
            }
        );
    }
}

#[test]
fn drained_control_projection_matches_completion_without_becoming_done() {
    let recovery = recover(graph(), limits(100)).unwrap();
    let completed = analyze(graph()).unwrap();
    assert_eq!(completed.state.phase, Phase::Done);
    assert_eq!(recovery.state().phase(), Phase::Recover);
    assert_eq!(recovery.state().pending, completed.state.pending);
    assert_eq!(recovery.state().visited, completed.state.visited);
    assert_eq!(recovery.state().decoded, completed.state.decoded);
    assert_eq!(recovery.state().provenance, completed.state.provenance);
    assert_eq!(recovery.state().edges, completed.state.edges);
    assert_eq!(recovery.state().obligations, completed.state.obligations);
    assert!(!completed.state.reaching[&20].is_empty());
    assert!(!recovery.state().visited.contains(&80));
    assert!(!recovery.state().visited.contains(&90));
    assert_eq!(recovery.receipt().stop, RecoveryStop::Drained);
    assert_eq!(recovery.receipt().visits, 6);
}

#[test]
fn a_call_target_is_visited_only_when_also_an_independent_root() {
    let mut request = graph();
    request.entry_points.insert(80);
    let result = recover(request, limits(100)).unwrap();
    assert!(result.state().decoded.contains(&80));
    assert!(!result.state().visited.contains(&90));
    assert_eq!(result.receipt().visits, 7);
}

#[test]
fn detached_state_changes_do_not_change_the_sealed_result() {
    let result = recover(graph(), limits(1)).unwrap();
    let mut detached = result.state().clone();
    detached.visited.clear();
    detached.edges.clear();
    assert_eq!(result.state().visited, [10].into());
    assert_eq!(result.state().edges.len(), 2);
}

#[test]
fn zero_limits_stop_before_any_visit_and_visit_limit_has_priority() {
    let deadline = recover(
        graph(),
        RecoveryLimits {
            max_visits: 100,
            deadline_ms: 0,
        },
    )
    .unwrap();
    assert_eq!(deadline.receipt().stop, RecoveryStop::Deadline);
    assert_eq!(deadline.receipt().visits, 0);
    assert!(deadline.state().visited.is_empty());
    let both = recover(
        graph(),
        RecoveryLimits {
            max_visits: 0,
            deadline_ms: 0,
        },
    )
    .unwrap();
    assert_eq!(both.receipt().stop, RecoveryStop::VisitLimit);
    assert_eq!(both.receipt().visits, 0);
    assert_eq!(both.state(), deadline.state());
}

#[test]
fn invalid_requests_are_rejected_before_recovery() {
    let error = recover(AnalysisRequest::default(), limits(0)).unwrap_err();
    assert_eq!(error.field, "snapshot_id");
}

#[test]
fn producer_receipts_replay_to_identical_results() {
    for max_visits in [0, 1, 3, 6, 100] {
        let produced = recover(graph(), limits(max_visits)).unwrap();
        let replayed =
            replay_recovery(graph(), limits(max_visits), *produced.receipt(), 6).unwrap();
        assert_eq!(replayed, produced);
    }
}

#[test]
fn replay_checks_host_budget_before_analyzer_construction() {
    let receipt = RecoveryReceipt {
        visits: 1,
        elapsed_ms: 0,
        stop: RecoveryStop::VisitLimit,
    };
    assert_eq!(
        replay_recovery(AnalysisRequest::default(), limits(1), receipt, 0),
        Err(RecoveryReplayError::ReplayLimit)
    );
}

#[test]
fn replay_rejects_inconsistent_prefix_lengths_stops_and_clocks() {
    let cases = [
        (0, 0, RecoveryStop::Drained, 10, 100),
        (1, 0, RecoveryStop::VisitLimit, 10, 100),
        (3, 99, RecoveryStop::Deadline, 10, 100),
        (3, 100, RecoveryStop::Deadline, 3, 100),
        (6, 0, RecoveryStop::VisitLimit, 6, 100),
        (6, 100, RecoveryStop::Deadline, 10, 100),
        (7, 0, RecoveryStop::Drained, 10, 100),
        (1, 0, RecoveryStop::VisitLimit, 0, 100),
        (1, 0, RecoveryStop::VisitLimit, 1, 0),
    ];
    for (visits, elapsed_ms, stop, max_visits, deadline_ms) in cases {
        let error = replay_recovery(
            graph(),
            RecoveryLimits {
                max_visits,
                deadline_ms,
            },
            RecoveryReceipt {
                visits,
                elapsed_ms,
                stop,
            },
            100,
        )
        .unwrap_err();
        assert!(matches!(error, RecoveryReplayError::InvalidReceipt(_)));
    }
}

#[test]
fn deadline_receipts_replay_exact_prefix_without_reproducing_clock() {
    let declared = RecoveryLimits {
        max_visits: 100,
        deadline_ms: 10,
    };
    let receipt = RecoveryReceipt {
        visits: 3,
        elapsed_ms: 12,
        stop: RecoveryStop::Deadline,
    };
    let result = replay_recovery(graph(), declared, receipt, 3).unwrap();
    assert_eq!(result.state().visited, [10, 20, 30].into());
    assert_eq!(result.state().pending, [40, 50, 60].into());
    assert_eq!(*result.receipt(), receipt);
    assert_eq!(result.metrics().actions, 3);
}
