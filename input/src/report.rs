//! One evidence-bounded view over frozen minidump preparation and core analysis.
//! This is presentation/serialization; it does not certify ISA execution.
use crate::{ByteRead, CaptureSource, FilePreparedAnalysis, ReadStop};
use ariadne::effects::{EffectQuality, GapReason, InstructionEvidence, Operand, RegisterView};
use ariadne::render::{Format as CoreFormat, render as render_core};
use ariadne::{
    Address, AddressSet, AnalysisResult, ByteSource, DefinitionOrigin, EdgeKind, InstructionKind,
    ObligationReason, Phase,
};
use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::error::Error;
use std::fmt;
use std::fmt::Write as _;

pub const SCHEMA: &str = "ariadne-minidump-report-v1";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReportFormat {
    Text,
    Dot,
    Json,
}

#[derive(Debug)]
pub enum ReportError {
    IdentityMismatch,
    InvalidExceptionSeed,
    Json(serde_json::Error),
}
impl fmt::Display for ReportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::IdentityMismatch => write!(f, "report snapshot identity mismatch"),
            Self::InvalidExceptionSeed => write!(f, "exception RIP is not a selected slice seed"),
            Self::Json(error) => write!(f, "report JSON: {error}"),
        }
    }
}
impl Error for ReportError {}

