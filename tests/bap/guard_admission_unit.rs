use super::ast::{Expr, Stmt, Var};
use super::guard_admission::*;
use serde_json::Value;

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
fn guard(va: u64) -> CandidateSite {
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
            projection: PRODUCER_PROFILE.into(),
        },
        policy: PROFILE.into(),
        model_version: MODEL_VERSION.into(),
        model_sha256: model_identity(),
        limits: Limits::default(),
        candidate_epoch: 0,
        closure_complete: true,
        barriers: Vec::new(),
        sites,
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
    let mut i = input(vec![guard(0x2000), terminal(0x2008)], &[0x2000]);
    if let Some(r) = residue {
        observe(&mut i, 0x2000, r);
    }
    i
}
fn oracle() -> Value {
    serde_json::from_str(include_str!("fixtures/guards/contract.json")).unwrap()
}

#[test]
fn direct_guard_verdicts_match_frozen_independent_product_graph() {
    let fixture = oracle();
    for r in 0..16 {
        let name = format!("direct-residue-{r:02}");
        let expected = fixture["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["name"] == name)
            .unwrap();
        let i = direct(Some(r));
        let report = certify_guards(&i).unwrap();
        let g = &report.guards[0];
        let verdict = match expected["expected"]["guards"][0]["verdict"]
            .as_str()
            .unwrap()
        {
            "proved-aligned" => Verdict::Aligned,
            "proved-misaligned" => Verdict::Misaligned,
            v => panic!("unexpected fixture verdict {v}"),
        };
        assert_eq!(g.verdict, verdict, "{name}");
        assert_eq!(
            g.normal_ast.is_some(),
            expected["expected"]["guards"][0]["admit_normal"]
                .as_bool()
                .unwrap()
        );
        assert_eq!(g.address_residues, 1 << r);
        replay_report(&i, &report).unwrap();
    }
    let report = certify_guards(&direct(None)).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Unknown);
    assert_eq!(report.guards[0].input_residues, TOP);
    assert!(report.guards[0].normal_ast.is_none());
}

#[test]
fn typed_transfer_rows_match_all_720_frozen_independent_64_bit_executions() {
    let fixture = oracle();
    let rows = fixture["numeric_cases"].as_array().unwrap();
    assert_eq!(rows.len(), 720);
    let mut sites = Vec::new();
    let mut roots = Vec::new();
    for (index, case) in rows.iter().enumerate() {
        let va = 0x10000 + index as u64;
        let kind = case["kind"].as_str().unwrap();
        let n = case["constant"].as_u64().unwrap_or(8);
        let bil = match kind {
            "add" => arithmetic(18, n),
            "subtract" => arithmetic(17, n),
            "push8" => arithmetic(17, 8),
            "identity" | "havoc" => Vec::new(),
            _ => panic!("fixture transfer {kind}"),
        };
        let mut s = site(va, &bil, ControlKind::Stop, &[], &[]);
        s.opaque = kind == "havoc";
        sites.push(s);
        roots.push(va);
    }
    let i = input(sites, &roots);
    let report = certify_guards(&i).unwrap();
    assert!(report.stop.is_none());
    for (index, case) in rows.iter().enumerate() {
        let expected = case["expected"]
            .as_array()
            .unwrap()
            .iter()
            .fold(0u16, |mask, n| mask | 1 << n.as_u64().unwrap());
        let residue = case["residue"].as_u64().unwrap() as usize;
        assert_eq!(
            report.transfers[index].relation[residue], expected,
            "numeric oracle row {index}"
        );
    }
    replay_report(&i, &report).unwrap();
}

