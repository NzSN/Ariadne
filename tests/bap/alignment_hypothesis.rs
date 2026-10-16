use super::*;
use crate::bap::ast::{Expr, Stmt, Var};
use crate::bap::guard_admission::{
    Activation, CandidateControl, CandidateSite, ControlKind, GuardInput, NormalFlowEvidence,
    Premise, PremiseOrigin, Producer, Root,
};

fn hex(a: u64) -> String {
    format!("0x{a:016x}")
}
fn hash(s: &str) -> String {
    crate::reports::sha256(s.as_bytes())
}
fn var(name: &str, width: usize, virtual_: bool) -> Var {
    Var {
        name: name.into(),
        index: 0,
        virtual_,
        width,
        type_: if width == 0 { "mem" } else { "imm" }.into(),
    }
}
fn read(name: &str) -> Expr {
    Expr::Var {
        var: var(name, 64, false),
    }
}
fn integer(n: u64) -> Expr {
    Expr::Int {
        value: format!("0x{n:x}:64u"),
    }
}
fn arithmetic(op: i32, n: u64) -> Vec<Stmt> {
    vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: Expr::Binop {
            op,
            lhs: Box::new(read("RSP")),
            rhs: Box::new(integer(n)),
        },
    }]
}
fn control(kind: ControlKind, fall: &[u64], targets: &[u64]) -> CandidateControl {
    CandidateControl {
        kind,
        fall: fall.iter().map(|a| hex(*a)).collect(),
        targets: targets.iter().map(|a| hex(*a)).collect(),
        complete: true,
    }
}
fn site(va: u64, bil: &[Stmt], kind: ControlKind, fall: &[u64], targets: &[u64]) -> CandidateSite {
    CandidateSite {
        site: hex(va),
        bytes_hex: "90".into(),
        ast: serde_json::to_string(bil).unwrap(),
        control: control(kind, fall, targets),
        opaque: false,
    }
}
fn movaps(va: u64) -> CandidateSite {
    CandidateSite {
        site: hex(va),
        bytes_hex: "0f29b42440020000".into(),
        ast: include_str!("fixtures/vector/movaps-bil.json").into(),
        control: control(ControlKind::Ordinary, &[va + 8], &[]),
        opaque: true,
    }
}
fn terminal(va: u64) -> CandidateSite {
    let mut s = site(va, &[], ControlKind::Return, &[], &[]);
    s.opaque = true;
    s.bytes_hex = "c3".into();
    s
}
fn input(sites: Vec<CandidateSite>, roots: &[u64]) -> GuardInput {
    GuardInput {
        snapshot: "guard-fixture-snapshot".into(),
        artifact_sha256: hash("immutable-capture"),
        query_scope_sha256: hash("rooted-query"),
        preparation_sha256: hash("actual-prepare-options"),
        platform: "windows-amd64".into(),
        roots: roots
            .iter()
            .map(|a| Root {
                site: hex(*a),
                function_entry: true,
                anchor_sha256: hash(&format!("entry:{a}")),
            })
            .collect(),
        seeds: Vec::new(),
        activation: Activation {
            thread_id: 42,
            frame_activation: "chain:frame:stack".into(),
        },
        premises: Vec::new(),
        producer: Producer {
            helper_sha256: hash("pinned-helper"),
            runtime_sha256: hash("pinned-runtime"),
            decoder_sha256: hash("independent-decoder"),
            projection: guard::PRODUCER_PROFILE.into(),
        },
        policy: guard::PROFILE.into(),
        model_version: guard::MODEL_VERSION.into(),
        model_sha256: guard::model_identity(),
        limits: guard::Limits::default(),
        candidate_epoch: 0,
        closure_complete: true,
        barriers: Vec::new(),
        sites,
        normal_flow: Some(NormalFlowEvidence::empty()),
    }
}
fn observe(input: &mut GuardInput, point: u64, residue: u8) {
    input.premises.push(Premise {
        origin: PremiseOrigin::CapturedRegister,
        snapshot: input.snapshot.clone(),
        query_scope_sha256: input.query_scope_sha256.clone(),
        root: hex(point),
        point: hex(point),
        activation: input.activation.clone(),
        policy: "captured-register-at-root/v1".into(),
        evidence_sha256: hash(&format!("captured-rsp:{point}:{residue}")),
        rsp_residues: 1 << residue,
        rsp_value: Some(hex(0x8000 + u64::from(residue))),
    });
}
fn direct(residue: Option<u8>) -> GuardInput {
    let mut i = input(vec![movaps(0x2000), terminal(0x2008)], &[0x2000]);
    if let Some(r) = residue {
        observe(&mut i, 0x2000, r);
    }
    i
}
fn load_guard(va: u64) -> CandidateSite {
    let fixture: Value = serde_json::from_str(include_str!(
        "fixtures/caller-coverage/dump-four-shapes.json"
    ))
    .unwrap();
    let load = fixture["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["id"] == "movaps-load")
        .unwrap();
    CandidateSite {
        site: hex(va),
        bytes_hex: load["bap_original"]["bytes_hex"].as_str().unwrap().into(),
        ast: load["bap_original"]["ast"].as_str().unwrap().into(),
        control: control(ControlKind::Ordinary, &[va + 8], &[]),
        opaque: true,
    }
}

fn prepare(input: GuardInput) -> (AnalysisRequest, guard::Report, BTreeMap<String, String>) {
    let mut baseline = guard::certify_guards(&input).unwrap();
    let locations = crate::effects::Catalogue.locations();
    let mut base = AnalysisRequest {
        snapshot_id: input.snapshot.clone(),
        locations: locations.clone(),
        input_kind: crate::InputKind::Dump,
        entry_points: input
            .roots
            .iter()
            .map(|root| crate::bap::core_adapter::address(&root.site).unwrap())
            .collect(),
        slice_seeds: input
            .seeds
            .iter()
            .map(|site| crate::bap::core_adapter::address(site).unwrap())
            .collect(),
        ..AnalysisRequest::default()
    };
    let mut decoder = BTreeMap::new();
    for source in &input.sites {
        let site = crate::bap::core_adapter::address(&source.site).unwrap();
        let bytes = crate::investigation::frame_unwind::unhex(&source.bytes_hex).unwrap();
        let kind = match source.control.kind {
            ControlKind::Ordinary => InstructionKind::Ordinary,
            ControlKind::Conditional => InstructionKind::Conditional,
            ControlKind::Jump => InstructionKind::Jump,
            ControlKind::Indirect => InstructionKind::Indirect,
            ControlKind::Call => InstructionKind::Call,
            ControlKind::Return => InstructionKind::Return,
            ControlKind::Stop => InstructionKind::Stop,
        };
        let mut instruction = Instruction {
            kind,
            fall: source
                .control
                .fall
                .iter()
                .map(|site| crate::bap::core_adapter::address(site).unwrap())
                .collect(),
            targets: source
                .control
                .targets
                .iter()
                .map(|site| crate::bap::core_adapter::address(site).unwrap())
                .collect(),
            complete: source.control.complete,
            uses: locations.clone(),
            may_defs: locations.clone(),
            must_defs: Default::default(),
        };
        base.addresses.insert(site);
        base.captured.insert(site);
        base.decodable.insert(site);
        if guard::recognize_pending_for_input(&input, source)
            .unwrap()
            .is_some()
        {
            let opcode = if bytes.contains(&0x29) {
                "MOVAPSmr"
            } else {
                "MOVAPSrm"
            };
            decoder.insert(
                source.site.clone(),
                format!("v2 {opcode} 0 0 0 0 0 {site} ok {} ordinary -", bytes.len()),
            );
            if let Some(normal) = baseline.normal_selection(site) {
                instruction =
                    crate::bap::Backend::guard_normal_projection(normal, opcode, &bytes, site)
                        .unwrap()
                        .instruction;
            } else {
                instruction = Instruction {
                    kind: InstructionKind::Stop,
                    uses: locations.clone(),
                    may_defs: locations.clone(),
                    ..Instruction::default()
                };
                base.decodable.remove(&site);
            }
        }
        base.instructions.insert(site, instruction);
    }
    let referenced: Vec<_> = base
        .instructions
        .values()
        .flat_map(|instruction| instruction.fall.union(&instruction.targets).copied())
        .collect();
    for target in referenced {
        base.addresses.insert(target);
        base.instructions.entry(target).or_default();
    }
    base.validate().unwrap();
    guard::bind_final_request(
        &input,
        &mut baseline,
        &json_hash(&crate::bap::core_adapter::encode_request(&base).unwrap()).unwrap(),
    )
    .unwrap();
    (base, baseline, decoder)
}
fn limits() -> guard::Limits {
    guard::Limits {
        max_elapsed_ms: 60_000,
        ..guard::Limits::default()
    }
}
fn reseal(report: &mut Report) {
    report.binding_sha256 = binding(report).unwrap();
}

#[test]
fn unknown_becomes_explicitly_assumed_and_baseline_remains_unchanged() {
    let (base, baseline, decoder) = prepare(direct(None));
    assert_eq!(baseline.guards[0].verdict, guard::Verdict::Unknown);
    let original = baseline.clone();
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(baseline, original);
    assert!(!base.decodable.contains(&0x2000));
    assert!(conditional.decodable.contains(&0x2000));
    assert_eq!(report.decisions[0].basis, Basis::Assumed);
    assert_eq!(
        report
            .facts
            .iter()
            .find(|fact| fact.site == hex(0x2000))
            .unwrap()
            .incoming,
        guard::TOP
    );
    assert_eq!(
        report
            .facts
            .iter()
            .find(|fact| fact.site == hex(0x2000))
            .unwrap()
            .residues,
        1
    );
    assert_eq!(conditional.entry_points, base.entry_points);
    assert_eq!(conditional.slice_seeds, base.slice_seeds);
    validate(&report, &baseline, &decoder, &conditional, &limits()).unwrap();
    assert_eq!(base_request(&report).unwrap(), base);
    assert_ne!(
        analysis_id(&report).unwrap(),
        guard::analysis_id(&baseline).unwrap()
    );
}

#[test]
fn proved_and_empty_conditional_branches_do_not_invent_reachability() {
    for (residue, basis, verdict) in [
        (0, Basis::Proved, guard::Verdict::Aligned),
        (8, Basis::Unreachable, guard::Verdict::Unreached),
    ] {
        let (base, baseline, decoder) = prepare(direct(Some(residue)));
        let (conditional, report) =
            certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
        assert_eq!(report.decisions[0].basis, basis);
        assert_eq!(report.decisions[0].verdict, verdict);
        assert_eq!(conditional.decodable.contains(&0x2000), residue == 0);
        validate(&report, &baseline, &decoder, &conditional, &limits()).unwrap();
    }
    let input = input(
        vec![terminal(0x1000), movaps(0x2000), terminal(0x2008)],
        &[0x1000],
    );
    let (base, baseline, decoder) = prepare(input);
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(report.decisions[0].basis, Basis::Unreachable);
    assert_eq!(conditional.entry_points, [0x1000].into());
    assert!(!conditional.decodable.contains(&0x2000));
}

#[test]
fn load_and_signed_displacement_bind_the_exact_reviewed_predicate() {
    let mut load_input = direct(None);
    load_input.sites[0] = load_guard(0x2000);
    let (base, baseline, decoder) = prepare(load_input);
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(report.decisions[0].basis, Basis::Assumed);
    assert!(
        conditional.instructions[&0x2000]
            .uses
            .contains("memory:any")
    );
    let mut source = movaps(0x3000);
    source.bytes_hex = "0f297424f8".into();
    source.ast = source.ast.replace("0x240:64u", "0xfffffffffffffff8:64u");
    source.control.fall = vec![hex(0x3005)];
    let (base, baseline, decoder) = prepare(input(vec![source, terminal(0x3005)], &[0x3000]));
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x3000], &limits()).unwrap();
    assert_eq!(report.hypotheses[0].displacement, -8);
    assert_eq!(report.hypotheses[0].rsp_residues, 1 << 8);
    assert_eq!(report.decisions[0].address_residues, 1);
    validate(&report, &baseline, &decoder, &conditional, &limits()).unwrap();
}

