//! Supplied typed-BIL controls, independent of native BAP availability.
use super::*;

fn var(name: &str, width: usize) -> Var {
    Var {
        name: name.into(),
        index: 0,
        virtual_: name.starts_with('#'),
        width,
        type_: if width == 0 { "mem" } else { "imm" }.into(),
    }
}
fn read(name: &str, width: usize) -> Expr {
    Expr::Var {
        var: var(name, width),
    }
}
fn constant(value: u64, width: usize) -> Expr {
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
fn write(name: &str, width: usize, value: Expr) -> Stmt {
    Stmt::Move {
        var: var(name, width),
        value,
    }
}
fn load(address: &str) -> Expr {
    Expr::Load {
        width: 8,
        mem: Box::new(read("mem", 0)),
        addr: Box::new(read(address, 64)),
    }
}
fn loop_statement(body: Vec<Stmt>) -> Stmt {
    Stmt::While {
        condition: binary(4, read("RCX", 64), constant(0, 64)),
        body,
    }
}
fn byte_string_body(opcode: &str) -> Vec<Stmt> {
    let mut body = Vec::new();
    if opcode == "CMPSB" {
        // Independent dependency shape; the native oracle separately checks
        // the producer's exact subtraction/flag equations.
        for flag in ["CF", "PF", "AF", "ZF", "SF", "OF"] {
            body.push(write(flag, 1, binary(5, load("RSI"), load("RDI"))));
        }
    } else {
        body.push(write(
            "mem",
            0,
            Expr::Store {
                width: 8,
                mem: Box::new(read("mem", 0)),
                addr: Box::new(read("RDI", 64)),
                value: Box::new(if opcode == "MOVSB" {
                    load("RSI")
                } else {
                    Expr::Extract {
                        hi: 7,
                        lo: 0,
                        arg: Box::new(read("RAX", 64)),
                    }
                }),
            },
        ));
    }
    for pointer in if opcode == "STOSB" {
        vec!["RDI"]
    } else {
        vec!["RSI", "RDI"]
    } {
        body.push(write(
            pointer,
            64,
            binary(
                18,
                read(pointer, 64),
                Expr::Ite {
                    condition: Box::new(read("DF", 1)),
                    yes: Box::new(constant(u64::MAX, 64)),
                    no: Box::new(constant(1, 64)),
                },
            ),
        ));
    }
    body.push(write(
        "RCX",
        64,
        binary(17, read("RCX", 64), constant(1, 64)),
    ));
    body
}
fn project_rep(statements: &[Stmt], opcode: &str, bytes: &[u8]) -> Result<Projection, Error> {
    project_with_destination_profile(
        statements,
        opcode,
        bytes,
        0x401000,
        None,
        crate::bap::repeated_strings::PROFILE,
    )
}

#[test]
fn exact_forms_keep_zero_iteration_origins_and_weak_memory_effects() {
    for (opcode, byte) in [("MOVSB", 0xa4), ("STOSB", 0xaa), ("CMPSB", 0xa6)] {
        let statements = [loop_statement(byte_string_body(opcode))];
        let result = project_rep(&statements, opcode, &[0xf3, byte]).unwrap();
        assert!(result.must_defs.is_empty());
        assert!(result.targets.is_empty());
        for bank in ["rcx", "rdi"] {
            for byte in 0..8 {
                let location = format!("gpr:{bank}:{byte}");
                assert!(result.uses.contains(&location));
                assert!(result.may_defs.contains(&location));
            }
        }
        assert!(result.uses.contains("flag:df"));
        assert_eq!(result.may_defs.contains("memory:any"), opcode != "CMPSB");
        assert_eq!(result.uses.contains("memory:any"), opcode != "STOSB");
        if opcode == "STOSB" {
            assert!(result.uses.contains("gpr:rax:0"));
            assert!(!result.uses.contains("gpr:rax:1"));
            assert!(!result.uses.contains("gpr:rsi:0"));
        } else {
            assert!(result.uses.contains("gpr:rsi:0"));
            assert!(result.may_defs.contains("gpr:rsi:0"));
        }
        for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
            let location = format!("flag:{flag}");
            assert_eq!(result.may_defs.contains(&location), opcode == "CMPSB");
            // Initial flags remain possible origins on the zero-count path.
            assert_eq!(result.uses.contains(&location), opcode == "CMPSB");
        }
    }
}