fn prologue(with_abi: bool) -> GuardInput {
    let mut sites = Vec::new();
    for n in 0..8 {
        let mut s = site(
            0x1000 + n,
            &arithmetic(17, 8),
            ControlKind::Ordinary,
            &[0x1001 + n],
            &[],
        );
        s.bytes_hex = "50".into();
        sites.push(s);
    }
    let mut allocation = site(
        0x1008,
        &arithmetic(17, 0x258),
        ControlKind::Ordinary,
        &[0x100f],
        &[],
    );
    allocation.bytes_hex = "4881ec58020000".into();
    sites.extend([allocation, guard(0x100f), terminal(0x1017)]);
    let mut i = input(sites, &[0x1000]);
    if with_abi {
        observe(&mut i, 0x1000, 8);
        i.premises[0].origin = PremiseOrigin::AbiNormalCall;
        i.premises[0].policy = ABI_POLICY.into();
        i.premises[0].rsp_value = None;
    }
    i
}
#[test]
fn opt_in_abi_prologue_proves_alignment_and_unseeded_prologue_does_not() {
    let i = prologue(true);
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Aligned);
    assert_eq!(report.guards[0].input_residues, 1);
    assert_eq!(report.transfers[8].relation[8], 1);
    assert!(report.normal_selection(0x100f).is_some());
    assert_eq!(
        report.input.premises[0].origin,
        PremiseOrigin::AbiNormalCall
    );
    let unseeded = certify_guards(&prologue(false)).unwrap();
    assert_eq!(unseeded.guards[0].verdict, Verdict::Unknown);
    assert!(unseeded.normal_selection(0x100f).is_none());
}

#[test]
fn joined_paths_and_changing_loops_prevent_false_alignment() {
    let mut i = input(
        vec![
            site(0x1000, &[], ControlKind::Conditional, &[0x1100], &[0x1200]),
            site(0x1100, &[], ControlKind::Jump, &[], &[0x2000]),
            site(
                0x1200,
                &arithmetic(18, 8),
                ControlKind::Jump,
                &[],
                &[0x2000],
            ),
            guard(0x2000),
            terminal(0x2008),
        ],
        &[0x1000],
    );
    observe(&mut i, 0x1000, 0);
    let report = certify_guards(&i).unwrap();
    // Both ordinary alternatives are included regardless of branch feasibility.
    assert_eq!(report.guards[0].verdict, Verdict::Unknown);
    let identity = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: read("RSP"),
    }];
    i.sites[0].ast = serde_json::to_string(&identity).unwrap();
    i.sites[1].ast = serde_json::to_string(&identity).unwrap();
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].input_residues, (1 << 0) | (1 << 8));
    assert_eq!(report.guards[0].verdict, Verdict::Unknown);
    let mut looped = direct(Some(0));
    looped.sites[1] = site(
        0x2008,
        &arithmetic(18, 8),
        ControlKind::Jump,
        &[],
        &[0x2000],
    );
    let report = certify_guards(&looped).unwrap();
    assert_eq!(report.guards[0].input_residues, (1 << 0) | (1 << 8));
    assert_eq!(report.guards[0].verdict, Verdict::Unknown);
    looped.sites[1].ast = serde_json::to_string(&identity).unwrap();
    let report = certify_guards(&looped).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Aligned);
    assert_eq!(
        report.transfers[0].rule,
        "pending-legacy128-movaps-rsp-identity/v1"
    );
    assert_eq!(report.transfers[0].relation[0], 1);
}

#[test]
fn opaque_calls_stack_loads_and_unsupported_writes_havoc_rsp() {
    let load = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: Expr::Load {
            width: 64,
            mem: Box::new(Expr::Var {
                var: var("mem", 0, false),
            }),
            addr: Box::new(read("RBP")),
        },
    }];
    let unsupported = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: Expr::Unknown {
            reason: "unsupported rsp output".into(),
        },
    }];
    for (bil, kind, opaque) in [
        (arithmetic(17, 8), ControlKind::Call, false),
        (arithmetic(17, 8), ControlKind::Ordinary, true),
        (load, ControlKind::Ordinary, false),
        (unsupported, ControlKind::Ordinary, false),
    ] {
        let mut first = site(0x1000, &bil, kind, &[0x2000], &[]);
        first.opaque = opaque;
        let mut i = input(vec![first, guard(0x2000), terminal(0x2008)], &[0x1000]);
        observe(&mut i, 0x1000, 8);
        let report = certify_guards(&i).unwrap();
        assert_eq!(report.guards[0].input_residues, TOP);
        assert_eq!(report.guards[0].verdict, Verdict::Unknown);
        assert!(report.guards[0].normal_ast.is_none());
    }
}

