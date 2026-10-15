//! Source-bound admission of reviewed MOVAPS normal outcomes and scoped terminals.
//! Facts describe possible states under explicit premises, never execution history.
use super::ast::{Expr, Stmt, Var};
use super::{Error, invalid};
use crate::{Instruction, InstructionKind};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

pub const LEGACY_PROFILE: &str = "bap-guard-admission-v1";
pub const PROFILE: &str = "bap-guard-admission-v2";
pub const LEGACY_PRODUCER_PROFILE: &str = "bap-bit-provenance-v7";
pub const PRODUCER_PROFILE: &str = "bap-bit-provenance-v8";
pub const ABI_POLICY: &str = "windows-amd64-normal-call-entry/v1";
pub const LEGACY_MODEL_VERSION: &str = "ariadne.predicate-admission/v1";
pub const MODEL_VERSION: &str = "ariadne.predicate-admission/v2";
pub const TOP: u16 = u16::MAX;
const LEGACY_SCHEMA: &str = "ariadne.guard-admission/v1";
const SCHEMA: &str = "ariadne.guard-admission/v2";
const PENDING_IDENTITY: &str = "pending-legacy128-movaps-rsp-identity/v1";
const PENDING_LOAD_IDENTITY: &str = "pending-legacy128-movaps-load-rsp-identity/v1";
const TYPED_TRANSFER: &str = "typed-bil-rsp-residue/v1";
const OPAQUE_TRANSFER: &str = "opaque-rsp-havoc/v1";

pub fn model_identity() -> String {
    crate::reports::sha256(include_bytes!("../../Specs/AriadnePredicateAdmission.tla"))
}
pub fn checker_identity() -> String {
    let guard = crate::reports::sha256(include_bytes!("guard_admission.rs"));
    let terminal = crate::reports::sha256(include_bytes!("terminal_control.rs"));
    crate::reports::sha256(format!("ariadne.guard-checker/v2\n{guard}\n{terminal}\n").as_bytes())
}
pub fn legacy_checker_identity() -> String {
    crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/caller-coverage/legacy-v2/guard_admission.rs.txt"
    ))
}
pub fn legacy_model_identity() -> String {
    crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/caller-coverage/legacy-v2/AriadnePredicateAdmission.tla.txt"
    ))
}
pub use super::terminal_control::{NormalFlowEvidence, NormalFlowKind, TerminalReceipt};
fn legacy_input(input: &GuardInput) -> bool {
    input.policy == LEGACY_PROFILE
}
pub fn is_legacy(report: &Report) -> bool {
    report.schema == LEGACY_SCHEMA && report.profile == LEGACY_PROFILE
}
pub fn normal_flow_scope(report: &Report) -> Option<&str> {
    report.input.normal_flow.as_ref().map(|e| e.scope.as_str())
}
pub fn terminal_receipt(input: &GuardInput, site: u64) -> Option<&TerminalReceipt> {
    input
        .normal_flow
        .as_ref()?
        .terminals
        .iter()
        .find(|t| t.site == hex(site))
}
pub fn terminal_valid(site: &CandidateSite, receipt: &TerminalReceipt) -> Result<bool, Error> {
    super::terminal_control::validate_source(site, receipt)?;
    Ok(true)
}
pub fn validate_terminal_capture(receipt: &TerminalReceipt, prefix: &[u8]) -> Result<(), Error> {
    super::terminal_control::validate_capture(receipt, prefix)
}
pub fn validate_normal_flow_request(
    input: &GuardInput,
    request: &crate::AnalysisRequest,
) -> Result<(), Error> {
    if !legacy_input(input) {
        for (&site, instruction) in &request.instructions {
            if instruction.kind == InstructionKind::Stop
                && request.decodable.contains(&site)
                && terminal_receipt(input, site).is_none()
            {
                return Err(invalid("decodable normal Stop lacks a terminal receipt"));
            }
        }
    }
    if let Some(normal) = &input.normal_flow {
        if normal.scope != super::terminal_control::SCOPE
            || (!normal.terminals.is_empty()
                && (request.snapshot_id != input.snapshot
                    || request.input_kind != crate::InputKind::Dump
                    || !request.file_backed.is_empty()
                    || !request.trusted_fallback.is_empty()))
        {
            return Err(invalid(
                "terminal request scope or captured snapshot mismatch",
            ));
        }
        for receipt in &normal.terminals {
            let source = input
                .sites
                .iter()
                .find(|s| s.site == receipt.site)
                .ok_or_else(|| invalid("terminal candidate source absent"))?;
            terminal_valid(source, receipt)?;
            let site = address(&receipt.site)?;
            let instruction = request
                .instructions
                .get(&site)
                .ok_or_else(|| invalid("terminal final instruction absent"))?;
            if instruction.kind != InstructionKind::Stop
                || !instruction.complete
                || !instruction.fall.is_empty()
                || !instruction.targets.is_empty()
                || instruction.uses != request.locations
                || instruction.may_defs != request.locations
                || !instruction.must_defs.is_empty()
                || !request.captured.contains(&site)
                || !request.decodable.contains(&site)
            {
                return Err(invalid(
                    "terminal final request normal-control or conservative-effect mismatch",
                ));
            }
        }
    }
    Ok(())
}

