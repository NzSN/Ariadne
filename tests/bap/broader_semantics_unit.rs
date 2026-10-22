//! Independent data-effect expectations for actual pinned FP-control BIL.
use super::*;
use crate::bap::admission;
use serde_json::Value as Json;

const ADVANCED: [&str; 2] = ["bap-bit-provenance-v10", "bap-bit-provenance-v11"];

fn variable(name: &str, width: usize) -> Var {
    Var {
        name: name.into(),
        index: 0,
        virtual_: false,
        width,
        type_: "imm".into(),
    }
}
fn read(name: &str, width: usize) -> Expr {
    Expr::Var {
        var: variable(name, width),
    }
}
fn constant(value: u64, width: usize) -> Expr {
    Expr::Int {
        value: format!("{value}:{width}u"),
    }
}
fn assignment(name: &str, width: usize, value: Expr) -> Stmt {
    Stmt::Move {
        var: variable(name, width),
        value,
    }
}
fn extend(value: Expr, width: usize) -> Expr {
    Expr::Cast {
        op: 3,
        width,
        arg: Box::new(value),
    }
}
fn cells(name: &str) -> LocationSet {
    (0..8).map(|byte| format!("gpr:{name}:{byte}")).collect()
}
fn selected(bil: &[Stmt], profile: &str) -> Projection {
    project_with_destination_profile(
        bil,
        "typed-control-fixture",
        &[0x90],
        0x401000,
        None,
        profile,
    )
    .unwrap()
}
fn actual_cases() -> Vec<(String, String, Vec<Stmt>)> {
    let fixture: Json = serde_json::from_str(include_str!(
        "fixtures/broader-semantics/fp-control-bil.json"
    ))
    .unwrap();
    fixture["cases"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| {
            (
                row["bytes"].as_str().unwrap().into(),
                row["opcode"].as_str().unwrap().into(),
                serde_json::from_value(row["bil"].clone()).unwrap(),
            )
        })
        .collect()
}

#[test]
fn actual_control_loads_and_stores_have_independent_memory_and_state_effects() {
    for (hex, opcode, bil) in actual_cases() {
        let bytes: Vec<_> = (0..hex.len())
            .step_by(2)
            .map(|at| u8::from_str_radix(&hex[at..at + 2], 16).unwrap())
            .collect();
        let load = matches!(hex.as_str(), "0fae10" | "d928");
        for profile in ADVANCED {
            let p =
                project_with_destination_profile(&bil, &opcode, &bytes, 0x401000, None, profile)
                    .unwrap();
            let mut uses = cells("rax");
            uses.insert(if load { "memory:any" } else { "state:other" }.into());
            assert_eq!(p.uses, uses, "{hex}/{profile}");
            assert_eq!(
                p.may_defs,
                [if load { "state:other" } else { "memory:any" }.into()].into()
            );
            assert!(
                p.must_defs.is_empty(),
                "aggregate state/memory must retain unrelated origins"
            );
            assert!(p.targets.is_empty());
            assert_eq!(p.gaps, ["fp-control-state-coarsened:state:other"]);
        }
    }
}

#[test]
fn old_and_unknown_profiles_keep_fp_control_namespace_refusal() {
    for (_, opcode, bil) in actual_cases() {
        assert!(project(&bil, &opcode, &[0x90], 0x401000).is_err());
        assert!(admission::capabilities(&bil).is_err());
        for profile in [
            "bap-bit-provenance-v3",
            "bap-bit-provenance-v4",
            "bap-bit-provenance-v5",
            "bap-bit-provenance-v6",
            "bap-bit-provenance-v7",
            "bap-bit-provenance-v8",
            "bap-bit-provenance-v9",
            "bap-bit-provenance-v12",
            "unknown",
        ] {
            let error = admission::admit_with_profile(&bil, &opcode, &[0x90], profile).unwrap_err();
            assert!(!admission::ordinary_unknown_with_profile(
                &bil,
                &[0x90],
                &error,
                profile
            ));
            assert!(
                project_with_destination_profile(&bil, &opcode, &[0x90], 0x401000, None, profile)
                    .is_err()
            );
        }
    }
}

