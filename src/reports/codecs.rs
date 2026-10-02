use crate::reports::{Error, invalid};
use crate::{Edge, EdgeKind, llvm_ir as ir, machine_state as ms};
use serde::de::{self, MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

pub fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
struct Strict(Value);
impl<'de> Deserialize<'de> for Strict {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = Strict;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                write!(f, "JSON without duplicate fields")
            }
            fn visit_bool<E: de::Error>(self, value: bool) -> Result<Strict, E> {
                Ok(Strict(value.into()))
            }
            fn visit_i64<E: de::Error>(self, value: i64) -> Result<Strict, E> {
                Ok(Strict(value.into()))
            }
            fn visit_u64<E: de::Error>(self, value: u64) -> Result<Strict, E> {
                Ok(Strict(value.into()))
            }
            fn visit_f64<E: de::Error>(self, value: f64) -> Result<Strict, E> {
                serde_json::Number::from_f64(value)
                    .map(|n| Strict(n.into()))
                    .ok_or_else(|| E::custom("nonfinite JSON number"))
            }
            fn visit_str<E: de::Error>(self, value: &str) -> Result<Strict, E> {
                Ok(Strict(value.into()))
            }
            fn visit_string<E: de::Error>(self, value: String) -> Result<Strict, E> {
                Ok(Strict(value.into()))
            }
            fn visit_unit<E: de::Error>(self) -> Result<Strict, E> {
                Ok(Strict(Value::Null))
            }
            fn visit_none<E: de::Error>(self) -> Result<Strict, E> {
                Ok(Strict(Value::Null))
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut access: A) -> Result<Strict, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = access.next_element::<Strict>()? {
                    values.push(value.0);
                }
                Ok(Strict(Value::Array(values)))
            }
            fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<Strict, A::Error> {
                let mut values = serde_json::Map::new();
                while let Some(key) = access.next_key::<String>()? {
                    if values.contains_key(&key) {
                        return Err(de::Error::custom(format!("duplicate field: {key}")));
                    }
                    values.insert(key, access.next_value::<Strict>()?.0);
                }
                Ok(Strict(Value::Object(values)))
            }
        }
        deserializer.deserialize_any(V)
    }
}
pub fn strict_json(bytes: &[u8]) -> Result<Value, Error> {
    strict_json_with_limit(bytes, 8 * 1024 * 1024)
}
pub fn strict_json_with_limit(bytes: &[u8], limit: usize) -> Result<Value, Error> {
    if bytes.len() > limit {
        return Err(invalid("JSON input exceeds its byte limit"));
    }
    Ok(serde_json::from_slice::<Strict>(bytes)?.0)
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
struct Va(u64);
impl Serialize for Va {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&format!("0x{:016x}", self.0))
    }
}
impl<'de> Deserialize<'de> for Va {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let text = String::deserialize(d)?;
        let digits = text
            .strip_prefix("0x")
            .ok_or_else(|| de::Error::custom("VA requires 0x prefix"))?;
        if digits.len() != 16
            || !digits
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return Err(de::Error::custom("VA requires 16 lowercase hex digits"));
        }
        Ok(Self(
            u64::from_str_radix(digits, 16).map_err(de::Error::custom)?,
        ))
    }
}
pub(crate) fn edge_kind(kind: EdgeKind) -> &'static str {
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
fn parse_edge(text: &str) -> Result<EdgeKind, Error> {
    Ok(match text {
        "next" => EdgeKind::Next,
        "taken" => EdgeKind::Taken,
        "fallthrough" => EdgeKind::Fallthrough,
        "jump" => EdgeKind::Jump,
        "indirect" => EdgeKind::Indirect,
        "summary" => EdgeKind::Summary,
        "call" => EdgeKind::Call,
        _ => return Err(invalid("unknown machine edge kind")),
    })
}
fn unique<T: Ord>(values: impl IntoIterator<Item = T>) -> Result<BTreeSet<T>, Error> {
    let mut set = BTreeSet::new();
    for value in values {
        if !set.insert(value) {
            return Err(invalid("duplicate set member"));
        }
    }
    Ok(set)
}
fn map<K: Ord, V>(values: impl IntoIterator<Item = (K, V)>) -> Result<BTreeMap<K, V>, Error> {
    let mut map = BTreeMap::new();
    for (key, value) in values {
        if map.insert(key, value).is_some() {
            return Err(invalid("duplicate table key"));
        }
    }
    Ok(map)
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EdgeRow {
    src: Va,
    dst: Va,
    kind: String,
}
impl From<Edge> for EdgeRow {
    fn from(e: Edge) -> Self {
        Self {
            src: Va(e.src),
            dst: Va(e.dst),
            kind: edge_kind(e.kind).into(),
        }
    }
}
impl EdgeRow {
    fn model(self) -> Result<Edge, Error> {
        Ok(Edge {
            src: self.src.0,
            dst: self.dst.0,
            kind: parse_edge(&self.kind)?,
        })
    }
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct StateRow {
    status: String,
    valuation: BTreeMap<String, Vec<String>>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EntryRow {
    va: Va,
    states: Vec<String>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct StepRow {
    edge: EdgeRow,
    before: String,
    after: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TerminalRow {
    site: Va,
    before: String,
    after: String,
    outcome: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ObligationRow {
    site: Va,
    reason: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EffectsRow {
    va: Va,
    uses: Vec<String>,
    must_defs: Vec<String>,
    may_defs: Vec<String>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct MachineDto {
    schema: String,
    snapshot_id: String,
    value_domain: BTreeMap<String, Vec<String>>,
    catalogue: BTreeMap<String, StateRow>,
    entry_states: Vec<EntryRow>,
    steps: Vec<StepRow>,
    terminal_transitions: Vec<TerminalRow>,
    complete_sites: Vec<Va>,
    adapter_obligations: Vec<ObligationRow>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    nodes: Option<Vec<Va>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    structural_edges: Option<Vec<EdgeRow>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    effects: Option<Vec<EffectsRow>>,
}
fn status(text: &str) -> Result<ms::Status, Error> {
    Ok(match text {
        "running" => ms::Status::Running,
        "faulted" => ms::Status::Faulted,
        "returned" => ms::Status::Returned,
        "stopped" => ms::Status::Stopped,
        _ => return Err(invalid("unknown state status")),
    })
}
pub(crate) fn status_name(s: ms::Status) -> &'static str {
    match s {
        ms::Status::Running => "running",
        ms::Status::Faulted => "faulted",
        ms::Status::Returned => "returned",
        ms::Status::Stopped => "stopped",
    }
}
pub(crate) fn outcome_name(o: ms::TerminalOutcome) -> &'static str {
    status_name(o.into())
}
pub(crate) fn ms_reason(r: ms::AdapterObligationReason) -> &'static str {
    match r {
        ms::AdapterObligationReason::UnknownMemory => "unknown-memory",
        ms::AdapterObligationReason::UnmodeledException => "unmodeled-exception",
        ms::AdapterObligationReason::UnmodeledSystemCall => "unmodeled-system-call",
        ms::AdapterObligationReason::UnmodeledConcurrency => "unmodeled-concurrency",
    }
}
fn ms_obligation(text: &str) -> Result<ms::AdapterObligationReason, Error> {
    Ok(match text {
        "unknown-memory" => ms::AdapterObligationReason::UnknownMemory,
        "unmodeled-exception" => ms::AdapterObligationReason::UnmodeledException,
        "unmodeled-system-call" => ms::AdapterObligationReason::UnmodeledSystemCall,
        "unmodeled-concurrency" => ms::AdapterObligationReason::UnmodeledConcurrency,
        _ => return Err(invalid("unknown machine adapter obligation")),
    })
}
impl MachineDto {
    fn semantics(self) -> Result<ms::SemanticInputs, Error> {
        Ok(ms::SemanticInputs {
            snapshot_id: self.snapshot_id,
            value_domain: self
                .value_domain
                .into_iter()
                .map(|(l, v)| Ok((l, unique(v.into_iter().map(ms::AbstractValue))?)))
                .collect::<Result<_, Error>>()?,
            catalogue: self
                .catalogue
                .into_iter()
                .map(|(id, row)| {
                    Ok((
                        ms::StateId(id),
                        ms::AbstractState {
                            status: status(&row.status)?,
                            valuation: row
                                .valuation
                                .into_iter()
                                .map(|(l, v)| {
                                    Ok((l, unique(v.into_iter().map(ms::AbstractValue))?))
                                })
                                .collect::<Result<_, Error>>()?,
                        },
                    ))
                })
                .collect::<Result<_, Error>>()?,
            entry_states: map(self
                .entry_states
                .into_iter()
                .map(|row| Ok((row.va.0, unique(row.states.into_iter().map(ms::StateId))?)))
                .collect::<Result<Vec<_>, Error>>()?)?,
            steps: unique(
                self.steps
                    .into_iter()
                    .map(|row| {
                        Ok(ms::StateStep {
                            edge: row.edge.model()?,
                            before: ms::StateId(row.before),
                            after: ms::StateId(row.after),
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()?,
            )?,
            terminal_transitions: unique(
                self.terminal_transitions
                    .into_iter()
                    .map(|row| {
                        Ok(ms::TerminalTransition {
                            site: row.site.0,
                            before: ms::StateId(row.before),
                            after: ms::StateId(row.after),
                            outcome: match status(&row.outcome)? {
                                ms::Status::Faulted => ms::TerminalOutcome::Faulted,
                                ms::Status::Returned => ms::TerminalOutcome::Returned,
                                ms::Status::Stopped => ms::TerminalOutcome::Stopped,
                                ms::Status::Running => {
                                    return Err(invalid("terminal state cannot be running"));
                                }
                            },
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()?,
            )?,
            complete_sites: unique(self.complete_sites.into_iter().map(|va| va.0))?,
            adapter_obligations: unique(
                self.adapter_obligations
                    .into_iter()
                    .map(|row| {
                        Ok(ms::AdapterObligation {
                            site: row.site.0,
                            reason: ms_obligation(&row.reason)?,
                        })
                    })
                    .collect::<Result<Vec<_>, Error>>()?,
            )?,
        })
    }
}
pub fn decode_semantics(bytes: &[u8]) -> Result<ms::SemanticInputs, Error> {
    let value = strict_json(bytes)?;
    if ["nodes", "structural_edges", "effects"]
        .iter()
        .any(|key| value.get(key).is_some())
    {
        return Err(invalid("semantic input must not supply graph or effects"));
    }
    let dto: MachineDto = serde_json::from_value(value)?;
    if dto.schema != "ariadne.machine-state-semantics/v1"
        || dto.nodes.is_some()
        || dto.structural_edges.is_some()
        || dto.effects.is_some()
    {
        return Err(invalid(
            "expected semantic-input schema without graph/effects",
        ));
    }
    dto.semantics()
}
pub fn decode_machine_request(bytes: &[u8]) -> Result<ms::Request, Error> {
    let mut dto: MachineDto = serde_json::from_value(strict_json(bytes)?)?;
    if dto.schema != "ariadne.machine-state-request/v1" {
        return Err(invalid("unsupported machine request schema"));
    }
    let nodes = unique(
        dto.nodes
            .take()
            .ok_or_else(|| invalid("missing nodes"))?
            .into_iter()
            .map(|va| va.0),
    )?;
    let structural_edges = unique(
        dto.structural_edges
            .take()
            .ok_or_else(|| invalid("missing graph"))?
            .into_iter()
            .map(EdgeRow::model)
            .collect::<Result<Vec<_>, Error>>()?,
    )?;
    let effects = map(dto
        .effects
        .take()
        .ok_or_else(|| invalid("missing effects"))?
        .into_iter()
        .map(|row| {
            Ok((
                row.va.0,
                ms::Effects {
                    uses: unique(row.uses)?,
                    must_defs: unique(row.must_defs)?,
                    may_defs: unique(row.may_defs)?,
                },
            ))
        })
        .collect::<Result<Vec<_>, Error>>()?)?;
    let s = dto.semantics()?;
    let request = ms::Request {
        snapshot_id: s.snapshot_id,
        nodes,
        structural_edges,
        value_domain: s.value_domain,
        catalogue: s.catalogue,
        entry_states: s.entry_states,
        effects,
        steps: s.steps,
        terminal_transitions: s.terminal_transitions,
        complete_sites: s.complete_sites,
        adapter_obligations: s.adapter_obligations,
    };
    request.validate()?;
    Ok(request)
}
fn machine_dto(request: &ms::Request) -> MachineDto {
    MachineDto {
        schema: "ariadne.machine-state-request/v1".into(),
        snapshot_id: request.snapshot_id.clone(),
        nodes: Some(request.nodes.iter().map(|&va| Va(va)).collect()),
        structural_edges: Some(
            request
                .structural_edges
                .iter()
                .copied()
                .map(EdgeRow::from)
                .collect(),
        ),
        value_domain: request
            .value_domain
            .iter()
            .map(|(l, v)| (l.clone(), v.iter().map(|v| v.0.clone()).collect()))
            .collect(),
        catalogue: request
            .catalogue
            .iter()
            .map(|(id, state)| {
                (
                    id.0.clone(),
                    StateRow {
                        status: status_name(state.status).into(),
                        valuation: state
                            .valuation
                            .iter()
                            .map(|(l, v)| (l.clone(), v.iter().map(|v| v.0.clone()).collect()))
                            .collect(),
                    },
                )
            })
            .collect(),
        entry_states: request
            .entry_states
            .iter()
            .map(|(&va, s)| EntryRow {
                va: Va(va),
                states: s.iter().map(|id| id.0.clone()).collect(),
            })
            .collect(),
        effects: Some(
            request
                .effects
                .iter()
                .map(|(&va, e)| EffectsRow {
                    va: Va(va),
                    uses: e.uses.iter().cloned().collect(),
                    must_defs: e.must_defs.iter().cloned().collect(),
                    may_defs: e.may_defs.iter().cloned().collect(),
                })
                .collect(),
        ),
        steps: request
            .steps
            .iter()
            .map(|s| StepRow {
                edge: s.edge.into(),
                before: s.before.0.clone(),
                after: s.after.0.clone(),
            })
            .collect(),
        terminal_transitions: request
            .terminal_transitions
            .iter()
            .map(|s| TerminalRow {
                site: Va(s.site),
                before: s.before.0.clone(),
                after: s.after.0.clone(),
                outcome: outcome_name(s.outcome).into(),
            })
            .collect(),
        complete_sites: request.complete_sites.iter().map(|&va| Va(va)).collect(),
        adapter_obligations: request
            .adapter_obligations
            .iter()
            .map(|o| ObligationRow {
                site: Va(o.site),
                reason: ms_reason(o.reason).into(),
            })
            .collect(),
    }
}
pub fn encode_machine_request(request: &ms::Request) -> Result<Value, Error> {
    request.validate()?;
    Ok(serde_json::to_value(machine_dto(request))?)
}
pub fn encode_semantics(request: &ms::Request) -> Result<Value, Error> {
    request.validate()?;
    let mut dto = machine_dto(request);
    dto.schema = "ariadne.machine-state-semantics/v1".into();
    dto.nodes = None;
    dto.structural_edges = None;
    dto.effects = None;
    Ok(serde_json::to_value(dto)?)
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRBlock {
    terminator: String,
    kind: String,
    successors: Vec<IRSuccessor>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRSuccessor {
    dst: String,
    kind: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRInstruction {
    block: String,
    index: u32,
    uses: Vec<String>,
    phi_incoming: Vec<IRPhi>,
    memory_preds: Vec<String>,
    call_targets: Vec<String>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRPhi {
    pred: String,
    value: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRValue {
    kind: String,
    def_site: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IRObligation {
    site: String,
    reason: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IrDto {
    schema: String,
    artifact_id: String,
    module_id: String,
    function_id: String,
    verified_ir: bool,
    blocks: BTreeMap<String, IRBlock>,
    entry_block: String,
    instructions: BTreeMap<String, IRInstruction>,
    values: BTreeMap<String, IRValue>,
    phi_nodes: Vec<String>,
    call_sites: Vec<String>,
    callees: Vec<String>,
    complete_calls: Vec<String>,
    adapter_obligations: Vec<IRObligation>,
    slice_seeds: Vec<String>,
}
pub(crate) fn ir_edge(kind: ir::ControlEdgeKind) -> &'static str {
    match kind {
        ir::ControlEdgeKind::Next => "next",
        ir::ControlEdgeKind::True => "true",
        ir::ControlEdgeKind::False => "false",
        ir::ControlEdgeKind::Case => "case",
        ir::ControlEdgeKind::Default => "default",
        ir::ControlEdgeKind::Indirect => "indirect",
        ir::ControlEdgeKind::Normal => "normal",
        ir::ControlEdgeKind::Unwind => "unwind",
        ir::ControlEdgeKind::Fallthrough => "fallthrough",
        ir::ControlEdgeKind::Catch => "catch",
        ir::ControlEdgeKind::Cleanup => "cleanup",
    }
}
fn parse_ir_edge(text: &str) -> Result<ir::ControlEdgeKind, Error> {
    use ir::ControlEdgeKind::*;
    Ok(match text {
        "next" => Next,
        "true" => True,
        "false" => False,
        "case" => Case,
        "default" => Default,
        "indirect" => Indirect,
        "normal" => Normal,
        "unwind" => Unwind,
        "fallthrough" => Fallthrough,
        "catch" => Catch,
        "cleanup" => Cleanup,
        _ => return Err(invalid("unknown IR edge kind")),
    })
}
fn term(text: &str) -> Result<ir::TerminatorKind, Error> {
    use ir::TerminatorKind::*;
    Ok(match text {
        "br" => Br,
        "switch" => Switch,
        "indirectbr" => IndirectBr,
        "invoke" => Invoke,
        "callbr" => CallBr,
        "ret" => Ret,
        "resume" => Resume,
        "unreachable" => Unreachable,
        "catchswitch" => CatchSwitch,
        "catchret" => CatchRet,
        "cleanupret" => CleanupRet,
        _ => return Err(invalid("unknown IR terminator")),
    })
}
fn term_name(t: ir::TerminatorKind) -> &'static str {
    use ir::TerminatorKind::*;
    match t {
        Br => "br",
        Switch => "switch",
        IndirectBr => "indirectbr",
        Invoke => "invoke",
        CallBr => "callbr",
        Ret => "ret",
        Resume => "resume",
        Unreachable => "unreachable",
        CatchSwitch => "catchswitch",
        CatchRet => "catchret",
        CleanupRet => "cleanupret",
    }
}
fn value_kind(text: &str) -> Result<ir::ValueKind, Error> {
    use ir::ValueKind::*;
    Ok(match text {
        "instruction" => Instruction,
        "argument" => Argument,
        "constant" => Constant,
        "global" => Global,
        "external" => External,
        _ => return Err(invalid("unknown IR value kind")),
    })
}
fn value_name(v: ir::ValueKind) -> &'static str {
    use ir::ValueKind::*;
    match v {
        Instruction => "instruction",
        Argument => "argument",
        Constant => "constant",
        Global => "global",
        External => "external",
    }
}
pub(crate) fn ir_reason(r: ir::AdapterObligationReason) -> &'static str {
    use ir::AdapterObligationReason::*;
    match r {
        UnsupportedInstruction => "unsupported-instruction",
        IncompleteSemantics => "incomplete-semantics",
        UnknownMemoryAlias => "unknown-memory-alias",
        UnmodeledException => "unmodeled-exception",
        UnmodeledSystemCall => "unmodeled-system-call",
        UnmodeledConcurrency => "unmodeled-concurrency",
    }
}
fn parse_ir_reason(text: &str) -> Result<ir::AdapterObligationReason, Error> {
    use ir::AdapterObligationReason::*;
    Ok(match text {
        "unsupported-instruction" => UnsupportedInstruction,
        "incomplete-semantics" => IncompleteSemantics,
        "unknown-memory-alias" => UnknownMemoryAlias,
        "unmodeled-exception" => UnmodeledException,
        "unmodeled-system-call" => UnmodeledSystemCall,
        "unmodeled-concurrency" => UnmodeledConcurrency,
        _ => return Err(invalid("unknown IR adapter obligation")),
    })
}
pub fn decode_ir_request(bytes: &[u8]) -> Result<ir::Request, Error> {
    let dto: IrDto = serde_json::from_value(strict_json(bytes)?)?;
    if dto.schema != "ariadne.llvm-ir-request/v1" {
        return Err(invalid("unsupported IR request schema"));
    }
    let request = ir::Request {
        artifact_id: dto.artifact_id,
        module_id: dto.module_id,
        function_id: dto.function_id,
        verified_ir: dto.verified_ir,
        entry_block: ir::BlockId(dto.entry_block),
        blocks: dto
            .blocks
            .into_iter()
            .map(|(id, row)| {
                Ok((
                    ir::BlockId(id),
                    ir::BlockInfo {
                        terminator: ir::InstructionId(row.terminator),
                        kind: term(&row.kind)?,
                        successors: unique(
                            row.successors
                                .into_iter()
                                .map(|s| {
                                    Ok(ir::Successor {
                                        dst: ir::BlockId(s.dst),
                                        kind: parse_ir_edge(&s.kind)?,
                                    })
                                })
                                .collect::<Result<Vec<_>, Error>>()?,
                        )?,
                    },
                ))
            })
            .collect::<Result<_, Error>>()?,
        instructions: dto
            .instructions
            .into_iter()
            .map(|(id, row)| {
                Ok((
                    ir::InstructionId(id),
                    ir::InstructionInfo {
                        block: ir::BlockId(row.block),
                        index: row.index,
                        uses: unique(row.uses.into_iter().map(ir::ValueId))?,
                        phi_incoming: unique(row.phi_incoming.into_iter().map(|p| {
                            ir::PhiIncoming {
                                pred: ir::BlockId(p.pred),
                                value: ir::ValueId(p.value),
                            }
                        }))?,
                        memory_preds: unique(row.memory_preds.into_iter().map(ir::InstructionId))?,
                        call_targets: unique(row.call_targets.into_iter().map(ir::CalleeId))?,
                    },
                ))
            })
            .collect::<Result<_, Error>>()?,
        values: dto
            .values
            .into_iter()
            .map(|(id, row)| {
                Ok((
                    ir::ValueId(id),
                    ir::ValueInfo {
                        kind: value_kind(&row.kind)?,
                        def_site: ir::InstructionId(row.def_site),
                    },
                ))
            })
            .collect::<Result<_, Error>>()?,
        phi_nodes: unique(dto.phi_nodes.into_iter().map(ir::InstructionId))?,
        call_sites: unique(dto.call_sites.into_iter().map(ir::InstructionId))?,
        callees: unique(dto.callees.into_iter().map(ir::CalleeId))?,
        complete_calls: unique(dto.complete_calls.into_iter().map(ir::InstructionId))?,
        adapter_obligations: unique(
            dto.adapter_obligations
                .into_iter()
                .map(|o| {
                    Ok(ir::AdapterObligation {
                        site: ir::InstructionId(o.site),
                        reason: parse_ir_reason(&o.reason)?,
                    })
                })
                .collect::<Result<Vec<_>, Error>>()?,
        )?,
        slice_seeds: unique(dto.slice_seeds.into_iter().map(ir::InstructionId))?,
    };
    request.validate()?;
    Ok(request)
}
pub fn encode_ir_request(request: &ir::Request) -> Result<Value, Error> {
    request.validate()?;
    Ok(serde_json::to_value(IrDto {
        schema: "ariadne.llvm-ir-request/v1".into(),
        artifact_id: request.artifact_id.clone(),
        module_id: request.module_id.clone(),
        function_id: request.function_id.clone(),
        verified_ir: request.verified_ir,
        entry_block: request.entry_block.0.clone(),
        blocks: request
            .blocks
            .iter()
            .map(|(id, b)| {
                (
                    id.0.clone(),
                    IRBlock {
                        terminator: b.terminator.0.clone(),
                        kind: term_name(b.kind).into(),
                        successors: b
                            .successors
                            .iter()
                            .map(|s| IRSuccessor {
                                dst: s.dst.0.clone(),
                                kind: ir_edge(s.kind).into(),
                            })
                            .collect(),
                    },
                )
            })
            .collect(),
        instructions: request
            .instructions
            .iter()
            .map(|(id, i)| {
                (
                    id.0.clone(),
                    IRInstruction {
                        block: i.block.0.clone(),
                        index: i.index,
                        uses: i.uses.iter().map(|id| id.0.clone()).collect(),
                        phi_incoming: i
                            .phi_incoming
                            .iter()
                            .map(|p| IRPhi {
                                pred: p.pred.0.clone(),
                                value: p.value.0.clone(),
                            })
                            .collect(),
                        memory_preds: i.memory_preds.iter().map(|id| id.0.clone()).collect(),
                        call_targets: i.call_targets.iter().map(|id| id.0.clone()).collect(),
                    },
                )
            })
            .collect(),
        values: request
            .values
            .iter()
            .map(|(id, v)| {
                (
                    id.0.clone(),
                    IRValue {
                        kind: value_name(v.kind).into(),
                        def_site: v.def_site.0.clone(),
                    },
                )
            })
            .collect(),
        phi_nodes: request.phi_nodes.iter().map(|id| id.0.clone()).collect(),
        call_sites: request.call_sites.iter().map(|id| id.0.clone()).collect(),
        callees: request.callees.iter().map(|id| id.0.clone()).collect(),
        complete_calls: request
            .complete_calls
            .iter()
            .map(|id| id.0.clone())
            .collect(),
        adapter_obligations: request
            .adapter_obligations
            .iter()
            .map(|o| IRObligation {
                site: o.site.0.clone(),
                reason: ir_reason(o.reason).into(),
            })
            .collect(),
        slice_seeds: request.slice_seeds.iter().map(|id| id.0.clone()).collect(),
    })?)
}
