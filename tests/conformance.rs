mod common;

use DefinitionOrigin::{Entry, Instruction as Written};
use InstructionKind::*;
use ObligationReason::*;
use ariadne::*;
use common::*;

fn edge(src: Address, dst: Address, kind: EdgeKind) -> Edge {
    Edge { src, dst, kind }
}

fn obligation(site: Address, reason: ObligationReason) -> Obligation {
    Obligation { site, reason }
}

// Ports of AriadneExample.tla's three instruction tables and input policies.
fn example(input_kind: InputKind, scenario: &str) -> AnalysisRequest {
    let mut r = request(&[1, 2, 3, 4, 5, 6, 7], &["x", "target"]);
    r.snapshot_id = "example-snapshot".into();
    r.input_kind = input_kind;
    r.file_backed = [1, 2, 3, 4, 5, 7].into();
    r.captured = if scenario == "partial" {
        [1, 3, 4].into()
    } else {
        [1, 3, 4, 5].into()
    };
    r.trusted_fallback = [2, 7].into();
    r.decodable = (1..=6).collect();
    r.slice_seeds = if scenario == "loop" {
        [5].into()
    } else {
        [4, 5].into()
    };
    for address in 1..=7 {
        let summary = if scenario == "loop" {
            match address {
                1 => instruction(Conditional, &[2], &[3], true, &[], &[], &[]),
                2 | 3 => instruction(Ordinary, &[4], &[], true, &[], &["x"], &["x"]),
                4 => instruction(Conditional, &[5], &[2], true, &["x"], &[], &[]),
                _ => instruction(Return, &[], &[], true, &["x"], &[], &[]),
            }
        } else {
            match address {
                1 => instruction(Conditional, &[2], &[3], true, &[], &[], &[]),
                2 => instruction(Ordinary, &[4], &[], true, &[], &["x"], &["x"]),
                3 => instruction(
                    Indirect,
                    &[],
                    if scenario == "closed" {
                        &[4]
                    } else {
                        &[4, 6, 7]
                    },
                    scenario == "closed",
                    &["target"],
                    &[],
                    &[],
                ),
                4 => instruction(
                    Call,
                    &[5],
                    &[6],
                    scenario == "closed",
                    &["x"],
                    &[],
                    &["x", "target"],
                ),
                _ => instruction(Return, &[], &[], true, &["x"], &[], &[]),
            }
        };
        r.instructions.insert(address, summary);
    }
    r
}

fn partial_obligations() -> ObligationSet {
    [
        obligation(3, IndirectTargets),
        obligation(4, CallTargets),
        obligation(6, Unavailable),
        obligation(7, DecodeFailed),
    ]
    .into()
}

fn partial_edges() -> EdgeSet {
    [
        edge(1, 2, EdgeKind::Fallthrough),
        edge(1, 3, EdgeKind::Taken),
        edge(2, 4, EdgeKind::Next),
        edge(3, 4, EdgeKind::Indirect),
        edge(3, 6, EdgeKind::Indirect),
        edge(3, 7, EdgeKind::Indirect),
        edge(4, 5, EdgeKind::Summary),
        edge(4, 6, EdgeKind::Call),
    ]
    .into()
}

#[test]
fn binary_fixture() {
    let result = run_checked(example(InputKind::Binary, "partial"));
    assert_eq!(result.state.visited, (1..=7).collect());
    assert_eq!(result.state.decoded, (1..=5).collect());
    assert_eq!(result.state.edges, partial_edges());
    assert_eq!(result.state.obligations, partial_obligations());
    assert_eq!(result.state.slice, [2, 4, 5].into());
    assert!(result.missing_slice_seeds.is_empty());
    assert!(!result.scope_closed());
    assert_eq!(result.state.provenance[&1], ByteSource::File);
}

#[test]
fn dump_fixture() {
    let result = run_checked(example(InputKind::Dump, "partial"));
    assert_eq!(result.state.visited, (1..=7).collect());
    assert_eq!(result.state.decoded, (1..=4).collect());
    assert_eq!(result.state.edges, partial_edges());
    let mut expected = partial_obligations();
    expected.insert(obligation(5, Unavailable));
    assert_eq!(result.state.obligations, expected);
    assert_eq!(result.state.slice, [2, 4].into());
    assert_eq!(result.missing_slice_seeds, [5].into());
    assert_eq!(result.state.provenance[&1], ByteSource::Captured);
    assert_eq!(result.state.provenance[&2], ByteSource::File);
    assert!(!result.scope_closed());
}