#[test]
fn definitely_false_condition_does_not_project_body_effects() {
    let statements = [Stmt::While {
        condition: constant(0, 1),
        body: byte_string_body("MOVSB"),
    }];
    let result = project_rep(&statements, "MOVSB", &[0xf3, 0xa4]).unwrap();
    assert!(result.uses.is_empty());
    assert!(result.may_defs.is_empty());
    assert!(result.must_defs.is_empty());
}

#[test]
fn fixed_point_carries_origins_through_multiple_body_iterations() {
    let body = [
        write("RAX", 64, read("RBX", 64)),
        write("RBX", 64, read("RDX", 64)),
        write("RDX", 64, read("RSI", 64)),
    ];
    let result = run_repeated_string_loop(
        &binary(4, read("RCX", 64), constant(0, 64)),
        &body,
        State {
            advanced: true,
            repeated_strings: true,
            join_data_paths: true,
            ..State::default()
        },
        0x401000,
        0,
        &mut ProjectionBudget {
            remaining: Some(1000),
        },
    )
    .unwrap();
    let carried = result.env[&var("RAX", 64).key()].deps();
    // RSI reaches RAX only after three body applications. Retaining the entry
    // RAX origin also checks the possible zero-iteration path.
    for bank in ["rax", "rbx", "rdx", "rsi"] {
        assert!(carried.contains(&format!("gpr:{bank}:0")));
    }
}

#[test]
fn loop_admission_binds_exact_bytes_opcode_and_new_profile() {
    let statements = [loop_statement(byte_string_body("MOVSB"))];
    for profile in [
        "bap-bit-provenance-v7",
        "bap-bit-provenance-v8",
        "bap-bit-provenance-v9",
        "bap-bit-provenance-v10",
        "bap-bit-provenance-v11",
    ] {
        assert!(
            crate::bap::admission::admit_with_profile(
                &statements,
                "MOVSB",
                &[0xf3, 0xa4],
                profile,
            )
            .is_err()
        );
    }
    for bytes in [
        &[0xa4][..],
        &[0xf2, 0xa4],
        &[0x66, 0xf3, 0xa4],
        &[0xf3, 0x48, 0xa4],
        &[0xf3, 0x64, 0xa4],
        &[0xf3, 0x67, 0xa4],
        &[0xf3, 0xa5],
        &[0xf3, 0xab],
        &[0xf3, 0xae],
        &[0xf0, 0xf3, 0xa4],
    ] {
        assert!(project_rep(&statements, "MOVSB", bytes).is_err());
    }
    assert!(project_rep(&statements, "STOSB", &[0xf3, 0xa4]).is_err());
    assert!(project_rep(&statements, "typed-transfer", &[0xf3, 0xa4]).is_err());
}

#[test]
fn loops_cannot_export_body_only_virtual_bindings_or_read_future_bindings() {
    let body_only = [
        loop_statement(vec![write("#temporary", 64, constant(1, 64))]),
        write("RAX", 64, read("#temporary", 64)),
    ];
    assert!(project_rep(&body_only, "MOVSB", &[0xf3, 0xa4]).is_err());
    let read_before_write = [loop_statement(vec![
        write("RAX", 64, read("#temporary", 64)),
        write("#temporary", 64, constant(1, 64)),
    ])];
    assert!(project_rep(&read_before_write, "MOVSB", &[0xf3, 0xa4]).is_err());
    let changed_type = [
        write("#temporary", 64, constant(1, 64)),
        loop_statement(vec![write("#temporary", 1, constant(0, 1))]),
    ];
    assert!(project_rep(&changed_type, "MOVSB", &[0xf3, 0xa4]).is_err());
    let bad_condition = [Stmt::While {
        condition: constant(1, 8),
        body: vec![],
    }];
    assert!(project_rep(&bad_condition, "MOVSB", &[0xf3, 0xa4]).is_err());
}

