//! Independent shift typing, count and origin controls. Numeric expectations
//! come from the standalone Python integer oracle, not the projector.
use super::ast::{Expr, Lift, Stmt, Var};
use super::{admission, guard_admission, projection, refinement, target_resolution};
use crate::LocationSet;

fn var(name: &str, width: usize, virtual_: bool) -> Var {
    Var {
        name: name.into(),
        index: 0,
        virtual_,
        width,
        type_: "imm".into(),
    }
}
fn read(name: &str, width: usize, virtual_: bool) -> Expr {
    Expr::Var {
        var: var(name, width, virtual_),
    }
}
fn constant(value: &str, width: usize) -> Expr {
    Expr::Int {
        value: format!("{value}:{width}u"),
    }
}
fn binary(op: i32, lhs: Expr, rhs: Expr) -> Expr {
    Expr::Binop {
        op,
        lhs: Box::new(lhs),
        rhs: Box::new(rhs),
    }
}
fn mov(name: &str, width: usize, virtual_: bool, value: Expr) -> Stmt {
    Stmt::Move {
        var: var(name, width, virtual_),
        value,
    }
}
fn gpr(name: &str) -> LocationSet {
    (0..8).map(|i| format!("gpr:{name}:{i}")).collect()
}
fn project(bil: &[Stmt]) -> projection::Projection {
    projection::project(bil, "typed-shift-fixture", &[0x90], 0x1000).unwrap()
}

#[test]
fn independent_count_width_is_valid_but_nonshift_width_mismatches_stay_invalid() {
    for op in [9, 10, 11] {
        let bil = [mov(
            "tmp",
            128,
            true,
            binary(op, constant("1", 128), constant("1", 8)),
        )];
        assert!(
            admission::admit(&bil, "typed-shift-fixture", &[0x90]).is_ok(),
            "shift {op}"
        );
        project(&bil);
    }
    for op in [0, 1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18] {
        let width = if op <= 5 { 1 } else { 128 };
        let bil = [mov(
            "tmp",
            width,
            true,
            binary(op, constant("1", 128), constant("1", 8)),
        )];
        assert!(admission::capabilities(&bil).is_err(), "nonshift {op}");
    }
}

#[test]
fn equal_abstract_metadata_does_not_prove_computed_values_equal() {
    let different = binary(
        6,
        binary(18, read("RBX", 64, false), constant("1", 64)),
        binary(18, read("RBX", 64, false), constant("2", 64)),
    );
    let p = project(&[mov("RAX", 64, false, different)]);
    assert!(
        p.uses.is_superset(&gpr("rbx")),
        "different expressions falsely cancelled"
    );
    let shared = binary(18, read("RBX", 64, false), constant("1", 64));
    let p = project(&[
        mov("tmp", 64, true, shared),
        mov(
            "RAX",
            64,
            false,
            binary(6, read("tmp", 64, true), read("tmp", 64, true)),
        ),
    ]);
    assert!(p.uses.is_empty(), "the same bound temporary should cancel");
}

#[test]
fn captured_xorps_retains_legacy_upper_half_and_coarse_old_origins() {
    let lift: Lift =
        serde_json::from_str(include_str!("fixtures/shifts/captured-xorps-bil.json")).unwrap();
    assert_eq!(lift.bytes, "0f57c0");
    let bil = lift.bil;
    let p = projection::project(&bil, "XORPSrr", &[0x0f, 0x57, 0xc0], 0x7ff7744075b3).unwrap();
    assert_eq!(p.uses, ["state:other".into()].into());
    assert_eq!(p.may_defs, ["state:other".into()].into());
    assert!(p.must_defs.is_empty());
    assert!(
        p.gaps
            .iter()
            .any(|g| g == "vector-state-coarsened:state:other")
    );
    let mut after = bil;
    after.push(mov(
        "RAX",
        64,
        false,
        Expr::Extract {
            hi: 191,
            lo: 128,
            arg: Box::new(read("YMM0", 256, false)),
        },
    ));
    let p = project(&after);
    assert!(p.uses.contains("state:other"));
    assert_eq!(p.must_defs, gpr("rax"));
    assert!(!p.must_defs.contains("state:other"));
}

