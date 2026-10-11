//! Generated normalized-graph contracts, independent of native instruction semantics.
use super::*;
use proptest::prelude::*;
use proptest::test_runner::{Config, FileFailurePersistence, RngSeed};
use std::sync::OnceLock;

#[derive(Clone, Debug)]
struct GraphCase {
    nodes: usize,
    edges: Vec<(usize, usize, u8)>,
    steps: usize,
    visits: usize,
}
fn graph_cases() -> impl Strategy<Value = GraphCase> {
    (2usize..=5)
        .prop_flat_map(|nodes| {
            (
                Just(nodes),
                proptest::collection::btree_set((0..nodes, 0..nodes, 0u8..6), 0..=8),
                2usize..=4,
                1usize..=2,
            )
        })
        .prop_map(|(nodes, edges, steps, visits)| GraphCase {
            nodes,
            edges: edges.into_iter().collect(),
            steps,
            visits,
        })
}
fn config() -> Config {
    Config {
        cases: 128,
        max_shrink_iters: 4096,
        rng_seed: RngSeed::Fixed(0xf0a1_17e5_8b29_403c),
        failure_persistence: Some(Box::new(FileFailurePersistence::Direct(
            "tests/investigation/frame_paths.proptest-regressions",
        ))),
        ..Config::default()
    }
}
fn kind(index: u8) -> FramePathEdgeKind {
    [
        FramePathEdgeKind::Next,
        FramePathEdgeKind::Taken,
        FramePathEdgeKind::Fallthrough,
        FramePathEdgeKind::Jump,
        FramePathEdgeKind::Indirect,
        FramePathEdgeKind::Summary,
    ][index as usize]
}
fn site(index: usize, nodes: usize) -> u64 {
    if index == nodes - 1 {
        0x400206
    } else {
        0x400200 + index as u64
    }
}
fn generated_input(case: &GraphCase) -> Input {
    static TEMPLATE: OnceLock<Input> = OnceLock::new();
    let mut input = TEMPLATE.get_or_init(|| super::tests::input(&[])).clone();
    let template = input.graphs[0].nodes[0].clone();
    input.graphs[0].nodes = (0..case.nodes)
        .map(|index| {
            let mut node = template.clone();
            let va = site(index, case.nodes);
            let delta = va - node.evidence.va;
            node.evidence.va = va;
            node.evidence.bytes_hex = format!(
                "{:02x}",
                [0x48u8, 0x83, 0xec, 0x20, 0x90, 0x90, 0x48][delta as usize]
            );
            node.evidence.spans[0].va = va;
            for c in &mut node.evidence.spans[0].contributors {
                c.file_offset += delta;
            }
            // Normalized graph fixtures assert control facts, not hardware conformance.
            node.evidence.quality = "generated-normalized-graph-fixture".into();
            node
        })
        .collect();
    input.graphs[0].edges = case
        .edges
        .iter()
        .map(|&(a, b, k)| FramePathEdge {
            src: FramePathNode {
                frame: 0,
                site: site(a, case.nodes),
            },
            dst: FramePathNode {
                frame: 0,
                site: site(b, case.nodes),
            },
            kind: kind(k),
        })
        .collect();
    input
}
fn question(np: usize) -> FramePathQuestion {
    FramePathQuestion {
        from_frame: 1,
        to_frame: 0,
        np,
    }
}
fn generous(case: &GraphCase) -> FramePathLimits {
    FramePathLimits {
        max_path_steps: case.steps + 1,
        max_node_visits: case.visits,
        max_output_bytes: 16 * 1024 * 1024,
        ..FramePathLimits::default()
    }
}
type Signature = Vec<(usize, usize, u8)>;
fn signatures(r: &FramePathListing, case: &GraphCase) -> Vec<Signature> {
    r.paths
        .iter()
        .map(|path| {
            path.edges[1..]
                .iter()
                .map(|e| {
                    let index = |s| {
                        (0..case.nodes)
                            .find(|i| site(*i, case.nodes) == s)
                            .expect("generated node")
                    };
                    let k = (0..6).find(|k| kind(*k) == e.kind).expect("local kind");
                    (index(e.src.site), index(e.dst.site), k)
                })
                .collect()
        })
        .collect()
}
/// Cartesian words over edge IDs, filtered after construction. No CFG search.
fn cartesian_oracle(case: &GraphCase) -> BTreeSet<Signature> {
    let mut paths = BTreeSet::new();
    let radix = case.edges.len();
    for length in 1..case.steps {
        for word in 0..radix.pow(length as u32) {
            let mut digits = word;
            let mut selected = Vec::new();
            for _ in 0..length {
                selected.push(case.edges[digits % radix]);
                digits /= radix;
            }
            let mut cursor = 0;
            let mut visits = vec![0usize; case.nodes];
            visits[0] = 1;
            let mut valid = true;
            for &(from, to, _) in &selected {
                if from != cursor || cursor == case.nodes - 1 {
                    valid = false;
                    break;
                }
                cursor = to;
                visits[to] += 1;
            }
            if valid && cursor == case.nodes - 1 && visits.iter().all(|v| *v <= case.visits) {
                paths.insert(selected);
            }
        }
    }
    paths
}
fn run(case: &GraphCase, np: usize, limits: FramePathLimits) -> FramePathListing {
    list(
        generated_input(case),
        question(np),
        limits,
        Some(usize::MAX),
    )
    .unwrap()
}

