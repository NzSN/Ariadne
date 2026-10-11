//! Immutable, candidate-preserving memory-origin assessment over completed facts.
use super::fault_context::{CapturedFaultContext, validate_context, values};
use super::validate::{digest, site_valid};
use super::{
    AccessRole, AddressUse, BackwardValue, BoundInvestigation, Error, FaultAddressQuestion,
    Identity, OriginKind, SiteEvidence, invalid, sha,
};
use super::{FaultDatum, FaultMetadata, backward_preimage};
use crate::bap::refinement::{TransferExpression, TransferReceipt};
use crate::{DefinitionOrigin, InstructionKind};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const MEMORY_PROVENANCE_SCHEMA: &str = "ariadne.memory-provenance-assessment/v1";
pub const MEMORY_PROVENANCE_PROFILE: &str = "captured-amd64-memory-provenance-v1";
const BANKS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryRefinementLimits {
    pub max_candidates: usize,
    pub max_pair_checks: usize,
    pub max_numerical_tasks: usize,
    pub max_alternatives: usize,
    pub max_expression_nodes: usize,
    pub max_expression_depth: usize,
}
impl Default for MemoryRefinementLimits {
    fn default() -> Self {
        Self {
            max_candidates: 128,
            max_pair_checks: 4096,
            max_numerical_tasks: 4096,
            max_alternatives: 256,
            max_expression_nodes: 8192,
            max_expression_depth: 64,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct NodeRef {
    #[serde(with = "super::model::va")]
    site: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ScopeNode {
    #[serde(with = "super::model::va")]
    site: u64,
    predecessors: Vec<NodeRef>,
    root: bool,
    may_defs: Vec<String>,
    memory_kill: bool,
    ordinary: bool,
    uses: Vec<String>,
    in_slice: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryCandidate {
    #[serde(with = "super::model::va")]
    pub site: u64,
    pub origin: OriginKind,
    pub disposition: String,
    pub reason: String,
    pub pairs: Vec<MemoryPair>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryPair {
    pub store_access: usize,
    pub relation: String,
    pub rule: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryDependencyDiagnostic {
    #[serde(with = "super::model::va")]
    pub site: u64,
    pub kind: String,
    pub original_gaps: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NumericalBoundary {
    #[serde(with = "super::model::va")]
    pub site: u64,
    pub register: String,
    pub value: BackwardValue,
    pub reason: Option<String>,
    pub predecessor: Option<String>,
    pub path_scope: Vec<String>,
    pub classification: super::Classification,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct FaultWitness {
    metadata: FaultMetadata,
    data: Vec<FaultDatum>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    identity: Identity,
    question: FaultAddressQuestion,
    nodes: Vec<ScopeNode>,
    sites: Vec<SiteEvidence>,
    receipts: Vec<TransferReceipt>,
    originals: Vec<MemoryCandidate>,
    recovery_closed: bool,
    fault: Option<FaultWitness>,
}
/// Capture adapter supplies receipts. The symbolic constructor supplies none.
pub struct BoundMemoryRefinement {
    analysis: BoundInvestigation,
    receipts: BTreeMap<u64, TransferReceipt>,
    fault: Option<FaultWitness>,
}
impl BoundMemoryRefinement {
    pub fn from_investigation(analysis: BoundInvestigation) -> Self {
        Self {
            analysis,
            receipts: BTreeMap::new(),
            fault: None,
        }
    }
    pub(crate) fn new(
        analysis: BoundInvestigation,
        receipts: BTreeMap<u64, TransferReceipt>,
        fault: Option<CapturedFaultContext>,
    ) -> Result<Self, Error> {
        for (site, receipt) in &receipts {
            receipt.validate(
                analysis
                    .sites
                    .get(site)
                    .ok_or_else(|| invalid("receipt site outside query"))?,
            )?;
        }
        let fault = fault.map(|f| FaultWitness {
            metadata: f.metadata,
            data: f.data,
        });
        if let Some(f) = &fault {
            validate_context(&f.metadata, &f.data, true)?;
            if f.metadata.snapshot_id != analysis.identity.snapshot_id
                || f.metadata.artifact_sha256 != analysis.identity.artifact_sha256
            {
                return Err(invalid("fault witness belongs to another snapshot"));
            }
        }
        Ok(Self {
            analysis,
            receipts,
            fault,
        })
    }
    pub fn identity(&self) -> &Identity {
        self.analysis.identity()
    }
    fn input(&self, question: FaultAddressQuestion) -> Result<Input, Error> {
        let site = self
            .analysis
            .sites
            .get(&question.site)
            .ok_or_else(|| invalid("question site is outside this query"))?;
        if site.accesses.is_empty() {
            if question.memory_access != 0 {
                return Err(invalid("memory-access index does not exist"));
            }
        } else {
            let access = site
                .accesses
                .get(question.memory_access)
                .ok_or_else(|| invalid("memory-access index does not exist"))?;
            if access.role != AccessRole::Load {
                return Err(invalid("memory provenance requires a load"));
            }
        }
        let request = &self.analysis.request;
        let state = &self.analysis.state;
        let nodes = state
            .decoded
            .iter()
            .map(|&site| ScopeNode {
                site,
                root: request.entry_points.contains(&site),
                predecessors: state
                    .edges
                    .iter()
                    .filter(|e| {
                        e.dst == site && e.kind.is_local() && state.decoded.contains(&e.src)
                    })
                    .map(|e| NodeRef { site: e.src })
                    .collect::<BTreeSet<_>>()
                    .into_iter()
                    .collect(),
                may_defs: request.instructions[&site]
                    .may_defs
                    .iter()
                    .cloned()
                    .collect(),
                memory_kill: request.instructions[&site].must_defs.contains("memory:any"),
                ordinary: request.instructions[&site].kind == InstructionKind::Ordinary,
                uses: request.instructions[&site].uses.iter().cloned().collect(),
                in_slice: state.slice.contains(&site),
            })
            .collect();
        let originals = state.reaching[&question.site]
            .iter()
            .filter(|d| d.loc == "memory:any")
            .map(|d| MemoryCandidate {
                site: d.site,
                origin: if d.origin == DefinitionOrigin::Entry {
                    OriginKind::Entry
                } else {
                    OriginKind::Instruction
                },
                disposition: "unresolved".into(),
                reason: "not-assessed".into(),
                pairs: Vec::new(),
            })
            .collect();
        Ok(Input {
            identity: self.analysis.identity.clone(),
            question,
            nodes,
            sites: self.analysis.sites.values().cloned().collect(),
            receipts: self.receipts.values().cloned().collect(),
            originals,
            recovery_closed: state.obligations.is_empty(),
            fault: self.fault.clone(),
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryProvenanceAssessment {
    pub schema: String,
    pub profile: String,
    pub identity: Identity,
    pub question: FaultAddressQuestion,
    pub scope_id: String,
    pub input_digest: String,
    pub limits: MemoryRefinementLimits,
    pub available: bool,
    pub original_candidate_count: usize,
    pub candidates: Vec<MemoryCandidate>,
    pub numerical: Vec<NumericalBoundary>,
    pub diagnostics: Vec<MemoryDependencyDiagnostic>,
    pub gaps: Vec<String>,
    pub truncated: bool,
    pub premises: Vec<String>,
    input: Input,
}

/// Exact modular byte overlap for the admitted scalar access sizes.
pub fn modular_memory_overlap(a: u64, n: usize, b: u64, m: usize) -> Result<bool, Error> {
    if ![1, 2, 4, 8].contains(&n) || ![1, 2, 4, 8].contains(&m) {
        return Err(invalid("unsupported access width"));
    }
    fn intervals(a: u64, n: usize) -> Vec<(u128, u128)> {
        let modulus = 1u128 << 64;
        let start = u128::from(a);
        let end = start + n as u128;
        if end <= modulus {
            vec![(start, end)]
        } else {
            vec![(start, modulus), (0, end - modulus)]
        }
    }
    Ok(intervals(a, n)
        .iter()
        .any(|(a, z)| intervals(b, m).iter().any(|(b, y)| a < y && b < z)))
}
fn ancestors(nodes: &BTreeMap<u64, &ScopeNode>, site: u64) -> BTreeSet<u64> {
    let mut todo = vec![site];
    let mut seen = BTreeSet::new();
    while let Some(site) = todo.pop() {
        if seen.insert(site)
            && let Some(n) = nodes.get(&site)
        {
            todo.extend(n.predecessors.iter().map(|p| p.site));
        }
    }
    seen
}
fn acyclic(nodes: &BTreeMap<u64, &ScopeNode>, prefix: &BTreeSet<u64>) -> bool {
    let mut remaining: BTreeMap<u64, usize> = prefix
        .iter()
        .map(|s| {
            (
                *s,
                nodes.get(s).map_or(0, |n| {
                    n.predecessors
                        .iter()
                        .filter(|p| prefix.contains(&p.site))
                        .count()
                }),
            )
        })
        .collect();
    let mut ready: BTreeSet<u64> = remaining
        .iter()
        .filter_map(|(&s, &n)| (n == 0).then_some(s))
        .collect();
    let mut visited = 0;
    while let Some(site) = ready.pop_first() {
        visited += 1;
        for (&s, n) in nodes {
            if prefix.contains(&s)
                && n.predecessors.iter().any(|p| p.site == site)
                && let Some(count) = remaining.get_mut(&s)
                && *count > 0
            {
                *count -= 1;
                if *count == 0 {
                    ready.insert(s);
                }
            }
        }
    }
    visited == prefix.len()
}
fn unchanged_base(input: &Input, store: u64, load: u64, bank: u8) -> bool {
    if !input.recovery_closed || bank >= 16 {
        return false;
    }
    let nodes: BTreeMap<_, _> = input.nodes.iter().map(|n| (n.site, n)).collect();
    let prefix = ancestors(&nodes, load);
    if !prefix.contains(&store) || !acyclic(&nodes, &prefix) {
        return false;
    }
    let mut descendants = BTreeSet::from([store]);
    let mut todo = vec![store];
    while let Some(s) = todo.pop() {
        for (&dst, n) in &nodes {
            if prefix.contains(&dst)
                && n.predecessors.iter().any(|p| p.site == s)
                && descendants.insert(dst)
            {
                todo.push(dst);
            }
        }
    }
    descendants.remove(&load);
    let cells: BTreeSet<String> = (0..8)
        .map(|i| format!("gpr:{}:{i}", BANKS[usize::from(bank)]))
        .collect();
    descendants.iter().all(|s| {
        nodes
            .get(s)
            .is_some_and(|n| n.may_defs.iter().all(|l| !cells.contains(l)))
    })
}
fn pair(
    input: &Input,
    store_site: u64,
    store: &AddressUse,
    load: &AddressUse,
) -> Result<MemoryPair, Error> {
    let unknown = || MemoryPair {
        store_access: store.index,
        relation: "unknown".into(),
        rule: "unsupported-address-or-scope".into(),
    };
    if store.address_width != 64
        || load.address_width != 64
        || !store.gaps.is_empty()
        || !load.gaps.is_empty()
        || ![8, 16, 32, 64].contains(&store.access_width)
        || ![8, 16, 32, 64].contains(&load.access_width)
    {
        return Ok(unknown());
    }
    let (Some(a), Some(b)) = (&store.expression, &load.expression) else {
        return Ok(unknown());
    };
    let rule = if a.terms.is_empty() && b.terms.is_empty() {
        "constant-ranges"
    } else if a.terms.len() == 1
        && a.terms == b.terms
        && unchanged_base(input, store_site, input.question.site, a.terms[0].bank)
    {
        "preserved-common-base"
    } else {
        return Ok(unknown());
    };
    let overlapping = modular_memory_overlap(
        a.constant,
        usize::from(store.access_width / 8),
        b.constant,
        usize::from(load.access_width / 8),
    )?;
    Ok(MemoryPair {
        store_access: store.index,
        relation: if overlapping {
            "overlapping"
        } else {
            "disjoint"
        }
        .into(),
        rule: rule.into(),
    })
}
fn validate_input(input: &Input) -> Result<(), Error> {
    if !digest(&input.identity.artifact_sha256)
        || !digest(&input.identity.query_id)
        || !digest(&input.identity.request_sha256)
        || input.identity.snapshot_id.is_empty()
    {
        return Err(invalid("invalid refinement identity"));
    }
    if let Some(f) = &input.fault {
        validate_context(&f.metadata, &f.data, true)?;
        if f.metadata.snapshot_id != input.identity.snapshot_id
            || f.metadata.artifact_sha256 != input.identity.artifact_sha256
        {
            return Err(invalid("fault witness identity mismatch"));
        }
    }
    let sites: BTreeMap<_, _> = input.sites.iter().map(|s| (s.va, s)).collect();
    if sites.len() != input.sites.len() || input.sites.iter().any(|s| !site_valid(s)) {
        return Err(invalid("invalid refinement site evidence"));
    }
    let selected = sites
        .get(&input.question.site)
        .ok_or_else(|| invalid("selected site missing"))?;
    if selected.accesses.is_empty() {
        if input.question.memory_access != 0 {
            return Err(invalid("invalid selected index"));
        }
    } else if selected
        .accesses
        .get(input.question.memory_access)
        .is_none_or(|a| a.role != AccessRole::Load)
    {
        return Err(invalid("invalid selected load"));
    }
    let nodes: BTreeMap<_, _> = input.nodes.iter().map(|n| (n.site, n)).collect();
    if nodes.len() != input.nodes.len()
        || input.nodes.iter().any(|n| {
            n.memory_kill
                || !sites.contains_key(&n.site)
                || n.predecessors.iter().any(|p| !nodes.contains_key(&p.site))
        })
    {
        return Err(invalid("invalid refinement graph or global memory kill"));
    }
    let mut seen = BTreeSet::new();
    for receipt in &input.receipts {
        if !seen.insert(receipt.site) {
            return Err(invalid("duplicate receipt"));
        }
        receipt.validate(
            sites
                .get(&receipt.site)
                .ok_or_else(|| invalid("receipt lacks instruction"))?,
        )?;
    }
    let mut prefix = BTreeSet::new();
    if let Some(selected) = nodes.get(&input.question.site) {
        for predecessor in &selected.predecessors {
            prefix.extend(ancestors(&nodes, predecessor.site));
        }
    }
    let mut expected = BTreeSet::new();
    for site in prefix {
        if let Some(n) = nodes.get(&site) {
            if n.root {
                expected.insert((site, 0));
            }
            if n.may_defs.iter().any(|l| l == "memory:any") {
                expected.insert((site, 1));
            }
        }
    }
    if nodes.get(&input.question.site).is_some_and(|n| n.root) {
        expected.insert((input.question.site, 0));
    }
    let originals: BTreeSet<_> = input
        .originals
        .iter()
        .map(|c| (c.site, if c.origin == OriginKind::Entry { 0 } else { 1 }))
        .collect();
    if input
        .originals
        .iter()
        .any(|c| c.disposition != "unresolved" || c.reason != "not-assessed" || !c.pairs.is_empty())
        || originals.len() != input.originals.len()
        || originals != expected
    {
        return Err(invalid(
            "candidate universe disagrees with memory origin graph",
        ));
    }
    Ok(())
}

/// New seed profile: coherent ordinary scalar AV accesses, not historical values.
fn fault_seeds(input: &Input) -> Option<(u64, BTreeMap<u8, u64>)> {
    let f = input.fault.as_ref()?;
    if f.metadata.platform != "windows-amd64"
        || !f.metadata.exception_present
        || !f.metadata.context_supported
    {
        return None;
    }
    let fields = values(&f.data);
    if fields.get("code") != Some(&0xc0000005)
        || fields.get("flags") != Some(&0)
        || fields.get("chain") != Some(&0)
        || *fields.get("number_parameters")? < 2
    {
        return None;
    }
    let rip = *fields.get("reg:rip")?;
    if fields.get("exception_location") != Some(&rip)
        || !input.nodes.iter().any(|n| n.site == rip && n.ordinary)
    {
        return None;
    }
    let site = input.sites.iter().find(|s| s.va == rip)?;
    if site.semantic_status.as_deref() != Some("projected")
        || site.quality != "external_lift"
        || !site.captured
    {
        return None;
    }
    let access = site.accesses.first()?;
    if access.address_width != 64
        || ![8, 16, 32, 64].contains(&access.access_width)
        || !access.gaps.is_empty()
    {
        return None;
    }
    let expression = access.expression.as_ref()?;
    if site.accesses.iter().any(|a| {
        a.expression.as_ref() != Some(expression)
            || a.access_width != access.access_width
            || a.role != access.role
            || !a.gaps.is_empty()
    }) {
        return None;
    }
    let operation = if access.role == AccessRole::Load {
        0
    } else {
        1
    };
    if fields.get("parameter:0") != Some(&operation) {
        return None;
    }
    let mut address = expression.constant;
    for term in &expression.terms {
        let name = format!("reg:{}", BANKS[usize::from(term.bank)]);
        address = address.wrapping_add(fields.get(name.as_str())?.wrapping_mul(term.coefficient));
    }
    let reported = *fields.get("parameter:1")?;
    let end = u128::from(address) + u128::from(access.access_width / 8);
    if end > 0x0000800000000000 || reported < address || u128::from(reported) >= end {
        return None;
    }
    let selected = input
        .sites
        .iter()
        .find(|s| s.va == input.question.site)?
        .accesses
        .get(input.question.memory_access)?;
    let mut seeds = BTreeMap::new();
    for term in &selected.expression.as_ref()?.terms {
        let name = format!("reg:{}", BANKS[usize::from(term.bank)]);
        if let Some(value) = fields.get(name.as_str()) {
            seeds.insert(term.bank, *value);
        }
    }
    Some((rip, seeds))
}
type InverseExpressionResult = (Option<(u8, BackwardValue)>, Option<String>);
fn inverse_expression(
    value: &BackwardValue,
    expression: &TransferExpression,
    destination: u8,
    depth: usize,
    limit: usize,
) -> Result<InverseExpressionResult, Error> {
    if depth >= limit {
        return Ok((None, Some("constraint-expression-budget".into())));
    }
    match expression {
        TransferExpression::Input { bank } => Ok((Some((*bank, value.clone())), None)),
        TransferExpression::Constant { value: constant } => {
            let result =
                backward_preimage(value, &super::ScalarTransfer::Constant { value: *constant })?;
            Ok((result.before.map(|v| (destination, v)), result.boundary))
        }
        TransferExpression::Apply { operation, input } => {
            let result = backward_preimage(value, operation)?;
            if let Some(value) = result.before {
                if let Some(reason) = result.boundary {
                    Ok((Some((destination, value)), Some(reason)))
                } else {
                    inverse_expression(&value, input, destination, depth + 1, limit)
                }
            } else {
                Ok((None, result.boundary))
            }
        }
        TransferExpression::Unsupported { reason } => Ok((None, Some(reason.clone()))),
    }
}
fn numerical(
    input: &Input,
    limits: &MemoryRefinementLimits,
) -> Result<(Vec<NumericalBoundary>, Vec<String>, bool), Error> {
    let Some((rip, seeds)) = fault_seeds(input) else {
        return Ok((Vec::new(), vec!["fault-seed-unavailable".into()], false));
    };
    walk_numerical(input, limits, rip, seeds)
}
fn walk_numerical(
    input: &Input,
    limits: &MemoryRefinementLimits,
    rip: u64,
    seeds: BTreeMap<u8, u64>,
) -> Result<(Vec<NumericalBoundary>, Vec<String>, bool), Error> {
    let nodes: BTreeMap<_, _> = input.nodes.iter().map(|n| (n.site, n)).collect();
    let receipts: BTreeMap<_, _> = input.receipts.iter().map(|r| (r.site, r)).collect();
    let mut queue = std::collections::VecDeque::new();
    for (bank, value) in seeds {
        queue.push_back((
            rip,
            bank,
            BackwardValue::Exact { width: 64, value },
            vec![rip],
        ));
    }
    let mut facts = Vec::new();
    let mut gaps = Vec::new();
    let mut truncated = false;
    let mut tasks = 0;
    let mut alternatives = 0;
    let mut memo = BTreeSet::new();
    while let Some((site, bank, value, path)) = queue.pop_front() {
        if tasks >= limits.max_numerical_tasks {
            truncated = true;
            gaps.push("numerical-task-budget".into());
            break;
        }
        let key = sha(&serde_json::to_vec(&(site, bank, &value, &path))?);
        if !memo.insert(key) {
            continue;
        }
        tasks += 1;
        let node = nodes
            .get(&site)
            .ok_or_else(|| invalid("numerical task outside graph"))?;
        let mut current = NumericalBoundary {
            site,
            register: BANKS[usize::from(bank)].into(),
            value: value.clone(),
            reason: None,
            predecessor: None,
            path_scope: path.iter().map(|s| format!("0x{s:016x}")).collect(),
            classification: super::Classification::DerivedUnderPremises,
        };
        if node.predecessors.is_empty() {
            current.reason = Some("entry-value-boundary".into());
            facts.push(current);
            continue;
        }
        if path.len() > limits.max_expression_depth {
            current.reason = Some("value-scope-budget".into());
            facts.push(current);
            gaps.push("value-scope-budget".into());
            truncated = true;
            continue;
        }
        facts.push(current.clone());
        for p in &node.predecessors {
            if alternatives >= limits.max_alternatives {
                truncated = true;
                gaps.push("predecessor-alternative-budget".into());
                break;
            }
            alternatives += 1;
            if path.contains(&p.site) {
                let mut boundary = current.clone();
                boundary.reason = Some("cyclic-value-scope".into());
                boundary.predecessor = Some(format!("0x{:016x}", p.site));
                facts.push(boundary);
                continue;
            }
            let pred = nodes[&p.site];
            let prefix = format!("gpr:{}:", BANKS[usize::from(bank)]);
            let written = pred.may_defs.iter().any(|l| l.starts_with(&prefix));
            let (before, reason) = if !written {
                (Some((bank, value.clone())), None)
            } else if let Some(expression) =
                receipts.get(&p.site).and_then(|r| r.outputs.get(&bank))
            {
                inverse_expression(
                    &value,
                    expression,
                    bank,
                    0,
                    limits.max_expression_depth.min(limits.max_expression_nodes),
                )?
            } else {
                (
                    None,
                    Some("unsupported-or-unavailable-register-transfer".into()),
                )
            };
            if let Some((next_bank, next_value)) = before {
                let mut next_path = path.clone();
                next_path.push(p.site);
                if let Some(reason) = reason {
                    if reason.ends_with("-budget") {
                        truncated = true;
                        gaps.push(reason.clone());
                    }
                    let classification = if matches!(next_value, BackwardValue::Unknown { .. }) {
                        super::Classification::Unknown
                    } else {
                        super::Classification::DerivedUnderPremises
                    };
                    facts.push(NumericalBoundary {
                        site: p.site,
                        register: BANKS[usize::from(next_bank)].into(),
                        value: next_value,
                        reason: Some(reason),
                        predecessor: None,
                        path_scope: next_path.iter().map(|s| format!("0x{s:016x}")).collect(),
                        classification,
                    });
                } else {
                    queue.push_back((p.site, next_bank, next_value, next_path));
                }
            } else {
                let mut boundary = current.clone();
                if let Some(reason) = &reason {
                    if reason.ends_with("-budget") {
                        truncated = true;
                        gaps.push(reason.clone());
                    }
                }
                boundary.reason = reason;
                boundary.predecessor = Some(format!("0x{:016x}", p.site));
                facts.push(boundary);
            }
        }
    }
    gaps.sort();
    gaps.dedup();
    Ok((facts, gaps, truncated))
}
fn run(input: Input, limits: MemoryRefinementLimits) -> Result<MemoryProvenanceAssessment, Error> {
    validate_input(&input)?;
    let input_digest = sha(&serde_json::to_vec(&input)?);
    let scope_id = sha(&serde_json::to_vec(&(
        &input.identity,
        &input.question,
        MEMORY_PROVENANCE_PROFILE,
        &input_digest,
        &limits,
    ))?);
    let mut out = MemoryProvenanceAssessment {
        schema: MEMORY_PROVENANCE_SCHEMA.into(),
        profile: MEMORY_PROVENANCE_PROFILE.into(),
        identity: input.identity.clone(),
        question: input.question.clone(),
        scope_id,
        input_digest,
        limits,
        available: true,
        original_candidate_count: input.originals.len(),
        candidates: Vec::new(),
        numerical: Vec::new(),
        diagnostics: Vec::new(),
        gaps: Vec::new(),
        truncated: false,
        premises: vec![
            "possible writers under the bound captured query; no executed writer or root cause"
                .into(),
            "pinned BAP and admitted byte-range relations are semantic premises".into(),
            "numerical facts are scalar path-scoped constraints; they do not select execution history or establish a jointly reconstructed pointer".into(),
        ],
        input,
    };
    if out.original_candidate_count > out.limits.max_candidates
        || out.input.nodes.len() > out.limits.max_expression_nodes
    {
        out.available = false;
        out.truncated = true;
        out.gaps.push("refinement-input-budget".into());
        return Ok(out);
    }
    let sites: BTreeMap<_, _> = out.input.sites.iter().map(|s| (s.va, s)).collect();
    let Some(load) = sites[&out.question.site]
        .accesses
        .get(out.question.memory_access)
    else {
        out.available = false;
        out.gaps.push("load-evidence-unavailable".into());
        return Ok(out);
    };
    if load.address_width != 64
        || ![8, 16, 32, 64].contains(&load.access_width)
        || load.expression.is_none()
        || !load.gaps.is_empty()
        || sites[&out.question.site].semantic_status.as_deref() != Some("projected")
    {
        out.available = false;
        out.gaps.push("unsupported-load-address-evidence".into());
        return Ok(out);
    }
    if !out.input.nodes.iter().any(|n| n.site == out.question.site) {
        out.available = false;
        out.gaps.push("not-reached".into());
        return Ok(out);
    }
    let receipts: BTreeMap<_, _> = out.input.receipts.iter().map(|r| (r.site, r)).collect();
    let mut checks = 0;
    for original in &out.input.originals {
        let mut c = original.clone();
        c.pairs.clear();
        if c.origin == OriginKind::Entry {
            c.reason = "entry-memory".into();
        } else if receipts
            .get(&c.site)
            .is_none_or(|r| !r.memory_footprint_complete)
        {
            c.reason = "unverified-memory-footprint".into();
        } else {
            let stores: Vec<_> = sites[&c.site]
                .accesses
                .iter()
                .filter(|a| a.role == AccessRole::Store)
                .collect();
            if stores.is_empty() {
                c.reason = "unknown-memory-effects".into();
            } else {
                for store in stores {
                    if checks >= out.limits.max_pair_checks {
                        out.truncated = true;
                        out.gaps.push("access-pair-budget".into());
                        break;
                    }
                    checks += 1;
                    c.pairs.push(pair(&out.input, c.site, store, load)?);
                }
                let total = sites[&c.site]
                    .accesses
                    .iter()
                    .filter(|a| a.role == AccessRole::Store)
                    .count();
                if c.pairs.len() == total && c.pairs.iter().all(|p| p.relation == "disjoint") {
                    c.disposition = "excluded_within_scope".into();
                    c.reason = "all-stores-proved-disjoint".into();
                } else if c.pairs.iter().any(|p| p.relation == "overlapping") {
                    c.disposition = "retained".into();
                    c.reason = "possible-overlapping-writer".into();
                } else {
                    c.reason = "unresolved-alias-or-budget".into();
                }
            }
        }
        out.candidates.push(c);
    }
    for node in &out.input.nodes {
        if (node.in_slice
            || node.site == out.question.site
            || out.candidates.iter().any(|c| c.site == node.site))
            && node.uses.iter().any(|l| l == "memory:any")
        {
            let site = sites[&node.site];
            let kind = if site.accesses.iter().any(|a| a.role == AccessRole::Load) {
                "memory-load-provenance"
            } else if site.gaps.iter().any(|g| g.starts_with("unknown-output:")) {
                "unknown-output-dependency"
            } else {
                "opaque-or-unclassified-memory-dependency"
            };
            out.diagnostics.push(MemoryDependencyDiagnostic {
                site: node.site,
                kind: kind.into(),
                original_gaps: site.gaps.clone(),
            });
        }
    }
    let (facts, gaps, truncated) = numerical(&out.input, &out.limits)?;
    out.numerical = facts;
    out.gaps.extend(gaps);
    out.truncated |= truncated;
    out.gaps.sort();
    out.gaps.dedup();
    Ok(out)
}
pub fn assess_memory_origins(
    bound: &BoundMemoryRefinement,
    question: FaultAddressQuestion,
    limits: MemoryRefinementLimits,
) -> Result<MemoryProvenanceAssessment, Error> {
    run(bound.input(question)?, limits)
}
impl MemoryProvenanceAssessment {
    pub fn validate(&self) -> Result<(), Error> {
        let expected = run(self.input.clone(), self.limits.clone())?;
        if expected != *self {
            return Err(invalid("memory assessment recomputation mismatch"));
        }
        Ok(())
    }
    pub fn validate_for(&self, bound: &BoundMemoryRefinement) -> Result<(), Error> {
        if self.input != bound.input(self.question.clone())? {
            return Err(invalid("assessment belongs to another bound analysis"));
        }
        self.validate()
    }
}

#[cfg(test)]
#[path = "../../tests/investigation/memory_refinement_unit.rs"]
mod tests;