#[test]
fn all_value_count_width_pairs_return_the_left_type() {
    for width in 1..=256 {
        for count_width in 1..=256 {
            for op in [9, 10, 11] {
                let bil = [mov(
                    "tmp",
                    width,
                    true,
                    binary(op, constant("0", width), constant("0", count_width)),
                )];
                assert!(
                    admission::capabilities(&bil).is_ok(),
                    "op={op} value={width} count={count_width}"
                );
            }
        }
    }
    let memory = Expr::Var {
        var: Var {
            name: "mem".into(),
            index: 0,
            virtual_: false,
            width: 0,
            type_: "mem".into(),
        },
    };
    for op in [9, 10, 11] {
        for expression in [
            binary(op, memory.clone(), constant("0", 8)),
            binary(op, constant("0", 64), memory.clone()),
        ] {
            assert!(admission::capabilities(&[mov("tmp", 64, true, expression)]).is_err());
        }
        for width in [0, 257] {
            assert!(
                admission::capabilities(&[mov(
                    "tmp",
                    64,
                    true,
                    binary(op, constant("0", 64), constant("0", width))
                )])
                .is_err()
            );
            assert!(
                admission::capabilities(&[mov(
                    "tmp",
                    64,
                    true,
                    binary(op, constant("0", width), constant("0", 8)),
                )])
                .is_err()
            );
        }
    }
}

fn hex_bit(text: &str, bit: usize) -> bool {
    let digits = text.strip_prefix("0x").unwrap();
    digits
        .as_bytes()
        .iter()
        .rev()
        .nth(bit / 4)
        .is_some_and(|c| char::from(*c).to_digit(16).unwrap() & (1 << (bit % 4)) != 0)
}

fn numeric_probe(expression: Expr, width: usize, bit: usize) -> projection::Projection {
    project(&[
        mov("shifted", width, true, expression),
        Stmt::If {
            condition: Expr::Extract {
                hi: bit,
                lo: bit,
                arg: Box::new(read("shifted", width, true)),
            },
            yes: vec![mov("RAX", 64, false, read("RBX", 64, false))],
            no: vec![mov("RAX", 64, false, read("RCX", 64, false))],
        },
    ])
}

#[test]
fn full_unsigned_counts_and_boundary_fills_match_the_independent_integer_oracle() {
    let oracle: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/shifts/contract.json")).unwrap();
    assert_eq!(oracle["schema"], "ariadne.bap-shift-oracle/v1");
    assert_eq!(oracle["campaign"]["width_pairs"], 65536);
    assert_eq!(
        oracle["captured_xorps_sha256"],
        crate::reports::sha256(include_bytes!("fixtures/shifts/captured-xorps-bil.json"))
    );
    let mut value_widths = std::collections::BTreeSet::new();
    let mut count_widths = std::collections::BTreeSet::new();
    let mut high_count = false;
    for row in oracle["cases"].as_array().unwrap() {
        let op = row["op"].as_i64().unwrap() as i32;
        let width = row["value_width"].as_u64().unwrap() as usize;
        let count_width = row["count_width"].as_u64().unwrap() as usize;
        let value = row["value_hex"].as_str().unwrap();
        let count = row["count_hex"].as_str().unwrap();
        let expected = row["result_hex"].as_str().unwrap();
        value_widths.insert(width);
        count_widths.insert(count_width);
        high_count |= (64..count_width).any(|bit| hex_bit(count, bit));
        for bit in row["probe_bits"].as_array().unwrap() {
            let bit = bit.as_u64().unwrap() as usize;
            let p = numeric_probe(
                binary(op, constant(value, width), constant(count, count_width)),
                width,
                bit,
            );
            assert_eq!(
                p.uses,
                gpr(if hex_bit(expected, bit) { "rbx" } else { "rcx" }),
                "op={op} data={width}:{value} count={count_width}:{count} probe={bit}"
            );
            assert_eq!(p.must_defs, gpr("rax"));
        }
    }
    assert_eq!(value_widths, (1..=256).collect());
    assert_eq!(count_widths, (1..=256).collect());
    assert!(high_count, "oracle must catch high count-bit truncation");
}

#[test]
fn signed_spelling_does_not_turn_a_count_bitvector_into_a_negative_count() {
    for op in [9, 10, 11] {
        let p = numeric_probe(
            binary(
                op,
                constant("0x80", 8),
                Expr::Int {
                    value: "-1:8s".into(),
                },
            ),
            8,
            0,
        );
        assert_eq!(p.uses, gpr(if op == 9 { "rbx" } else { "rcx" }));
    }
}