#[test]
fn cycle_reapplies_hypothesis_and_bypass_or_clobber_stays_unknown() {
    let mut looped = direct(Some(0));
    let mut back = site(
        0x2008,
        &arithmetic(18, 8),
        ControlKind::Jump,
        &[],
        &[0x2000],
    );
    back.bytes_hex = "4883c408".into();
    looped.sites[1] = back;
    let (base, baseline, decoder) = prepare(looped);
    assert_eq!(baseline.guards[0].input_residues, 1 | (1 << 8));
    let (_, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(report.decisions[0].input_residues, 1);
    assert_eq!(
        report
            .facts
            .iter()
            .find(|fact| fact.site == hex(0x2000))
            .unwrap()
            .incoming,
        1 | (1 << 8)
    );
    let identity = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: read("RSP"),
    }];
    let mut merge = input(
        vec![
            site(
                0x1000,
                &identity,
                ControlKind::Conditional,
                &[0x2000],
                &[0x3000],
            ),
            movaps(0x2000),
            site(0x2008, &identity, ControlKind::Jump, &[], &[0x3000]),
            movaps(0x3000),
            terminal(0x3008),
        ],
        &[0x1000],
    );
    let (base, baseline, decoder) = prepare(merge.clone());
    let (_, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(
        report
            .decisions
            .iter()
            .find(|decision| decision.site == hex(0x3000))
            .unwrap()
            .verdict,
        guard::Verdict::Unknown
    );
    merge.sites[0].control.kind = ControlKind::Ordinary;
    merge.sites[0].control.targets.clear();
    merge.sites[2].opaque = true;
    let (base, baseline, decoder) = prepare(merge);
    let (_, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert_eq!(
        report
            .decisions
            .iter()
            .find(|decision| decision.site == hex(0x3000))
            .unwrap()
            .verdict,
        guard::Verdict::Unknown
    );
}

#[test]
fn zero_open_and_each_closure_epoch_boundary_allow_no_assumed_edge() {
    let (base, baseline, decoder) = prepare(direct(None));
    for limit in [
        guard::Limits {
            max_transfer_evaluations: 0,
            ..limits()
        },
        guard::Limits {
            max_residue_updates: 0,
            ..limits()
        },
        guard::Limits {
            max_elapsed_ms: 0,
            ..limits()
        },
        guard::Limits {
            max_edges: 0,
            ..limits()
        },
    ] {
        let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limit).unwrap();
        assert!(report.stop.is_some());
        assert_eq!(report.decisions[0].basis, Basis::Unknown);
        assert!(!conditional.decodable.contains(&0x2000));
        validate(&report, &baseline, &decoder, &conditional, &limit).unwrap();
    }
    let mut epoch = direct(None);
    epoch.candidate_epoch = 1;
    let (base, baseline, decoder) = prepare(epoch);
    for cap in [0usize, 1, 2] {
        let (conditional, report) = certify(
            &base,
            &baseline,
            &decoder,
            &[0x2000],
            &guard::Limits {
                max_closure_rounds: cap,
                ..limits()
            },
        )
        .unwrap();
        assert_eq!(conditional.decodable.contains(&0x2000), cap > 1);
        assert_eq!(report.stop.is_none(), cap > 1);
    }
    let mut open = direct(None);
    open.closure_complete = false;
    let (base, baseline, decoder) = prepare(open);
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    assert!(report.stop.is_some());
    assert!(!conditional.decodable.contains(&0x2000));
}

