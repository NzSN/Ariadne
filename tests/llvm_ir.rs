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
fn names<T: Ord>(values: impl IntoIterator<Item = T>) -> BTreeSet<T> {
    values.into_iter().collect()
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
fn fixture() -> ir::Request {
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

#[test]
fn four_block_phi_memory_and_call_fixture_matches_the_model() {
    let mut analyzer = ir::Analyzer::new(fixture()).unwrap();
    assert_eq!(analyzer.state().phase, ir::Phase::Slice);
    assert_eq!(analyzer.state().slice, [i("join.ret")].into());
    let mut steps = 0;
    while analyzer.step() {
        steps += 1;
    }
    assert!(steps <= analyzer.request().instructions.len() + 1);
    let result = analyzer.finish();
    assert_eq!(result.state().phase, ir::Phase::Done);
    assert_eq!(
        result.state().slice,
        names([
            i("left.def"),
            i("left.store"),
            i("right.def"),
            i("right.store"),
            i("join.phi"),
            i("join.call"),
            i("join.load"),
            i("join.combine"),
            i("join.ret"),
        ])
    );
    assert_eq!(
        result.request().control_graph(),
        names([
            ir::ControlEdge {
                src: b("entry"),
                dst: b("left"),
                kind: ir::ControlEdgeKind::True
            },
            ir::ControlEdge {
                src: b("entry"),
                dst: b("right"),
                kind: ir::ControlEdgeKind::False
            },
            ir::ControlEdge {
                src: b("left"),
                dst: b("join"),
                kind: ir::ControlEdgeKind::Next
            },
            ir::ControlEdge {
                src: b("right"),
                dst: b("join"),
                kind: ir::ControlEdgeKind::Next
            },
        ])
    );
    assert_eq!(
        result.request().call_graph(),
        names([ir::CallEdge {
            site: i("join.call"),
            callee: c("possible.callee")
        }])
    );
    assert_eq!(
        result.request().obligations(),
        names([ir::Obligation {
            site: i("join.call"),
            reason: ir::ObligationReason::CallTargets
        }])
    );
    assert!(!result.state().slice.contains(&i("entry.br")));
}

#[test]
fn verifier_phi_predecessors_and_memory_domains_are_contract_checks() {
    let mut request = fixture();
    request.verified_ir = false;
    assert_eq!(request.validate().unwrap_err().field, "verified_ir");

    let mut request = fixture();
    request
        .instructions
        .get_mut(&i("join.phi"))
        .unwrap()
        .phi_incoming
        .remove(&ir::PhiIncoming {
            pred: b("right"),
            value: v("right.value"),
        });
    assert_eq!(request.validate().unwrap_err().field, "phi_incoming");

    let mut request = fixture();
    request
        .instructions
        .get_mut(&i("join.load"))
        .unwrap()
        .memory_preds
        .insert(i("ghost"));
    assert_eq!(request.validate().unwrap_err().field, "memory_preds");

    let mut request = fixture();
    request
        .blocks
        .get_mut(&b("join"))
        .unwrap()
        .successors
        .insert(ir::Successor {
            dst: b("entry"),
            kind: ir::ControlEdgeKind::Next,
        });
    assert_eq!(request.validate().unwrap_err().field, "terminator");

    let mut request = fixture();
    request.complete_calls.insert(i("join.ret"));
    assert_eq!(request.validate().unwrap_err().field, "sets");
}

#[test]
fn empty_seed_and_unaccepted_memory_predecessors_remain_explicit() {
    let mut request = fixture();
    request.slice_seeds.clear();
    let result = ir::analyze(request).unwrap();
    assert!(result.state().slice.is_empty());
    assert_eq!(result.request().obligations().len(), 1);

    let mut request = fixture();
    request
        .instructions
        .get_mut(&i("join.load"))
        .unwrap()
        .memory_preds
        .clear();
    request.adapter_obligations.insert(ir::AdapterObligation {
        site: i("join.load"),
        reason: ir::AdapterObligationReason::UnknownMemoryAlias,
    });
    let result = ir::analyze(request).unwrap();
    assert!(!result.state().slice.contains(&i("left.store")));
    assert!(
        result
            .request()
            .obligations()
            .iter()
            .any(|row| row.site == i("join.load"))
    );
}

#[test]
fn multiple_phi_nodes_are_valid_before_non_phi_instructions() {
    let mut request = fixture();
    for info in request.instructions.values_mut() {
        if info.block == b("join") && info.index >= 1 {
            info.index += 1;
        }
    }
    let mut second = instruction("join", 1, &["left.value", "right.value"]);
    second.phi_incoming = request.instructions[&i("join.phi")].phi_incoming.clone();
    request.instructions.insert(i("join.phi2"), second);
    request.phi_nodes.insert(i("join.phi2"));
    request.values.insert(
        v("joined2.value"),
        ir::ValueInfo {
            kind: ir::ValueKind::Instruction,
            def_site: i("join.phi2"),
        },
    );
    request.validate().unwrap();

    request.instructions.get_mut(&i("join.call")).unwrap().index = 1;
    request.instructions.get_mut(&i("join.phi2")).unwrap().index = 2;
    assert_eq!(request.validate().unwrap_err().field, "phi_incoming");
}
