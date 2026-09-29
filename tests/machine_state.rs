use ariadne::machine_state as ms;
use ariadne::{
    AnalysisRequest, Analyzer as RecoveryAnalyzer, Edge, EdgeKind, Instruction, InstructionKind,
    Phase as RecoveryPhase,
};
use std::collections::{BTreeMap, BTreeSet};

fn id(name: &str) -> ms::StateId {
    ms::StateId(name.into())
}
fn values(names: &[&str]) -> ms::ValueSet {
    names
        .iter()
        .map(|name| ms::AbstractValue((*name).into()))
        .collect()
}
fn state(status: ms::Status, rax: &[&str], zf: &[&str]) -> ms::AbstractState {
    ms::AbstractState {
        status,
        valuation: [("rax".into(), values(rax)), ("zf".into(), values(zf))].into(),
    }
}
fn edge(src: u64, dst: u64, kind: EdgeKind) -> Edge {
    Edge { src, dst, kind }
}
fn step(src: u64, dst: u64, kind: EdgeKind, before: &str, after: &str) -> ms::StateStep {
    ms::StateStep {
        edge: edge(src, dst, kind),
        before: id(before),
        after: id(after),
    }
}
fn fixture() -> ms::Request {
    let nodes: ariadne::AddressSet = (1..=5).collect();
    let mut effects: BTreeMap<_, _> = nodes
        .iter()
        .map(|&site| (site, ms::Effects::default()))
        .collect();
    effects.get_mut(&1).unwrap().may_defs.insert("rax".into());
    effects.get_mut(&1).unwrap().must_defs.insert("rax".into());
    effects.get_mut(&2).unwrap().may_defs.insert("zf".into());
    effects.get_mut(&2).unwrap().must_defs.insert("zf".into());
    effects.get_mut(&2).unwrap().uses.insert("rax".into());
    effects.get_mut(&3).unwrap().uses.insert("zf".into());
    ms::Request {
        snapshot_id: "machine-state-snapshot".into(),
        nodes: nodes.clone(),
        structural_edges: [
            edge(1, 2, EdgeKind::Next),
            edge(2, 3, EdgeKind::Next),
            edge(3, 4, EdgeKind::Taken),
            edge(3, 5, EdgeKind::Fallthrough),
        ]
        .into(),
        value_domain: [
            ("rax".into(), values(&["zero", "five", "other"])),
            ("zf".into(), values(&["false", "true"])),
        ]
        .into(),
        catalogue: [
            (
                id("entry"),
                state(
                    ms::Status::Running,
                    &["zero", "five", "other"],
                    &["false", "true"],
                ),
            ),
            (
                id("rax-five"),
                state(ms::Status::Running, &["five"], &["false", "true"]),
            ),
            (
                id("zf-true"),
                state(ms::Status::Running, &["five"], &["true"]),
            ),
            (
                id("returned"),
                state(ms::Status::Returned, &["five"], &["true"]),
            ),
        ]
        .into(),
        entry_states: [(1, [id("entry")].into())].into(),
        effects,
        steps: [
            step(1, 2, EdgeKind::Next, "entry", "rax-five"),
            step(2, 3, EdgeKind::Next, "rax-five", "zf-true"),
            step(3, 4, EdgeKind::Taken, "zf-true", "zf-true"),
        ]
        .into(),
        terminal_transitions: [
            ms::TerminalTransition {
                site: 4,
                before: id("zf-true"),
                after: id("returned"),
                outcome: ms::TerminalOutcome::Returned,
            },
            ms::TerminalTransition {
                site: 5,
                before: id("zf-true"),
                after: id("returned"),
                outcome: ms::TerminalOutcome::Returned,
            },
        ]
        .into(),
        complete_sites: nodes,
        adapter_obligations: BTreeSet::new(),
    }
}

