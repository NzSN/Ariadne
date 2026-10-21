//! Generated finite core conformance. This literal reference follows
//! Specs/Ariadne.tla; it is distinct from TLC-generated MirrorRust replay.
use ariadne::{
    AnalysisRequest, AnalysisState, Analyzer, ByteSource, Definition, DefinitionOrigin, Edge,
    EdgeKind, InputKind, Instruction, InstructionKind, Obligation, ObligationReason, Phase,
};
use proptest::prelude::*;
use proptest::test_runner::{Config, FileFailurePersistence, RngSeed};
use std::collections::BTreeSet;

fn config() -> Config {
    let cases = std::env::var("ARIADNE_CORE_PROPERTY_CASES")
        .map(|s| s.parse().expect("positive property case count"))
        .unwrap_or(256);
    assert!(cases > 0);
    let seed = std::env::var("ARIADNE_CORE_PROPERTY_SEED")
        .map(|s| s.parse().expect("u64 property seed"))
        .unwrap_or(0x61c4_982b_30a7_df05);
    Config {
        cases,
        max_shrink_iters: 4096,
        rng_seed: RngSeed::Fixed(seed),
        failure_persistence: Some(Box::new(FileFailurePersistence::Direct(
            "tests/core.proptest-regressions",
        ))),
        ..Config::default()
    }
}

fn requests() -> impl Strategy<Value = AnalysisRequest> {
    (
        proptest::collection::vec(any::<[u8; 8]>(), 1..=7),
        prop_oneof![Just(0u64), Just(1u64 << 48), Just(u64::MAX - 128)],
        any::<bool>(),
        any::<u8>(),
        any::<u8>(),
    )
        .prop_map(|(rows, base, binary, roots, seeds)| {
            let addresses: Vec<_> = (0..rows.len()).map(|i| base + i as u64 * 17).collect();
            let locations = ["gpr:rax", "flag:zf", "memory:any"];
            let mut request = AnalysisRequest {
                snapshot_id: format!("generated:{base}:{roots}:{seeds}"),
                addresses: addresses.iter().copied().collect(),
                locations: locations.iter().map(|s| (*s).into()).collect(),
                input_kind: if binary {
                    InputKind::Binary
                } else {
                    InputKind::Dump
                },
                ..AnalysisRequest::default()
            };
            for (i, row) in rows.iter().enumerate() {
                let address = addresses[i];
                if i == 0 || roots & (1 << i) != 0 {
                    request.entry_points.insert(address);
                }
                if seeds & (1 << i) != 0 {
                    request.slice_seeds.insert(address);
                }
                if row[1] & 1 != 0 {
                    request.captured.insert(address);
                }
                if row[1] & 2 != 0 {
                    request.file_backed.insert(address);
                    if row[1] & 4 != 0 {
                        request.trusted_fallback.insert(address);
                    }
                }
                if row[1] & 8 != 0 {
                    request.decodable.insert(address);
                }
                let kind = match row[0] % 7 {
                    0 => InstructionKind::Ordinary,
                    1 => InstructionKind::Conditional,
                    2 => InstructionKind::Jump,
                    3 => InstructionKind::Indirect,
                    4 => InstructionKind::Call,
                    5 => InstructionKind::Return,
                    _ => InstructionKind::Stop,
                };
                let mut instruction = Instruction {
                    kind,
                    complete: row[1] & 16 != 0,
                    ..Instruction::default()
                };
                if matches!(
                    kind,
                    InstructionKind::Ordinary
                        | InstructionKind::Conditional
                        | InstructionKind::Call
                ) {
                    instruction
                        .fall
                        .insert(addresses[row[2] as usize % rows.len()]);
                }
                if matches!(kind, InstructionKind::Conditional | InstructionKind::Jump) {
                    instruction
                        .targets
                        .insert(addresses[row[3] as usize % rows.len()]);
                } else if matches!(kind, InstructionKind::Indirect | InstructionKind::Call) {
                    instruction.targets.extend(
                        addresses
                            .iter()
                            .enumerate()
                            .filter(|(j, _)| row[3] & (1 << j) != 0)
                            .map(|(_, a)| *a),
                    );
                }
                for (j, location) in locations.iter().enumerate() {
                    if row[4] & (1 << j) != 0 {
                        instruction.uses.insert((*location).into());
                    }
                    if row[5] & (1 << j) != 0 {
                        instruction.may_defs.insert((*location).into());
                        if row[6] & (1 << j) != 0 {
                            instruction.must_defs.insert((*location).into());
                        }
                    }
                }
                request.instructions.insert(address, instruction);
            }
            request
        })
}

