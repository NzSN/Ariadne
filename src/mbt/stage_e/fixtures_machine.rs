use crate::machine_state as ms;
use crate::{Edge, EdgeKind};
use std::collections::{BTreeMap, BTreeSet};

fn id(name: &str) -> ms::StateId {
    ms::StateId(name.into())
}
fn values(names: &[&str]) -> ms::ValueSet {
    names
        .iter()
        .map(|name| ms::AbstractValue((*name).into()))
        .collect()
}
fn state(status: ms::Status, rax: &[&str], zf: &[&str]) -> ms::AbstractState {
    ms::AbstractState {
        status,
        valuation: [("rax".into(), values(rax)), ("zf".into(), values(zf))].into(),
    }
}
fn edge(src: u64, dst: u64, kind: EdgeKind) -> Edge {
    Edge { src, dst, kind }
}
fn step(src: u64, dst: u64, kind: EdgeKind, before: &str, after: &str) -> ms::StateStep {
    ms::StateStep {
        edge: edge(src, dst, kind),
        before: id(before),
        after: id(after),
    }
}
pub fn request() -> ms::Request {
    let nodes: crate::AddressSet = (1..=5).collect();
    let mut effects: BTreeMap<_, _> = nodes
        .iter()
        .map(|&site| (site, ms::Effects::default()))
        .collect();
    effects.get_mut(&1).unwrap().may_defs.insert("rax".into());
    effects.get_mut(&1).unwrap().must_defs.insert("rax".into());
    effects.get_mut(&2).unwrap().may_defs.insert("zf".into());
    effects.get_mut(&2).unwrap().must_defs.insert("zf".into());
    effects.get_mut(&2).unwrap().uses.insert("rax".into());
    effects.get_mut(&3).unwrap().uses.insert("zf".into());
    ms::Request {
        snapshot_id: "machine-state-snapshot".into(),
        nodes: nodes.clone(),
        structural_edges: [
            edge(1, 2, EdgeKind::Next),
            edge(2, 3, EdgeKind::Next),
            edge(3, 4, EdgeKind::Taken),
            edge(3, 5, EdgeKind::Fallthrough),
        ]
        .into(),
        value_domain: [
            ("rax".into(), values(&["zero", "five", "other"])),
            ("zf".into(), values(&["false", "true"])),
        ]
        .into(),
        catalogue: [
            (
                id("entry"),
                state(
                    ms::Status::Running,
                    &["zero", "five", "other"],
                    &["false", "true"],
                ),
            ),
            (
                id("rax-five"),
                state(ms::Status::Running, &["five"], &["false", "true"]),
            ),
            (
                id("zf-true"),
                state(ms::Status::Running, &["five"], &["true"]),
            ),
            (
                id("returned"),
                state(ms::Status::Returned, &["five"], &["true"]),
            ),
        ]
        .into(),
        entry_states: [(1, [id("entry")].into())].into(),
        effects,
        steps: [
            step(1, 2, EdgeKind::Next, "entry", "rax-five"),
            step(2, 3, EdgeKind::Next, "rax-five", "zf-true"),
            step(3, 4, EdgeKind::Taken, "zf-true", "zf-true"),
        ]
        .into(),
        terminal_transitions: [
            ms::TerminalTransition {
                site: 4,
                before: id("zf-true"),
                after: id("returned"),
                outcome: ms::TerminalOutcome::Returned,
            },
            ms::TerminalTransition {
                site: 5,
                before: id("zf-true"),
                after: id("returned"),
                outcome: ms::TerminalOutcome::Returned,
            },
        ]
        .into(),
        complete_sites: nodes,
        adapter_obligations: BTreeSet::new(),
    }
}
