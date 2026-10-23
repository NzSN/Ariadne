//! Bounded snapshot-relative near-jump resolution over admitted BIL.
//! Candidate destinations do not identify an executed branch or stable history.
use super::ast::{Expr, Stmt};
use super::{Error, invalid};
use crate::{Address, AddressSet, Instruction, InstructionKind, LocationSet};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

pub const PROFILE: &str = "captured-indirect-targets/v1";
pub const LEGACY_LOCAL_PROFILE: &str = "captured-local-indirect-targets/v1";
pub const LOCAL_PROFILE: &str = "captured-local-indirect-targets/v2";
pub const ADVANCED_PROFILE: &str = "captured-indirect-targets/v2";
pub const ADVANCED_LOCAL_PROFILE: &str = "captured-local-indirect-targets/v3";
pub const ADVANCED_SCHEMA: &str = "ariadne.indirect-target-resolution/v4";
pub(crate) const PRE_ADVANCED_LOOP_ENGINE: &str =
    "acdf884e7d041157bab3d1b065a2f9be26653d72f65b00ea8767abc437510d4a";
pub(crate) fn is_advanced(report: &Report) -> bool {
    report.schema == ADVANCED_SCHEMA
        && [ADVANCED_PROFILE, ADVANCED_LOCAL_PROFILE].contains(&report.profile.as_str())
}
pub(crate) fn promote_advanced(report: &mut Report) -> Result<(), Error> {
    report.profile = match report.profile.as_str() {
        PROFILE => ADVANCED_PROFILE,
        LOCAL_PROFILE => ADVANCED_LOCAL_PROFILE,
        _ => return Err(invalid("source advanced target promotion profile")),
    }
    .into();
    report.schema = ADVANCED_SCHEMA.into();
    Ok(())
}
#[path = "target_resolution/loop_closure.rs"]
mod loop_closure;
pub use loop_closure::{CoverageEvidence, LoopClosureReceipt};

pub(crate) fn loop_engine_identity() -> String {
    let resolver = crate::reports::sha256(include_bytes!("target_resolution.rs"));
    let closure = crate::reports::sha256(include_bytes!("target_resolution/loop_closure.rs"));
    crate::reports::sha256(
        format!("ariadne.loop-target-engine/v1\n{resolver}\n{closure}\n").as_bytes(),
    )
}
pub(crate) const LEGACY_QUESTION_LOOP_ENGINE: &str =
    "afc1b4b991a2bdf402dc8036eb0cfba0d0232505ea5dab31a6e2e2d267a15d95";