fn va(address: Address) -> String {
    format!("0x{address:016x}")
}
fn addresses(set: &AddressSet) -> Vec<String> {
    set.iter().map(|&address| va(address)).collect()
}
fn hex(bytes: &[u8]) -> String {
    use std::fmt::Write;
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        write!(result, "{byte:02x}").unwrap();
    }
    result
}
fn byte_source(source: ByteSource) -> &'static str {
    match source {
        ByteSource::Captured => "captured",
        ByteSource::File => "file",
        ByteSource::Unavailable => "unavailable",
    }
}
fn quality(quality: &EffectQuality) -> &'static str {
    match quality {
        EffectQuality::Reviewed => "reviewed",
        EffectQuality::ExternalLifted => "external_lift",
        EffectQuality::Opaque => "opaque",
        EffectQuality::Unavailable => "unavailable",
    }
}
fn gap_reason(reason: &GapReason) -> &'static str {
    match reason {
        GapReason::MissingBytes => "missing_bytes",
        GapReason::InvalidEncoding => "invalid_encoding",
        GapReason::UnsupportedControl => "unsupported_control",
        GapReason::OpaqueEffects => "opaque_effects",
        GapReason::UndefinedFlags => "undefined_flags",
    }
}
fn instruction_kind(kind: InstructionKind) -> &'static str {
    match kind {
        InstructionKind::Ordinary => "ordinary",
        InstructionKind::Conditional => "conditional",
        InstructionKind::Jump => "jump",
        InstructionKind::Indirect => "indirect",
        InstructionKind::Call => "call",
        InstructionKind::Return => "return",
        InstructionKind::Stop => "stop",
    }
}
fn edge_kind(kind: EdgeKind) -> &'static str {
    match kind {
        EdgeKind::Next => "next",
        EdgeKind::Taken => "taken",
        EdgeKind::Fallthrough => "fallthrough",
        EdgeKind::Jump => "jump",
        EdgeKind::Indirect => "indirect",
        EdgeKind::Summary => "summary",
        EdgeKind::Call => "call",
    }
}
fn obligation_reason(reason: ObligationReason) -> &'static str {
    match reason {
        ObligationReason::Unavailable => "unavailable",
        ObligationReason::DecodeFailed => "decode_failed",
        ObligationReason::IndirectTargets => "indirect_targets",
        ObligationReason::CallTargets => "call_targets",
    }
}
fn phase(phase: Phase) -> &'static str {
    match phase {
        Phase::Recover => "recover",
        Phase::Dataflow => "dataflow",
        Phase::Slice => "slice",
        Phase::Done => "done",
    }
}
fn register(view: &RegisterView) -> Value {
    json!({"bank": view.bank(), "bit_offset": view.bit_offset(), "width": view.width()})
}
fn operand(value: &Operand) -> Value {
    match value {
        Operand::Condition(value) => json!({"kind": "condition", "selector": value}),
        Operand::Register(value) => json!({"kind": "register", "view": register(value)}),
        Operand::Immediate {
            bits,
            encoded_width,
            semantic_width,
            sign_extend,
        } => json!({
            "kind": "immediate", "bits": va(*bits), "encoded_width": encoded_width,
            "semantic_width": semantic_width, "sign_extend": sign_extend,
        }),
        Operand::Memory {
            base,
            index,
            scale,
            displacement,
            address_width,
            access_width,
            next_ip,
        } => json!({
            "kind": "memory", "base": base.as_ref().map(register),
            "index": index.as_ref().map(register), "scale": scale,
            "displacement": displacement.to_string(), "address_width": address_width,
            "access_width": access_width, "next_ip": next_ip.map(va),
        }),
        Operand::Relative {
            displacement,
            target,
            encoded_width,
        } => json!({
            "kind": "relative", "displacement": displacement.to_string(),
            "target": va(*target), "encoded_width": encoded_width,
        }),
    }
}
fn capture_source(source: &CaptureSource) -> Value {
    json!({
        "stream": source.stream, "entry": source.entry,
        "file_offset": va(source.file_offset),
    })
}
fn read_stop(stop: &ReadStop) -> Value {
    match stop {
        ReadStop::RequestedLength => json!({"kind": "requested_length"}),
        ReadStop::NotCaptured(address) => json!({"kind": "not_captured", "va": va(*address)}),
        ReadStop::ConflictingCapture(address) => {
            json!({"kind": "conflicting_capture", "va": va(*address)})
        }
        ReadStop::AddressOverflow => json!({"kind": "address_overflow"}),
    }
}
fn read(address: Address, value: &ByteRead) -> Value {
    json!({
        "va": va(address), "bytes_hex": hex(&value.bytes),
        "stop": read_stop(&value.stop),
        "spans": value.spans.iter().map(|span| json!({
            "va": va(span.address), "length": span.length,
            "contributors": span.contributors.iter().map(capture_source).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
        "conflict_sources": value.conflict_sources.iter().map(capture_source).collect::<Vec<_>>(),
    })
}
fn site_issues(
    prepared: &FilePreparedAnalysis,
    address: Address,
    evidence: &InstructionEvidence,
) -> Vec<&'static str> {
    let mut issues = Vec::new();
    if !prepared.materialization.attempted.contains(&address) {
        issues.push("unvisited_reference");
        return issues;
    }
    if evidence.quality == EffectQuality::Unavailable {
        if let Some(read) = prepared.reads.get(&address) {
            match read.stop {
                ReadStop::NotCaptured(_) => issues.push("not_captured"),
                ReadStop::ConflictingCapture(_) => issues.push("conflicting_capture"),
                _ => {}
            }
        }
        if issues.is_empty() {
            issues.push("decode_failed");
        }
    }
    if evidence.quality == EffectQuality::Opaque {
        issues.push("unsupported_semantics");
    }
    if !evidence.undefined_flags.is_empty() {
        issues.push("architecturally_undefined");
    }
    issues
}
fn site(
    prepared: &FilePreparedAnalysis,
    address: Address,
    evidence: &InstructionEvidence,
) -> Value {
    let mut value = json!({
        "va": va(address), "bytes_hex": hex(&evidence.bytes),
        "byte_source": byte_source(evidence.source), "opcode": evidence.opcode,
        "length": evidence.length, "operands": evidence.operands.iter().map(operand).collect::<Vec<_>>(),
        "rule": evidence.rule, "control": evidence.control.map(instruction_kind),
        "quality": quality(&evidence.quality), "undefined_flags": evidence.undefined_flags,
        "decoder_record": evidence.decoder_record,
        "issues": site_issues(prepared, address, evidence),
    });
    if let Some(semantic) = &evidence.semantic {
        value["semantic"] = json!({"backend":semantic.backend,"helper_sha256":semantic.helper_sha256,"runtime_sha256":semantic.runtime_sha256,"projection":semantic.projection,"status":semantic.status,"ast_sha256":semantic.ast_sha256,"fallback":semantic.fallback,"gaps":semantic.gaps,"memory_accesses":semantic.memory_accesses.iter().map(ariadne_investigation::AddressUse::from).collect::<Vec<_>>()});
    }
    value
}

fn register_name(view: &RegisterView) -> String {
    const LOW: [&str; 8] = ["AL", "CL", "DL", "BL", "SPL", "BPL", "SIL", "DIL"];
    const WORD: [&str; 8] = ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"];
    const DWORD: [&str; 8] = ["EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI"];
    const QWORD: [&str; 8] = ["RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI"];
    let bank = usize::from(view.bank());
    if view.bit_offset() == 8 && view.width() == 8 && bank < 4 {
        return ["AH", "CH", "DH", "BH"][bank].into();
    }
    if bank < 8 {
        return match view.width() {
            8 => LOW[bank],
            16 => WORD[bank],
            32 => DWORD[bank],
            64 => QWORD[bank],
            _ => "?",
        }
        .into();
    }
    let suffix = match view.width() {
        8 => "B",
        16 => "W",
        32 => "D",
        64 => "",
        _ => "?",
    };
    format!("R{bank}{suffix}")
}

fn operand_label(value: &Operand) -> String {
    match value {
        Operand::Condition(selector) => format!("cc#{selector}"),
        Operand::Register(view) => register_name(view),
        Operand::Immediate {
            bits,
            encoded_width,
            semantic_width,
            sign_extend,
        } => format!(
            "imm{encoded_width}->{semantic_width}:{}{}",
            va(*bits),
            if *sign_extend { "/sext" } else { "" }
        ),
        Operand::Memory {
            base,
            index,
            scale,
            displacement,
            address_width,
            access_width,
            next_ip,
        } => {
            let mut terms = Vec::new();
            if let Some(next_ip) = next_ip {
                terms.push(format!("RIP@{}", va(*next_ip)));
            }
            if let Some(base) = base {
                terms.push(register_name(base));
            }
            if let Some(index) = index {
                terms.push(format!("{}*{scale}", register_name(index)));
            }
            let mut address = if terms.is_empty() {
                "0".to_string()
            } else {
                terms.join("+")
            };
            if *displacement > 0 {
                write!(address, "+0x{displacement:x}").unwrap();
            } else if *displacement < 0 {
                write!(address, "-0x{:x}", displacement.unsigned_abs()).unwrap();
            }
            format!("mem{access_width}/addr{address_width}[{address}]")
        }
        Operand::Relative {
            displacement,
            target,
            encoded_width,
        } => format!("rel{encoded_width}->{},disp={displacement:+}", va(*target)),
    }
}

fn one_line(value: &str) -> String {
    value.chars().flat_map(char::escape_default).collect()
}

fn capture_spans(prepared: &FilePreparedAnalysis, address: Address, length: u8) -> String {
    let Some(read) = prepared.reads.get(&address) else {
        return "none".into();
    };
    let end = address.saturating_add(u64::from(length));
    let mut spans = Vec::new();
    for span in &read.spans {
        let start = address.max(span.address);
        if start >= end || start >= span.address.saturating_add(span.length as u64) {
            continue;
        }
        for contributor in &span.contributors {
            if let Some(offset) = contributor.file_offset.checked_add(start - span.address) {
                spans.push(format!(
                    "s{}#{}@{}",
                    contributor.stream,
                    contributor.entry,
                    va(offset)
                ));
            }
        }
    }
    if spans.is_empty() {
        "none".into()
    } else {
        spans.join(",")
    }
}

fn possible_origin_counts(
    prepared: &FilePreparedAnalysis,
    result: &AnalysisResult,
    address: Address,
) -> (usize, usize) {
    let Some(instruction) = prepared.prepared.request.instructions.get(&address) else {
        return (0, 0);
    };
    let Some(reaching) = result.state.reaching.get(&address) else {
        return (0, 0);
    };
    let mut instructions = BTreeSet::new();
    let mut entries = BTreeSet::new();
    for definition in reaching {
        if !instruction.uses.contains(&definition.loc) {
            continue;
        }
        match definition.origin {
            DefinitionOrigin::Entry => {
                entries.insert(definition.site);
            }
            DefinitionOrigin::Instruction => {
                instructions.insert(definition.site);
            }
        }
    }
    (instructions.len(), entries.len())
}

fn instruction_overview(prepared: &FilePreparedAnalysis, result: &AnalysisResult) -> String {
    let mut out = String::from(
        "Instruction overview (normalized operands; possible input origins are site counts)\n",
    );
    for (&address, evidence) in &prepared.prepared.instructions {
        let bytes = if evidence.bytes.is_empty() {
            "?".into()
        } else {
            hex(&evidence.bytes)
        };
        let operands = if evidence.operands.is_empty() {
            "-".into()
        } else {
            evidence
                .operands
                .iter()
                .map(operand_label)
                .collect::<Vec<_>>()
                .join(", ")
        };
        writeln!(
            out,
            "{}  {bytes}  {}  {operands}",
            va(address),
            one_line(evidence.opcode.as_deref().unwrap_or("?")),
        )
        .unwrap();
        let (instruction_origins, entry_origins) =
            possible_origin_counts(prepared, result, address);
        let issues = site_issues(prepared, address, evidence);
        writeln!(
            out,
            "  rule={} quality={} source={} span={} slice={} possible-input-origins=instruction:{instruction_origins},entry:{entry_origins} issues={}",
            one_line(evidence.rule.as_deref().unwrap_or("none")),
            quality(&evidence.quality),
            byte_source(evidence.source),
            capture_spans(prepared, address, evidence.length),
            if result.state.slice.contains(&address) {
                "yes"
            } else {
                "no"
            },
            if issues.is_empty() {
                "none".into()
            } else {
                issues.join(",")
            },
        )
        .unwrap();
    }
    out.push_str("Full reaching definitions, edges and gaps follow below.\n");
    out
}
fn identity(prepared: &FilePreparedAnalysis) -> Value {
    let snapshot = &prepared.snapshot;
    let preparation = &prepared.prepared.identity;
    json!({
        "snapshot_id": snapshot.snapshot_id,
        "artifact_sha256": snapshot.artifact_sha256,
        "query_id": prepared.materialization.query_identity,
        "platform": match snapshot.platform { crate::Platform::Windows => "windows", crate::Platform::Linux => "linux" },
        "decoder_target": preparation.target, "decoder_build": preparation.decoder,
        "decoder_protocol": preparation.protocol, "effects_ruleset": preparation.ruleset,
        "location_catalogue": preparation.catalogue,
        "input_package_version": env!("CARGO_PKG_VERSION"),
        "core_package_version": ariadne::PACKAGE_VERSION,
    })
}
fn json_report(
    prepared: &FilePreparedAnalysis,
    result: &AnalysisResult,
    exception_rip_seed: bool,
) -> Value {
    let report = &prepared.materialization;
    let snapshot = &prepared.snapshot;
    let state = &result.state;
    let open = &prepared.open_limits;
    let limits = &report.limits;
    json!({
        "schema": SCHEMA,
        "identity": identity(prepared),
        "query": {
            "entries": addresses(&report.entry_points),
            "seeds": addresses(&report.slice_seeds),
            "exception_rip_seed": exception_rip_seed,
        },
        "input": {
            "artifact_bytes": snapshot.artifact_bytes,
            "streams": snapshot.streams.iter().map(|stream| json!({
                "kind": stream.kind, "file_offset": va(stream.file_offset),
                "size": va(stream.size), "supported": stream.supported,
            })).collect::<Vec<_>>(),
            "modules": snapshot.modules.iter().map(|module| json!({
                "name": module.name, "base": va(module.base), "size": va(module.size),
                "timestamp": module.timestamp, "checksum": module.checksum,
                "codeview_hex": hex(&module.codeview),
            })).collect::<Vec<_>>(),
            "threads": snapshot.threads.iter().map(|thread| json!({
                "id": thread.id, "registers": thread.registers.iter().map(|(name, value)| (name.clone(), va(*value))).collect::<std::collections::BTreeMap<_,_>>(),
            })).collect::<Vec<_>>(),
            "exception": snapshot.exception.as_ref().map(|exception| json!({
                "thread_id": exception.thread_id, "code": exception.code,
                "reported_address": va(exception.reported_address),
                "registers": exception.registers.iter().map(|(name, value)| (name.clone(), va(*value))).collect::<std::collections::BTreeMap<_,_>>(),
            })),
            "memory_info": snapshot.memory_info.iter().map(|info| json!({
                "base": va(info.base), "size": va(info.size), "protection": info.protection,
                "state": info.state, "kind": info.kind,
            })).collect::<Vec<_>>(),
            "metadata_gaps": snapshot.gaps.iter().map(|gap| json!({
                "stream": gap.stream, "entry": gap.entry, "reason": gap.reason,
            })).collect::<Vec<_>>(),
            "open_limits": {
                "max_file_bytes": open.max_file_bytes, "max_streams": open.max_streams,
                "max_records": open.max_records, "max_metadata_bytes": open.max_metadata_bytes,
                "max_capture_ranges": open.max_capture_ranges, "max_overlap": open.max_overlap,
                "max_read_bytes": open.max_read_bytes,
            },
            "prepare_limits": {
                "max_starts": limits.max_starts, "max_candidates": limits.max_candidates,
                "max_prefix_bytes": limits.max_prefix_bytes,
                "max_decoder_batches": limits.max_decoder_batches, "batch_size": limits.batch_size,
            },
            "attempted": addresses(&report.attempted),
            "referenced": addresses(&report.referenced),
            "unvisited_references": addresses(&report.unattempted_references),
            "prefix_bytes": report.prefix_bytes, "decoder_batches": report.decoder_batches,
            "overlapping_starts": report.overlapping_starts.iter().map(|(a,b)| [va(*a), va(*b)]).collect::<Vec<_>>(),
            "reads": prepared.reads.iter().map(|(&address, value)| read(address, value)).collect::<Vec<_>>(),
        },
        "preparation": {
            "sites": prepared.prepared.instructions.iter().map(|(&address, evidence)| site(prepared, address, evidence)).collect::<Vec<_>>(),
            "gaps": prepared.prepared.gaps.iter().map(|gap| json!({
                "va": va(gap.address), "reason": gap_reason(&gap.reason),
            })).collect::<Vec<_>>(),
        },
        "analysis": {
            "phase": phase(state.phase),
            "scope_closed": result.scope_closed(),
            "scope_note": "recovery only; relative to supplied inputs",
            "pending": addresses(&state.pending), "visited": addresses(&state.visited),
            "decoded": addresses(&state.decoded), "slice": addresses(&state.slice),
            "missing_slice_seeds": addresses(&result.missing_slice_seeds),
            "provenance": state.provenance.iter().map(|(&address, &source)| json!({
                "va": va(address), "byte_source": byte_source(source),
            })).collect::<Vec<_>>(),
            "edges": state.edges.iter().map(|edge| json!({
                "src": va(edge.src), "dst": va(edge.dst), "kind": edge_kind(edge.kind),
                "local": edge.kind.is_local(),
            })).collect::<Vec<_>>(),
            "reaching": state.reaching.iter().map(|(&address, definitions)| json!({
                "before": va(address), "definitions": definitions.iter().map(|definition| json!({
                    "loc": definition.loc, "site": va(definition.site),
                    "origin": match definition.origin { DefinitionOrigin::Entry => "entry", DefinitionOrigin::Instruction => "instruction" },
                })).collect::<Vec<_>>(),
            })).collect::<Vec<_>>(),
            "obligations": state.obligations.iter().map(|obligation| json!({
                "va": va(obligation.site), "reason": obligation_reason(obligation.reason),
            })).collect::<Vec<_>>(),
        },
    })
}

/// Render the same frozen evidence in one format. `exception_rip_seed` is a
/// command-origin marker; the selected seed itself is already in the query.
pub fn render(
    prepared: &FilePreparedAnalysis,
    result: &AnalysisResult,
    format: ReportFormat,
    exception_rip_seed: bool,
) -> Result<String, ReportError> {
    if prepared.snapshot.snapshot_id != result.snapshot_id
        || prepared.prepared.request.snapshot_id != result.snapshot_id
    {
        return Err(ReportError::IdentityMismatch);
    }
    if exception_rip_seed
        && !prepared
            .snapshot
            .exception
            .as_ref()
            .is_some_and(|exception| {
                exception
                    .registers
                    .get("rip")
                    .is_some_and(|rip| prepared.materialization.slice_seeds.contains(rip))
            })
    {
        return Err(ReportError::InvalidExceptionSeed);
    }
    let value = json_report(prepared, result, exception_rip_seed);
    match format {
        ReportFormat::Json => Ok(format!(
            "{}\n",
            serde_json::to_string_pretty(&value).map_err(ReportError::Json)?
        )),
        ReportFormat::Text => {
            let mut out = String::new();
            writeln!(out, "Ariadne minidump report ({SCHEMA})").unwrap();
            writeln!(out, "identity: {}", value["identity"]).unwrap();
            writeln!(out, "query: {}", value["query"]).unwrap();
            out.push_str(&instruction_overview(prepared, result));
            for site in value["preparation"]["sites"].as_array().unwrap() {
                writeln!(out, "site: {site}").unwrap();
            }
            for gap in value["preparation"]["gaps"].as_array().unwrap() {
                writeln!(out, "preparation gap: {gap}").unwrap();
            }
            for read in value["input"]["reads"].as_array().unwrap() {
                writeln!(out, "captured read: {read}").unwrap();
            }
            for gap in value["input"]["metadata_gaps"].as_array().unwrap() {
                writeln!(out, "input metadata gap: {gap}").unwrap();
            }
            writeln!(
                out,
                "unvisited references: {}",
                value["input"]["unvisited_references"]
            )
            .unwrap();
            writeln!(out).unwrap();
            out.push_str(&render_core(result, CoreFormat::Text));
            Ok(out)
        }
        ReportFormat::Dot => {
            let mut out = format!("// {SCHEMA}\n");
            for key in ["identity", "query"] {
                writeln!(out, "// {key}: {}", value[key]).unwrap();
            }
            for site in value["preparation"]["sites"].as_array().unwrap() {
                writeln!(out, "// site: {site}").unwrap();
            }
            for gap in value["preparation"]["gaps"].as_array().unwrap() {
                writeln!(out, "// preparation gap: {gap}").unwrap();
            }
            for read in value["input"]["reads"].as_array().unwrap() {
                writeln!(out, "// captured read: {read}").unwrap();
            }
            for gap in value["input"]["metadata_gaps"].as_array().unwrap() {
                writeln!(out, "// input metadata gap: {gap}").unwrap();
            }
            writeln!(
                out,
                "// unvisited references: {}",
                value["input"]["unvisited_references"]
            )
            .unwrap();
            out.push_str(&render_core(result, CoreFormat::Dot));
            Ok(out)
        }
    }
}