fn initial(request: &AnalysisRequest) -> AnalysisState {
    AnalysisState {
        pending: request.entry_points.clone(),
        provenance: request
            .addresses
            .iter()
            .map(|&a| (a, ByteSource::Unavailable))
            .collect(),
        reaching: request
            .addresses
            .iter()
            .map(|&a| (a, Default::default()))
            .collect(),
        ..AnalysisState::default()
    }
}

// No analyzer transfer, graph, definition-set union or completion helpers are
// used here. Every Incoming equation scans the frozen edge set from scratch.
fn incoming(
    request: &AnalysisRequest,
    state: &AnalysisState,
    address: u64,
) -> BTreeSet<Definition> {
    let mut result = BTreeSet::new();
    if request.entry_points.contains(&address) {
        for loc in &request.locations {
            result.insert(Definition {
                loc: loc.clone(),
                site: address,
                origin: DefinitionOrigin::Entry,
            });
        }
    }
    for edge in &state.edges {
        if edge.dst != address || edge.kind == EdgeKind::Call || !state.decoded.contains(&edge.src)
        {
            continue;
        }
        let instruction = &request.instructions[&edge.src];
        for definition in &state.reaching[&edge.src] {
            if !instruction.must_defs.contains(&definition.loc) {
                result.insert(definition.clone());
            }
        }
        for loc in &instruction.may_defs {
            result.insert(Definition {
                loc: loc.clone(),
                site: edge.src,
                origin: DefinitionOrigin::Instruction,
            });
        }
    }
    result
}

fn reference_step(request: &AnalysisRequest, state: &AnalysisState) -> Option<AnalysisState> {
    let mut next = state.clone();
    match state.phase {
        Phase::Recover => {
            let Some(&address) = state.pending.first() else {
                next.phase = Phase::Dataflow;
                return Some(next);
            };
            next.visited.insert(address);
            next.pending.remove(&address);
            let source = match request.input_kind {
                InputKind::Binary if request.file_backed.contains(&address) => ByteSource::File,
                InputKind::Dump if request.captured.contains(&address) => ByteSource::Captured,
                InputKind::Dump if request.trusted_fallback.contains(&address) => ByteSource::File,
                _ => ByteSource::Unavailable,
            };
            if source == ByteSource::Unavailable || !request.decodable.contains(&address) {
                next.obligations.insert(Obligation {
                    site: address,
                    reason: if source == ByteSource::Unavailable {
                        ObligationReason::Unavailable
                    } else {
                        ObligationReason::DecodeFailed
                    },
                });
                return Some(next);
            }
            next.decoded.insert(address);
            next.provenance.insert(address, source);
            let instruction = &request.instructions[&address];
            let pairs: &[(_, _)] = match instruction.kind {
                InstructionKind::Ordinary => &[(&instruction.fall, EdgeKind::Next)],
                InstructionKind::Conditional => &[
                    (&instruction.fall, EdgeKind::Fallthrough),
                    (&instruction.targets, EdgeKind::Taken),
                ],
                InstructionKind::Jump => &[(&instruction.targets, EdgeKind::Jump)],
                InstructionKind::Indirect => &[(&instruction.targets, EdgeKind::Indirect)],
                InstructionKind::Call => &[
                    (&instruction.targets, EdgeKind::Call),
                    (&instruction.fall, EdgeKind::Summary),
                ],
                _ => &[],
            };
            for (destinations, kind) in pairs {
                for &dst in *destinations {
                    next.edges.insert(Edge {
                        src: address,
                        dst,
                        kind: *kind,
                    });
                    if *kind != EdgeKind::Call && !next.visited.contains(&dst) {
                        next.pending.insert(dst);
                    }
                }
            }
            if !instruction.complete {
                let reason = match instruction.kind {
                    InstructionKind::Indirect => Some(ObligationReason::IndirectTargets),
                    InstructionKind::Call => Some(ObligationReason::CallTargets),
                    _ => None,
                };
                if let Some(reason) = reason {
                    next.obligations.insert(Obligation {
                        site: address,
                        reason,
                    });
                }
            }
        }
        Phase::Dataflow => {
            for &address in &state.decoded {
                let expected = incoming(request, state, address);
                if expected
                    .iter()
                    .any(|d| !state.reaching[&address].contains(d))
                {
                    next.reaching.get_mut(&address).unwrap().extend(expected);
                    return Some(next);
                }
            }
            next.phase = Phase::Slice;
            next.slice = request
                .slice_seeds
                .intersection(&state.decoded)
                .copied()
                .collect();
        }
        Phase::Slice => {
            for address in &state.slice {
                for definition in &state.reaching[address] {
                    if definition.origin == DefinitionOrigin::Instruction
                        && request.instructions[address].uses.contains(&definition.loc)
                    {
                        next.slice.insert(definition.site);
                    }
                }
            }
            if next.slice == state.slice {
                next.phase = Phase::Done;
            }
        }
        Phase::Done => return None,
    }
    Some(next)
}

