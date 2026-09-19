mod common;

use std::collections::BTreeMap;

use ariadne::*;
use common::*;

// Fixed seed, no external test dependency, and reproducible failures.
struct Generator(u64);

impl Generator {
    fn choose(&mut self, limit: u64) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0 % limit
    }
}

fn generated_request(random: &mut Generator) -> (AnalysisRequest, EdgeSet) {
    let nodes = [0, 3, 10, 20, 77, u64::MAX];
    let mut r = request(&nodes, &["x", "y"]);
    r.input_kind = if random.choose(2) == 0 {
        InputKind::Binary
    } else {
        InputKind::Dump
    };
    r.file_backed.clear();
    r.decodable.clear();
    r.slice_seeds.clear();
    // Record expected edges while generating each instruction. Recovery below
    // starts from this independent graph, not the implementation's output.
    let mut graph = EdgeSet::new();
    for &src in &nodes {
        let mut add = |dst, kind| {
            graph.insert(Edge { src, dst, kind });
        };
        let mut i = instruction(
            InstructionKind::Stop,
            &[],
            &[],
            random.choose(2) == 0,
            &[],
            &[],
            &[],
        );
        let first = nodes[random.choose(nodes.len() as u64) as usize];
        let second = nodes[random.choose(nodes.len() as u64) as usize];
        match random.choose(7) {
            0 => {
                i.kind = InstructionKind::Ordinary;
                i.fall.insert(first);
                add(first, EdgeKind::Next);
            }
            1 => {
                i.kind = InstructionKind::Conditional;
                i.fall.insert(first);
                i.targets.insert(second);
                add(first, EdgeKind::Fallthrough);
                add(second, EdgeKind::Taken);
            }
            2 => {
                i.kind = InstructionKind::Jump;
                i.targets.insert(first);
                add(first, EdgeKind::Jump);
            }
            3 => {
                i.kind = InstructionKind::Indirect;
                for &dst in &nodes {
                    if random.choose(3) == 0 {
                        i.targets.insert(dst);
                        add(dst, EdgeKind::Indirect);
                    }
                }
            }
            4 => {
                i.kind = InstructionKind::Call;
                i.fall.insert(first);
                add(first, EdgeKind::Summary);
                for &dst in &nodes {
                    if random.choose(3) == 0 {
                        i.targets.insert(dst);
                        add(dst, EdgeKind::Call);
                    }
                }
            }
            5 => i.kind = InstructionKind::Return,
            _ => {}
        }
        for loc in ["x", "y"] {
            if random.choose(2) == 0 {
                i.uses.insert(loc.into());
            }
            match random.choose(3) {
                1 => {
                    i.may_defs.insert(loc.into());
                }
                2 => {
                    i.may_defs.insert(loc.into());
                    i.must_defs.insert(loc.into());
                }
                _ => {}
            }
        }
        if random.choose(4) == 0 {
            r.entry_points.insert(src);
        }
        if random.choose(2) == 0 {
            r.slice_seeds.insert(src);
        }
        if random.choose(3) != 0 {
            r.decodable.insert(src);
        }
        if random.choose(2) == 0 {
            r.captured.insert(src);
        }
        if random.choose(4) != 0 {
            r.file_backed.insert(src);
            if random.choose(2) == 0 {
                r.trusted_fallback.insert(src);
            }
        }
        r.instructions.insert(src, i);
    }
    (r, graph)
}

fn available_source(r: &AnalysisRequest, a: Address) -> ByteSource {
    if r.input_kind == InputKind::Dump && r.captured.contains(&a) {
        ByteSource::Captured
    } else if (r.input_kind == InputKind::Binary && r.file_backed.contains(&a))
        || (r.input_kind == InputKind::Dump && r.trusted_fallback.contains(&a))
    {
        ByteSource::File
    } else {
        ByteSource::Unavailable
    }
}