#[test]
fn unreviewed_source_control_is_a_barrier_even_with_forged_ordinary_metadata() {
    let reset = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: integer(0),
    }];
    for unsafe_control in [
        Stmt::Special,
        Stmt::Exception { number: 13 },
        Stmt::Unsupported,
    ] {
        let mut first = site(
            0x1000,
            &[unsafe_control],
            ControlKind::Ordinary,
            &[0x1100],
            &[],
        );
        first.opaque = true;
        let mut i = input(
            vec![
                first,
                site(0x1100, &reset, ControlKind::Ordinary, &[0x2000], &[]),
                guard(0x2000),
                terminal(0x2008),
            ],
            &[0x1000],
        );
        observe(&mut i, 0x1000, 8);
        let report = certify_guards(&i).unwrap();
        assert_eq!(
            report.stop.as_deref(),
            Some("candidate-coverage-incomplete")
        );
        assert_eq!(report.guards[0].verdict, Verdict::Unknown);
        assert!(report.normal_selection(0x2000).is_none());
        replay_report(&i, &report).unwrap();
    }
    // A later definite assignment can restore precision after ordinary,
    // conservatively opaque data, without certifying unknown source control.
    let opaque_data = vec![Stmt::Move {
        var: var("RSP", 64, false),
        value: Expr::Unknown {
            reason: "ordinary unknown output".into(),
        },
    }];
    let mut i = input(
        vec![
            site(0x1000, &opaque_data, ControlKind::Ordinary, &[0x1100], &[]),
            site(0x1100, &reset, ControlKind::Ordinary, &[0x2000], &[]),
            guard(0x2000),
            terminal(0x2008),
        ],
        &[0x1000],
    );
    observe(&mut i, 0x1000, 8);
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Aligned);
}

#[test]
fn temporaries_are_supported_and_call_targets_are_not_local_predecessors() {
    let bil = vec![
        Stmt::Move {
            var: var("tmp", 64, true),
            value: Expr::Binop {
                op: 17,
                lhs: Box::new(read("RSP")),
                rhs: Box::new(integer(8)),
            },
        },
        Stmt::Move {
            var: var("RSP", 64, false),
            value: Expr::Var {
                var: var("tmp", 64, true),
            },
        },
    ];
    let mut i = input(
        vec![
            site(0x1000, &bil, ControlKind::Ordinary, &[0x2000], &[]),
            guard(0x2000),
            terminal(0x2008),
        ],
        &[0x1000],
    );
    observe(&mut i, 0x1000, 8);
    assert_eq!(
        certify_guards(&i).unwrap().guards[0].verdict,
        Verdict::Aligned
    );
    let mut i = direct(Some(0));
    let mut call = site(0x3000, &[], ControlKind::Call, &[0x3001], &[0x2000]);
    call.opaque = true;
    i.sites.extend([call, terminal(0x3001)]);
    i.roots.push(Root {
        site: hex(0x3000),
        function_entry: true,
        anchor_sha256: hash("separate-call-root"),
    });
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Aligned);
    replay_report(&i, &report).unwrap();
}