#[test]
fn loop_fixture() {
    let result = run_checked(example(InputKind::Binary, "loop"));
    assert_eq!(result.state.decoded, (1..=5).collect());
    assert_eq!(result.state.slice, [2, 3, 5].into());
    assert_eq!(
        result.state.edges,
        [
            edge(1, 2, EdgeKind::Fallthrough),
            edge(1, 3, EdgeKind::Taken),
            edge(2, 4, EdgeKind::Next),
            edge(3, 4, EdgeKind::Next),
            edge(4, 5, EdgeKind::Fallthrough),
            edge(4, 2, EdgeKind::Taken),
        ]
        .into()
    );
    assert_eq!(
        result.state.reaching[&5],
        [
            definition("x", 2, Written),
            definition("x", 3, Written),
            definition("target", 1, Entry)
        ]
        .into()
    );
    assert!(result.scope_closed());
    assert_eq!(result.call_graph().count(), 0);
}

#[test]
fn closed_fixture() {
    let result = run_checked(example(InputKind::Dump, "closed"));
    assert_eq!(result.state.visited, (1..=5).collect());
    assert_eq!(result.state.decoded, (1..=5).collect());
    assert_eq!(result.state.slice, [2, 4, 5].into());
    assert_eq!(
        result.state.edges,
        partial_edges()
            .into_iter()
            .filter(|e| e.src != 3 || e.dst == 4)
            .collect()
    );
    assert!(result.scope_closed());
    assert_eq!(
        result.call_graph().copied().collect::<EdgeSet>(),
        [edge(4, 6, EdgeKind::Call)].into()
    );
    assert!(!result.state.visited.contains(&6));
}

fn pipeline() -> AnalysisRequest {
    let mut r = request(&[4096, 4100], &["x"]);
    r.snapshot_id = "pipeline-snapshot".into();
    r.instructions.insert(
        4096,
        instruction(Ordinary, &[4100], &[], true, &[], &["x"], &["x"]),
    );
    r.instructions
        .insert(4100, instruction(Return, &[], &[], true, &["x"], &[], &[]));
    r
}

#[test]
fn pipeline_fixture_and_eight_transition_witness() {
    let result = run_checked(pipeline());
    assert_eq!(result.state.decoded, [4096, 4100].into());
    assert_eq!(result.state.slice, [4096, 4100].into());
    assert_eq!(
        result.state.reaching[&4100],
        [definition("x", 4096, Written)].into()
    );
    assert_eq!(
        result.identity_of(4096),
        AddressIdentity {
            snapshot: "pipeline-snapshot".into(),
            va: 4096
        }
    );
    assert!(result.scope_closed());
    let mut analyzer = Analyzer::new(pipeline()).unwrap();
    let mut phases = vec![analyzer.state().phase];
    while analyzer.step() {
        phases.push(analyzer.state().phase);
    }
    assert_eq!(
        phases,
        [
            Phase::Recover,
            Phase::Recover,
            Phase::Recover,
            Phase::Dataflow,
            Phase::Dataflow,
            Phase::Dataflow,
            Phase::Slice,
            Phase::Slice,
            Phase::Done
        ]
    );
    assert_eq!(analyzer.finish(), result);
}

#[test]
fn calls_fixture_keeps_graph_visibility_discovery_and_dataflow_distinct() {
    let mut r = request(&[1, 2, 3, 4], &["x"]);
    r.snapshot_id = "calls-snapshot".into();
    r.entry_points = [1, 3].into();
    r.slice_seeds = [2, 3].into();
    r.instructions
        .insert(1, instruction(Call, &[2], &[3, 4], true, &[], &[], &["x"]));
    for address in [2, 3, 4] {
        r.instructions.insert(
            address,
            instruction(Return, &[], &[], true, &["x"], &[], &[]),
        );
    }
    let result = run_checked(r);
    assert_eq!(result.state.visited, [1, 2, 3].into());
    assert_eq!(result.state.decoded, [1, 2, 3].into());
    assert_eq!(result.state.slice, [1, 2, 3].into());
    assert_eq!(
        result.state.edges,
        [
            edge(1, 2, EdgeKind::Summary),
            edge(1, 3, EdgeKind::Call),
            edge(1, 4, EdgeKind::Call)
        ]
        .into()
    );
    assert_eq!(
        result.state.reaching[&2],
        [definition("x", 1, Entry), definition("x", 1, Written)].into()
    );
    assert_eq!(
        result.state.reaching[&3],
        [definition("x", 3, Entry)].into()
    );
    assert_eq!(
        result.local_graph().copied().collect::<EdgeSet>(),
        [edge(1, 2, EdgeKind::Summary)].into()
    );
    assert!(result.scope_closed());
}