#[test]
fn rehashed_hypotheses_scope_source_facts_and_final_request_are_rechecked() {
    let (base, baseline, decoder) = prepare(direct(None));
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    for field in [
        "snapshot",
        "artifact_sha256",
        "query_scope_sha256",
        "root",
        "point",
        "bytes_hex",
        "original_ast_sha256",
        "pending_relation_sha256",
        "decoder_record_sha256",
        "candidate_epoch",
        "activation",
    ] {
        let mut raw = serde_json::to_value(&report).unwrap();
        let value = &mut raw["hypotheses"][0][field];
        *value = match field {
            "activation" => serde_json::json!({"thread_id":99,"frame_activation":"other"}),
            "candidate_epoch" => serde_json::json!(99),
            "point" | "root" => serde_json::json!(hex(0x2008)),
            _ => serde_json::json!("changed"),
        };
        let mut changed: Report = serde_json::from_value(raw).unwrap();
        reseal(&mut changed);
        assert!(
            validate(&changed, &baseline, &decoder, &conditional, &limits()).is_err(),
            "changed {field}"
        );
    }
    let mut changed = report.clone();
    changed.hypotheses.clear();
    reseal(&mut changed);
    assert!(validate(&changed, &baseline, &decoder, &conditional, &limits()).is_err());
    let mut changed = report.clone();
    changed.facts[0].residues = guard::TOP;
    reseal(&mut changed);
    assert!(validate(&changed, &baseline, &decoder, &conditional, &limits()).is_err());
    let mut changed = report.clone();
    changed.decisions[0].basis = Basis::Proved;
    reseal(&mut changed);
    assert!(validate(&changed, &baseline, &decoder, &conditional, &limits()).is_err());
    let mut final_request = conditional.clone();
    final_request
        .instructions
        .get_mut(&0x2000)
        .unwrap()
        .fall
        .clear();
    assert!(validate(&report, &baseline, &decoder, &final_request, &limits()).is_err());
    assert!(certify(&base, &baseline, &decoder, &[0x2000, 0x2000], &limits()).is_err());
    assert!(certify(&base, &baseline, &decoder, &[0x2008], &limits()).is_err());
    let mut missing = decoder.clone();
    missing.clear();
    assert!(certify(&base, &baseline, &missing, &[0x2000], &limits()).is_err());
    assert!(
        validate(
            &report,
            &baseline,
            &decoder,
            &conditional,
            &guard::Limits {
                max_transfer_evaluations: 0,
                ..limits()
            }
        )
        .is_err()
    );
}