#[test]
fn control_and_rip_writes_are_refused_even_in_unreachable_loop_bodies() {
    for forbidden in [
        Stmt::Jump {
            target: constant(0x401002, 64),
        },
        Stmt::Exception { number: 13 },
        Stmt::Special,
        Stmt::Unsupported,
        write("RIP", 64, constant(0x401002, 64)),
    ] {
        let statements = [Stmt::While {
            condition: constant(0, 1),
            body: vec![Stmt::If {
                condition: constant(0, 1),
                yes: vec![forbidden],
                no: vec![],
            }],
        }];
        assert!(project_rep(&statements, "MOVSB", &[0xf3, 0xa4]).is_err());
    }
    let outside = [
        loop_statement(vec![]),
        Stmt::Jump {
            target: constant(0x401002, 64),
        },
    ];
    assert!(project_rep(&outside, "MOVSB", &[0xf3, 0xa4]).is_err());
}

#[test]
fn nested_sequential_and_conditionally_entered_loops_are_refused() {
    for statements in [
        vec![loop_statement(vec![loop_statement(vec![])])],
        vec![loop_statement(vec![]), loop_statement(vec![])],
        vec![Stmt::If {
            condition: constant(0, 1),
            yes: vec![loop_statement(vec![])],
            no: vec![],
        }],
        vec![
            Stmt::Jump {
                target: constant(0x401002, 64),
            },
            loop_statement(vec![]),
        ],
    ] {
        assert!(project_rep(&statements, "MOVSB", &[0xf3, 0xa4]).is_err());
    }
    assert!(
        project_rep(
            &[write("#guard", 1, constant(1, 1))],
            "MOVSB",
            &[0xf3, 0xa4]
        )
        .is_err()
    );
}

#[test]
fn fixed_point_work_exhaustion_is_an_explicit_resource_failure() {
    let error = run_repeated_string_loop(
        &binary(4, read("RCX", 64), constant(0, 64)),
        &[write("RAX", 64, read("RBX", 64))],
        State {
            advanced: true,
            repeated_strings: true,
            join_data_paths: true,
            ..State::default()
        },
        0x401000,
        0,
        &mut ProjectionBudget { remaining: Some(1) },
    )
    .err()
    .expect("insufficient work must refuse the projection");
    assert_eq!(
        error
            .downcast_ref::<crate::bap::admission::Failure>()
            .unwrap()
            .kind,
        crate::bap::admission::FailureKind::Resource,
    );
}

#[test]
#[ignore = "requires fresh producer output in ARIADNE_REP_FRESH_LIFTS"]
fn fresh_producer_loops_project_under_only_the_repeated_string_profile() {
    let path = std::env::var_os("ARIADNE_REP_FRESH_LIFTS")
        .expect("ARIADNE_REP_FRESH_LIFTS must name fresh native typed BIL");
    let lifts: Vec<crate::bap::ast::Lift> =
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    assert_eq!(lifts.len(), 3);
    for (lift, (opcode, bytes)) in lifts.iter().zip([
        ("MOVSB", [0xf3, 0xa4]),
        ("STOSB", [0xf3, 0xaa]),
        ("CMPSB", [0xf3, 0xa6]),
    ]) {
        lift.validate_ast().unwrap();
        assert_eq!(lift.status, "decoded");
        assert_eq!(lift.length, 2);
        assert_eq!(lift.bytes, format!("{:02x}{:02x}", bytes[0], bytes[1]));
        assert_eq!(lift.opcode.as_deref(), Some(opcode));
        let result = project_rep(&lift.bil, opcode, &bytes).unwrap();
        assert!(result.must_defs.is_empty());
        assert!(result.may_defs.contains("gpr:rcx:0"));
        assert!(result.may_defs.contains("gpr:rdi:0"));
        assert!(result.uses.contains("flag:df"));
        assert_eq!(result.may_defs.contains("memory:any"), opcode != "CMPSB");
        if opcode == "CMPSB" {
            for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
                let location = format!("flag:{flag}");
                assert!(result.may_defs.contains(&location));
                assert!(result.uses.contains(&location));
            }
        }
        assert!(
            crate::bap::admission::admit_with_profile(
                &lift.bil,
                opcode,
                &bytes,
                "bap-bit-provenance-v10",
            )
            .is_err()
        );
    }
}