#[test]
fn captured_decode_failure_does_not_use_file_fallback() {
    let mut r = request(&[1, 2], &["x"]);
    r.input_kind = InputKind::Dump;
    r.captured = [1].into();
    r.trusted_fallback = [1, 2].into();
    r.decodable.remove(&1);
    r.instructions
        .insert(1, instruction(Ordinary, &[2], &[], true, &[], &[], &[]));
    let result = run_checked(r);
    assert_eq!(result.state.visited, [1].into());
    assert!(result.state.decoded.is_empty());
    assert!(result.state.edges.is_empty());
    assert_eq!(
        result.state.obligations,
        [obligation(1, DecodeFailed)].into()
    );
    assert_eq!(result.missing_slice_seeds, [2].into());
}

#[test]
fn captured_jit_bytes_need_no_file_and_binary_ignores_capture() {
    let mut r = request(&[1], &[]);
    r.input_kind = InputKind::Dump;
    r.captured = [1].into();
    r.file_backed.clear();
    let result = run_checked(r.clone());
    assert_eq!(result.state.decoded, [1].into());
    assert_eq!(result.state.provenance[&1], ByteSource::Captured);
    r.input_kind = InputKind::Binary;
    let result = run_checked(r);
    assert!(result.state.decoded.is_empty());
    assert_eq!(
        result.state.obligations,
        [obligation(1, Unavailable)].into()
    );
}

#[test]
fn two_labels_to_one_destination_are_distinct_edges() {
    let mut r = request(&[1, 2], &[]);
    r.instructions
        .insert(1, instruction(Conditional, &[2], &[2], true, &[], &[], &[]));
    let result = run_checked(r);
    assert_eq!(
        result.state.edges,
        [
            edge(1, 2, EdgeKind::Taken),
            edge(1, 2, EdgeKind::Fallthrough)
        ]
        .into()
    );
    assert_eq!(result.state.visited, [1, 2].into());
}

#[test]
fn self_loop_terminates_and_entry_and_instruction_origins_do_not_collide() {
    let mut r = request(&[11], &["x"]);
    r.instructions.insert(
        11,
        instruction(Ordinary, &[11], &[], true, &["x"], &["x"], &["x"]),
    );
    let result = run_checked(r);
    assert_eq!(
        result.state.reaching[&11],
        [definition("x", 11, Entry), definition("x", 11, Written)].into()
    );
    assert_eq!(result.state.slice, [11].into());
    assert!(result.scope_closed());
}

#[test]
fn may_writes_preserve_origins_and_must_writes_kill_them() {
    let mut r = request(&[1, 2, 3, 4], &["x"]);
    r.instructions.insert(
        1,
        instruction(Ordinary, &[2], &[], true, &[], &["x"], &["x"]),
    );
    r.instructions
        .insert(2, instruction(Ordinary, &[3], &[], true, &[], &[], &["x"]));
    r.instructions.insert(
        3,
        instruction(Ordinary, &[4], &[], true, &[], &["x"], &["x"]),
    );
    r.instructions
        .insert(4, instruction(Return, &[], &[], true, &["x"], &[], &[]));
    let result = run_checked(r);
    assert_eq!(
        result.state.reaching[&3],
        [definition("x", 1, Written), definition("x", 2, Written)].into()
    );
    assert_eq!(
        result.state.reaching[&4],
        [definition("x", 3, Written)].into()
    );
    assert_eq!(result.state.slice, [3, 4].into());
}

#[test]
fn empty_targets_need_obligations_only_when_uncertified() {
    for kind in [Indirect, Call] {
        for complete in [false, true] {
            let mut r = request(&[1, 2], &[]);
            let fall: &[Address] = if kind == Call { &[2] } else { &[] };
            r.instructions
                .insert(1, instruction(kind, fall, &[], complete, &[], &[], &[]));
            let result = run_checked(r);
            let expected = if complete {
                ObligationSet::new()
            } else {
                [obligation(
                    1,
                    if kind == Call {
                        CallTargets
                    } else {
                        IndirectTargets
                    },
                )]
                .into()
            };
            assert_eq!(result.state.obligations, expected);
        }
    }
}

#[test]
fn closed_recovery_can_have_missing_slice_seeds() {
    let result = run_checked(request(&[1, 2], &["x"]));
    assert!(result.scope_closed());
    assert_eq!(result.missing_slice_seeds, [2].into());
    assert!(result.state.slice.is_empty());
    assert_eq!(result.state.visited, [1].into());
}

#[test]
fn entry_values_do_not_become_producer_instructions() {
    let mut r = request(&[1, 2], &["x"]);
    r.instructions
        .insert(1, instruction(Jump, &[], &[2], true, &[], &[], &[]));
    r.instructions
        .insert(2, instruction(Return, &[], &[], true, &["x"], &[], &[]));
    let result = run_checked(r);
    assert_eq!(
        result.state.reaching[&2],
        [definition("x", 1, Entry)].into()
    );
    assert_eq!(result.state.slice, [2].into());
}

