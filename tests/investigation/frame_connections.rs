use super::*;
use serde::Deserialize;
#[derive(Deserialize)]
struct Case {
    n: usize,
    edges: Vec<(usize, usize, String)>,
    forward: Vec<usize>,
    backward: Vec<usize>,
    corridor: Vec<usize>,
    groups: Vec<Vec<usize>>,
    cyclic: Vec<bool>,
    shortest: Option<usize>,
}
fn limits() -> FrameConnectionLimits {
    FrameConnectionLimits {
        deadline_ms: 60_000,
        ..Default::default()
    }
}
fn node(i: usize) -> FramePathNode {
    FramePathNode {
        frame: 0,
        site: i as u64,
    }
}
fn graph_case(case: &Case) -> Graph {
    let mut edges: Vec<_> = case
        .edges
        .iter()
        .map(|(a, b, k)| FramePathEdge {
            src: node(*a),
            dst: node(*b),
            kind: match k.as_str() {
                "taken" => FramePathEdgeKind::Taken,
                "fallthrough" => FramePathEdgeKind::Fallthrough,
                "jump" => FramePathEdgeKind::Jump,
                _ => FramePathEdgeKind::Next,
            },
        })
        .collect();
    edges.sort();
    Graph {
        nodes: (0..case.n).map(node).collect(),
        edges,
        ..Default::default()
    }
}
#[test]
fn independent_closure_partition_condensation_and_shortest_oracle() {
    let cases: Vec<Case> =
        serde_json::from_str(include_str!("fixtures/frame_connections_oracle.json")).unwrap();
    for (number, c) in cases.iter().enumerate() {
        let l = limits();
        let g = graph_case(c);
        let i = Index::new(&g);
        let (f, fs) = reachable(&g, &i, 0, false, &mut Meter::new(l.reach_work, &l, None));
        let (b, bs) = reachable(
            &g,
            &i,
            c.n - 1,
            true,
            &mut Meter::new(l.reach_work, &l, None),
        );
        assert_eq!(fs, None);
        assert_eq!(bs, None);
        assert_eq!(
            f.iter().copied().collect::<Vec<_>>(),
            c.forward,
            "case {number}"
        );
        assert_eq!(b.iter().copied().collect::<Vec<_>>(), c.backward);
        assert_eq!(f.intersection(&b).copied().collect::<Vec<_>>(), c.corridor);
        let (cs, es) =
            components(&g, &i, "scope", &l, &mut Meter::new(l.scc_work, &l, None)).unwrap();
        assert_eq!(
            cs.iter()
                .map(|c| c
                    .members
                    .iter()
                    .map(|n| n.site as usize)
                    .collect::<Vec<_>>())
                .collect::<Vec<_>>(),
            c.groups,
            "case {number}"
        );
        assert_eq!(cs.iter().map(|c| c.cyclic).collect::<Vec<_>>(), c.cyclic);
        let mut original: Vec<_> = es.iter().flat_map(|e| e.original_edges.clone()).collect();
        original.sort();
        let owners: BTreeMap<_, _> = cs
            .iter()
            .enumerate()
            .flat_map(|(j, c)| c.members.iter().cloned().map(move |n| (n, j)))
            .collect();
        assert_eq!(
            original,
            g.edges
                .iter()
                .filter(|e| owners[&e.src] != owners[&e.dst])
                .cloned()
                .collect::<Vec<_>>()
        );
        for np in [1, 2, 4] {
            let (paths, _) = examples(
                &g,
                &i,
                0,
                c.n - 1,
                np,
                "scope",
                &l,
                &mut Meter::new(l.example_work, &l, None),
            );
            assert!(paths.len() < np);
            if np == 1 {
                assert!(paths.is_empty());
                continue;
            }
            assert!(
                paths
                    .first()
                    .is_none_or(|p| p.shortest_in_represented_graph)
            );
            assert_eq!(
                paths.first().map(|p| p.edges.len()),
                c.shortest,
                "case {number}"
            );
            for p in &paths {
                assert_eq!(p.nodes.first(), Some(&node(0)));
                assert_eq!(p.nodes.last(), Some(&node(c.n - 1)));
                assert_eq!(p.nodes.len(), p.nodes.iter().collect::<BTreeSet<_>>().len());
                assert!(p.edges.iter().all(|e| g.edges.contains(e)));
                assert!(
                    p.edges
                        .iter()
                        .zip(p.nodes.windows(2))
                        .all(|(e, n)| e.src == n[0] && e.dst == n[1])
                );
            }
        }
    }
}
#[test]
fn independent_layer_stops_and_deadline_prefix_replay() {
    let c = Case {
        n: 3,
        edges: vec![(0, 1, "next".into()), (1, 2, "next".into())],
        forward: vec![],
        backward: vec![],
        corridor: vec![],
        groups: vec![],
        cyclic: vec![],
        shortest: None,
    };
    let g = graph_case(&c);
    let i = Index::new(&g);
    let l = limits();
    assert_eq!(
        reachable(&g, &i, 0, false, &mut Meter::new(0, &l, None)).1,
        Some(ConnectionStop::WorkLimit)
    );
    assert_eq!(
        components(&g, &i, "s", &l, &mut Meter::new(0, &l, None)).err(),
        Some(ConnectionStop::WorkLimit)
    );
    for work in 0..5 {
        let receipt = ConnectionReceipt {
            work,
            elapsed_ms: l.deadline_ms,
            stop: Some(ConnectionStop::Deadline),
        };
        let mut meter = Meter::new(l.reach_work, &l, Some(&receipt));
        let (_, stop) = reachable(&g, &i, 0, false, &mut meter);
        assert_eq!(stop, Some(ConnectionStop::Deadline));
        assert_eq!(meter.receipt(stop), receipt);
    }
    for cap in 0..5 {
        let stopped = FrameConnectionLimits {
            max_path_nodes: cap,
            ..l.clone()
        };
        let (paths, stop) = examples(
            &g,
            &i,
            0,
            2,
            2,
            "s",
            &stopped,
            &mut Meter::new(l.example_work, &l, None),
        );
        if cap < 3 {
            assert!(paths.is_empty());
            assert_eq!(stop, Some(ConnectionStop::PathLengthLimit));
        } else {
            assert_eq!(paths.len(), 1);
        }
    }
    let (paths, stop) = examples(&g, &i, 0, 2, 2, "s", &l, &mut Meter::new(0, &l, None));
    assert!(paths.is_empty());
    assert_eq!(stop, Some(ConnectionStop::WorkLimit));
}
#[test]
fn parallel_edge_identity_and_recursive_activation_identity() {
    let c = Case {
        n: 2,
        edges: vec![(0, 1, "taken".into()), (0, 1, "fallthrough".into())],
        forward: vec![],
        backward: vec![],
        corridor: vec![],
        groups: vec![],
        cyclic: vec![],
        shortest: None,
    };
    let mut g = graph_case(&c);
    let l = limits();
    let i = Index::new(&g);
    let (paths, _) = examples(
        &g,
        &i,
        0,
        1,
        4,
        "s",
        &l,
        &mut Meter::new(l.example_work, &l, None),
    );
    assert_eq!(paths.len(), 2);
    assert_eq!(paths[0].nodes, paths[1].nodes);
    assert_ne!(paths[0].id, paths[1].id);
    g.nodes = vec![
        FramePathNode {
            frame: 0,
            site: 100,
        },
        FramePathNode {
            frame: 1,
            site: 100,
        },
    ];
    g.edges.clear();
    let (cs, _) = components(
        &g,
        &Index::new(&g),
        "s",
        &l,
        &mut Meter::new(l.scc_work, &l, None),
    )
    .unwrap();
    assert_eq!(cs.len(), 2);
}
#[test]
fn iterative_algorithms_accept_graph_larger_than_old_path_cap() {
    let n = 10_000;
    let g = Graph {
        nodes: (0..n).map(node).collect(),
        edges: (0..n - 1)
            .map(|j| FramePathEdge {
                src: node(j),
                dst: node(j + 1),
                kind: FramePathEdgeKind::Next,
            })
            .collect(),
        ..Default::default()
    };
    let i = Index::new(&g);
    let l = FrameConnectionLimits {
        max_path_nodes: n,
        ..limits()
    };
    let (cs, _) = components(&g, &i, "s", &l, &mut Meter::new(l.scc_work, &l, None)).unwrap();
    assert_eq!(cs.len(), n);
    let p = bfs(
        &g,
        &i,
        0,
        n - 1,
        None,
        &l,
        &mut Meter::new(l.example_work, &l, None),
    )
    .unwrap()
    .unwrap();
    assert_eq!(p.len(), n - 1);
}
#[cfg(feature = "input")]
fn source() -> BoundFrameStructure {
    let (chain, recovery) = crate::investigation::frame_structure::tests::fixture();
    crate::investigation::bind_frame_structure(
        chain,
        super::super::FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, recovery)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap()
}
#[test]
#[cfg(feature = "input")]
fn public_bound_codec_rejects_rehashed_claims_and_host_exhaustion() {
    use crate::reports::{frame_connections as report, frame_structure as structural};
    let input = source();
    let source_json = structural::render_json(&input).unwrap();
    let l = limits();
    let bound = summarize_frame_connections(input, 2, l.clone()).unwrap();
    assert_eq!(
        structural::render_json(bound.source()).unwrap(),
        source_json
    );
    assert_eq!(
        bound.analysis().connection,
        RepresentedConnection::UnavailableAnchors
    );
    assert_eq!(
        bound.analysis().scc_status,
        ConnectionLayerStatus::CompleteForRepresentedGraph
    );
    let bytes = report::render_json(&bound).unwrap();
    let decoded = report::decode(bytes.as_bytes(), &l).unwrap();
    assert_eq!(report::render_json(&decoded).unwrap(), bytes);
    assert_eq!(
        report::render_text(&decoded).unwrap(),
        report::render_text(&bound).unwrap()
    );
    assert_eq!(
        report::render_dot(&decoded).unwrap(),
        report::render_dot(&bound).unwrap()
    );
    let original: serde_json::Value = serde_json::from_str(&bytes).unwrap();
    for changed in [
        "source_fingerprint",
        "scope_id",
        "connection",
        "conditional_on",
    ] {
        let mut value = original.clone();
        value["assessment"][changed] = match changed {
            "connection" => serde_json::json!("found"),
            "conditional_on" => serde_json::json!(["fake"]),
            _ => serde_json::json!("forged"),
        };
        let assessment: FrameConnectionAnalysis =
            serde_json::from_value(value["assessment"].clone()).unwrap();
        value["publication_binding"] = digest(
            &(
                FRAME_CONNECTION_SCHEMA,
                value["source_json"].as_str().unwrap(),
                &assessment,
            ),
            l.max_output_bytes,
        )
        .unwrap()
        .into();
        assert!(
            report::decode(&serde_json::to_vec(&value).unwrap(), &l).is_err(),
            "{changed}"
        );
    }
    for hostile in [
        FrameConnectionLimits {
            graph_work: 0,
            ..l.clone()
        },
        FrameConnectionLimits {
            max_input_bytes: 0,
            ..l.clone()
        },
        FrameConnectionLimits {
            max_source_bytes: 0,
            ..l.clone()
        },
    ] {
        assert!(report::decode(bytes.as_bytes(), &hostile).is_err());
    }
    assert!(report::decode_expected(bytes.as_bytes(), &l, "wrong").is_err());
    assert!(summarize_frame_connections(source(), 0, l.clone()).is_err());
    let stopped = summarize_frame_connections(
        source(),
        2,
        FrameConnectionLimits {
            graph_work: 0,
            ..l.clone()
        },
    )
    .unwrap();
    assert_eq!(
        stopped.analysis().connection,
        RepresentedConnection::UnknownWorkStopped
    );
    let bytes = report::render_json(&stopped).unwrap();
    assert!(report::decode(bytes.as_bytes(), &l).is_ok());
}
#[test]
#[cfg(feature = "input")]
fn projection_keeps_off_corridor_unknowns_context_and_admitted_links_only() {
    let l = limits();
    let source = crate::investigation::frame_structure::tests::connection_projection_fixture(true);
    let anchors = BTreeMap::from([(1, FramePathNode { frame: 1, site: 10 })]);
    let mut g = graph(
        &source,
        &l,
        &mut Meter::new(l.graph_work, &l, None),
        &anchors,
    )
    .unwrap();
    assert_eq!(g.nodes.len(), 6);
    assert_eq!(g.edges.len(), 4);
    assert_eq!(
        g.edges
            .iter()
            .map(|e| (e.src, e.dst, e.kind))
            .collect::<BTreeSet<_>>(),
        BTreeSet::from([
            (node(10), node(20), FramePathEdgeKind::Taken),
            (node(10), node(30), FramePathEdgeKind::Fallthrough),
            (node(20), node(40), FramePathEdgeKind::Next),
            (
                FramePathNode { frame: 1, site: 10 },
                node(10),
                FramePathEdgeKind::Call
            ),
        ])
    );
    assert_eq!(g.context.len(), 3);
    assert_eq!(
        g.edges
            .iter()
            .filter(|e| e.kind == FramePathEdgeKind::Call)
            .count(),
        1
    );
    let i = Index::new(&g);
    let start = i.ids[&FramePathNode { frame: 1, site: 10 }];
    let end = i.ids[&node(40)];
    let (f, _) = reachable(
        &g,
        &i,
        start,
        false,
        &mut Meter::new(l.reach_work, &l, None),
    );
    let (b, _) = reachable(&g, &i, end, true, &mut Meter::new(l.reach_work, &l, None));
    let forward: Vec<_> = f.iter().map(|j| g.nodes[*j]).collect();
    let corridor: Vec<_> = f.intersection(&b).map(|j| g.nodes[*j]).collect();
    assert_eq!(corridor.len(), 4);
    assert!(!corridor.contains(&node(30)));
    classify_frontiers(&mut g, &i, &corridor, &forward, true);
    assert_eq!(g.frontiers.len(), 1);
    assert_eq!(g.frontiers[0].gap.site, 30);
    assert_eq!(g.frontiers[0].relation, FrontierRelation::ForwardReachable);
    let denied = crate::investigation::frame_structure::tests::connection_projection_fixture(false);
    let denied = graph(
        &denied,
        &l,
        &mut Meter::new(l.graph_work, &l, None),
        &anchors,
    )
    .unwrap();
    assert!(
        !denied
            .edges
            .iter()
            .any(|e| e.kind == FramePathEdgeKind::Call)
    );
    for policy in [
        FrameConnectionLimits {
            max_graph_nodes: 0,
            ..l.clone()
        },
        FrameConnectionLimits {
            max_graph_edges: 0,
            ..l.clone()
        },
        FrameConnectionLimits {
            max_work_bytes: 0,
            ..l.clone()
        },
    ] {
        assert!(
            graph(
                &source,
                &policy,
                &mut Meter::new(l.graph_work, &policy, None),
                &anchors
            )
            .is_err()
        );
    }
}

#[test]
#[ignore = "requires an explicitly selected saved conditional structural source"]
fn conditional_saved_source_preserves_hypotheses() {
    let path =
        std::env::var_os("ARIADNE_CONNECTION_CONDITIONAL_SOURCE").expect("conditional source path");
    let bytes = std::fs::read(path).unwrap();
    let source =
        crate::reports::frame_structure::decode(&bytes, &FrameStructureLimits::default()).unwrap();
    assert!(source.is_conditional());
    let hypotheses = source.hypothesis_ids();
    assert!(!hypotheses.is_empty());
    let bound = summarize_frame_connections(source, 2, limits()).unwrap();
    assert_eq!(bound.analysis().conditional_on, hypotheses);
    assert_eq!(
        crate::reports::frame_structure::render_json(bound.source())
            .unwrap()
            .as_bytes(),
        bytes
    );
}
