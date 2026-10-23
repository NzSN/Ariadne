//! Supplied-BIL regression controls for consumers of repeated instructions.
//! These check possible writes and stale-value refusal, not REP arithmetic.
use super::*;
use crate::bap::{address as memory_address, ast::Var};
use crate::effects::MemoryAccessRole;

fn var(name: &str, width: usize, virtual_: bool) -> Var {
    Var {
        name: name.into(),
        index: 0,
        virtual_,
        width,
        type_: if width == 0 { "mem" } else { "imm" }.into(),
    }
}
fn register(name: &str) -> Var {
    var(name, 64, false)
}
fn read(var: &Var) -> Expr {
    Expr::Var { var: var.clone() }
}
fn number(n: u64) -> Expr {
    Expr::Int {
        value: format!("{n}:64u"),
    }
}
fn assign(var: &Var, value: Expr) -> Stmt {
    Stmt::Move {
        var: var.clone(),
        value,
    }
}
fn add(value: Expr, amount: u64) -> Expr {
    Expr::Binop {
        op: 18,
        lhs: Box::new(value),
        rhs: Box::new(number(amount)),
    }
}
fn load(address: Expr) -> Expr {
    Expr::Load {
        width: 8,
        mem: Box::new(read(&var("mem", 0, false))),
        addr: Box::new(address),
    }
}
fn store(address: Expr) -> Stmt {
    let memory = var("mem", 0, false);
    assign(
        &memory,
        Expr::Store {
            width: 8,
            mem: Box::new(read(&memory)),
            addr: Box::new(address),
            value: Box::new(Expr::Int {
                value: "1:8u".into(),
            }),
        },
    )
}
fn assert_unknown(term: &Term, width: u8) {
    assert_eq!(term.width, width);
    assert!(matches!(term.kind, TermKind::Unknown));
}

#[test]
fn loop_addresses_cover_iteration_support_and_never_claim_first_iteration() {
    let source = register("RSI");
    let destination = register("RDI");
    let count = register("RCX");
    let temporary = var("pointer", 64, true);
    let ast = vec![
        assign(&temporary, read(&source)),
        Stmt::While {
            condition: read(&count),
            body: vec![
                assign(&var("byte", 8, true), load(read(&temporary))),
                store(read(&destination)),
                assign(
                    &temporary,
                    Expr::Ite {
                        condition: Box::new(read(&var("DF", 1, false))),
                        yes: Box::new(add(read(&temporary), u64::MAX)),
                        no: Box::new(add(read(&temporary), 1)),
                    },
                ),
                assign(&destination, add(read(&destination), 1)),
                assign(&count, add(read(&count), u64::MAX)),
            ],
        },
        assign(&var("later", 8, true), load(read(&temporary))),
        store(read(&destination)),
    ];
    let accesses = memory_address::extract(&ast, 0x401000);
    assert_eq!(accesses.len(), 4);
    assert_eq!(accesses[0].role, MemoryAccessRole::Load);
    assert_eq!(accesses[1].role, MemoryAccessRole::Store);
    for access in &accesses {
        assert!(access.expression.is_none());
        assert!(access.address_inputs.contains("gpr:rsi:0"));
        assert!(access.address_inputs.contains("gpr:rdi:7"));
        assert!(access.address_inputs.contains("gpr:rcx:0"));
        assert!(access.address_inputs.contains("flag:df"));
    }
    for access in &accesses[..2] {
        assert!(
            access
                .gaps
                .iter()
                .any(|gap| gap == "iteration-dependent-memory-access")
        );
    }
}

