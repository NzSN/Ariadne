//! Coordinator tests use captured bytes and the checked typed-BIL seam. Native
//! producer/capture parity remains a separately exercised qualification tier.
use super::*;
use crate::effects::{PreparationIdentity, SemanticEvidence};
use crate::llvm_mc::{PreparedBatch, PreparedSite};

const ROOT: u64 = 0x401000;
const STORE: u64 = ROOT + 4;
const END: u64 = STORE + 8;
const STORE_BYTES: [u8; 8] = [0x0f, 0x29, 0xb4, 0x24, 0x40, 0x02, 0, 0];

fn rsp_sub() -> String {
    serde_json::json!([{"kind":"move", "var": {
        "name":"RSP", "index":0,"virtual":false,"width":64,"type":"imm"
    }, "value":{"kind":"binop","op":17,
        "lhs":{"kind":"var","var":{
            "name":"RSP","index":0,"virtual":false,"width":64,"type":"imm"
        }}, "rhs":{"kind":"int","value":"0x8:64"}
    }}])
    .to_string()
}
fn snapshot() -> FileSnapshot {
    let mut bytes = vec![0x48, 0x83, 0xec, 8];
    bytes.extend(STORE_BYTES);
    bytes.push(0xc3);
    let mut dump = common::Dump::new(false);
    dump.memory64(&[(ROOT, &bytes)]);
    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap()
}
fn setup(snapshot: &FileSnapshot, premise: bool) -> GuardPreparation {
    let query = AnalysisQuery {
        entry_points: [ROOT].into(),
        slice_seeds: [STORE].into(),
    };
    let activation = guard::Activation {
        thread_id: 17,
        frame_activation: "synthetic-frame-activation".into(),
    };
    let roots = vec![guard::Root {
        site: format!("0x{ROOT:016x}"),
        function_entry: premise,
        anchor_sha256: "1".repeat(64),
    }];
    let scope = guard_query_scope(
        &snapshot.metadata.snapshot_id,
        &query,
        &PrepareLimits::default(),
        &activation,
        &roots,
    )
    .unwrap();
    let premises = if premise {
        vec![guard::Premise {
            origin: guard::PremiseOrigin::AbiNormalCall,
            snapshot: snapshot.metadata.snapshot_id.clone(),
            query_scope_sha256: scope.clone(),
            root: format!("0x{ROOT:016x}"),
            point: format!("0x{ROOT:016x}"),
            activation: activation.clone(),
            policy: guard::ABI_POLICY.into(),
            evidence_sha256: "2".repeat(64),
            rsp_residues: 1 << 8,
            rsp_value: None,
        }]
    } else {
        Vec::new()
    };
    GuardPreparation {
        limits: guard::Limits::default(),
        activation,
        roots,
        premises,
        query_scope_sha256: scope,
        producer: Some(guard::Producer {
            helper_sha256: "3".repeat(64),
            runtime_sha256: "4".repeat(64),
            decoder_sha256: "5".repeat(64),
            projection: guard::PRODUCER_PROFILE.into(),
        }),
    }
}
fn batch(
    candidates: &BTreeMap<u64, Option<Vec<u8>>>,
) -> (
    PreparedBatch,
    BTreeMap<u64, crate::bap::target_resolution::Transfer>,
    BTreeMap<u64, guard::CandidateSite>,
) {
    let mut sites = BTreeMap::new();
    let mut sources = BTreeMap::new();
    for (&va, prefix) in candidates {
        let (length, opcode, ast, kind, opaque) = match va {
            ROOT => (4, "SUB64ri8", rsp_sub(), InstructionKind::Ordinary, false),
            STORE => (
                8,
                "MOVAPSmr",
                include_str!("../bap/fixtures/vector/movaps-bil.json")
                    .trim()
                    .into(),
                InstructionKind::Ordinary,
                true,
            ),
            END => (1, "RET64", "[]".into(), InstructionKind::Return, true),
            _ => (0, "", "[]".into(), InstructionKind::Stop, true),
        };
        let bytes = prefix
            .as_ref()
            .map_or_else(Vec::new, |b| b[..length].to_vec());
        let instruction = Instruction {
            kind,
            complete: length != 0,
            fall: if kind == InstructionKind::Ordinary {
                [va + length as u64].into()
            } else {
                Default::default()
            },
            ..Instruction::default()
        };
        let mut evidence = placeholder();
        evidence.bytes = bytes.clone();
        evidence.length = length as u8;
        evidence.source = if length == 0 {
            ByteSource::Unavailable
        } else {
            ByteSource::Captured
        };
        evidence.opcode = Some(opcode.into());
        evidence.decoder_control = Some(kind);
        evidence.control = Some(kind);
        evidence.quality = if opaque {
            EffectQuality::Opaque
        } else {
            EffectQuality::ExternalLifted
        };
        evidence.rule = (!opaque).then(|| guard::PRODUCER_PROFILE.into());
        evidence.semantic = Some(SemanticEvidence {
            backend: "bap-x86-legacy".into(),
            helper_sha256: "3".repeat(64),
            runtime_sha256: "4".repeat(64),
            projection: guard::PRODUCER_PROFILE.into(),
            status: if va == STORE {
                "guard-pending"
            } else if opaque {
                "opaque-call-return"
            } else {
                "projected"
            }
            .into(),
            ast_sha256: Some(crate::reports::sha256(ast.as_bytes())),
            fallback: None,
            gaps: Vec::new(),
            memory_accesses: Vec::new(),
        });
        sources.insert(
            va,
            guard::CandidateSite {
                site: format!("0x{va:016x}"),
                bytes_hex: bytes.iter().map(|b| format!("{b:02x}")).collect(),
                ast,
                control: guard::CandidateControl::from_instruction(&instruction),
                opaque,
            },
        );
        sites.insert(
            va,
            PreparedSite {
                instruction,
                evidence,
                gaps: Vec::new(),
                decodable: length != 0,
                complete_capture: length != 0,
            },
        );
    }
    (
        PreparedBatch {
            sites,
            identity: PreparationIdentity {
                target: "x86_64-pc-windows-msvc".into(),
                decoder: "test independent control".into(),
                protocol: 1,
                ruleset: guard::PRODUCER_PROFILE.into(),
                catalogue: "gpr-bytes-status-df-memory-other-v1".into(),
            },
        },
        BTreeMap::new(),
        sources,
    )
}
fn prepare(snapshot: &FileSnapshot, setup: &GuardPreparation) -> FilePreparedAnalysis {
    snapshot
        .prepare_materialization_guarded(
            &AnalysisQuery {
                entry_points: [ROOT].into(),
                slice_seeds: [STORE].into(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            None,
            Some(setup),
            |_, candidates, _, _| Ok(batch(candidates)),
        )
        .unwrap()
}

#[test]
fn unseeded_guard_continuation_is_candidate_only_and_commits_no_store() {
    let snapshot = snapshot();
    let prepared = prepare(&snapshot, &setup(&snapshot, false));
    assert_eq!(
        prepared.materialization.attempted,
        [ROOT, STORE, END].into()
    );
    let report = prepared.guard_admission().unwrap();
    assert_eq!(report.guards[0].verdict, guard::Verdict::Unknown);
    assert!(report.guards[0].normal_ast.is_none());
    let stop = &prepared.prepared.request.instructions[&STORE];
    assert_eq!(stop.kind, InstructionKind::Stop);
    assert!(stop.fall.is_empty());
    assert!(stop.must_defs.is_empty());
    assert_eq!(
        prepared.prepared.instructions[&STORE].quality,
        EffectQuality::Opaque
    );
    prepared.validate_guard_admission().unwrap();
    let completed = crate::analyze(prepared.prepared.request.clone()).unwrap();
    assert!(!completed.state.decoded.contains(&END));
}

#[test]
fn frozen_alignment_selection_projects_the_store_and_binds_noncyclic_identity() {
    let snapshot = snapshot();
    let prepared = prepare(&snapshot, &setup(&snapshot, true));
    let report = prepared.guard_admission().unwrap();
    assert_eq!(report.guards[0].verdict, guard::Verdict::Aligned);
    assert_eq!(report.guards[0].input_residues, 1);
    assert_eq!(
        prepared.prepared.request.instructions[&STORE].kind,
        InstructionKind::Ordinary
    );
    assert_eq!(
        prepared.prepared.request.instructions[&STORE].may_defs,
        ["memory:any".into()].into()
    );
    assert!(
        prepared.prepared.request.instructions[&STORE]
            .must_defs
            .is_empty()
    );
    assert_ne!(
        report.guards[0].original_ast_sha256,
        report.guards[0].normal_ast_sha256.clone().unwrap()
    );
    assert_eq!(
        report.final_request_sha256.as_ref().unwrap(),
        &normalized_request_digest(&prepared.prepared.request).unwrap()
    );
    assert_eq!(
        prepared.materialization.query_identity,
        guard::analysis_id(report).unwrap()
    );
    let unseeded = prepare(&snapshot, &setup(&snapshot, false));
    assert_ne!(
        report.intent_id,
        unseeded.guard_admission().unwrap().intent_id
    );
    assert_ne!(
        prepared.materialization.query_identity,
        unseeded.materialization.query_identity
    );
    prepared.validate_guard_admission().unwrap();
}

#[test]
fn guarded_publication_rejects_source_premise_effect_and_request_tampering() {
    let snapshot = snapshot();
    let original = prepare(&snapshot, &setup(&snapshot, true));
    let mut changed = original.clone();
    changed.guard_admission.as_mut().unwrap().input.premises[0].evidence_sha256 = "9".repeat(64);
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original.clone();
    changed
        .prepared
        .instructions
        .get_mut(&STORE)
        .unwrap()
        .semantic
        .as_mut()
        .unwrap()
        .ast_sha256 = Some("9".repeat(64));
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original.clone();
    changed
        .prepared
        .request
        .instructions
        .get_mut(&STORE)
        .unwrap()
        .may_defs
        .clear();
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original.clone();
    changed.prepared.request.slice_seeds.clear();
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original;
    changed.reads.get_mut(&STORE).unwrap().bytes[0] ^= 1;
    assert!(changed.validate_guard_admission().is_err());
}

#[test]
fn frame_assumption_names_validated_entry_and_distinct_recursive_activation() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures/frame_paths/recursive.dmp");
    let snapshot = FileSnapshot::open_minidump(path, OpenLimits::default()).unwrap();
    let chain = snapshot
        .recover_thread_frames(17, crate::investigation::FrameRecoveryLimits::default())
        .unwrap();
    let first = chain.frames[1].function_begin.unwrap();
    let second = chain.frames[2].function_begin.unwrap();
    assert_eq!(first, second);
    let (_, one) = snapshot
        .frame_guard_preparation(
            &chain,
            1,
            first,
            &PrepareLimits::default(),
            guard::Limits::default(),
        )
        .unwrap();
    let (_, two) = snapshot
        .frame_guard_preparation(
            &chain,
            2,
            second,
            &PrepareLimits::default(),
            guard::Limits::default(),
        )
        .unwrap();
    assert_ne!(one.activation, two.activation);
    assert_ne!(one.query_scope_sha256, two.query_scope_sha256);
    assert_eq!(one.premises[0].origin, guard::PremiseOrigin::AbiNormalCall);
    assert_eq!(one.premises[0].point, format!("0x{first:016x}"));
    assert_eq!(one.premises[0].rsp_residues, 1 << 8);
    assert!(one.premises[0].rsp_value.is_none());
    assert!(
        snapshot
            .frame_guard_preparation(
                &chain,
                1,
                chain.frames[1].pc,
                &PrepareLimits::default(),
                guard::Limits::default()
            )
            .is_err()
    );
    let mut forged = chain.clone();
    forged.frames[1].function_begin = Some(chain.frames[1].pc);
    assert!(
        snapshot
            .frame_guard_preparation(
                &forged,
                1,
                chain.frames[1].pc,
                &PrepareLimits::default(),
                guard::Limits::default()
            )
            .is_err()
    );
}

#[test]
fn guard_candidate_budget_returns_no_partial_prefix_proof() {
    let snapshot = snapshot();
    let mut scoped = setup(&snapshot, true);
    scoped.limits.max_sites = 1;
    let result = snapshot.prepare_materialization_guarded(
        &AnalysisQuery {
            entry_points: [ROOT].into(),
            slice_seeds: [STORE].into(),
        },
        &PreparationOptions::default(),
        PrepareLimits::default(),
        None,
        Some(&scoped),
        |_, candidates, _, _| Ok(batch(candidates)),
    );
    assert!(matches!(result, Err(PreparationError::LimitReached { .. })));
}

#[test]
fn scoped_guard_setup_cannot_be_reused_with_other_seeds_or_preparation_limits() {
    let snapshot = snapshot();
    let scoped = setup(&snapshot, true);
    for (seeds, limits) in [
        (AddressSet::new(), PrepareLimits::default()),
        (
            [STORE].into(),
            PrepareLimits {
                batch_size: 64,
                ..PrepareLimits::default()
            },
        ),
    ] {
        let mut calls = 0;
        let result = snapshot.prepare_materialization_guarded(
            &AnalysisQuery {
                entry_points: [ROOT].into(),
                slice_seeds: seeds,
            },
            &PreparationOptions::default(),
            limits,
            None,
            Some(&scoped),
            |_, candidates, _, _| {
                calls += 1;
                Ok(batch(candidates))
            },
        );
        assert!(matches!(
            result,
            Err(PreparationError::InvalidQuery(
                "guard premise scope differs from actual query or limits"
            ))
        ));
        assert_eq!(calls, 0);
    }
}

#[test]
fn empty_budget_receipts_never_publish_the_provisional_continuation() {
    let snapshot = snapshot();
    let mut scoped = setup(&snapshot, true);
    scoped.limits.max_residue_updates = 0;
    let prepared = prepare(&snapshot, &scoped);
    let report = prepared.guard_admission().unwrap();
    assert_eq!(report.stop.as_deref(), Some("guard-zero-work-budget"));
    assert!(report.guards.is_empty());
    assert_eq!(
        prepared.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
    assert!(!prepared.prepared.request.decodable.contains(&STORE));
    prepared.validate_guard_admission().unwrap();
}

#[test]
fn a_later_candidate_barrier_cannot_certify_the_aligned_prefix() {
    let snapshot = snapshot();
    let scoped = setup(&snapshot, true);
    let prepared = snapshot
        .prepare_materialization_guarded(
            &AnalysisQuery {
                entry_points: [ROOT].into(),
                slice_seeds: [STORE].into(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            None,
            Some(&scoped),
            |_, candidates, _, _| {
                let (mut batch, transfers, mut sources) = batch(candidates);
                if let Some(site) = batch.sites.get_mut(&END) {
                    site.instruction.kind = InstructionKind::Stop;
                    site.instruction.complete = false;
                    site.decodable = false;
                    let source = sources.get_mut(&END).unwrap();
                    source.control = guard::CandidateControl::from_instruction(&site.instruction);
                }
                Ok((batch, transfers, sources))
            },
        )
        .unwrap();
    let report = prepared.guard_admission().unwrap();
    assert!(report.input.barriers.contains(&format!("0x{END:016x}")));
    assert_eq!(report.guards[0].verdict, guard::Verdict::Unknown);
    assert!(report.normal_selection(STORE).is_none());
    assert_eq!(
        prepared.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
    prepared.validate_guard_admission().unwrap();
}

#[test]
fn a_candidate_only_backedge_joins_before_any_normal_store_is_admitted() {
    let mut code = vec![0x48, 0x83, 0xec, 8];
    code.extend(STORE_BYTES);
    code.extend([0xeb, 0xf2]);
    let mut dump = common::Dump::new(false);
    dump.memory64(&[(ROOT, &code)]);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let scoped = setup(&snapshot, true);
    let prepared = snapshot
        .prepare_materialization_guarded(
            &AnalysisQuery {
                entry_points: [ROOT].into(),
                slice_seeds: [STORE].into(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            None,
            Some(&scoped),
            |_, candidates, _, _| {
                let (mut batch, transfers, mut sources) = batch(candidates);
                if let Some(site) = batch.sites.get_mut(&END) {
                    site.instruction.kind = InstructionKind::Jump;
                    site.instruction.targets = [ROOT].into();
                    site.evidence.length = 2;
                    site.evidence.bytes = vec![0xeb, 0xf2];
                    site.evidence.opcode = Some("JMP_1".into());
                    site.evidence.quality = EffectQuality::ExternalLifted;
                    site.evidence.rule = Some(guard::PRODUCER_PROFILE.into());
                    let source = sources.get_mut(&END).unwrap();
                    source.bytes_hex = "ebf2".into();
                    source.opaque = false;
                    source.ast = serde_json::json!([{"kind":"jump","target":{
                        "kind":"int","value":"0x401000:64"
                    }}])
                    .to_string();
                    source.control = guard::CandidateControl::from_instruction(&site.instruction);
                    let semantic = site.evidence.semantic.as_mut().unwrap();
                    semantic.status = "projected".into();
                    semantic.ast_sha256 = Some(crate::reports::sha256(source.ast.as_bytes()));
                }
                Ok((batch, transfers, sources))
            },
        )
        .unwrap();
    let report = prepared.guard_admission().unwrap();
    assert!(report.input.barriers.is_empty());
    assert_eq!(report.guards[0].input_residues, (1 << 8) | 1);
    assert_eq!(report.guards[0].verdict, guard::Verdict::Unknown);
    assert_eq!(
        prepared.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
    assert!(report.normal_selection(STORE).is_none());
    prepared.validate_guard_admission().unwrap();
}

#[test]
fn guarded_frame_v2_retains_full_sources_and_renders_the_assumed_entry_premise() {
    let snapshot = FileSnapshot::open_minidump(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/input/fixtures/guard-frame.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, crate::investigation::FrameRecoveryLimits::default())
        .unwrap();
    let entry = 0x400200;
    let (query, mut scoped) = snapshot
        .frame_guard_preparation(
            &chain,
            0,
            entry,
            &PrepareLimits::default(),
            guard::Limits::default(),
        )
        .unwrap();
    scoped.producer = setup(&snapshot, true).producer;
    let prepared = snapshot
        .prepare_materialization_guarded(
            &query,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            None,
            Some(&scoped),
            |_, candidates, _, _| {
                let shifted = candidates
                    .iter()
                    .map(|(&va, bytes)| (va - entry + ROOT, bytes.clone()))
                    .collect();
                let (mut batch, transfers, sources) = batch(&shifted);
                let unshift = |va: u64| va - ROOT + entry;
                let mut new_sources = BTreeMap::new();
                batch.sites = batch
                    .sites
                    .into_iter()
                    .map(|(va, mut site)| {
                        site.instruction.fall =
                            site.instruction.fall.into_iter().map(unshift).collect();
                        site.instruction.targets =
                            site.instruction.targets.into_iter().map(unshift).collect();
                        let mut source = sources[&va].clone();
                        source.site = format!("0x{:016x}", unshift(va));
                        source.control =
                            guard::CandidateControl::from_instruction(&site.instruction);
                        new_sources.insert(unshift(va), source);
                        (unshift(va), site)
                    })
                    .collect();
                Ok((batch, transfers, new_sources))
            },
        )
        .unwrap();
    prepared.validate_guard_admission().unwrap();
    let completed = crate::CompletedAnalysis::from_analyzer(
        crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
    );
    let investigation =
        crate::input::investigation::bind_investigation(&prepared, &completed).unwrap();
    let explanation = crate::investigation::explain_fault_address(
        &investigation,
        crate::investigation::FaultAddressQuestion {
            site: entry + 4,
            memory_access: 0,
        },
        crate::investigation::ExplainLimits::default(),
    )
    .unwrap();
    explanation.validate().unwrap();
    let encoded_explanation = crate::reports::encode_explanation(&explanation).unwrap();
    let restored =
        crate::reports::decode_explanation(&serde_json::to_vec(&encoded_explanation).unwrap())
            .unwrap();
    assert!(restored.guard_request.is_some());
    let mut changed = explanation.clone();
    changed.guard_request = None;
    assert_eq!(
        changed.validate().unwrap_err().to_string(),
        "guarded explanation normalized request absent"
    );
    let mut changed = explanation.clone();
    changed.guard_request.as_mut().unwrap()["instructions"][1]["may_defs"] = serde_json::json!([]);
    assert!(changed.validate().is_err());
    for field in ["bytes", "ast", "producer", "access"] {
        let mut changed = explanation.clone();
        let record = changed
            .evidence
            .iter_mut()
            .find(|e| e.instruction.va == entry + 4)
            .unwrap();
        match field {
            "bytes" => record.instruction.bytes_hex = "90".into(),
            "ast" => record.instruction.ast_sha256 = Some("9".repeat(64)),
            "producer" => record.instruction.helper_sha256 = Some("9".repeat(64)),
            "access" => record.instruction.accesses[0].access_width = 64,
            _ => unreachable!(),
        }
        let expected = if field == "access" {
            "guarded explanation selected normal access changed"
        } else {
            "guarded explanation captured bytes or original AST changed"
        };
        assert_eq!(
            changed.validate().unwrap_err().to_string(),
            expected,
            "{field}"
        );
    }
    let bound = crate::investigation::bind_frame_paths(chain, vec![(0, investigation)]).unwrap();
    let listing = crate::investigation::list_frame_paths(
        &bound,
        crate::investigation::FramePathQuestion {
            from_frame: 0,
            to_frame: 0,
            np: 2,
        },
        crate::investigation::FramePathLimits::default(),
    )
    .unwrap();
    assert_eq!(listing.schema, "ariadne.frame-paths/v2");
    assert!(
        listing
            .premises
            .iter()
            .any(|p| p.contains("assumed windows-amd64-normal-call-entry/v1")
                && p.contains("entry RSP mod 16 = 8"))
    );
    let encoded = crate::reports::encode_frame_paths(&listing).unwrap();
    let graph = &encoded["input"]["graphs"][0]["guard_admission"];
    assert_eq!(
        graph["report"]["input"]["sites"].as_array().unwrap().len(),
        3
    );
    assert_eq!(
        graph["normalized"]["instructions"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    assert_eq!(graph["sites"].as_array().unwrap().len(), 3);
    let roundtrip =
        crate::reports::decode_frame_paths(&serde_json::to_vec(&encoded).unwrap()).unwrap();
    roundtrip.validate_for(&bound).unwrap();
    let mut forged = encoded.clone();
    let profile = forged["input"]["graphs"][0]["identity"]["semantic_profile"]
        .as_str()
        .unwrap()
        .to_string();
    let changed = profile.replace("RSP-residue-mask=0x0100", "RSP-residue-mask=0x0001");
    assert_ne!(profile, changed);
    forged["input"]["graphs"][0]["identity"]["semantic_profile"] = serde_json::json!(changed);
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
    let mut forged = encoded.clone();
    forged["input"]["graphs"][0]["guard_admission"]["report"]["input"]["activation"]["frame_activation"] =
        serde_json::json!("another-frame");
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
    let mut forged = encoded.clone();
    forged["input"]["graphs"][0]["guard_admission"]["normalized"]["instructions"][1]["may_defs"] =
        serde_json::json!([]);
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
    let mut forged = encoded;
    forged["schema"] = serde_json::json!("ariadne.frame-paths/v1");
    assert!(crate::reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err());
}