#[test]
fn exact_guard_recognition_rejects_every_unreviewed_leaf_and_source_mismatch() {
    let original = guard(0x2000);
    let pending = recognize_pending(&original).unwrap().unwrap();
    assert_eq!(pending.displacement, 0x240);
    assert_eq!(pending.vector_bank, 6);
    assert_eq!(pending.original_ast_sha256, hash(&original.ast));
    let ast: Value = serde_json::from_str(&original.ast).unwrap();
    let mut variations = Vec::new();
    for (path, value) in [
        ("/0/value/width", serde_json::json!(256)),
        ("/0/value/value/width", serde_json::json!(64)),
        ("/0/value/value/arg/var/name", serde_json::json!("YMM7")),
        ("/0/value/addr/rhs/value", serde_json::json!("0x241:64u")),
        ("/1/condition/lhs/rhs/value", serde_json::json!("0x7:64u")),
        ("/1/condition/lhs/rhs/value", serde_json::json!("0xF:64uu")),
        ("/1/condition/rhs/value", serde_json::json!("0:64us")),
        ("/1/condition/rhs/value", serde_json::json!("1:64u")),
        ("/1/no/0/number", serde_json::json!(14)),
    ] {
        let mut changed = ast.clone();
        *changed.pointer_mut(path).unwrap() = value;
        let mut s = original.clone();
        s.ast = changed.to_string();
        variations.push(s);
    }
    for arm in ["yes", "no"] {
        let mut changed = ast.clone();
        changed[1][arm]
            .as_array_mut()
            .unwrap()
            .push(serde_json::json!({"kind":"special"}));
        let mut s = original.clone();
        s.ast = changed.to_string();
        variations.push(s);
    }
    for bytes in [
        "0f29b42441020000",   // displacement mismatches BIL
        "660f29b42440020000", // MOVAPD
        "c5f829b42440020000", // VEX family
        "410f29b42440020000", // R12 base
        "0f28b42440020000",   // load
        "0f29f4",             // register destination
        "0f29b4244002000090", // extra instruction
    ] {
        let mut s = original.clone();
        s.bytes_hex = bytes.into();
        variations.push(s);
    }
    let mut s = original.clone();
    s.control.fall = vec![hex(0x2009)];
    variations.push(s);
    let mut s = original.clone();
    s.control.kind = ControlKind::Stop;
    s.control.fall.clear();
    variations.push(s);
    for (n, s) in variations.iter().enumerate() {
        assert!(
            !matches!(recognize_pending(s), Ok(Some(_))),
            "unsupported variant {n}"
        );
    }
}

#[test]
fn selected_normal_store_retains_weak_memory_definition_and_original_source() {
    let i = direct(Some(0));
    let report = certify_guards(&i).unwrap();
    let g = &report.guards[0];
    let normal: Vec<Stmt> = serde_json::from_str(g.normal_ast.as_ref().unwrap()).unwrap();
    assert_eq!(normal.len(), 1);
    let projected = super::projection::project(
        &normal,
        "MOVAPS-reviewed-store",
        &[0x0f, 0x29, 0xb4, 0x24, 0x40, 0x02, 0x00, 0x00],
        0x2000,
    )
    .unwrap();
    assert!(projected.may_defs.contains("memory:any"));
    assert!(projected.must_defs.is_empty());
    assert!(projected.uses.contains("state:other"));
    assert!(projected.uses.contains("gpr:rsp:0"));
    assert_eq!(g.original_ast_sha256, hash(&i.sites[0].ast));
    assert_eq!(
        g.normal_ast_sha256.as_ref().unwrap(),
        &hash(g.normal_ast.as_ref().unwrap())
    );
    assert_eq!(g.removed_statement_paths, ["bil[1]"]);
    assert!(report.input.sites[0].ast.contains("exception"));
    for residue in [None, Some(8)] {
        let report = certify_guards(&direct(residue)).unwrap();
        assert!(report.guards[0].normal_ast.is_none());
        assert!(report.guards[0].normal_ast_sha256.is_none());
        assert!(report.guards[0].removed_statement_paths.is_empty());
    }
}

#[test]
fn wrong_or_conflicting_premises_are_errors_not_empty_path_proofs() {
    let original = direct(Some(0));
    let mut variations = Vec::new();
    let mut i = original.clone();
    i.premises[0].snapshot = "other-snapshot".into();
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].query_scope_sha256 = hash("other-query");
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].point = hex(0x2008);
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].root = hex(0x2008);
    i.premises[0].point = hex(0x2008);
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].activation.frame_activation = "recursive-other-activation".into();
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].activation.thread_id += 1;
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].rsp_residues = 0;
    variations.push(i);
    let mut i = original.clone();
    i.premises[0].rsp_value = Some(hex(0x8008));
    variations.push(i);
    let mut i = original.clone();
    observe(&mut i, 0x2000, 8);
    variations.push(i);
    let mut i = prologue(true);
    i.roots[0].function_entry = false;
    variations.push(i);
    let mut i = prologue(true);
    i.platform = "linux-amd64".into();
    variations.push(i);
    let mut i = prologue(true);
    i.premises[0].policy = "unselected-abi".into();
    variations.push(i);
    for (n, i) in variations.iter().enumerate() {
        assert!(certify_guards(i).is_err(), "invalid premise {n}");
    }
}