pub const MEMORY_PREMISE: &str = "FrozenCapturedControlData";
const BANKS: [&str; 16] = [
    "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12", "R13",
    "R14", "R15",
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Limits {
    pub max_entries: usize,
    pub max_targets: usize,
    pub max_read_bytes: usize,
    pub max_evidence_bytes: usize,
    pub max_values: usize,
    pub max_steps: usize,
    pub max_path_steps: usize,
    pub max_rounds: usize,
    pub max_elapsed_ms: u64,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            max_entries: 4096,
            max_targets: 65536,
            max_read_bytes: 1048576,
            max_evidence_bytes: 4194304,
            max_values: 256,
            max_steps: 262144,
            max_path_steps: 256,
            max_rounds: 16,
            max_elapsed_ms: 1000,
        }
    }
}
impl Limits {
    /// Caller-selected finite budgets are independent of their defaults.
    pub fn validate(&self) -> Result<(), Error> {
        for n in [
            self.max_entries,
            self.max_targets,
            self.max_read_bytes,
            self.max_evidence_bytes,
            self.max_values,
            self.max_steps,
            self.max_path_steps,
            self.max_rounds,
        ] {
            u64::try_from(n).map_err(|_| invalid("resolver unsigned budget representation"))?;
        }
        Ok(())
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contributor {
    pub stream: u32,
    pub entry: usize,
    pub file_offset: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Span {
    pub address: String,
    pub length: usize,
    pub contributors: Vec<Contributor>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DataRead {
    pub address: String,
    pub requested: usize,
    pub bytes_hex: String,
    pub spans: Vec<Span>,
    pub conflict_sources: Vec<Contributor>,
    pub stop: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Term {
    width: u8,
    kind: TermKind,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum TermKind {
    Constant {
        value: String,
    },
    Input {
        key: String,
    },
    Unknown,
    Binary {
        op: i32,
        left: Box<Term>,
        right: Box<Term>,
    },
    Unary {
        op: i32,
        arg: Box<Term>,
    },
    Cast {
        op: i32,
        arg: Box<Term>,
    },
    Load {
        site: String,
        address: Box<Term>,
    },
}
fn hex(a: u64) -> String {
    format!("0x{a:016x}")
}
fn address(s: &str) -> Result<u64, Error> {
    let value = s
        .strip_prefix("0x")
        .and_then(|v| u64::from_str_radix(v, 16).ok())
        .ok_or_else(|| invalid("resolver address"))?;
    if hex(value) != s {
        return Err(invalid("noncanonical resolver address"));
    }
    Ok(value)
}
fn mask(width: u8) -> u64 {
    if width == 64 {
        u64::MAX
    } else {
        (1u64 << width) - 1
    }
}
fn signed(value: u64, width: u8) -> i64 {
    ((value << (64 - width)) as i64) >> (64 - width)
}
impl Term {
    fn unknown(width: u8) -> Self {
        Self {
            width,
            kind: TermKind::Unknown,
        }
    }
    fn constant(value: u64, width: u8) -> Self {
        Self {
            width,
            kind: TermKind::Constant {
                value: hex(value & mask(width)),
            },
        }
    }
    fn number(&self) -> Option<u64> {
        if let TermKind::Constant { value } = &self.kind {
            address(value).ok()
        } else {
            None
        }
    }
    fn input(key: String, width: u8) -> Self {
        Self {
            width,
            kind: TermKind::Input { key },
        }
    }
    fn cast(op: i32, width: u8, arg: Self) -> Self {
        if width == arg.width && matches!(op, 0 | 2 | 3) {
            return arg;
        }
        if op == 0
            && let TermKind::Cast { op: 3, arg: inner } = &arg.kind
            && width == inner.width
        {
            return *inner.clone();
        }
        if op == 3
            && let TermKind::Cast { op: 3, arg: inner } = &arg.kind
            && width >= arg.width
        {
            return Self::cast(3, width, *inner.clone());
        }
        if let Some(n) = arg.number() {
            let value = match op {
                0 | 3 => n,
                1 if width <= arg.width => n >> (arg.width - width),
                2 if width >= arg.width => signed(n, arg.width) as u64,
                _ => return Self::unknown(width),
            };
            return Self::constant(value, width);
        }
        Self {
            width,
            kind: TermKind::Cast {
                op,
                arg: Box::new(arg),
            },
        }
    }
    fn unary(op: i32, arg: Self) -> Self {
        if let Some(n) = arg.number() {
            return Self::constant(if op == 0 { !n } else { n.wrapping_neg() }, arg.width);
        }
        Self {
            width: arg.width,
            kind: TermKind::Unary {
                op,
                arg: Box::new(arg),
            },
        }
    }
    fn binary(op: i32, left: Self, right: Self) -> Self {
        let width = if op <= 5 { 1 } else { left.width };
        if left.width != right.width {
            return Self::unknown(width);
        }
        if let (Some(l), Some(r)) = (left.number(), right.number()) {
            let value = match op {
                0 => u64::from(signed(l, left.width) <= signed(r, right.width)),
                1 => u64::from(signed(l, left.width) < signed(r, right.width)),
                2 => u64::from(l <= r),
                3 => u64::from(l < r),
                4 => u64::from(l != r),
                5 => u64::from(l == r),
                6 => l ^ r,
                7 => l | r,
                8 => l & r,
                9 => {
                    if r >= u64::from(left.width) {
                        if signed(l, left.width) < 0 {
                            u64::MAX
                        } else {
                            0
                        }
                    } else {
                        (signed(l, left.width) >> r) as u64
                    }
                }
                10 => {
                    if r >= 64 {
                        0
                    } else {
                        l >> r
                    }
                }
                11 => {
                    if r >= 64 {
                        0
                    } else {
                        l << r
                    }
                }
                16 => l.wrapping_mul(r),
                17 => l.wrapping_sub(r),
                18 => l.wrapping_add(r),
                _ => return Self::unknown(width),
            };
            return Self::constant(value, width);
        }
        // Modular subtraction equals zero exactly when its operands are equal.
        if op == 5 {
            let sub = if left.number() == Some(0) {
                &right
            } else if right.number() == Some(0) {
                &left
            } else {
                &Self::unknown(1)
            };
            if let TermKind::Binary {
                op: 17,
                left: a,
                right: b,
            } = &sub.kind
            {
                return Self::binary(5, *a.clone(), *b.clone());
            }
        }
        Self {
            width,
            kind: TermKind::Binary {
                op,
                left: Box::new(left),
                right: Box::new(right),
            },
        }
    }
    fn rewrite(
        &self,
        outputs: &BTreeMap<String, Term>,
        killed: &LocationSet,
        steps: &mut usize,
    ) -> Option<Self> {
        if *steps == 0 {
            return None;
        }
        *steps -= 1;
        Some(match &self.kind {
            TermKind::Input { key } => {
                if let Some(value) = outputs.get(key) {
                    value.clone()
                } else if clobbered(key, killed) {
                    Self::unknown(self.width)
                } else {
                    self.clone()
                }
            }
            TermKind::Binary { op, left, right } => Self::binary(
                *op,
                left.rewrite(outputs, killed, steps)?,
                right.rewrite(outputs, killed, steps)?,
            ),
            TermKind::Unary { op, arg } => Self::unary(*op, arg.rewrite(outputs, killed, steps)?),
            TermKind::Cast { op, arg } => {
                Self::cast(*op, self.width, arg.rewrite(outputs, killed, steps)?)
            }
            TermKind::Load { site, address } => Self {
                width: self.width,
                kind: TermKind::Load {
                    site: site.clone(),
                    address: Box::new(address.rewrite(outputs, killed, steps)?),
                },
            },
            _ => self.clone(),
        })
    }
}
fn clobbered(key: &str, locations: &LocationSet) -> bool {
    let name = key.split(':').next().unwrap_or("");
    if let Some(bank) = BANKS.iter().position(|v| *v == name) {
        (0..8).any(|byte| {
            locations.contains(&format!("gpr:{}:{byte}", BANKS[bank].to_ascii_lowercase()))
        })
    } else {
        locations.contains(&format!("flag:{}", name.to_ascii_lowercase()))
    }
}
fn lift_expr(e: &Expr, env: &BTreeMap<String, Term>, site: u64, depth: usize) -> Term {
    if depth > 32 {
        return Term::unknown(64);
    }
    let child = |e| lift_expr(e, env, site, depth + 1);
    match e {
        Expr::Var { var } => env.get(&var.key()).cloned().unwrap_or_else(|| {
            if !var.virtual_ && var.name == "RIP" {
                Term::constant(site, 64)
            } else if !var.virtual_ && var.type_ == "imm" && (1..=64).contains(&var.width) {
                Term::input(var.key(), var.width as u8)
            } else {
                Term::unknown(var.width.clamp(1, 64) as u8)
            }
        }),
        Expr::Int { value } => {
            let n = value.split_once(':').and_then(|(n, w)| {
                let width = w.trim_end_matches(['u', 's']).parse::<u8>().ok()?;
                let v = if let Some(h) = n.strip_prefix("0x") {
                    u64::from_str_radix(h, 16).ok()?
                } else {
                    n.parse::<i64>().ok()? as u64
                };
                (width > 0 && width <= 64).then_some((v, width))
            });
            n.map(|(v, w)| Term::constant(v, w))
                .unwrap_or_else(|| Term::unknown(64))
        }
        Expr::Cast { op, width, arg } if (1..=64).contains(width) => {
            Term::cast(*op, *width as u8, child(arg))
        }
        Expr::Extract { hi, lo, arg } if *lo == 0 && *hi < 64 => {
            Term::cast(0, (*hi + 1) as u8, child(arg))
        }
        Expr::Binop { op, lhs, rhs } if matches!(op,0..=11|16..=18) => {
            Term::binary(*op, child(lhs), child(rhs))
        }
        Expr::Unop { op, arg } if matches!(op, 0 | 1) => Term::unary(*op, child(arg)),
        Expr::Load { width, addr, .. } if matches!(width, 8 | 16 | 32 | 64) => Term {
            width: *width as u8,
            kind: TermKind::Load {
                site: hex(site),
                address: Box::new(child(addr)),
            },
        },
        Expr::Let { var, value, body } => {
            let mut local = env.clone();
            local.insert(var.key(), child(value));
            lift_expr(body, &local, site, depth + 1)
        }
        _ => Term::unknown(64),
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Transfer {
    pub site: String,
    pub bytes_hex: String,
    pub ast: String,
    pub ast_sha256: String,
    outputs: BTreeMap<String, Term>,
    jump: Option<Term>,
    condition: Option<Term>,
}
impl Transfer {
    pub(crate) fn is_scalar_identity(&self) -> bool {
        self.outputs.is_empty() && self.jump.is_none() && self.condition.is_none()
    }
}
fn loop_writes(statements: &[Stmt], writes: &mut BTreeMap<String, super::ast::Var>) {
    for statement in statements {
        match statement {
            Stmt::Move { var, .. } => {
                if var.type_ == "imm" && (1..=64).contains(&var.width) {
                    writes.insert(var.key(), var.clone());
                }
            }
            Stmt::If { yes, no, .. } => {
                loop_writes(yes, writes);
                loop_writes(no, writes);
            }
            Stmt::While { body, .. } => loop_writes(body, writes),
            _ => {}
        }
    }
}
pub(crate) fn extract(statements: &[Stmt], site: u64, bytes: &[u8]) -> Result<Transfer, Error> {
    let mut env = BTreeMap::new();
    let mut outputs = BTreeSet::new();
    let mut jump = None;
    let mut condition = None;
    for statement in statements {
        match statement {
            Stmt::Move { var, value } => {
                let term = lift_expr(value, &env, site, 0);
                if var.type_ == "imm" && (1..=64).contains(&var.width) {
                    let term = if term.width == var.width as u8 {
                        term
                    } else {
                        Term::unknown(var.width as u8)
                    };
                    env.insert(var.key(), term);
                    if !var.virtual_
                        && (BANKS.contains(&var.name.as_str())
                            || ["CF", "ZF"].contains(&var.name.as_str()))
                    {
                        outputs.insert(var.key());
                    }
                }
            }
            Stmt::Jump { target } => jump = Some(lift_expr(target, &env, site, 0)),
            Stmt::If {
                condition: c,
                yes,
                no,
            } if no.is_empty() && yes.len() == 1 && matches!(yes[0], Stmt::Jump { .. }) => {
                condition = Some(lift_expr(c, &env, site, 0))
            }
            Stmt::While { body, .. } => {
                let mut writes = BTreeMap::new();
                loop_writes(body, &mut writes);
                for (key, var) in writes {
                    // The body may execute zero or many times. Neither an
                    // earlier constant nor one execution is a post-loop fact.
                    env.insert(key.clone(), Term::unknown(var.width as u8));
                    if !var.virtual_
                        && (BANKS.contains(&var.name.as_str())
                            || ["CF", "ZF"].contains(&var.name.as_str()))
                    {
                        outputs.insert(key);
                    }
                }
            }
            _ => {}
        }
    }
    let ast = serde_json::to_string(statements)?;
    Ok(Transfer {
        site: hex(site),
        bytes_hex: bytes.iter().map(|b| format!("{b:02x}")).collect(),
        ast_sha256: crate::reports::sha256(ast.as_bytes()),
        ast,
        outputs: outputs
            .into_iter()
            .filter_map(|key| env.remove(&key).map(|v| (key, v)))
            .collect(),
        jump,
        condition,
    })
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Guard {
    expression: Term,
    taken: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entry {
    #[serde(with = "crate::investigation::model::va")]
    pub index: u64,
    pub slot: String,
    pub bytes_hex: String,
    pub target: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PathReceipt {
    pub root: String,
    /// Unconstrained register state at a bounded local cut, never a new root.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub frontier: bool,
    pub reverse_path: Vec<String>,
    pub reverse_edges: Vec<bool>,
    pub form: String,
    pub base: String,
    #[serde(with = "unsigned_vec")]
    pub indices: Vec<u64>,
    pub entries: Vec<Entry>,
    expression: Term,
    guards: Vec<Guard>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Resolution {
    pub site: String,
    pub targets: Vec<String>,
    pub complete: bool,
    pub paths: Vec<PathReceipt>,
    pub unresolved: BTreeSet<String>,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "deserialize_coverage"
    )]
    pub coverage: Option<CoverageEvidence>,
}
// Absence preserves the frozen legacy wire. A present field must contain a
// coverage variant; JSON null is not an alternate spelling of omission.
fn deserialize_coverage<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<CoverageEvidence>, D::Error> {
    CoverageEvidence::deserialize(deserializer).map(Some)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Report {
    pub schema: String,
    pub profile: String,
    pub memory_premise: String,
    pub snapshot: String,
    pub artifact_sha256: String,
    pub graph_sha256: String,
    pub limits: Limits,
    pub resolutions: Vec<Resolution>,
    pub data_reads: Vec<DataRead>,
    pub(crate) transfers: Vec<Transfer>,
    pub stop: Option<String>,
}
pub(crate) fn legacy_graph_digest(
    instructions: &BTreeMap<Address, Instruction>,
    roots: &AddressSet,
) -> Result<String, Error> {
    let rows: Vec<_> = instructions
        .iter()
        .map(|(&a, i)| {
            (
                hex(a),
                format!("{:?}", i.kind),
                i.fall.iter().map(|v| hex(*v)).collect::<Vec<_>>(),
                i.targets.iter().map(|v| hex(*v)).collect::<Vec<_>>(),
                &i.uses,
                &i.may_defs,
                &i.must_defs,
            )
        })
        .collect();
    Ok(crate::reports::sha256(&serde_json::to_vec(&(roots, rows))?))
}
pub(crate) fn graph_digest(
    instructions: &BTreeMap<Address, Instruction>,
    roots: &AddressSet,
) -> Result<String, Error> {
    let legacy = legacy_graph_digest(instructions, roots)?;
    let completeness: Vec<_> = instructions
        .iter()
        .map(|(a, i)| (hex(*a), i.complete))
        .collect();
    Ok(crate::reports::sha256(&serde_json::to_vec(&(
        legacy,
        completeness,
    ))?))
}
pub(crate) fn report_graph_digest(
    report: &Report,
    instructions: &BTreeMap<Address, Instruction>,
    roots: &AddressSet,
) -> Result<String, Error> {
    if report.schema == "ariadne.indirect-target-resolution/v3"
        || (is_advanced(report) && report.profile == ADVANCED_LOCAL_PROFILE)
    {
        graph_digest(instructions, roots)
    } else {
        legacy_graph_digest(instructions, roots)
    }
}
pub(crate) fn invalidate_loop_coverage(report: &mut Report, reason: &str) {
    for row in &mut report.resolutions {
        if matches!(
            row.coverage,
            Some(CoverageEvidence::InductiveDispatch { .. })
        ) {
            row.coverage = Some(CoverageEvidence::ExistingPrefixTree {
                path_receipt_refs: (0..row.paths.len()).collect(),
            });
            row.complete = false;
            row.unresolved.insert(reason.to_owned());
        }
    }
}

fn successors(i: &Instruction) -> Vec<(u64, bool)> {
    let mut out = Vec::new();
    if matches!(
        i.kind,
        InstructionKind::Ordinary | InstructionKind::Conditional | InstructionKind::Call
    ) {
        out.extend(i.fall.iter().map(|v| (*v, false)));
    }
    if matches!(
        i.kind,
        InstructionKind::Conditional | InstructionKind::Jump | InstructionKind::Indirect
    ) {
        out.extend(i.targets.iter().map(|v| (*v, true)));
    }
    out
}
fn values(t: &Term, cap: usize, depth: usize) -> Option<BTreeSet<u64>> {
    if depth > 32 || cap == 0 {
        return None;
    }
    if let Some(n) = t.number() {
        return Some([n].into());
    }
    match &t.kind {
        TermKind::Load { .. } if t.width <= 16 && (1usize << t.width) <= cap => {
            Some((0..(1u64 << t.width)).collect())
        }
        TermKind::Unary { op, arg } => Some(
            values(arg, cap, depth + 1)?
                .into_iter()
                .map(|v| {
                    Term::unary(*op, Term::constant(v, arg.width))
                        .number()
                        .unwrap()
                })
                .collect(),
        ),
        TermKind::Cast { op, arg } => values(arg, cap, depth + 1)?
            .into_iter()
            .map(|v| Term::cast(*op, t.width, Term::constant(v, arg.width)).number())
            .collect(),
        TermKind::Binary { op, left, right } => {
            if *op == 8 {
                let bounded = left.number().or_else(|| right.number());
                if let Some(m) = bounded
                    && m < cap as u64
                {
                    return Some((0..=m).filter(|v| v & !m == 0).collect());
                }
            }
            let l = values(left, cap, depth + 1)?;
            let r = values(right, cap, depth + 1)?;
            if l.len().checked_mul(r.len())? > cap {
                return None;
            }
            let mut out = BTreeSet::new();
            for a in l {
                for b in &r {
                    out.insert(
                        Term::binary(
                            *op,
                            Term::constant(a, left.width),
                            Term::constant(*b, right.width),
                        )
                        .number()?,
                    );
                }
            }
            Some(out)
        }
        _ => None,
    }
}
fn evaluate(t: &Term, index: &Term, value: u64, depth: usize) -> Option<u64> {
    if depth > 32 {
        return None;
    }
    if t == index {
        return Some(value);
    }
    if let Some(v) = t.number() {
        return Some(v);
    }
    match &t.kind {
        TermKind::Binary { op, left, right } => Term::binary(
            *op,
            Term::constant(evaluate(left, index, value, depth + 1)?, left.width),
            Term::constant(evaluate(right, index, value, depth + 1)?, right.width),
        )
        .number(),
        TermKind::Unary { op, arg } => Term::unary(
            *op,
            Term::constant(evaluate(arg, index, value, depth + 1)?, arg.width),
        )
        .number(),
        TermKind::Cast { op, arg } => Term::cast(
            *op,
            t.width,
            Term::constant(evaluate(arg, index, value, depth + 1)?, arg.width),
        )
        .number(),
        _ => None,
    }
}
fn same_unsigned_index(term: &Term, index: &Term) -> bool {
    term == index
        || matches!(&term.kind,
        TermKind::Cast { op: 3, arg } if term.width >= arg.width && same_unsigned_index(arg, index))
}
fn range(t: &Term, taken: bool, index: &Term) -> (u64, u64) {
    let full = (0, mask(index.width));
    match &t.kind {
        TermKind::Unary { op: 0, arg } if t.width == 1 => range(arg, !taken, index),
        TermKind::Binary { op, left, right } if matches!(op, 7 | 8) && t.width == 1 => {
            let a = range(left, taken, index);
            let b = range(right, taken, index);
            if (*op == 7 && !taken) || (*op == 8 && taken) {
                (a.0.max(b.0), a.1.min(b.1))
            } else {
                (a.0.min(b.0), a.1.max(b.1))
            }
        }
        TermKind::Binary { op, left, right }
            if same_unsigned_index(left, index) && right.number().is_some() =>
        {
            let k = right.number().unwrap();
            let max = mask(index.width);
            match (*op, taken) {
                (2, true) => (0, k),
                (3, true) if k > 0 => (0, k - 1),
                (2, false) if k < max => (k + 1, max),
                (3, false) => (k, max),
                (5, true) => (k, k),
                (4, false) => (k, k),
                (5, false) | (4, true) if k == 0 => (1, max),
                _ => full,
            }
        }
        TermKind::Binary { op: 5, left, right }
            if same_unsigned_index(right, index) && left.number().is_some() =>
        {
            range(
                &Term::binary(5, *right.clone(), *left.clone()),
                taken,
                index,
            )
        }
        _ => full,
    }
}
fn relative(t: &Term) -> Option<(u64, Term)> {
    let TermKind::Binary {
        op: 18,
        left,
        right,
    } = &t.kind
    else {
        return None;
    };
    let (base, offset) = if let Some(b) = left.number() {
        (b, right.as_ref())
    } else {
        (right.number()?, left.as_ref())
    };
    let TermKind::Cast { op: 2, arg } = &offset.kind else {
        return None;
    };
    if offset.width != 64 || arg.width != 32 {
        return None;
    }
    let TermKind::Load { address, .. } = &arg.kind else {
        return None;
    };
    let TermKind::Binary {
        op: 18,
        left,
        right,
    } = &address.kind
    else {
        return None;
    };
    let scaled = if left.number() == Some(base) {
        right.as_ref()
    } else if right.number() == Some(base) {
        left.as_ref()
    } else {
        return None;
    };
    let TermKind::Binary { op, left, right } = &scaled.kind else {
        return None;
    };
    if !((*op == 11 && right.number() == Some(2)) || (*op == 16 && right.number() == Some(4))) {
        return None;
    }
    let index = if let TermKind::Cast { op: 3, arg } = &left.kind {
        *arg.clone()
    } else {
        *left.clone()
    };
    if has_unknown(&index) {
        return None;
    }
    Some((base, index))
}
fn has_unknown(t: &Term) -> bool {
    match &t.kind {
        TermKind::Unknown => true,
        TermKind::Binary { left, right, .. } => has_unknown(left) || has_unknown(right),
        TermKind::Unary { arg, .. } | TermKind::Cast { arg, .. } => has_unknown(arg),
        TermKind::Load { address, .. } => has_unknown(address),
        _ => false,
    }
}
fn bounded_form(term: &Term, guards: &[Guard], limits: &Limits) -> bool {
    if let Some((_, index)) = relative(term) {
        if values(&index, limits.max_values, 0).is_some() {
            return true;
        }
        let (low, high) = guards.iter().fold((0, mask(index.width)), |a, g| {
            let b = range(&g.expression, g.taken, &index);
            (a.0.max(b.0), a.1.min(b.1))
        });
        high.checked_sub(low)
            .is_some_and(|n| n < limits.max_entries as u64)
    } else {
        matches!(&term.kind, TermKind::Load { address, .. }
            if term.width == 64 && address.number().is_some())
    }
}
/// Relational subjects retain definition/read identity; Unsupported Unknown
/// is never a common symbolic value and cannot justify a contradiction.
fn guard_subjects(term: &Term, depth: usize, out: &mut Vec<Term>) {
    if depth > 32 {
        return;
    }
    match &term.kind {
        TermKind::Binary { op, left, right } => {
            if *op <= 5 {
                for subject in [left.as_ref(), right.as_ref()] {
                    if subject.number().is_none() && !has_unknown(subject) && !out.contains(subject)
                    {
                        out.push(subject.clone());
                    }
                }
            }
            guard_subjects(left, depth + 1, out);
            guard_subjects(right, depth + 1, out);
        }
        TermKind::Unary { arg, .. } | TermKind::Cast { arg, .. } => {
            guard_subjects(arg, depth + 1, out)
        }
        TermKind::Load { address, .. } => guard_subjects(address, depth + 1, out),
        _ => {}
    }
}
fn guards_infeasible(guards: &[Guard], limits: &Limits) -> bool {
    let mut subjects = Vec::new();
    for guard in guards {
        guard_subjects(&guard.expression, 0, &mut subjects);
    }
    subjects.iter().any(|subject| {
        let (low, high) = guards
            .iter()
            .fold((0, mask(subject.width)), |(low, high), guard| {
                let (a, b) = range(&guard.expression, guard.taken, subject);
                (low.max(a), high.min(b))
            });
        low > high
            || high.checked_sub(low).is_some_and(|distance| {
                distance < limits.max_values as u64
                    && (low..=high).all(|value| {
                        guards.iter().any(|guard| {
                            evaluate(&guard.expression, subject, value, 0)
                                .is_some_and(|v| (v != 0) != guard.taken)
                        })
                    })
            })
    })
}
fn memory_write_expr(expr: &Expr) -> bool {
    match expr {
        Expr::Store { .. } => true,
        Expr::Load { mem, addr, .. }
        | Expr::Binop {
            lhs: mem,
            rhs: addr,
            ..
        }
        | Expr::Concat {
            lhs: mem,
            rhs: addr,
        } => memory_write_expr(mem) || memory_write_expr(addr),
        Expr::Unop { arg, .. } | Expr::Cast { arg, .. } | Expr::Extract { arg, .. } => {
            memory_write_expr(arg)
        }
        Expr::Ite { condition, yes, no } => {
            memory_write_expr(condition) || memory_write_expr(yes) || memory_write_expr(no)
        }
        Expr::Let { value, body, .. } => memory_write_expr(value) || memory_write_expr(body),
        _ => false,
    }
}
fn memory_write_bil(statements: &[Stmt]) -> bool {
    statements.iter().any(|stmt| match stmt {
        Stmt::Move { var, value } => var.type_ == "mem" || memory_write_expr(value),
        Stmt::Jump { target } => memory_write_expr(target),
        Stmt::If { condition, yes, no } => {
            memory_write_expr(condition) || memory_write_bil(yes) || memory_write_bil(no)
        }
        _ => true,
    })
}
fn writes_address_bil(statements: &[Stmt], keys: &BTreeSet<String>) -> bool {
    statements.iter().any(|stmt| match stmt {
        Stmt::Move { var, .. } => !var.virtual_ && keys.contains(&var.key()),
        Stmt::If { yes, no, .. } => writes_address_bil(yes, keys) || writes_address_bil(no, keys),
        Stmt::While { body, .. } => writes_address_bil(body, keys),
        _ => false,
    })
}
fn address_inputs(term: &Term, inside: bool, out: &mut BTreeSet<String>) {
    match &term.kind {
        TermKind::Input { key } if inside => {
            out.insert(key.clone());
        }
        TermKind::Load { address, .. } => address_inputs(address, true, out),
        TermKind::Binary { left, right, .. } => {
            address_inputs(left, inside, out);
            address_inputs(right, inside, out);
        }
        TermKind::Unary { arg, .. } | TermKind::Cast { arg, .. } => {
            address_inputs(arg, inside, out)
        }
        _ => {}
    }
}
/// At most one observed simple cycle is unfolded, preserving its edge word.
/// Only the first repeated edge may differ (exit versus closing cycle edge).
fn cycle_window(path: &[(u64, bool)]) -> Option<(usize, usize)> {
    let mut seen: BTreeMap<u64, usize> = BTreeMap::new();
    let mut cycle: Option<(usize, usize)> = None;
    for (at, &(site, taken)) in path.iter().enumerate() {
        if let Some((first, repeated)) = cycle {
            let relative = at - repeated;
            if relative >= repeated - first
                || path[first + relative].0 != site
                || (relative > 0 && path[first + relative].1 != taken)
            {
                return None;
            }
        } else if let Some(&first) = seen.get(&site) {
            cycle = Some((first, at));
        } else {
            seen.insert(site, at);
        }
    }
    cycle
}
fn stable_cycle(
    path: &[(u64, bool)],
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
    term: &Term,
    guards: &[Guard],
) -> bool {
    let Some((first, repeated)) = cycle_window(path) else {
        return false;
    };
    let mut keys = BTreeSet::new();
    address_inputs(term, false, &mut keys);
    for guard in guards {
        address_inputs(&guard.expression, false, &mut keys);
    }
    path[first..repeated].iter().all(|(site, _)| {
        let instruction = &instructions[site];
        let Some(transfer) = transfers.get(site) else {
            return false;
        };
        let Ok(bil) = serde_json::from_str::<Vec<Stmt>>(&transfer.ast) else {
            return false;
        };
        instruction.kind != InstructionKind::Call
            && !instruction.may_defs.contains("memory:any")
            && !memory_write_bil(&bil)
            && !writes_address_bil(&bil, &keys)
            && !keys.iter().any(|key| clobbered(key, &instruction.may_defs))
    })
}
fn has_repeat(path: &[(u64, bool)]) -> bool {
    let mut seen = BTreeSet::new();
    path.iter().any(|(site, _)| !seen.insert(*site))
}

fn decode_bytes(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0
        || !s
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return None;
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).ok())
        .collect()
}

pub(crate) fn resolve<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    read: F,
) -> Result<Report, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    resolve_inner(
        snapshot,
        artifact,
        instructions,
        roots,
        transfers,
        limits,
        false,
        read,
    )
}
pub(crate) fn resolve_candidate<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    read: F,
) -> Result<Report, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    resolve_inner(
        snapshot,
        artifact,
        instructions,
        roots,
        transfers,
        limits,
        true,
        read,
    )
}
#[derive(Clone, Debug)]
pub(crate) struct QuestionTargetSchedule {
    pub priority: AddressSet,
    pub quantum: usize,
    pub deadline: Option<Instant>,
    pub work: std::cell::Cell<usize>,
    pub service: std::cell::RefCell<Vec<u64>>,
}
#[allow(clippy::too_many_arguments)]
fn resolve_inner<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    local: bool,
    read: F,
) -> Result<Report, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    resolve_scheduled(
        snapshot,
        artifact,
        instructions,
        roots,
        transfers,
        limits,
        local,
        None,
        read,
    )
}
#[allow(clippy::too_many_arguments)]
pub(crate) fn resolve_question<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    schedule: &QuestionTargetSchedule,
    read: F,
) -> Result<Report, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    if schedule.quantum == 0 {
        return Err(invalid("question resolver quantum must be positive"));
    }
    resolve_scheduled(
        snapshot,
        artifact,
        instructions,
        roots,
        transfers,
        limits,
        true,
        Some(schedule),
        read,
    )
}
type ResolutionPrefix = (u64, Term, Vec<Guard>, Vec<(u64, bool)>);
struct ResolutionTask {
    site: u64,
    result: Resolution,
    pending: Vec<ResolutionPrefix>,
    targets: BTreeSet<u64>,
}
#[allow(clippy::too_many_arguments)]
fn resolve_scheduled<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    local: bool,
    schedule: Option<&QuestionTargetSchedule>,
    mut read: F,
) -> Result<Report, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    limits.validate()?;
    let start = Instant::now();
    let mut steps = limits.max_steps;
    let mut reads: BTreeMap<(u64, usize), DataRead> = BTreeMap::new();
    let mut read_bytes = 0usize;
    let mut used = BTreeSet::new();
    let mut predecessors: BTreeMap<u64, Vec<(u64, bool)>> = BTreeMap::new();
    for (&p, i) in instructions {
        for (to, taken) in successors(i) {
            predecessors.entry(to).or_default().push((p, taken));
        }
    }
    let mut results = Vec::new();
    let mut stop = None;
    let mut retained_targets = BTreeSet::new();
    let mut fair = crate::bap::work_schedule::FairQueue::default();
    let mut legacy = std::collections::VecDeque::new();
    for (&site, _) in instructions
        .iter()
        .filter(|(_, i)| i.kind == InstructionKind::Indirect)
    {
        let mut result = Resolution {
            site: hex(site),
            targets: Vec::new(),
            complete: true,
            paths: Vec::new(),
            unresolved: BTreeSet::new(),
            coverage: local.then(|| CoverageEvidence::ExistingPrefixTree {
                path_receipt_refs: Vec::new(),
            }),
        };
        let Some(jump) = transfers.get(&site).and_then(|t| t.jump.clone()) else {
            result.complete = false;
            result
                .unresolved
                .insert("unsupported-jump-expression".into());
            results.push(result);
            continue;
        };
        used.insert(site);
        let task = ResolutionTask {
            site,
            result,
            pending: vec![(site, jump, Vec::new(), Vec::new())],
            targets: BTreeSet::new(),
        };
        if let Some(policy) = schedule {
            fair.push(usize::from(!policy.priority.contains(&site)), task);
        } else {
            legacy.push_back(task);
        }
    }
    while let Some((band, task)) = if schedule.is_some() {
        fair.pop()
    } else {
        legacy.pop_front().map(|t| (0, t))
    } {
        let ResolutionTask {
            site,
            mut result,
            mut pending,
            mut targets,
        } = task;
        if let Some(policy) = schedule {
            if policy.service.borrow().len() < 8192 {
                policy.service.borrow_mut().push(site);
            }
        }
        let mut serviced = 0usize;
        while let Some((cursor, term, guards, path)) = pending.pop() {
            if schedule.is_some_and(|policy| serviced >= policy.quantum) {
                pending.push((cursor, term, guards, path));
                break;
            }
            serviced += 1;
            if steps == 0
                || limits.max_values == 0
                || limits.max_rounds == 0
                || start.elapsed().as_millis() >= u128::from(limits.max_elapsed_ms)
                || schedule.is_some_and(|p| p.deadline.is_some_and(|d| Instant::now() >= d))
                || path.len() >= limits.max_path_steps
            {
                result.unresolved.insert("resolution-work-limit".into());
                result.complete = false;
                continue;
            }
            steps -= 1;
            if local
                && !roots.contains(&cursor)
                && guards_infeasible(&guards, limits)
                && (!has_repeat(&path)
                    || stable_cycle(&path, instructions, transfers, &term, &guards))
            {
                result.paths.push(PathReceipt {
                    root: hex(cursor),
                    frontier: true,
                    reverse_path: path.iter().map(|(v, _)| hex(*v)).collect(),
                    reverse_edges: path.iter().map(|(_, v)| *v).collect(),
                    form: "infeasible".into(),
                    base: hex(0),
                    indices: Vec::new(),
                    entries: Vec::new(),
                    expression: term,
                    guards,
                });
                continue;
            }
            let frontier =
                local && !roots.contains(&cursor) && bounded_form(&term, &guards, limits);
            if roots.contains(&cursor) || frontier {
                let mut certificate = PathReceipt {
                    root: hex(cursor),
                    frontier,
                    reverse_path: path.iter().map(|(v, _)| hex(*v)).collect(),
                    reverse_edges: path.iter().map(|(_, v)| *v).collect(),
                    form: String::new(),
                    base: hex(0),
                    indices: Vec::new(),
                    entries: Vec::new(),
                    expression: term.clone(),
                    guards: guards.clone(),
                };
                let form = if let Some((base, index)) = relative(&term) {
                    Some(("relative32", base, Some(index), 4))
                } else if let TermKind::Load { address, .. } = &term.kind {
                    address
                        .number()
                        .filter(|_| term.width == 64)
                        .map(|a| ("pointer64", a, None, 8))
                } else {
                    None
                };
                if let Some((form, base, index, width)) = form {
                    certificate.form = form.into();
                    certificate.base = hex(base);
                    let indices = if let Some(index) = &index {
                        let domain = guards.iter().fold((0, mask(index.width)), |a, g| {
                            let b = range(&g.expression, g.taken, index);
                            (a.0.max(b.0), a.1.min(b.1))
                        });
                        let values = values(index, limits.max_values, 0).or_else(|| {
                            domain.1.checked_sub(domain.0).and_then(|n| {
                                (n < limits.max_entries as u64)
                                    .then(|| (domain.0..=domain.1).collect())
                            })
                        });
                        values.map(|s| {
                            s.into_iter()
                                .filter(|v| {
                                    *v >= domain.0
                                        && *v <= domain.1
                                        && guards.iter().all(|g| {
                                            evaluate(&g.expression, index, *v, 0)
                                                .is_none_or(|n| (n != 0) == g.taken)
                                        })
                                })
                                .collect::<Vec<_>>()
                        })
                    } else {
                        Some(vec![0])
                    };
                    if let Some(indices) = indices.filter(|v| v.len() <= limits.max_entries) {
                        certificate.indices = indices.clone();
                        for index in indices {
                            let slot = if form == "relative32" {
                                base.wrapping_add(index.wrapping_mul(4))
                            } else {
                                base
                            };
                            let record = if let Some(r) = reads.get(&(slot, width)) {
                                r.clone()
                            } else {
                                if read_bytes
                                    .checked_add(width)
                                    .is_none_or(|n| n > limits.max_read_bytes)
                                {
                                    result.complete = false;
                                    result
                                        .unresolved
                                        .insert("resolution-read-target-limit".into());
                                    break;
                                }
                                let r = read(slot, width)?;
                                validate_data_read(&r)?;
                                if r.address != hex(slot) || r.requested != width {
                                    return Err(invalid("resolver captured read identity"));
                                }
                                read_bytes += width;
                                reads.insert((slot, width), r.clone());
                                r
                            };
                            let Some(bytes) =
                                decode_bytes(&record.bytes_hex).filter(|b| b.len() == width)
                            else {
                                result.complete = false;
                                result.unresolved.insert("unavailable-control-data".into());
                                continue;
                            };
                            if record.spans.is_empty() {
                                return Err(invalid("control-data contributors absent"));
                            }
                            let target = if width == 4 {
                                base.wrapping_add(i32::from_le_bytes(
                                    bytes.as_slice().try_into().unwrap(),
                                ) as i64 as u64)
                            } else {
                                u64::from_le_bytes(bytes.as_slice().try_into().unwrap())
                            };
                            if !retained_targets.contains(&target)
                                && retained_targets.len() >= limits.max_targets
                            {
                                result.complete = false;
                                result
                                    .unresolved
                                    .insert("resolution-read-target-limit".into());
                                continue;
                            }
                            targets.insert(target);
                            retained_targets.insert(target);
                            certificate.entries.push(Entry {
                                index,
                                slot: hex(slot),
                                bytes_hex: record.bytes_hex,
                                target: hex(target),
                            });
                        }
                        result.paths.push(certificate);
                    } else {
                        result.complete = false;
                        result.unresolved.insert("unbounded-control-index".into());
                    }
                } else {
                    result.complete = false;
                    result
                        .unresolved
                        .insert("unsupported-or-unknown-target".into());
                }
                if frontier {
                    // This witness quantifies over arbitrary incoming registers
                    // at the cut. Its local branch constraints already bound
                    // the table; older definitions cannot narrow the claim.
                    continue;
                }
            }
            let incoming = predecessors.get(&cursor).cloned().unwrap_or_default();
            if incoming.is_empty() && !roots.contains(&cursor) {
                result.complete = false;
                result.unresolved.insert("unanchored-incoming-state".into());
            }
            for (parent, taken) in incoming {
                let mut path = path.clone();
                path.push((parent, taken));
                if parent == site
                    || (has_repeat(&path)
                        && (!local
                            || !stable_cycle(&path, instructions, transfers, &term, &guards)))
                {
                    result.complete = false;
                    result.unresolved.insert("cyclic-incoming-state".into());
                    continue;
                }
                let instruction = &instructions[&parent];
                let transfer = transfers.get(&parent);
                if transfer.is_some() {
                    used.insert(parent);
                }
                let outputs = transfer.map(|v| &v.outputs).cloned().unwrap_or_default();
                let Some(next) = term.rewrite(&outputs, &instruction.may_defs, &mut steps) else {
                    result.complete = false;
                    result.unresolved.insert("expression-work-limit".into());
                    continue;
                };
                let rewritten: Option<Vec<_>> = guards
                    .iter()
                    .map(|g| {
                        g.expression
                            .rewrite(&outputs, &instruction.may_defs, &mut steps)
                            .map(|expression| Guard {
                                expression,
                                taken: g.taken,
                            })
                    })
                    .collect();
                if let Some(mut guards) = rewritten {
                    // extract() has already expanded this instruction's
                    // condition into its pre-state. Only downstream guards
                    // cross the write; applying outputs here again would
                    // decrement a LOOP-style counter twice.
                    if instruction.kind == InstructionKind::Conditional
                        && let Some(condition) = transfer.and_then(|v| v.condition.clone())
                    {
                        guards.push(Guard {
                            expression: condition,
                            taken,
                        });
                    }
                    if pending.len() >= limits.max_values {
                        result.complete = false;
                        result.unresolved.insert("resolution-frontier-limit".into());
                        continue;
                    }
                    pending.push((parent, next, guards, path));
                } else {
                    result.complete = false;
                    result.unresolved.insert("guard-work-limit".into());
                }
            }
        }
        if !pending.is_empty() {
            fair.push(
                band,
                ResolutionTask {
                    site,
                    result,
                    pending,
                    targets,
                },
            );
            continue;
        }
        if result.paths.is_empty() {
            result.complete = false;
        }
        result.targets = targets.into_iter().map(hex).collect();
        if local {
            result.coverage = Some(CoverageEvidence::ExistingPrefixTree {
                path_receipt_refs: (0..result.paths.len()).collect(),
            });
            if result.unresolved.contains("cyclic-incoming-state") {
                match loop_closure::propose(
                    snapshot,
                    artifact,
                    instructions,
                    roots,
                    transfers,
                    limits,
                    &mut steps,
                    &start,
                    &mut read,
                    &mut reads,
                    &mut read_bytes,
                    site,
                    &result,
                )? {
                    loop_closure::Attempt::Candidate(receipt) => {
                        for source in &receipt.source_refs {
                            used.insert(address(&source.site)?);
                        }
                        result.coverage = Some(CoverageEvidence::InductiveDispatch { receipt });
                        result.unresolved.clear();
                        result.complete = true;
                    }
                    loop_closure::Attempt::Partial(reason) => {
                        result.unresolved.insert(reason);
                    }
                    loop_closure::Attempt::NotApplicable => {}
                }
            }
        }
        if !result.unresolved.is_empty() {
            result.complete = false;
        }
        results.push(result);
    }
    if let Some(policy) = schedule {
        policy.work.set(limits.max_steps.saturating_sub(steps));
        results.sort_by_key(|r| r.site.clone());
    }
    let mut report = Report {
        schema: if local {
            "ariadne.indirect-target-resolution/v3"
        } else {
            "ariadne.indirect-target-resolution/v1"
        }
        .into(),
        profile: if local { LOCAL_PROFILE } else { PROFILE }.into(),
        memory_premise: MEMORY_PREMISE.into(),
        snapshot: snapshot.into(),
        artifact_sha256: artifact.into(),
        graph_sha256: if local {
            graph_digest(instructions, roots)?
        } else {
            legacy_graph_digest(instructions, roots)?
        },
        limits: limits.clone(),
        resolutions: results,
        data_reads: reads.into_values().collect(),
        transfers: used
            .into_iter()
            .filter_map(|a| transfers.get(&a).cloned())
            .collect(),
        stop: stop.take(),
    };
    if !within_evidence_budget(&report)? {
        report.resolutions.clear();
        report.data_reads.clear();
        report.transfers.clear();
        report.stop = Some("resolution-evidence-limit".into());
    }
    if std::env::var_os("ARIADNE_TARGET_DIAGNOSTICS").is_some() {
        eprintln!(
            "resolver pass_elapsed_us={} instructions={} reads={} stop={:?}",
            start.elapsed().as_micros(),
            instructions.len(),
            report.data_reads.len(),
            report.stop
        );
    }
    Ok(report)
}

