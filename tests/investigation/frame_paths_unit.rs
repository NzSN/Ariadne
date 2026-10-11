use super::*;
use crate::input::{FileSnapshot, OpenLimits};
use crate::investigation::{Contributor, FrameRecoveryLimits, Span};
use std::path::PathBuf;
pub(super) fn input(edges: &[(usize, usize)]) -> Input {
    let snapshot = FileSnapshot::open_minidump(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/input/fixtures/frame_paths/diamond.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let map = [0x400200, 0x400201, 0x400202, 0x400206];
    let node = |site, len, call, fall, targets| {
        let read = snapshot.read_prefix(site, len).unwrap();
        GraphNode {
            evidence: SiteEvidence {
                va: site,
                bytes_hex: super::super::frame_unwind::hex(&read.bytes),
                captured: true,
                opcode: None,
                quality: "fixture".into(),
                semantic_status: None,
                helper_sha256: None,
                runtime_sha256: None,
                ast_sha256: None,
                projection: None,
                accesses: vec![],
                spans: read
                    .spans
                    .iter()
                    .map(|s| Span {
                        va: s.address,
                        length: s.length,
                        contributors: s
                            .contributors
                            .iter()
                            .map(|c| Contributor {
                                stream: c.stream,
                                entry: c.entry,
                                file_offset: c.file_offset,
                            })
                            .collect(),
                    })
                    .collect(),
                gaps: vec![],
            },
            call,
            fall,
            targets,
        }
    };
    let identity = |frame| Identity {
        snapshot_id: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        query_id: sha(&[frame]),
        request_sha256: sha(&[frame, 1]),
        semantic_profile: "independent-normalized-graph-fixture".into(),
    };
    let graph = FrameGraph {
        frame: 0,
        identity: identity(0),
        entry: map[0],
        nodes: map
            .iter()
            .map(|site| node(*site, 1, false, vec![], vec![]))
            .collect(),
        edges: edges
            .iter()
            .map(|&(a, b)| FramePathEdge {
                src: FramePathNode {
                    frame: 0,
                    site: map[a],
                },
                dst: FramePathNode {
                    frame: 0,
                    site: map[b],
                },
                kind: FramePathEdgeKind::Next,
            })
            .collect(),
        gaps: vec![],
    };
    let parent = FrameGraph {
        frame: 1,
        identity: identity(1),
        entry: 0x400300,
        nodes: vec![
            node(0x400300, 4, false, vec![0x400310], vec![]),
            node(0x400310, 5, true, vec![0x400315], vec![0x400200]),
        ],
        edges: vec![],
        gaps: vec![],
    };
    Input {
        chain,
        graphs: vec![graph, parent],
    }
}
fn q(np: usize) -> FramePathQuestion {
    FramePathQuestion {
        from_frame: 1,
        to_frame: 0,
        np,
    }
}
fn limits() -> FramePathLimits {
    FramePathLimits {
        max_path_steps: 7,
        deadline_ms: 60000,
        ..FramePathLimits::default()
    }
}
#[test]
fn enumerated_paths_match_64_independent_cartesian_oracles() {
    let cases: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/frame_paths_oracle.json")).unwrap();
    let sites = [0x400200, 0x400201, 0x400202, 0x400206];
    for case in cases.as_array().unwrap() {
        let edges: Vec<(usize, usize)> = serde_json::from_value(case["edges"].clone()).unwrap();
        let r = list(input(&edges), q(100), limits(), Some(usize::MAX)).unwrap();
        assert!(r.available, "{}", r.stop_reason);
        let actual: BTreeSet<Vec<usize>> = r
            .paths
            .iter()
            .map(|p| {
                p.nodes[1..]
                    .iter()
                    .map(|n| sites.iter().position(|s| *s == n.site).unwrap())
                    .collect()
            })
            .collect();
        let expected: BTreeSet<Vec<usize>> = serde_json::from_value(case["paths"].clone()).unwrap();
        assert_eq!(actual, expected, "edges={edges:?}");
        r.validate().unwrap();
    }
}
#[test]
fn strict_np_and_equal_frame_cases_preserve_empty_list_meaning() {
    let diamond = [(0, 1), (0, 2), (1, 3), (2, 3)];
    let r = list(input(&diamond), q(1), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 0);
    assert!(r.truncated);
    assert!(!r.enumeration_exhausted);
    r.validate().unwrap();
    let r = list(input(&diamond), q(2), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 1);
    assert!(r.truncated);
    assert_eq!(r.stop_reason, "path-count-budget");
    r.validate().unwrap();
    let r = list(input(&diamond), q(3), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 2);
    assert!(r.enumeration_exhausted);
    r.validate().unwrap();
    let r = list(
        input(&diamond),
        FramePathQuestion {
            from_frame: 0,
            to_frame: 0,
            np: 2,
        },
        limits(),
        Some(usize::MAX),
    )
    .unwrap();
    assert_eq!(r.paths[0].nodes.len(), 1);
    assert!(r.paths[0].edges.is_empty());
    r.validate().unwrap();
}
#[test]
fn every_search_work_and_retention_boundary_stays_explicit() {
    let edges = [(0, 1), (0, 2), (1, 3), (2, 3)];
    let mut variants = Vec::new();
    let mut l = limits();
    l.max_graph_nodes = 0;
    variants.push(l);
    let mut l = limits();
    l.max_graph_edges = 0;
    variants.push(l);
    let mut l = limits();
    l.max_search_states = 0;
    variants.push(l);
    let mut l = limits();
    l.max_scanned_edges = 0;
    variants.push(l);
    let mut l = limits();
    l.max_path_steps = 1;
    variants.push(l);
    let mut l = limits();
    l.max_node_visits = 0;
    variants.push(l);
    let mut l = limits();
    l.max_frontier_bytes = 0;
    variants.push(l);
    for l in variants {
        let r = list(input(&edges), q(10), l, Some(usize::MAX)).unwrap();
        assert!(r.truncated, "{}", r.stop_reason);
        assert!(!r.enumeration_exhausted);
        r.validate().unwrap();
    }
    let mut l = limits();
    l.deadline_ms = 0;
    let r = list(input(&edges), q(10), l, None).unwrap();
    assert_eq!(r.stop_reason, "deadline-budget");
    r.validate().unwrap();
    let mut l = limits();
    l.max_output_bytes = 0;
    assert!(list(input(&edges), q(10), l, Some(usize::MAX)).is_err());
}
#[test]
fn closed_no_path_and_missing_frame_evidence_are_distinct() {
    let r = list(input(&[]), q(10), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 0);
    assert!(r.enumeration_exhausted);
    assert_eq!(r.coverage, "complete_within_declared_scope");
    r.validate().unwrap();
    let mut i = input(&[]);
    i.graphs.pop();
    let r = list(i, q(10), limits(), Some(usize::MAX)).unwrap();
    assert!(!r.available);
    assert_eq!(r.coverage, "unavailable");
    assert!(!r.enumeration_exhausted);
    r.validate().unwrap();
    let mut i = input(&[]);
    i.graphs[0].gaps.push("unknown-control-target".into());
    let r = list(i, q(10), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 0);
    assert_eq!(r.coverage, "partial");
}
#[test]
fn invalid_questions_and_evidence_never_pass_under_zero_work_budgets() {
    let mut l = limits();
    l.max_search_states = 0;
    assert!(list(input(&[]), q(0), l.clone(), Some(usize::MAX)).is_err());
    assert!(
        list(
            input(&[]),
            FramePathQuestion {
                from_frame: 0,
                to_frame: 1,
                np: 10
            },
            l.clone(),
            Some(usize::MAX)
        )
        .is_err()
    );
    assert!(
        list(
            input(&[]),
            FramePathQuestion {
                from_frame: 3,
                to_frame: 0,
                np: 10
            },
            l.clone(),
            Some(usize::MAX)
        )
        .is_err()
    );
    let mut i = input(&[]);
    i.graphs[0].identity.snapshot_id = "wrong".into();
    assert!(list(i, q(10), l.clone(), Some(usize::MAX)).is_err());
    let mut i = input(&[]);
    i.graphs[0].edges.push(FramePathEdge {
        src: FramePathNode { frame: 0, site: 1 },
        dst: FramePathNode { frame: 0, site: 2 },
        kind: FramePathEdgeKind::Next,
    });
    assert!(list(i, q(10), l, Some(usize::MAX)).is_err());
}
#[test]
fn active_call_witnesses_and_strict_reports_reject_forgery() {
    let edges = [(0, 1), (1, 3)];
    let bound = BoundFramePaths {
        input: input(&edges),
    };
    let r = list_frame_paths(&bound, q(10), limits()).unwrap();
    r.validate_for(&bound).unwrap();
    for format in [
        crate::reports::Format::Json,
        crate::reports::Format::Text,
        crate::reports::Format::Dot,
    ] {
        assert!(
            !crate::reports::render_frame_paths(&r, format)
                .unwrap()
                .is_empty()
        );
    }
    let value = crate::reports::encode_frame_paths(&r).unwrap();
    let bytes = serde_json::to_vec(&value).unwrap();
    assert_eq!(crate::reports::decode_frame_paths(&bytes).unwrap(), r);
    let mut v = value.clone();
    v["paths"][0]["edges"][0]["dst"]["site"] = serde_json::json!("0x0000000000000001");
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&v).unwrap()).is_err());
    let mut v = value.clone();
    v["returned_count"] = serde_json::json!(999);
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&v).unwrap()).is_err());
    let mut v = value;
    v["unexpected"] = serde_json::json!(true);
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&v).unwrap()).is_err());
    let mut i = input(&edges);
    i.graphs[1].nodes[1].targets[0] = 0x400999;
    let r = list(i, q(10), limits(), Some(usize::MAX)).unwrap();
    assert!(!r.available);
    let mut other = BoundFramePaths {
        input: input(&edges),
    };
    other.input.graphs[0].identity.query_id = sha(b"different query");
    assert!(
        list_frame_paths(&bound, q(10), limits())
            .unwrap()
            .validate_for(&other)
            .is_err()
    );
}
#[test]
fn typed_parallel_edges_are_distinct_alternatives() {
    let mut i = input(&[(0, 3)]);
    let mut other = i.graphs[0].edges[0].clone();
    other.kind = FramePathEdgeKind::Taken;
    i.graphs[0].edges.push(other);
    let r = list(i, q(10), limits(), Some(usize::MAX)).unwrap();
    assert_eq!(r.returned_count, 2);
    assert_ne!(r.paths[0].path_id, r.paths[1].path_id);
    r.validate().unwrap();
}
#[test]
fn opaque_summaries_are_labeled_and_loops_keep_incomplete_coverage() {
    let mut i = input(&[(0, 1), (1, 1), (1, 3)]);
    i.graphs[0].edges[0].kind = FramePathEdgeKind::Summary;
    let r = list(i, q(10), limits(), Some(usize::MAX)).unwrap();
    assert!(r.paths.iter().all(|p| p.contains_opaque_summary));
    assert!(r.truncated);
    assert!(r.gaps.iter().any(|g| g == "loop-visit-budget"));
    assert_eq!(r.coverage, "partial");
    r.validate().unwrap();
}
