use super::ast::{Expr, Stmt, Var};
use super::{admission, projection};
use crate::{LocationSet, effects::Catalogue};

fn var(name: &str, width: usize) -> Var {
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
        var: var(name, width),
    }
}
fn constant(value: &str, width: usize) -> Expr {
    Expr::Int {
        value: format!("{value}:{width}u"),
    }
}
fn low(arg: Expr, width: usize) -> Expr {
    Expr::Cast {
        op: 0,
        width,
        arg: Box::new(arg),
    }
}
fn mov(name: &str, width: usize, value: Expr) -> Stmt {
    Stmt::Move {
        var: var(name, width),
        value,
    }
}
fn project(bil: &[Stmt]) -> projection::Projection {
    projection::project(bil, "typed-vector-fixture", &[0x90], 0x1000).unwrap()
}
fn gpr(name: &str) -> LocationSet {
    (0..8).map(|i| format!("gpr:{name}:{i}")).collect()
}

#[test]
fn vector_namespace_requires_canonical_names_indices_and_exact_widths() {
    for bank in 0..16 {
        for (prefix, width) in [("XMM", 128), ("YMM", 256)] {
            assert!(
                admission::capabilities(&[mov(
                    &format!("{prefix}{bank}"),
                    width,
                    constant("0", width)
                )])
                .is_ok()
            );
        }
    }
    for (name, width) in [
        ("YMM16", 256),
        ("XMM16", 128),
        ("YMM00", 256),
        ("YMM-1", 256),
        ("ymm6", 256),
        ("YMM6", 128),
        ("XMM6", 256),
        ("ZMM6", 256),
        ("K6", 64),
    ] {
        assert!(
            admission::capabilities(&[mov(name, width, constant("0", width))]).is_err(),
            "{name}/{width}"
        );
    }
    let mut indexed = var("YMM6", 256);
    indexed.index = 1;
    assert!(
        admission::capabilities(&[Stmt::Move {
            var: indexed,
            value: constant("0", 256)
        }])
        .is_err()
    );
}

#[test]
fn ymm_and_xmm_share_backing_in_both_read_directions() {
    let p = project(&[
        mov("YMM6", 256, constant("0x1234", 256)),
        mov("RAX", 64, low(read("XMM6", 128), 64)),
    ]);
    assert_eq!(p.uses, LocationSet::new());
    assert_eq!(
        p.may_defs,
        gpr("rax")
            .union(&["state:other".into()].into())
            .cloned()
            .collect()
    );
    assert_eq!(p.must_defs, gpr("rax"));
    let p = project(&[
        mov("XMM6", 128, constant("0x1234", 128)),
        mov("RAX", 64, low(read("YMM6", 256), 64)),
    ]);
    assert_eq!(p.must_defs, gpr("rax"));
    assert!(!p.must_defs.contains("state:other"));
    let p = project(&[
        mov("YMM6", 256, constant("1", 256)),
        Stmt::If {
            condition: low(read("XMM6", 128), 1),
            yes: vec![mov("RAX", 64, read("RBX", 64))],
            no: vec![mov("RAX", 64, constant("0", 64))],
        },
    ]);
    assert!(p.uses.is_superset(&gpr("rbx")));
}

#[test]
fn xmm_write_preserves_upper_ymm_and_ymm_write_replaces_prior_xmm_view() {
    let high = Expr::Extract {
        hi: 191,
        lo: 128,
        arg: Box::new(read("YMM6", 256)),
    };
    let p = project(&[mov("XMM6", 128, constant("0", 128)), mov("RAX", 64, high)]);
    assert!(p.uses.contains("state:other"));
    assert_eq!(p.must_defs, gpr("rax"));

    // The known low half must be visible through the wider alias. A separate
    // YMM environment would make both branches possible and add RBX origins.
    let p = project(&[
        mov("XMM6", 128, constant("0", 128)),
        Stmt::If {
            condition: low(read("YMM6", 256), 1),
            yes: vec![mov("RAX", 64, read("RBX", 64))],
            no: vec![mov("RAX", 64, constant("0", 64))],
        },
    ]);
    assert!(p.uses.is_disjoint(&gpr("rbx")));

    // An XMM assignment preserves the high half. Its old bit stays unknown,
    // so the conditional RAX write remains possible rather than definite.
    let p = project(&[
        mov("XMM6", 128, constant("0", 128)),
        Stmt::If {
            condition: Expr::Extract {
                hi: 128,
                lo: 128,
                arg: Box::new(read("YMM6", 256)),
            },
            yes: vec![mov("RAX", 64, constant("1", 64))],
            no: vec![],
        },
    ]);
    assert!(p.may_defs.is_superset(&gpr("rax")));
    assert!(p.must_defs.is_disjoint(&gpr("rax")));
    let p = project(&[
        mov("XMM6", 128, constant("0", 128)),
        mov("YMM6", 256, read("YMM7", 256)),
        mov("RAX", 64, low(read("XMM6", 128), 64)),
    ]);
    assert!(p.uses.contains("state:other"));
    assert_eq!(p.must_defs, gpr("rax"));
}