fn activation_input(recursive: bool, kinds: usize) -> Input {
    use crate::input::{FileSnapshot, OpenLimits};
    use crate::investigation::FrameRecoveryLimits;
    let bytes: &[u8] = if recursive {
        include_bytes!("../input/fixtures/frame_paths/recursive.dmp")
    } else {
        include_bytes!("../input/fixtures/frame_paths/diamond.dmp")
    };
    let snapshot =
        FileSnapshot::from_minidump_bytes(bytes.to_vec(), OpenLimits::default()).unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let mut input = super::tests::input(&[]);
    let mut graphs = Vec::new();
    for frame in 0..3 {
        let entry = chain.frames[frame].function_begin.unwrap();
        let anchor = if frame == 0 {
            chain.frames[0].pc
        } else {
            chain.frames[frame].pc - 5
        };
        let mut base = input.graphs[0].clone();
        base.frame = frame;
        base.entry = entry;
        base.nodes.clear();
        base.edges.clear();
        base.identity.snapshot_id = chain.snapshot_id.clone();
        base.identity.artifact_sha256 = chain.artifact_sha256.clone();
        for site in [entry, anchor] {
            let mut node = input.graphs[0].nodes[0].clone();
            let call = frame > 0 && site == anchor;
            let len = if call { 5 } else { 1 };
            let read = snapshot.read_prefix(site, len).unwrap();
            node.evidence.va = site;
            node.evidence.bytes_hex = super::super::frame_unwind::hex(&read.bytes);
            node.evidence.spans = read
                .spans
                .iter()
                .map(|s| crate::investigation::Span {
                    va: s.address,
                    length: s.length,
                    contributors: s
                        .contributors
                        .iter()
                        .map(|c| crate::investigation::Contributor {
                            stream: c.stream,
                            entry: c.entry,
                            file_offset: c.file_offset,
                        })
                        .collect(),
                })
                .collect();
            node.call = call;
            node.fall = if call {
                vec![chain.frames[frame].pc]
            } else {
                vec![]
            };
            node.targets = if call {
                vec![chain.frames[frame - 1].function_begin.unwrap()]
            } else {
                vec![]
            };
            base.nodes.push(node);
        }
        for k in 0..kinds {
            base.edges.push(FramePathEdge {
                src: FramePathNode { frame, site: entry },
                dst: FramePathNode {
                    frame,
                    site: anchor,
                },
                kind: kind(k as u8),
            });
        }
        graphs.push(base);
    }
    input.chain = chain;
    input.graphs = graphs;
    input
}