#[test]
fn zero_iterations_do_not_turn_body_assignments_into_post_loop_constants() {
    let source = register("RSI");
    let temporary = var("pointer", 64, true);
    let ast = vec![
        assign(&temporary, read(&source)),
        Stmt::While {
            condition: number(0),
            body: vec![assign(&temporary, number(0x9000)), store(number(0x8000))],
        },
        assign(&var("later", 8, true), load(read(&temporary))),
    ];
    let accesses = memory_address::extract(&ast, 0x401000);
    assert_eq!(accesses.len(), 2);
    assert!(accesses.iter().all(|access| access.expression.is_none()));
    assert!(accesses[1].address_inputs.contains("gpr:rsi:0"));
    assert!(
        accesses[0]
            .gaps
            .contains(&"iteration-dependent-memory-access".into())
    );
}

#[test]
fn loop_inside_branch_cannot_restore_stale_address_bindings() {
    let source = register("RSI");
    let temporary = var("pointer", 64, true);
    let ast = vec![
        assign(&temporary, number(0x8000)),
        Stmt::If {
            condition: read(&var("ZF", 1, false)),
            yes: vec![Stmt::While {
                condition: read(&register("RCX")),
                body: vec![assign(&temporary, read(&source))],
            }],
            no: vec![],
        },
        assign(&var("later", 8, true), load(read(&temporary))),
        assign(&var("constant", 8, true), load(number(0x1234))),
    ];
    let accesses = memory_address::extract(&ast, 0x401000);
    assert_eq!(accesses.len(), 2);
    assert!(accesses[0].expression.is_none());
    assert!(accesses[0].address_inputs.contains("gpr:rsi:0"));
    assert_eq!(accesses[1].expression.as_ref().unwrap().constant, 0x1234);
}

#[test]
fn target_transfer_havocs_architectural_and_virtual_loop_writes() {
    let rax = register("RAX");
    let rbx = register("RBX");
    let preserved = register("RDX");
    let temporary = var("temporary", 64, true);
    let ast = vec![
        assign(&rax, number(0x1000)),
        assign(&temporary, number(0x2000)),
        assign(&preserved, number(0x3000)),
        Stmt::While {
            condition: number(0),
            body: vec![
                assign(&rax, add(read(&rax), 1)),
                Stmt::If {
                    condition: read(&var("DF", 1, false)),
                    yes: vec![Stmt::While {
                        condition: read(&register("RCX")),
                        body: vec![assign(&temporary, number(0x4000))],
                    }],
                    no: vec![],
                },
            ],
        },
        assign(&rbx, read(&temporary)),
        Stmt::Jump { target: read(&rax) },
    ];
    let transfer = extract(&ast, 0x401000, &[0xf3, 0xa4]).unwrap();
    assert_unknown(&transfer.outputs[&rax.key()], 64);
    assert_unknown(&transfer.outputs[&rbx.key()], 64);
    assert_unknown(transfer.jump.as_ref().unwrap(), 64);
    assert_eq!(transfer.outputs[&preserved.key()].number(), Some(0x3000));
    assert!(!transfer.outputs.contains_key(&temporary.key()));
}

#[test]
fn loop_writes_invalidate_stable_table_address_even_when_nested() {
    let pointer = register("RSI");
    let ast = vec![Stmt::While {
        condition: number(0),
        body: vec![Stmt::If {
            condition: read(&var("ZF", 1, false)),
            yes: vec![assign(&pointer, add(read(&pointer), 1))],
            no: vec![],
        }],
    }];
    assert!(writes_address_bil(&ast, &[pointer.key()].into()));
    assert!(!writes_address_bil(&ast, &[register("RDX").key()].into()));
    assert!(memory_write_bil(&ast));
}

#[test]
fn non_loop_transfer_keeps_existing_scalar_behavior() {
    let rax = register("RAX");
    let temporary = var("temporary", 64, true);
    let ast = vec![
        assign(&temporary, number(0x8000)),
        assign(&rax, add(read(&temporary), 4)),
        Stmt::Jump { target: read(&rax) },
    ];
    let transfer = extract(&ast, 0x401000, &[0x90]).unwrap();
    assert_eq!(transfer.outputs[&rax.key()].number(), Some(0x8004));
    assert_eq!(transfer.jump.as_ref().unwrap().number(), Some(0x8004));
}