#[test]
fn fp_control_names_indices_and_widths_are_exact() {
    for (name, correct) in [("MXCSR", 32), ("FPU_CONTROL", 16)] {
        for width in [1, 8, 16, 32, 64, 80, 128, 256] {
            let bil = [assignment(name, width, constant(0, width))];
            assert_eq!(
                admission::capabilities_with_profile(&bil, ADVANCED[0]).is_ok(),
                width == correct
            );
        }
        for index in [-1, 1, i32::MAX] {
            let mut var = variable(name, correct);
            var.index = index;
            assert!(
                admission::capabilities_with_profile(
                    &[Stmt::Move {
                        var,
                        value: constant(0, correct)
                    }],
                    ADVANCED[0]
                )
                .is_err()
            );
        }
    }
    for name in [
        "mxcsr",
        "MXCSR_MASK",
        "FPCW",
        "FPSW",
        "FPU_STATUS",
        "FPU_TAG",
        "R_MXCSR",
        "CR0",
        "XCR0",
    ] {
        assert!(
            admission::capabilities_with_profile(
                &[assignment(name, 32, constant(0, 32))],
                ADVANCED[0]
            )
            .is_err(),
            "{name}"
        );
    }
}

#[test]
fn fp_control_variables_are_distinct_despite_the_shared_output_location() {
    for (written, width, other, other_width) in [
        ("MXCSR", 32, "FPU_CONTROL", 16),
        ("FPU_CONTROL", 16, "MXCSR", 32),
        ("MXCSR", 32, "YMM6", 256),
        ("YMM6", 256, "MXCSR", 32),
    ] {
        let bil = [
            assignment(written, width, constant(0, width)),
            Stmt::If {
                condition: Expr::Extract {
                    hi: 0,
                    lo: 0,
                    arg: Box::new(read(other, other_width)),
                },
                yes: vec![assignment("RAX", 64, read("RBX", 64))],
                no: vec![assignment("RAX", 64, constant(1, 64))],
            },
        ];
        let p = selected(&bil, ADVANCED[0]);
        assert!(p.uses.contains("state:other"));
        assert!(
            p.uses.is_superset(&cells("rbx")),
            "incorrect alias eliminated a possible branch"
        );
        assert!(!p.must_defs.contains("state:other"));
    }
    let p = selected(
        &[
            assignment("MXCSR", 32, constant(17, 32)),
            assignment("RAX", 64, extend(read("MXCSR", 32), 64)),
        ],
        ADVANCED[0],
    );
    assert!(
        p.uses.is_empty(),
        "known per-variable bits should remain available within the lift"
    );
    assert_eq!(p.must_defs, cells("rax"));
}

#[test]
fn partial_fp_control_updates_preserve_old_aggregate_origins() {
    let p = selected(
        &[assignment(
            "MXCSR",
            32,
            Expr::Concat {
                lhs: Box::new(Expr::Extract {
                    hi: 31,
                    lo: 8,
                    arg: Box::new(read("MXCSR", 32)),
                }),
                rhs: Box::new(Expr::Extract {
                    hi: 7,
                    lo: 0,
                    arg: Box::new(read("RBX", 64)),
                }),
            },
        )],
        ADVANCED[0],
    );
    assert_eq!(p.uses, ["state:other".into(), "gpr:rbx:0".into()].into());
    assert_eq!(p.may_defs, ["state:other".into()].into());
    assert!(p.must_defs.is_empty());
}

#[test]
fn actual_memory_width_and_address_mutations_are_rejected() {
    for (_, _, bil) in actual_cases() {
        for mutation in 0..3 {
            let mut changed = bil.clone();
            let Stmt::Move { value, .. } = &mut changed[0] else {
                unreachable!()
            };
            let (width, mem, addr) = match value {
                Expr::Load { width, mem, addr }
                | Expr::Store {
                    width, mem, addr, ..
                } => (width, mem, addr),
                _ => unreachable!(),
            };
            match mutation {
                0 => *width = if *width == 16 { 32 } else { 16 },
                1 => *addr = Box::new(constant(0, 32)),
                _ => *mem = Box::new(read("RAX", 64)),
            }
            assert!(
                admission::admit_with_profile(
                    &changed,
                    "actual-control-input",
                    &[0x90],
                    ADVANCED[0]
                )
                .is_err()
            );
        }
    }
}

