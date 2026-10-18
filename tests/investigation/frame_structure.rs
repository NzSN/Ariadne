//! Independent unavailable-endpoint fixture; no native helpers or effect fallback.
use super::*;
use crate::bap::{composition, guard_admission as guard, target_resolution as target};
use crate::investigation::{
    FrameRecoveryLimits, SiteEvidence, composition_capture_binding, composition_semantic_suffix,
    sha,
};
use crate::{AnalysisRequest, InputKind, Instruction, InstructionKind};
use std::collections::BTreeMap;
use std::path::PathBuf;
pub(crate) fn fixture() -> (CapturedFrameChain, BoundFrameRecovery) {
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
    let policy = FrameStructureLimits::default();
    let prep = PreparationProof {
        limits: PreparationLimitsProof {
            max_starts: 4096,
            max_candidates: 8192,
            max_prefix_bytes: 4096 * 15,
            max_decoder_batches: 4096,
            batch_size: 128,
        },
        open_limits: OpenLimitsProof {
            max_file_bytes: 256 * 1024 * 1024,
            max_streams: 1024,
            max_records: 131072,
            max_metadata_bytes: 16 * 1024 * 1024,
            max_capture_ranges: 131072,
            max_overlap: 64,
            max_read_bytes: 65536,
        },
    };
    let roots = vec![guard::Root {
        site: name.clone(),
        function_entry: true,
        anchor_sha256: frame_entry_anchor(&chain, 0, site).unwrap(),
    }];
    use sha2::{Digest, Sha256};
    let mut digest = Sha256::new();
    digest.update(b"ariadne-minidump-query-v1\0");
    digest.update(request.snapshot_id.as_bytes());
    for set in [&request.entry_points, &request.slice_seeds] {
        digest.update((set.len() as u64).to_le_bytes());
        for address in set {
            digest.update(address.to_le_bytes());
        }
    }
    for value in [4096u64, 8192, 4096 * 15, 4096, 128] {
        digest.update(value.to_le_bytes());
    }
    let original_query = format!("{:x}", digest.finalize());
    let scope = sha(&serde_json::to_vec(&(original_query, &activation, &roots)).unwrap());
    let preparation_hash = sha(&serde_json::to_vec(&serde_json::json!({"limits":prep.limits,"locations":request.locations,"open_limits":prep.open_limits,"profile":guard::PROFILE})).unwrap());
    let input = guard::GuardInput {
        normal_flow: Some(guard::NormalFlowEvidence::empty()),
        snapshot: chain.snapshot_id.clone(),
        artifact_sha256: chain.artifact_sha256.clone(),
        query_scope_sha256: scope.clone(),
        preparation_sha256: preparation_hash,
        platform: "windows-amd64".into(),
        roots: vec![guard::Root {
            site: name.clone(),
            function_entry: true,
            anchor_sha256: frame_entry_anchor(&chain, 0, site).unwrap(),
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
    let recovery =
        crate::recovery::recover(request, FrameStructureLimits::default().recovery_limits())
            .unwrap();
    let bound = bind_recovery(
        &chain,
        0,
        recovery,
        context,
        RecoveryProofs {
            alignment: None,
            guard: Some(guards),
            target: Some(targets),
            composition: Some(composition),
            decoder_records: BTreeMap::new(),
            preparation: prep,
        },
        &policy,
    )
    .unwrap();
    (chain, bound)
}

#[test]
fn unavailable_endpoint_drains_with_gap_without_dataflow() {
    let (chain, bound) = fixture();
    assert!(bound.recovery().state().pending.is_empty());
    assert_eq!(bound.recovery().state().phase(), crate::Phase::Recover);
    let bound = bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, bound)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap();
    assert_eq!(bound.frames().len(), 1);
    assert!(bound.links().is_empty());
    assert!(bound.frames()[0].recovery_drained);
    assert_eq!(
        bound.frames()[0].gaps[0].kind,
        FrameStructureGapKind::UnavailableBytes
    );
}

#[test]
fn v1_rejects_even_null_conditional_alignment_transport() {
    let (chain, frame) = fixture();
    let bound = bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, frame)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap();
    let bytes = crate::reports::frame_structure::render_json(&bound).unwrap();
    let mut value: serde_json::Value = serde_json::from_str(&bytes).unwrap();
    value["frames"][0]["alignment"] = serde_json::Value::Null;
    crate::reports::frame_structure::rehash_for_test(&mut value).unwrap();
    value["frames"][0]["alignment"] = serde_json::Value::Null;
    assert!(
        crate::reports::frame_structure::decode(
            &serde_json::to_vec(&value).unwrap(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper in remote WSL"]
fn conditional_report_rejects_rehashed_hypothesis_stripping_and_reassignment() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let snapshot = crate::input::FileSnapshot::open_minidump(
        root.join("tests/input/fixtures/guard-frame.dmp"),
        crate::input::OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let config = crate::bap::Config::from_env();
    let options = crate::effects::PreparationOptions::default();
    let decoder = root.join("target/ariadne-llvm-mc");
    let setup = crate::input::FramePreparation {
        decoder: &decoder,
        config: &config,
        options: &options,
        limits: crate::input::PrepareLimits::default(),
    };
    let policy = FrameStructureLimits::default();
    let prepared = snapshot
        .prepare_frame_structure(
            &chain,
            0,
            0x400200,
            None,
            &setup,
            false,
            policy.guard.clone(),
            None,
        )
        .unwrap();
    let recovery = snapshot
        .bind_frame_recovery_hypotheses(&chain, 0, &prepared, &[0x400204], &policy)
        .unwrap();
    let bound = bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, recovery)],
        vec![],
        policy.clone(),
    )
    .unwrap();
    let report = crate::reports::frame_structure::render_json(&bound).unwrap();
    let original: serde_json::Value = serde_json::from_str(&report).unwrap();
    assert_eq!(original["schema"], CONDITIONAL_FRAME_STRUCTURE_SCHEMA);
    for mutation in 0..4 {
        let mut changed = original.clone();
        match mutation {
            0 => changed["conditional_on"] = serde_json::json!([]),
            1 => {
                changed["frames"][0]
                    .as_object_mut()
                    .unwrap()
                    .remove("alignment");
            }
            2 => changed["frames"][0]["alignment"]["owner"] = serde_json::json!(1),
            3 => {
                changed["schema"] = serde_json::json!(FRAME_STRUCTURE_SCHEMA);
                changed["producer"] = serde_json::json!(FRAME_STRUCTURE_PRODUCER);
            }
            _ => unreachable!(),
        }
        crate::reports::frame_structure::rehash_for_test(&mut changed).unwrap();
        assert!(
            crate::reports::frame_structure::decode(
                &serde_json::to_vec(&changed).unwrap(),
                &policy
            )
            .is_err(),
            "mutation {mutation}"
        );
    }
    assert!(
        snapshot
            .bind_frame_recovery_hypotheses(&bound.chain, 0, &prepared, &[0x400200], &policy)
            .is_err()
    );
}
#[test]
fn missing_selected_frame_keeps_independent_map_and_replay_is_idempotent() {
    let (chain, bound) = fixture();
    let question = FrameStructureQuestion {
        from_frame: 1,
        to_frame: 0,
    };
    let bound = bind_frame_structure(
        chain,
        question,
        vec![(0, bound)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap();
    assert_eq!(bound.frames().len(), 1);
    assert!(
        bound
            .diagnostics()
            .iter()
            .any(|diagnostic| diagnostic.frame == 1)
    );
    let (chain, recovery) = fixture();
    let again = bind_frame_structure(
        chain,
        bound.question().clone(),
        vec![(0, recovery)],
        bound.diagnostics().to_vec(),
        FrameStructureLimits::default(),
    )
    .unwrap();
    assert_eq!(bound.diagnostics(), again.diagnostics());
}
#[test]
fn rehashed_source_identity_or_activation_and_missing_proof_rejected() {
    let (chain, bound) = fixture();
    let request = bound.request().clone();
    let context = bound.context().clone();
    let receipt = *bound.recovery().receipt();
    let producer = *bound.recovery().limits();
    let mut proofs = bound.proofs().clone();
    proofs.guard = None;
    assert!(
        replay_frame_recovery(
            &chain,
            0,
            request.clone(),
            context.clone(),
            proofs,
            receipt,
            producer,
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let mut wrong = context.clone();
    wrong.snapshot_id = "wrong".into();
    assert!(
        replay_frame_recovery(
            &chain,
            0,
            request.clone(),
            wrong,
            bound.proofs().clone(),
            receipt,
            producer,
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let limited = FrameStructureLimits {
        max_replay_visits: 0,
        ..FrameStructureLimits::default()
    };
    assert!(
        replay_frame_recovery(
            &chain,
            0,
            request,
            context,
            bound.proofs().clone(),
            receipt,
            producer,
            &limited
        )
        .is_err()
    );
}
#[test]
fn aggregate_zero_node_or_proof_policy_rejects_instead_of_clipping() {
    let (chain, bound) = fixture();
    let limits = FrameStructureLimits {
        max_graph_nodes: 0,
        ..FrameStructureLimits::default()
    };
    assert!(
        bind_frame_structure(
            chain,
            FrameStructureQuestion {
                from_frame: 0,
                to_frame: 0
            },
            vec![(0, bound)],
            vec![],
            limits
        )
        .is_err()
    );
    let (chain, bound) = fixture();
    let limits = FrameStructureLimits {
        max_proof_bytes: 0,
        ..FrameStructureLimits::default()
    };
    assert!(
        bind_frame_structure(
            chain,
            FrameStructureQuestion {
                from_frame: 0,
                to_frame: 0
            },
            vec![(0, bound)],
            vec![],
            limits
        )
        .is_err()
    );
}

#[test]
fn active_call_requires_reached_e8_not_merely_prepared_source() {
    // Exercise the shared admission predicate directly with private fixture values.
    // The capture's physical chain is not asserted as a new unwind qualification.
    let (mut chain, fixture) = fixture();
    let call = 0x1005u64;
    let target = chain.frames[0].function_begin.unwrap();
    let continuation = call + 5;
    let mut parent = chain.frames[0].clone();
    parent.index = 1;
    parent.pc = continuation;
    parent.function_begin = Some(0x1000);
    parent.function_end = Some(0x1100);
    chain.frames.truncate(1);
    chain.frames.push(parent);
    let locations: crate::LocationSet = ["state:other".into()].into();
    let ret = Instruction {
        kind: InstructionKind::Return,
        uses: locations.clone(),
        may_defs: locations.clone(),
        ..Instruction::default()
    };
    let call_instruction = Instruction {
        kind: InstructionKind::Call,
        fall: [continuation].into(),
        targets: [target].into(),
        complete: true,
        uses: locations.clone(),
        may_defs: locations.clone(),
        must_defs: Default::default(),
    };
    let mut request = AnalysisRequest {
        snapshot_id: chain.snapshot_id.clone(),
        addresses: [0x1000, call, continuation, target].into(),
        locations,
        entry_points: [0x1000].into(),
        slice_seeds: Default::default(),
        input_kind: InputKind::Dump,
        captured: [0x1000, call, continuation].into(),
        file_backed: Default::default(),
        trusted_fallback: Default::default(),
        decodable: [0x1000, call, continuation].into(),
        instructions: [
            (0x1000, ret.clone()),
            (call, call_instruction),
            (continuation, ret),
            (target, Instruction::default()),
        ]
        .into(),
    };
    let offset = (target as i64 - continuation as i64) as i32;
    let bytes = [vec![0xe8], offset.to_le_bytes().to_vec()].concat();
    let mut context = fixture.context.clone();
    context.sites = vec![SiteEvidence {
        va: call,
        bytes_hex: crate::investigation::frame_unwind::hex(&bytes),
        captured: true,
        opcode: Some("CALL64pcrel32".into()),
        quality: "opaque".into(),
        semantic_status: Some("opaque-call-return".into()),
        helper_sha256: None,
        runtime_sha256: None,
        ast_sha256: None,
        projection: None,
        accesses: vec![],
        gaps: vec![],
        spans: vec![crate::investigation::Span {
            va: call,
            length: 5,
            contributors: vec![crate::investigation::Contributor {
                stream: 5,
                entry: 0,
                file_offset: 0,
            }],
        }],
    }];
    let mut proofs = fixture.proofs;
    proofs
        .guard
        .as_mut()
        .unwrap()
        .input
        .activation
        .frame_activation = format!("{}:1:0x{:016x}", chain.chain_id, chain.frames[1].sp);
    let recovery = crate::recovery::recover(
        request.clone(),
        FrameStructureLimits::default().recovery_limits(),
    )
    .unwrap();
    let parent = BoundFrameRecovery {
        recovery,
        context: context.clone(),
        proofs: proofs.clone(),
        identity: fixture.identity.clone(),
    };
    assert!(
        active_calls(&chain, 0, &parent).unwrap().is_empty(),
        "prepared but unreached E8 must not justify activation link"
    );
    request.entry_points = [call].into();
    let recovery =
        crate::recovery::recover(request, FrameStructureLimits::default().recovery_limits())
            .unwrap();
    let parent = BoundFrameRecovery {
        recovery,
        context,
        proofs,
        identity: fixture.identity,
    };
    assert_eq!(
        active_calls(&chain, 0, &parent).unwrap(),
        vec![(call, target)]
    );
    let child_request = AnalysisRequest {
        snapshot_id: chain.snapshot_id.clone(),
        addresses: [target].into(),
        locations: ["state:other".into()].into(),
        entry_points: [target].into(),
        slice_seeds: Default::default(),
        input_kind: InputKind::Dump,
        captured: [target].into(),
        file_backed: Default::default(),
        trusted_fallback: Default::default(),
        decodable: [target].into(),
        instructions: [(
            target,
            Instruction {
                kind: InstructionKind::Return,
                ..Instruction::default()
            },
        )]
        .into(),
    };
    let pending = crate::recovery::recover(
        child_request.clone(),
        crate::recovery::RecoveryLimits {
            max_visits: 0,
            deadline_ms: 60_000,
        },
    )
    .unwrap();
    let child = BoundFrameRecovery {
        recovery: pending,
        context: parent.context.clone(),
        proofs: parent.proofs.clone(),
        identity: parent.identity.clone(),
    };
    let (link, diagnostic) = frame_link(&chain, 0, Some(&parent), Some(&child)).unwrap();
    assert!(!link.admitted);
    assert_eq!(
        (link.call_site, link.child_entry),
        (Some(call), Some(target))
    );
    assert_eq!(
        diagnostic.unwrap().kind,
        FrameStructureDiagnosticKind::UnavailableLinkEndpoint
    );
    let mut failed_request = child_request.clone();
    failed_request.decodable.clear();
    let failed = crate::recovery::recover(
        failed_request,
        FrameStructureLimits::default().recovery_limits(),
    )
    .unwrap();
    let failed_child = BoundFrameRecovery {
        recovery: failed,
        context: parent.context.clone(),
        proofs: parent.proofs.clone(),
        identity: parent.identity.clone(),
    };
    assert!(
        !frame_link(&chain, 0, Some(&parent), Some(&failed_child))
            .unwrap()
            .0
            .admitted
    );
    let admitted = crate::recovery::recover(
        child_request,
        FrameStructureLimits::default().recovery_limits(),
    )
    .unwrap();
    let child = BoundFrameRecovery {
        recovery: admitted,
        context: parent.context.clone(),
        proofs: parent.proofs.clone(),
        identity: parent.identity.clone(),
    };
    assert!(
        frame_link(&chain, 0, Some(&parent), Some(&child))
            .unwrap()
            .0
            .admitted
    );
}

fn report_fixture() -> BoundFrameStructure {
    let (chain, bound) = fixture();
    bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, bound)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap()
}

#[test]
fn structural_codec_checks_an_independent_publication_binding_before_replay() {
    let limits = FrameStructureLimits::default();
    let encoded = crate::reports::frame_structure::render_json(&report_fixture()).unwrap();
    let mut raw: serde_json::Value = serde_json::from_str(&encoded).unwrap();
    let expected = raw["structure_id"].as_str().unwrap().to_string();
    assert!(
        crate::reports::frame_structure::decode_expected(encoded.as_bytes(), &limits, &expected)
            .is_ok()
    );
    raw["frames"][0]["receipt"]["visits"] = serde_json::json!(0);
    crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
    let error = crate::reports::frame_structure::decode_expected(
        &serde_json::to_vec(&raw).unwrap(),
        &limits,
        &expected,
    )
    .err()
    .unwrap();
    assert!(error.to_string().contains("trusted publication binding"));
}

#[test]
fn structural_codec_roundtrip_and_all_views_retain_unknown_endpoint() {
    let bound = report_fixture();
    let encoded = crate::reports::frame_structure::render_json(&bound).unwrap();
    let decoded = crate::reports::frame_structure::decode(
        encoded.as_bytes(),
        &FrameStructureLimits::default(),
    )
    .unwrap();
    assert_eq!(decoded.frames(), bound.frames());
    assert_eq!(decoded.links(), bound.links());
    assert_eq!(decoded.diagnostics(), bound.diagnostics());
    assert!(
        crate::reports::frame_structure::render_text(&decoded)
            .unwrap()
            .contains("UnavailableBytes")
    );
    assert!(
        crate::reports::frame_structure::render_dot(&decoded)
            .unwrap()
            .contains("UnavailableBytes")
    );
    assert_eq!(
        crate::reports::frame_structure::render_json(&decoded).unwrap(),
        encoded
    );
}

#[test]
fn structural_codec_rejects_unknown_duplicate_fields_and_host_limits() {
    let encoded = crate::reports::frame_structure::render_json(&report_fixture()).unwrap();
    let mut raw: serde_json::Value = serde_json::from_str(&encoded).unwrap();
    raw["unknown"] = serde_json::json!(1);
    assert!(
        crate::reports::frame_structure::decode(
            &serde_json::to_vec(&raw).unwrap(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let duplicate = encoded.replacen(
        "\"schema\":",
        "\"schema\":\"ariadne.frame-structure/v1\",\"schema\":",
        1,
    );
    assert!(
        crate::reports::frame_structure::decode(
            duplicate.as_bytes(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let mut limits = FrameStructureLimits {
        max_input_bytes: encoded.len(),
        ..FrameStructureLimits::default()
    };
    assert!(crate::reports::frame_structure::decode(encoded.as_bytes(), &limits).is_ok());
    limits.max_input_bytes = encoded.len() - 1;
    assert!(crate::reports::frame_structure::decode(encoded.as_bytes(), &limits).is_err());
    let limits = FrameStructureLimits {
        max_replay_visits: 0,
        ..FrameStructureLimits::default()
    };
    assert!(crate::reports::frame_structure::decode(encoded.as_bytes(), &limits).is_err());
    let limits = FrameStructureLimits {
        max_dictionary_entries: 0,
        ..FrameStructureLimits::default()
    };
    assert!(crate::reports::frame_structure::decode(encoded.as_bytes(), &limits).is_err());
    let limits = FrameStructureLimits {
        max_replay_work: 0,
        ..FrameStructureLimits::default()
    };
    assert!(crate::reports::frame_structure::decode(encoded.as_bytes(), &limits).is_err());
    let mut bound = report_fixture();
    bound.limits.max_output_bytes = 0;
    assert!(crate::reports::frame_structure::render_json(&bound).is_err());
    assert!(crate::reports::frame_structure::render_text(&bound).is_err());
    assert!(crate::reports::frame_structure::render_dot(&bound).is_err());
}

#[test]
fn conditional_scope_raw_limits_precede_family_hash_and_proof_validation() {
    let encoded = crate::reports::frame_structure::render_json(&report_fixture()).unwrap();
    let original: serde_json::Value = serde_json::from_str(&encoded).unwrap();
    let mut count = original.clone();
    count["schema"] = serde_json::json!("invalid-family");
    count["conditional_on"] = serde_json::json!(["a".repeat(64), "b".repeat(64)]);
    let host = FrameStructureLimits {
        max_graph_nodes: 1,
        ..FrameStructureLimits::default()
    };
    let error =
        crate::reports::frame_structure::decode(&serde_json::to_vec(&count).unwrap(), &host)
            .err()
            .unwrap();
    assert_eq!(error.to_string(), "structural conditional scope host limit");
    for scope in [
        serde_json::Value::Null,
        serde_json::json!({"not":"an array"}),
    ] {
        let mut raw = original.clone();
        raw["schema"] = serde_json::json!("invalid-family");
        raw["conditional_on"] = scope;
        let error =
            crate::reports::frame_structure::decode(&serde_json::to_vec(&raw).unwrap(), &host)
                .err()
                .unwrap();
        assert_eq!(
            error.to_string(),
            "structural conditional scope must be an array"
        );
    }
    for id in [
        serde_json::json!(7),
        serde_json::json!("a".repeat(63)),
        serde_json::json!("A".repeat(64)),
        serde_json::json!("g".repeat(64)),
        serde_json::json!("a".repeat(8192)),
    ] {
        let mut raw = original.clone();
        raw["schema"] = serde_json::json!("invalid-family");
        raw["conditional_on"] = serde_json::json!([id]);
        let error =
            crate::reports::frame_structure::decode(&serde_json::to_vec(&raw).unwrap(), &host)
                .err()
                .unwrap();
        assert_eq!(
            error.to_string(),
            "structural conditional scope identifier must be canonical 64-digit lowercase hex"
        );
    }
    // The exact host count passes the early gate; v1 still rejects the field.
    let mut exact = original;
    exact["conditional_on"] = serde_json::json!(["a".repeat(64)]);
    let error =
        crate::reports::frame_structure::decode(&serde_json::to_vec(&exact).unwrap(), &host)
            .err()
            .unwrap();
    assert_eq!(
        error.to_string(),
        "structural schema, producer, semantic backend or binding changed"
    );
}

#[test]
fn conditional_scope_respects_lower_producer_cap_before_evidence_replay() {
    let encoded = crate::reports::frame_structure::render_json(&report_fixture()).unwrap();
    let mut raw: serde_json::Value = serde_json::from_str(&encoded).unwrap();
    raw["schema"] = serde_json::json!(CONDITIONAL_FRAME_STRUCTURE_SCHEMA);
    raw["producer"] = serde_json::json!(CONDITIONAL_FRAME_STRUCTURE_PRODUCER);
    raw["conditional_on"] = serde_json::json!(["a".repeat(64)]);
    raw["policy"]["max_graph_nodes"] = serde_json::json!(0);
    // This deliberately missing proof must not be dereferenced: the smaller
    // producer/host policy rejects the scope first, even with a valid rehash.
    raw["frames"][0]["alignment"] = serde_json::json!({
        "owner":0,"role":"alignment","id":"b".repeat(64)
    });
    crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
    let error = crate::reports::frame_structure::decode(
        &serde_json::to_vec(&raw).unwrap(),
        &FrameStructureLimits::default(),
    )
    .err()
    .unwrap();
    assert_eq!(
        error.to_string(),
        "structural conditional scope policy limit"
    );
}

#[test]
fn structural_codec_rehashed_owner_role_counter_and_proof_stripping_fail() {
    let encoded = crate::reports::frame_structure::render_json(&report_fixture()).unwrap();
    let original: serde_json::Value = serde_json::from_str(&encoded).unwrap();
    for (field, value) in [
        (
            "request",
            serde_json::json!({"owner":1,"role":"request","id":original["frames"][0]["request"]["id"]}),
        ),
        (
            "context",
            serde_json::json!({"owner":0,"role":"request","id":original["frames"][0]["context"]["id"]}),
        ),
        ("guard", serde_json::Value::Null),
        (
            "receipt",
            serde_json::json!({"visits":0,"elapsed_ms":0,"stop":"drained"}),
        ),
    ] {
        let mut raw = original.clone();
        raw["frames"][0][field] = value;
        crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
        assert!(
            crate::reports::frame_structure::decode(
                &serde_json::to_vec(&raw).unwrap(),
                &FrameStructureLimits::default()
            )
            .is_err(),
            "rehashed {field}"
        );
    }
    let mut raw = original.clone();
    raw["diagnostics"] = serde_json::json!([{"frame":0,"kind":"missing_frame","message":"forged","attempted":[],"unattempted_references":[]}]);
    crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
    assert!(
        crate::reports::frame_structure::decode(
            &serde_json::to_vec(&raw).unwrap(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let mut raw = original.clone();
    raw["evidence"].as_array_mut().unwrap().pop();
    crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
    assert!(
        crate::reports::frame_structure::decode(
            &serde_json::to_vec(&raw).unwrap(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
    let mut raw = original;
    raw["evidence"][0]["id"] = serde_json::json!("0".repeat(64));
    crate::reports::frame_structure::rehash_for_test(&mut raw).unwrap();
    assert!(
        crate::reports::frame_structure::decode(
            &serde_json::to_vec(&raw).unwrap(),
            &FrameStructureLimits::default()
        )
        .is_err()
    );
}

#[test]
fn auxiliary_scope_follows_multiple_missing_entries_to_first_independent_caller() {
    // This control exercises scope selection only; it does not assert that the
    // edited metadata is a captured unwind or an admitted E8 witness.
    let (mut chain, _) = fixture();
    let original = chain.frames[0].clone();
    chain.frames = (0..4)
        .map(|index| {
            let mut frame = original.clone();
            frame.index = index;
            frame.function_begin = (index >= 2).then_some(0x400200 + index as u64 * 0x100);
            frame.function_end = frame.function_begin.map(|entry| entry + 0x100);
            frame
        })
        .collect();
    let question = FrameStructureQuestion {
        from_frame: 0,
        to_frame: 0,
    };
    assert_eq!(auxiliary_frame_ceiling(&chain, &question), 2);
    // Ancestor 2 remains in the necessary witness scope if frame 1 fails to
    // prepare. The per-recovery E8 checks still prohibit an unproven leaf map.
    let available = [2usize];
    assert!(
        available
            .into_iter()
            .all(|frame| frame <= auxiliary_frame_ceiling(&chain, &question))
    );
    chain.frames[1].function_begin = Some(0x400300);
    assert_eq!(auxiliary_frame_ceiling(&chain, &question), 1);
    chain.frames[0].function_begin = Some(0x400200);
    assert_eq!(auxiliary_frame_ceiling(&chain, &question), 0);
    // A requested older frame supplies the same independent starting point.
    assert_eq!(
        auxiliary_frame_ceiling(
            &chain,
            &FrameStructureQuestion {
                from_frame: 2,
                to_frame: 1
            }
        ),
        2
    );
    chain
        .frames
        .iter_mut()
        .for_each(|frame| frame.function_begin = None);
    assert_eq!(auxiliary_frame_ceiling(&chain, &question), 3);
}

#[test]
fn original_decode_continuations_and_opaque_receipt_domain_are_required() {
    // These are independent decoded-reference controls, not a lifting claim for
    // the on-disk guard fixture. The complete binder separately replays BIL.
    let (_, bound) = fixture();
    let address = 0x400200u64;
    for (kind, opcode, bytes, length, target) in [
        (InstructionKind::Ordinary, "NOOP", "90", 1, None),
        (
            InstructionKind::Conditional,
            "JCC_1",
            "7402",
            2,
            Some(address + 4),
        ),
        (
            InstructionKind::Call,
            "CALL64pcrel32",
            "e800000000",
            5,
            Some(address + 5),
        ),
    ] {
        let mut report = bound.proofs.guard.as_ref().unwrap().clone();
        let control = Instruction {
            kind,
            fall: [address + length].into(),
            targets: target.into_iter().collect(),
            complete: true,
            ..Instruction::default()
        };
        report.input.sites = vec![guard::CandidateSite {
            site: format!("0x{address:016x}"),
            bytes_hex: bytes.into(),
            ast: "[]".into(),
            control: guard::CandidateControl::from_instruction(&control),
            opaque: kind == InstructionKind::Call,
        }];
        let mut site = bound.context.sites[0].clone();
        site.captured = true;
        site.bytes_hex = bytes.into();
        site.opcode = Some(opcode.into());
        site.semantic_status = Some(
            if kind == InstructionKind::Call {
                "opaque-call-return"
            } else {
                "projected"
            }
            .into(),
        );
        let kind_name = match kind {
            InstructionKind::Ordinary => "ordinary",
            InstructionKind::Conditional => "conditional",
            _ => "call",
        };
        let record = format!(
            "v2 {opcode} 0 0 0 0 0 {address} ok {length} {kind_name} {}",
            target
                .map(|target| target.to_string())
                .unwrap_or_else(|| "-".into())
        );
        let records: BTreeMap<_, _> = [(format!("0x{address:016x}"), record)].into();
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &report,
                &[site.clone()],
                &records
            )
            .is_ok(),
            "valid {opcode}"
        );
        let mut changed = report.clone();
        changed.input.sites[0].control.fall = vec![format!("0x{:016x}", address + 17)];
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &changed,
                &[site.clone()],
                &records
            )
            .is_err(),
            "forged {opcode} continuation"
        );
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &report,
                &[site],
                &BTreeMap::new()
            )
            .is_err(),
            "missing {opcode} receipt"
        );
    }
    let mut report = bound.proofs.guard.as_ref().unwrap().clone();
    report.input.sites[0].bytes_hex = "0f".into();
    let mut site = bound.context.sites[0].clone();
    site.captured = true;
    site.bytes_hex = "0f".into();
    site.semantic_status = Some("invalid-decode".into());
    let records = [(
        format!("0x{address:016x}"),
        format!("v2 - 0 0 0 0 0 {address} invalid 0 - -"),
    )]
    .into();
    assert!(
        crate::investigation::frame_paths::validate_structural_decode_sources(
            &report,
            &[site],
            &records
        )
        .is_ok(),
        "invalid captured prefix retains a required zero-extent decode receipt"
    );
}

#[test]
fn captured_membership_admission_and_artifact_extents_have_independent_controls() {
    // Isolate membership and extent premises from BIL replay and physical unwind.
    let (chain, bound) = fixture();
    let address = 0x400200;
    let mut request = bound.request().clone();
    request.captured.insert(address);
    request.decodable.insert(address);
    request.instructions.insert(
        address,
        Instruction {
            kind: InstructionKind::Return,
            complete: true,
            ..Instruction::default()
        },
    );
    let mut context = bound.context.clone();
    let site = &mut context.sites[0];
    site.captured = true;
    site.bytes_hex = "c3".into();
    site.opcode = Some("RET64".into());
    site.semantic_status = Some("opaque-call-return".into());
    site.spans = vec![crate::investigation::Span {
        va: address,
        length: 1,
        contributors: vec![crate::investigation::Contributor {
            stream: 5,
            entry: 0,
            file_offset: chain.artifact_bytes() as u64 - 1,
        }],
    }];
    let mut proofs = bound.proofs.clone();
    proofs.decoder_records.insert(
        format!("0x{address:016x}"),
        format!("v2 RET64 0 0 4 0 0 {address} ok 1 return -"),
    );
    assert!(validate_capture_membership_and_extents(&chain, &request, &context, &proofs).is_ok());
    let mut changed = request.clone();
    changed.captured.clear();
    assert!(validate_capture_membership_and_extents(&chain, &changed, &context, &proofs).is_err());
    let mut changed = request.clone();
    changed.decodable.clear();
    assert!(validate_capture_membership_and_extents(&chain, &changed, &context, &proofs).is_err());
    let mut changed = context.clone();
    changed.sites[0].spans[0].contributors[0].file_offset = chain.artifact_bytes() as u64;
    assert!(validate_capture_membership_and_extents(&chain, &request, &changed, &proofs).is_err());
    changed.sites[0].spans[0].contributors[0].file_offset = u64::MAX;
    assert!(validate_capture_membership_and_extents(&chain, &request, &changed, &proofs).is_err());
    let mut changed = proofs.clone();
    changed.decoder_records.clear();
    assert!(validate_capture_membership_and_extents(&chain, &request, &context, &changed).is_err());
    let mut changed = proofs.clone();
    changed
        .target
        .as_mut()
        .unwrap()
        .data_reads
        .push(target::DataRead {
            address: format!("0x{address:016x}"),
            requested: 1,
            bytes_hex: "00".into(),
            spans: vec![target::Span {
                address: format!("0x{address:016x}"),
                length: 1,
                contributors: vec![target::Contributor {
                    stream: 5,
                    entry: 0,
                    file_offset: chain.artifact_bytes() as u64,
                }],
            }],
            conflict_sources: vec![],
            stop: "RequestedLength".into(),
        });
    assert!(validate_capture_membership_and_extents(&chain, &request, &context, &changed).is_err());
    request.decodable.clear();
    request.captured.clear();
    request.instructions.insert(address, Instruction::default());
    context.sites[0].bytes_hex = "0f".into();
    context.sites[0].opcode = None;
    context.sites[0].semantic_status = Some("invalid-decode".into());
    proofs.decoder_records.insert(
        format!("0x{address:016x}"),
        format!("v2 - 0 0 0 0 0 {address} invalid 0 - -"),
    );
    assert!(
        validate_capture_membership_and_extents(&chain, &request, &context, &proofs).is_ok(),
        "short invalid prefix is captured evidence, but not normalized captured instruction membership"
    );
    request.captured.insert(address);
    assert!(validate_capture_membership_and_extents(&chain, &request, &context, &proofs).is_err());
}

#[test]
fn certified_complete_terminal_stops_require_their_exact_source_and_decode_receipts() {
    // Two frozen source certificates exercise the original failure: certified
    // INT3 and pinned-extent UD1 Stops are complete within normal-flow scope.
    // Addresses are rebased for this decode/source control; no dump rerun is claimed.
    let (_, bound) = fixture();
    for (source_json, receipt_json) in [
        (
            "{\"ast\":\"[{\\\"kind\\\":\\\"exception\\\",\\\"number\\\":3}]\",\"bytes_hex\":\"cc\",\"control\":{\"complete\":true,\"fall\":[],\"kind\":\"stop\",\"targets\":[]},\"opaque\":true,\"site\":\"0x0000000000400200\"}",
            "{\"annotation\":\"exception-exit\",\"ast_sha256\":\"e698c4ea0ca7e41c22fd980e05e32c9e8f876e9e78f49f998d6ac99610a2ff80\",\"bap\":{\"bytes_hex\":\"cc\",\"length\":1,\"opcode\":\"INT3\",\"properties\":{\"call\":false,\"conditional\":false,\"control\":false,\"indirect\":false,\"jump\":false,\"return\":false},\"status\":\"decoded\"},\"bytes_hex\":\"cc\",\"exception\":3,\"reference\":{\"control\":\"stop\",\"decoder_record\":\"v2 INT3 0 0 7 0 0 4194816 ok 1 stop -\",\"length\":1,\"opcode\":\"INT3\"},\"resumption\":\"exception-resumption-outside-local-scope\",\"rule\":\"int3-exception/v1\",\"schema\":\"ariadne.normal-terminal/v1\",\"site\":\"0x0000000000400200\"}",
        ),
        (
            "{\"ast\":\"[]\",\"bytes_hex\":\"670fb94012\",\"control\":{\"complete\":true,\"fall\":[],\"kind\":\"stop\",\"targets\":[]},\"opaque\":true,\"site\":\"0x0000000000400200\"}",
            "{\"annotation\":\"exception-exit\",\"ast_sha256\":\"4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945\",\"bap\":{\"bytes_hex\":\"670fb9\",\"length\":3,\"opcode\":\"UD2B\",\"properties\":{\"call\":false,\"conditional\":false,\"control\":false,\"indirect\":false,\"jump\":false,\"return\":false},\"status\":\"decoded\"},\"bytes_hex\":\"670fb94012\",\"exception\":6,\"reference\":{\"control\":\"stop\",\"decoder_record\":\"v2 UD1Lm 6 r:EAX r:EAX i:1 r:NONE i:18 r:NONE 0 5 0 0 -1 -1 -1 -1 -1 -1 4194816 ok 5 stop -\",\"length\":5,\"opcode\":\"UD1Lm\"},\"resumption\":\"exception-resumption-outside-local-scope\",\"rule\":\"ud1-pinned-extent/v1\",\"schema\":\"ariadne.normal-terminal/v1\",\"site\":\"0x0000000000400200\"}",
        ),
    ] {
        let source: guard::CandidateSite = serde_json::from_str(source_json).unwrap();
        let receipt: guard::TerminalReceipt = serde_json::from_str(receipt_json).unwrap();
        let mut report = bound.proofs.guard.as_ref().unwrap().clone();
        report.input.sites = vec![source.clone()];
        let mut flow = guard::NormalFlowEvidence::empty();
        flow.terminals.push(receipt.clone());
        report.input.normal_flow = Some(flow);
        let mut site = bound.context.sites[0].clone();
        site.captured = true;
        site.bytes_hex = source.bytes_hex.clone();
        site.opcode = Some(receipt.reference.opcode.clone());
        site.quality = "opaque".into();
        site.semantic_status = Some("normal-flow-terminal".into());
        let records = [(
            source.site.clone(),
            receipt.reference.decoder_record.clone(),
        )]
        .into();
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &report,
                std::slice::from_ref(&site),
                &records
            )
            .is_ok(),
            "certified {}",
            receipt.rule
        );
        let mut changed = report.clone();
        changed
            .input
            .normal_flow
            .as_mut()
            .unwrap()
            .terminals
            .clear();
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &changed,
                std::slice::from_ref(&site),
                &records
            )
            .is_err(),
            "complete Stop without certificate"
        );
        let mut changed = report.clone();
        changed.input.sites[0].control.complete = false;
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &changed,
                std::slice::from_ref(&site),
                &records
            )
            .is_err(),
            "certified Stop lost completeness"
        );
        let mut changed = report.clone();
        changed.input.sites[0].ast = "[{\"kind\":\"exception\",\"number\":4}]".into();
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &changed,
                std::slice::from_ref(&site),
                &records
            )
            .is_err(),
            "changed terminal source"
        );
        let mut changed_site = site.clone();
        changed_site.semantic_status = Some("opaque-unsupported".into());
        assert!(
            crate::investigation::frame_paths::validate_structural_decode_sources(
                &report,
                &[changed_site],
                &records
            )
            .is_err(),
            "ordinary opaque Stop cannot claim completeness"
        );
        let changed_record =
            receipt
                .reference
                .decoder_record
                .replacen(" 0 0 7 0 0 ", " 0 0 0 0 0 ", 1);
        if changed_record != receipt.reference.decoder_record {
            let changed_records = [(source.site.clone(), changed_record)].into();
            assert!(
                crate::investigation::frame_paths::validate_structural_decode_sources(
                    &report,
                    &[site],
                    &changed_records
                )
                .is_err(),
                "changed terminal decode reference"
            );
        }
    }
}

/// Internal projection fixture only. Deliberately bypasses source admission so
/// graph-policy tests do not need a lifter; never published/replayed as evidence.
pub(crate) fn connection_projection_fixture(admitted: bool) -> BoundFrameStructure {
    let (chain, recovery) = fixture();
    let mut bound = bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, recovery)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap();
    let mut older = bound.chain.frames[0].clone();
    older.index = 1;
    bound.chain.frames = vec![bound.chain.frames[0].clone(), older];
    for frame in &mut bound.chain.frames {
        frame.function_begin = Some(0);
        frame.function_end = Some(1000);
    }
    bound.question = FrameStructureQuestion {
        from_frame: 1,
        to_frame: 0,
    };
    let template = bound.recoveries[0].1.context.sites[0].clone();
    let node = |frame, site| super::super::FramePathNode { frame, site };
    let mut m = bound.frames[0].clone();
    m.nodes = [10, 20, 30, 40, 2000]
        .into_iter()
        .map(|va| {
            let mut site = template.clone();
            site.va = va;
            site.bytes_hex = "90".into();
            site
        })
        .collect();
    m.edges = vec![
        (10, 20, super::super::FramePathEdgeKind::Taken),
        (10, 30, super::super::FramePathEdgeKind::Fallthrough),
        (20, 40, super::super::FramePathEdgeKind::Next),
        (20, 2000, super::super::FramePathEdgeKind::Jump),
        (20, 30, super::super::FramePathEdgeKind::Call),
    ]
    .into_iter()
    .map(|(a, b, kind)| FrameStructureEdge {
        src: node(0, a),
        dst: node(0, b),
        kind,
    })
    .collect();
    m.gaps = vec![FrameStructureGap {
        kind: FrameStructureGapKind::UnknownIndirectTarget,
        site: 30,
        destination: None,
    }];
    let mut parent = m.clone();
    parent.frame = 1;
    parent.nodes.truncate(2);
    parent.gaps.clear();
    parent.edges = vec![FrameStructureEdge {
        src: node(1, 10),
        dst: node(1, 20),
        kind: super::super::FramePathEdgeKind::Summary,
    }];
    bound.frames = vec![m, parent];
    bound.links = vec![FrameStructureLink {
        conditional_on: vec![],
        caller: 1,
        child: 0,
        call_site: Some(10),
        child_entry: Some(10),
        continuation: 15,
        admitted,
    }];
    bound
}
