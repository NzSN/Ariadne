//! Self-contained Stage 5.2 publication and deterministic assessment replay.
use super::{Error, invalid, strict_json_with_limit};
use crate::investigation::frame_connections::{digest, replay_connections};
use crate::investigation::{
    BoundFrameConnections, FRAME_CONNECTION_SCHEMA, FrameConnectionAnalysis, FrameConnectionLimits,
};
use serde::{Deserialize, Serialize};
use std::fmt::Write as _;
use std::io::Write;

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Report {
    schema: String,
    publication_binding: String,
    // A UTF-8 JSON string preserves the source publication byte for byte,
    // including its existing schema, dictionary and publication binding.
    source_json: String,
    assessment: FrameConnectionAnalysis,
}
fn binding(source: &str, assessment: &FrameConnectionAnalysis) -> Result<String, Error> {
    digest(
        &(FRAME_CONNECTION_SCHEMA, source, assessment),
        assessment.limits.max_output_bytes,
    )
}
struct Bounded {
    bytes: Vec<u8>,
    cap: usize,
}
impl Write for Bounded {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if bytes.len() > self.cap.saturating_sub(self.bytes.len()) {
            return Err(std::io::Error::other("connection publication byte budget"));
        }
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
pub fn render_json(bound: &BoundFrameConnections) -> Result<String, Error> {
    let source_json = super::frame_structure::render_json(bound.source())?;
    if source_json.len() > bound.analysis().limits.max_source_bytes {
        return Err(invalid("connection source publication byte cap"));
    }
    let publication_binding = binding(&source_json, bound.analysis())?;
    // Borrow the assessment; a second graph/proof copy is unnecessary.
    #[derive(Serialize)]
    struct Borrowed<'a> {
        schema: &'a str,
        publication_binding: String,
        source_json: &'a str,
        assessment: &'a FrameConnectionAnalysis,
    }
    let mut output = Bounded {
        bytes: Vec::new(),
        cap: bound.analysis().limits.max_output_bytes,
    };
    serde_json::to_writer_pretty(
        &mut output,
        &Borrowed {
            schema: FRAME_CONNECTION_SCHEMA,
            publication_binding,
            source_json: &source_json,
            assessment: bound.analysis(),
        },
    )?;
    output.write_all(b"\n")?;
    Ok(String::from_utf8(output.bytes)?)
}
/// Decode under an independent host policy. A smaller verifier policy rejects
/// producer work rather than silently replacing the producer's scope/prefix.
pub fn decode(bytes: &[u8], host: &FrameConnectionLimits) -> Result<BoundFrameConnections, Error> {
    decode_inner(bytes, host, None)
}
pub fn decode_expected(
    bytes: &[u8],
    host: &FrameConnectionLimits,
    expected: &str,
) -> Result<BoundFrameConnections, Error> {
    decode_inner(bytes, host, Some(expected))
}
fn policy_within(producer: &serde_json::Value, host: &serde_json::Value) -> bool {
    match (producer, host) {
        (serde_json::Value::Object(a), serde_json::Value::Object(b)) => a
            .iter()
            .all(|(k, v)| b.get(k).is_some_and(|h| policy_within(v, h))),
        (a, b) => a.as_u64().zip(b.as_u64()).is_some_and(|(a, b)| a <= b),
    }
}
fn decode_inner(
    bytes: &[u8],
    host: &FrameConnectionLimits,
    expected: Option<&str>,
) -> Result<BoundFrameConnections, Error> {
    host.validate()?;
    let value = strict_json_with_limit(bytes, host.max_input_bytes)?;
    let source = value["source_json"]
        .as_str()
        .ok_or_else(|| invalid("connection source JSON absent"))?;
    if source.len() > host.max_source_bytes {
        return Err(invalid("connection source host byte cap"));
    }
    let a = &value["assessment"];
    if !policy_within(&a["limits"], &serde_json::to_value(host)?) {
        return Err(invalid("connection producer limits exceed verifier policy"));
    }
    // Enforce host collection bounds before typed copies and replay. Input bytes
    // independently bound strings, nesting and the source/proof payload.
    for (field, cap) in [
        ("nodes", host.max_graph_nodes),
        ("edges", host.max_graph_edges),
        ("context_edges", host.max_graph_edges),
        ("components", host.max_graph_nodes),
        ("condensation", host.max_graph_edges),
        ("examples", host.max_count_bound.saturating_sub(1)),
    ] {
        if a[field].as_array().is_none_or(|items| items.len() > cap) {
            return Err(invalid(format!("connection {field} host collection cap")));
        }
    }
    for field in ["forward", "backward", "corridor"] {
        if a[field]
            .as_array()
            .is_none_or(|v| v.len() > host.max_graph_nodes)
        {
            return Err(invalid("connection reachability collection host cap"));
        }
    }
    let cardinality = |container: &str, field: &str, cap: usize| -> Result<(), Error> {
        let mut total = 0usize;
        for item in a[container]
            .as_array()
            .ok_or_else(|| invalid("connection collection absent"))?
        {
            let items = item[field]
                .as_array()
                .ok_or_else(|| invalid("connection nested collection absent"))?;
            total = total
                .checked_add(items.len())
                .ok_or_else(|| invalid("connection collection overflow"))?;
            if total > cap {
                return Err(invalid("connection nested collection host cap"));
            }
        }
        Ok(())
    };
    cardinality("components", "members", host.max_graph_nodes)?;
    cardinality("condensation", "original_edges", host.max_graph_edges)?;
    cardinality("examples", "nodes", host.max_work_bytes / 128)?;
    cardinality("examples", "edges", host.max_work_bytes / 128)?;
    if a["frontiers"].as_array().is_none_or(|v| {
        v.len()
            > host
                .max_graph_nodes
                .saturating_mul(16)
                .saturating_add(host.max_graph_edges)
    }) {
        return Err(invalid("connection frontier host collection cap"));
    }
    let raw: Report = serde_json::from_value(value)?;
    raw.assessment.limits.validate()?;
    if raw.schema != FRAME_CONNECTION_SCHEMA
        || expected.is_some_and(|id| id != raw.publication_binding)
        || binding(&raw.source_json, &raw.assessment)? != raw.publication_binding
    {
        return Err(invalid("connection schema or publication binding changed"));
    }
    // Source admission is exclusively the existing strict structural decoder.
    let source = super::frame_structure::decode(raw.source_json.as_bytes(), &host.structural)?;
    replay_connections(source, &raw.assessment)
}
struct Text {
    value: String,
    cap: usize,
}
impl std::fmt::Write for Text {
    fn write_str(&mut self, s: &str) -> std::fmt::Result {
        if s.len() > self.cap.saturating_sub(self.value.len()) {
            return Err(std::fmt::Error);
        }
        self.value.push_str(s);
        Ok(())
    }
}
pub fn render_text(bound: &BoundFrameConnections) -> Result<String, Error> {
    let a = bound.analysis();
    let mut text = Text {
        value: String::new(),
        cap: a.limits.max_output_bytes,
    };
    writeln!(
        text,
        "{} frames {}:{}\nsource={}\nscope={}\nconnection={:?}\ngraph={:?} corridor={:?} SCC={:?} example-search={:?}",
        FRAME_CONNECTION_SCHEMA,
        a.from_frame,
        a.to_frame,
        a.source_fingerprint,
        a.scope_id,
        a.connection,
        a.graph_status,
        a.corridor_status,
        a.scc_status,
        a.examples_status
    )?;
    writeln!(
        text,
        "represented nodes={} edges={} corridor={} SCCs={} cyclic={} examples={} < NP={}",
        a.nodes.len(),
        a.edges.len(),
        a.corridor.len(),
        a.components.len(),
        a.components.iter().filter(|c| c.cyclic).count(),
        a.examples.len(),
        a.example_count_bound
    )?;
    if !a.conditional_on.is_empty() {
        writeln!(text, "CONDITIONAL on {}", a.conditional_on.join(", "))?;
    }
    for premise in &a.premises {
        writeln!(text, "premise: {premise}")?;
    }
    for gap in &a.anchor_gaps {
        writeln!(text, "anchor unavailable: {gap}")?;
    }
    writeln!(
        text,
        "forward={:?}\nbackward={:?}\ncorridor={:?}",
        a.forward, a.backward, a.corridor
    )?;
    for edge in &a.edges {
        writeln!(text, "edge: {:?}", edge)?;
    }
    for edge in &a.context_edges {
        writeln!(text, "context: {:?}", edge)?;
    }
    for edge in &a.condensation {
        writeln!(text, "condensation: {:?}", edge)?;
    }
    for c in &a.components {
        writeln!(
            text,
            "SCC {} cyclic={} members={:?}",
            c.id, c.cyclic, c.members
        )?;
    }
    for f in &a.frontiers {
        writeln!(
            text,
            "frontier frame={} VA=0x{:x} {:?} {:?}",
            f.frame, f.gap.site, f.gap.kind, f.relation
        )?;
    }
    for e in &a.examples {
        writeln!(
            text,
            "example {} first-shortest={} nodes={:?} edges={:?}",
            e.id, e.shortest_in_represented_graph, e.nodes, e.edges
        )?;
    }
    writeln!(text, "work receipts: {:?}", a.receipts)?;
    Ok(text.value)
}
pub fn render_dot(bound: &BoundFrameConnections) -> Result<String, Error> {
    let a = bound.analysis();
    let mut text = Text {
        value: String::new(),
        cap: a.limits.max_output_bytes,
    };
    text.write_str("digraph frame_connections {\n  rankdir=LR;\n")?;
    writeln!(
        text,
        "  label=\"frames {}:{}; source={}; connection={:?}; corridor={:?}; SCC={:?}; examples={:?}; nonexhaustive; conditional={}\";",
        a.from_frame,
        a.to_frame,
        a.source_fingerprint,
        a.connection,
        a.corridor_status,
        a.scc_status,
        a.examples_status,
        a.conditional_on.join(",")
    )?;
    for n in &a.nodes {
        writeln!(
            text,
            "  f{}_v{:x} [label=\"frame {}: 0x{:x}\",style=filled,fillcolor={}];",
            n.frame,
            n.site,
            n.frame,
            n.site,
            if a.corridor.binary_search(n).is_ok() {
                "lightblue"
            } else {
                "white"
            }
        )?;
    }
    for e in &a.edges {
        writeln!(
            text,
            "  f{}_v{:x} -> f{}_v{:x} [label=\"{:?}\"];",
            e.src.frame, e.src.site, e.dst.frame, e.dst.site, e.kind
        )?;
    }
    for e in &a.context_edges {
        writeln!(
            text,
            "  f{}_v{:x} -> f{}_v{:x} [style=dashed,color=gray,label=\"{:?}: {}\"];",
            e.edge.src.frame,
            e.edge.src.site,
            e.edge.dst.frame,
            e.edge.dst.site,
            e.edge.kind,
            e.reason
        )?;
    }
    for c in &a.components {
        if c.cyclic {
            writeln!(
                text,
                "  subgraph cluster_{} {{ label=\"structural cycle\";",
                c.id
            )?;
            for n in &c.members {
                writeln!(text, "    f{}_v{:x};", n.frame, n.site)?;
            }
            text.write_str("  }\n")?;
        }
    }
    for (i, f) in a.frontiers.iter().enumerate() {
        writeln!(
            text,
            "  gap{i} [shape=note,label=\"frame {} 0x{:x}: {:?} / {:?}\"];",
            f.frame, f.gap.site, f.gap.kind, f.relation
        )?;
        writeln!(
            text,
            "  f{}_v{:x} -> gap{i} [style=dashed];",
            f.frame, f.gap.site
        )?;
    }
    text.write_str("}\n")?;
    Ok(text.value)
}