/// Leave room to retain the same witnesses after discovery invalidates coverage.
/// The reserved form has no new rows or per-row diagnostics; one global reason
/// explains the stop. Actual admission still checks the serialized report size.
pub(crate) fn within_evidence_budget(report: &Report) -> Result<bool, Error> {
    let actual = serde_json::to_vec(report)?.len();
    // In compact JSON, `false` needs one extra byte per replaced `true`.
    // Account for just the changed fields instead of cloning the BIL/read data.
    let downgrade = actual - serde_json::to_vec(&report.stop)?.len()
        + serde_json::to_vec(&Some("resolution-retention-limit"))?.len()
        + report.resolutions.iter().filter(|row| row.complete).count();
    Ok(actual.max(downgrade) <= report.limits.max_evidence_bytes)
}

#[derive(Default)]
struct CoveragePrefix {
    children: BTreeMap<(u64, bool), usize>,
    terminal: bool,
    frontier: bool,
}

/// Validate the captured-read wire contract without reopening its artifact.
/// A full prefix cannot hide a conflict or a hole behind nonempty metadata.
pub(crate) fn validate_data_read(read: &DataRead) -> Result<(), Error> {
    let start = address(&read.address)?;
    let bytes = decode_bytes(&read.bytes_hex)
        .ok_or_else(|| invalid("resolver captured read byte encoding"))?;
    if !matches!(read.requested, 4 | 8) || bytes.len() > read.requested {
        return Err(invalid("resolver captured read width or prefix length"));
    }
    if bytes.len() != read.requested {
        // An explicit partial prefix cannot support a table entry. Preserve
        // its holes/conflicts rather than claiming complete captured bytes.
        return Ok(());
    }
    if read.stop != "RequestedLength" || !read.conflict_sources.is_empty() {
        return Err(invalid("resolver ambiguous full captured read"));
    }
    let mut covered = 0usize;
    for span in &read.spans {
        let low = address(&span.address)?;
        if span.length == 0 || span.contributors.is_empty() {
            return Err(invalid("resolver captured read contributor coverage"));
        }
        let current = start
            .checked_add(covered as u64)
            .ok_or_else(|| invalid("resolver captured read address overflow"))?;
        if low > current {
            return Err(invalid("resolver captured read span hole"));
        }
        let delta = current - low;
        let length = u64::try_from(span.length)
            .map_err(|_| invalid("resolver captured span representation"))?;
        if delta < length {
            covered += usize::try_from((length - delta).min((read.requested - covered) as u64))
                .map_err(|_| invalid("resolver captured span representation"))?;
        }
    }
    if covered != read.requested {
        return Err(invalid("resolver incomplete captured read coverage"));
    }
    Ok(())
}

