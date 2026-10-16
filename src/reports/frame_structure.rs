//! Separate self-contained structural reports, validated by exact prefix replay.
use super::frame_structure_dictionary::{Dictionary, Entry};
use super::{Error, invalid, strict_json_with_limit};
use crate::investigation::frame_structure::{
    CONDITIONAL_FRAME_STRUCTURE_PRODUCER, CONDITIONAL_FRAME_STRUCTURE_SCHEMA,
};
use crate::investigation::frame_structure::{RecoveryProofs, replay_frame_recovery};
use crate::investigation::{
    BoundFrameStructure, CapturedFrameChain, EvidenceContext, FRAME_STRUCTURE_PRODUCER,
    FRAME_STRUCTURE_SCHEMA, FrameStructureDiagnostic, FrameStructureLimits, FrameStructureQuestion,
    bind_frame_structure,
};
use crate::recovery::{RecoveryLimits, RecoveryReceipt, RecoveryStop};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::io::Write;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Role {
    Alignment,
    Chain,
    Request,
    Context,
    Guard,
    Target,
    Composition,
    DecoderRecords,
    Preparation,
    Projection,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Reference {
    owner: Option<usize>,
    role: Role,
    id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ProducerLimits {
    max_visits: u64,
    deadline_ms: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Stop {
    Drained,
    VisitLimit,
    Deadline,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Receipt {
    visits: u64,
    elapsed_ms: u64,
    stop: Stop,
}
impl From<RecoveryReceipt> for Receipt {
    fn from(r: RecoveryReceipt) -> Self {
        Self {
            visits: r.visits,
            elapsed_ms: r.elapsed_ms,
            stop: match r.stop {
                RecoveryStop::Drained => Stop::Drained,
                RecoveryStop::VisitLimit => Stop::VisitLimit,
                RecoveryStop::Deadline => Stop::Deadline,
            },
        }
    }
}
impl From<Receipt> for RecoveryReceipt {
    fn from(r: Receipt) -> Self {
        Self {
            visits: r.visits,
            elapsed_ms: r.elapsed_ms,
            stop: match r.stop {
                Stop::Drained => RecoveryStop::Drained,
                Stop::VisitLimit => RecoveryStop::VisitLimit,
                Stop::Deadline => RecoveryStop::Deadline,
            },
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Frame {
    frame: usize,
    request: Reference,
    context: Reference,
    guard: Option<Reference>,
    target: Option<Reference>,
    composition: Option<Reference>,
    decoder_records: Reference,
    preparation: Reference,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    alignment: Option<Reference>,
    limits: ProducerLimits,
    receipt: Receipt,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawReport {
    schema: String,
    producer: String,
    semantic_backend: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    conditional_on: Vec<String>,
    structure_id: String,
    question: FrameStructureQuestion,
    policy: FrameStructureLimits,
    chain: Reference,
    frames: Vec<Frame>,
    diagnostics: Vec<FrameStructureDiagnostic>,
    projection: Reference,
    evidence: Vec<Entry>,
}

fn reference(
    dictionary: &mut Dictionary,
    owner: Option<usize>,
    role: Role,
    value: Value,
    limits: &FrameStructureLimits,
) -> Result<Reference, Error> {
    Ok(Reference {
        owner,
        role,
        id: dictionary.intern(value, limits)?,
    })
}
fn resolve(
    dictionary: &mut Dictionary,
    r: &Reference,
    owner: Option<usize>,
    role: Role,
    limits: &FrameStructureLimits,
) -> Result<Value, Error> {
    if r.owner != owner || r.role != role {
        return Err(invalid(
            "structural evidence reference owner or role changed",
        ));
    }
    dictionary.resolve(&r.id, limits)
}
fn optional<T: serde::de::DeserializeOwned>(
    dictionary: &mut Dictionary,
    r: Option<&Reference>,
    owner: usize,
    role: Role,
    limits: &FrameStructureLimits,
) -> Result<Option<T>, Error> {
    r.map(|r| {
        Ok(serde_json::from_value(resolve(
            dictionary,
            r,
            Some(owner),
            role,
            limits,
        )?)?)
    })
    .transpose()
}

fn projection(bound: &BoundFrameStructure) -> Result<Value, Error> {
    let mut controls=bound.recoveries().iter().map(|(frame,b)| {
        let s=b.recovery().state();
        let addresses=|set:&crate::AddressSet|set.iter().map(|a|format!("0x{a:016x}")).collect::<Vec<_>>();
        json!({"frame":frame,"phase":"recover","visited":addresses(&s.visited),"decoded":addresses(&s.decoded),
            "pending":addresses(&s.pending),"provenance":s.provenance.iter().map(|(a,p)|json!({"site":format!("0x{a:016x}"),"source":format!("{p:?}")})).collect::<Vec<_>>(),
            "obligations":s.obligations.iter().map(|o|json!({"site":format!("0x{:016x}",o.site),"reason":format!("{:?}",o.reason)})).collect::<Vec<_>>(),
            "visits":b.recovery().receipt().visits,"dataflow_actions":0,"slice_actions":0})
    }).collect::<Vec<_>>();
    if bound.is_conditional() {
        for control in &mut controls {
            control["conditional_on"] = json!(bound.hypothesis_ids());
        }
    }
    let mut value = json!({"frames":bound.frames(),"links":bound.links(),"diagnostics":bound.diagnostics(),"controls":controls});
    if bound.is_conditional() {
        value["conditional_on"] = json!(bound.hypothesis_ids());
    }
    Ok(value)
}

fn identity(raw: &RawReport) -> Result<String, Error> {
    use sha2::{Digest, Sha256};
    struct HashWriter(Sha256);
    impl Write for HashWriter {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.0.update(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    // The ID is outside its own hash domain. A borrowed envelope avoids copying
    // either the raw dictionary or an entire serialized report to hash it.
    #[derive(Serialize)]
    struct Binding<'a> {
        schema: &'a str,
        producer: &'a str,
        semantic_backend: &'a str,
        #[serde(skip_serializing_if = "Vec::is_empty")]
        conditional_on: &'a Vec<String>,
        question: &'a FrameStructureQuestion,
        policy: &'a FrameStructureLimits,
        chain: &'a Reference,
        frames: &'a [Frame],
        diagnostics: &'a [FrameStructureDiagnostic],
        projection: &'a Reference,
        evidence: &'a [Entry],
    }
    let mut writer = HashWriter(Sha256::new());
    writer.write_all(if raw.schema == CONDITIONAL_FRAME_STRUCTURE_SCHEMA {
        b"ariadne.frame-structure-binding/v2\n"
    } else {
        b"ariadne.frame-structure-binding/v1\n"
    })?;
    serde_json::to_writer(
        &mut writer,
        &Binding {
            schema: &raw.schema,
            producer: &raw.producer,
            semantic_backend: &raw.semantic_backend,
            conditional_on: &raw.conditional_on,
            question: &raw.question,
            policy: &raw.policy,
            chain: &raw.chain,
            frames: &raw.frames,
            diagnostics: &raw.diagnostics,
            projection: &raw.projection,
            evidence: &raw.evidence,
        },
    )?;
    Ok(format!("{:x}", writer.0.finalize()))
}

struct BoundedWriter {
    bytes: Vec<u8>,
    limit: usize,
}
impl Write for BoundedWriter {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if bytes.len() > self.limit.saturating_sub(self.bytes.len()) {
            return Err(std::io::Error::other("structural publication byte limit"));
        }
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

/// Serialize original inputs, shared source/proof dictionary and exact control
/// projection. No omitted proof or clipped graph is accepted as a publication.
pub fn render_json(bound: &BoundFrameStructure) -> Result<String, Error> {
    let limits = bound.limits();
    limits.validate()?;
    let mut dictionary = Dictionary::new();
    let chain = reference(
        &mut dictionary,
        None,
        Role::Chain,
        serde_json::to_value(bound.chain())?,
        limits,
    )?;
    let mut frames = Vec::new();
    for (index, b) in bound.recoveries() {
        let request = reference(
            &mut dictionary,
            Some(*index),
            Role::Request,
            crate::bap::core_adapter::encode_request(b.request())?,
            limits,
        )?;
        let context = reference(
            &mut dictionary,
            Some(*index),
            Role::Context,
            serde_json::to_value(b.context())?,
            limits,
        )?;
        let p = b.proofs();
        let guard = p
            .guard
            .as_ref()
            .map(|v| {
                reference(
                    &mut dictionary,
                    Some(*index),
                    Role::Guard,
                    serde_json::to_value(v)?,
                    limits,
                )
            })
            .transpose()?;
        let target = p
            .target
            .as_ref()
            .map(|v| {
                reference(
                    &mut dictionary,
                    Some(*index),
                    Role::Target,
                    serde_json::to_value(v)?,
                    limits,
                )
            })
            .transpose()?;
        let composition = p
            .composition
            .as_ref()
            .map(|v| {
                reference(
                    &mut dictionary,
                    Some(*index),
                    Role::Composition,
                    serde_json::to_value(v)?,
                    limits,
                )
            })
            .transpose()?;
        let decoder_records = reference(
            &mut dictionary,
            Some(*index),
            Role::DecoderRecords,
            serde_json::to_value(&p.decoder_records)?,
            limits,
        )?;
        let preparation = reference(
            &mut dictionary,
            Some(*index),
            Role::Preparation,
            serde_json::to_value(&p.preparation)?,
            limits,
        )?;
        let l = b.recovery().limits();
        let alignment = p
            .alignment
            .as_ref()
            .map(|report| {
                reference(
                    &mut dictionary,
                    Some(*index),
                    Role::Alignment,
                    serde_json::to_value(report)?,
                    limits,
                )
            })
            .transpose()?;
        frames.push(Frame {
            frame: *index,
            request,
            context,
            guard,
            target,
            composition,
            decoder_records,
            preparation,
            alignment,
            limits: ProducerLimits {
                max_visits: l.max_visits,
                deadline_ms: l.deadline_ms,
            },
            receipt: (*b.recovery().receipt()).into(),
        });
    }
    let projection = reference(
        &mut dictionary,
        None,
        Role::Projection,
        projection(bound)?,
        limits,
    )?;
    let mut raw = RawReport {
        schema: if bound.is_conditional() {
            CONDITIONAL_FRAME_STRUCTURE_SCHEMA
        } else {
            FRAME_STRUCTURE_SCHEMA
        }
        .into(),
        producer: if bound.is_conditional() {
            CONDITIONAL_FRAME_STRUCTURE_PRODUCER
        } else {
            FRAME_STRUCTURE_PRODUCER
        }
        .into(),
        semantic_backend: "bap".into(),
        conditional_on: bound.hypothesis_ids(),
        structure_id: String::new(),
        question: bound.question().clone(),
        policy: limits.clone(),
        chain,
        frames,
        diagnostics: bound.diagnostics().to_vec(),
        projection,
        evidence: dictionary.entries(),
    };
    raw.structure_id = identity(&raw)?;
    let mut writer = BoundedWriter {
        bytes: Vec::new(),
        limit: limits.max_output_bytes,
    };
    serde_json::to_writer(&mut writer, &raw)?;
    writer.write_all(b"\n")?;
    Ok(String::from_utf8(writer.bytes)?)
}

fn intersect(
    producer: &FrameStructureLimits,
    host: &FrameStructureLimits,
) -> Result<FrameStructureLimits, Error> {
    fn merge(a: &mut Value, b: &Value) -> Result<(), Error> {
        if let (Some(x), Some(y)) = (a.as_u64(), b.as_u64()) {
            *a = json!(x.min(y));
            return Ok(());
        }
        let a = a
            .as_object_mut()
            .ok_or_else(|| invalid("structural policy must contain finite integer caps"))?;
        let b = b
            .as_object()
            .ok_or_else(|| invalid("structural policy shape changed"))?;
        if a.len() != b.len() {
            return Err(invalid("structural policy shape changed"));
        }
        for (key, value) in a {
            merge(
                value,
                b.get(key)
                    .ok_or_else(|| invalid("structural policy field absent"))?,
            )?;
        }
        Ok(())
    }
    let mut value = serde_json::to_value(producer)?;
    merge(&mut value, &serde_json::to_value(host)?)?;
    let limits: FrameStructureLimits = serde_json::from_value(value)?;
    limits.validate()?;
    Ok(limits)
}

fn encoded_size<T: Serialize>(value: &T, limit: usize) -> Result<usize, Error> {
    struct Counter {
        used: usize,
        limit: usize,
    }
    impl Write for Counter {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            if bytes.len() > self.limit.saturating_sub(self.used) {
                return Err(std::io::Error::other(
                    "structural aggregate evidence byte limit",
                ));
            }
            self.used += bytes.len();
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut counter = Counter { used: 0, limit };
    serde_json::to_writer(&mut counter, value)?;
    Ok(counter.used)
}

/// Decode under independent host caps; only complete evidence validation and
/// deterministic recovery replay can construct the privately owned result.
/// This checks consistency under the declared capture identity, not the
/// authenticity of an externally supplied capture. Use `decode_expected` when
/// an independently retained structural binding is available.
pub fn decode(bytes: &[u8], host: &FrameStructureLimits) -> Result<BoundFrameStructure, Error> {
    decode_inner(bytes, host, None)
}

/// Reject a changed report binding before proof replay. The expected binding
/// must come from a trusted publication receipt, not from the report itself.
pub fn decode_expected(
    bytes: &[u8],
    host: &FrameStructureLimits,
    expected_binding: &str,
) -> Result<BoundFrameStructure, Error> {
    decode_inner(bytes, host, Some(expected_binding))
}

fn decode_inner(
    bytes: &[u8],
    host: &FrameStructureLimits,
    expected_binding: Option<&str>,
) -> Result<BoundFrameStructure, Error> {
    host.validate()?;
    let value = strict_json_with_limit(bytes, host.max_input_bytes)?;
    // Inspect collection cardinalities before allocating their typed copies or
    // hashing/replaying their payload. The byte cap was checked before parsing.
    let frames = value["frames"]
        .as_array()
        .ok_or_else(|| invalid("structural frame array absent"))?;
    let evidence = value["evidence"]
        .as_array()
        .ok_or_else(|| invalid("structural evidence array absent"))?;
    let diagnostics = value["diagnostics"]
        .as_array()
        .ok_or_else(|| invalid("structural diagnostic array absent"))?;
    if frames.len() > host.max_frames
        || evidence.len() > host.max_dictionary_entries
        || diagnostics.len() > host.max_frames.saturating_mul(4)
    {
        return Err(invalid("structural raw collection host limit"));
    }
    if let Some(scope) = value.get("conditional_on") {
        let ids = scope
            .as_array()
            .ok_or_else(|| invalid("structural conditional scope must be an array"))?;
        if ids.len() > host.max_graph_nodes {
            return Err(invalid("structural conditional scope host limit"));
        }
        for id in ids {
            if !id.as_str().is_some_and(|id| {
                id.len() == 64
                    && id
                        .bytes()
                        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            }) {
                return Err(invalid(
                    "structural conditional scope identifier must be canonical 64-digit lowercase hex",
                ));
            }
        }
    }
    let has_alignment_fields = frames.iter().any(|frame| frame.get("alignment").is_some());
    let has_conditional_scope = value.get("conditional_on").is_some();
    let raw: RawReport = serde_json::from_value(value)?;
    let conditional = raw.schema == CONDITIONAL_FRAME_STRUCTURE_SCHEMA;
    let limits = intersect(&raw.policy, host)?;
    if raw.conditional_on.len() > limits.max_graph_nodes {
        return Err(invalid("structural conditional scope policy limit"));
    }
    if expected_binding.is_some_and(|expected| expected != raw.structure_id) {
        return Err(invalid(
            "structural report differs from trusted publication binding",
        ));
    }
    if (!conditional
        && (raw.schema != FRAME_STRUCTURE_SCHEMA || has_alignment_fields || has_conditional_scope))
        || (conditional
            && (!raw.frames.iter().any(|frame| frame.alignment.is_some())
                || raw.conditional_on.is_empty()))
        || raw.producer
            != if conditional {
                CONDITIONAL_FRAME_STRUCTURE_PRODUCER
            } else {
                FRAME_STRUCTURE_PRODUCER
            }
        || raw.semantic_backend != "bap"
        || identity(&raw)? != raw.structure_id
    {
        return Err(invalid(
            "structural schema, producer, semantic backend or binding changed",
        ));
    }
    if raw.frames.len() > limits.max_frames
        || raw.diagnostics.len() > limits.max_frames.saturating_mul(4)
    {
        return Err(invalid("structural frame/diagnostic limit"));
    }
    let mut dictionary = Dictionary::from_entries(raw.evidence, &limits)?;
    let chain: CapturedFrameChain = serde_json::from_value(resolve(
        &mut dictionary,
        &raw.chain,
        None,
        Role::Chain,
        &limits,
    )?)?;
    if chain.frames.len() > limits.max_frames
        || chain.limits.max_frames > limits.max_frames
        || chain.limits.max_runtime_entries > limits.max_runtime_entries
        || chain.limits.max_read_bytes > limits.max_unwind_read_bytes
        || chain.limits.max_stack_adjustment > limits.max_stack_adjustment
        || chain.read_bytes > limits.max_unwind_read_bytes
    {
        return Err(invalid("structural unwind host policy"));
    }
    let claimed = resolve(
        &mut dictionary,
        &raw.projection,
        None,
        Role::Projection,
        &limits,
    )?;
    let maps = claimed["frames"]
        .as_array()
        .ok_or_else(|| invalid("structural projected maps absent"))?;
    let mut projected_edges = 0usize;
    for map in maps {
        projected_edges = projected_edges
            .checked_add(
                map["edges"]
                    .as_array()
                    .ok_or_else(|| invalid("structural projected edges absent"))?
                    .len(),
            )
            .ok_or_else(|| invalid("structural projected edge overflow"))?;
        if projected_edges > limits.max_graph_edges {
            return Err(invalid("structural aggregate projected edge limit"));
        }
    }
    let mut visits = 0u64;
    let mut nodes = 0usize;
    let mut owned = 0usize;
    let mut proof_bytes = 0usize;
    let mut seen = BTreeSet::new();
    let mut loaded = Vec::new();
    for f in raw.frames {
        if !seen.insert(f.frame) {
            return Err(invalid("duplicate structural frame"));
        }
        visits = visits
            .checked_add(f.receipt.visits)
            .ok_or_else(|| invalid("structural replay visits overflow"))?;
        if visits > limits.max_replay_visits as u64 {
            return Err(invalid("structural aggregate replay visit limit"));
        }
        let request = crate::investigation::frame_paths::decode_guard_request(&resolve(
            &mut dictionary,
            &f.request,
            Some(f.frame),
            Role::Request,
            &limits,
        )?)?;
        let context: EvidenceContext = serde_json::from_value(resolve(
            &mut dictionary,
            &f.context,
            Some(f.frame),
            Role::Context,
            &limits,
        )?)?;
        let proofs = RecoveryProofs {
            alignment: optional(
                &mut dictionary,
                f.alignment.as_ref(),
                f.frame,
                Role::Alignment,
                &limits,
            )?,
            guard: optional(
                &mut dictionary,
                f.guard.as_ref(),
                f.frame,
                Role::Guard,
                &limits,
            )?,
            target: optional(
                &mut dictionary,
                f.target.as_ref(),
                f.frame,
                Role::Target,
                &limits,
            )?,
            composition: optional(
                &mut dictionary,
                f.composition.as_ref(),
                f.frame,
                Role::Composition,
                &limits,
            )?,
            decoder_records: serde_json::from_value(resolve(
                &mut dictionary,
                &f.decoder_records,
                Some(f.frame),
                Role::DecoderRecords,
                &limits,
            )?)?,
            preparation: serde_json::from_value(resolve(
                &mut dictionary,
                &f.preparation,
                Some(f.frame),
                Role::Preparation,
                &limits,
            )?)?,
        };
        nodes = nodes
            .checked_add(request.addresses.len())
            .ok_or_else(|| invalid("structural aggregate node overflow"))?;
        if nodes > limits.max_graph_nodes {
            return Err(invalid("structural aggregate node limit"));
        }
        owned = owned
            .checked_add(encoded_size(
                &(
                    crate::bap::core_adapter::encode_request(&request)?,
                    &context.sites,
                ),
                limits.max_owned_bytes.saturating_sub(owned),
            )?)
            .ok_or_else(|| invalid("structural owned byte overflow"))?;
        if let Some(alignment) = &proofs.alignment {
            owned = owned
                .checked_add(encoded_size(
                    &alignment.base_request,
                    limits.max_owned_bytes.saturating_sub(owned),
                )?)
                .ok_or_else(|| invalid("structural base request byte overflow"))?;
        }
        proof_bytes = proof_bytes
            .checked_add(encoded_size(
                &proofs,
                limits.max_proof_bytes.saturating_sub(proof_bytes),
            )?)
            .ok_or_else(|| invalid("structural proof byte overflow"))?;
        loaded.push((f, request, context, proofs));
    }
    dictionary.finish()?;
    // Every frame's aggregate evidence and work envelope has been admitted
    // before any expensive BIL/proof replay begins.
    let mut frames = Vec::new();
    for (f, request, context, proofs) in loaded {
        frames.push((
            f.frame,
            replay_frame_recovery(
                &chain,
                f.frame,
                request,
                context,
                proofs,
                f.receipt.into(),
                RecoveryLimits {
                    max_visits: f.limits.max_visits,
                    deadline_ms: f.limits.deadline_ms,
                },
                &limits,
            )?,
        ));
    }
    let claimed_diagnostics = raw.diagnostics.clone();
    let bound = bind_frame_structure(chain, raw.question, frames, raw.diagnostics, limits)?;
    if bound.is_conditional() != conditional || bound.hypothesis_ids() != raw.conditional_on {
        return Err(invalid("conditional alignment scope differs from replay"));
    }
    if bound.diagnostics() != claimed_diagnostics.as_slice() {
        return Err(invalid(
            "structural diagnostics are contradictory or noncanonical",
        ));
    }
    if projection(&bound)? != claimed {
        return Err(invalid(
            "structural graph, status, frontier or diagnostic differs from replay",
        ));
    }
    Ok(bound)
}

#[cfg(test)]
pub(crate) fn rehash_for_test(value: &mut Value) -> Result<(), Error> {
    let mut raw: RawReport = serde_json::from_value(value.clone())?;
    raw.structure_id = identity(&raw)?;
    *value = serde_json::to_value(raw)?;
    Ok(())
}

fn text_writer(limits: &FrameStructureLimits) -> BoundedWriter {
    BoundedWriter {
        bytes: Vec::new(),
        limit: limits.max_output_bytes,
    }
}
fn finish_text(writer: BoundedWriter) -> Result<String, Error> {
    Ok(String::from_utf8(writer.bytes)?)
}

pub fn render_text(bound: &BoundFrameStructure) -> Result<String, Error> {
    let mut out = text_writer(bound.limits());
    writeln!(
        out,
        "{}\nproducer={} semantic_backend=bap\nframes {} -> {}\nphase=recover; dataflow_actions=0; slice_actions=0",
        if bound.is_conditional() {
            CONDITIONAL_FRAME_STRUCTURE_SCHEMA
        } else {
            FRAME_STRUCTURE_SCHEMA
        },
        if bound.is_conditional() {
            CONDITIONAL_FRAME_STRUCTURE_PRODUCER
        } else {
            FRAME_STRUCTURE_PRODUCER
        },
        bound.question().from_frame,
        bound.question().to_frame
    )?;
    if bound.is_conditional() {
        writeln!(
            out,
            "CONDITIONAL derived structure under alignment hypotheses {:?}; captured byte provenance unchanged",
            bound.hypothesis_ids()
        )?;
        for (frame, recovery) in bound.recoveries() {
            if let Some(report) = recovery.alignment_hypotheses() {
                for h in &report.hypotheses {
                    writeln!(
                        out,
                        "  hypothesis {} frame {} site {}: effective address aligned to {} bytes when reached",
                        h.id, frame, h.point, h.alignment
                    )?;
                }
                for d in &report.decisions {
                    writeln!(
                        out,
                        "  frame {} site {} baseline={:?} conditional={:?} basis={:?}",
                        frame, d.site, d.baseline_verdict, d.verdict, d.basis
                    )?;
                }
            }
        }
    }
    for frame in bound.frames() {
        let recovery = bound
            .recoveries()
            .iter()
            .find(|(index, _)| *index == frame.frame)
            .expect("bound map recovery")
            .1
            .recovery();
        writeln!(
            out,
            "frame {}{}: {} visited={} decoded={} edges={} pending={} stop={:?}{}",
            frame.frame,
            if frame.auxiliary {
                " (auxiliary entry witness)"
            } else {
                ""
            },
            if frame.recovery_drained {
                "drained"
            } else {
                "work_stopped"
            },
            recovery.state().visited.len(),
            recovery.state().decoded.len(),
            frame.edges.len(),
            recovery.state().pending.len(),
            recovery.receipt().stop,
            if bound.is_conditional() {
                "; conditional under report hypotheses"
            } else {
                ""
            }
        )?;
        for (site, source) in &recovery.state().provenance {
            writeln!(
                out,
                "  site 0x{site:016x} source={source:?} visited={} decoded={} pending={}",
                recovery.state().visited.contains(site),
                recovery.state().decoded.contains(site),
                recovery.state().pending.contains(site)
            )?;
        }
        for node in &frame.nodes {
            writeln!(
                out,
                "  0x{:016x} {} {}",
                node.va,
                node.bytes_hex,
                node.opcode.as_deref().unwrap_or("unknown")
            )?;
        }
        let assumed_sites: BTreeSet<u64> = frame
            .alignment_decisions
            .iter()
            .filter(|decision| {
                decision.baseline_verdict != crate::bap::guard_admission::Verdict::Aligned
                    && decision.normal_ast.is_some()
            })
            .map(|decision| crate::bap::core_adapter::address(&decision.site))
            .collect::<Result<_, _>>()?;
        for edge in &frame.edges {
            let assumed = assumed_sites.contains(&edge.src.site);
            writeln!(
                out,
                "  0x{:016x} -> 0x{:016x} {:?}{}",
                edge.src.site,
                edge.dst.site,
                edge.kind,
                if assumed {
                    " conditional normal under alignment hypothesis"
                } else {
                    ""
                }
            )?;
        }
        for gap in &frame.gaps {
            writeln!(
                out,
                "  boundary 0x{:016x} {:?} destination={:?}",
                gap.site, gap.kind, gap.destination
            )?;
        }
    }
    for link in bound.links() {
        writeln!(
            out,
            "frame {} -> {}: {} call_site={:?} continuation=0x{:016x}{}",
            link.caller,
            link.child,
            if link.admitted {
                "captured E8 CALL under premises"
            } else {
                "captured frame relation; call link unavailable"
            },
            link.call_site,
            link.continuation,
            if bound.is_conditional() {
                "; conditional under report hypotheses"
            } else {
                ""
            }
        )?;
    }
    for diagnostic in bound.diagnostics() {
        writeln!(
            out,
            "frame {} {:?}: {}; attempted={:?}; unattempted_references={:?}",
            diagnostic.frame,
            diagnostic.kind,
            diagnostic.message,
            diagnostic.attempted,
            diagnostic.unattempted_references
        )?;
    }
    finish_text(out)
}

pub fn render_dot(bound: &BoundFrameStructure) -> Result<String, Error> {
    let mut out = text_writer(bound.limits());
    writeln!(
        out,
        "digraph frame_structure {{\n  label=\"Recovery structure under premises; no executed-history claim; dataflow=0, slice=0\";"
    )?;
    if bound.is_conditional() {
        let label = serde_json::to_string(&format!(
            "CONDITIONAL derived structure under alignment hypotheses {:?}; captured provenance unchanged",
            bound.hypothesis_ids()
        ))?;
        writeln!(out, "  alignment_scope [shape=note,label={label}];")?;
        for (frame, recovery) in bound.recoveries() {
            if let Some(report) = recovery.alignment_hypotheses() {
                for (index, d) in report.decisions.iter().enumerate() {
                    let label = serde_json::to_string(&format!(
                        "frame {frame} site {} baseline={:?}; conditional={:?}; basis={:?}",
                        d.site, d.baseline_verdict, d.verdict, d.basis
                    ))?;
                    writeln!(
                        out,
                        "  f{frame}_alignment{index} [shape=note,label={label}];"
                    )?;
                }
            }
        }
    }
    for index in bound.question().to_frame..=bound.question().from_frame {
        if !bound.frames().iter().any(|f| f.frame == index) {
            writeln!(
                out,
                "  f{index}_status [shape=note,label=\"frame {index}: unavailable\"];"
            )?;
        }
    }
    for frame in bound.frames() {
        let recovery = bound
            .recoveries()
            .iter()
            .find(|(index, _)| *index == frame.frame)
            .expect("bound map recovery")
            .1
            .recovery();
        writeln!(
            out,
            "  subgraph cluster_{} {{\n    label=\"frame {} ({}{})\";",
            frame.frame,
            frame.frame,
            if frame.recovery_drained {
                "drained"
            } else {
                "work_stopped"
            },
            if bound.is_conditional() {
                "; conditional under report hypotheses"
            } else {
                ""
            }
        )?;
        writeln!(
            out,
            "    f{}_status [shape=note,label=\"visited={} decoded={} pending={} stop={:?}{}\"];",
            frame.frame,
            recovery.state().visited.len(),
            recovery.state().decoded.len(),
            recovery.state().pending.len(),
            recovery.receipt().stop,
            if frame.auxiliary {
                "; auxiliary witness"
            } else {
                ""
            }
        )?;
        for site in recovery.state().visited.union(&recovery.state().pending) {
            writeln!(
                out,
                "    f{}_a{:x} [label=\"0x{:016x}\",xlabel=\"source={:?}; {}\"];",
                frame.frame,
                site,
                site,
                recovery.state().provenance[site],
                if recovery.state().decoded.contains(site) {
                    "decoded"
                } else if recovery.state().pending.contains(site) {
                    "pending"
                } else {
                    "failed endpoint"
                }
            )?;
        }
        for (index, gap) in frame.gaps.iter().enumerate() {
            let label = serde_json::to_string(&format!(
                "{:?}; destination={:?}",
                gap.kind, gap.destination
            ))?;
            writeln!(
                out,
                "    f{}_gap{} [shape=note,label={}];\n    f{}_a{:x} -> f{}_gap{} [style=dashed,label=\"boundary\"];",
                frame.frame, index, label, frame.frame, gap.site, frame.frame, index
            )?;
        }
        let assumed_sites: BTreeSet<u64> = frame
            .alignment_decisions
            .iter()
            .filter(|decision| {
                decision.baseline_verdict != crate::bap::guard_admission::Verdict::Aligned
                    && decision.normal_ast.is_some()
            })
            .map(|decision| crate::bap::core_adapter::address(&decision.site))
            .collect::<Result<_, _>>()?;
        for edge in &frame.edges {
            let assumed = assumed_sites.contains(&edge.src.site);
            writeln!(
                out,
                "    f{}_a{:x} -> f{}_a{:x} [label=\"{:?}{}\"];",
                frame.frame,
                edge.src.site,
                frame.frame,
                edge.dst.site,
                edge.kind,
                if assumed {
                    "; conditional normal under alignment hypothesis"
                } else {
                    ""
                }
            )?;
        }
        writeln!(out, "  }}")?;
    }
    for link in bound.links() {
        if let (true, Some(site), Some(entry)) = (link.admitted, link.call_site, link.child_entry) {
            writeln!(
                out,
                "  f{}_a{:x} -> f{}_a{:x} [label=\"captured E8 CALL{}\"];",
                link.caller,
                site,
                link.child,
                entry,
                if bound.is_conditional() {
                    "; conditional under report hypotheses"
                } else {
                    ""
                }
            )?;
        } else {
            writeln!(
                out,
                "  f{}_status -> f{}_status [style=dashed,label=\"captured stack relation; CALL unavailable; continuation=0x{:016x}\"];",
                link.caller, link.child, link.continuation
            )?;
        }
    }
    for (index, diagnostic) in bound.diagnostics().iter().enumerate() {
        let mut label = BoundedWriter {
            bytes: Vec::new(),
            limit: out.limit.saturating_sub(out.bytes.len()),
        };
        write!(
            label,
            "frame {} {:?}: {}; attempted={:?}; unattempted={:?}",
            diagnostic.frame,
            diagnostic.kind,
            diagnostic.message,
            diagnostic.attempted,
            diagnostic.unattempted_references
        )?;
        let label = String::from_utf8(label.bytes)?;
        write!(out, "  diagnostic{index} [shape=note,label=")?;
        serde_json::to_writer(&mut out, &label)?;
        writeln!(
            out,
            "];\n  f{}_status -> diagnostic{index} [style=dotted];",
            diagnostic.frame
        )?;
    }
    writeln!(out, "}}")?;
    finish_text(out)
}