#[test]
fn removing_captured_membership_is_rejected_after_baseline_proof_rebinding() {
    let (mut base, baseline, decoder) = prepare(direct(None));
    base.captured.remove(&0x2000);
    let mut rebound = guard::certify_guards(&baseline.input).unwrap();
    let request_hash =
        json_hash(&crate::bap::core_adapter::encode_request(&base).unwrap()).unwrap();
    guard::bind_final_request(&baseline.input, &mut rebound, &request_hash).unwrap();
    guard::validate_final_request(&baseline.input, &rebound, &request_hash).unwrap();
    assert!(certify(&base, &rebound, &decoder, &[0x2000], &limits()).is_err());
}

#[test]
fn host_evidence_and_cardinality_caps_precede_report_hashing() {
    let (base, baseline, decoder) = prepare(direct(None));
    let (conditional, report) = certify(&base, &baseline, &decoder, &[0x2000], &limits()).unwrap();
    let host = guard::Limits {
        max_evidence_bytes: 64,
        ..limits()
    };
    let mut oversized = report.clone();
    oversized.limits.max_evidence_bytes = 64;
    oversized.binding_sha256 = "invalid-binding-must-not-be-hashed-first".into();
    let error = validate(&oversized, &baseline, &decoder, &conditional, &host).unwrap_err();
    assert!(
        error
            .to_string()
            .contains("alignment hypothesis evidence byte limit"),
        "{error}"
    );
    let host = guard::Limits {
        max_sites: 1,
        ..limits()
    };
    for field in ["hypotheses", "decisions", "facts"] {
        let mut oversized = report.clone();
        oversized.limits.max_sites = 1;
        oversized.hypotheses.truncate(1);
        oversized.decisions.truncate(1);
        oversized.facts.truncate(1);
        match field {
            "hypotheses" => oversized.hypotheses.push(oversized.hypotheses[0].clone()),
            "decisions" => oversized.decisions.push(oversized.decisions[0].clone()),
            _ => oversized.facts.push(oversized.facts[0].clone()),
        }
        oversized.binding_sha256 = "invalid-binding-must-not-be-hashed-first".into();
        let error = validate(&oversized, &baseline, &decoder, &conditional, &host).unwrap_err();
        assert!(
            error
                .to_string()
                .contains("report cardinality exceeds trusted host"),
            "{field}: {error}"
        );
    }
}

