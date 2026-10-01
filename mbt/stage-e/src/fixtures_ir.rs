//! Finite normalized model fixtures from `Specs/AriadneLLVMIRExample.tla`.
use ariadne::llvm_ir as ir;
use std::collections::{BTreeMap, BTreeSet};

fn b(name: &str) -> ir::BlockId {
    ir::BlockId(name.into())
}
fn i(name: &str) -> ir::InstructionId {
    ir::InstructionId(name.into())
}
fn v(name: &str) -> ir::ValueId {
    ir::ValueId(name.into())
}
fn c(name: &str) -> ir::CalleeId {
    ir::CalleeId(name.into())
}
fn instruction(block: &str, index: u32, uses: &[&str]) -> ir::InstructionInfo {
    ir::InstructionInfo {
        block: b(block),
        index,
        uses: uses.iter().map(|name| v(name)).collect(),
        phi_incoming: BTreeSet::new(),
        memory_preds: BTreeSet::new(),
        call_targets: BTreeSet::new(),
    }
}
fn block(
    terminator: &str,
    kind: ir::TerminatorKind,
    successors: &[(&str, ir::ControlEdgeKind)],
) -> ir::BlockInfo {
    ir::BlockInfo {
        terminator: i(terminator),
        kind,
        successors: successors
            .iter()
            .map(|(dst, kind)| ir::Successor {
                dst: b(dst),
                kind: *kind,
            })
            .collect(),
    }
}
pub fn request() -> ir::Request {
    use ir::ControlEdgeKind as K;
    use ir::TerminatorKind as T;
    let blocks = [
        (
            b("entry"),
            block("entry.br", T::Br, &[("left", K::True), ("right", K::False)]),
        ),
        (b("left"), block("left.br", T::Br, &[("join", K::Next)])),
        (b("right"), block("right.br", T::Br, &[("join", K::Next)])),
        (b("join"), block("join.ret", T::Ret, &[])),
    ]
    .into();
    let mut instructions: BTreeMap<_, _> = [
        (i("entry.br"), instruction("entry", 0, &["arg.cond"])),
        (i("left.def"), instruction("left", 0, &[])),
        (
            i("left.store"),
            instruction("left", 1, &["arg.ptr", "left.value"]),
        ),
        (i("left.br"), instruction("left", 2, &[])),
        (i("right.def"), instruction("right", 0, &[])),
        (
            i("right.store"),
            instruction("right", 1, &["arg.ptr", "right.value"]),
        ),
        (i("right.br"), instruction("right", 2, &[])),
        (
            i("join.phi"),
            instruction("join", 0, &["left.value", "right.value"]),
        ),
        (i("join.call"), instruction("join", 1, &["joined.value"])),
        (i("join.load"), instruction("join", 2, &["arg.ptr"])),
        (
            i("join.combine"),
            instruction("join", 3, &["joined.value", "loaded.value"]),
        ),
        (i("join.ret"), instruction("join", 4, &["result.value"])),
    ]
    .into();
    instructions.get_mut(&i("join.phi")).unwrap().phi_incoming = [
        ir::PhiIncoming {
            pred: b("left"),
            value: v("left.value"),
        },
        ir::PhiIncoming {
            pred: b("right"),
            value: v("right.value"),
        },
    ]
    .into();
    instructions.get_mut(&i("join.load")).unwrap().memory_preds =
        [i("left.store"), i("right.store"), i("join.call")].into();
    instructions
        .get_mut(&i("join.call"))
        .unwrap()
        .call_targets
        .insert(c("possible.callee"));
    let mut values = BTreeMap::new();
    for name in ["arg.cond", "arg.ptr"] {
        values.insert(
            v(name),
            ir::ValueInfo {
                kind: ir::ValueKind::Argument,
                def_site: i("entry.br"),
            },
        );
    }
    for (value, site) in [
        ("left.value", "left.def"),
        ("right.value", "right.def"),
        ("joined.value", "join.phi"),
        ("loaded.value", "join.load"),
        ("result.value", "join.combine"),
    ] {
        values.insert(
            v(value),
            ir::ValueInfo {
                kind: ir::ValueKind::Instruction,
                def_site: i(site),
            },
        );
    }
    ir::Request {
        artifact_id: "fixture.bc.sha256".into(),
        module_id: "fixture-module".into(),
        function_id: "fixture-function".into(),
        verified_ir: true,
        blocks,
        entry_block: b("entry"),
        instructions,
        values,
        phi_nodes: [i("join.phi")].into(),
        call_sites: [i("join.call")].into(),
        callees: [c("possible.callee")].into(),
        complete_calls: BTreeSet::new(),
        adapter_obligations: BTreeSet::new(),
        slice_seeds: [i("join.ret")].into(),
    }
}
