//! Offline paired-proof controls over an explicit unavailable-code endpoint.
//! This fixture claims neither target completeness nor a normal guard path.
use super::*;
use crate::bap::{composition, guard_admission as guard, target_resolution as target};
use crate::{
    AnalysisRequest, Analyzer, CompletedAnalysis, InputKind, Instruction, InstructionKind,
};
use std::collections::BTreeMap;
use std::path::PathBuf;

fn fixture() -> (CapturedFrameChain, BoundInvestigation) {
    let snapshot = crate::input::FileSnapshot::open_minidump(
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/input/fixtures/guard-frame.dmp"),
        crate::input::OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let site = 0x400200;
    let name = format!("0x{site:016x}");
    let locations: crate::LocationSet = ["state:other".to_owned()].into();
    let instruction = Instruction {
        kind: InstructionKind::Stop,
        fall: Default::default(),
        targets: Default::default(),
        complete: false,
        uses: locations.clone(),
        may_defs: locations.clone(),
        must_defs: Default::default(),
    };
    let request = AnalysisRequest {
        snapshot_id: chain.snapshot_id.clone(),
        addresses: [site].into(),
        locations,
        entry_points: [site].into(),
        slice_seeds: Default::default(),
        input_kind: InputKind::Dump,
        captured: Default::default(),
        file_backed: Default::default(),
        trusted_fallback: Default::default(),
        decodable: Default::default(),
        instructions: [(site, instruction.clone())].into(),
    };
    request.validate().unwrap();
    let control = guard::CandidateControl::from_instruction(&instruction);
    let activation = guard::Activation {
        thread_id: chain.thread_id,
        frame_activation: format!("{}:0:0x{:016x}", chain.chain_id, chain.frames[0].sp),
    };
    let scope = sha(b"independent-composition-codec-scope");
    let input = guard::GuardInput {
        snapshot: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        query_scope_sha256: scope.clone(),
        preparation_sha256: sha(b"independent-preparation"),
        platform: "windows-amd64".into(),
        roots: vec![guard::Root {
            site: name.clone(),
            function_entry: true,
            anchor_sha256: sha(b"entry-anchor"),
        }],
        seeds: vec![],
        activation: activation.clone(),
        premises: vec![guard::Premise {
            origin: guard::PremiseOrigin::AbiNormalCall,
            snapshot: chain.snapshot_id.clone(),
            query_scope_sha256: scope,
            root: name.clone(),
            point: name.clone(),
            activation,
            policy: guard::ABI_POLICY.into(),
            evidence_sha256: sha(b"normal-call-premise"),
            rsp_residues: 1 << 8,
            rsp_value: None,
        }],
        producer: guard::Producer {
            helper_sha256: sha(b"fixture-helper"),
            runtime_sha256: sha(b"fixture-runtime"),
            decoder_sha256: sha(b"fixture-decoder"),
            projection: guard::PRODUCER_PROFILE.into(),
        },
        policy: guard::PROFILE.into(),
        model_version: guard::MODEL_VERSION.into(),
        model_sha256: guard::model_identity(),
        limits: guard::Limits::default(),
        candidate_epoch: 0,
        closure_complete: false,
        barriers: vec![name.clone()],
        sites: vec![guard::CandidateSite {
            site: name,
            bytes_hex: String::new(),
            ast: "[]".into(),
            control: control.clone(),
            opaque: true,
        }],
    };
    let mut guards = guard::certify_guards(&input).unwrap();
    let normalized = crate::bap::core_adapter::encode_request(&request).unwrap();
    guard::bind_final_request(
        &input,
        &mut guards,
        &sha(&serde_json::to_vec(&normalized).unwrap()),
    )
    .unwrap();
    let targets = target::Report {
        schema: "ariadne.indirect-target-resolution/v3".into(),
        profile: target::LOCAL_PROFILE.into(),
        memory_premise: target::MEMORY_PREMISE.into(),
        snapshot: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        graph_sha256: target::graph_digest(&request.instructions, &request.entry_points).unwrap(),
        limits: target::Limits::default(),
        resolutions: vec![],
        data_reads: vec![],
        transfers: vec![],
        stop: None,
    };
    let composition = composition::seal(
        &request,
        &BTreeMap::from([(site, control)]),
        0,
        &targets,
        &guards,
        &request,
    )
    .unwrap();
    let sources = vec![SiteEvidence {
        va: site,
        bytes_hex: String::new(),
        captured: false,
        opcode: None,
        quality: "unavailable".into(),
        semantic_status: None,
        helper_sha256: None,
        runtime_sha256: None,
        ast_sha256: None,
        projection: None,
        accesses: vec![],
        spans: vec![],
        gaps: vec!["missing-code".into()],
    }];
    let context = EvidenceContext {
        snapshot_id: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        query_id: composition::analysis_id(&composition).unwrap(),
        semantic_profile: format!(
            "independent:{}{}",
            composition_capture_binding(&composition, &sources).unwrap(),
            composition_semantic_suffix(&composition, &targets, &guards).unwrap()
        ),
        sites: sources,
        recovery_gaps: vec![],
    };
    let completed = CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
    let mut bound = BoundInvestigation::new(&completed, &request, context).unwrap();
    bound.guard_admission = Some(guards);
    bound.target_resolution = Some(targets);
    bound.composition = Some(composition);
    (chain, bound)
}

#[test]
fn paired_explanation_roundtrip_preserves_sources_premises_and_unknown_endpoint() {
    let (_, bound) = fixture();
    let explanation = explain_fault_address(
        &bound,
        FaultAddressQuestion {
            site: 0x400200,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    assert_eq!(explanation.schema, "ariadne.fault-address-explanation/v4");
    assert!(explanation.composition.is_some());
    assert!(explanation.target_resolution.is_some());
    assert!(explanation.guard_admission.is_some());
    assert_eq!(
        explanation.guard_sources.as_ref().unwrap(),
        &bound.context.sites
    );
    let encoded = crate::reports::encode_explanation(&explanation).unwrap();
    let decoded =
        crate::reports::decode_explanation(&serde_json::to_vec(&encoded).unwrap()).unwrap();
    assert_eq!(decoded, explanation);
    for format in [crate::reports::Format::Text, crate::reports::Format::Dot] {
        let rendered = crate::reports::render_explanation(&decoded, format).unwrap();
        assert!(rendered.contains(composition::PROFILE));
        assert!(rendered.contains(guard::ABI_POLICY));
        assert!(rendered.contains(target::MEMORY_PREMISE));
    }
    for field in [
        "composition",
        "target_resolution",
        "guard_admission",
        "guard_request",
        "guard_sources",
    ] {
        let mut forged = encoded.clone();
        forged.as_object_mut().unwrap().remove(field);
        assert!(
            crate::reports::decode_explanation(&serde_json::to_vec(&forged).unwrap()).is_err(),
            "stripped {field}"
        );
    }
    let mut changed = decoded.clone();
    changed.guard_sources.as_mut().unwrap()[0]
        .gaps
        .push("forged-source-gap".into());
    assert!(changed.validate().is_err());
    let mut changed = decoded.clone();
    changed.target_resolution.as_mut().unwrap().memory_premise = "historical-memory".into();
    assert!(changed.validate().is_err());
    let mut changed = decoded.clone();
    changed.composition.as_mut().unwrap().candidate_epoch += 1;
    assert!(changed.validate().is_err());
    let mut changed = decoded;
    changed.schema = "ariadne.fault-address-explanation/v2".into();
    assert!(changed.validate().is_err());
}

#[test]
fn paired_frame_codec_replays_full_request_and_rejects_proof_or_source_changes() {
    let (chain, bound) = fixture();
    let bound = bind_frame_paths(chain, vec![(0, bound)]).unwrap();
    let listing = list_frame_paths(
        &bound,
        FramePathQuestion {
            from_frame: 0,
            to_frame: 0,
            np: 2,
        },
        FramePathLimits::default(),
    )
    .unwrap();
    assert_eq!(listing.schema, COMPOSED_FRAME_PATH_SCHEMA);
    assert!(!listing.available);
    let encoded = crate::reports::encode_frame_paths(&listing).unwrap();
    assert_eq!(
        crate::reports::decode_frame_paths(&serde_json::to_vec(&encoded).unwrap()).unwrap(),
        listing
    );
    for field in [
        "composition",
        "target_resolution",
        "report",
        "normalized",
        "sites",
    ] {
        let mut forged = encoded.clone();
        forged["input"]["graphs"][0]["guard_admission"]
            .as_object_mut()
            .unwrap()
            .remove(field);
        assert!(
            crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err(),
            "stripped {field}"
        );
    }
    let mut forged = encoded;
    forged["input"]["graphs"][0]["guard_admission"]["sites"][0]["gaps"] =
        serde_json::json!(["changed-capture-gap"]);
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
}

/// Exact capture bytes with independently supplied finite BIL facts. This
/// codec fixture deliberately has no native-producer qualification claim.
fn reachable_frame_fixture(normal: bool) -> (CapturedFrameChain, BoundInvestigation) {
    let (chain, template) = fixture();
    let snapshot = crate::input::FileSnapshot::open_minidump(
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/input/fixtures/guard-frame.dmp"),
        crate::input::OpenLimits::default(),
    )
    .unwrap();
    let root = 0x400200;
    let store = 0x400204;
    let ret = 0x40020c;
    let root_raw = serde_json::json!([{"kind":"move","var":{
        "name":"RSP","index":0,"virtual":false,"width":64,"type":"imm"
    },"value":{"kind":"binop","op":17,"lhs":{"kind":"var","var":{
        "name":"RSP","index":0,"virtual":false,"width":64,"type":"imm"
    }},"rhs":{"kind":"int","value":"0x8:64u"}}}]);
    let canonical = |raw: serde_json::Value| {
        serde_json::to_string(&serde_json::from_value::<Vec<crate::bap::ast::Stmt>>(raw).unwrap())
            .unwrap()
    };
    let asts = [
        (root, canonical(root_raw)),
        (
            store,
            canonical(
                serde_json::from_str(include_str!("../bap/fixtures/vector/movaps-bil.json"))
                    .unwrap(),
            ),
        ),
        (ret, "[]".into()),
    ]
    .into_iter()
    .collect::<BTreeMap<_, _>>();
    let locations = crate::effects::Catalogue.locations();
    let mut root_instruction = Instruction {
        kind: InstructionKind::Ordinary,
        fall: [store].into(),
        complete: true,
        ..Instruction::default()
    };
    let root_projection = crate::bap::Backend::guard_normal_projection(
        &asts[&root],
        "SUB64ri8",
        &snapshot.read_prefix(root, 4).unwrap().bytes,
        root,
    )
    .unwrap();
    root_instruction.uses = root_projection.instruction.uses;
    root_instruction.may_defs = root_projection.instruction.may_defs;
    root_instruction.must_defs = root_projection.instruction.must_defs;
    if !normal {
        root_instruction.uses = locations.clone();
        root_instruction.may_defs = locations.clone();
        root_instruction.must_defs.clear();
    }
    let candidate = AnalysisRequest {
        snapshot_id: chain.snapshot_id.clone(),
        addresses: [root, store, ret].into(),
        locations: locations.clone(),
        entry_points: [root].into(),
        slice_seeds: [ret].into(),
        input_kind: InputKind::Dump,
        captured: [root, store, ret].into(),
        decodable: [root, store, ret].into(),
        instructions: [
            (root, root_instruction),
            (
                store,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [ret].into(),
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                ret,
                Instruction {
                    kind: InstructionKind::Return,
                    complete: true,
                    uses: locations.clone(),
                    may_defs: locations.clone(),
                    ..Instruction::default()
                },
            ),
        ]
        .into(),
        ..AnalysisRequest::default()
    };
    candidate.validate().unwrap();
    let mut input = template.guard_admission.unwrap().input;
    input.seeds = vec![format!("0x{ret:016x}")];
    input.candidate_epoch = 1;
    input.closure_complete = true;
    input.barriers.clear();
    input.sites = [(root, 4), (store, 8), (ret, 1)]
        .into_iter()
        .map(|(site, length)| guard::CandidateSite {
            site: format!("0x{site:016x}"),
            bytes_hex: crate::investigation::frame_unwind::hex(
                &snapshot.read_prefix(site, length).unwrap().bytes,
            ),
            ast: asts[&site].clone(),
            control: guard::CandidateControl::from_instruction(&candidate.instructions[&site]),
            opaque: site != root || !normal,
        })
        .collect();
    let mut guards = guard::certify_guards(&input).unwrap();
    assert_eq!(guards.guards[0].verdict == guard::Verdict::Aligned, normal);
    let mut request = candidate.clone();
    let selected = guards.normal_selection(store).map(|ast| {
        crate::bap::Backend::guard_normal_projection(
            ast,
            "MOVAPSmr",
            &snapshot.read_prefix(store, 8).unwrap().bytes,
            store,
        )
        .unwrap()
    });
    if let Some(selected) = &selected {
        request
            .instructions
            .insert(store, selected.instruction.clone());
    } else {
        request.instructions.insert(
            store,
            Instruction {
                kind: InstructionKind::Stop,
                uses: request.locations.clone(),
                may_defs: request.locations.clone(),
                ..Instruction::default()
            },
        );
        request.decodable.remove(&store);
    }
    let normalized = crate::bap::core_adapter::encode_request(&request).unwrap();
    guard::bind_final_request(
        &input,
        &mut guards,
        &sha(&serde_json::to_vec(&normalized).unwrap()),
    )
    .unwrap();
    let mut targets = template.target_resolution.unwrap();
    targets.graph_sha256 =
        target::graph_digest(&candidate.instructions, &candidate.entry_points).unwrap();
    let composed = composition::seal(
        &candidate,
        &input
            .sites
            .iter()
            .map(|s| {
                (
                    crate::bap::core_adapter::address(&s.site).unwrap(),
                    s.control.clone(),
                )
            })
            .collect(),
        input.candidate_epoch,
        &targets,
        &guards,
        &request,
    )
    .unwrap();
    let sources: Vec<_> = input
        .sites
        .iter()
        .map(|s| {
            let site = crate::bap::core_adapter::address(&s.site).unwrap();
            let read = snapshot.read_prefix(site, s.bytes_hex.len() / 2).unwrap();
            let projected = (site == store || site == root) && normal;
            SiteEvidence {
                va: site,
                bytes_hex: s.bytes_hex.clone(),
                captured: true,
                opcode: Some(
                    if site == root {
                        "SUB64ri8"
                    } else if site == store {
                        "MOVAPSmr"
                    } else {
                        "RET64"
                    }
                    .into(),
                ),
                quality: if projected { "external_lift" } else { "opaque" }.into(),
                semantic_status: Some(
                    if site == store && !normal {
                        "guard-not-admitted"
                    } else if site == ret {
                        "opaque-call-return"
                    } else if projected {
                        "projected"
                    } else {
                        "opaque-ordinary"
                    }
                    .into(),
                ),
                helper_sha256: Some(input.producer.helper_sha256.clone()),
                runtime_sha256: Some(input.producer.runtime_sha256.clone()),
                ast_sha256: Some(sha(s.ast.as_bytes())),
                projection: Some(input.producer.projection.clone()),
                accesses: if site == store {
                    selected.as_ref().map_or_else(Vec::new, |s| {
                        s.memory_accesses.iter().map(AddressUse::from).collect()
                    })
                } else {
                    Vec::new()
                },
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
            }
        })
        .collect();
    let context = EvidenceContext {
        snapshot_id: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        query_id: composition::analysis_id(&composed).unwrap(),
        semantic_profile: format!(
            "independent:{}{}",
            composition_capture_binding(&composed, &sources).unwrap(),
            composition_semantic_suffix(&composed, &targets, &guards).unwrap()
        ),
        sites: sources,
        recovery_gaps: vec![],
    };
    let completed = CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
    let mut bound = BoundInvestigation::new(&completed, &request, context).unwrap();
    bound.guard_admission = Some(guards);
    bound.composition = Some(composed);
    bound.target_resolution = Some(targets);
    (chain, bound)
}
fn reached_listing(normal: bool) -> FramePathListing {
    let (chain, bound) = reachable_frame_fixture(normal);
    let bound = bind_frame_paths(chain, vec![(0, bound)]).unwrap();
    list_frame_paths(
        &bound,
        FramePathQuestion {
            from_frame: 0,
            to_frame: 0,
            np: 3,
        },
        FramePathLimits::default(),
    )
    .unwrap()
}

#[test]
fn paired_frame_recovery_has_exact_reached_nodes_edges_and_unknown_stop_gaps() {
    let normal = reached_listing(true);
    assert!(normal.available);
    normal.validate().unwrap();
    let encoded = crate::reports::encode_frame_paths(&normal).unwrap();
    assert_eq!(
        encoded["input"]["graphs"][0]["nodes"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    assert_eq!(
        encoded["input"]["graphs"][0]["edges"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    let unknown = reached_listing(false);
    assert!(!unknown.available);
    unknown.validate().unwrap();
    let encoded = crate::reports::encode_frame_paths(&unknown).unwrap();
    assert_eq!(
        encoded["input"]["graphs"][0]["nodes"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    let gaps = encoded["input"]["graphs"][0]["gaps"].as_array().unwrap();
    assert!(
        gaps.iter()
            .any(|g| g.as_str().unwrap().contains("DecodeFailed"))
    );
    assert!(
        gaps.iter()
            .any(|g| g.as_str().unwrap().contains("missing-seed"))
    );
}

#[test]
fn rehashed_paired_frame_graph_cannot_insert_remove_or_relabel_edges_and_nodes() {
    let listing = reached_listing(true);
    let original = crate::reports::encode_frame_paths(&listing).unwrap();
    for mutation in 0..4 {
        let mut forged = original.clone();
        let graph = &mut forged["input"]["graphs"][0];
        match mutation {
            0 => {
                graph["edges"].as_array_mut().unwrap().pop();
            }
            1 => {
                let mut extra = graph["edges"][0].clone();
                extra["dst"]["site"] = serde_json::json!("0x000000000040020c");
                graph["edges"].as_array_mut().unwrap().push(extra);
            }
            2 => graph["edges"][0]["kind"] = serde_json::json!("taken"),
            _ => {
                graph["nodes"].as_array_mut().unwrap().pop();
                graph["edges"].as_array_mut().unwrap().pop();
            }
        }
        // Re-enumerating also refreshes scope/path hashes and output counters;
        // exact recovery validation must reject the attacker-controlled input.
        let parsed: FramePathListing = serde_json::from_value(forged).unwrap();
        assert!(
            parsed
                .relist_for_test()
                .unwrap_err()
                .to_string()
                .contains("topology or coverage gaps"),
            "mutation {mutation}"
        );
    }
}

#[test]
fn unknown_guard_cannot_publish_an_unreached_candidate_node_or_erase_recovery_gaps() {
    let original = crate::reports::encode_frame_paths(&reached_listing(false)).unwrap();
    for add_node in [true, false] {
        let mut forged = original.clone();
        let graph = &mut forged["input"]["graphs"][0];
        if add_node {
            let source = graph["guard_admission"]["sites"]
                .as_array()
                .unwrap()
                .iter()
                .find(|s| s["va"] == "0x000000000040020c")
                .unwrap()
                .clone();
            graph["nodes"]
                .as_array_mut()
                .unwrap()
                .push(serde_json::json!({
                    "evidence":source,"call":false,"fall":[],"targets":[],
                }));
        } else {
            graph["gaps"] = serde_json::json!([]);
        }
        let parsed: FramePathListing = serde_json::from_value(forged).unwrap();
        assert!(
            parsed
                .relist_for_test()
                .unwrap_err()
                .to_string()
                .contains("topology or coverage gaps")
        );
    }
}
