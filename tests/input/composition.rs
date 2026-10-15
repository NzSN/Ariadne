//! Captured coordinator controls for the independent C0 composition contract.
use super::*;
use crate::bap::ast::Stmt;
use crate::effects::{PreparationIdentity, SemanticEvidence};
use crate::llvm_mc::{PreparedBatch, PreparedSite};
use serde_json::{Value, json};

const ROOT: u64 = 0x401000;
const LOAD: u64 = ROOT + 4;
const STORE: u64 = LOAD + 7;
const DISPATCH: u64 = STORE + 8;
const TARGET: u64 = 0x402000;
const SLOT: u64 = 0x403000;
const STORE_BYTES: [u8; 8] = [0x0f, 0x29, 0xb4, 0x24, 0x40, 0x02, 0, 0];

fn reg(name: &str) -> Value {
    json!({"name":name,"index":0,"virtual":false,"width":64,"type":"imm"})
}
fn value(name: &str) -> Value {
    json!({"kind":"var","var":reg(name)})
}
fn ast(va: u64, backedge: Option<u64>) -> String {
    let raw = match va {
        ROOT => json!([{"kind":"move","var":reg("RSP"),"value":{
            "kind":"binop","op":17,"lhs":value("RSP"),
            "rhs":{"kind":"int","value":"0x8:64u"}}}]),
        LOAD => json!([{"kind":"move","var":reg("RAX"),"value":{
            "kind":"load","width":64,
            "mem":{"kind":"var","var":{"name":"mem","index":0,
                "virtual":false,"width":0,"type":"mem"}},
            "addr":{"kind":"int","value":format!("0x{SLOT:x}:64u")}}}]),
        STORE => {
            serde_json::from_str(include_str!("../bap/fixtures/vector/movaps-bil.json")).unwrap()
        }
        DISPATCH => json!([{"kind":"jump","target":value("RAX")}]),
        TARGET if backedge.is_some() => json!([{"kind":"jump","target":{
            "kind":"int","value":format!("0x{:x}:64u", backedge.unwrap())}}]),
        _ => json!([]),
    };
    // Match the producer's canonical original AST serialization, rather than
    // changing source identity when extracting a target transfer.
    serde_json::to_string(&serde_json::from_value::<Vec<Stmt>>(raw).unwrap()).unwrap()
}
fn snapshot(code: bool, slot_bytes: usize) -> FileSnapshot {
    snapshot_with_backedge(code, slot_bytes, false)
}
fn snapshot_with_backedge(code: bool, slot_bytes: usize, backedge: bool) -> FileSnapshot {
    snapshot_with_backedge_to(code, slot_bytes, backedge.then_some(STORE))
}
fn snapshot_with_backedge_to(code: bool, slot_bytes: usize, backedge: Option<u64>) -> FileSnapshot {
    let mut bytes = vec![0x48, 0x83, 0xec, 8];
    bytes.extend([0x48, 0x8b, 0x05, 0xf5, 0x1f, 0, 0]);
    bytes.extend(STORE_BYTES);
    bytes.extend([0xff, 0xe0]);
    let pointer = TARGET.to_le_bytes();
    let mut ranges = vec![(ROOT, bytes.as_slice()), (SLOT, &pointer[..slot_bytes])];
    let target_bytes = if let Some(destination) = backedge {
        let offset = i32::try_from(i128::from(destination) - i128::from(TARGET + 5)).unwrap();
        let mut bytes = vec![0xe9];
        bytes.extend(offset.to_le_bytes());
        bytes
    } else {
        vec![0xc3]
    };
    if code {
        ranges.push((TARGET, target_bytes.as_slice()));
    }
    let mut dump = common::Dump::new(false);
    dump.memory64(&ranges);
    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap()
}
fn query() -> AnalysisQuery {
    AnalysisQuery {
        entry_points: [ROOT].into(),
        slice_seeds: [DISPATCH, 0xdead0000].into(),
    }
}
fn setup(snapshot: &FileSnapshot, premise: bool) -> GuardPreparation {
    let activation = guard::Activation {
        thread_id: 17,
        frame_activation: "composition-fixture".into(),
    };
    let roots = vec![guard::Root {
        site: format!("0x{ROOT:016x}"),
        function_entry: premise,
        anchor_sha256: "1".repeat(64),
    }];
    let query_scope_sha256 = guard_query_scope(
        &snapshot.metadata.snapshot_id,
        &query(),
        &PrepareLimits::default(),
        &activation,
        &roots,
    )
    .unwrap();
    let premises = if premise {
        vec![guard::Premise {
            origin: guard::PremiseOrigin::AbiNormalCall,
            snapshot: snapshot.metadata.snapshot_id.clone(),
            query_scope_sha256: query_scope_sha256.clone(),
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
        query_scope_sha256,
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
    backedge: bool,
) -> (
    PreparedBatch,
    BTreeMap<u64, crate::bap::target_resolution::Transfer>,
    BTreeMap<u64, guard::CandidateSite>,
) {
    batch_with_backedge_to(candidates, backedge.then_some(STORE))
}
fn batch_with_backedge_to(
    candidates: &BTreeMap<u64, Option<Vec<u8>>>,
    backedge: Option<u64>,
) -> (
    PreparedBatch,
    BTreeMap<u64, crate::bap::target_resolution::Transfer>,
    BTreeMap<u64, guard::CandidateSite>,
) {
    let mut sites = BTreeMap::new();
    let mut transfers = BTreeMap::new();
    let mut sources = BTreeMap::new();
    for (&va, prefix) in candidates {
        let available = prefix.is_some();
        let (length, opcode, kind) = if !available {
            (0, "", InstructionKind::Stop)
        } else {
            match va {
                ROOT => (4, "SUB64ri8", InstructionKind::Ordinary),
                LOAD => (7, "MOV64rm", InstructionKind::Ordinary),
                STORE => (8, "MOVAPSmr", InstructionKind::Ordinary),
                DISPATCH => (2, "JMP64r", InstructionKind::Indirect),
                TARGET if backedge.is_some() => (5, "JMP_4", InstructionKind::Jump),
                _ => (1, "RET64", InstructionKind::Return),
            }
        };
        let bytes = prefix
            .as_ref()
            .map_or_else(Vec::new, |b| b[..length].to_vec());
        let source_ast = ast(va, backedge);
        let opaque = va == STORE || !available || kind == InstructionKind::Return;
        let instruction = Instruction {
            kind,
            complete: available && kind != InstructionKind::Indirect,
            fall: if kind == InstructionKind::Ordinary {
                [va + length as u64].into()
            } else {
                AddressSet::new()
            },
            targets: backedge
                .filter(|_| va == TARGET)
                .map_or_else(AddressSet::new, |target| [target].into()),
            ..Instruction::default()
        };
        let mut evidence = placeholder();
        evidence.bytes = bytes.clone();
        evidence.length = length as u8;
        evidence.source = if available {
            ByteSource::Captured
        } else {
            ByteSource::Unavailable
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
            } else {
                "projected"
            }
            .into(),
            ast_sha256: Some(crate::reports::sha256(source_ast.as_bytes())),
            fallback: None,
            gaps: Vec::new(),
            memory_accesses: Vec::new(),
        });
        if available && !matches!(kind, InstructionKind::Return | InstructionKind::Jump) {
            transfers.insert(
                va,
                crate::bap::target_resolution::extract(
                    &serde_json::from_str::<Vec<Stmt>>(&source_ast).unwrap(),
                    va,
                    &bytes,
                )
                .unwrap(),
            );
        }
        sources.insert(
            va,
            guard::CandidateSite {
                site: format!("0x{va:016x}"),
                bytes_hex: bytes.iter().map(|b| format!("{b:02x}")).collect(),
                ast: source_ast,
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
                decodable: available,
                complete_capture: available,
            },
        );
    }
    (
        PreparedBatch {
            sites,
            identity: PreparationIdentity {
                target: "x86_64-pc-windows-msvc".into(),
                decoder: "independent composition fixture".into(),
                protocol: 1,
                ruleset: guard::PRODUCER_PROFILE.into(),
                catalogue: "gpr-bytes-status-df-memory-other-v1".into(),
            },
        },
        transfers,
        sources,
    )
}
fn prepare(
    snapshot: &FileSnapshot,
    premise: bool,
    backedge: bool,
    target_limits: crate::bap::target_resolution::Limits,
) -> FilePreparedAnalysis {
    snapshot
        .prepare_materialization_guarded(
            &query(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&target_limits),
            Some(&setup(snapshot, premise)),
            |_, candidates, _, _| Ok(batch(candidates, backedge)),
        )
        .unwrap()
}

#[test]
fn candidate_target_receipt_survives_unknown_final_guard_without_promoting_seeds() {
    let p = prepare(&snapshot(true, 8), false, false, Default::default());
    p.validate_target_resolution().unwrap();
    p.validate_guard_admission().unwrap();
    let target = &p.target_resolution().unwrap().resolutions[0];
    assert_eq!(target.targets, vec![format!("0x{TARGET:016x}")]);
    assert!(target.complete);
    assert!(p.materialization.attempted.contains(&TARGET));
    assert!(!p.materialization.attempted.contains(&0xdead0000));
    assert_eq!(p.prepared.request.entry_points, [ROOT].into());
    assert_eq!(
        p.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
    let candidate = crate::bap::composition::candidate_request(p.composition().unwrap()).unwrap();
    assert_eq!(
        candidate.instructions[&STORE].kind,
        InstructionKind::Ordinary
    );
    assert!(candidate.instructions[&STORE].may_defs.is_empty());
    assert_eq!(
        p.guard_admission().unwrap().guards[0].verdict,
        guard::Verdict::Unknown
    );
    assert_ne!(
        p.materialization.query_identity,
        guard::analysis_id(p.guard_admission().unwrap()).unwrap()
    );
    let result = crate::analyze(p.prepared.request.clone()).unwrap();
    assert!(!result.state.decoded.contains(&TARGET));
}

#[test]
fn paired_alignment_receipt_commits_only_checked_normal_store() {
    let p = prepare(&snapshot(true, 8), true, false, Default::default());
    p.validate_target_resolution().unwrap();
    p.validate_guard_admission().unwrap();
    assert_eq!(
        p.guard_admission().unwrap().guards[0].verdict,
        guard::Verdict::Aligned
    );
    assert_eq!(
        p.prepared.request.instructions[&STORE].may_defs,
        ["memory:any".into()].into()
    );
    assert!(p.prepared.request.instructions[&STORE].must_defs.is_empty());
    assert!(
        crate::analyze(p.prepared.request.clone())
            .unwrap()
            .state
            .decoded
            .contains(&TARGET)
    );
}

#[test]
fn known_missing_code_endpoint_is_attempted_and_keeps_guard_unknown() {
    let p = prepare(&snapshot(false, 8), true, false, Default::default());
    p.validate_target_resolution().unwrap();
    p.validate_guard_admission().unwrap();
    assert_eq!(
        p.target_resolution().unwrap().resolutions[0].targets,
        vec![format!("0x{TARGET:016x}")]
    );
    assert!(p.materialization.attempted.contains(&TARGET));
    assert!(!p.prepared.request.decodable.contains(&TARGET));
    assert!(
        p.guard_admission()
            .unwrap()
            .input
            .barriers
            .contains(&format!("0x{TARGET:016x}"))
    );
    assert_eq!(
        p.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
}

#[test]
fn partial_capture_and_round_budget_preserve_explicit_coverage_residuals() {
    let partial = prepare(&snapshot(true, 4), true, false, Default::default());
    partial.validate_target_resolution().unwrap();
    partial.validate_guard_admission().unwrap();
    assert!(!partial.target_resolution().unwrap().resolutions[0].complete);
    assert!(
        partial.target_resolution().unwrap().resolutions[0]
            .targets
            .is_empty()
    );
    assert_eq!(
        partial.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
    let one_round = prepare(
        &snapshot(true, 8),
        true,
        false,
        crate::bap::target_resolution::Limits {
            max_rounds: 1,
            ..Default::default()
        },
    );
    one_round.validate_target_resolution().unwrap();
    one_round.validate_guard_admission().unwrap();
    assert!(one_round.materialization.attempted.contains(&TARGET));
    assert_eq!(
        one_round.target_resolution().unwrap().stop.as_deref(),
        Some("discovery-round-limit")
    );
    assert!(!one_round.target_resolution().unwrap().resolutions[0].complete);
    assert_eq!(
        one_round.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
}

#[test]
fn late_backedge_invalidates_target_completeness_and_keeps_known_destination() {
    let p = prepare(
        &snapshot_with_backedge(true, 8, true),
        true,
        true,
        Default::default(),
    );
    p.validate_target_resolution().unwrap();
    p.validate_guard_admission().unwrap();
    assert_eq!(
        p.target_resolution().unwrap().resolutions[0].targets,
        vec![format!("0x{TARGET:016x}")]
    );
    assert!(!p.target_resolution().unwrap().resolutions[0].complete);
    assert_eq!(
        p.prepared.request.instructions[&STORE].kind,
        InstructionKind::Stop
    );
}

#[test]
fn proof_relevant_completeness_barrier_and_transfer_changes_advance_epoch() {
    let (_, mut transfers, sources) =
        batch(&[(ROOT, Some(vec![0x48, 0x83, 0xec, 8]))].into(), false);
    let (b, _, _) = batch(&[(ROOT, Some(vec![0x48, 0x83, 0xec, 8]))].into(), false);
    let mut sites = b.sites;
    let mut epoch = 0;
    let mut state = None;
    for change in 0..4 {
        match change {
            1 => sites.get_mut(&ROOT).unwrap().instruction.complete = false,
            2 => sites.get_mut(&ROOT).unwrap().decodable = false,
            3 => {
                transfers.clear();
            }
            _ => {}
        }
        advance_candidate_epoch(
            candidate_fingerprint(&sites, &sources, Some(&transfers)).unwrap(),
            &mut state,
            &mut epoch,
        )
        .unwrap();
        assert_eq!(epoch, change + 1);
    }
    advance_candidate_epoch(
        candidate_fingerprint(&sites, &sources, Some(&transfers)).unwrap(),
        &mut state,
        &mut epoch,
    )
    .unwrap();
    assert_eq!(epoch, 4);
}

#[test]
fn paired_publication_rejects_missing_proofs_stale_epochs_and_forged_final_store() {
    let original = prepare(&snapshot(true, 8), false, false, Default::default());
    let mut changed = original.clone();
    changed.composition = None;
    assert!(changed.validate_target_resolution().is_err());
    let mut changed = original.clone();
    changed.target_resolution = None;
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original.clone();
    changed.composition.as_mut().unwrap().candidate_epoch -= 1;
    assert!(changed.validate_composition().is_err());
    let mut changed = original.clone();
    changed
        .prepared
        .request
        .instructions
        .get_mut(&STORE)
        .unwrap()
        .kind = InstructionKind::Ordinary;
    changed
        .prepared
        .request
        .instructions
        .get_mut(&STORE)
        .unwrap()
        .fall = [DISPATCH].into();
    assert!(changed.validate_guard_admission().is_err());
    let mut changed = original;
    changed
        .target_resolution
        .as_mut()
        .unwrap()
        .memory_premise
        .clear();
    assert!(changed.validate_target_resolution().is_err());
}

#[test]
#[ignore = "requires pinned BAP/LLVM and rebuilt native combined-profile helper"]
fn actual_bap_pending_store_targets_and_native_rust_results_agree() {
    let decoder = Path::new(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc");
    let core = crate::bap::core_session::CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| {
                Path::new(env!("CARGO_MANIFEST_DIR"))
                    .join("target/guarded-target-resolution-native")
            }),
    );
    for (premise, code, slot_bytes, aligned, known) in [
        (false, true, 8, false, true),
        (true, true, 8, true, true),
        (true, false, 8, false, true),
        (true, true, 4, false, false),
    ] {
        let snapshot = snapshot(code, slot_bytes);
        let mut scoped = setup(&snapshot, premise);
        scoped.producer = None;
        let prepared = snapshot
            .prepare_bap_guarded_targets(
                &query(),
                &decoder,
                &crate::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                scoped,
                Default::default(),
            )
            .unwrap();
        prepared.validate_target_resolution().unwrap();
        prepared.validate_guard_admission().unwrap();
        assert_eq!(
            !prepared.target_resolution().unwrap().resolutions[0]
                .targets
                .is_empty(),
            known
        );
        assert_eq!(
            prepared.guard_admission().unwrap().guards[0].verdict == guard::Verdict::Aligned,
            aligned
        );
        let native = crate::bap::core_adapter::NativeAnalyzer::from_capture(
            &core,
            "combined-pending-store-fixture",
            &prepared,
        )
        .unwrap()
        .complete()
        .unwrap()
        .into_result();
        let rust = crate::analyze(prepared.prepared.request.clone()).unwrap();
        assert_eq!(native, rust);
        assert_eq!(native.state.decoded.contains(&TARGET), aligned);
    }
}

#[test]
fn resealed_composition_cannot_rewrite_retained_original_control() {
    let mut p = prepare(&snapshot(true, 8), false, false, Default::default());
    let candidate = crate::bap::composition::candidate_request(p.composition().unwrap()).unwrap();
    let mut forged_original = (**p.original_controls.as_ref().unwrap()).clone();
    forged_original.get_mut(&DISPATCH).unwrap().targets = vec![format!("0x{TARGET:016x}")];
    // Even a fresh central seal must reject resolved targets being relabeled
    // as original decoded facts.
    assert!(
        crate::bap::composition::seal(
            &candidate,
            &forged_original,
            p.composition().unwrap().candidate_epoch,
            p.target_resolution().unwrap(),
            p.guard_admission().unwrap(),
            &p.prepared.request,
        )
        .is_err()
    );
    p.composition
        .as_mut()
        .unwrap()
        .original_controls
        .iter_mut()
        .find(|row| row.site == format!("0x{DISPATCH:016x}"))
        .unwrap()
        .control
        .targets = vec![format!("0x{TARGET:016x}")];
    assert!(
        p.validate_composition()
            .unwrap_err()
            .to_string()
            .contains("original control capture changed")
    );
}

#[test]
fn late_backedge_through_defining_load_keeps_a_universal_local_frontier() {
    let snapshot = snapshot_with_backedge_to(true, 8, Some(LOAD));
    let prepared = snapshot
        .prepare_materialization_guarded(
            &query(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&Default::default()),
            Some(&setup(&snapshot, true)),
            |_, c, _, _| Ok(batch_with_backedge_to(c, Some(LOAD))),
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    prepared.validate_guard_admission().unwrap();
    assert!(prepared.target_resolution().unwrap().resolutions[0].complete);
    assert_eq!(
        prepared.target_resolution().unwrap().resolutions[0].targets,
        vec![format!("0x{TARGET:016x}")]
    );
    assert_eq!(
        prepared.guard_admission().unwrap().guards[0].verdict,
        guard::Verdict::Aligned
    );
}

#[test]
fn fresh_paired_seal_rejects_indirect_bil_relabelled_as_direct_jump() {
    let prepared = prepare(&snapshot(true, 8), false, false, Default::default());
    let mut candidate =
        crate::bap::composition::candidate_request(prepared.composition().unwrap()).unwrap();
    let mut final_request = prepared.prepared.request.clone();
    for request in [&mut candidate, &mut final_request] {
        let i = request.instructions.get_mut(&DISPATCH).unwrap();
        i.kind = InstructionKind::Jump;
        i.complete = true;
    }
    let forged_control =
        guard::CandidateControl::from_instruction(&candidate.instructions[&DISPATCH]);
    let mut original = (**prepared.original_controls.as_ref().unwrap()).clone();
    original.insert(DISPATCH, forged_control.clone());
    let mut target_report = prepared.target_resolution().unwrap().clone();
    target_report.resolutions.clear();
    target_report.graph_sha256 = crate::bap::target_resolution::graph_digest(
        &candidate.instructions,
        &candidate.entry_points,
    )
    .unwrap();
    let mut input = prepared.guard_admission().unwrap().input.clone();
    input
        .sites
        .iter_mut()
        .find(|s| s.site == format!("0x{DISPATCH:016x}"))
        .unwrap()
        .control = forged_control;
    let mut guard_report = guard::certify_guards(&input).unwrap();
    guard::bind_final_request(
        &input,
        &mut guard_report,
        &normalized_request_digest(&final_request).unwrap(),
    )
    .unwrap();
    crate::bap::target_resolution::validate(
        &target_report,
        &candidate.instructions,
        &candidate.entry_points,
    )
    .unwrap();
    guard::replay_report(&input, &guard_report).unwrap();
    assert!(
        crate::bap::composition::seal(
            &candidate,
            &original,
            input.candidate_epoch,
            &target_report,
            &guard_report,
            &final_request,
        )
        .is_err(),
        "fresh hashes and individually replayed proofs do not authorize changing original BIL control"
    );
}

#[test]
fn resealed_candidate_cannot_add_an_unsourced_indirect_without_a_receipt() {
    let p = prepare(&snapshot(true, 8), false, false, Default::default());
    let mut candidate =
        crate::bap::composition::candidate_request(p.composition().unwrap()).unwrap();
    let mut final_request = p.prepared.request.clone();
    for request in [&mut candidate, &mut final_request] {
        let endpoint = request.instructions.get_mut(&0xdead0000).unwrap();
        endpoint.kind = InstructionKind::Indirect;
    }
    let mut targets = p.target_resolution().unwrap().clone();
    targets.graph_sha256 = crate::bap::target_resolution::graph_digest(
        &candidate.instructions,
        &candidate.entry_points,
    )
    .unwrap();
    let input = p.guard_admission().unwrap().input.clone();
    let mut guards = guard::certify_guards(&input).unwrap();
    guard::bind_final_request(
        &input,
        &mut guards,
        &normalized_request_digest(&final_request).unwrap(),
    )
    .unwrap();
    crate::bap::target_resolution::validate(
        &targets,
        &candidate.instructions,
        &candidate.entry_points,
    )
    .unwrap();
    guard::replay_report(&input, &guards).unwrap();
    assert!(
        crate::bap::composition::seal(
            &candidate,
            p.original_controls.as_ref().unwrap(),
            p.composition().unwrap().candidate_epoch,
            &targets,
            &guards,
            &final_request
        )
        .unwrap_err()
        .to_string()
        .contains("indirect receipt absent")
    );
}

#[test]
#[ignore = "requires pinned BAP/LLVM native helpers; exercises two fixed-capacity BAP children"]
fn native_query_rotation_obeys_selected_aggregate_budget_and_pinned_capture_identity() {
    const COUNT: usize = 8193;
    const START: u64 = 0x500000;
    let mut code = vec![0x90; COUNT];
    code[COUNT - 1] = 0xc3;
    let mut dump = common::Dump::new(false);
    dump.memory64(&[(START, code.as_slice())]);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let decoder = Path::new(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc");
    let config = crate::bap::Config::from_env();
    let options = PreparationOptions::default();
    let candidates = |start: usize, count: usize| {
        (start..start + count)
            .map(|index| {
                let va = START + index as u64;
                (va, Some(snapshot.read_prefix(va, 15).unwrap().bytes))
            })
            .collect::<BTreeMap<_, _>>()
    };
    let mut backend = crate::bap::Backend::new(config.clone(), &decoder).unwrap();
    backend.set_query_site_limit(COUNT).unwrap();
    backend.enable_guard_admission();
    backend.enable_target_resolution();
    let mut first_identity = None;
    let mut pinned_semantic_identity = None;
    for start in (0..COUNT).step_by(256) {
        let count = 256.min(COUNT - start);
        let batch = backend
            .prepare(
                &snapshot.metadata.snapshot_id,
                &candidates(start, count),
                &options,
                snapshot.metadata.platform.decoder_target(),
            )
            .unwrap();
        if let Some(identity) = &first_identity {
            assert_eq!(identity, &batch.identity);
        } else {
            first_identity = Some(batch.identity.clone());
        }
        for site in batch.sites.values() {
            assert!(site.decodable);
            assert_eq!(site.evidence.source, ByteSource::Captured);
            let source = site.evidence.semantic.as_ref().unwrap();
            let identity = (
                source.helper_sha256.clone(),
                source.runtime_sha256.clone(),
                source.projection.clone(),
            );
            if let Some(expected) = &pinned_semantic_identity {
                assert_eq!(expected, &identity);
            } else {
                pinned_semantic_identity = Some(identity);
            }
        }
    }
    assert_eq!(backend.metrics().helper_processes, 2);
    assert_eq!(backend.metrics().reference_processes, 1);
    assert_eq!(backend.take_guard_sites().len(), COUNT);
    assert_eq!(backend.take_target_transfers().len(), COUNT - 1);
    assert!(backend.set_query_site_limit(COUNT + 1).is_err());
    assert!(
        backend
            .prepare(
                "another-capture",
                &candidates(0, 1),
                &options,
                snapshot.metadata.platform.decoder_target()
            )
            .unwrap_err()
            .to_string()
            .contains("snapshot/target")
    );
    backend.finish().unwrap();

    // The immutable reader selects its aggregate limit from the explicit
    // preparation budget, independently of each helper's fixed 8,192 sites.
    let query = AnalysisQuery {
        entry_points: (0..COUNT).map(|index| START + index as u64).collect(),
        slice_seeds: AddressSet::new(),
    };
    let limits = PrepareLimits {
        max_starts: COUNT,
        max_candidates: COUNT,
        max_prefix_bytes: COUNT * 15,
        max_decoder_batches: COUNT,
        batch_size: 256,
    };
    let prepared = snapshot
        .prepare_with_bap(&query, &decoder, &config, &options, limits)
        .unwrap();
    assert_eq!(prepared.materialization.attempted.len(), COUNT);
    assert_eq!(
        prepared.prepared.request.snapshot_id,
        snapshot.metadata.snapshot_id
    );
    assert_eq!(prepared.prepared.request.decodable.len(), COUNT);

    // The public direct-backend default still rejects the aggregate 8,193rd
    // site before rotating; explicit smaller budgets also remain effective.
    let mut direct = crate::bap::Backend::new(config.clone(), &decoder).unwrap();
    for start in (0..8192).step_by(256) {
        direct
            .prepare(
                &snapshot.metadata.snapshot_id,
                &candidates(start, 256),
                &options,
                snapshot.metadata.platform.decoder_target(),
            )
            .unwrap();
    }
    assert!(
        direct
            .prepare(
                &snapshot.metadata.snapshot_id,
                &candidates(8192, 1),
                &options,
                snapshot.metadata.platform.decoder_target()
            )
            .unwrap_err()
            .to_string()
            .contains("query site budget exceeded")
    );
    assert_eq!(direct.metrics().helper_processes, 1);
    direct.finish().unwrap();
    let mut limited = crate::bap::Backend::new(config, &decoder).unwrap();
    limited.set_query_site_limit(3).unwrap();
    limited
        .prepare(
            &snapshot.metadata.snapshot_id,
            &candidates(0, 2),
            &options,
            snapshot.metadata.platform.decoder_target(),
        )
        .unwrap();
    assert!(
        limited
            .prepare(
                &snapshot.metadata.snapshot_id,
                &candidates(2, 2),
                &options,
                snapshot.metadata.platform.decoder_target()
            )
            .unwrap_err()
            .to_string()
            .contains("query site budget exceeded")
    );
    assert_eq!(limited.metrics().helper_processes, 1);
    limited.finish().unwrap();
}

/// Non-followed call targets and unattempted seeds become represented Stop
/// endpoints in the final request. They must already belong to the graph to
/// which a whole-dispatch loop receipt is bound during resolver closure.
#[test]
fn loop_publication_binds_unattempted_seed_and_nonlocal_call_endpoints() {
    use crate::bap::target_resolution as resolver;
    let fixture: Value =
        serde_json::from_str(include_str!("../bap/fixtures/loop-closure/dump-da09.json")).unwrap();
    let mut sites = BTreeMap::new();
    let mut transfers = BTreeMap::new();
    for source in fixture["sources"].as_array().unwrap() {
        let site = parse_target_address(source["site"].as_str().unwrap()).unwrap();
        let row = &source["candidate_instruction"];
        let addresses = |field: &str| {
            row[field]
                .as_array()
                .unwrap()
                .iter()
                .map(|a| parse_target_address(a.as_str().unwrap()).unwrap())
                .collect()
        };
        let locations = |field: &str| {
            row[field]
                .as_array()
                .unwrap()
                .iter()
                .map(|a| a.as_str().unwrap().to_owned())
                .collect()
        };
        let instruction = Instruction {
            kind: match row["kind"].as_str().unwrap() {
                "ordinary" => InstructionKind::Ordinary,
                "conditional" => InstructionKind::Conditional,
                "jump" => InstructionKind::Jump,
                "indirect" => InstructionKind::Indirect,
                other => panic!("unexpected fixture kind {other}"),
            },
            complete: row["targets_complete"].as_bool().unwrap(),
            fall: addresses("fall"),
            targets: addresses("targets"),
            uses: locations("uses"),
            may_defs: locations("may_defs"),
            must_defs: locations("must_defs"),
        };
        let bil: Vec<Stmt> = serde_json::from_str(source["ast"].as_str().unwrap()).unwrap();
        let bytes =
            crate::investigation::frame_unwind::unhex(source["bytes_hex"].as_str().unwrap())
                .unwrap();
        transfers.insert(site, resolver::extract(&bil, site, &bytes).unwrap());
        sites.insert(
            site,
            PreparedSite {
                instruction,
                evidence: placeholder(),
                gaps: Vec::new(),
                decodable: true,
                complete_capture: true,
            },
        );
    }
    let root = 0x00007ff774300000;
    let call_target = 0x00007ff775000000;
    let unattempted_seed = 0xdead0000;
    let reset = 0x00007ff77440d9e2;
    sites.insert(
        root,
        PreparedSite {
            instruction: Instruction {
                kind: InstructionKind::Call,
                fall: [reset].into(),
                targets: [call_target].into(),
                complete: true,
                ..Instruction::default()
            },
            evidence: placeholder(),
            gaps: Vec::new(),
            decodable: true,
            complete_capture: true,
        },
    );
    let mut referenced: AddressSet = sites.keys().copied().collect();
    for site in sites.values() {
        referenced.extend(edges(&site.instruction).into_iter().map(|(to, _)| to));
    }
    // Model already-attempted unavailable local endpoints. Only the seed and
    // nonlocal call target deliberately have no prepared site.
    for address in referenced.clone() {
        if address != call_target {
            sites.entry(address).or_insert_with(|| PreparedSite {
                instruction: Instruction::default(),
                evidence: placeholder(),
                gaps: Vec::new(),
                decodable: false,
                complete_capture: false,
            });
        }
    }
    referenced.insert(unattempted_seed);
    let roots: AddressSet = [root].into();
    let query = AnalysisQuery {
        entry_points: roots.clone(),
        slice_seeds: [unattempted_seed].into(),
    };
    let mut materialization = MaterializationReport {
        entry_points: roots.clone(),
        slice_seeds: query.slice_seeds.clone(),
        referenced,
        attempted: sites.keys().copied().collect(),
        limits: PrepareLimits::default(),
        ..MaterializationReport::default()
    };
    let data: Vec<_> = fixture["table_reads"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| {
            (
                parse_target_address(r["address"].as_str().unwrap()).unwrap(),
                crate::investigation::frame_unwind::unhex(r["bytes_hex"].as_str().unwrap())
                    .unwrap(),
            )
        })
        .collect();
    let ranges: Vec<_> = data.iter().map(|(a, b)| (*a, b.as_slice())).collect();
    let mut dump = common::Dump::new(false);
    dump.memory64(&ranges);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let limits = resolver::Limits {
        max_steps: 2_000_000,
        max_path_steps: 512,
        max_rounds: 64,
        max_elapsed_ms: 30_000,
        ..Default::default()
    };
    let mut coordinator = TargetResolutionCoordinator::new(&limits);
    coordinator.candidate_mode = true;
    coordinator.transfers = transfers;
    let mut pending = AddressSet::new();
    let mut epoch = 0;
    let mut fingerprint = None;
    advance_candidate_epoch(
        candidate_fingerprint(&sites, &BTreeMap::new(), Some(&coordinator.transfers)).unwrap(),
        &mut fingerprint,
        &mut epoch,
    )
    .unwrap();
    assert!(
        !coordinator
            .advance(
                &snapshot,
                &roots,
                &mut sites,
                &mut pending,
                &mut materialization
            )
            .unwrap()
    );
    assert!(pending.is_empty());
    advance_candidate_epoch(
        candidate_fingerprint(&sites, &BTreeMap::new(), Some(&coordinator.transfers)).unwrap(),
        &mut fingerprint,
        &mut epoch,
    )
    .unwrap();
    assert_eq!(
        epoch, 2,
        "completeness-only changes advance the candidate epoch"
    );
    assert!(
        coordinator
            .advance(
                &snapshot,
                &roots,
                &mut sites,
                &mut pending,
                &mut materialization
            )
            .unwrap()
    );
    let final_request = request_from_sites(
        &snapshot.metadata.snapshot_id,
        &query,
        &materialization.referenced,
        &PreparationOptions::default(),
        &sites,
    );
    let report = coordinator.report.as_ref().unwrap();
    let row = report
        .resolutions
        .iter()
        .find(|r| r.site == "0x00007ff77440da09")
        .unwrap();
    assert!(row.complete, "{:?}", row.unresolved);
    let Some(resolver::CoverageEvidence::InductiveDispatch { receipt }) = &row.coverage else {
        panic!("loop induction absent")
    };
    let graph_digest =
        resolver::report_graph_digest(report, &final_request.instructions, &roots).unwrap();
    assert_eq!(report.graph_sha256, graph_digest);
    assert_eq!(receipt.graph_sha256, graph_digest);
    assert_eq!(receipt.region.len(), 9);
    assert_eq!(row.targets.len(), 4);
    resolver::validate(report, &final_request.instructions, &roots).unwrap();
    for endpoint in [unattempted_seed, call_target] {
        assert_eq!(
            final_request.instructions[&endpoint].kind,
            InstructionKind::Stop
        );
        assert!(!materialization.attempted.contains(&endpoint));
        assert!(!final_request.decodable.contains(&endpoint));
        assert!(!final_request.entry_points.contains(&endpoint));
    }
    assert_eq!(final_request.entry_points, roots);
}

fn captured_terminal_fixture(
    captured_byte: u8,
    include_receipt: bool,
) -> Result<FilePreparedAnalysis, PreparationError> {
    captured_terminal_case_fixture("int3", Some(captured_byte), include_receipt)
}
fn captured_terminal_case_fixture(
    name: &str,
    override_first_byte: Option<u8>,
    include_receipt: bool,
) -> Result<FilePreparedAnalysis, PreparationError> {
    let captured: Value = serde_json::from_str(include_str!(
        "../bap/fixtures/caller-coverage/dump-four-shapes.json"
    ))
    .unwrap();
    let raw: Value = serde_json::from_str(include_str!(
        "../bap/fixtures/caller-coverage/raw-bap-observations.json"
    ))
    .unwrap();
    let case = captured["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["id"] == name)
        .unwrap();
    let lift: crate::bap::ast::Lift = serde_json::from_value(
        raw["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["id"] == name)
            .unwrap()["raw_bap"]
            .clone(),
    )
    .unwrap();
    let va = parse_target_address(case["site"].as_str().unwrap()).unwrap();
    let record = case["llvm_and_preparation"]["decoder_record"]
        .as_str()
        .unwrap()
        .replace(" unsupported 1 - -", " ok 1 stop -");
    let ast = serde_json::to_string(&lift.bil).unwrap();
    let full_bytes = crate::investigation::frame_unwind::unhex(
        case["llvm_and_preparation"]["bytes_hex"].as_str().unwrap(),
    )
    .unwrap();
    let receipt = crate::bap::terminal_control::recognize(va, &full_bytes, &ast, &lift, &record)
        .unwrap()
        .unwrap();
    let mut dump = common::Dump::new(false);
    let mut captured_bytes = full_bytes.clone();
    if let Some(first) = override_first_byte {
        captured_bytes[0] = first;
    }
    dump.memory64(&[(va, captured_bytes.as_slice())]);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let query = AnalysisQuery {
        entry_points: [va].into(),
        slice_seeds: AddressSet::new(),
    };
    let limits = PrepareLimits::default();
    let activation = guard::Activation {
        thread_id: 17,
        frame_activation: "terminal-capture-fixture".into(),
    };
    let roots = vec![guard::Root {
        site: format!("0x{va:016x}"),
        function_entry: false,
        anchor_sha256: "1".repeat(64),
    }];
    let scope = guard_query_scope(
        &snapshot.metadata.snapshot_id,
        &query,
        &limits,
        &activation,
        &roots,
    )
    .unwrap();
    let setup = GuardPreparation {
        limits: guard::Limits::default(),
        activation,
        roots,
        premises: vec![],
        query_scope_sha256: scope,
        producer: Some(guard::Producer {
            helper_sha256: "3".repeat(64),
            runtime_sha256: "4".repeat(64),
            decoder_sha256: "5".repeat(64),
            projection: guard::PRODUCER_PROFILE.into(),
        }),
    };
    snapshot.prepare_materialization_with_terminals(
        &query,
        &PreparationOptions::default(),
        limits,
        None,
        Some(&setup),
        |_, candidates, options, _| {
            assert_eq!(
                candidates.keys().copied().collect::<AddressSet>(),
                [va].into()
            );
            let instruction = Instruction {
                kind: InstructionKind::Stop,
                complete: include_receipt,
                uses: options.catalogue.locations(),
                may_defs: options.catalogue.locations(),
                must_defs: LocationSet::new(),
                fall: AddressSet::new(),
                targets: AddressSet::new(),
            };
            let source = guard::CandidateSite {
                site: format!("0x{va:016x}"),
                bytes_hex: receipt.bytes_hex.clone(),
                ast: ast.clone(),
                control: guard::CandidateControl::from_instruction(&instruction),
                opaque: true,
            };
            let mut evidence = placeholder();
            evidence.bytes = full_bytes.clone();
            evidence.length = u8::try_from(full_bytes.len()).unwrap();
            evidence.source = ByteSource::Captured;
            evidence.opcode = Some(receipt.reference.opcode.clone());
            evidence.quality = EffectQuality::Opaque;
            evidence.control = Some(InstructionKind::Stop);
            evidence.decoder_control = Some(InstructionKind::Stop);
            evidence.decoder_record = Some(record.clone());
            evidence.rule = include_receipt.then(|| "captured-normal-terminal/v1".into());
            evidence.semantic = Some(SemanticEvidence {
                backend: "bap-x86-legacy".into(),
                helper_sha256: "3".repeat(64),
                runtime_sha256: "4".repeat(64),
                projection: guard::PRODUCER_PROFILE.into(),
                status: if include_receipt {
                    "normal-flow-terminal"
                } else {
                    "opaque-unsupported"
                }
                .into(),
                ast_sha256: Some(crate::reports::sha256(ast.as_bytes())),
                fallback: None,
                gaps: if include_receipt {
                    vec![
                        "exception-exit".into(),
                        "exception-resumption-outside-local-scope".into(),
                        "unsupported-exception-effects".into(),
                    ]
                } else {
                    vec!["unmodeled BIL control/special/loop semantics".into()]
                },
                memory_accesses: vec![],
            });
            let batch = PreparedBatch {
                sites: [(
                    va,
                    PreparedSite {
                        instruction,
                        evidence,
                        gaps: vec![],
                        decodable: include_receipt,
                        complete_capture: true,
                    },
                )]
                .into(),
                identity: PreparationIdentity {
                    target: "x86_64-pc-windows-msvc".into(),
                    decoder: "independent terminal fixture".into(),
                    protocol: 1,
                    ruleset: guard::PRODUCER_PROFILE.into(),
                    catalogue: "gpr-bytes-status-df-memory-other-v1".into(),
                },
            };
            Ok((
                batch,
                BTreeMap::new(),
                [(va, source)].into(),
                if include_receipt {
                    [(va, receipt.clone())].into()
                } else {
                    BTreeMap::new()
                },
            ))
        },
    )
}
#[test]
fn captured_terminals_close_only_checked_normal_flow_and_keep_opaque_effects() {
    let prepared = captured_terminal_fixture(0xcc, true).unwrap();
    prepared.validate_guard_admission().unwrap();
    let guard = prepared.guard_admission().unwrap();
    assert!(guard.input.barriers.is_empty());
    assert_eq!(guard.input.normal_flow.as_ref().unwrap().terminals.len(), 1);
    assert_eq!(
        guard::normal_flow_scope(guard),
        Some("local-normal-completion/v1")
    );
    let va = prepared
        .prepared
        .request
        .entry_points
        .iter()
        .copied()
        .next()
        .unwrap();
    let instruction = &prepared.prepared.request.instructions[&va];
    assert_eq!(instruction.kind, InstructionKind::Stop);
    assert!(
        instruction.fall.is_empty()
            && instruction.targets.is_empty()
            && instruction.must_defs.is_empty()
    );
    assert_eq!(instruction.uses, prepared.prepared.request.locations);
    assert_eq!(instruction.may_defs, prepared.prepared.request.locations);
    let analyzed = crate::analyze(prepared.prepared.request.clone()).unwrap();
    assert!(analyzed.state.decoded.contains(&va));
    assert!(analyzed.state.obligations.is_empty());
    assert!(analyzed.state.edges.is_empty());
    let mut forged = prepared.clone();
    forged
        .prepared
        .request
        .instructions
        .get_mut(&va)
        .unwrap()
        .may_defs
        .clear();
    assert!(forged.validate_guard_admission().is_err());
    let missing = captured_terminal_fixture(0xcc, false).unwrap();
    assert_eq!(
        missing.guard_admission().unwrap().input.barriers,
        vec![format!("0x{va:016x}")]
    );
    assert_eq!(
        missing.guard_admission().unwrap().stop.as_deref(),
        Some("candidate-coverage-incomplete")
    );
    assert!(
        captured_terminal_fixture(0x90, true).is_err(),
        "terminal evidence cannot replace captured bytes"
    );
}
#[test]
fn terminal_receipt_changes_advance_epoch_even_without_control_changes() {
    let prepared = captured_terminal_fixture(0xcc, true).unwrap();
    let receipt = prepared
        .guard_admission()
        .unwrap()
        .input
        .normal_flow
        .as_ref()
        .unwrap()
        .terminals[0]
        .clone();
    let va = parse_target_address(&receipt.site).unwrap();
    let mut terminals: BTreeMap<_, _> = [(va, receipt)].into();
    let mut previous = None;
    let mut epoch = 0;
    advance_candidate_epoch(
        candidate_fingerprint_with_terminals(&BTreeMap::new(), &BTreeMap::new(), None, &terminals)
            .unwrap(),
        &mut previous,
        &mut epoch,
    )
    .unwrap();
    terminals
        .get_mut(&va)
        .unwrap()
        .resumption
        .push_str("changed");
    advance_candidate_epoch(
        candidate_fingerprint_with_terminals(&BTreeMap::new(), &BTreeMap::new(), None, &terminals)
            .unwrap(),
        &mut previous,
        &mut epoch,
    )
    .unwrap();
    assert_eq!(epoch, 2);
}

#[test]
fn terminal_guard_only_reports_preserve_sources_scope_and_native_input() {
    for name in ["int3", "ud2", "ud1"] {
        let prepared = captured_terminal_case_fixture(name, None, true).unwrap();
        let completed = crate::CompletedAnalysis::from_analyzer(
            crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
        );
        let bound = crate::input::investigation::bind_investigation(&prepared, &completed).unwrap();
        let site = prepared
            .prepared
            .request
            .entry_points
            .iter()
            .copied()
            .next()
            .unwrap();
        let explanation = crate::investigation::explain_fault_address(
            &bound,
            crate::investigation::FaultAddressQuestion {
                site,
                memory_access: 0,
            },
            Default::default(),
        )
        .unwrap();
        assert_eq!(explanation.schema, "ariadne.fault-address-explanation/v5");
        assert_eq!(explanation.guard_sources.as_ref().unwrap().len(), 1);
        let encoded = crate::reports::encode_explanation(&explanation).unwrap();
        assert_eq!(
            crate::reports::decode_explanation(&serde_json::to_vec(&encoded).unwrap()).unwrap(),
            explanation
        );
        let mut stripped = encoded.clone();
        stripped["guard_admission"]["input"]
            .as_object_mut()
            .unwrap()
            .remove("normal_flow");
        assert!(
            crate::reports::decode_explanation(&serde_json::to_vec(&stripped).unwrap()).is_err()
        );
        let saved = crate::input::report::render_bound(
            &prepared,
            &completed,
            crate::input::report::ReportFormat::Json,
            false,
        )
        .unwrap();
        let value: Value = serde_json::from_str(&saved).unwrap();
        assert_eq!(value["schema"], "ariadne-minidump-report-v6");
        assert!(value["capture_sources"].is_array());
        assert!(value["normalized"].is_object());
        for format in [
            crate::input::report::ReportFormat::Text,
            crate::input::report::ReportFormat::Dot,
        ] {
            let saved =
                crate::input::report::render_bound(&prepared, &completed, format, false).unwrap();
            assert!(saved.contains("exception-resumption-outside-local-scope"));
            assert!(saved.contains("capture_sources"));
        }
        let wire =
            crate::bap::core_adapter::NativeAnalyzer::capture_wire_for_test(&prepared).unwrap();
        assert_eq!(wire["guard_admission"]["profile"], guard::PROFILE);
        if let Some(directory) = std::env::var_os("ARIADNE_CALLER_WIRE_DIR") {
            let directory = std::path::PathBuf::from(directory);
            std::fs::create_dir_all(&directory).unwrap();
            std::fs::write(
                directory.join(format!("{name}-guarded-wire.json")),
                serde_json::to_vec_pretty(&wire).unwrap(),
            )
            .unwrap();
        }
    }
}