#[test]
fn formal_five_node_fixture_matches_stateflow_schedule_and_observations() {
    let mut analyzer = ms::Analyzer::new(fixture()).unwrap();
    assert_eq!(analyzer.state().phase, ms::Phase::Stateflow);
    assert!(
        analyzer
            .observations()
            .feasible_edges
            .contains(&edge(1, 2, EdgeKind::Next))
    );
    assert!(analyzer.observations().provably_infeasible_edges.is_empty());
    for site in [2, 3, 4] {
        assert!(analyzer.step());
        assert_eq!(analyzer.state().states_at[&site].len(), 1);
        assert_eq!(analyzer.state().phase, ms::Phase::Stateflow);
    }
    assert!(analyzer.step());
    assert_eq!(analyzer.state().phase, ms::Phase::Done);
    assert!(!analyzer.step());
    let result = analyzer.finish();
    assert_eq!(result.state().states_at[&1], [id("entry")].into());
    assert_eq!(result.state().states_at[&2], [id("rax-five")].into());
    assert_eq!(result.state().states_at[&3], [id("zf-true")].into());
    assert_eq!(result.state().states_at[&4], [id("zf-true")].into());
    assert!(result.state().states_at[&5].is_empty());
    let observations = result.observations();
    assert_eq!(
        observations.feasible_edges,
        [
            edge(1, 2, EdgeKind::Next),
            edge(2, 3, EdgeKind::Next),
            edge(3, 4, EdgeKind::Taken)
        ]
        .into()
    );
    assert_eq!(
        observations.provably_infeasible_edges,
        [edge(3, 5, EdgeKind::Fallthrough)].into()
    );
    assert!(observations.unknown_feasibility_edges.is_empty());
    assert_eq!(observations.not_reached_nodes, [5].into());
    assert_eq!(observations.reached_terminal_transitions.len(), 1);
    assert_eq!(
        observations
            .reached_terminal_transitions
            .iter()
            .next()
            .unwrap()
            .site,
        4
    );
    assert!(observations.obligations.is_empty());
}

#[test]
fn invalid_domains_frames_edges_and_terminal_states_are_rejected_before_analysis() {
    let mut request = fixture();
    request.entry_states.insert(2, BTreeSet::new());
    assert_eq!(request.validate().unwrap_err().field, "entry_states");

    let mut request = fixture();
    request.value_domain.get_mut("zf").unwrap().clear();
    assert_eq!(request.validate().unwrap_err().field, "value_domain");

    let mut request = fixture();
    request.effects.get_mut(&1).unwrap().may_defs.clear();
    assert_eq!(request.validate().unwrap_err().field, "effects");

    let mut request = fixture();
    request
        .effects
        .get_mut(&2)
        .unwrap()
        .may_defs
        .insert("rax".into());
    request.effects.get_mut(&2).unwrap().may_defs.clear();
    request.effects.get_mut(&2).unwrap().must_defs.clear();
    assert_eq!(request.validate().unwrap_err().field, "steps");

    let mut request = fixture();
    request.structural_edges.insert(edge(3, 5, EdgeKind::Call));
    assert_eq!(request.validate().unwrap_err().field, "structural_edges");

    let mut request = fixture();
    request.terminal_transitions.insert(ms::TerminalTransition {
        site: 4,
        before: id("zf-true"),
        after: id("rax-five"),
        outcome: ms::TerminalOutcome::Returned,
    });
    assert_eq!(
        request.validate().unwrap_err().field,
        "terminal_transitions"
    );
}

#[test]
fn incomplete_and_unreached_sources_keep_unwitnessed_edges_unknown() {
    let mut request = fixture();
    request.complete_sites.remove(&3);
    let result = ms::analyze(request).unwrap();
    assert!(result.observations().provably_infeasible_edges.is_empty());
    assert_eq!(
        result.observations().unknown_feasibility_edges,
        [edge(3, 5, EdgeKind::Fallthrough)].into()
    );
    assert!(result.observations().obligations.contains(&ms::Obligation {
        site: 3,
        reason: ms::ObligationReason::IncompleteSemantics,
    }));

    let mut request = fixture();
    request.entry_states.clear();
    let result = ms::analyze(request).unwrap();
    assert!(result.observations().feasible_edges.is_empty());
    assert!(result.observations().provably_infeasible_edges.is_empty());
    assert_eq!(
        result.observations().unknown_feasibility_edges,
        result.request().structural_edges
    );
    assert_eq!(result.observations().not_reached_nodes, (1..=5).collect());
}

