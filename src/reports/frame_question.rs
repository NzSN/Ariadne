//! Self-contained question publication; every conclusion is replayed from sources.
use super::{Error, invalid, strict_json_with_limit};
use crate::investigation::frame_connections::digest;
use crate::investigation::frame_question::{EvidenceData, replay_question};
use crate::investigation::{
    BoundFrameQuestion, FRAME_QUESTION_SCHEMA, FrameQuestionAssessment, FrameQuestionLimits,
    FrameQuestionSource,
};
use serde::{Deserialize, Serialize};
use std::fmt::Write as _;
use std::io::Write;
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Report {
    schema: String,
    publication_binding: String,
    source_kind: String,
    source_json: String,
    revisions: Vec<String>,
    evidence: EvidenceData,
    assessment: FrameQuestionAssessment,
}
struct Bounded {
    bytes: Vec<u8>,
    cap: usize,
}
impl Write for Bounded {
    fn write(&mut self, b: &[u8]) -> std::io::Result<usize> {
        if b.len() > self.cap.saturating_sub(self.bytes.len()) {
            return Err(std::io::Error::other("question publication byte cap"));
        }
        self.bytes.extend_from_slice(b);
        Ok(b.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
fn binding(
    kind: &str,
    source: &str,
    revisions: &[String],
    evidence: &EvidenceData,
    a: &FrameQuestionAssessment,
) -> Result<String, Error> {
    digest(
        &(FRAME_QUESTION_SCHEMA, kind, source, revisions, evidence, a),
        a.limits.max_output_bytes,
    )
}
pub fn render_json(bound: &BoundFrameQuestion) -> Result<String, Error> {
    let a = bound.assessment();
    let (source_kind, source_json) = bound.source().publication()?;
    let mut revisions = Vec::new();
    let mut size = source_json.len();
    if size > a.limits.max_source_bytes {
        return Err(invalid("question source publication byte cap"));
    }
    for s in bound.revisions() {
        let json = super::frame_structure::render_json(s)?;
        size = size
            .checked_add(json.len())
            .ok_or_else(|| invalid("question source byte overflow"))?;
        if size > a.limits.max_source_bytes {
            return Err(invalid("question source chain byte cap"));
        }
        revisions.push(json);
    }
    let id = binding(&source_kind, &source_json, &revisions, bound.evidence(), a)?;
    #[derive(Serialize)]
    struct Borrowed<'a> {
        schema: &'a str,
        publication_binding: String,
        source_kind: &'a str,
        source_json: &'a str,
        revisions: &'a [String],
        evidence: &'a EvidenceData,
        assessment: &'a FrameQuestionAssessment,
    }
    let mut out = Bounded {
        bytes: Vec::new(),
        cap: a.limits.max_output_bytes,
    };
    serde_json::to_writer_pretty(
        &mut out,
        &Borrowed {
            schema: FRAME_QUESTION_SCHEMA,
            publication_binding: id,
            source_kind: &source_kind,
            source_json: &source_json,
            revisions: &revisions,
            evidence: bound.evidence(),
            assessment: a,
        },
    )?;
    out.write_all(b"\n")?;
    Ok(String::from_utf8(out.bytes)?)
}
pub fn decode(bytes: &[u8], host: &FrameQuestionLimits) -> Result<BoundFrameQuestion, Error> {
    decode_inner(bytes, host, None)
}
pub fn decode_expected(
    bytes: &[u8],
    host: &FrameQuestionLimits,
    expected: &str,
) -> Result<BoundFrameQuestion, Error> {
    decode_inner(bytes, host, Some(expected))
}
fn within(a: &serde_json::Value, b: &serde_json::Value) -> bool {
    match (a, b) {
        (serde_json::Value::Object(a), serde_json::Value::Object(b)) => a
            .iter()
            .all(|(k, v)| b.get(k).is_some_and(|h| within(v, h))),
        _ => a.as_u64().zip(b.as_u64()).is_some_and(|(a, b)| a <= b),
    }
}
fn decode_inner(
    bytes: &[u8],
    host: &FrameQuestionLimits,
    expected: Option<&str>,
) -> Result<BoundFrameQuestion, Error> {
    host.validate()?;
    let value = strict_json_with_limit(bytes, host.max_input_bytes)?;
    if !within(&value["assessment"]["limits"], &serde_json::to_value(host)?) {
        return Err(invalid(
            "question producer limits exceed independent verifier policy",
        ));
    }
    let source = value["source_json"]
        .as_str()
        .ok_or_else(|| invalid("question source absent"))?;
    let revisions = value["revisions"]
        .as_array()
        .ok_or_else(|| invalid("question revision array absent"))?;
    if revisions.len() > host.max_revisions {
        return Err(invalid("question revision host cap"));
    }
    let mut size = source.len();
    for r in revisions {
        size = size
            .checked_add(
                r.as_str()
                    .ok_or_else(|| invalid("question revision source must be JSON text"))?
                    .len(),
            )
            .ok_or_else(|| invalid("question source size overflow"))?;
    }
    if size > host.max_source_bytes {
        return Err(invalid("question source host byte cap"));
    }
    for (field, cap) in [
        ("values", host.max_proofs),
        ("origins", host.max_candidates.saturating_add(2)),
        ("serviced_tasks", host.max_proofs),
        (
            "obligations",
            host.structural
                .max_graph_nodes
                .saturating_mul(16)
                .saturating_add(host.max_proofs),
        ),
    ] {
        if value["assessment"][field]
            .as_array()
            .is_none_or(|v| v.len() > cap)
        {
            return Err(invalid(format!("question {field} raw collection host cap")));
        }
    }
    let a = &value["assessment"];
    if a["question"]["conditions"]
        .as_array()
        .is_none_or(|v| v.len() > host.max_proofs)
        || a["revisions"]
            .as_array()
            .is_none_or(|v| v.len() > host.max_revisions.saturating_add(1))
        || a["conditional_on"]
            .as_array()
            .is_none_or(|v| v.len() > host.structural.guard.max_sites)
    {
        return Err(invalid("question nested collection host cap"));
    }
    for v in a["values"].as_array().expect("checked values") {
        if v["context"]
            .as_array()
            .is_none_or(|v| v.len() > host.max_expression_depth.saturating_add(1))
        {
            return Err(invalid("question value context host cap"));
        }
    }
    let mut pairs = 0usize;
    for v in a["origins"].as_array().expect("checked origins") {
        pairs = pairs
            .checked_add(
                v["pairs"]
                    .as_array()
                    .ok_or_else(|| invalid("question writer pair array"))?
                    .len(),
            )
            .ok_or_else(|| invalid("question pair count overflow"))?;
    }
    if pairs > host.max_pair_checks
        || value["evidence"]["control_reads"]
            .as_array()
            .is_none_or(|v| v.len() > host.max_tasks)
        || value["evidence"]["completed_frames"]
            .as_array()
            .is_none_or(|v| v.len() > host.structural.max_frames)
    {
        return Err(invalid("question evidence/pair collection host cap"));
    }
    if !a["witness"].is_null()
        && a["witness"]["nodes"]
            .as_array()
            .is_none_or(|v| v.len() > host.max_expression_depth)
    {
        return Err(invalid("question witness host cap"));
    }
    if serde_json::to_vec(a)?.len() > host.max_proof_bytes
        || serde_json::to_vec(&value["evidence"])?.len() > host.max_proof_bytes
    {
        return Err(invalid("question proof host byte cap"));
    }
    let raw: Report = serde_json::from_value(value)?;
    raw.assessment.limits.validate()?;
    if raw.schema != FRAME_QUESTION_SCHEMA
        || expected.is_some_and(|id| id != raw.publication_binding)
        || binding(
            &raw.source_kind,
            &raw.source_json,
            &raw.revisions,
            &raw.evidence,
            &raw.assessment,
        )? != raw.publication_binding
    {
        return Err(invalid("question schema/publication binding changed"));
    }
    for (r, cap) in [
        (&raw.assessment.layers.resolution, host.resolver_work),
        (&raw.assessment.layers.feasibility, host.constraint_work),
        (&raw.assessment.layers.values, host.numerical_work),
        (&raw.assessment.layers.origins, host.origin_work),
    ] {
        if r.elapsed_ms > raw.assessment.elapsed_total_ms
            || (r.work > 0
                && (raw.assessment.limits.deadline_ms == 0
                    || raw.assessment.limits.total_deadline_ms == 0))
            || (r.reason.as_deref() == Some("total-deadline")
                && raw.assessment.elapsed_total_ms < raw.assessment.limits.total_deadline_ms)
            || r.work > cap
            || r.reason.as_deref() == Some("deadline")
                && r.elapsed_ms < raw.assessment.limits.deadline_ms
        {
            return Err(invalid("question invalid work/clock receipt"));
        }
    }
    let source: FrameQuestionSource = match raw.source_kind.as_str() {
        "structure" => {
            super::frame_structure::decode(raw.source_json.as_bytes(), &host.structural)?.into()
        }
        "connections" => super::frame_connections::decode(
            raw.source_json.as_bytes(),
            &crate::investigation::FrameConnectionLimits {
                structural: host.structural.clone(),
                max_input_bytes: host.max_input_bytes,
                max_source_bytes: host.max_source_bytes,
                ..Default::default()
            },
        )?
        .into(),
        _ => return Err(invalid("question source kind unsupported")),
    };
    let revisions = raw
        .revisions
        .iter()
        .map(|s| super::frame_structure::decode(s.as_bytes(), &host.structural))
        .collect::<Result<_, _>>()?;
    replay_question(source, revisions, raw.evidence, &raw.assessment, host)
}
struct Text {
    text: String,
    cap: usize,
}
impl std::fmt::Write for Text {
    fn write_str(&mut self, s: &str) -> std::fmt::Result {
        if s.len() > self.cap.saturating_sub(self.text.len()) {
            return Err(std::fmt::Error);
        }
        self.text.push_str(s);
        Ok(())
    }
}
pub fn render_text(bound: &BoundFrameQuestion) -> Result<String, Error> {
    let a = bound.assessment();
    let mut out = Text {
        text: String::new(),
        cap: a.limits.max_output_bytes,
    };
    writeln!(
        out,
        "{}\nscope={}\nquestion={:?}\nverdict={:?}\nlayers={:?}\nconditional_on={:?}",
        FRAME_QUESTION_SCHEMA, a.scope_id, a.question, a.verdict, a.layers, a.conditional_on
    )?;
    for r in &a.revisions {
        writeln!(out, "source revision: {:?}", r)?;
    }
    for p in &a.premises {
        writeln!(out, "premise: {p}")?;
    }
    if let Some(r) = &a.resolution {
        for row in &r.report.resolutions {
            writeln!(
                out,
                "dispatch {} targets={:?} complete={} unresolved={:?}",
                row.site, row.targets, row.complete, row.unresolved
            )?;
        }
    }
    if let Some(w) = &a.witness {
        writeln!(out, "model witness (not recording): {:?}", w)?;
    }
    for v in &a.values {
        writeln!(out, "value: {:?}", v)?;
    }
    writeln!(
        out,
        "candidate count={:?} universe={:?}",
        a.candidate_count, a.candidate_universe_sha256
    )?;
    for c in &a.origins {
        writeln!(out, "origin: {:?}", c)?;
    }
    for o in &a.obligations {
        writeln!(
            out,
            "unknown: frame={} site={:?} {} — {}",
            o.frame, o.site, o.kind, o.requirement
        )?;
    }
    Ok(out.text)
}
pub fn render_dot(bound: &BoundFrameQuestion) -> Result<String, Error> {
    let a = bound.assessment();
    let mut out = Text {
        text: String::new(),
        cap: a.limits.max_output_bytes,
    };
    let label = serde_json::to_string(&format!(
        "{:?}; normal-flow model; execution not supplied; conditional={}",
        a.verdict,
        a.conditional_on.join(",")
    ))?;
    writeln!(
        out,
        "digraph frame_question {{\n  rankdir=LR;\n  label={label};"
    )?;
    writeln!(
        out,
        "  question [shape=box,label=\"question {}:0x{:x}\"];",
        a.question.question.frame(),
        a.question.question.site()
    )?;
    for (i, v) in a.values.iter().enumerate() {
        let label = serde_json::to_string(&format!(
            "frame {} 0x{:x} {:?} GPR{} {:?}",
            v.point.frame, v.point.site, v.point.moment, v.bank, v.value
        ))?;
        writeln!(out, "  value{i} [label={label}];\n  question -> value{i};")?;
    }
    for (i, c) in a.origins.iter().enumerate() {
        let label = serde_json::to_string(&format!("{} {:?}: {}", c.kind, c.site, c.disposition))?;
        writeln!(
            out,
            "  origin{i} [label={label}];\n  question -> origin{i} [style=dashed];"
        )?;
    }
    for (i, o) in a.obligations.iter().enumerate() {
        let label = serde_json::to_string(&format!("frame {} {:?}: {}", o.frame, o.site, o.kind))?;
        writeln!(
            out,
            "  gap{i} [shape=note,label={label}];\n  question -> gap{i} [style=dotted];"
        )?;
    }
    writeln!(out, "}}")?;
    Ok(out.text)
}

#[cfg(test)]
pub(crate) fn rehash_for_test(v: &mut serde_json::Value) -> Result<(), Error> {
    let r: Report = serde_json::from_value(v.clone())?;
    v["publication_binding"] = serde_json::json!(binding(
        &r.source_kind,
        &r.source_json,
        &r.revisions,
        &r.evidence,
        &r.assessment
    )?);
    Ok(())
}