#[test]
fn vector_stores_keep_payload_and_address_origins_without_memory_kills() {
    for width in [128, 256] {
        let memory = Var {
            name: "mem".into(),
            index: 0,
            virtual_: false,
            width: 0,
            type_: "mem".into(),
        };
        let p = project(&[Stmt::Move {
            var: memory.clone(),
            value: Expr::Store {
                width,
                mem: Box::new(Expr::Var { var: memory }),
                addr: Box::new(read("RSP", 64)),
                value: Box::new(if width == 128 {
                    low(read("YMM6", 256), 128)
                } else {
                    read("YMM6", 256)
                }),
            },
        }]);
        assert_eq!(
            p.uses,
            gpr("rsp")
                .union(&["state:other".into()].into())
                .cloned()
                .collect()
        );
        assert_eq!(p.may_defs, ["memory:any".into()].into());
        assert!(p.must_defs.is_empty());
    }
}

#[test]
fn vector_load_self_move_and_conditional_writes_never_kill_aggregate_origins() {
    let load = Expr::Load {
        width: 128,
        mem: Box::new(Expr::Var {
            var: Var {
                name: "mem".into(),
                index: 0,
                virtual_: false,
                width: 0,
                type_: "mem".into(),
            },
        }),
        addr: Box::new(read("RAX", 64)),
    };
    for bil in [
        vec![mov("XMM6", 128, load)],
        vec![mov("YMM6", 256, read("YMM6", 256))],
        vec![Stmt::If {
            condition: read("ZF", 1),
            yes: vec![mov("YMM6", 256, constant("0", 256))],
            no: vec![],
        }],
    ] {
        let p = project(&bil);
        assert!(p.may_defs.contains("state:other"));
        assert!(!p.must_defs.contains("state:other"));
        assert!(p.uses.is_subset(&Catalogue.locations()));
        assert!(
            p.gaps
                .contains(&"vector-state-coarsened:state:other".into())
        );
    }
}

#[test]
fn vector_banks_stay_independent_despite_shared_public_location() {
    let p = project(&[
        mov("YMM6", 256, constant("0", 256)),
        Stmt::If {
            condition: low(read("XMM7", 128), 1),
            yes: vec![mov("RAX", 64, read("RBX", 64))],
            no: vec![mov("RAX", 64, constant("0", 64))],
        },
    ]);
    assert!(p.uses.is_superset(&gpr("rbx")));
    assert!(p.uses.contains("state:other"));
    assert!(!p.must_defs.contains("state:other"));
}

#[test]
fn captured_movaps_namespace_is_admitted_but_alignment_exception_stays_explicit() {
    let bil: Vec<Stmt> =
        serde_json::from_str(include_str!("fixtures/vector/movaps-bil.json")).unwrap();
    let e = admission::capabilities(&bil).err().unwrap();
    assert_eq!(
        e.to_string(),
        "unmodeled BIL control/special/loop semantics"
    );
    assert!(!admission::ordinary_unknown(&bil, &[0x0f, 0x29], &e));
    let p = project(&bil[..1]);
    assert!(p.uses.contains("state:other"));
    assert_eq!(p.may_defs, ["memory:any".into()].into());
    assert!(p.must_defs.is_empty());
}