#[test]
fn unknown_control_values_and_unmodeled_control_do_not_become_supported() {
    let bil = [assignment(
        "MXCSR",
        32,
        Expr::Unknown {
            reason: "unmodeled producer result".into(),
        },
    )];
    let error = admission::admit_with_profile(&bil, "fixture", &[0x90], ADVANCED[0]).unwrap_err();
    assert!(admission::ordinary_unknown_with_profile(
        &bil,
        &[0x90],
        &error,
        ADVANCED[0]
    ));
    assert!(
        project_with_destination_profile(&bil, "fixture", &[0x90], 0x401000, None, ADVANCED[0])
            .is_err()
    );
    for control in [
        Stmt::Exception { number: 13 },
        Stmt::Special,
        Stmt::While {
            condition: constant(1, 1),
            body: vec![],
        },
    ] {
        let mut code = bil.to_vec();
        code.push(control);
        let error =
            admission::admit_with_profile(&code, "fixture", &[0x90], ADVANCED[0]).unwrap_err();
        assert!(!admission::ordinary_unknown_with_profile(
            &code,
            &[0x90],
            &error,
            ADVANCED[0]
        ));
    }
    assert!(
        Catalogue.locations().contains("state:other"),
        "opaque call/unknown effects must still cover FP control state"
    );
}

fn canonical_nops() -> Vec<(Vec<u8>, &'static str)> {
    [
        ("90", "NOOP"),
        ("6690", "NOOP"),
        ("0f1f00", "NOOPL"),
        ("0f1f4000", "NOOPL"),
        ("0f1f440000", "NOOPL"),
        ("660f1f440000", "NOOPW"),
        ("0f1f8000000000", "NOOPL"),
        ("0f1f840000000000", "NOOPL"),
        ("660f1f840000000000", "NOOPW"),
    ]
    .into_iter()
    .map(|(hex, opcode)| {
        (
            (0..hex.len())
                .step_by(2)
                .map(|at| u8::from_str_radix(&hex[at..at + 2], 16).unwrap())
                .collect(),
            opcode,
        )
    })
    .collect()
}

#[test]
fn canonical_multibyte_nops_are_exact_new_profile_empty_lifts() {
    for (bytes, opcode) in canonical_nops() {
        for profile in ADVANCED {
            let p = project_with_destination_profile(&[], opcode, &bytes, 0x401000, None, profile)
                .unwrap();
            assert!(
                p.uses.is_empty()
                    && p.may_defs.is_empty()
                    && p.must_defs.is_empty()
                    && p.targets.is_empty()
                    && p.gaps.is_empty()
            );
        }
        for profile in ["bap-bit-provenance-v6", "bap-bit-provenance-v9"] {
            assert_eq!(
                project_with_destination_profile(&[], opcode, &bytes, 0x401000, None, profile)
                    .is_ok(),
                bytes == [0x90]
            );
        }
        assert!(admission::admit_with_profile(&[], "MOV64rr", &bytes, ADVANCED[0]).is_err());
        for prefix in [0x66, 0x67, 0xf0, 0xf2, 0xf3, 0x2e, 0x48] {
            let altered: Vec<_> = [prefix].into_iter().chain(bytes.iter().copied()).collect();
            let admitted_canonical = canonical_nops()
                .iter()
                .any(|(b, op)| *b == altered && *op == opcode);
            assert_eq!(
                admission::admit_with_profile(&[], opcode, &altered, ADVANCED[0]).is_ok(),
                admitted_canonical
            );
        }
        let mut trailing = bytes.clone();
        trailing.push(0x90);
        assert!(admission::admit_with_profile(&[], opcode, &trailing, ADVANCED[0]).is_err());
        if let Some(modrm) = bytes
            .windows(2)
            .position(|b| b == [0x0f, 0x1f])
            .map(|at| at + 2)
        {
            let mut neighbor = bytes.clone();
            neighbor[modrm] |= 0x08;
            assert!(admission::admit_with_profile(&[], opcode, &neighbor, ADVANCED[0]).is_err());
            assert!(
                admission::admit_with_profile(&[], opcode, &bytes[..modrm], ADVANCED[0]).is_err()
            );
        }
    }
    for (opcode, bytes) in [
        ("PAUSE", &[0xf3, 0x90][..]),
        ("MFENCE", &[0x0f, 0xae, 0xf0][..]),
        ("LFENCE", &[0x0f, 0xae, 0xe8][..]),
    ] {
        assert!(admission::admit_with_profile(&[], opcode, bytes, ADVANCED[0]).is_err());
    }
}