#[test]
fn barriers_limits_and_unreached_facts_never_admit_a_normal_outcome() {
    let mut i = direct(Some(0));
    i.barriers.push(hex(0x2008));
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Unknown);
    assert_eq!(report.guards[0].input_residues, TOP);
    replay_report(&i, &report).unwrap();
    i.barriers.clear();
    i.closure_complete = false;
    assert_eq!(
        certify_guards(&i).unwrap().guards[0].verdict,
        Verdict::Unknown
    );
    let mut i = direct(Some(0));
    i.sites[1] = site(0x2008, &[], ControlKind::Indirect, &[], &[]);
    i.sites[1].control.complete = false;
    assert_eq!(
        certify_guards(&i).unwrap().guards[0].verdict,
        Verdict::Unknown
    );
    let i = input(
        vec![
            site(0x1000, &[], ControlKind::Stop, &[], &[]),
            guard(0x2000),
            terminal(0x2008),
        ],
        &[0x1000],
    );
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].input_residues, 0);
    assert_eq!(report.guards[0].verdict, Verdict::Unreached);
    assert!(report.normal_selection(0x2000).is_none());
    for budget in 0..5 {
        let mut i = direct(Some(0));
        match budget {
            0 => i.limits.max_elapsed_ms = 0,
            1 => i.limits.max_residue_updates = 0,
            2 => i.limits.max_transfer_evaluations = 0,
            3 => i.limits.max_sites = 0,
            _ => i.limits.max_closure_rounds = 0,
        }
        let report = certify_guards(&i).unwrap();
        assert!(report.stop.is_some());
        assert!(report.normal_selection(0x2000).is_none());
        replay_report(&i, &report).unwrap();
    }
    let mut i = direct(Some(0));
    i.limits.max_evidence_bytes = 1;
    assert!(certify_guards(&i).is_err());
}

#[test]
fn replay_rejects_omitted_roots_candidate_predecessors_and_tampering() {
    let i = direct(Some(0));
    let report = certify_guards(&i).unwrap();
    let mut forged = report.clone();
    forged.facts[0].residues = 0;
    assert!(
        replay_report(&i, &forged)
            .unwrap_err()
            .to_string()
            .contains("eligible root")
    );
    let mut forged = report.clone();
    forged.transfers[0].relation[0] = TOP;
    assert!(replay_report(&i, &forged).is_err());
    let mut forged = report.clone();
    forged.guards[0].normal_ast = Some("[]".into());
    assert!(replay_report(&i, &forged).is_err());
    let mut forged = report.clone();
    forged.guards[0].receipt_sha256 = hash("forged");
    assert!(replay_report(&i, &forged).is_err());
    let mut looped = direct(Some(0));
    looped.sites[1] = site(
        0x2008,
        &arithmetic(18, 8),
        ControlKind::Jump,
        &[],
        &[0x2000],
    );
    let mut omitted = certify_guards(&looped).unwrap();
    omitted.facts[0].residues = 1;
    assert!(
        replay_report(&looped, &omitted)
            .unwrap_err()
            .to_string()
            .contains("candidate predecessor")
    );
    let mut late = i.clone();
    late.candidate_epoch += 1;
    assert!(replay_report(&late, &report).is_err());
    let mut late = i.clone();
    late.roots.push(Root {
        site: hex(0x2008),
        function_entry: false,
        anchor_sha256: hash("late-root"),
    });
    assert!(replay_report(&late, &report).is_err());
    let mut changed = i.clone();
    changed.producer.helper_sha256 = hash("replacement-helper");
    assert!(replay_report(&changed, &report).is_err());
    let mut changed = i.clone();
    changed.sites[0].ast.push(' ');
    assert!(replay_report(&changed, &report).is_err());
}