#[test]
fn zero_count_preserves_source_bit_identity_even_when_the_count_is_wide() {
    for op in [9, 10, 11] {
        let expression = binary(
            6,
            binary(op, read("RBX", 64, false), constant("0", 256)),
            read("RBX", 64, false),
        );
        let p = numeric_probe(expression, 64, 0);
        assert_eq!(
            p.uses,
            gpr("rcx"),
            "zero shift lost preserved source identity for op {op}"
        );
    }
}

#[test]
fn unknown_shift_counts_and_distinct_shifts_keep_their_possible_origins() {
    for op in [9, 10, 11] {
        let p = project(&[mov(
            "RAX",
            64,
            false,
            binary(op, read("RBX", 64, false), read("RCX", 64, false)),
        )]);
        assert!(p.uses.is_superset(&gpr("rbx")));
        assert!(p.uses.is_superset(&gpr("rcx")));
        let a = binary(op, read("RBX", 64, false), read("RCX", 64, false));
        let b = binary(op, read("RBX", 64, false), read("RDX", 64, false));
        let p = project(&[mov("RAX", 64, false, binary(6, a, b))]);
        assert!(p.uses.is_superset(&gpr("rbx")));
        assert!(p.uses.is_superset(&gpr("rcx")));
        assert!(p.uses.is_superset(&gpr("rdx")));
        let shared = binary(op, read("RBX", 64, false), read("RCX", 64, false));
        let p = project(&[
            mov("same", 64, true, shared),
            mov(
                "RAX",
                64,
                false,
                binary(6, read("same", 64, true), read("same", 64, true)),
            ),
        ]);
        assert!(
            p.uses.is_empty(),
            "same bound expression should cancel for op {op}"
        );
        // Generic untyped Unknown in a wide value remains the ordinary opaque
        // data policy; it is distinct from admitted typed variable counts.
        let bil = [mov(
            "RAX",
            64,
            false,
            binary(
                op,
                read("RBX", 64, false),
                Expr::Unknown {
                    reason: "unknown-shift-count".into(),
                },
            ),
        )];
        let error = admission::admit(&bil, "typed-shift-fixture", &[0x90]).unwrap_err();
        assert_eq!(
            error.downcast_ref::<admission::Failure>().unwrap().kind,
            admission::FailureKind::UnsupportedData
        );
        assert!(admission::ordinary_unknown(&bil, &[0x90], &error));
    }
    // Values with identical dependency metadata are not correlated merely
    // because both stem from the coarse vector state.
    let p = project(&[mov(
        "XMM2",
        128,
        false,
        binary(
            6,
            binary(11, read("XMM0", 128, false), constant("1", 8)),
            binary(11, read("XMM0", 128, false), constant("2", 8)),
        ),
    )]);
    assert!(p.uses.contains("state:other"));
    assert!(p.must_defs.is_empty());
    let alias = binary(
        6,
        read("XMM0", 128, false),
        Expr::Cast {
            op: 0,
            width: 128,
            arg: Box::new(read("YMM0", 256, false)),
        },
    );
    let p = numeric_probe(alias, 128, 0);
    assert_eq!(
        p.uses,
        gpr("rcx"),
        "matching preserved XMM/YMM source bits should cancel"
    );
}

#[test]
fn a_known_oversized_count_erases_data_origins_without_modulo_reduction() {
    for op in [10, 11] {
        let p = project(&[mov(
            "RAX",
            64,
            false,
            binary(
                op,
                read("RBX", 64, false),
                constant("0x10000000000000000", 65),
            ),
        )]);
        assert!(
            p.uses.is_empty(),
            "wide count was truncated or wrapped for op {op}"
        );
        assert_eq!(p.must_defs, gpr("rax"));
    }
    let p = project(&[mov(
        "RAX",
        64,
        false,
        binary(
            9,
            read("RBX", 64, false),
            constant("0x10000000000000000", 65),
        ),
    )]);
    assert_eq!(p.uses, ["gpr:rbx:7".into()].into());
}

