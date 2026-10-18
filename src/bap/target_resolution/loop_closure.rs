//! Local phase induction. Proposal discovers assertions; replay checks each edge
//! inclusion independently and never uses a convergence flag as proof.
#![allow(clippy::too_many_arguments)]
use super::*;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum CoverageEvidence {
    ExistingPrefixTree { path_receipt_refs: Vec<usize> },
    InductiveDispatch { receipt: Box<LoopClosureReceipt> },
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoopEdge {
    pub from: String,
    pub to: String,
    pub taken: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoopCorridor {
    pub entrance: LoopEdge,
    pub sites: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WordDomain {
    pub width: u8,
    pub kind: WordDomainKind,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum WordDomainKind {
    Top,
    Constant { value: String },
    UnsignedInterval { lower: String, upper: String },
    FiniteSet { values: Vec<String> },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PointAssertion {
    pub site: String,
    pub domains: BTreeMap<String, WordDomain>,
    pub(crate) flags: BTreeMap<String, Term>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoopTable {
    pub load_site: String,
    pub base_bank: String,
    pub selector_bank: String,
    pub base: String,
    #[serde(with = "super::unsigned_vec")]
    pub indices: Vec<u64>,
    pub entries: Vec<Entry>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoopSourceRef {
    pub site: String,
    pub bytes_hex: String,
    pub ast_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoopClosureReceipt {
    pub schema: String,
    pub rule: String,
    pub snapshot: String,
    pub artifact_sha256: String,
    pub graph_sha256: String,
    pub model_sha256: String,
    pub engine_sha256: String,
    pub dispatch: String,
    pub region: Vec<String>,
    pub internal_edges: Vec<LoopEdge>,
    pub entrances: Vec<LoopEdge>,
    pub exits: Vec<LoopEdge>,
    pub corridors: Vec<LoopCorridor>,
    pub assertions: Vec<PointAssertion>,
    pub table: LoopTable,
    pub source_refs: Vec<LoopSourceRef>,
}
fn model_identity() -> String {
    crate::reports::sha256(include_bytes!(
        "../../../Specs/AriadneLoopTargetClosure.tla"
    ))
}
struct Work<'a> {
    left: &'a mut usize,
    start: &'a Instant,
    limits: &'a Limits,
}
impl Work<'_> {
    fn charge(&mut self, n: usize) -> Result<(), Error> {
        if self.limits.max_values == 0
            || self.limits.max_rounds == 0
            || self.start.elapsed().as_millis() >= u128::from(self.limits.max_elapsed_ms)
            || *self.left < n
        {
            return Err(invalid("loop closure work limit"));
        }
        *self.left -= n;
        Ok(())
    }
}
impl WordDomain {
    fn top(width: u8) -> Self {
        Self {
            width,
            kind: WordDomainKind::Top,
        }
    }
    fn constant(value: u64, width: u8) -> Self {
        Self {
            width,
            kind: WordDomainKind::Constant {
                value: hex(value & mask(width)),
            },
        }
    }
    fn interval(low: u64, high: u64, width: u8) -> Self {
        if low == high {
            Self::constant(low, width)
        } else if low == 0 && high == mask(width) {
            Self::top(width)
        } else {
            Self {
                width,
                kind: WordDomainKind::UnsignedInterval {
                    lower: hex(low),
                    upper: hex(high),
                },
            }
        }
    }
    fn bounds(&self) -> Result<(u64, u64), Error> {
        if !(1..=64).contains(&self.width) {
            return Err(invalid("loop domain width"));
        }
        let pair = match &self.kind {
            WordDomainKind::Top => (0, mask(self.width)),
            WordDomainKind::Constant { value } => {
                let n = address(value)?;
                (n, n)
            }
            WordDomainKind::UnsignedInterval { lower, upper } => (address(lower)?, address(upper)?),
            WordDomainKind::FiniteSet { values } => {
                let values = values
                    .iter()
                    .map(|s| address(s))
                    .collect::<Result<Vec<_>, _>>()?;
                if values.is_empty() || values.windows(2).any(|v| v[0] >= v[1]) {
                    return Err(invalid("loop finite domain order"));
                }
                (values[0], values[values.len() - 1])
            }
        };
        if pair.0 > pair.1 || pair.1 > mask(self.width) {
            return Err(invalid("loop domain bounds"));
        }
        Ok(pair)
    }
    fn cost(&self) -> usize {
        if let WordDomainKind::FiniteSet { values } = &self.kind {
            values.len().max(1)
        } else {
            1
        }
    }
    fn values(&self, work: &mut Work<'_>) -> Result<Option<Vec<u64>>, Error> {
        work.charge(self.cost())?;
        let (low, high) = self.bounds()?;
        if let WordDomainKind::FiniteSet { values } = &self.kind {
            if values.len() > work.limits.max_values {
                return Ok(None);
            }
            work.charge(values.len())?;
            return values
                .iter()
                .map(|s| address(s))
                .collect::<Result<Vec<_>, _>>()
                .map(Some);
        }
        if high - low >= work.limits.max_values as u64 {
            return Ok(None);
        }
        let length = usize::try_from(high - low)
            .ok()
            .and_then(|n| n.checked_add(1))
            .ok_or_else(|| invalid("loop value count representation"))?;
        // Reserve proof work before allocating or enumerating a domain.
        work.charge(length)?;
        Ok(Some((low..=high).collect()))
    }
    fn finite(values: BTreeSet<u64>, width: u8) -> Self {
        if values.len() == 1 {
            Self::constant(*values.first().unwrap(), width)
        } else {
            Self {
                width,
                kind: WordDomainKind::FiniteSet {
                    values: values.into_iter().map(hex).collect(),
                },
            }
        }
    }
    fn includes(&self, other: &Self, work: &mut Work<'_>) -> Result<bool, Error> {
        work.charge(self.cost().saturating_add(other.cost()))?;
        if self.width != other.width {
            return Ok(false);
        }
        let (lo, hi) = self.bounds()?;
        let (a, b) = other.bounds()?;
        if a < lo || b > hi {
            return Ok(false);
        }
        if let WordDomainKind::FiniteSet { values } = &self.kind {
            let Some(actual) = other.values(work)? else {
                return Ok(false);
            };
            Ok(actual
                .iter()
                .all(|n| values.binary_search(&hex(*n)).is_ok()))
        } else {
            Ok(true)
        }
    }
    fn join(&self, other: &Self, work: &mut Work<'_>) -> Result<Self, Error> {
        work.charge(self.cost().saturating_add(other.cost()))?;
        if self == other {
            return Ok(self.clone());
        }
        let (a, b) = self.bounds()?;
        let (c, d) = other.bounds()?;
        // Intervals deliberately forget correlations across loop iterations.
        Ok(Self::interval(a.min(c), b.max(d), self.width))
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
struct State {
    domains: BTreeMap<String, WordDomain>,
    flags: BTreeMap<String, Term>,
}
impl State {
    fn empty(table: &LoopTable) -> Self {
        Self {
            domains: [
                (table.base_bank.clone(), WordDomain::top(64)),
                (table.selector_bank.clone(), WordDomain::top(64)),
            ]
            .into(),
            flags: BTreeMap::new(),
        }
    }
    fn assertion(&self, site: u64) -> PointAssertion {
        PointAssertion {
            site: hex(site),
            domains: self.domains.clone(),
            flags: self.flags.clone(),
        }
    }
    fn from_assertion(
        a: &PointAssertion,
        table: &LoopTable,
        work: &mut Work<'_>,
    ) -> Result<Self, Error> {
        if a.domains.keys().cloned().collect::<BTreeSet<_>>()
            != [table.base_bank.clone(), table.selector_bank.clone()].into()
        {
            return Err(invalid("loop assertion bank domain"));
        }
        for d in a.domains.values() {
            work.charge(1)?;
            if let WordDomainKind::FiniteSet { values } = &d.kind {
                if values.len() > work.limits.max_values {
                    return Err(invalid("loop finite assertion value limit"));
                }
                work.charge(values.len())?;
            }
            d.bounds()?;
            if d.width != 64 {
                return Err(invalid("loop bank width"));
            }
        }
        for (key, value) in &a.flags {
            if !matches!(key.as_str(), "CF:0:false" | "ZF:0:false")
                || value.width != 1
                || has_unknown(value)
            {
                return Err(invalid("loop assertion flag"));
            }
            validate_predicate(value, work, 0)?;
        }
        Ok(Self {
            domains: a.domains.clone(),
            flags: a.flags.clone(),
        })
    }
    fn join(&self, other: &Self, work: &mut Work<'_>) -> Result<Self, Error> {
        let mut out = self.clone();
        for (k, v) in &other.domains {
            out.domains
                .insert(k.clone(), self.domains[k].join(v, work)?);
        }
        out.flags.retain(|k, v| other.flags.get(k) == Some(v));
        Ok(out)
    }
    fn included(&self, other: &Self, work: &mut Work<'_>) -> Result<bool, Error> {
        for (k, v) in &self.domains {
            if !other.domains[k].includes(v, work)? {
                return Ok(false);
            }
        }
        Ok(other
            .flags
            .iter()
            .all(|(k, v)| self.flags.get(k) == Some(v)))
    }
}
fn validate_predicate(term: &Term, work: &mut Work<'_>, depth: usize) -> Result<(), Error> {
    work.charge(1)?;
    if depth > 32 || !(1..=64).contains(&term.width) {
        return Err(invalid("loop flag term width or depth"));
    }
    match &term.kind {
        TermKind::Constant { value } => {
            if address(value)? > mask(term.width) {
                return Err(invalid("loop flag constant width"));
            }
        }
        TermKind::Input { key } => {
            if term.width != 64 || !BANKS.iter().any(|b| key == &format!("{b}:0:false")) {
                return Err(invalid("loop flag input"));
            }
        }
        TermKind::Binary { op, left, right } => {
            validate_predicate(left, work, depth + 1)?;
            validate_predicate(right, work, depth + 1)?;
            if !matches!(op,0..=11|16..=18)
                || left.width != right.width
                || term.width != if *op <= 5 { 1 } else { left.width }
            {
                return Err(invalid("loop flag binary type"));
            }
        }
        TermKind::Unary { op, arg } => {
            validate_predicate(arg, work, depth + 1)?;
            if !matches!(op, 0 | 1) || term.width != arg.width {
                return Err(invalid("loop flag unary type"));
            }
        }
        TermKind::Cast { op, arg } => {
            validate_predicate(arg, work, depth + 1)?;
            if !matches!(op, 0..=3)
                || (matches!(op, 0 | 1) && term.width > arg.width)
                || (matches!(op, 2 | 3) && term.width < arg.width)
            {
                return Err(invalid("loop flag cast type"));
            }
        }
        _ => return Err(invalid("loop flag load or unknown")),
    }
    Ok(())
}

fn inputs(t: &Term, out: &mut BTreeSet<String>) {
    match &t.kind {
        TermKind::Input { key } => {
            out.insert(key.clone());
        }
        TermKind::Binary { left, right, .. } => {
            inputs(left, out);
            inputs(right, out);
        }
        TermKind::Unary { arg, .. } | TermKind::Cast { arg, .. } => inputs(arg, out),
        TermKind::Load { address, .. } => inputs(address, out),
        _ => {}
    }
}
fn eval(
    t: &Term,
    state: &State,
    table: &LoopTable,
    reads: &BTreeMap<(u64, usize), DataRead>,
    work: &mut Work<'_>,
    depth: usize,
) -> Result<WordDomain, Error> {
    work.charge(1)?;
    if depth > 32 {
        return Err(invalid("loop expression depth"));
    }
    if let Some(n) = t.number() {
        return Ok(WordDomain::constant(n, t.width));
    }
    let child = |t: &Term, w: &mut Work<'_>| eval(t, state, table, reads, w, depth + 1);
    match &t.kind {
        TermKind::Input { key } => Ok(state
            .domains
            .get(key)
            .cloned()
            .unwrap_or_else(|| WordDomain::top(t.width))),
        TermKind::Unknown => Ok(WordDomain::top(t.width)),
        TermKind::Load { site, address } => {
            if t.width == 8 || t.width == 16 {
                return Ok(WordDomain::interval(0, mask(t.width), t.width));
            }
            if t.width != 32 || site != &table.load_site {
                return Ok(WordDomain::top(t.width));
            }
            let addresses = child(address, work)?
                .values(work)?
                .ok_or_else(|| invalid("loop table address unbounded"))?;
            let mut values = BTreeSet::new();
            for a in addresses {
                work.charge(1)?;
                let r = reads
                    .get(&(a, 4))
                    .ok_or_else(|| invalid("loop table captured read missing"))?;
                let bytes = decode_bytes(&r.bytes_hex)
                    .filter(|b| b.len() == 4)
                    .ok_or_else(|| invalid("loop table captured read incomplete"))?;
                values.insert(u64::from(u32::from_le_bytes(bytes.try_into().unwrap())));
            }
            Ok(WordDomain::finite(values, 32))
        }
        TermKind::Unary { op, arg } | TermKind::Cast { op, arg } => {
            let d = child(arg, work)?;
            if let Some(values) = d.values(work)? {
                let mut out = BTreeSet::new();
                for v in values {
                    work.charge(1)?;
                    let a = Term::constant(v, arg.width);
                    let n = if matches!(t.kind, TermKind::Unary { .. }) {
                        Term::unary(*op, a)
                    } else {
                        Term::cast(*op, t.width, a)
                    };
                    let Some(n) = n.number() else {
                        return Ok(WordDomain::top(t.width));
                    };
                    out.insert(n);
                }
                return Ok(WordDomain::finite(out, t.width));
            }
            if matches!(t.kind, TermKind::Cast { op: 0 | 3, .. }) {
                let (lo, hi) = d.bounds()?;
                if hi <= mask(t.width) {
                    return Ok(WordDomain::interval(lo, hi, t.width));
                }
            }
            Ok(WordDomain::top(t.width))
        }
        TermKind::Binary { op, left, right } => {
            let l = child(left, work)?;
            let r = child(right, work)?;
            if let (Some(l), Some(r)) = (l.values(work)?, r.values(work)?) {
                let n = l
                    .len()
                    .checked_mul(r.len())
                    .ok_or_else(|| invalid("loop value product"))?;
                if n <= work.limits.max_values {
                    let mut out = BTreeSet::new();
                    for a in l {
                        for b in &r {
                            work.charge(1)?;
                            let Some(v) = Term::binary(
                                *op,
                                Term::constant(a, left.width),
                                Term::constant(*b, right.width),
                            )
                            .number() else {
                                return Ok(WordDomain::top(t.width));
                            };
                            out.insert(v);
                        }
                    }
                    return Ok(WordDomain::finite(out, t.width));
                }
            }
            Ok(WordDomain::top(t.width))
        }
        _ => Ok(WordDomain::top(t.width)),
    }
}
fn safe(
    site: u64,
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
) -> Result<(), Error> {
    let i = instructions
        .get(&site)
        .ok_or_else(|| invalid("loop instruction missing"))?;
    let t = transfers
        .get(&site)
        .ok_or_else(|| invalid("loop transfer missing"))?;
    let bil: Vec<Stmt> = serde_json::from_value(crate::reports::strict_json(t.ast.as_bytes())?)?;
    if i.kind == InstructionKind::Call
        || i.may_defs.contains("memory:any")
        || memory_write_bil(&bil)
    {
        return Err(invalid("loop unsafe original effects"));
    }
    let bytes = decode_bytes(&t.bytes_hex).ok_or_else(|| invalid("loop source bytes"))?;
    if !(1..=15).contains(&bytes.len()) {
        return Err(invalid("loop instruction byte width"));
    }
    if extract(&bil, site, &bytes)? != *t {
        return Err(invalid("loop original BIL mismatch"));
    }
    let fall = [site.wrapping_add(bytes.len() as u64)]
        .into_iter()
        .collect::<AddressSet>();
    match i.kind {
        InstructionKind::Ordinary
            if t.jump.is_none()
                && t.condition.is_none()
                && i.fall == fall
                && i.targets.is_empty() => {}
        InstructionKind::Jump
            if t.condition.is_none()
                && t.jump
                    .as_ref()
                    .and_then(Term::number)
                    .is_some_and(|target| i.targets == [target].into())
                && i.fall.is_empty() => {}
        InstructionKind::Conditional
            if t.condition.is_some() && t.jump.is_none() && i.fall == fall =>
        {
            let mut env = BTreeMap::new();
            let mut target = None;
            for statement in &bil {
                match statement {
                    Stmt::Move { var, value } => {
                        env.insert(var.key(), lift_expr(value, &env, site, 0));
                    }
                    Stmt::If { yes, no, .. } if no.is_empty() && yes.len() == 1 => {
                        if let Stmt::Jump { target: expression } = &yes[0] {
                            target = lift_expr(expression, &env, site, 0).number();
                        }
                    }
                    _ => {}
                }
            }
            if target.is_none_or(|target| i.targets != [target].into()) {
                return Err(invalid("loop original conditional control"));
            }
        }
        InstructionKind::Indirect
            if t.jump.as_ref().is_some_and(|v| v.number().is_none())
                && t.condition.is_none()
                && i.fall.is_empty() => {}
        _ => return Err(invalid("loop original control mismatch")),
    }
    Ok(())
}
fn transfer(
    site: u64,
    taken: bool,
    state: &State,
    table: &LoopTable,
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
    reads: &BTreeMap<(u64, usize), DataRead>,
    work: &mut Work<'_>,
) -> Result<Option<State>, Error> {
    work.charge(1)?;
    let source = transfers
        .get(&site)
        .ok_or_else(|| invalid("loop transfer missing"))?;
    work.charge(source.ast.len())?;
    safe(site, instructions, transfers)?;
    let t = &transfers[&site];
    let i = &instructions[&site];
    let mut before = state.clone();
    if i.kind == InstructionKind::Conditional {
        if t.outputs.keys().any(|k| state.domains.contains_key(k)) {
            return Err(invalid("loop branch writes relevant bank"));
        }
        if let Some(condition) = &t.condition {
            let condition = condition
                .rewrite(&state.flags, &LocationSet::new(), work.left)
                .ok_or_else(|| invalid("loop condition work"))?;
            let index = Term::input(table.selector_bank.clone(), 64);
            let (lo, hi) = range(&condition, taken, &index);
            let (a, b) = before.domains[&table.selector_bank].bounds()?;
            if a.max(lo) > b.min(hi) {
                return Ok(None);
            }
            before.domains.insert(
                table.selector_bank.clone(),
                WordDomain::interval(a.max(lo), b.min(hi), 64),
            );
        }
    }
    let mut out = before.clone();
    for key in [&table.base_bank, &table.selector_bank] {
        if let Some(value) = t.outputs.get(key) {
            out.domains
                .insert(key.clone(), eval(value, &before, table, reads, work, 0)?);
        } else if clobbered(key, &i.may_defs) {
            out.domains.insert(key.clone(), WordDomain::top(64));
        }
    }
    let writes: BTreeSet<_> = t
        .outputs
        .keys()
        .filter(|k| !matches!(k.as_str(), "CF:0:false" | "ZF:0:false"))
        .cloned()
        .collect();
    out.flags.retain(|_, value| {
        let mut refs = BTreeSet::new();
        inputs(value, &mut refs);
        refs.is_disjoint(&writes) && !refs.iter().any(|k| clobbered(k, &i.may_defs))
    });
    for flag in ["CF:0:false", "ZF:0:false"] {
        if let Some(value) = t.outputs.get(flag) {
            let mut refs = BTreeSet::new();
            inputs(value, &mut refs);
            let mut check = Work {
                left: work.left,
                start: work.start,
                limits: work.limits,
            };
            if refs.is_disjoint(&writes) && validate_predicate(value, &mut check, 0).is_ok() {
                out.flags.insert(flag.into(), value.clone());
            } else {
                out.flags.remove(flag);
            }
        } else if clobbered(flag, &i.may_defs) {
            out.flags.remove(flag);
        }
    }
    Ok(Some(out))
}
fn edge(from: u64, to: u64, taken: bool) -> LoopEdge {
    LoopEdge {
        from: hex(from),
        to: hex(to),
        taken,
    }
}
type RegionEdges = (Vec<LoopEdge>, Vec<LoopEdge>, Vec<LoopEdge>);

fn inventory(
    region: &BTreeSet<u64>,
    instructions: &BTreeMap<u64, Instruction>,
    work: &mut Work<'_>,
) -> Result<RegionEdges, Error> {
    let (mut internal, mut incoming, mut exits) =
        (BTreeSet::new(), BTreeSet::new(), BTreeSet::new());
    for (&from, i) in instructions {
        work.charge(1)?;
        for (to, taken) in successors(i) {
            work.charge(1)?;
            match (region.contains(&from), region.contains(&to)) {
                (true, true) => {
                    internal.insert(edge(from, to, taken));
                }
                (false, true) => {
                    incoming.insert(edge(from, to, taken));
                }
                (true, false) => {
                    exits.insert(edge(from, to, taken));
                }
                _ => {}
            }
        }
    }
    Ok((
        internal.into_iter().collect(),
        incoming.into_iter().collect(),
        exits.into_iter().collect(),
    ))
}
fn shape(
    site: u64,
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
    work: &mut Work<'_>,
) -> Result<Option<(String, String, String)>, Error> {
    let Some(mut term) = transfers.get(&site).and_then(|t| t.jump.clone()) else {
        return Ok(None);
    };
    let TermKind::Input { key: selector } = &term.kind else {
        return Ok(None);
    };
    let selector = selector.clone();
    let mut cursor = site;
    for _ in 0..work.limits.max_path_steps {
        work.charge(1)?;
        let mut refs = BTreeSet::new();
        inputs(&term, &mut refs);
        for key in refs {
            if key == selector {
                continue;
            }
            let replaced = term
                .rewrite(
                    &[(key.clone(), Term::constant(0, 64))].into(),
                    &LocationSet::new(),
                    work.left,
                )
                .ok_or_else(|| invalid("loop shape work"))?;
            if let Some((0, index)) = relative(&replaced) {
                if index != Term::input(selector.clone(), 64) {
                    continue;
                }
                fn load_site(t: &Term) -> Option<String> {
                    match &t.kind {
                        TermKind::Load { site, .. } if t.width == 32 => Some(site.clone()),
                        TermKind::Binary { left, right, .. } => {
                            load_site(left).or_else(|| load_site(right))
                        }
                        TermKind::Cast { arg, .. } | TermKind::Unary { arg, .. } => load_site(arg),
                        _ => None,
                    }
                }
                if let Some(load) = load_site(&term) {
                    return Ok(Some((key, selector, load)));
                }
            }
        }
        let parents: Vec<_> = instructions
            .iter()
            .filter_map(|(&p, i)| {
                successors(i)
                    .iter()
                    .any(|(to, _)| *to == cursor)
                    .then_some(p)
            })
            .collect();
        work.charge(instructions.len())?;
        if parents.len() != 1 {
            return Ok(None);
        }
        cursor = parents[0];
        let Some(t) = transfers.get(&cursor) else {
            return Ok(None);
        };
        term = term
            .rewrite(&t.outputs, &instructions[&cursor].may_defs, work.left)
            .ok_or_else(|| invalid("loop shape rewrite work"))?;
    }
    Ok(None)
}
fn corridors(
    entrances: &[LoopEdge],
    region: &BTreeSet<u64>,
    base_bank: &str,
    base: u64,
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
    roots: &AddressSet,
    work: &mut Work<'_>,
) -> Result<Vec<LoopCorridor>, Error> {
    let mut out = Vec::new();
    for entrance in entrances {
        let mut site = address(&entrance.from)?;
        let mut reverse = Vec::new();
        let mut seen = BTreeSet::new();
        loop {
            work.charge(1)?;
            if region.contains(&site)
                || !seen.insert(site)
                || reverse.len() >= work.limits.max_path_steps
            {
                return Err(invalid("loop initialization corridor cycle or length"));
            }
            work.charge(
                transfers
                    .get(&site)
                    .ok_or_else(|| invalid("loop transfer missing"))?
                    .ast
                    .len(),
            )?;
            safe(site, instructions, transfers)?;
            if !matches!(
                instructions[&site].kind,
                InstructionKind::Ordinary | InstructionKind::Jump | InstructionKind::Conditional
            ) {
                return Err(invalid("loop unsupported corridor control"));
            }
            reverse.push(site);
            if transfers[&site]
                .outputs
                .get(base_bank)
                .and_then(Term::number)
                == Some(base)
            {
                break;
            }
            if roots.contains(&site) {
                return Err(invalid("loop root bypasses base reset"));
            }
            let parents: Vec<_> = instructions
                .iter()
                .flat_map(|(&p, i)| {
                    successors(i)
                        .into_iter()
                        .filter(move |(to, _)| *to == site)
                        .map(move |_| p)
                })
                .collect();
            work.charge(instructions.len())?;
            if parents.len() != 1 {
                return Err(invalid("loop unproved initialization entrance"));
            }
            site = parents[0];
        }
        reverse.reverse();
        out.push(LoopCorridor {
            entrance: entrance.clone(),
            sites: reverse.into_iter().map(hex).collect(),
        });
    }
    Ok(out)
}
fn corridor_state(
    c: &LoopCorridor,
    table: &LoopTable,
    region: &BTreeSet<u64>,
    instructions: &BTreeMap<u64, Instruction>,
    transfers: &BTreeMap<u64, Transfer>,
    roots: &AddressSet,
    reads: &BTreeMap<(u64, usize), DataRead>,
    work: &mut Work<'_>,
) -> Result<State, Error> {
    if c.sites.is_empty() || c.sites.len() > work.limits.max_path_steps {
        return Err(invalid("loop empty initialization corridor"));
    }
    let sites = c
        .sites
        .iter()
        .map(|s| address(s))
        .collect::<Result<Vec<_>, _>>()?;
    let mut seen = BTreeSet::new();
    let mut state = State::empty(table);
    let last = *sites.last().unwrap();
    if c.entrance.from != hex(last) {
        return Err(invalid("loop corridor boundary"));
    }
    if transfers
        .get(&sites[0])
        .and_then(|t| t.outputs.get(&table.base_bank))
        .and_then(Term::number)
        != Some(address(&table.base)?)
    {
        return Err(invalid("loop corridor missing original base reset"));
    }
    for (at, &site) in sites.iter().enumerate() {
        work.charge(1)?;
        if !matches!(
            instructions.get(&site).map(|i| &i.kind),
            Some(InstructionKind::Ordinary | InstructionKind::Jump | InstructionKind::Conditional)
        ) {
            return Err(invalid("loop unsupported corridor control"));
        }
        if region.contains(&site) || !seen.insert(site) || (at > 0 && roots.contains(&site)) {
            return Err(invalid("loop corridor cycle or root bypass"));
        }
        let (to, taken) = if at + 1 == sites.len() {
            (address(&c.entrance.to)?, c.entrance.taken)
        } else {
            let next = sites[at + 1];
            let edges: Vec<_> = successors(&instructions[&site])
                .into_iter()
                .filter(|(to, _)| *to == next)
                .collect();
            if edges.len() != 1 {
                return Err(invalid("loop corridor edge"));
            }
            edges[0]
        };
        if !successors(&instructions[&site]).contains(&(to, taken)) {
            return Err(invalid("loop corridor edge missing"));
        }
        if at > 0 {
            let actual: BTreeSet<_> = instructions
                .iter()
                .flat_map(|(&p, i)| {
                    successors(i)
                        .into_iter()
                        .filter(move |(to, _)| *to == site)
                        .map(move |(_, t)| (p, t))
                })
                .collect();
            work.charge(instructions.len())?;
            if actual
                != [(
                    sites[at - 1],
                    successors(&instructions[&sites[at - 1]])
                        .into_iter()
                        .find(|(to, _)| *to == site)
                        .unwrap()
                        .1,
                )]
                .into()
            {
                return Err(invalid("loop corridor hidden entrance"));
            }
        }
        state = transfer(
            site,
            taken,
            &state,
            table,
            instructions,
            transfers,
            reads,
            work,
        )?
        .ok_or_else(|| invalid("loop infeasible initialization corridor"))?;
    }
    Ok(state)
}
fn retained_table(
    row: &Resolution,
    base: u64,
    table: &LoopTable,
    work: &mut Work<'_>,
) -> Result<(), Error> {
    for entry in &table.entries {
        let mut found = false;
        for path in &row.paths {
            work.charge(
                1usize
                    .saturating_add(path.indices.len())
                    .saturating_add(path.entries.len()),
            )?;
            if path.form == "relative32"
                && path.base == hex(base)
                && path.indices.contains(&entry.index)
                && path.entries.contains(entry)
            {
                found = true;
                break;
            }
        }
        if !found {
            return Err(invalid("loop table requires new path witness"));
        }
    }
    Ok(())
}

fn table_entries(
    table: &LoopTable,
    reads: &BTreeMap<(u64, usize), DataRead>,
    work: &mut Work<'_>,
) -> Result<BTreeSet<String>, Error> {
    if table.indices.is_empty()
        || table.indices.len() > work.limits.max_entries
        || table.indices.len() > work.limits.max_values
        || table.indices.windows(2).any(|x| x[0] >= x[1])
        || table.entries.len() != table.indices.len()
    {
        return Err(invalid("loop table domain limit or order"));
    }
    let base = address(&table.base)?;
    let mut targets = BTreeSet::new();
    for (&index, e) in table.indices.iter().zip(&table.entries) {
        work.charge(1)?;
        let slot = base.wrapping_add(index.wrapping_mul(4));
        if e.index != index || e.slot != hex(slot) {
            return Err(invalid("loop table slot"));
        }
        let r = reads
            .get(&(slot, 4))
            .ok_or_else(|| invalid("loop table read missing"))?;
        validate_data_read(r)?;
        let bytes = decode_bytes(&r.bytes_hex)
            .filter(|b| b.len() == 4)
            .ok_or_else(|| invalid("loop table read incomplete"))?;
        if e.bytes_hex != r.bytes_hex {
            return Err(invalid("loop table byte binding"));
        }
        let target = base.wrapping_add(i32::from_le_bytes(bytes.try_into().unwrap()) as i64 as u64);
        if e.target != hex(target) {
            return Err(invalid("loop table target arithmetic"));
        }
        targets.insert(hex(target));
    }
    Ok(targets)
}
fn checked_assertions(
    receipt: &LoopClosureReceipt,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    reads: &BTreeMap<(u64, usize), DataRead>,
    row: &Resolution,
    work: &mut Work<'_>,
) -> Result<(), Error> {
    let region = receipt
        .region
        .iter()
        .map(|s| address(s))
        .collect::<Result<BTreeSet<_>, _>>()?;
    let dispatch_site = address(&receipt.dispatch)?;
    for &site in &region {
        let i = instructions
            .get(&site)
            .ok_or_else(|| invalid("loop region instruction missing"))?;
        if (i.kind == InstructionKind::Indirect && site != dispatch_site)
            || !matches!(
                i.kind,
                InstructionKind::Ordinary
                    | InstructionKind::Jump
                    | InstructionKind::Conditional
                    | InstructionKind::Indirect
            )
        {
            return Err(invalid("loop unsupported regional control"));
        }
    }
    if region.len() != receipt.region.len()
        || receipt.region != region.iter().copied().map(hex).collect::<Vec<_>>()
        || region.is_empty()
        || region.len() > work.limits.max_path_steps
        || !region.contains(&address(&receipt.dispatch)?)
        || !region.is_disjoint(roots)
    {
        return Err(invalid("loop region domain or root"));
    }
    if receipt.table.base_bank == receipt.table.selector_bank
        || ![&receipt.table.base_bank, &receipt.table.selector_bank]
            .iter()
            .all(|k| BANKS.iter().any(|b| **k == format!("{b}:0:false")))
    {
        return Err(invalid("loop table bank identity"));
    }
    let actual = inventory(&region, instructions, work)?;
    if actual
        != (
            receipt.internal_edges.clone(),
            receipt.entrances.clone(),
            receipt.exits.clone(),
        )
        || receipt.entrances.is_empty()
    {
        return Err(invalid("loop edge inventory"));
    }
    if receipt
        .corridors
        .iter()
        .map(|c| c.entrance.clone())
        .collect::<Vec<_>>()
        != receipt.entrances
    {
        return Err(invalid("loop entrance corridors"));
    }
    let mut expected_sources = region.clone();
    for c in &receipt.corridors {
        for s in &c.sites {
            expected_sources.insert(address(s)?);
        }
    }
    work.charge(expected_sources.len())?;
    let expected = expected_sources
        .iter()
        .map(|s| {
            transfers
                .get(s)
                .map(|t| LoopSourceRef {
                    site: hex(*s),
                    bytes_hex: t.bytes_hex.clone(),
                    ast_sha256: t.ast_sha256.clone(),
                })
                .ok_or_else(|| invalid("loop source missing"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    if expected != receipt.source_refs {
        return Err(invalid("loop source inventory"));
    }
    for &s in &expected_sources {
        work.charge(1)?;
        work.charge(
            transfers
                .get(&s)
                .ok_or_else(|| invalid("loop source missing"))?
                .ast
                .len(),
        )?;
        safe(s, instructions, transfers)?;
    }
    if receipt
        .assertions
        .iter()
        .map(|a| a.site.clone())
        .collect::<Vec<_>>()
        != receipt.region
    {
        return Err(invalid("loop assertion inventory"));
    }
    let assertions = receipt
        .assertions
        .iter()
        .map(|a| {
            Ok((
                address(&a.site)?,
                State::from_assertion(a, &receipt.table, work)?,
            ))
        })
        .collect::<Result<BTreeMap<_, _>, Error>>()?;
    let base = WordDomain::constant(address(&receipt.table.base)?, 64);
    for assertion in assertions.values() {
        if assertion.domains[&receipt.table.base_bank] != base {
            return Err(invalid("loop stable base invariant"));
        }
    }
    for c in &receipt.corridors {
        let state = corridor_state(
            c,
            &receipt.table,
            &region,
            instructions,
            transfers,
            roots,
            reads,
            work,
        )?;
        if !state.included(&assertions[&address(&c.entrance.to)?], work)? {
            return Err(invalid("loop entrance inclusion"));
        }
    }
    for e in receipt.internal_edges.iter().chain(&receipt.exits) {
        let from = address(&e.from)?;
        let to = address(&e.to)?;
        if let Some(state) = transfer(
            from,
            e.taken,
            &assertions[&from],
            &receipt.table,
            instructions,
            transfers,
            reads,
            work,
        )? {
            if region.contains(&to) && !state.included(&assertions[&to], work)? {
                return Err(invalid("loop preservation inclusion"));
            }
        }
    }
    let load = address(&receipt.table.load_site)?;
    let state = assertions
        .get(&load)
        .ok_or_else(|| invalid("loop table load outside region"))?;
    let indices = state.domains[&receipt.table.selector_bank]
        .values(work)?
        .ok_or_else(|| invalid("loop table domain unbounded"))?;
    if indices != receipt.table.indices {
        return Err(invalid("loop selector domain coverage"));
    }
    let derived = table_entries(&receipt.table, reads, work)?;
    retained_table(row, address(&receipt.table.base)?, &receipt.table, work)?;
    let dispatch = address(&receipt.dispatch)?;
    let targets: BTreeSet<_> = instructions[&dispatch]
        .targets
        .iter()
        .copied()
        .map(hex)
        .collect();
    if derived != targets || derived != row.targets.iter().cloned().collect() {
        return Err(invalid("loop dispatch successor coverage"));
    }
    let jump = transfers
        .get(&dispatch)
        .and_then(|t| t.jump.as_ref())
        .ok_or_else(|| invalid("loop dispatch source jump"))?;
    let values = eval(jump, &assertions[&dispatch], &receipt.table, reads, work, 0)?
        .values(work)?
        .ok_or_else(|| invalid("loop dispatch domain unbounded"))?;
    if values.into_iter().map(hex).collect::<BTreeSet<_>>() != derived {
        return Err(invalid("loop dispatch invariant target domain"));
    }
    // The table form is independently reconstructed from original source
    // transfers; this is not an assertion that arbitrary load values are targets.
    let Some((base_bank, selector_bank, load_site)) =
        shape(dispatch, instructions, transfers, work)?
    else {
        return Err(invalid("loop relative table source form"));
    };
    if (base_bank, selector_bank, load_site)
        != (
            receipt.table.base_bank.clone(),
            receipt.table.selector_bank.clone(),
            receipt.table.load_site.clone(),
        )
    {
        return Err(invalid("loop table source shape"));
    }
    Ok(())
}
pub(super) fn validate(
    receipt: &LoopClosureReceipt,
    report: &Report,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    reads: &BTreeMap<(u64, usize), DataRead>,
    row: &Resolution,
) -> Result<(), Error> {
    if receipt.schema != "ariadne.loop-target-closure/v1"
        || receipt.rule != "local-phase-induction/v1"
        || receipt.snapshot != report.snapshot
        || receipt.artifact_sha256 != report.artifact_sha256
        || receipt.graph_sha256 != report.graph_sha256
        || receipt.model_sha256 != model_identity()
        || (receipt.engine_sha256 != loop_engine_identity()
            && receipt.engine_sha256 != LEGACY_QUESTION_LOOP_ENGINE)
        || receipt.dispatch != row.site
    {
        return Err(invalid("loop closure identity"));
    }
    let start = Instant::now();
    let mut left = report.limits.max_steps;
    let mut work = Work {
        left: &mut left,
        start: &start,
        limits: &report.limits,
    };
    checked_assertions(
        receipt,
        instructions,
        roots,
        transfers,
        reads,
        row,
        &mut work,
    )
}
#[allow(clippy::too_many_arguments)]
pub(super) enum Attempt {
    NotApplicable,
    Candidate(Box<LoopClosureReceipt>),
    Partial(String),
}

pub(super) fn propose<F>(
    snapshot: &str,
    artifact: &str,
    instructions: &BTreeMap<u64, Instruction>,
    roots: &AddressSet,
    transfers: &BTreeMap<u64, Transfer>,
    limits: &Limits,
    left: &mut usize,
    start: &Instant,
    _read: &mut F,
    reads: &mut BTreeMap<(u64, usize), DataRead>,
    _read_bytes: &mut usize,
    site: u64,
    row: &Resolution,
) -> Result<Attempt, Error>
where
    F: FnMut(u64, usize) -> Result<DataRead, Error>,
{
    let mut work = Work {
        left,
        start,
        limits,
    };
    let result = (|| -> Result<Option<LoopClosureReceipt>, Error> {
        // This first rule supplies coverage for an already witnessed finite
        // table. Do not scan an unrelated cyclic dispatch's graph.
        let bases: BTreeSet<_> = row
            .paths
            .iter()
            .filter(|p| p.form == "relative32" && !p.entries.is_empty())
            .map(|p| p.base.clone())
            .collect();
        if bases.len() != 1 || row.targets.is_empty() {
            return Ok(None);
        }
        let base = address(bases.first().unwrap())?;
        let Some((base_bank, selector_bank, load_site)) =
            shape(site, instructions, transfers, &mut work)?
        else {
            return Ok(None);
        };
        let mut entries = BTreeMap::new();
        for p in &row.paths {
            work.charge(1usize.saturating_add(p.entries.len()))?;
            if p.form == "relative32" && p.base == hex(base) {
                for e in &p.entries {
                    entries.insert(e.index, e.clone());
                }
            }
        }
        let table = LoopTable {
            load_site,
            base_bank: base_bank.clone(),
            selector_bank,
            base: hex(base),
            indices: entries.keys().copied().collect(),
            entries: entries.into_values().collect(),
        };
        let mut previous: BTreeMap<u64, BTreeSet<u64>> = BTreeMap::new();
        for (&p, i) in instructions {
            work.charge(1)?;
            for (to, _) in successors(i) {
                work.charge(1)?;
                previous.entry(to).or_default().insert(p);
            }
        }
        let mut closure = BTreeSet::new();
        let mut pending = vec![site];
        while let Some(s) = pending.pop() {
            work.charge(1)?;
            if !closure.insert(s) {
                continue;
            }
            if closure.len() > limits.max_path_steps {
                return Ok(None);
            }
            for &p in previous.get(&s).into_iter().flatten() {
                let reset = transfers
                    .get(&p)
                    .and_then(|t| t.outputs.get(&base_bank))
                    .and_then(Term::number)
                    .is_some();
                if !reset {
                    pending.push(p);
                }
            }
        }
        let mut region = BTreeSet::new();
        let mut pending = vec![site];
        while let Some(s) = pending.pop() {
            work.charge(1)?;
            if !region.insert(s) {
                continue;
            }
            for (to, _) in successors(&instructions[&s]) {
                if closure.contains(&to) {
                    pending.push(to);
                }
            }
        }
        if region.len() < 2 {
            return Ok(None);
        }
        let (internal_edges, entrances, exits) = inventory(&region, instructions, &mut work)?;
        if entrances.is_empty() {
            return Ok(None);
        }
        let corridors = corridors(
            &entrances,
            &region,
            &base_bank,
            base,
            instructions,
            transfers,
            roots,
            &mut work,
        )?;
        let mut states: BTreeMap<u64, State> = BTreeMap::new();
        let mut pending = BTreeSet::new();
        for c in &corridors {
            let to = address(&c.entrance.to)?;
            let state = corridor_state(
                c,
                &table,
                &region,
                instructions,
                transfers,
                roots,
                reads,
                &mut work,
            )?;
            let state = if let Some(old) = states.get(&to) {
                old.join(&state, &mut work)?
            } else {
                state
            };
            states.insert(to, state);
            pending.insert(to);
        }
        let mut rounds = 0usize;
        while !pending.is_empty() {
            rounds += 1;
            if rounds > limits.max_rounds.saturating_mul(region.len()) {
                return Ok(None);
            }
            let current = std::mem::take(&mut pending);
            for from in current {
                work.charge(1)?;
                for (to, taken) in successors(&instructions[&from]) {
                    if !region.contains(&to) {
                        continue;
                    }
                    if let Some(out) = transfer(
                        from,
                        taken,
                        &states[&from],
                        &table,
                        instructions,
                        transfers,
                        reads,
                        &mut work,
                    )? {
                        let joined = if let Some(old) = states.get(&to) {
                            old.join(&out, &mut work)?
                        } else {
                            out
                        };
                        if states.get(&to) != Some(&joined) {
                            states.insert(to, joined);
                            pending.insert(to);
                        }
                    }
                }
            }
        }
        if states.len() != region.len() {
            return Ok(None);
        }
        let mut sources = region.clone();
        for c in &corridors {
            for s in &c.sites {
                sources.insert(address(s)?);
            }
        }
        let source_refs = sources
            .into_iter()
            .map(|s| {
                transfers
                    .get(&s)
                    .map(|t| LoopSourceRef {
                        site: hex(s),
                        bytes_hex: t.bytes_hex.clone(),
                        ast_sha256: t.ast_sha256.clone(),
                    })
                    .ok_or_else(|| invalid("loop proposal source missing"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        let receipt = LoopClosureReceipt {
            schema: "ariadne.loop-target-closure/v1".into(),
            rule: "local-phase-induction/v1".into(),
            snapshot: snapshot.into(),
            artifact_sha256: artifact.into(),
            graph_sha256: graph_digest(instructions, roots)?,
            model_sha256: model_identity(),
            engine_sha256: loop_engine_identity(),
            dispatch: hex(site),
            region: region.iter().copied().map(hex).collect(),
            internal_edges,
            entrances,
            exits,
            corridors,
            assertions: states.iter().map(|(&s, a)| a.assertion(s)).collect(),
            table,
            source_refs,
        };
        checked_assertions(
            &receipt,
            instructions,
            roots,
            transfers,
            reads,
            row,
            &mut work,
        )?;
        Ok(Some(receipt))
    })();
    // A declined induction proposal never weakens an existing path witness.
    match result {
        Ok(Some(receipt)) => Ok(Attempt::Candidate(Box::new(receipt))),
        Ok(None) => Ok(Attempt::NotApplicable),
        Err(error) => {
            if std::env::var_os("ARIADNE_TARGET_DIAGNOSTICS").is_some() {
                eprintln!("loop closure site={} declined: {error}", hex(site));
            }
            let reason = if error.to_string().contains("new path witness") {
                "loop-closure-requires-retained-table-witness"
            } else if error.to_string().contains("work") {
                "loop-closure-work-limit"
            } else {
                "loop-closure-unproved"
            };
            Ok(Attempt::Partial(reason.into()))
        }
    }
}