#[test]
fn packed_byte_shuffle_joins_data_choices_without_a_query_failure_or_strong_aggregate_write() {
    let fixture: Json =
        serde_json::from_str(include_str!("fixtures/broader-semantics/pshufb-bil.json")).unwrap();
    let bil: Vec<Stmt> = serde_json::from_value(fixture["bil"].clone()).unwrap();
    let bytes = [0x66, 0x0f, 0x38, 0x00, 0xc1];
    for profile in ADVANCED {
        let p = project_with_destination_profile(&bil, "PSHUFBrr", &bytes, 0x401000, None, profile)
            .unwrap();
        assert_eq!(p.uses, ["state:other".into()].into());
        assert_eq!(p.may_defs, ["state:other".into()].into());
        assert!(p.must_defs.is_empty());
        assert!(p.targets.is_empty());
        assert!(
            p.gaps
                .iter()
                .any(|gap| gap == "data-paths-joined:possible-origin-union")
        );
        assert!(!p.gaps.iter().any(|gap| gap.contains("unknown-output")));
    }
    for profile in ["bap-bit-provenance-v6", "bap-bit-provenance-v9"] {
        let error =
            project_with_destination_profile(&bil, "PSHUFBrr", &bytes, 0x401000, None, profile)
                .unwrap_err();
        assert_eq!(error.to_string(), "BIL path limit");
    }
}

#[test]
fn joined_data_paths_keep_conditional_old_origins_and_all_possible_writes() {
    let statements: Vec<_> = ["CF", "PF", "AF", "ZF", "SF", "OF"]
        .into_iter()
        .map(|flag| Stmt::If {
            condition: read(flag, 1),
            yes: vec![],
            no: vec![assignment("RAX", 64, read("RBX", 64))],
        })
        .collect();
    let p = selected(&statements, ADVANCED[0]);
    assert_eq!(p.may_defs, cells("rax"));
    assert!(
        p.must_defs.is_empty(),
        "the all-true path keeps the previous RAX value"
    );
    assert!(p.uses.is_superset(&cells("rbx")));
    assert!(p.uses.is_superset(&cells("rax")));
    for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
        assert!(p.uses.contains(&format!("flag:{flag}")));
    }
    let mut overwritten = statements;
    overwritten.push(assignment("RAX", 64, constant(0, 64)));
    assert_eq!(selected(&overwritten, ADVANCED[0]).must_defs, cells("rax"));
}

#[test]
fn joining_does_not_make_control_paths_or_recursive_work_unbounded() {
    let mut control: Vec<_> = ["CF", "PF", "AF", "ZF", "SF", "OF"]
        .into_iter()
        .map(|flag| Stmt::If {
            condition: read(flag, 1),
            yes: vec![],
            no: vec![],
        })
        .collect();
    control.push(Stmt::Jump {
        target: constant(0x402000, 64),
    });
    let error = project_with_destination_profile(
        &control,
        "typed-control-fixture",
        &[0x90],
        0x401000,
        None,
        ADVANCED[0],
    )
    .unwrap_err();
    assert_eq!(error.to_string(), "BIL path limit");

    fn nested(level: usize) -> Vec<Stmt> {
        if level == 0 {
            return vec![assignment("RAX", 64, constant(1, 64))];
        }
        let mut code: Vec<_> = (0..5)
            .map(|_| Stmt::If {
                condition: read("CF", 1),
                yes: vec![],
                no: vec![],
            })
            .collect();
        code.push(Stmt::If {
            condition: read("ZF", 1),
            yes: nested(level - 1),
            no: vec![],
        });
        code
    }
    let code = nested(4);
    admission::admit_with_profile(&code, "typed-data-fixture", &[0x90], ADVANCED[0]).unwrap();
    // Exercise the shared recursive work counter with a small injected limit;
    // exhausting the production 262144-step ceiling would slow ordinary tests.
    let error = run(
        &code,
        vec![State {
            advanced: true,
            join_data_paths: true,
            ..State::default()
        }],
        0x401000,
        0,
        &mut ProjectionBudget {
            remaining: Some(128),
        },
    )
    .err()
    .expect("recursive projection must stop at its work limit");
    assert_eq!(error.to_string(), "BIL projection work limit");
    assert!(admission::fatal(&error));
    assert!(!admission::ordinary_unknown_with_profile(
        &code,
        &[0x90],
        &error,
        ADVANCED[0]
    ));
}