#[test]
fn full_u64_addresses_are_preserved_without_arithmetic() {
    let mut r = request(&[0, u64::MAX], &["x"]);
    r.instructions.insert(
        0,
        instruction(Jump, &[], &[u64::MAX], true, &[], &["x"], &["x"]),
    );
    r.instructions.insert(
        u64::MAX,
        instruction(Return, &[], &[], true, &["x"], &[], &[]),
    );
    let result = run_checked(r);
    assert_eq!(result.state.slice, [0, u64::MAX].into());
    assert_eq!(
        result.state.edges,
        [edge(0, u64::MAX, EdgeKind::Jump)].into()
    );
}

#[test]
fn empty_locations_and_seeds_are_valid() {
    let mut r = request(&[1], &[]);
    r.slice_seeds.clear();
    let result = run_checked(r);
    assert!(result.state.slice.is_empty());
    assert!(result.state.reaching[&1].is_empty());
    assert!(result.scope_closed());
}

#[test]
fn owned_request_and_result_are_independent_of_caller_mutations() {
    let mut r = pipeline();
    let analyzer = Analyzer::new(r.clone()).unwrap();
    r.snapshot_id = "another-snapshot".into();
    r.file_backed.clear();
    r.instructions.clear();
    let result = analyzer.finish();
    assert_eq!(result.snapshot_id, "pipeline-snapshot");
    assert_eq!(result.state.slice, [4096, 4100].into());
    assert_eq!(result, analyze(pipeline()).unwrap());
}

#[test]
fn malformed_requests_are_rejected_before_analysis() {
    type Mutation = fn(&mut AnalysisRequest);
    let cases: &[(&str, Mutation)] = &[
        ("snapshot_id", |r| r.snapshot_id.clear()),
        ("addresses", |r| r.addresses.clear()),
        ("entry_points", |r| r.entry_points.clear()),
        ("entry_points", |r| {
            r.entry_points.insert(999);
        }),
        ("slice_seeds", |r| {
            r.slice_seeds.insert(999);
        }),
        ("captured", |r| {
            r.captured.insert(999);
        }),
        ("file_backed", |r| {
            r.file_backed.insert(999);
        }),
        ("decodable", |r| {
            r.decodable.insert(999);
        }),
        ("trusted_fallback", |r| {
            r.trusted_fallback.insert(999);
        }),
        ("trusted_fallback", |r| {
            r.file_backed.remove(&4100);
            r.trusted_fallback.insert(4100);
        }),
        ("instructions", |r| {
            r.instructions.remove(&4100);
        }),
        ("instructions", |r| {
            r.instructions.insert(999, Instruction::default());
        }),
        ("instructions", |r| {
            let summary = r.instructions.remove(&4100).unwrap();
            r.instructions.insert(999, summary);
        }),
        ("fall", |r| {
            r.instructions.get_mut(&4096).unwrap().fall.insert(999);
        }),
        ("fall", |r| {
            r.instructions.get_mut(&4096).unwrap().fall.clear()
        }),
        ("fall", |r| {
            r.instructions.get_mut(&4096).unwrap().fall.insert(4096);
        }),
        ("fall", |r| {
            r.instructions.get_mut(&4100).unwrap().fall.insert(4096);
        }),
        ("targets", |r| {
            r.instructions.get_mut(&4096).unwrap().targets.insert(999);
        }),
        ("targets", |r| {
            r.instructions.get_mut(&4096).unwrap().targets.insert(4100);
        }),
        ("targets", |r| {
            r.instructions.get_mut(&4100).unwrap().targets.insert(4096);
        }),
        ("targets", |r| {
            r.instructions.get_mut(&4096).unwrap().kind = Conditional
        }),
        ("targets", |r| {
            let i = r.instructions.get_mut(&4096).unwrap();
            i.kind = Conditional;
            i.targets = [4096, 4100].into();
        }),
        ("targets", |r| {
            let i = r.instructions.get_mut(&4096).unwrap();
            i.kind = Jump;
            i.fall.clear();
        }),
        ("uses", |r| {
            r.instructions
                .get_mut(&4096)
                .unwrap()
                .uses
                .insert("bad".into());
        }),
        ("must_defs", |r| {
            r.instructions.get_mut(&4096).unwrap().may_defs.clear()
        }),
        ("may_defs", |r| {
            r.instructions
                .get_mut(&4096)
                .unwrap()
                .may_defs
                .insert("bad".into());
        }),
        ("fall", |r| {
            r.decodable.remove(&4096);
            r.instructions.get_mut(&4096).unwrap().fall.clear();
        }),
    ];
    for (index, (field, mutate)) in cases.iter().enumerate() {
        let mut r = pipeline();
        mutate(&mut r);
        let error = Analyzer::new(r).unwrap_err();
        assert_eq!(error.field, *field, "case {index}: {error}");
        assert!(!error.to_string().is_empty());
    }
}