#[test]
fn final_identity_binds_actual_premises_and_request_without_hash_cycles() {
    let i = direct(Some(0));
    let mut report = certify_guards(&i).unwrap();
    assert!(analysis_id(&report).is_err());
    let tentative = report.guards[0].receipt_sha256.clone();
    let request = hash("normalized-final-request-without-final-identities");
    bind_final_request(&i, &mut report, &request).unwrap();
    assert_ne!(tentative, report.guards[0].receipt_sha256);
    // Independent literal tuple encoding checks the cached-prefix hash codec.
    let mut row = report.guards[0].clone();
    row.receipt_sha256.clear();
    let encoded = serde_json::to_vec(&(
        "ariadne-guard-receipt/v1",
        &report.checker_sha256,
        &report.intent_id,
        &report.candidate_graph_sha256,
        report.input.candidate_epoch,
        &report.input.model_version,
        &report.input.model_sha256,
        &report.input.premises,
        &report.input.limits,
        &report.transfers,
        &report.facts,
        &report.stop,
        &report.final_request_sha256,
        row,
    ))
    .unwrap();
    assert_eq!(
        crate::reports::sha256(&encoded),
        report.guards[0].receipt_sha256
    );
    let id = analysis_id(&report).unwrap();
    assert_eq!(validate_final_request(&i, &report, &request).unwrap(), id);
    assert!(validate_final_request(&i, &report, &hash("different-request")).is_err());
    assert!(bind_final_request(&i, &mut report, &hash("different-request")).is_err());
    let changed = direct(Some(8));
    assert_ne!(intent_id(&i).unwrap(), intent_id(&changed).unwrap());
    let mut reordered = i.clone();
    reordered.sites.reverse();
    assert_eq!(intent_id(&i).unwrap(), intent_id(&reordered).unwrap());
    assert_eq!(graph_digest(&i).unwrap(), graph_digest(&reordered).unwrap());
    replay_report(&reordered, &report).unwrap();
    let json = serde_json::to_vec(&report).unwrap();
    let decoded: Report = serde_json::from_slice(&json).unwrap();
    assert_eq!(analysis_id(&decoded).unwrap(), id);
    let mut value: Value = serde_json::from_slice(&json).unwrap();
    value["guessed_alignment"] = serde_json::json!(true);
    assert!(serde_json::from_value::<Report>(value).is_err());
}

#[test]
fn caller_selected_budgets_can_exceed_every_default_and_bind_the_proof() {
    for index in 0..7 {
        let mut i = direct(Some(0));
        match index {
            0 => i.limits.max_sites += 1,
            1 => i.limits.max_edges += 1,
            2 => i.limits.max_residue_updates += 1,
            3 => i.limits.max_transfer_evaluations += 1,
            4 => i.limits.max_closure_rounds += 1,
            5 => i.limits.max_evidence_bytes = 32 * 1024 * 1024,
            _ => i.limits.max_elapsed_ms += 1,
        }
        i.limits.validate().unwrap();
        let report = certify_guards(&i).unwrap();
        assert_eq!(report.guards[0].verdict, Verdict::Aligned);
        assert_eq!(report.input.limits, i.limits);
        replay_report(&i, &report).unwrap();
        let mut changed = i.clone();
        changed.limits.max_evidence_bytes += 1;
        assert_ne!(intent_id(&changed).unwrap(), report.intent_id);
        assert!(replay_report(&changed, &report).is_err());
    }
    let mut i = direct(Some(0));
    i.limits = Limits {
        max_sites: usize::MAX,
        max_edges: usize::MAX,
        max_residue_updates: usize::MAX,
        max_transfer_evaluations: usize::MAX,
        max_closure_rounds: usize::MAX,
        max_evidence_bytes: usize::MAX,
        max_elapsed_ms: u64::MAX,
    };
    let report = certify_guards(&i).unwrap();
    assert_eq!(report.guards[0].verdict, Verdict::Aligned);
    replay_report(&i, &report).unwrap();
    for invalid in ["-1", "1.5", "18446744073709551616"] {
        let text = serde_json::to_string(&Limits::default()).unwrap();
        let text = text.replace(
            "\"max_elapsed_ms\":1000",
            &format!("\"max_elapsed_ms\":{invalid}"),
        );
        assert!(serde_json::from_str::<Limits>(&text).is_err(), "{invalid}");
    }
}