proptest! {
    #![proptest_config(config())]

    #[test]
    fn prop_paths_equal_independent_edge_word_oracle(case in graph_cases()){
        let result=run(&case,4097,generous(&case));
        let actual:BTreeSet<_>=signatures(&result,&case).into_iter().collect();
        prop_assert_eq!(actual,cartesian_oracle(&case));
        prop_assert_eq!(result.returned_count,result.paths.len());
        prop_assert!(result.returned_count<4097);
        result.validate().unwrap();
        for path in &result.paths{
            prop_assert_eq!(path.nodes.first().unwrap().frame,1);
            prop_assert_eq!(path.nodes.last().unwrap(),&FramePathNode{frame:0,site:0x400206});
            prop_assert_eq!(path.edges[0].kind,FramePathEdgeKind::Call);
            prop_assert_eq!(path.edges.len()+1,path.nodes.len());
            prop_assert_eq!(path.contains_opaque_summary,path.edges.iter().any(|e|e.kind==FramePathEdgeKind::Summary));
        }
    }

    #[test]
    fn prop_np_is_strict_and_larger_capacity_preserves_the_prefix(case in graph_cases(),np in 1usize..=12){
        let small=run(&case,np,generous(&case));let large=run(&case,np+1,generous(&case));
        prop_assert!(small.returned_count<np);
        let a=signatures(&small,&case);let b=signatures(&large,&case);
        prop_assert!(b.starts_with(&a));
        small.validate().unwrap();large.validate().unwrap();
    }

    #[test]
    fn prop_resource_limits_preserve_sound_paths_and_honest_completion(case in graph_cases(),states in 0usize..=32,scans in 0usize..=48,depth in 0usize..=6,visits in 0usize..=2,frontier in 0usize..=1536,np in 1usize..=10){
        let limits=FramePathLimits{max_search_states:states,max_scanned_edges:scans,max_path_steps:depth,max_node_visits:visits,max_frontier_bytes:frontier,..generous(&case)};
        let result=run(&case,np,limits.clone());
        prop_assert!(result.returned_count<np);
        prop_assert!(result.counters.expanded_states<=states);
        prop_assert!(result.counters.scanned_edges<=scans);
        prop_assert!(result.counters.peak_frontier_bytes<=frontier);
        prop_assert!(!result.truncated || !result.enumeration_exhausted);
        let bounded=GraphCase{steps:depth.saturating_sub(1),visits,..case.clone()};
        let allowed=cartesian_oracle(&bounded);
        for path in signatures(&result,&case){prop_assert!(allowed.contains(&path));}
        result.validate().unwrap();
    }

    #[test]
    fn prop_more_search_work_preserves_previously_returned_paths(case in graph_cases(),budget in 0usize..=32){
        let small=run(&case,4097,FramePathLimits{max_search_states:budget,..generous(&case)});
        let large=run(&case,4097,FramePathLimits{max_search_states:budget+32,..generous(&case)});
        prop_assert!(signatures(&large,&case).starts_with(&signatures(&small,&case)));
    }

    #[test]
    fn prop_input_table_order_does_not_change_path_choices(case in graph_cases(),np in 1usize..=12){
        let a=run(&case,np,generous(&case));let mut input=generated_input(&case);
        input.graphs.reverse();for g in &mut input.graphs{g.nodes.reverse();g.edges.reverse();}
        let b=list(input,question(np),generous(&case),Some(usize::MAX)).unwrap();
        prop_assert_eq!(signatures(&a,&case),signatures(&b,&case));
        prop_assert_eq!(&a.counters,&b.counters);
        b.validate().unwrap();
    }

    #[test]
    fn prop_path_ids_and_live_binding_are_query_scoped(case in graph_cases(),nonce in any::<u64>()){
        let mut case=case;case.edges.push((0,case.nodes-1,0));case.edges.sort();case.edges.dedup();
        let original=BoundFramePaths{input:generated_input(&case)};
        let old=list(original.input.clone(),question(4097),generous(&case),Some(usize::MAX)).unwrap();
        let mut other=BoundFramePaths{input:generated_input(&case)};
        other.input.graphs[0].identity.query_id=sha(&serde_json::to_vec(&("changed-query",nonce)).unwrap());
        let new=list(other.input.clone(),question(4097),generous(&case),Some(usize::MAX)).unwrap();
        prop_assert_eq!(signatures(&old,&case),signatures(&new,&case));
        prop_assert_ne!(&old.scope_id,&new.scope_id);
        prop_assert!(old.paths.iter().zip(&new.paths).all(|(a,b)|a.path_id!=b.path_id));
        prop_assert!(old.validate_for(&other).is_err());
    }

    #[test]
    fn prop_tampered_reports_never_validate(case in graph_cases(),field in 0u8..6,delta in 1u32..10000){
        let mut case=case;case.edges.push((0,case.nodes-1,0));case.edges.sort();case.edges.dedup();
        let mut r=run(&case,4097,generous(&case));
        match field{
            0=>r.paths[0].nodes[0].site+=u64::from(delta),
            1=>r.returned_count+=delta as usize,
            2=>r.counters.expanded_states+=delta as usize,
            3=>r.paths[0].contains_opaque_summary = !r.paths[0].contains_opaque_summary,
            4=>r.input.graphs[0].identity.snapshot_id.push_str("-foreign"),
            _=>r.scope_id=sha(&delta.to_le_bytes()),
        }
        prop_assert!(r.validate().is_err());
    }

    #[test]
    fn prop_codec_round_trips_generated_paths_and_rejects_unknown_fields(case in graph_cases(),np in 1usize..=12){
        let r=run(&case,np,generous(&case));let value=crate::reports::encode_frame_paths(&r).unwrap();
        prop_assert_eq!(crate::reports::decode_frame_paths(&serde_json::to_vec(&value).unwrap()).unwrap(),r);
        let mut forged=value;forged["unreviewed_field"]=serde_json::json!(true);
        prop_assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
    }

    #[test]
    fn prop_nested_and_recursive_activations_keep_frame_identity(recursive in any::<bool>(),from in 0usize..3,to_hint in 0usize..3,kinds in 1usize..=6,np in 1usize..=12){
        let to=to_hint%(from+1);let q=FramePathQuestion{from_frame:from,to_frame:to,np};
        let r=list(activation_input(recursive,kinds),q,FramePathLimits::default(),Some(usize::MAX)).unwrap();
        prop_assert!(r.available);prop_assert!(r.returned_count<np);
        // Each younger activation contributes one of the typed entry-to-anchor alternatives.
        let expected=kinds.pow((from-to) as u32).min(np-1);
        prop_assert_eq!(r.returned_count,expected);
        for p in &r.paths{
            prop_assert_eq!(p.nodes[0].frame,from);prop_assert_eq!(p.nodes.last().unwrap().frame,to);
            prop_assert_eq!(p.edges.iter().filter(|e|e.kind==FramePathEdgeKind::Call).count(),from-to);
            for e in &p.edges{
                if e.kind==FramePathEdgeKind::Call{prop_assert_eq!(e.src.frame,e.dst.frame+1);}else{prop_assert_eq!(e.src.frame,e.dst.frame);}
            }
        }
        r.validate().unwrap();
    }

    #[test]
    fn prop_output_byte_limits_never_publish_oversized_results(case in graph_cases(),bytes in 0usize..32768,np in 1usize..=12){
        if let Ok(r)=list(generated_input(&case),question(np),FramePathLimits{max_output_bytes:bytes,..generous(&case)},Some(usize::MAX)){
            prop_assert!(serde_json::to_vec(&r).unwrap().len()<=bytes);r.validate().unwrap();
            for format in [crate::reports::Format::Json,crate::reports::Format::Text,crate::reports::Format::Dot]{
                if let Ok(output)=crate::reports::render_frame_paths(&r,format){prop_assert!(output.len()<=bytes);}
            }
        }
    }
}