#[test]
fn joins_loops_and_equal_valuations_keep_distinct_state_id_paths() {
    let mut request = fixture();
    request.catalogue.insert(
        id("zf-alternative"),
        state(ms::Status::Running, &["five"], &["true"]),
    );
    request
        .steps
        .insert(step(2, 3, EdgeKind::Next, "rax-five", "zf-alternative"));
    request.steps.insert(step(
        3,
        5,
        EdgeKind::Fallthrough,
        "zf-alternative",
        "zf-alternative",
    ));
    request.structural_edges.insert(edge(4, 3, EdgeKind::Jump));
    request
        .steps
        .insert(step(4, 3, EdgeKind::Jump, "zf-true", "zf-true"));
    request.terminal_transitions.insert(ms::TerminalTransition {
        site: 5,
        before: id("zf-alternative"),
        after: id("returned"),
        outcome: ms::TerminalOutcome::Returned,
    });

    // Independent pair-reachability oracle, seeded only from entry facts.
    let mut pairs: BTreeSet<_> = request
        .entry_states
        .iter()
        .flat_map(|(&site, ids)| ids.iter().map(move |id| (site, id.clone())))
        .collect();
    let mut frontier: Vec<_> = pairs.iter().cloned().collect();
    while let Some((site, before)) = frontier.pop() {
        for transition in request
            .steps
            .iter()
            .filter(|row| row.edge.src == site && row.before == before)
        {
            let after = (transition.edge.dst, transition.after.clone());
            if pairs.insert(after.clone()) {
                frontier.push(after);
            }
        }
    }
    let result = ms::analyze(request).unwrap();
    let actual: BTreeSet<_> = result
        .state()
        .states_at
        .iter()
        .flat_map(|(&site, ids)| ids.iter().map(move |id| (site, id.clone())))
        .collect();
    assert_eq!(actual, pairs);
    assert_eq!(
        result.state().states_at[&3],
        [id("zf-true"), id("zf-alternative")].into()
    );
    assert!(
        result
            .observations()
            .feasible_edges
            .contains(&edge(3, 4, EdgeKind::Taken))
    );
    assert!(
        result
            .observations()
            .feasible_edges
            .contains(&edge(3, 5, EdgeKind::Fallthrough))
    );
    assert!(
        result
            .observations()
            .feasible_edges
            .contains(&edge(4, 3, EdgeKind::Jump))
    );
    assert!(result.observations().provably_infeasible_edges.is_empty());
    assert_eq!(result.observations().reached_terminal_transitions.len(), 2);
}

fn recovery() -> RecoveryAnalyzer {
    let request = AnalysisRequest {
        snapshot_id: "handoff".into(),
        addresses: [1, 2, 99].into(),
        locations: ["x".into()].into(),
        entry_points: [1].into(),
        slice_seeds: [2, 99].into(),
        file_backed: [1, 2].into(),
        decodable: [1, 2].into(),
        instructions: [
            (
                1,
                Instruction {
                    kind: InstructionKind::Call,
                    fall: [2].into(),
                    targets: [99].into(),
                    ..Instruction::default()
                },
            ),
            (
                2,
                Instruction {
                    kind: InstructionKind::Return,
                    ..Instruction::default()
                },
            ),
            (99, Instruction::default()),
        ]
        .into(),
        ..AnalysisRequest::default()
    };
    let mut analyzer = RecoveryAnalyzer::new(request).unwrap();
    while analyzer.state().phase == RecoveryPhase::Recover {
        assert!(analyzer.step());
    }
    analyzer
}
fn handoff_inputs() -> ms::SemanticInputs {
    let entry = ms::AbstractState {
        status: ms::Status::Running,
        valuation: [("x".into(), values(&["same"]))].into(),
    };
    ms::SemanticInputs {
        snapshot_id: "handoff".into(),
        value_domain: [("x".into(), values(&["same"]))].into(),
        catalogue: [(id("entry"), entry.clone()), (id("after"), entry)].into(),
        entry_states: [(1, [id("entry")].into())].into(),
        steps: [step(1, 2, EdgeKind::Summary, "entry", "after")].into(),
        terminal_transitions: BTreeSet::new(),
        complete_sites: BTreeSet::new(),
        adapter_obligations: BTreeSet::new(),
    }
}

#[test]
fn recovery_handoff_keeps_summary_edge_and_separate_call_obligation() {
    let analyzer = recovery();
    let handoff = ms::prepare_from_recovery(&analyzer, handoff_inputs()).unwrap();
    assert_eq!(handoff.request.nodes, [1, 2].into());
    assert_eq!(
        handoff.request.structural_edges,
        [edge(1, 2, EdgeKind::Summary)].into()
    );
    assert!(
        handoff
            .context
            .full_edges
            .contains(&edge(1, 99, EdgeKind::Call))
    );
    assert_eq!(handoff.context.missing_slice_seeds, [99].into());
    assert!(!handoff.context.recovery_obligations.is_empty());
    let result = ms::analyze(handoff.request).unwrap();
    assert_eq!(result.state().states_at[&2], [id("after")].into());
    assert!(
        result
            .observations()
            .feasible_edges
            .contains(&edge(1, 2, EdgeKind::Summary))
    );
    assert_eq!(result.observations().obligations.len(), 2);

    let mut mismatched = handoff_inputs();
    mismatched.snapshot_id = "other".into();
    assert!(matches!(
        ms::prepare_from_recovery(&analyzer, mismatched),
        Err(ms::HandoffError::SnapshotMismatch)
    ));
    let mut mismatched = handoff_inputs();
    mismatched
        .value_domain
        .insert("extra".into(), values(&["same"]));
    assert!(matches!(
        ms::prepare_from_recovery(&analyzer, mismatched),
        Err(ms::HandoffError::LocationMismatch)
    ));
}
