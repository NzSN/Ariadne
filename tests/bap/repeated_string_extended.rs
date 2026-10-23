//! v13 default-address memory-REP controls. Actual arithmetic is checked by the
//! independent fresh-BIL numeric oracle; these controls check admission and
//! conservative possible-origin projection.
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
fn integer(value: u64, width: usize) -> Expr {
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
fn assign(name: &str, width: usize, value: Expr) -> Stmt {
    Stmt::Move {
        var: var(name, width),
        value,
    }
}
fn load(name: &str, width: usize) -> Expr {
    Expr::Load {
        width,
        mem: Box::new(read("mem", 0)),
        addr: Box::new(read(name, 64)),
    }
}
fn low_accumulator(width: usize) -> Expr {
    Expr::Extract {
        hi: width - 1,
        lo: 0,
        arg: Box::new(read("RAX", 64)),
    }
}
fn loop_body(family: &str, width: usize) -> Vec<Stmt> {
    let mut body = Vec::new();
    if family == "stos" || family == "movs" {
        body.push(assign(
            "mem",
            0,
            Expr::Store {
                width,
                mem: Box::new(read("mem", 0)),
                addr: Box::new(read("RDI", 64)),
                value: Box::new(if family == "stos" {
                    low_accumulator(width)
                } else {
                    load("RSI", width)
                }),
            },
        ));
    } else if family == "scas" || family == "cmps" {
        for flag in ["CF", "PF", "AF", "ZF", "SF", "OF"] {
            body.push(assign(
                flag,
                1,
                binary(
                    5,
                    if family == "scas" {
                        low_accumulator(width)
                    } else {
                        load("RSI", width)
                    },
                    load("RDI", width),
                ),
            ));
        }
    } else if family == "lods" {
        // This plausible supplied body must never substitute for absent BAP
        // semantics. Its opcode/bytes remain outside the v13 admission map.
        body.push(assign(
            "RAX",
            64,
            Expr::Cast {
                op: 0,
                width: 64,
                arg: Box::new(load("RSI", width)),
            },
        ));
    }
    let mut pointers = vec![];
    if ["movs", "lods", "cmps"].contains(&family) {
        pointers.push("RSI");
    }
    if ["movs", "stos", "cmps", "scas"].contains(&family) {
        pointers.push("RDI");
    }
    for pointer in pointers {
        let size = (width / 8) as u64;
        body.push(assign(
            pointer,
            64,
            binary(
                18,
                read(pointer, 64),
                Expr::Ite {
                    condition: Box::new(read("DF", 1)),
                    yes: Box::new(integer(0u64.wrapping_sub(size), 64)),
                    no: Box::new(integer(size, 64)),
                },
            ),
        ));
    }
    body.push(assign(
        "RCX",
        64,
        binary(17, read("RCX", 64), integer(1, 64)),
    ));
    body
}
fn loop_ast(family: &str, width: usize) -> Vec<Stmt> {
    vec![Stmt::While {
        condition: binary(4, read("RCX", 64), integer(0, 64)),
        body: loop_body(family, width),
    }]
}
fn project_extended(statements: &[Stmt], opcode: &str, bytes: &[u8]) -> Result<Projection, Error> {
    project_with_destination_profile(
        statements,
        opcode,
        bytes,
        0x401000,
        None,
        crate::bap::repeated_strings::PROFILE13,
    )
}
fn recipes() -> Vec<serde_json::Value> {
    let document: serde_json::Value = serde_json::from_str(include_str!(
        "fixtures/repeated-string/memory-recipes-v2.json"
    ))
    .unwrap();
    document["cases"].as_array().unwrap().clone()
}
fn bytes(hex: &str) -> Vec<u8> {
    hex.as_bytes()
        .chunks_exact(2)
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

#[test]
fn exact_reviewed_recipe_map_freezes_v12_and_refuses_missing_lods() {
    let mut admitted = 0;
    for case in recipes() {
        let opcode = case["bapOpcode"].as_str().unwrap();
        let encoding = bytes(case["bytes"].as_str().unwrap());
        let allowed = !case["profile"].is_null();
        assert_eq!(
            crate::bap::repeated_strings::opcode(
                &encoding,
                crate::bap::repeated_strings::PROFILE13,
            ),
            allowed.then_some(opcode),
        );
        let statements = loop_ast(
            case["family"].as_str().unwrap(),
            case["elementBits"].as_u64().unwrap() as usize,
        );
        assert_eq!(
            project_extended(&statements, opcode, &encoding).is_ok(),
            allowed
        );
        if allowed {
            admitted += 1;
            let v12 = crate::bap::repeated_strings::opcode(
                &encoding,
                crate::bap::repeated_strings::PROFILE,
            );
            assert_eq!(
                v12.is_some(),
                matches!(&encoding[..], [0xf3, 0xa4 | 0xaa | 0xa6])
            );
            for previous in [
                "bap-bit-provenance-v7",
                "bap-bit-provenance-v8",
                "bap-bit-provenance-v9",
                "bap-bit-provenance-v10",
                "bap-bit-provenance-v11",
            ] {
                assert!(
                    project_with_destination_profile(
                        &statements,
                        opcode,
                        &encoding,
                        0x401000,
                        None,
                        previous
                    )
                    .is_err()
                );
            }
        }
    }
    assert_eq!(admitted, 24);
}

#[test]
fn unreviewed_prefix_order_widths_io_and_opcode_aliases_are_refused() {
    let statements = loop_ast("movs", 16);
    for encoding in [
        &[0xf3, 0x66, 0xa5][..],
        &[0x67, 0xf3, 0xa5],
        &[0x64, 0x66, 0xf3, 0xa5],
        &[0x66, 0xf3, 0xf3, 0xa5],
        &[0xf0, 0x66, 0xf3, 0xa5],
        &[0xf3, 0x48, 0xa4],
        &[0x48, 0xf3, 0xa5],
        &[0xf3, 0x6c],
        &[0xf3, 0x6e],
    ] {
        assert!(project_extended(&statements, "MOVSW", encoding).is_err());
    }
    assert!(project_extended(&statements, "MOVSD", &[0xf3, 0xa5]).is_err());
    assert!(project_extended(&statements, "MOVSB", &[0x66, 0xf3, 0xa5]).is_err());
    assert!(project_extended(&[], "LODSB", &[0xf3, 0xac]).is_err());
}

#[test]
fn accumulator_lanes_and_zero_entry_origins_are_preserved() {
    for (width, stores, scans) in [
        (8, &[0xf3, 0xaa][..], &[0xf2, 0xae][..]),
        (16, &[0x66, 0xf3, 0xab], &[0x66, 0xf2, 0xaf]),
        (32, &[0xf3, 0xab], &[0xf2, 0xaf]),
        (64, &[0xf3, 0x48, 0xab], &[0xf2, 0x48, 0xaf]),
    ] {
        for (family, encoding) in [("stos", stores), ("scas", scans)] {
            let opcode = crate::bap::repeated_strings::opcode(
                encoding,
                crate::bap::repeated_strings::PROFILE13,
            )
            .unwrap();
            let result = project_extended(&loop_ast(family, width), opcode, encoding).unwrap();
            assert!(result.must_defs.is_empty());
            assert_eq!(result.may_defs.contains("memory:any"), family == "stos");
            assert_eq!(result.uses.contains("memory:any"), family == "scas");
            assert!(!result.may_defs.contains("gpr:rax:0"));
            for lane in 0..8 {
                assert_eq!(
                    result.uses.contains(&format!("gpr:rax:{lane}")),
                    lane < width / 8
                );
                for bank in ["rcx", "rdi"] {
                    let location = format!("gpr:{bank}:{lane}");
                    assert!(result.uses.contains(&location));
                    assert!(result.may_defs.contains(&location));
                }
                assert!(!result.uses.contains(&format!("gpr:rsi:{lane}")));
                assert!(!result.may_defs.contains(&format!("gpr:rsi:{lane}")));
            }
            for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
                let location = format!("flag:{flag}");
                assert_eq!(result.may_defs.contains(&location), family == "scas");
                assert_eq!(result.uses.contains(&location), family == "scas");
            }
            assert!(result.uses.contains("flag:df"));
        }
    }
}

#[test]
fn false_loop_condition_keeps_all_widths_effect_free() {
    for (opcode, encoding) in [
        ("MOVSW", &[0x66, 0xf3, 0xa5][..]),
        ("SCASQ", &[0xf2, 0x48, 0xaf][..]),
    ] {
        let statements = [Stmt::While {
            condition: integer(0, 1),
            body: loop_body(
                if opcode == "MOVSW" { "movs" } else { "scas" },
                if opcode == "MOVSW" { 16 } else { 64 },
            ),
        }];
        let result = project_extended(&statements, opcode, encoding).unwrap();
        assert!(result.uses.is_empty());
        assert!(result.may_defs.is_empty());
        assert!(result.must_defs.is_empty());
    }
}

#[test]
#[ignore = "requires all 28 fresh producer lifts in ARIADNE_REP_MEMORY_FRESH_LIFTS"]
fn fresh_producer_24_nonempty_lifts_project_and_four_empty_lods_are_refused() {
    let path = std::env::var_os("ARIADNE_REP_MEMORY_FRESH_LIFTS")
        .expect("ARIADNE_REP_MEMORY_FRESH_LIFTS must name the fresh all-28 lift array");
    let lifts: Vec<crate::bap::ast::Lift> =
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let cases = recipes();
    assert_eq!(lifts.len(), 28);
    let mut projected = 0;
    let mut missing = 0;
    for (case, lift) in cases.iter().zip(&lifts) {
        lift.validate_ast().unwrap();
        let encoding = bytes(case["bytes"].as_str().unwrap());
        let opcode = case["bapOpcode"].as_str().unwrap();
        assert_eq!(lift.bytes, case["bytes"].as_str().unwrap());
        assert_eq!(lift.opcode.as_deref(), Some(opcode));
        assert_eq!(usize::from(lift.length), encoding.len());
        if case["profile"].is_null() {
            assert!(lift.bil.is_empty());
            assert!(project_extended(&lift.bil, opcode, &encoding).is_err());
            missing += 1;
        } else {
            assert!(!lift.bil.is_empty());
            let result = project_extended(&lift.bil, opcode, &encoding).unwrap();
            assert!(result.must_defs.is_empty());
            assert!(result.may_defs.contains("gpr:rcx:0"));
            assert!(result.uses.contains("flag:df"));
            assert_eq!(
                result.may_defs.contains("memory:any"),
                ["movs", "stos"].contains(&case["family"].as_str().unwrap())
            );
            projected += 1;
        }
    }
    assert_eq!((projected, missing), (24, 4));
}