proptest! {
    #![proptest_config(config())]

    #[test]
    fn generated_transitions_and_completion_match_reference(request in requests()) {
        let mut analyzer = Analyzer::new(request.clone()).unwrap();
        let mut expected = initial(&request);
        prop_assert_eq!(analyzer.state(), &expected);
        // Each non-phase transition visits a fresh address, adds at least one
        // (site,location,origin) reaching fact, or adds one slice member.
        let n = request.addresses.len();
        let limit = n + 2 * n * n * request.locations.len() + n + 3;
        let mut actions = 0;
        while let Some(next) = reference_step(&request, &expected) {
            actions += 1;
            prop_assert!(actions <= limit);
            prop_assert!(analyzer.step());
            prop_assert_eq!(analyzer.state(), &next);
            expected = next;
        }
        prop_assert!(!analyzer.step());
        prop_assert_eq!(analyzer.state(), &expected);
        let completed = Analyzer::new(request.clone()).unwrap().finish_bounded(ariadne::CompletionLimits {
            max_actions: limit as u64,
            ..ariadne::CompletionLimits::default()
        }).unwrap().0;
        prop_assert_eq!(&completed.state, &expected);
        prop_assert_eq!(&completed.snapshot_id, &request.snapshot_id);
        prop_assert_eq!(completed.missing_slice_seeds, request.slice_seeds.difference(&expected.decoded).copied().collect());
    }

    #[test]
    fn slice_seeds_do_not_become_roots(request in requests()) {
        let baseline = Analyzer::new(request.clone()).unwrap().finish();
        let mut changed = request;
        changed.slice_seeds = changed.addresses.clone();
        let other = Analyzer::new(changed).unwrap().finish();
        prop_assert_eq!(baseline.state.visited, other.state.visited);
        prop_assert_eq!(baseline.state.edges, other.state.edges);
        prop_assert_eq!(baseline.state.reaching, other.state.reaching);
        prop_assert_eq!(baseline.state.obligations, other.state.obligations);
    }

    #[test]
    fn replacing_definite_writes_with_possible_writes_preserves_origins(request in requests()) {
        let baseline = Analyzer::new(request.clone()).unwrap().finish();
        let mut changed = request;
        for instruction in changed.instructions.values_mut() { instruction.must_defs.clear(); }
        let other = Analyzer::new(changed).unwrap().finish();
        for (address, definitions) in &baseline.state.reaching {
            prop_assert!(definitions.is_subset(&other.state.reaching[address]));
        }
        prop_assert!(baseline.state.slice.is_subset(&other.state.slice));
    }
}