fn deserialize_normal_flow<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<NormalFlowEvidence>, D::Error> {
    NormalFlowEvidence::deserialize(deserializer).map(Some)
}
fn append_normal_flow(
    mut tuple: Vec<u8>,
    evidence: &Option<NormalFlowEvidence>,
) -> Result<Vec<u8>, Error> {
    tuple.pop();
    tuple.push(b',');
    tuple.extend(serde_json::to_vec(evidence)?);
    tuple.push(b']');
    Ok(tuple)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Limits {
    pub max_sites: usize,
    pub max_edges: usize,
    pub max_residue_updates: usize,
    pub max_transfer_evaluations: usize,
    pub max_closure_rounds: usize,
    pub max_evidence_bytes: usize,
    pub max_elapsed_ms: u64,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            max_sites: 4096,
            max_edges: 16384,
            max_residue_updates: 131072,
            max_transfer_evaluations: 262144,
            max_closure_rounds: 8,
            max_evidence_bytes: 4194304,
            max_elapsed_ms: 1000,
        }
    }
}
impl Limits {
    /// Defaults are policy choices, not ceilings. Typed unsigned fields remain
    /// finite; the native wire checker uses their unsigned-64 representation.
    pub fn validate(&self) -> Result<(), Error> {
        for value in [
            self.max_sites,
            self.max_edges,
            self.max_residue_updates,
            self.max_transfer_evaluations,
            self.max_closure_rounds,
            self.max_evidence_bytes,
        ] {
            u64::try_from(value)
                .map_err(|_| invalid("guard budget exceeds unsigned-64 representation"))?;
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ControlKind {
    Ordinary,
    Conditional,
    Jump,
    Indirect,
    Call,
    Return,
    Stop,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CandidateControl {
    pub kind: ControlKind,
    pub fall: Vec<String>,
    pub targets: Vec<String>,
    pub complete: bool,
}
impl CandidateControl {
    pub fn from_instruction(i: &Instruction) -> Self {
        Self {
            kind: match i.kind {
                InstructionKind::Ordinary => ControlKind::Ordinary,
                InstructionKind::Conditional => ControlKind::Conditional,
                InstructionKind::Jump => ControlKind::Jump,
                InstructionKind::Indirect => ControlKind::Indirect,
                InstructionKind::Call => ControlKind::Call,
                InstructionKind::Return => ControlKind::Return,
                InstructionKind::Stop => ControlKind::Stop,
            },
            fall: i.fall.iter().map(|a| hex(*a)).collect(),
            targets: i.targets.iter().map(|a| hex(*a)).collect(),
            complete: i.complete,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CandidateSite {
    pub site: String,
    pub bytes_hex: String,
    /// Exact original serialized AST bytes, before any normal selection.
    pub ast: String,
    pub control: CandidateControl,
    pub opaque: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Root {
    pub site: String,
    /// The coordinator validates the concrete function-entry anchor.
    pub function_entry: bool,
    pub anchor_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Activation {
    pub thread_id: u32,
    pub frame_activation: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Producer {
    pub helper_sha256: String,
    pub runtime_sha256: String,
    pub decoder_sha256: String,
    pub projection: String,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PremiseOrigin {
    AbiNormalCall,
    CapturedRegister,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Premise {
    pub origin: PremiseOrigin,
    pub snapshot: String,
    pub query_scope_sha256: String,
    pub root: String,
    pub point: String,
    pub activation: Activation,
    pub policy: String,
    pub evidence_sha256: String,
    pub rsp_residues: u16,
    pub rsp_value: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GuardInput {
    pub snapshot: String,
    pub artifact_sha256: String,
    pub query_scope_sha256: String,
    pub preparation_sha256: String,
    pub platform: String,
    pub roots: Vec<Root>,
    pub seeds: Vec<String>,
    pub activation: Activation,
    pub premises: Vec<Premise>,
    pub producer: Producer,
    pub policy: String,
    pub model_version: String,
    pub model_sha256: String,
    pub limits: Limits,
    pub candidate_epoch: u64,
    pub closure_complete: bool,
    /// An unresolved incoming/control source. These never become roots.
    pub barriers: Vec<String>,
    pub sites: Vec<CandidateSite>,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "deserialize_normal_flow"
    )]
    pub normal_flow: Option<NormalFlowEvidence>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PendingGuard {
    pub site: String,
    pub displacement: i64,
    pub vector_bank: u8,
    pub original_ast_sha256: String,
    pub pending_relation_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransferReceipt {
    pub site: String,
    pub bytes_sha256: String,
    pub ast_sha256: String,
    pub rule: String,
    /// Row r contains every possible outgoing residue for incoming r.
    pub relation: Vec<u16>,
    pub relation_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResidueFact {
    pub site: String,
    pub residues: u16,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    Aligned,
    Misaligned,
    Unknown,
    Unreached,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GuardDecision {
    pub site: String,
    pub verdict: Verdict,
    pub input_residues: u16,
    pub address_residues: u16,
    pub original_ast_sha256: String,
    pub normal_ast: Option<String>,
    pub normal_ast_sha256: Option<String>,
    pub removed_statement_paths: Vec<String>,
    pub residual: String,
    pub receipt_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Report {
    pub schema: String,
    pub profile: String,
    pub checker_sha256: String,
    pub input: GuardInput,
    pub intent_id: String,
    pub candidate_graph_sha256: String,
    pub transfers: Vec<TransferReceipt>,
    pub facts: Vec<ResidueFact>,
    pub guards: Vec<GuardDecision>,
    pub stop: Option<String>,
    /// Added after the normalized request without final IDs/receipts exists.
    pub final_request_sha256: Option<String>,
}
impl Report {
    pub fn normal_selection(&self, site: u64) -> Option<&str> {
        self.guards
            .iter()
            .find(|g| g.site == hex(site) && g.verdict == Verdict::Aligned)
            .and_then(|g| g.normal_ast.as_deref())
    }
}

fn hex(a: u64) -> String {
    format!("0x{a:016x}")
}
fn address(s: &str) -> Result<u64, Error> {
    let a = s
        .strip_prefix("0x")
        .and_then(|v| u64::from_str_radix(v, 16).ok())
        .ok_or_else(|| invalid("guard address"))?;
    if hex(a) != s {
        return Err(invalid("noncanonical guard address"));
    }
    Ok(a)
}
fn digest_shape(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn bytes(s: &str) -> Result<Vec<u8>, Error> {
    if s.len() % 2 != 0
        || s.len() > 30
        || !s
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid("guard instruction bytes"));
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).map_err(|_| invalid("guard bytes")))
        .collect()
}
fn statements(s: &str) -> Result<Vec<Stmt>, Error> {
    Ok(serde_json::from_value(crate::reports::strict_json(
        s.as_bytes(),
    )?)?)
}

fn architectural(v: &Var, name: &str, width: usize, ty: &str) -> bool {
    !v.virtual_ && v.index == 0 && v.name == name && v.width == width && v.type_ == ty
}
fn integer(e: &Expr) -> Option<(u64, usize)> {
    let Expr::Int { value } = e else {
        return None;
    };
    let (number, width) = value.split_once(':')?;
    let width = width
        .strip_suffix('u')
        .or_else(|| width.strip_suffix('s'))
        .unwrap_or(width)
        .parse::<usize>()
        .ok()?;
    if !(1..=64).contains(&width) {
        return None;
    }
    let n = if let Some(n) = number.strip_prefix("0x") {
        u64::from_str_radix(n, 16).ok()?
    } else {
        let n = number.parse::<i128>().ok()?;
        if n < -(1i128 << (width - 1)) || n >= (1i128 << width) {
            return None;
        }
        n as u64
    };
    if width < 64 && number.starts_with("0x") && n >= 1u64 << width {
        return None;
    }
    Some((n, width))
}
fn integer64(e: &Expr, n: u64) -> bool {
    integer(e) == Some((n, 64))
}
fn rsp_address(e: &Expr) -> Option<i64> {
    match e {
        Expr::Var { var } if architectural(var, "RSP", 64, "imm") => Some(0),
        Expr::Binop { op: 18, lhs, rhs } if matches!(&**lhs, Expr::Var { var } if architectural(var, "RSP", 64, "imm")) => {
            integer(rhs)
                .filter(|(_, width)| *width == 64)
                .map(|(n, _)| n as i64)
        }
        _ => None,
    }
}

/// Independently identify reviewed legacy 128-bit RSP-relative MOVAPS forms.
/// No opcode text, predicate verdict or selected effects justify this rule.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Operation {
    Store,
    Load,
}
fn movaps_encoding(b: &[u8], legacy: bool) -> Option<(i64, u8, Operation)> {
    let (b, high) = match b.first() {
        Some(0x40) => (&b[1..], 0),
        Some(0x44) => (&b[1..], 8),
        _ => (b, 0),
    };
    if b.len() < 4 || b[0] != 0x0f || b[2] & 7 != 4 || b[3] != 0x24 {
        return None;
    }
    let operation = match b[1] {
        0x29 => Operation::Store,
        0x28 if !legacy => Operation::Load,
        _ => return None,
    };
    let bank = ((b[2] >> 3) & 7) + high;
    let displacement = match b[2] >> 6 {
        0 if b.len() == 4 => 0,
        1 if b.len() == 5 => i64::from(b[4] as i8),
        2 if b.len() == 8 => i64::from(i32::from_le_bytes(b[4..8].try_into().ok()?)),
        _ => return None,
    };
    Some((displacement, bank, operation))
}
struct Recognized {
    pending: PendingGuard,
    normal_ast: String,
    pending_rule: &'static str,
}
fn recognize(site: &CandidateSite, legacy: bool) -> Result<Option<Recognized>, Error> {
    let b = bytes(&site.bytes_hex)?;
    let Some((displacement, bank, operation)) = movaps_encoding(&b, legacy) else {
        return Ok(None);
    };
    let va = address(&site.site)?;
    if site.control.kind != ControlKind::Ordinary
        || (!legacy && !site.control.complete)
        || !site.control.targets.is_empty()
        || site.control.fall
            != [hex(va
                .checked_add(b.len() as u64)
                .ok_or_else(|| invalid("guard next address overflow"))?)]
    {
        return Ok(None);
    }
    let bil = statements(&site.ast)?;
    let [Stmt::Move { var, value }, Stmt::If { condition, yes, no }] = bil.as_slice() else {
        return Ok(None);
    };
    if !yes.is_empty() || !matches!(no.as_slice(), [Stmt::Exception { number: 13 }]) {
        return Ok(None);
    }
    let expected_bank = format!("YMM{bank}");
    let shape = match operation {
        Operation::Store => {
            matches!(value,Expr::Store {width:128,mem,addr,value}
                if architectural(var,"mem",0,"mem")
                && matches!(&**mem,Expr::Var {var} if architectural(var,"mem",0,"mem"))
                && rsp_address(addr)==Some(displacement)
                && matches!(&**value,Expr::Cast {op:0,width:128,arg} if matches!(&**arg,Expr::Var {var} if architectural(var,&expected_bank,256,"imm"))))
        }
        Operation::Load => {
            matches!(value,Expr::Concat {lhs,rhs}
                if architectural(var,&expected_bank,256,"imm")
                && matches!(&**lhs,Expr::Extract {hi:255,lo:128,arg} if matches!(&**arg,Expr::Var {var} if architectural(var,&expected_bank,256,"imm")))
                && matches!(&**rhs,Expr::Cast {op:3,width:128,arg}
                    if matches!(&**arg,Expr::Load {width:128,mem,addr}
                        if matches!(&**mem,Expr::Var {var} if architectural(var,"mem",0,"mem")) && rsp_address(addr)==Some(displacement))))
        }
    };
    if !shape {
        return Ok(None);
    }
    let Expr::Binop { op: 5, lhs, rhs } = condition else {
        return Ok(None);
    };
    let Expr::Binop {
        op: 8,
        lhs: guard_addr,
        rhs: mask,
    } = &**lhs
    else {
        return Ok(None);
    };
    if !integer64(rhs, 0) || !integer64(mask, 15) || rsp_address(guard_addr) != Some(displacement) {
        return Ok(None);
    }
    // This validates the normal operation's widths, namespaces and operands.
    // The discarded statement has already been checked in its entirety above.
    super::admission::admit(
        &bil[..1],
        if operation == Operation::Store {
            "MOVAPS-reviewed-store"
        } else {
            "MOVAPS-reviewed-load"
        },
        &b,
    )?;
    let pending_rule = if operation == Operation::Store {
        PENDING_IDENTITY
    } else {
        PENDING_LOAD_IDENTITY
    };
    let normal_ast = serde_json::to_string(&bil[..1])?;
    let relation: Vec<u16> = (0..16).map(|r| 1u16 << r).collect();
    Ok(Some(Recognized {
        pending: PendingGuard {
            site: site.site.clone(),
            displacement,
            vector_bank: bank,
            original_ast_sha256: crate::reports::sha256(site.ast.as_bytes()),
            pending_relation_sha256: crate::reports::sha256(&serde_json::to_vec(&(
                pending_rule,
                &relation,
            ))?),
        },
        normal_ast,
        pending_rule,
    }))
}
/// Recognition authorizes candidate control and an RSP relation, no memory effect.
pub fn recognize_pending(site: &CandidateSite) -> Result<Option<PendingGuard>, Error> {
    Ok(recognize(site, false)?.map(|r| r.pending))
}

pub fn recognize_pending_for_input(
    input: &GuardInput,
    site: &CandidateSite,
) -> Result<Option<PendingGuard>, Error> {
    Ok(recognize(site, legacy_input(input))?.map(|r| r.pending))
}

fn shift(values: u16, delta: u64) -> u16 {
    let mut out = 0;
    for r in 0..16 {
        if values & (1 << r) != 0 {
            out |= 1 << ((r + (delta & 15) as usize) & 15);
        }
    }
    out
}
fn combine(left: u16, right: u16, subtract: bool) -> u16 {
    let mut out = 0;
    for r in 0..16 {
        if right & (1 << r) != 0 {
            let delta = if subtract { (16 - r) & 15 } else { r };
            out |= shift(left, delta);
        }
    }
    out
}
fn expr_residues(e: &Expr, env: &BTreeMap<String, u16>) -> u16 {
    match e {
        Expr::Var { var } if var.type_ == "imm" && var.width == 64 => {
            env.get(&var.key()).copied().unwrap_or(TOP)
        }
        Expr::Int { .. } => integer(e)
            .filter(|(_, width)| *width == 64)
            .map_or(TOP, |(n, _)| 1 << (n & 15)),
        Expr::Binop { op, lhs, rhs } if matches!(op, 17 | 18) => {
            combine(expr_residues(lhs, env), expr_residues(rhs, env), *op == 17)
        }
        Expr::Cast {
            op: 0 | 2 | 3,
            width: 64,
            arg,
        } => {
            // A same-width cast preserves a supported 64-bit expression.
            expr_residues(arg, env)
        }
        Expr::Extract { hi: 63, lo: 0, arg } => expr_residues(arg, env),
        Expr::Let { var, value, body } if var.virtual_ && var.width == 64 => {
            let mut next = env.clone();
            next.insert(var.key(), expr_residues(value, env));
            expr_residues(body, &next)
        }
        _ => TOP,
    }
}
fn transfer_statements(bil: &[Stmt], env: &mut BTreeMap<String, u16>) {
    for stmt in bil {
        match stmt {
            Stmt::Move { var, value } if var.type_ == "imm" && var.width == 64 => {
                let values = expr_residues(value, env);
                env.insert(var.key(), values);
            }
            Stmt::Move { .. } | Stmt::Jump { .. } => {}
            Stmt::If { yes, no, .. } => {
                let mut left = env.clone();
                let mut right = env.clone();
                transfer_statements(yes, &mut left);
                transfer_statements(no, &mut right);
                let keys: BTreeSet<_> = left.keys().chain(right.keys()).cloned().collect();
                *env = keys
                    .into_iter()
                    .map(|key| {
                        let value = left.get(&key).copied().unwrap_or(TOP)
                            | right.get(&key).copied().unwrap_or(TOP);
                        (key, value)
                    })
                    .collect();
            }
            _ => {
                env.insert("RSP:0:false".into(), TOP);
            }
        }
    }
}
fn derive_transfer(
    site: &CandidateSite,
    pending: Option<&Recognized>,
) -> Result<TransferReceipt, Error> {
    let b = bytes(&site.bytes_hex)?;
    let (rule, relation) = if let Some(pending) = pending {
        // Shape recognition precedes every verdict. This relation overapproximates
        // every candidate normal transition and commits no pending store.
        (pending.pending_rule, (0..16).map(|r| 1u16 << r).collect())
    } else if site.opaque || site.control.kind == ControlKind::Call {
        (OPAQUE_TRANSFER, vec![TOP; 16])
    } else {
        let bil = statements(&site.ast)?;
        if super::admission::admit(
            &bil,
            if b == [0x90] {
                "NOOP"
            } else {
                "typed-transfer"
            },
            &b,
        )
        .is_err()
        {
            (OPAQUE_TRANSFER, vec![TOP; 16])
        } else {
            let relation = (0..16)
                .map(|r| {
                    let mut env = [("RSP:0:false".into(), 1u16 << r)].into();
                    transfer_statements(&bil, &mut env);
                    env.get("RSP:0:false").copied().unwrap_or(TOP)
                })
                .collect();
            (TYPED_TRANSFER, relation)
        }
    };
    Ok(TransferReceipt {
        site: site.site.clone(),
        bytes_sha256: crate::reports::sha256(&b),
        ast_sha256: crate::reports::sha256(site.ast.as_bytes()),
        rule: rule.into(),
        relation_sha256: crate::reports::sha256(&serde_json::to_vec(&(rule, &relation))?),
        relation,
    })
}
fn apply(relation: &[u16], values: u16) -> u16 {
    relation
        .iter()
        .enumerate()
        .fold(0, |out, (r, values_after)| {
            if values & (1 << r) != 0 {
                out | values_after
            } else {
                out
            }
        })
}

fn normalized(input: &GuardInput) -> Result<GuardInput, Error> {
    input.limits.validate()?;
    if input.snapshot.is_empty()
        || input.snapshot.len() > 1024
        || input.activation.frame_activation.is_empty()
        || input.activation.frame_activation.len() > 1024
        || input.roots.is_empty()
        || !(if legacy_input(input) {
            input.normal_flow.is_none()
                && input.model_version == LEGACY_MODEL_VERSION
                && input.model_sha256 == legacy_model_identity()
                && input.producer.projection == LEGACY_PRODUCER_PROFILE
        } else {
            input.policy == PROFILE
                && input.normal_flow.is_some()
                && input.model_version == MODEL_VERSION
                && input.model_sha256 == model_identity()
                && input.producer.projection == PRODUCER_PROFILE
        })
    {
        return Err(invalid("guard input profile, snapshot or activation"));
    }
    for hash in [
        &input.artifact_sha256,
        &input.query_scope_sha256,
        &input.preparation_sha256,
        &input.producer.helper_sha256,
        &input.producer.runtime_sha256,
        &input.producer.decoder_sha256,
    ] {
        if !digest_shape(hash) {
            return Err(invalid("guard source identity"));
        }
    }
    let mut out = input.clone();
    out.sites.sort_by(|a, b| a.site.cmp(&b.site));
    out.roots.sort_by(|a, b| a.site.cmp(&b.site));
    out.seeds.sort();
    out.barriers.sort();
    if out.sites.windows(2).any(|s| s[0].site == s[1].site)
        || out.roots.windows(2).any(|s| s[0].site == s[1].site)
        || out.seeds.windows(2).any(|s| s[0] == s[1])
        || out.barriers.windows(2).any(|s| s[0] == s[1])
    {
        return Err(invalid("duplicate guard input point"));
    }
    for point in out.seeds.iter().chain(&out.barriers) {
        address(point)?;
    }
    let mut sites = BTreeSet::new();
    for s in &mut out.sites {
        address(&s.site)?;
        sites.insert(s.site.clone());
        let b = bytes(&s.bytes_hex)?;
        if b.is_empty() && !(s.opaque && s.control.kind == ControlKind::Stop) {
            return Err(invalid("missing guard site bytes without opaque stop"));
        }
        s.control.fall.sort();
        s.control.targets.sort();
        for points in [&s.control.fall, &s.control.targets] {
            if points.windows(2).any(|s| s[0] == s[1]) {
                return Err(invalid("duplicate candidate control target"));
            }
            for p in points {
                address(p)?;
            }
        }
        let has_fall = matches!(
            s.control.kind,
            ControlKind::Ordinary | ControlKind::Conditional | ControlKind::Call
        );
        if s.control.fall.len() != usize::from(has_fall)
            || (matches!(
                s.control.kind,
                ControlKind::Ordinary | ControlKind::Return | ControlKind::Stop
            ) && !s.control.targets.is_empty())
            || (matches!(s.control.kind, ControlKind::Conditional | ControlKind::Jump)
                && s.control.targets.len() != 1)
        {
            return Err(invalid("candidate control shape"));
        }
    }
    if let Some(normal) = &out.normal_flow {
        if normal.scope != super::terminal_control::SCOPE
            || normal.terminals.windows(2).any(|v| v[0].site >= v[1].site)
        {
            return Err(invalid("normal-flow scope or terminal order"));
        }
        for receipt in &normal.terminals {
            let site = out
                .sites
                .iter()
                .find(|s| s.site == receipt.site)
                .ok_or_else(|| invalid("terminal source outside candidate graph"))?;
            terminal_valid(site, receipt)?;
        }
    }
    let roots: BTreeMap<_, _> = out.roots.iter().map(|r| (r.site.as_str(), r)).collect();
    for root in &out.roots {
        address(&root.site)?;
        if !sites.contains(&root.site) || !digest_shape(&root.anchor_sha256) {
            return Err(invalid("guard root anchor"));
        }
    }
    let mut root_states: BTreeMap<_, _> =
        out.roots.iter().map(|r| (r.site.as_str(), TOP)).collect();
    for p in &out.premises {
        let root = roots
            .get(p.root.as_str())
            .ok_or_else(|| invalid("guard premise is not a root"))?;
        if p.snapshot != out.snapshot
            || p.query_scope_sha256 != out.query_scope_sha256
            || p.point != p.root
            || p.activation != out.activation
            || !digest_shape(&p.evidence_sha256)
            || p.rsp_residues == 0
        {
            return Err(invalid("guard premise binding or empty constraint"));
        }
        match p.origin {
            PremiseOrigin::AbiNormalCall => {
                if out.platform != "windows-amd64"
                    || p.policy != ABI_POLICY
                    || !root.function_entry
                    || p.rsp_residues != 1 << 8
                    || p.rsp_value.is_some()
                {
                    return Err(invalid("guard ABI premise policy or entry anchor"));
                }
            }
            PremiseOrigin::CapturedRegister => {
                if p.policy != "captured-register-at-root/v1" || out.activation.thread_id == 0 {
                    return Err(invalid("guard captured observation context"));
                }
                let value = address(
                    p.rsp_value
                        .as_deref()
                        .ok_or_else(|| invalid("guard captured RSP missing"))?,
                )?;
                if p.rsp_residues != 1 << (value & 15) {
                    return Err(invalid("guard captured RSP residue mismatch"));
                }
            }
        }
        *root_states.get_mut(p.root.as_str()).unwrap() &= p.rsp_residues;
    }
    if root_states.values().any(|r| *r == 0) {
        return Err(invalid("inconsistent guard premises"));
    }
    // Serialization order is part of the canonical actual-premise identity.
    let mut premises: Vec<_> = out
        .premises
        .iter()
        .map(|p| Ok((serde_json::to_vec(p)?, p.clone())))
        .collect::<Result<_, Error>>()?;
    premises.sort_by(|a, b| a.0.cmp(&b.0));
    if premises.windows(2).any(|p| p[0].0 == p[1].0) {
        return Err(invalid("duplicate guard premise instance"));
    }
    out.premises = premises.into_iter().map(|(_, p)| p).collect();
    Ok(out)
}
fn root_states(input: &GuardInput) -> BTreeMap<String, u16> {
    let mut states: BTreeMap<_, _> = input.roots.iter().map(|r| (r.site.clone(), TOP)).collect();
    for p in &input.premises {
        *states.get_mut(&p.root).unwrap() &= p.rsp_residues;
    }
    states
}
#[derive(Serialize)]
struct CandidateEdge<'a> {
    src: &'a str,
    dst: &'a str,
    kind: &'static str,
}
fn edges(input: &GuardInput) -> Vec<CandidateEdge<'_>> {
    let mut out = Vec::new();
    for s in &input.sites {
        let fall_kind = match s.control.kind {
            ControlKind::Ordinary => "next",
            ControlKind::Conditional => "fallthrough",
            ControlKind::Call => "summary",
            _ => "next",
        };
        out.extend(s.control.fall.iter().map(|dst| CandidateEdge {
            src: &s.site,
            dst,
            kind: fall_kind,
        }));
        if matches!(
            s.control.kind,
            ControlKind::Conditional | ControlKind::Jump | ControlKind::Indirect
        ) {
            let kind = match s.control.kind {
                ControlKind::Conditional => "taken",
                ControlKind::Jump => "jump",
                _ => "indirect",
            };
            out.extend(s.control.targets.iter().map(|dst| CandidateEdge {
                src: &s.site,
                dst,
                kind,
            }));
        }
        // Call targets remain in source control evidence, not local propagation.
    }
    out
}
fn coverage_closed(input: &GuardInput) -> Result<bool, Error> {
    let points: BTreeSet<_> = input.sites.iter().map(|s| s.site.as_str()).collect();
    if !input.closure_complete
        || !input.barriers.is_empty()
        || input
            .sites
            .iter()
            .any(|s| s.control.kind == ControlKind::Indirect && !s.control.complete)
        || !edges(input).iter().all(|e| points.contains(e.dst))
    {
        return Ok(false);
    }
    for site in &input.sites {
        if matches!(site.control.kind, ControlKind::Call | ControlKind::Return)
            || recognize(site, legacy_input(input))?.is_some()
        {
            continue;
        }
        if !legacy_input(input) && site.control.kind == ControlKind::Stop {
            if terminal_receipt(input, address(&site.site)?).is_some() {
                continue;
            }
            return Ok(false);
        }
        let bil = statements(&site.ast)?;
        let b = bytes(&site.bytes_hex)?;
        if let Err(error) = super::admission::admit(
            &bil,
            if b == [0x90] {
                "NOOP"
            } else {
                "typed-transfer"
            },
            &b,
        ) && !super::admission::ordinary_unknown(&bil, &b, &error)
        {
            // Unreviewed source control cannot borrow an ordinary continuation
            // merely because caller metadata describes one. Ordinary data-only
            // opacity has its separate conservative continuation contract.
            return Ok(false);
        }
    }
    Ok(true)
}
pub fn intent_id(input: &GuardInput) -> Result<String, Error> {
    let i = normalized(input)?;
    let encoded = serde_json::to_vec(&(
        if legacy_input(&i) {
            "ariadne-guard-intent/v1"
        } else {
            "ariadne-guard-intent/v2"
        },
        &i.snapshot,
        &i.artifact_sha256,
        &i.query_scope_sha256,
        &i.preparation_sha256,
        &i.roots,
        &i.seeds,
        &i.activation,
        &i.premises,
        &i.platform,
        &i.policy,
        &i.model_version,
        &i.model_sha256,
        &i.producer,
        &i.limits,
    ))?;
    Ok(crate::reports::sha256(&if legacy_input(&i) {
        encoded
    } else {
        append_normal_flow(encoded, &i.normal_flow)?
    }))
}
pub fn graph_digest(input: &GuardInput) -> Result<String, Error> {
    let i = normalized(input)?;
    let encoded = serde_json::to_vec(&(
        if legacy_input(&i) {
            "ariadne-guard-candidate/v1"
        } else {
            "ariadne-guard-candidate/v2"
        },
        &i.roots,
        i.candidate_epoch,
        i.closure_complete,
        &i.barriers,
        &i.sites,
        edges(&i),
    ))?;
    Ok(crate::reports::sha256(&if legacy_input(&i) {
        encoded
    } else {
        append_normal_flow(encoded, &i.normal_flow)?
    }))
}
fn decision(r: &Recognized, values: u16, closed: bool) -> GuardDecision {
    let addresses = shift(values, r.pending.displacement as u64);
    let verdict = if !closed {
        Verdict::Unknown
    } else if values == 0 {
        Verdict::Unreached
    } else if addresses == 1 {
        Verdict::Aligned
    } else if addresses & 1 == 0 {
        Verdict::Misaligned
    } else {
        Verdict::Unknown
    };
    let aligned = verdict == Verdict::Aligned;
    GuardDecision {
        site: r.pending.site.clone(),
        verdict,
        input_residues: values,
        address_residues: addresses,
        original_ast_sha256: r.pending.original_ast_sha256.clone(),
        normal_ast: aligned.then(|| r.normal_ast.clone()),
        normal_ast_sha256: aligned.then(|| crate::reports::sha256(r.normal_ast.as_bytes())),
        removed_statement_paths: if aligned {
            vec!["bil[1]".into()]
        } else {
            Vec::new()
        },
        residual: match verdict {
            Verdict::Aligned => "alignment-fault-refuted-under-premises",
            Verdict::Misaligned => "normal-refuted-alignment-fault-remains",
            Verdict::Unreached => "unreached-no-predicate-claim",
            Verdict::Unknown => "normal-or-alignment-fault-unresolved",
        }
        .into(),
        receipt_sha256: String::new(),
    }
}
fn receipt_prefix(report: &Report) -> Result<Sha256, Error> {
    let prefix = serde_json::to_vec(&(
        if is_legacy(report) {
            "ariadne-guard-receipt/v1"
        } else {
            "ariadne-guard-receipt/v2"
        },
        &report.checker_sha256,
        &report.intent_id,
        &report.candidate_graph_sha256,
        report.input.candidate_epoch,
        &report.input.model_version,
        &report.input.model_sha256,
        &report.input.premises,
        &report.input.limits,
        &report.transfers,
        &report.facts,
        &report.stop,
        &report.final_request_sha256,
    ))?;
    // Extending this common JSON array preserves the original tuple codec.
    // Cache its SHA256 state to avoid quadratic shared-proof serialization.
    let mut digest = Sha256::new();
    digest.update(&prefix[..prefix.len() - 1]);
    digest.update(b",");
    Ok(digest)
}
fn receipt_digest(prefix: &Sha256, guard: &GuardDecision) -> Result<String, Error> {
    let mut row = guard.clone();
    row.receipt_sha256.clear();
    let mut digest = prefix.clone();
    digest.update(serde_json::to_vec(&row)?);
    digest.update(b"]");
    Ok(format!("{:x}", digest.finalize()))
}
fn refresh_receipts(report: &mut Report) -> Result<(), Error> {
    let prefix = receipt_prefix(report)?;
    let hashes = report
        .guards
        .iter()
        .map(|g| receipt_digest(&prefix, g))
        .collect::<Result<Vec<_>, _>>()?;
    for (guard, hash) in report.guards.iter_mut().zip(hashes) {
        guard.receipt_sha256 = hash;
    }
    Ok(())
}

fn static_limit(input: &GuardInput) -> Option<&'static str> {
    if input.sites.len() > input.limits.max_sites {
        Some("guard-site-limit")
    } else if edges(input).len() > input.limits.max_edges {
        Some("guard-edge-limit")
    } else if input.candidate_epoch >= input.limits.max_closure_rounds as u64 {
        Some("guard-closure-round-limit")
    } else if input.limits.max_elapsed_ms == 0
        || input.limits.max_residue_updates == 0
        || input.limits.max_transfer_evaluations == 0
    {
        Some("guard-zero-work-budget")
    } else {
        None
    }
}
fn deadline(start: Instant, limits: &Limits) -> bool {
    start.elapsed().as_millis() >= u128::from(limits.max_elapsed_ms)
}

/// Derive possible RSP residues over every represented candidate local edge.
/// On a limit or open incoming coverage, every guard retains its stop.
pub fn certify_guards(input: &GuardInput) -> Result<Report, Error> {
    let start = Instant::now();
    let input = normalized(input)?;
    if serde_json::to_vec(&input)?.len() > input.limits.max_evidence_bytes {
        return Err(invalid("guard input evidence byte limit"));
    }
    let mut report = Report {
        schema: if legacy_input(&input) {
            LEGACY_SCHEMA
        } else {
            SCHEMA
        }
        .into(),
        profile: input.policy.clone(),
        checker_sha256: if legacy_input(&input) {
            legacy_checker_identity()
        } else {
            checker_identity()
        },
        intent_id: intent_id(&input)?,
        candidate_graph_sha256: graph_digest(&input)?,
        input,
        transfers: Vec::new(),
        facts: Vec::new(),
        guards: Vec::new(),
        stop: None,
        final_request_sha256: None,
    };
    if let Some(stop) = static_limit(&report.input) {
        report.stop = Some(stop.into());
        return Ok(report);
    }
    let mut recognized = BTreeMap::new();
    for site in &report.input.sites {
        if deadline(start, &report.input.limits) {
            return Err(invalid("guard deadline while deriving source transfers"));
        }
        let guard = recognize(site, legacy_input(&report.input))?;
        report
            .transfers
            .push(derive_transfer(site, guard.as_ref())?);
        if let Some(guard) = guard {
            recognized.insert(site.site.clone(), guard);
        }
    }
    let mut facts: BTreeMap<String, u16> = report
        .input
        .sites
        .iter()
        .map(|s| (s.site.clone(), 0))
        .collect();
    let closed = coverage_closed(&report.input)?;
    for (root, values) in root_states(&report.input) {
        *facts.get_mut(&root).unwrap() |= values;
    }
    // A global conservative widening is used until a region-specific incoming
    // coverage contract is qualified. This does not invent discovery roots.
    if !closed {
        facts.values_mut().for_each(|v| *v = TOP);
        report.stop = Some("candidate-coverage-incomplete".into());
    }
    let relations: BTreeMap<_, _> = report
        .transfers
        .iter()
        .map(|t| (t.site.as_str(), t.relation.as_slice()))
        .collect();
    let mut successors: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for edge in edges(&report.input) {
        if facts.contains_key(edge.dst) {
            successors.entry(edge.src).or_default().push(edge.dst);
        }
    }
    let mut pending: BTreeSet<_> = facts
        .iter()
        .filter_map(|(site, values)| (*values != 0).then_some(site.clone()))
        .collect();
    let mut updates = facts
        .values()
        .try_fold(0usize, |count, value| {
            count.checked_add(value.count_ones() as usize)
        })
        .ok_or_else(|| invalid("guard residue update count overflow"))?;
    let mut evaluations = 0usize;
    while let Some(site) = pending.pop_first() {
        if deadline(start, &report.input.limits) {
            report.stop = Some("guard-deadline-limit".into());
            break;
        }
        if updates > report.input.limits.max_residue_updates {
            report.stop = Some("guard-residue-update-limit".into());
            break;
        }
        let out = apply(relations[site.as_str()], facts[&site]);
        if let Some(next) = successors.get(site.as_str()) {
            for &dst in next {
                if evaluations >= report.input.limits.max_transfer_evaluations {
                    report.stop = Some("guard-transfer-evaluation-limit".into());
                    break;
                }
                evaluations = evaluations
                    .checked_add(1)
                    .ok_or_else(|| invalid("guard transfer evaluation count overflow"))?;
                let fact = facts.get_mut(dst).unwrap();
                let grown = out & !*fact;
                if grown != 0 {
                    updates = updates
                        .checked_add(grown.count_ones() as usize)
                        .ok_or_else(|| invalid("guard residue update count overflow"))?;
                    *fact |= out;
                    pending.insert(dst.to_string());
                }
            }
        }
        if report.stop.as_deref() == Some("guard-transfer-evaluation-limit") {
            break;
        }
    }
    if updates > report.input.limits.max_residue_updates {
        report.stop = Some("guard-residue-update-limit".into());
    }
    if deadline(start, &report.input.limits) {
        report.stop = Some("guard-deadline-limit".into());
    }
    report.facts = facts
        .iter()
        .map(|(site, values)| ResidueFact {
            site: site.clone(),
            residues: *values,
        })
        .collect();
    report.guards = recognized
        .values()
        .map(|r| decision(r, facts[&r.pending.site], closed && report.stop.is_none()))
        .collect();
    if serde_json::to_vec(&report)?.len() > report.input.limits.max_evidence_bytes {
        return Err(invalid("guard receipt evidence byte limit"));
    }
    refresh_receipts(&mut report)?;
    if serde_json::to_vec(&report)?.len() > report.input.limits.max_evidence_bytes {
        // Never publish a partially truncated proof. The coordinator retains the
        // original preparation stop when this bounded evidence cannot be issued.
        return Err(invalid("guard receipt evidence byte limit"));
    }
    replay_report(&report.input, &report)?;
    if deadline(start, &report.input.limits) {
        return Err(invalid("guard deadline before proof publication"));
    }
    Ok(report)
}

/// Reconstruct every source transfer and replay supplied facts as an
/// overapproximation. In particular, candidate-only predecessors are checked.
pub fn replay_report(input: &GuardInput, report: &Report) -> Result<(), Error> {
    let input = normalized(input)?;
    if report.schema
        != if legacy_input(&input) {
            LEGACY_SCHEMA
        } else {
            SCHEMA
        }
        || report.profile != input.policy
        || report.checker_sha256
            != if legacy_input(&input) {
                legacy_checker_identity()
            } else {
                checker_identity()
            }
        || report.input != input
        || report.intent_id != intent_id(&input)?
        || report.candidate_graph_sha256 != graph_digest(&input)?
        || report
            .final_request_sha256
            .as_deref()
            .is_some_and(|h| !digest_shape(h))
    {
        return Err(invalid("guard receipt source, intent or closure binding"));
    }
    if serde_json::to_vec(report)?.len() > input.limits.max_evidence_bytes {
        return Err(invalid("guard receipt evidence byte limit"));
    }
    if let Some(expected) = static_limit(&input) {
        if report.stop.as_deref() != Some(expected)
            || !report.transfers.is_empty()
            || !report.facts.is_empty()
            || !report.guards.is_empty()
        {
            return Err(invalid("guard static-budget stop mismatch"));
        }
        return Ok(());
    }
    let closed = coverage_closed(&input)?;
    match report.stop.as_deref() {
        None if !closed => return Err(invalid("guard open candidate coverage")),
        Some("candidate-coverage-incomplete") if closed => {
            return Err(invalid("guard false coverage stop"));
        }
        None
        | Some(
            "candidate-coverage-incomplete"
            | "guard-deadline-limit"
            | "guard-residue-update-limit"
            | "guard-transfer-evaluation-limit",
        ) => {}
        Some(_) => return Err(invalid("guard unknown stop")),
    }
    let mut recognized = BTreeMap::new();
    let mut transfers = Vec::new();
    for site in &input.sites {
        let guard = recognize(site, legacy_input(&input))?;
        transfers.push(derive_transfer(site, guard.as_ref())?);
        if let Some(guard) = guard {
            recognized.insert(site.site.clone(), guard);
        }
    }
    if report.transfers != transfers {
        return Err(invalid("guard source transfer relation mismatch"));
    }
    let mut facts = BTreeMap::new();
    for fact in &report.facts {
        if facts.insert(fact.site.as_str(), fact.residues).is_some() {
            return Err(invalid("duplicate guard residue fact"));
        }
    }
    if facts.len() != input.sites.len()
        || input
            .sites
            .iter()
            .any(|s| !facts.contains_key(s.site.as_str()))
    {
        return Err(invalid("guard residue fact domain"));
    }
    if report.stop.is_none() || report.stop.as_deref() == Some("candidate-coverage-incomplete") {
        for (root, values) in root_states(&input) {
            if values & !facts[root.as_str()] != 0 {
                return Err(invalid("guard fact omits eligible root residues"));
            }
        }
        if !closed && facts.values().any(|v| *v != TOP) {
            return Err(invalid("guard unresolved incoming must widen to top"));
        }
        let relations: BTreeMap<_, _> = transfers
            .iter()
            .map(|t| (t.site.as_str(), t.relation.as_slice()))
            .collect();
        for edge in edges(&input) {
            if let Some(next) = facts.get(edge.dst)
                && apply(relations[edge.src], facts[edge.src]) & !*next != 0
            {
                return Err(invalid("guard fact omits candidate predecessor residues"));
            }
        }
    }
    if report.guards.len() != recognized.len() {
        return Err(invalid("guard decision domain"));
    }
    let mut seen = BTreeSet::new();
    let prefix = receipt_prefix(report)?;
    for guard in &report.guards {
        let source = recognized
            .get(&guard.site)
            .ok_or_else(|| invalid("unrecognized guard receipt"))?;
        let mut expected = decision(
            source,
            facts[guard.site.as_str()],
            closed && report.stop.is_none(),
        );
        expected.receipt_sha256 = receipt_digest(&prefix, &expected)?;
        if *guard != expected || !seen.insert(&guard.site) {
            return Err(invalid("guard verdict, selection or receipt mismatch"));
        }
    }
    Ok(())
}

/// Bind only the hash of the already normalized request without receipts/IDs.
/// Receipt hashes never include the final analysis ID which contains them.
pub fn bind_final_request(
    input: &GuardInput,
    report: &mut Report,
    request_hash: &str,
) -> Result<(), Error> {
    replay_report(input, report)?;
    if !digest_shape(request_hash) {
        return Err(invalid("guard final request digest"));
    }
    if report
        .final_request_sha256
        .as_deref()
        .is_some_and(|h| h != request_hash)
    {
        return Err(invalid("guard final request already bound differently"));
    }
    let mut bound = report.clone();
    bound.final_request_sha256 = Some(request_hash.into());
    refresh_receipts(&mut bound)?;
    replay_report(input, &bound)?;
    *report = bound;
    Ok(())
}
pub fn analysis_id(report: &Report) -> Result<String, Error> {
    replay_report(&report.input, report)?;
    let request_hash = report
        .final_request_sha256
        .as_ref()
        .ok_or_else(|| invalid("guard request is not finalized"))?;
    let mut receipts: Vec<_> = report
        .guards
        .iter()
        .map(|g| g.receipt_sha256.as_str())
        .collect();
    receipts.sort();
    Ok(crate::reports::sha256(&serde_json::to_vec(&(
        if is_legacy(report) {
            "ariadne-guard-analysis/v1"
        } else {
            "ariadne-guard-analysis/v2"
        },
        &report.intent_id,
        request_hash,
        receipts,
    ))?))
}
pub fn validate_final_request(
    input: &GuardInput,
    report: &Report,
    request_hash: &str,
) -> Result<String, Error> {
    replay_report(input, report)?;
    if report.final_request_sha256.as_deref() != Some(request_hash) {
        return Err(invalid("guard normalized final request mismatch"));
    }
    analysis_id(report)
}