#[test]
fn mixed_width_shift_adds_no_scalar_refinement_or_target_precision() {
    for op in [9, 10, 11] {
        let bil = [mov(
            "RSP",
            64,
            false,
            binary(op, read("RSP", 64, false), constant("0", 8)),
        )];
        let receipt = refinement::extract(&bil, 0x1000, "90".into()).unwrap();
        assert!(matches!(
            receipt.outputs[&4],
            refinement::TransferExpression::Unsupported { .. }
        ));
        let target = target_resolution::extract(&bil, 0x1000, &[0x90]).unwrap();
        let encoded = serde_json::to_value(target).unwrap();
        assert_eq!(encoded["outputs"]["RSP:0:false"]["kind"]["kind"], "unknown");
    }
}

#[test]
fn admitted_rsp_shifts_stay_top_in_the_guard_numerical_domain() {
    use guard_admission as guard;
    for op in [9, 10, 11] {
        let root_instruction = crate::Instruction {
            kind: crate::InstructionKind::Ordinary,
            fall: [0x1001].into(),
            complete: true,
            ..Default::default()
        };
        let store_instruction = crate::Instruction {
            kind: crate::InstructionKind::Ordinary,
            fall: [0x1009].into(),
            complete: true,
            ..Default::default()
        };
        let terminal = crate::Instruction {
            kind: crate::InstructionKind::Return,
            complete: true,
            ..Default::default()
        };
        let activation = guard::Activation {
            thread_id: 17,
            frame_activation: "shift-control-activation".into(),
        };
        let scope = "1".repeat(64);
        let source = serde_json::to_string(&[mov(
            "RSP",
            64,
            false,
            binary(op, read("RSP", 64, false), constant("0", 8)),
        )])
        .unwrap();
        let input = guard::GuardInput {
            snapshot: "shift-fixture".into(),
            artifact_sha256: "2".repeat(64),
            query_scope_sha256: scope.clone(),
            preparation_sha256: "3".repeat(64),
            platform: "windows-amd64".into(),
            roots: vec![guard::Root {
                site: "0x0000000000001000".into(),
                function_entry: true,
                anchor_sha256: "4".repeat(64),
            }],
            seeds: Vec::new(),
            activation: activation.clone(),
            premises: vec![guard::Premise {
                origin: guard::PremiseOrigin::AbiNormalCall,
                snapshot: "shift-fixture".into(),
                query_scope_sha256: scope,
                root: "0x0000000000001000".into(),
                point: "0x0000000000001000".into(),
                activation,
                policy: guard::ABI_POLICY.into(),
                evidence_sha256: "5".repeat(64),
                rsp_residues: 1 << 8,
                rsp_value: None,
            }],
            producer: guard::Producer {
                helper_sha256: "6".repeat(64),
                runtime_sha256: "7".repeat(64),
                decoder_sha256: "8".repeat(64),
                projection: guard::PRODUCER_PROFILE.into(),
            },
            policy: guard::PROFILE.into(),
            model_version: guard::MODEL_VERSION.into(),
            model_sha256: guard::model_identity(),
            limits: guard::Limits::default(),
            candidate_epoch: 1,
            closure_complete: true,
            barriers: Vec::new(),
            sites: vec![
                guard::CandidateSite {
                    site: "0x0000000000001000".into(),
                    bytes_hex: "90".into(),
                    ast: source,
                    control: guard::CandidateControl::from_instruction(&root_instruction),
                    opaque: false,
                },
                guard::CandidateSite {
                    site: "0x0000000000001001".into(),
                    bytes_hex: "0f29b42440020000".into(),
                    ast: include_str!("fixtures/vector/movaps-bil.json")
                        .trim()
                        .into(),
                    control: guard::CandidateControl::from_instruction(&store_instruction),
                    opaque: true,
                },
                guard::CandidateSite {
                    site: "0x0000000000001009".into(),
                    bytes_hex: "c3".into(),
                    ast: "[]".into(),
                    control: guard::CandidateControl::from_instruction(&terminal),
                    opaque: true,
                },
            ],
            normal_flow: Some(guard::NormalFlowEvidence::empty()),
        };
        let report = guard::certify_guards(&input).unwrap();
        assert!(
            report.stop.is_none(),
            "valid mixed shift is not a control barrier"
        );
        assert_eq!(report.transfers[0].relation, vec![guard::TOP; 16]);
        assert_eq!(report.guards[0].verdict, guard::Verdict::Unknown);
        assert!(report.normal_selection(0x1001).is_none());
    }
}