pub(crate) fn validate(
    report: &Report,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
) -> Result<(), Error> {
    let new_local = (report.schema == "ariadne.indirect-target-resolution/v3"
        && report.profile == LOCAL_PROFILE)
        || (is_advanced(report) && report.profile == ADVANCED_LOCAL_PROFILE);
    let legacy_local = report.schema == "ariadne.indirect-target-resolution/v2"
        && report.profile == LEGACY_LOCAL_PROFILE;
    let local = new_local || legacy_local;
    if !(local
        || (is_advanced(report) && report.profile == ADVANCED_PROFILE)
        || (report.schema == "ariadne.indirect-target-resolution/v1" && report.profile == PROFILE))
        || report.memory_premise != MEMORY_PREMISE
        || report.graph_sha256 != report_graph_digest(report, instructions, roots)?
    {
        return Err(invalid("resolver profile or graph binding"));
    }
    report.limits.validate()?;
    if report.stop.as_deref() == Some("resolution-evidence-limit")
        && report.resolutions.is_empty()
        && report.data_reads.is_empty()
        && report.transfers.is_empty()
    {
        return Ok(());
    }
    if serde_json::to_vec(report)?.len() > report.limits.max_evidence_bytes {
        return Err(invalid("resolver evidence byte limit"));
    }
    let no_work = report.limits.max_steps == 0
        || report.limits.max_elapsed_ms == 0
        || report.limits.max_rounds == 0
        || report.limits.max_values == 0;
    if no_work
        && (!report.data_reads.is_empty()
            || report
                .resolutions
                .iter()
                .any(|row| !row.paths.is_empty() || !row.targets.is_empty() || row.complete))
    {
        return Err(invalid("resolver zero work budget"));
    }
    let mut transfers = BTreeMap::new();
    for t in &report.transfers {
        if crate::reports::sha256(t.ast.as_bytes()) != t.ast_sha256 {
            return Err(invalid("resolver AST digest"));
        }
        let bil: Vec<Stmt> =
            serde_json::from_value(crate::reports::strict_json(t.ast.as_bytes())?)?;
        let site = address(&t.site)?;
        let bytes =
            decode_bytes(&t.bytes_hex).ok_or_else(|| invalid("resolver instruction bytes"))?;
        if extract(&bil, site, &bytes)? != *t || transfers.insert(site, t.clone()).is_some() {
            return Err(invalid("resolver transfer mismatch or duplicate"));
        }
    }
    let mut reads = BTreeMap::new();
    let mut read_bytes = 0usize;
    for r in &report.data_reads {
        validate_data_read(r)?;
        let key = (address(&r.address)?, r.requested);
        if reads.insert(key, r.clone()).is_some() {
            return Err(invalid("duplicate resolver read"));
        }
        read_bytes = read_bytes
            .checked_add(r.requested)
            .filter(|n| *n <= report.limits.max_read_bytes)
            .ok_or_else(|| invalid("resolver read byte limit"))?;
    }
    let mut predecessors: BTreeMap<u64, BTreeSet<(u64, bool)>> = BTreeMap::new();
    for (&parent, instruction) in instructions {
        for (to, taken) in successors(instruction) {
            predecessors.entry(to).or_default().insert((parent, taken));
        }
    }
    let mut seen = BTreeSet::new();
    let mut all_targets = BTreeSet::new();
    for row in &report.resolutions {
        let site = address(&row.site)?;
        if !seen.insert(site)
            || instructions
                .get(&site)
                .is_none_or(|i| i.kind != InstructionKind::Indirect)
        {
            return Err(invalid("resolver site domain"));
        }
        if new_local != row.coverage.is_some() {
            return Err(invalid("resolver coverage version"));
        }
        let inductive = matches!(
            row.coverage,
            Some(CoverageEvidence::InductiveDispatch { .. })
        );
        if let Some(CoverageEvidence::ExistingPrefixTree { path_receipt_refs }) = &row.coverage {
            if *path_receipt_refs != (0..row.paths.len()).collect::<Vec<_>>() {
                return Err(invalid("resolver prefix receipt references"));
            }
        }
        if let Some(CoverageEvidence::InductiveDispatch { receipt }) = &row.coverage {
            loop_closure::validate(
                receipt,
                report,
                instructions,
                roots,
                &transfers,
                &reads,
                row,
            )?;
        }
        if row.complete
            && (!row.unresolved.is_empty() || report.stop.is_some() || row.paths.is_empty())
        {
            return Err(invalid("resolver incomplete certificate"));
        }
        let mut targets = BTreeSet::new();
        // A prefix identifies a whole reverse path context, not just its current
        // instruction. Merging contexts at a join would lose path combinations.
        let mut prefixes = vec![CoveragePrefix::default()];
        let mut prefix_sites = vec![site];
        for path in &row.paths {
            if path.reverse_path.len() != path.reverse_edges.len() {
                return Err(invalid("resolver edge word length"));
            }
            if path.reverse_path.len() >= report.limits.max_path_steps
                || path.reverse_path.len() >= report.limits.max_steps
                || path.indices.len() > report.limits.max_entries
                || path.entries.len() > report.limits.max_entries
            {
                return Err(invalid("resolver path or entry limit"));
            }
            let mut term = transfers
                .get(&site)
                .and_then(|t| t.jump.clone())
                .ok_or_else(|| invalid("resolver jump evidence missing"))?;
            let mut guards: Vec<Guard> = Vec::new();
            let mut cursor = site;
            let mut path_seen = BTreeSet::new();
            let mut work = report.limits.max_steps;
            let mut prefix = 0;
            for (parent, taken) in path.reverse_path.iter().zip(&path.reverse_edges) {
                let parent = address(parent)?;
                if parent == site
                    || !(path_seen.insert(parent)
                        || (local && path.form == "infeasible" && path.frontier))
                {
                    return Err(invalid("resolver path cycle"));
                }
                let instruction = instructions
                    .get(&parent)
                    .ok_or_else(|| invalid("resolver predecessor absent"))?;
                if !successors(instruction).contains(&(cursor, *taken)) {
                    return Err(invalid("resolver path edge absent"));
                }
                let edge = (parent, *taken);
                prefix = if let Some(&child) = prefixes[prefix].children.get(&edge) {
                    child
                } else {
                    let child = prefixes.len();
                    prefixes[prefix].children.insert(edge, child);
                    prefixes.push(CoveragePrefix::default());
                    prefix_sites.push(parent);
                    child
                };
                let transfer = transfers.get(&parent);
                let outputs = transfer.map(|t| t.outputs.clone()).unwrap_or_default();
                term = term
                    .rewrite(&outputs, &instruction.may_defs, &mut work)
                    .ok_or_else(|| invalid("resolver proof work limit"))?;
                guards = guards
                    .into_iter()
                    .map(|g| {
                        g.expression
                            .rewrite(&outputs, &instruction.may_defs, &mut work)
                            .map(|expression| Guard {
                                expression,
                                taken: g.taken,
                            })
                            .ok_or_else(|| invalid("resolver guard proof limit"))
                    })
                    .collect::<Result<_, _>>()?;
                // The current branch predicate is already a pre-state term;
                // replay only the downstream guards through its outputs.
                if instruction.kind == InstructionKind::Conditional
                    && let Some(condition) = transfer.and_then(|t| t.condition.clone())
                {
                    guards.push(Guard {
                        expression: condition,
                        taken: *taken,
                    });
                }
                cursor = parent;
            }
            if cursor != address(&path.root)?
                || (if path.frontier {
                    !local
                        || roots.contains(&cursor)
                        || !(if path.form == "infeasible" {
                            guards_infeasible(&guards, &report.limits)
                        } else {
                            bounded_form(&term, &guards, &report.limits)
                        })
                } else {
                    !roots.contains(&cursor)
                })
                || term != path.expression
                || guards != path.guards
            {
                return Err(invalid("resolver path/semantic proof"));
            }
            if prefixes[prefix].terminal {
                return Err(invalid("duplicate resolver path"));
            }
            prefixes[prefix].terminal = true;
            prefixes[prefix].frontier = path.frontier;
            if path.form == "infeasible" {
                let word = path
                    .reverse_path
                    .iter()
                    .zip(&path.reverse_edges)
                    .map(|(a, taken)| Ok((address(a)?, *taken)))
                    .collect::<Result<Vec<_>, Error>>()?;
                if !local
                    || !path.frontier
                    || path.base != hex(0)
                    || !path.indices.is_empty()
                    || !path.entries.is_empty()
                    || !guards_infeasible(&guards, &report.limits)
                    || (has_repeat(&word)
                        && !stable_cycle(&word, instructions, &transfers, &term, &guards))
                {
                    return Err(invalid("resolver infeasible context proof"));
                }
                continue;
            }
            let (form, base, index, width) = if let Some((base, index)) = relative(&term) {
                ("relative32", base, Some(index), 4)
            } else if let TermKind::Load { address, .. } = &term.kind {
                (
                    "pointer64",
                    address
                        .number()
                        .filter(|_| term.width == 64)
                        .ok_or_else(|| invalid("resolver pointer expression"))?,
                    None,
                    8,
                )
            } else {
                return Err(invalid("resolver unsupported proof expression"));
            };
            if path.form != form || path.base != hex(base) {
                return Err(invalid("resolver table form/base"));
            }
            let expected = if let Some(index) = index {
                let domain = guards.iter().fold((0, mask(index.width)), |a, g| {
                    let b = range(&g.expression, g.taken, &index);
                    (a.0.max(b.0), a.1.min(b.1))
                });
                let values = values(&index, report.limits.max_values, 0)
                    .or_else(|| {
                        domain.1.checked_sub(domain.0).and_then(|n| {
                            (n < report.limits.max_entries as u64)
                                .then(|| (domain.0..=domain.1).collect())
                        })
                    })
                    .ok_or_else(|| invalid("resolver unbounded proof index"))?;
                values
                    .into_iter()
                    .filter(|v| {
                        *v >= domain.0
                            && *v <= domain.1
                            && guards.iter().all(|g| {
                                evaluate(&g.expression, &index, *v, 0)
                                    .is_none_or(|n| (n != 0) == g.taken)
                            })
                    })
                    .collect::<Vec<_>>()
            } else {
                vec![0]
            };
            if path.indices != expected {
                return Err(invalid("resolver index coverage"));
            }
            let mut entries = BTreeSet::new();
            for e in &path.entries {
                let slot = if form == "relative32" {
                    base.wrapping_add(e.index.wrapping_mul(4))
                } else {
                    base
                };
                if !entries.insert(e.index)
                    || !path.indices.contains(&e.index)
                    || e.slot != hex(slot)
                {
                    return Err(invalid("resolver entry index/slot"));
                }
                let read = reads
                    .get(&(slot, width))
                    .ok_or_else(|| invalid("resolver read absent"))?;
                if read.bytes_hex != e.bytes_hex || read.spans.is_empty() {
                    return Err(invalid("resolver entry/read binding"));
                }
                let bytes = decode_bytes(&e.bytes_hex)
                    .filter(|b| b.len() == width)
                    .ok_or_else(|| invalid("resolver entry bytes"))?;
                let target = if width == 4 {
                    base.wrapping_add(i32::from_le_bytes(bytes.try_into().unwrap()) as i64 as u64)
                } else {
                    u64::from_le_bytes(bytes.try_into().unwrap())
                };
                if e.target != hex(target) {
                    return Err(invalid("resolver target arithmetic"));
                }
                targets.insert(e.target.clone());
                all_targets.insert(e.target.clone());
                if all_targets.len() > report.limits.max_targets {
                    return Err(invalid("resolver distinct target limit"));
                }
            }
            if row.complete && entries != path.indices.iter().copied().collect() {
                return Err(invalid("resolver incomplete table coverage"));
            }
        }
        if row.targets != targets.into_iter().collect::<Vec<_>>() {
            return Err(invalid("resolver target witness set"));
        }
        if row.complete && !inductive {
            // Replay the producer's ascending predecessor pushes and LIFO pops.
            // A per-node fanout bound misses siblings already on the frontier.
            let mut pending = vec![0];
            while let Some(index) = pending.pop() {
                let prefix = &prefixes[index];
                let cursor = prefix_sites[index];
                let incoming = predecessors.get(&cursor).cloned().unwrap_or_default();
                let cut = local && prefix.frontier;
                if (cut && !prefix.children.is_empty())
                    || (!cut
                        && (prefix.children.keys().copied().collect::<BTreeSet<_>>() != incoming
                            || prefix.terminal != roots.contains(&cursor)))
                {
                    return Err(invalid("resolver uncovered incoming path"));
                }
                for &child in prefix.children.values() {
                    if pending.len() >= report.limits.max_values {
                        return Err(invalid("resolver frontier value limit"));
                    }
                    pending.push(child);
                }
            }
        }
    }

    Ok(())
}

#[cfg(test)]
#[path = "../../tests/bap/loop_closure_unit.rs"]
mod loop_tests;
#[cfg(test)]
#[path = "../../tests/bap/repeated_string_consumers.rs"]
mod repeated_string_consumers;
#[cfg(test)]
#[path = "../../tests/bap/target_resolution_unit.rs"]
mod tests;

mod unsigned_vec {
    use serde::{Deserialize, Serialize};
    pub fn serialize<S: serde::Serializer>(values: &[u64], s: S) -> Result<S::Ok, S::Error> {
        values
            .iter()
            .map(|v| super::hex(*v))
            .collect::<Vec<_>>()
            .serialize(s)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<u64>, D::Error> {
        Vec::<String>::deserialize(d)?
            .iter()
            .map(|v| super::address(v).map_err(serde::de::Error::custom))
            .collect()
    }
}

#[path = "target_resolution/question_semantics.rs"]
pub(crate) mod question_semantics;
