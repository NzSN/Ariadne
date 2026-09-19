use ariadne::*;

pub fn locations(names: &[&str]) -> LocationSet {
    names.iter().map(|name| (*name).to_owned()).collect()
}

pub fn request(addresses: &[Address], locs: &[&str]) -> AnalysisRequest {
    let addresses: AddressSet = addresses.iter().copied().collect();
    AnalysisRequest {
        snapshot_id: "test-snapshot".into(),
        entry_points: [*addresses.first().unwrap()].into(),
        slice_seeds: [*addresses.last().unwrap()].into(),
        locations: locations(locs),
        file_backed: addresses.clone(),
        decodable: addresses.clone(),
        instructions: addresses
            .iter()
            .map(|&a| (a, Instruction::default()))
            .collect(),
        addresses,
        ..AnalysisRequest::default()
    }
}

pub fn instruction(
    kind: InstructionKind,
    fall: &[Address],
    targets: &[Address],
    complete: bool,
    uses: &[&str],
    must_defs: &[&str],
    may_defs: &[&str],
) -> Instruction {
    Instruction {
        kind,
        fall: fall.iter().copied().collect(),
        targets: targets.iter().copied().collect(),
        complete,
        uses: locations(uses),
        must_defs: locations(must_defs),
        may_defs: locations(may_defs),
    }
}

pub fn definition(loc: &str, site: Address, origin: DefinitionOrigin) -> Definition {
    Definition {
        loc: loc.into(),
        site,
        origin,
    }
}

/// Checks phase boundaries, monotonicity, identity domains, local discovery,
/// definition origins, and a finite progress bound after every single step.
pub fn run_checked(request: AnalysisRequest) -> AnalysisResult {
    let mut analyzer = Analyzer::new(request.clone()).unwrap();
    assert_eq!(analyzer.request(), &request);
    assert_eq!(analyzer.state().phase, Phase::Recover);
    assert_eq!(analyzer.state().pending, request.entry_points);
    assert!(analyzer.state().visited.is_empty());
    assert!(analyzer.state().decoded.is_empty());
    assert!(analyzer.state().edges.is_empty());
    assert!(analyzer.state().obligations.is_empty());
    assert!(analyzer.state().slice.is_empty());
    assert!(
        analyzer
            .state()
            .reaching
            .values()
            .all(DefinitionSet::is_empty)
    );
    let n = request.addresses.len();
    let limit = n + 2 * n * n * request.locations.len() + n + 3;
    let mut steps = 0;
    loop {
        let before = analyzer.state().clone();
        let progressed = analyzer.step();
        let after = analyzer.state();
        if !progressed {
            assert_eq!(after.phase, Phase::Done);
            assert_eq!(&before, after);
            break;
        }
        steps += 1;
        assert!(steps <= limit, "analysis exceeded its finite growth bound");
        assert_ne!(&before, after);
        assert!(after.pending.is_disjoint(&after.visited));
        assert!(after.visited.is_subset(&request.addresses));
        assert!(after.decoded.is_subset(&after.visited));
        assert!(after.slice.is_subset(&after.decoded));
        let discovered: AddressSet = request
            .entry_points
            .iter()
            .copied()
            .chain(
                after
                    .edges
                    .iter()
                    .filter(|e| e.kind.is_local())
                    .map(|e| e.dst),
            )
            .collect();
        assert_eq!(
            after
                .pending
                .union(&after.visited)
                .copied()
                .collect::<AddressSet>(),
            discovered
        );
        assert!(before.visited.is_subset(&after.visited));
        assert!(before.decoded.is_subset(&after.decoded));
        assert!(before.edges.is_subset(&after.edges));
        assert!(before.obligations.is_subset(&after.obligations));
        assert!(before.slice.is_subset(&after.slice));
        assert_eq!(
            after.provenance.keys().copied().collect::<AddressSet>(),
            request.addresses
        );
        assert_eq!(
            after.reaching.keys().copied().collect::<AddressSet>(),
            request.addresses
        );
        for address in &request.addresses {
            assert!(before.reaching[address].is_subset(&after.reaching[address]));
            if !after.decoded.contains(address) {
                assert_eq!(after.provenance[address], ByteSource::Unavailable);
                assert!(after.reaching[address].is_empty());
            }
            for definition in &after.reaching[address] {
                assert!(request.locations.contains(&definition.loc));
                match definition.origin {
                    DefinitionOrigin::Entry => {
                        assert!(request.entry_points.contains(&definition.site))
                    }
                    DefinitionOrigin::Instruction => {
                        assert!(after.decoded.contains(&definition.site));
                        assert!(
                            request.instructions[&definition.site]
                                .may_defs
                                .contains(&definition.loc)
                        );
                    }
                }
            }
        }
        for edge in &after.edges {
            assert!(after.decoded.contains(&edge.src));
            assert!(request.addresses.contains(&edge.dst));
        }
        if before.phase != Phase::Recover {
            assert_eq!(before.pending, after.pending);
            assert_eq!(before.visited, after.visited);
            assert_eq!(before.decoded, after.decoded);
            assert_eq!(before.provenance, after.provenance);
            assert_eq!(before.edges, after.edges);
            assert_eq!(before.obligations, after.obligations);
        }
        match (before.phase, after.phase) {
            (Phase::Recover, Phase::Recover) => {
                assert_eq!(after.visited.len(), before.visited.len() + 1);
                assert_eq!(before.reaching, after.reaching);
                assert_eq!(before.slice, after.slice);
            }
            (Phase::Recover, Phase::Dataflow) => {
                let mut expected = before;
                expected.phase = Phase::Dataflow;
                assert!(expected.pending.is_empty());
                assert_eq!(&expected, after);
            }
            (Phase::Dataflow, Phase::Dataflow) => {
                assert_eq!(before.slice, after.slice);
                assert_eq!(
                    request
                        .addresses
                        .iter()
                        .filter(|a| before.reaching[a] != after.reaching[a])
                        .count(),
                    1
                );
            }
            (Phase::Dataflow, Phase::Slice) => {
                assert_eq!(before.reaching, after.reaching);
                assert_eq!(
                    after.slice,
                    request
                        .slice_seeds
                        .intersection(&after.decoded)
                        .copied()
                        .collect()
                );
            }
            (Phase::Slice, Phase::Slice) => assert_eq!(before.reaching, after.reaching),
            (Phase::Slice, Phase::Done) => {
                let mut expected = before;
                expected.phase = Phase::Done;
                assert_eq!(&expected, after);
            }
            phases => panic!("invalid phase transition: {phases:?}"),
        }
    }
    let result = analyzer.finish();
    assert_eq!(
        result.missing_slice_seeds,
        request
            .slice_seeds
            .difference(&result.state.decoded)
            .copied()
            .collect()
    );
    result
}