#[test]
#[ignore = "requires the pinned BAP runtime/helper and LLVM MC decode reference"]
fn actual_bap_and_llvm_control_state_and_nop_inputs_match_independent_effects() {
    use crate::bap::{Config, Session};
    use crate::effects::PreparationOptions;
    use crate::llvm_mc::{DecoderTarget, decode_captured_batch};
    use std::path::PathBuf;
    let mut cases: Vec<_> = actual_cases()
        .into_iter()
        .map(|(hex, opcode, _)| {
            (
                (0..hex.len())
                    .step_by(2)
                    .map(|at| u8::from_str_radix(&hex[at..at + 2], 16).unwrap())
                    .collect::<Vec<_>>(),
                opcode,
            )
        })
        .collect();
    cases.extend(
        canonical_nops()
            .into_iter()
            .map(|(bytes, opcode)| (bytes, opcode.into())),
    );
    let nop_end = cases.len();
    cases.push((vec![0x66, 0x0f, 0x38, 0x00, 0xc1], "PSHUFBrr".into()));
    let candidates: BTreeMap<_, _> = cases
        .iter()
        .enumerate()
        .map(|(index, (bytes, _))| (0x401000 + index as u64 * 32, bytes.clone()))
        .collect();
    let mut session = Session::start(
        &Config::from_env(),
        "broader-state-independent-expectations",
        "windows-amd64",
    )
    .unwrap();
    let lifted = session.lift(&candidates).unwrap();
    session.finish().unwrap();
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc")
        });
    let reference = decode_captured_batch(
        "broader-state-independent-expectations",
        &candidates
            .iter()
            .map(|(va, bytes)| (*va, Some(bytes.clone())))
            .collect(),
        &decoder,
        &PreparationOptions::default(),
        DecoderTarget::WindowsAmd64,
    )
    .unwrap();
    for (index, (bytes, opcode)) in cases.iter().enumerate() {
        let va = 0x401000 + index as u64 * 32;
        let lift = &lifted[&va];
        let decoded = &reference.sites[&va];
        assert_eq!(lift.length as usize, bytes.len());
        assert_eq!(decoded.evidence.length, lift.length);
        assert_eq!(decoded.evidence.bytes, *bytes);
        assert_eq!(decoded.evidence.opcode.as_ref(), Some(opcode));
        assert_eq!(decoded.instruction.kind, crate::InstructionKind::Ordinary);
        let control = lift.properties.as_ref().unwrap();
        assert!(
            !control.jump
                && !control.conditional
                && !control.indirect
                && !control.call
                && !control.return_
                && !control.control
        );
        let p = project_with_destination_profile(&lift.bil, opcode, bytes, va, None, ADVANCED[0])
            .unwrap();
        if index >= nop_end {
            assert!(!lift.bil.is_empty());
            assert_eq!(p.uses, ["state:other".into()].into());
            assert_eq!(p.may_defs, ["state:other".into()].into());
            assert!(p.must_defs.is_empty());
            assert!(
                p.gaps
                    .iter()
                    .any(|gap| gap == "data-paths-joined:possible-origin-union")
            );
        } else if index >= 4 {
            assert!(lift.bil.is_empty());
            assert!(p.uses.is_empty() && p.may_defs.is_empty() && p.must_defs.is_empty());
        } else {
            let load = index == 0 || index == 2;
            let mut uses = cells("rax");
            uses.insert(if load { "memory:any" } else { "state:other" }.into());
            assert_eq!(p.uses, uses);
            assert_eq!(
                p.may_defs,
                [if load { "state:other" } else { "memory:any" }.into()].into()
            );
            assert!(p.must_defs.is_empty());
        }
    }
}