#[test]
fn masked_kernel_matches_independent_product_graph_oracle() {
    // Exercise the actual finite transfer-system seam against literal BFS
    // expectations. These abstract matrices are not claimed as BAP source
    // certificates; the public-API tests above validate that separate boundary.
    let fixture: Value =
        serde_json::from_str(include_str!("fixtures/alignment-hypotheses/contract.json")).unwrap();
    let (base, baseline_template, decoder) = prepare(direct(None));
    let (_, hypothesis_template) =
        certify(&base, &baseline_template, &decoder, &[0x2000], &limits()).unwrap();
    let address = |site: u64| 0x1000 + 8 * site;
    let mask = |values: &Value| {
        values
            .as_array()
            .unwrap()
            .iter()
            .fold(0u16, |out, residue| {
                out | (1u16 << residue.as_u64().unwrap())
            })
    };
    let mut exercised = 0;
    let mut skipped_invalid = 0;
    let mut skipped_recursive = 0;
    let mut skipped_default = 0;
    for case in fixture["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let input = &case["input"];
        let expected = &case["expected"];
        if expected["status"] == "invalid" {
            // Synthetic identity violations have concrete public-API tamper controls.
            skipped_invalid += 1;
            continue;
        }
        if name == "recursive-activation-hypothesis-does-not-leak" {
            // One kernel invocation owns one activation; H2 binds each activation.
            skipped_recursive += 1;
            continue;
        }
        if name == "no-hypotheses-default-mathematical-projection" {
            // The empty-H product belongs to the unchanged v1 route.
            skipped_default += 1;
            continue;
        }
        let mut baseline = baseline_template.clone();
        baseline.input.sites.clear();
        baseline.input.roots.clear();
        baseline.input.premises.clear();
        baseline.transfers.clear();
        baseline.input.candidate_epoch = input["bindings"]["epoch"].as_u64().unwrap();
        baseline.stop = (!input["closed"].as_bool().unwrap()
            || !input["barriers"].as_array().unwrap().is_empty())
        .then(|| "abstract-oracle-open-coverage".into());
        for node in input["nodes"].as_array().unwrap() {
            let point = node["site"].as_u64().unwrap();
            let outgoing: Vec<_> = input["edges"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|edge| edge["src"].as_u64() == Some(point))
                .collect();
            let mut local = Vec::new();
            let mut jumps = Vec::new();
            let mut calls = Vec::new();
            for edge in outgoing {
                let destination = address(edge["dst"].as_u64().unwrap());
                match edge["kind"].as_str().unwrap() {
                    "call" => calls.push(destination),
                    "jump" => jumps.push(destination),
                    _ => local.push(destination),
                }
            }
            let kind = if !calls.is_empty() {
                jumps = calls;
                ControlKind::Call
            } else if local.len() > 1 || (!local.is_empty() && !jumps.is_empty()) {
                jumps.extend(local.drain(1..));
                ControlKind::Conditional
            } else if !jumps.is_empty() {
                ControlKind::Jump
            } else if !local.is_empty() {
                ControlKind::Ordinary
            } else {
                ControlKind::Return
            };
            let source = site(address(point), &[], kind, &local, &jumps);
            let delta = node["delta"].as_i64().unwrap();
            let relation = (0..16)
                .map(|residue| match node["transfer"].as_str().unwrap() {
                    "identity" => 1u16 << residue,
                    "add" => 1u16 << ((residue as i64 + delta).rem_euclid(16) as u32),
                    "havoc" => guard::TOP,
                    other => panic!("unsupported finite oracle transfer {other}"),
                })
                .collect();
            baseline.transfers.push(guard::TransferReceipt {
                site: source.site.clone(),
                bytes_sha256: String::new(),
                ast_sha256: String::new(),
                rule: "abstract-oracle-matrix".into(),
                relation,
                relation_sha256: String::new(),
            });
            baseline.input.sites.push(source);
        }
        for root in input["roots"].as_array().unwrap() {
            let point = address(root["site"].as_u64().unwrap());
            baseline.input.roots.push(Root {
                site: hex(point),
                function_entry: true,
                anchor_sha256: hash("abstract-root"),
            });
            baseline.input.premises.push(Premise {
                origin: PremiseOrigin::CapturedRegister,
                snapshot: baseline.input.snapshot.clone(),
                query_scope_sha256: baseline.input.query_scope_sha256.clone(),
                root: hex(point),
                point: hex(point),
                activation: baseline.input.activation.clone(),
                policy: "abstract-oracle-root-mask".into(),
                evidence_sha256: hash("abstract-root-mask"),
                rsp_residues: mask(&root["residues"]),
                rsp_value: None,
            });
        }
        let hypotheses: Vec<_> = input["hypotheses"]
            .as_array()
            .unwrap()
            .iter()
            .map(|raw| {
                let mut hypothesis = hypothesis_template.hypotheses[0].clone();
                hypothesis.point = hex(address(raw["point"].as_u64().unwrap()));
                hypothesis.displacement = raw["displacement"].as_i64().unwrap();
                hypothesis.rsp_residues =
                    1u16 << (0i64.wrapping_sub(hypothesis.displacement).rem_euclid(16) as u32);
                hypothesis
            })
            .collect();
        let policy = guard::Limits {
            max_residue_updates: input["max_states"].as_u64().unwrap() as usize,
            max_transfer_evaluations: input["max_transfers"].as_u64().unwrap() as usize,
            max_closure_rounds: input["max_closure_rounds"].as_u64().unwrap() as usize,
            ..limits()
        };
        let result = least_fixed_point(&baseline, &hypotheses, &policy).unwrap();
        assert_eq!(
            result.stop.is_none(),
            expected["status"] == "complete",
            "{name}"
        );
        let expected_facts: Vec<_> = expected["facts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|fact| Fact {
                site: hex(address(fact["site"].as_u64().unwrap())),
                incoming: mask(&fact["incoming"]),
                residues: mask(&fact["residues"]),
            })
            .collect();
        assert_eq!(result.facts, expected_facts, "{name}");
        exercised += 1;
    }
    assert_eq!(exercised, 21);
    assert_eq!(
        (skipped_invalid, skipped_recursive, skipped_default),
        (16, 1, 1)
    );
    println!(
        "alignment product oracle: {exercised} kernel cases; {skipped_invalid} identity cases covered by public-API tamper tests; one recursive aggregation and one no-H v1 case remain separate"
    );
}
