//! Deterministic presentation of the analyzer's result, with no I/O or graph
//! execution. This module renders `Specs/Ariadne.tla` facts; decoder/input
//! evidence must be retained and presented separately by callers.
//!
//! ```
//! use ariadne::render::{render, Format};
//! # let result = ariadne::AnalysisResult {
//! #   snapshot_id: "example".into(), state: ariadne::AnalysisState::default(),
//! #   missing_slice_seeds: Default::default(),
//! # };
//! let text = render(&result, Format::Text);
//! let graphviz = render(&result, Format::Dot);
//! assert!(text.contains("snapshot: \"example\""));
//! assert!(graphviz.starts_with("digraph Ariadne"));
//! ```

use crate::{
    Address, AddressSet, AnalysisResult, ByteSource, Definition, DefinitionOrigin, EdgeKind,
    ObligationReason, Phase,
};
use std::collections::BTreeMap;
use std::fmt::Write;
type ObligationsBySite = BTreeMap<Address, Vec<ObligationReason>>;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Format {
    Text,
    Dot,
}

/// Render one result without changing it. Ordered collections retain stable
/// output; addresses are full-width hexadecimal. DOT is a non-strict CFG so
/// parallel labeled edges survive. It does not infer data-dependency edges
/// from reaching definitions (the result does not contain instruction uses).
///
/// This is a presentation format, not a machine-readable serialization schema.
/// The renderer assumes an analyzer-produced result and does not revalidate
/// its semantics. `scope_closed` remains relative to the recovery contract.
pub fn render(result: &AnalysisResult, format: Format) -> String {
    let mut obligations = ObligationsBySite::new();
    for obligation in &result.state.obligations {
        obligations
            .entry(obligation.site)
            .or_default()
            .push(obligation.reason);
    }
    match format {
        Format::Text => text(result, &obligations),
        Format::Dot => dot(result, &obligations),
    }
}
fn va(address: Address) -> String {
    format!("0x{address:016x}")
}
fn node(address: Address) -> String {
    format!("n_{address:016x}")
}
fn quoted(value: &str) -> String {
    let mut out = String::from("\"");
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => {
                write!(out, "\\u{{{:x}}}", c as u32).unwrap();
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
// DOT quoting is separate from human string quoting: backslash substitutions
// such as \N in user metadata must stay literal, never become Graphviz macros.
fn dot_string(value: &str) -> String {
    let mut out = String::from("\"");
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
fn phase(p: Phase) -> &'static str {
    match p {
        Phase::Recover => "recover",
        Phase::Dataflow => "dataflow",
        Phase::Slice => "slice",
        Phase::Done => "done",
    }
}
fn kind(k: EdgeKind) -> &'static str {
    match k {
        EdgeKind::Next => "next",
        EdgeKind::Taken => "taken",
        EdgeKind::Fallthrough => "fallthrough",
        EdgeKind::Jump => "jump",
        EdgeKind::Indirect => "indirect",
        EdgeKind::Summary => "summary",
        EdgeKind::Call => "call",
    }
}
fn reason(r: ObligationReason) -> &'static str {
    match r {
        ObligationReason::Unavailable => "unavailable",
        ObligationReason::DecodeFailed => "decode-failed",
        ObligationReason::IndirectTargets => "indirect-targets",
        ObligationReason::CallTargets => "call-targets",
    }
}
fn origin(d: &Definition) -> String {
    format!(
        "{} <- {}@{}",
        quoted(&d.loc),
        match d.origin {
            DefinitionOrigin::Entry => "entry",
            DefinitionOrigin::Instruction => "instruction",
        },
        va(d.site)
    )
}
fn addresses(set: &AddressSet) -> String {
    format!(
        "[{}]",
        set.iter().map(|&a| va(a)).collect::<Vec<_>>().join(", ")
    )
}
fn nodes(r: &AnalysisResult) -> AddressSet {
    let s = &r.state;
    let mut set: AddressSet = s
        .pending
        .iter()
        .chain(&s.visited)
        .chain(&s.decoded)
        .chain(&s.slice)
        .chain(&r.missing_slice_seeds)
        .chain(s.provenance.keys())
        .chain(s.reaching.keys())
        .copied()
        .collect();
    set.extend(s.edges.iter().flat_map(|e| [e.src, e.dst]));
    set.extend(s.obligations.iter().map(|o| o.site));
    set.extend(s.reaching.values().flat_map(|ds| ds.iter().map(|d| d.site)));
    set
}
fn state(r: &AnalysisResult, a: Address) -> &'static str {
    if r.state.decoded.contains(&a) {
        "decoded"
    } else if r.state.visited.contains(&a) {
        "visited, not decoded"
    } else if r.state.pending.contains(&a) {
        "pending"
    } else {
        "unvisited"
    }
}
fn source(r: &AnalysisResult, a: Address) -> &'static str {
    match r.state.provenance.get(&a) {
        Some(ByteSource::Captured) => "captured",
        Some(ByteSource::File) => "file",
        Some(ByteSource::Unavailable) => "no successful decode",
        None => "not recorded",
    }
}
fn notes(r: &AnalysisResult, a: Address, obligations: &ObligationsBySite) -> Vec<String> {
    let mut notes = Vec::new();
    if r.state.slice.contains(&a) {
        notes.push("in data slice".into());
    }
    if r.missing_slice_seeds.contains(&a) {
        notes.push("missing slice seed".into());
    }
    for &r in obligations.get(&a).into_iter().flatten() {
        notes.push(format!("obligation: {}", reason(r)));
    }
    notes
}
fn text(r: &AnalysisResult, obligations: &ObligationsBySite) -> String {
    let mut out = String::new();
    let s = &r.state;
    writeln!(out, "Ariadne analysis (render v1)").unwrap();
    writeln!(out, "snapshot: {}", quoted(&r.snapshot_id)).unwrap();
    writeln!(out, "phase: {}", phase(s.phase)).unwrap();
    writeln!(
        out,
        "scope_closed: {} (recovery only; relative to supplied inputs)",
        r.scope_closed()
    )
    .unwrap();
    for (label, set) in [
        ("pending", &s.pending),
        ("visited", &s.visited),
        ("decoded", &s.decoded),
        ("data_slice", &s.slice),
        ("missing_slice_seeds", &r.missing_slice_seeds),
    ] {
        writeln!(out, "{label}: {}", addresses(set)).unwrap();
    }
    writeln!(out, "\nNodes:").unwrap();
    for a in nodes(r) {
        writeln!(out, "  {}: {}; source={}", va(a), state(r, a), source(r, a)).unwrap();
        for note in notes(r, a, obligations) {
            writeln!(out, "    {note}").unwrap();
        }
    }
    writeln!(out, "\nControl-flow edges (structural possibilities):").unwrap();
    if s.edges.is_empty() {
        writeln!(out, "  (none)").unwrap();
    }
    for e in &s.edges {
        writeln!(
            out,
            "  {} --{}--> {}{}",
            va(e.src),
            kind(e.kind),
            va(e.dst),
            if e.kind.is_local() {
                ""
            } else {
                " [excluded from local discovery/dataflow]"
            }
        )
        .unwrap();
    }
    writeln!(
        out,
        "\nReaching definitions (possible origins BEFORE each address):"
    )
    .unwrap();
    if s.reaching.is_empty() {
        writeln!(out, "  (none recorded)").unwrap();
    }
    for (a, definitions) in &s.reaching {
        writeln!(out, "  {}:", va(*a)).unwrap();
        if definitions.is_empty() {
            writeln!(out, "    (none)").unwrap();
        }
        for d in definitions {
            writeln!(out, "    {}", origin(d)).unwrap();
        }
    }
    writeln!(out, "\nUnresolved recovery obligations:").unwrap();
    if s.obligations.is_empty() {
        writeln!(out, "  (none)").unwrap();
    }
    for o in &s.obligations {
        writeln!(out, "  {}: {}", va(o.site), reason(o.reason)).unwrap();
    }
    writeln!(
        out,
        "\nScope: analyzer facts only. Input/preparation evidence is separate."
    )
    .unwrap();
    writeln!(
        out,
        "A completed data slice does not establish executed paths or a crash cause."
    )
    .unwrap();
    out
}
fn dot(r: &AnalysisResult, obligations: &ObligationsBySite) -> String {
    let mut out = String::from("digraph Ariadne {\n");
    let caption = format!(
        "Ariadne analysis | snapshot {}\nphase: {} | recovery scope closed: {}\nobligations: {} | missing slice seeds: {}\nBlue fill: data slice; dashed edge: call (excluded from local analysis)\nReaching definitions are possible origins; see node tooltips.\nAnalyzer facts only; input/preparation evidence is separate.",
        quoted(&r.snapshot_id),
        phase(r.state.phase),
        r.scope_closed(),
        r.state.obligations.len(),
        r.missing_slice_seeds.len()
    );
    writeln!(
        out,
        "  graph [rankdir=TB, labelloc=t, label={}];",
        dot_string(&caption)
    )
    .unwrap();
    writeln!(
        out,
        "  node [shape=box, fontname=\"monospace\"];\n  edge [fontname=\"monospace\"];"
    )
    .unwrap();
    for a in nodes(r) {
        let notes = notes(r, a, obligations);
        let mut label = format!("{}\n{}\nsource: {}", va(a), state(r, a), source(r, a));
        for note in &notes {
            write!(label, "\n{note}").unwrap();
        }
        let mut tooltip = format!("{}\nReaching definitions BEFORE this address:", va(a));
        match r.state.reaching.get(&a) {
            Some(ds) if !ds.is_empty() => {
                for d in ds {
                    write!(tooltip, "\n{}", origin(d)).unwrap();
                }
            }
            Some(_) => tooltip.push_str("\n(none)"),
            None => tooltip.push_str("\n(not recorded)"),
        }
        let in_slice = r.state.slice.contains(&a);
        let unresolved = obligations.contains_key(&a) || r.missing_slice_seeds.contains(&a);
        let style = if r.state.decoded.contains(&a) {
            "filled"
        } else {
            "filled,dashed"
        };
        writeln!(
            out,
            "  {} [label={}, tooltip={}, style={}, fillcolor={}, color={}, penwidth={}];",
            node(a),
            dot_string(&label),
            dot_string(&tooltip),
            dot_string(style),
            dot_string(if in_slice { "#dbeafe" } else { "#f3f4f6" }),
            dot_string(if unresolved { "#b45309" } else { "#334155" }),
            if unresolved { 2 } else { 1 }
        )
        .unwrap();
    }
    for e in &r.state.edges {
        writeln!(
            out,
            "  {} -> {} [label={}, style={}, color={}];",
            node(e.src),
            node(e.dst),
            dot_string(kind(e.kind)),
            dot_string(if e.kind.is_local() { "solid" } else { "dashed" }),
            dot_string(if e.kind.is_local() {
                "#334155"
            } else {
                "#64748b"
            })
        )
        .unwrap();
    }
    out.push_str("}\n");
    out
}