fn expected_recovery(
    r: &AnalysisRequest,
    graph: &EdgeSet,
) -> (AddressSet, AddressSet, ObligationSet) {
    let mut frontier: Vec<_> = r.entry_points.iter().copied().collect();
    let mut visited = AddressSet::new();
    let mut decoded = AddressSet::new();
    let mut obligations = ObligationSet::new();
    while let Some(a) = frontier.pop() {
        if !visited.insert(a) {
            continue;
        }
        let source = available_source(r, a);
        let reason = if source == ByteSource::Unavailable {
            Some(ObligationReason::Unavailable)
        } else if !r.decodable.contains(&a) {
            Some(ObligationReason::DecodeFailed)
        } else {
            decoded.insert(a);
            frontier.extend(
                graph
                    .iter()
                    .filter(|e| e.src == a && e.kind != EdgeKind::Call)
                    .map(|e| e.dst),
            );
            match (r.instructions[&a].kind, r.instructions[&a].complete) {
                (InstructionKind::Indirect, false) => Some(ObligationReason::IndirectTargets),
                (InstructionKind::Call, false) => Some(ObligationReason::CallTargets),
                _ => None,
            }
        };
        if let Some(reason) = reason {
            obligations.insert(Obligation { site: a, reason });
        }
    }
    (visited, decoded, obligations)
}

// A separate oracle: walk kill-free paths for EACH definition. It never calls
// the analyzer's transfer equations or repeats its node-wise fixed-point loop.
fn reaching_by_paths(
    r: &AnalysisRequest,
    decoded: &AddressSet,
    graph: &EdgeSet,
) -> BTreeMap<Address, DefinitionSet> {
    let successors = |src| -> Vec<Address> {
        graph
            .iter()
            .filter(|e| e.src == src && e.kind != EdgeKind::Call && decoded.contains(&e.dst))
            .map(|e| e.dst)
            .collect()
    };
    let mut origins = Vec::new();
    for &a in decoded {
        if r.entry_points.contains(&a) {
            for loc in &r.locations {
                origins.push((definition(loc, a, DefinitionOrigin::Entry), vec![a]));
            }
        }
        for loc in &r.instructions[&a].may_defs {
            origins.push((
                definition(loc, a, DefinitionOrigin::Instruction),
                successors(a),
            ));
        }
    }
    let mut expected: BTreeMap<_, _> = r
        .addresses
        .iter()
        .map(|&a| (a, DefinitionSet::new()))
        .collect();
    for (origin, mut frontier) in origins {
        let mut visited = AddressSet::new();
        while let Some(a) = frontier.pop() {
            if !visited.insert(a) {
                continue;
            }
            expected.get_mut(&a).unwrap().insert(origin.clone());
            if !r.instructions[&a].must_defs.contains(&origin.loc) {
                frontier.extend(successors(a));
            }
        }
    }
    expected
}

fn slice_by_paths(
    r: &AnalysisRequest,
    decoded: &AddressSet,
    reaching: &BTreeMap<Address, DefinitionSet>,
) -> AddressSet {
    let mut frontier: Vec<_> = r.slice_seeds.intersection(decoded).copied().collect();
    let mut expected = AddressSet::new();
    while let Some(a) = frontier.pop() {
        if !expected.insert(a) {
            continue;
        }
        frontier.extend(
            reaching[&a]
                .iter()
                .filter(|d| {
                    d.origin == DefinitionOrigin::Instruction
                        && r.instructions[&a].uses.contains(&d.loc)
                })
                .map(|d| d.site),
        );
    }
    expected
}

#[test]
fn generated_requests_match_independent_graph_and_path_oracles() {
    let mut random = Generator(0x61ad_7e29_8930_b5c1);
    for case in 0..256 {
        let (r, full_graph) = generated_request(&mut random);
        let (visited, decoded, obligations) = expected_recovery(&r, &full_graph);
        let graph: EdgeSet = full_graph
            .into_iter()
            .filter(|e| decoded.contains(&e.src))
            .collect();
        let reaching = reaching_by_paths(&r, &decoded, &graph);
        let slice = slice_by_paths(&r, &decoded, &reaching);
        let result = run_checked(r.clone());
        assert_eq!(result.state.visited, visited, "case {case}");
        assert_eq!(result.state.decoded, decoded, "case {case}");
        assert_eq!(result.state.edges, graph, "case {case}");
        assert_eq!(result.state.obligations, obligations, "case {case}");
        assert_eq!(result.state.reaching, reaching, "case {case}");
        assert_eq!(result.state.slice, slice, "case {case}");
        for &address in &r.addresses {
            let expected = if decoded.contains(&address) {
                available_source(&r, address)
            } else {
                ByteSource::Unavailable
            };
            assert_eq!(
                result.state.provenance[&address], expected,
                "case {case}, VA {address}"
            );
        }
    }
}
