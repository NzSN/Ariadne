//! Bounded snapshot-relative near-jump resolution over admitted BIL.
//! Candidate destinations do not identify an executed branch or stable history.
use super::ast::{Expr, Stmt};
use super::{Error, invalid};
use crate::{Address, AddressSet, Instruction, InstructionKind, LocationSet};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

pub const PROFILE: &str = "captured-indirect-targets/v1";
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
    /// The first qualified profile permits tightening, not unbounded increases.
    pub fn validate(&self) -> Result<(), Error> {
        let d = Self::default();
        if self.max_entries > d.max_entries
            || self.max_targets > d.max_targets
            || self.max_read_bytes > d.max_read_bytes
            || self.max_evidence_bytes > d.max_evidence_bytes
            || self.max_values > d.max_values
            || self.max_steps > d.max_steps
            || self.max_path_steps > d.max_path_steps
            || self.max_rounds > d.max_rounds
            || self.max_elapsed_ms > d.max_elapsed_ms
        {
            return Err(invalid("target-resolution profile limit exceeded"));
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
        Expr::Load { width, addr, .. } if matches!(width, 32 | 64) => Term {
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
pub(crate) fn graph_digest(
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
            if left.as_ref() == index && right.number().is_some() =>
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
            if right.as_ref() == index && left.number().is_some() =>
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
        let mut pending = vec![(site, jump, Vec::<Guard>::new(), Vec::<(u64, bool)>::new())];
        let mut targets = BTreeSet::new();
        while let Some((cursor, term, guards, path)) = pending.pop() {
            if steps == 0
                || limits.max_values == 0
                || limits.max_rounds == 0
                || start.elapsed().as_millis() >= u128::from(limits.max_elapsed_ms)
                || path.len() >= limits.max_path_steps
            {
                result.unresolved.insert("resolution-work-limit".into());
                result.complete = false;
                continue;
            }
            steps -= 1;
            if roots.contains(&cursor) {
                let mut certificate = PathReceipt {
                    root: hex(cursor),
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
            }
            let incoming = predecessors.get(&cursor).cloned().unwrap_or_default();
            if incoming.is_empty() && !roots.contains(&cursor) {
                result.complete = false;
                result.unresolved.insert("unanchored-incoming-state".into());
            }
            for (parent, taken) in incoming {
                if path.iter().any(|(v, _)| *v == parent) || parent == site {
                    result.complete = false;
                    result.unresolved.insert("cyclic-incoming-state".into());
                    continue;
                }
                let mut path = path.clone();
                path.push((parent, taken));
                let instruction = &instructions[&parent];
                let transfer = transfers.get(&parent);
                if transfer.is_some() {
                    used.insert(parent);
                }
                let outputs = transfer.map(|v| &v.outputs).cloned().unwrap_or_default();
                let mut guards = guards.clone();
                if instruction.kind == InstructionKind::Conditional {
                    if let Some(condition) = transfer.and_then(|v| v.condition.clone()) {
                        guards.push(Guard {
                            expression: condition,
                            taken,
                        });
                    }
                }
                let Some(next) = term.rewrite(&outputs, &instruction.may_defs, &mut steps) else {
                    result.complete = false;
                    result.unresolved.insert("expression-work-limit".into());
                    continue;
                };
                let rewritten: Option<Vec<_>> = guards
                    .into_iter()
                    .map(|g| {
                        g.expression
                            .rewrite(&outputs, &instruction.may_defs, &mut steps)
                            .map(|expression| Guard {
                                expression,
                                taken: g.taken,
                            })
                    })
                    .collect();
                if let Some(guards) = rewritten {
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
        if result.paths.is_empty() {
            result.complete = false;
        }
        result.targets = targets.into_iter().map(hex).collect();
        if !result.unresolved.is_empty() {
            result.complete = false;
        }
        results.push(result);
    }
    let mut report = Report {
        schema: "ariadne.indirect-target-resolution/v1".into(),
        profile: PROFILE.into(),
        memory_premise: MEMORY_PREMISE.into(),
        snapshot: snapshot.into(),
        artifact_sha256: artifact.into(),
        graph_sha256: graph_digest(instructions, roots)?,
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
}

pub(crate) fn validate(
    report: &Report,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
) -> Result<(), Error> {
    if report.schema != "ariadne.indirect-target-resolution/v1"
        || report.profile != PROFILE
        || report.memory_premise != MEMORY_PREMISE
        || report.graph_sha256 != graph_digest(instructions, roots)?
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
            let mut guards = Vec::new();
            let mut cursor = site;
            let mut path_seen = BTreeSet::new();
            let mut work = report.limits.max_steps;
            let mut prefix = 0;
            for (parent, taken) in path.reverse_path.iter().zip(&path.reverse_edges) {
                let parent = address(parent)?;
                if !path_seen.insert(parent) || parent == site {
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
                if instruction.kind == InstructionKind::Conditional
                    && let Some(condition) = transfer.and_then(|t| t.condition.clone())
                {
                    guards.push(Guard {
                        expression: condition,
                        taken: *taken,
                    });
                }
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
                cursor = parent;
            }
            if cursor != address(&path.root)?
                || !roots.contains(&cursor)
                || term != path.expression
                || guards != path.guards
            {
                return Err(invalid("resolver path/semantic proof"));
            }
            if prefixes[prefix].terminal {
                return Err(invalid("duplicate resolver path"));
            }
            prefixes[prefix].terminal = true;
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
        if row.complete {
            // Replay the producer's ascending predecessor pushes and LIFO pops.
            // A per-node fanout bound misses siblings already on the frontier.
            let mut pending = vec![0];
            while let Some(index) = pending.pop() {
                let prefix = &prefixes[index];
                let cursor = prefix_sites[index];
                let incoming = predecessors.get(&cursor).cloned().unwrap_or_default();
                if prefix.children.keys().copied().collect::<BTreeSet<_>>() != incoming
                    || prefix.terminal != roots.contains(&cursor)
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
