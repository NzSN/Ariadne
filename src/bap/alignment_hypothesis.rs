//! Explicit source-bound alignment hypotheses above unchanged baseline proofs.
use super::{Error, guard_admission as guard, invalid};
use crate::{AnalysisRequest, Instruction, InstructionKind};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;
use std::time::Instant;

pub const SCHEMA: &str = "ariadne.alignment-hypothesis/v1";
pub const PROFILE: &str = "captured-site-alignment-hypotheses/v1";
pub const POLICY: &str = "assumed-reviewed-movaps-alignment16/v1";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Hypothesis {
    pub id: String,
    pub snapshot: String,
    pub artifact_sha256: String,
    pub query_scope_sha256: String,
    pub root: String,
    pub activation: guard::Activation,
    pub point: String,
    pub bytes_hex: String,
    pub original_ast_sha256: String,
    pub pending_relation_sha256: String,
    pub displacement: i64,
    pub alignment: u8,
    pub rsp_residues: u16,
    pub decoder_record_sha256: String,
    pub candidate_epoch: u64,
    pub policy: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Fact {
    pub site: String,
    pub incoming: u16,
    pub residues: u16,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Basis {
    Proved,
    Assumed,
    Unreachable,
    Unknown,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Decision {
    pub site: String,
    pub baseline_verdict: guard::Verdict,
    pub verdict: guard::Verdict,
    pub basis: Basis,
    pub input_residues: u16,
    pub address_residues: u16,
    pub normal_ast: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Report {
    pub schema: String,
    pub profile: String,
    pub model_sha256: String,
    pub checker_sha256: String,
    pub baseline_guard_sha256: String,
    pub base_request: Value,
    pub hypotheses: Vec<Hypothesis>,
    pub facts: Vec<Fact>,
    pub decisions: Vec<Decision>,
    pub stop: Option<String>,
    pub limits: guard::Limits,
    pub final_request_sha256: String,
    pub binding_sha256: String,
}
impl Report {
    pub fn normal_selection(&self, site: u64) -> Option<&str> {
        let name = format!("0x{site:016x}");
        self.decisions
            .iter()
            .find(|decision| decision.site == name)
            .and_then(|decision| decision.normal_ast.as_deref())
    }
}
pub fn model_identity() -> String {
    crate::reports::sha256(include_bytes!("../../Specs/AriadneAlignmentHypothesis.tla"))
}
pub fn checker_identity() -> String {
    crate::reports::sha256(include_bytes!("alignment_hypothesis.rs"))
}
fn json_hash(value: &impl Serialize) -> Result<String, Error> {
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
    let mut writer = HashWriter(Sha256::new());
    serde_json::to_writer(&mut writer, value)?;
    Ok(format!("{:x}", writer.0.finalize()))
}
fn evidence_limit(value: &impl Serialize, limit: usize) -> Result<(), Error> {
    struct Counter {
        used: usize,
        limit: usize,
    }
    impl Write for Counter {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            if bytes.len() > self.limit.saturating_sub(self.used) {
                return Err(std::io::Error::other(
                    "alignment hypothesis evidence byte limit",
                ));
            }
            self.used += bytes.len();
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    serde_json::to_writer(&mut Counter { used: 0, limit }, value)?;
    Ok(())
}
fn digest(domain: &str, value: &impl Serialize) -> Result<String, Error> {
    json_hash(&(domain, value))
}
fn binding(report: &Report) -> Result<String, Error> {
    #[derive(Serialize)]
    struct Unsigned<'a> {
        schema: &'a str,
        profile: &'a str,
        model_sha256: &'a str,
        checker_sha256: &'a str,
        baseline_guard_sha256: &'a str,
        base_request: &'a Value,
        hypotheses: &'a [Hypothesis],
        facts: &'a [Fact],
        decisions: &'a [Decision],
        stop: &'a Option<String>,
        limits: &'a guard::Limits,
        final_request_sha256: &'a str,
        binding_sha256: &'static str,
    }
    digest(
        "ariadne.alignment-hypothesis-binding/v1",
        &Unsigned {
            schema: &report.schema,
            profile: &report.profile,
            model_sha256: &report.model_sha256,
            checker_sha256: &report.checker_sha256,
            baseline_guard_sha256: &report.baseline_guard_sha256,
            base_request: &report.base_request,
            hypotheses: &report.hypotheses,
            facts: &report.facts,
            decisions: &report.decisions,
            stop: &report.stop,
            limits: &report.limits,
            final_request_sha256: &report.final_request_sha256,
            binding_sha256: "",
        },
    )
}
pub fn analysis_id(report: &Report) -> Result<String, Error> {
    if report.schema != SCHEMA
        || report.profile != PROFILE
        || report.hypotheses.is_empty()
        || report.binding_sha256 != binding(report)?
    {
        return Err(invalid("alignment hypothesis report binding changed"));
    }
    digest(
        "ariadne.alignment-hypothesis-analysis/v1",
        &report.binding_sha256,
    )
}
pub fn base_request(report: &Report) -> Result<AnalysisRequest, Error> {
    crate::investigation::frame_paths::decode_guard_request(&report.base_request)
}
fn limits_within(producer: &guard::Limits, host: &guard::Limits) -> Result<(), Error> {
    producer.validate()?;
    host.validate()?;
    let producer = serde_json::to_value(producer)?;
    let host = serde_json::to_value(host)?;
    for (key, value) in producer.as_object().expect("limits object") {
        if value
            .as_u64()
            .ok_or_else(|| invalid("alignment hypothesis limit representation"))?
            > host[key]
                .as_u64()
                .ok_or_else(|| invalid("alignment hypothesis host limit representation"))?
        {
            return Err(invalid(
                "alignment hypothesis producer limits exceed trusted host",
            ));
        }
    }
    Ok(())
}
fn baseline_sources(
    base: &AnalysisRequest,
    baseline: &guard::Report,
    limits: &guard::Limits,
) -> Result<(), Error> {
    limits.validate()?;
    base.validate()?;
    if baseline.profile != guard::PROFILE
        || baseline.input.roots.len() != 1
        || baseline.input.snapshot != base.snapshot_id
        || base.input_kind != crate::InputKind::Dump
        || !base.file_backed.is_empty()
        || !base.trusted_fallback.is_empty()
        || baseline.input.sites.len() > limits.max_sites
    {
        return Err(invalid(
            "alignment hypothesis baseline scope or evidence limit",
        ));
    }
    evidence_limit(baseline, limits.max_evidence_bytes)?;
    let encoded = crate::bap::core_adapter::encode_request(base)?;
    evidence_limit(&encoded, limits.max_evidence_bytes)?;
    let roots: Vec<_> = base
        .entry_points
        .iter()
        .map(|site| format!("0x{site:016x}"))
        .collect();
    let seeds: Vec<_> = base
        .slice_seeds
        .iter()
        .map(|site| format!("0x{site:016x}"))
        .collect();
    if roots
        != baseline
            .input
            .roots
            .iter()
            .map(|root| root.site.clone())
            .collect::<Vec<_>>()
        || seeds != baseline.input.seeds
    {
        return Err(invalid("alignment hypothesis roots or slice seeds changed"));
    }
    guard::validate_final_request(&baseline.input, baseline, &json_hash(&encoded)?)?;
    Ok(())
}
struct Recognized<'a> {
    source: &'a guard::CandidateSite,
    pending: guard::PendingGuard,
    opcode: String,
    normal_ast: String,
    bytes: Vec<u8>,
}
fn recognized<'a>(
    baseline: &'a guard::Report,
    decoder: &BTreeMap<String, String>,
) -> Result<BTreeMap<String, Recognized<'a>>, Error> {
    let domain: BTreeSet<_> = baseline
        .input
        .sites
        .iter()
        .map(|source| source.site.as_str())
        .collect();
    if decoder.keys().any(|site| !domain.contains(site.as_str())) {
        return Err(invalid(
            "alignment hypothesis decoder receipt outside original source domain",
        ));
    }
    let mut out = BTreeMap::new();
    for source in &baseline.input.sites {
        let Some(pending) = guard::recognize_pending_for_input(&baseline.input, source)? else {
            continue;
        };
        let record = decoder
            .get(&source.site)
            .ok_or_else(|| invalid("alignment hypothesis guard decoder receipt absent"))?;
        let raw = crate::llvm_mc::protocol::parse(record)?;
        let address = crate::bap::core_adapter::address(&source.site)?;
        let bytes = crate::investigation::frame_unwind::unhex(&source.bytes_hex)?;
        let encoding = if matches!(bytes.first(), Some(0x40 | 0x44)) {
            &bytes[1..]
        } else {
            bytes.as_slice()
        };
        let expected_opcode = if encoding.get(1) == Some(&0x29) {
            "MOVAPSmr"
        } else {
            "MOVAPSrm"
        };
        if raw.decoded.address != address
            || raw.decoded.status != "ok"
            || raw.decoded.length != bytes.len() as u64
            || raw.decoded.kind != Some(InstructionKind::Ordinary)
            || raw.decoded.target.is_some()
            || raw.opcode != expected_opcode
        {
            return Err(invalid("alignment hypothesis guard decoded source changed"));
        }
        let original: Vec<super::ast::Stmt> = serde_json::from_str(&source.ast)?;
        // The authoritative recognizer above permits exactly this reviewed pair.
        let [normal, super::ast::Stmt::If { .. }] = original.as_slice() else {
            return Err(invalid(
                "alignment hypothesis guard statement shape changed",
            ));
        };
        let normal_ast = serde_json::to_string(&[normal])?;
        super::Backend::guard_normal_projection(&normal_ast, &raw.opcode, &bytes, address)?;
        out.insert(
            source.site.clone(),
            Recognized {
                source,
                pending,
                opcode: raw.opcode,
                normal_ast,
                bytes,
            },
        );
    }
    Ok(out)
}
fn make_hypotheses(
    baseline: &guard::Report,
    decoder: &BTreeMap<String, String>,
    selected: &[u64],
    sources: &BTreeMap<String, Recognized<'_>>,
) -> Result<Vec<Hypothesis>, Error> {
    if selected.is_empty() || selected.len() > baseline.input.sites.len() {
        return Err(invalid(
            "nonempty finite alignment hypothesis sites required",
        ));
    }
    let mut points = BTreeSet::new();
    let mut out = Vec::new();
    for point in selected {
        let name = format!("0x{point:016x}");
        if !points.insert(name.clone()) {
            return Err(invalid("duplicate alignment hypothesis site"));
        }
        let source = sources.get(&name).ok_or_else(|| {
            invalid("alignment hypothesis site is not a reviewed captured MOVAPS guard")
        })?;
        let residue = (0u64.wrapping_sub(source.pending.displacement as u64) & 15) as u32;
        let mut hypothesis = Hypothesis {
            id: String::new(),
            snapshot: baseline.input.snapshot.clone(),
            artifact_sha256: baseline.input.artifact_sha256.clone(),
            query_scope_sha256: baseline.input.query_scope_sha256.clone(),
            root: baseline.input.roots[0].site.clone(),
            activation: baseline.input.activation.clone(),
            point: name.clone(),
            bytes_hex: source.source.bytes_hex.clone(),
            original_ast_sha256: source.pending.original_ast_sha256.clone(),
            pending_relation_sha256: source.pending.pending_relation_sha256.clone(),
            displacement: source.pending.displacement,
            alignment: 16,
            rsp_residues: 1u16 << residue,
            decoder_record_sha256: crate::reports::sha256(decoder[&name].as_bytes()),
            candidate_epoch: baseline.input.candidate_epoch,
            policy: POLICY.into(),
        };
        hypothesis.id = digest("ariadne.alignment-hypothesis-premise/v1", &hypothesis)?;
        out.push(hypothesis);
    }
    out.sort_by(|a, b| a.point.cmp(&b.point));
    Ok(out)
}
fn edges(input: &guard::GuardInput) -> Vec<(String, String)> {
    let mut edges = Vec::new();
    for source in &input.sites {
        if matches!(
            source.control.kind,
            guard::ControlKind::Ordinary
                | guard::ControlKind::Conditional
                | guard::ControlKind::Call
        ) {
            edges.extend(
                source
                    .control
                    .fall
                    .iter()
                    .map(|target| (source.site.clone(), target.clone())),
            );
        }
        if matches!(
            source.control.kind,
            guard::ControlKind::Conditional
                | guard::ControlKind::Jump
                | guard::ControlKind::Indirect
        ) {
            edges.extend(
                source
                    .control
                    .targets
                    .iter()
                    .map(|target| (source.site.clone(), target.clone())),
            );
        }
    }
    edges
}
fn apply(relation: &[u16], values: u16) -> u16 {
    relation
        .iter()
        .enumerate()
        .fold(0, |out, (residue, after)| {
            if values & (1u16 << residue) != 0 {
                out | after
            } else {
                out
            }
        })
}
struct Closure {
    facts: Vec<Fact>,
    stop: Option<String>,
}
fn least_fixed_point(
    baseline: &guard::Report,
    hypotheses: &[Hypothesis],
    limits: &guard::Limits,
) -> Result<Closure, Error> {
    let stopped = |reason: &str| Closure {
        facts: Vec::new(),
        stop: Some(reason.into()),
    };
    if baseline.stop.is_some() {
        return Ok(stopped("baseline-guard-not-closed"));
    }
    if baseline.input.candidate_epoch >= limits.max_closure_rounds as u64 {
        return Ok(stopped("alignment-hypothesis-closure-round-limit"));
    }
    if limits.max_residue_updates == 0
        || limits.max_transfer_evaluations == 0
        || limits.max_elapsed_ms == 0
        || limits.max_closure_rounds == 0
    {
        return Ok(stopped("alignment-hypothesis-zero-work-budget"));
    }
    let mut edge_count = 0usize;
    for source in &baseline.input.sites {
        let fall = if matches!(
            source.control.kind,
            guard::ControlKind::Ordinary
                | guard::ControlKind::Conditional
                | guard::ControlKind::Call
        ) {
            source.control.fall.len()
        } else {
            0
        };
        let targets = if matches!(
            source.control.kind,
            guard::ControlKind::Conditional
                | guard::ControlKind::Jump
                | guard::ControlKind::Indirect
        ) {
            source.control.targets.len()
        } else {
            0
        };
        edge_count = edge_count
            .checked_add(fall)
            .and_then(|count| count.checked_add(targets))
            .ok_or_else(|| invalid("alignment hypothesis edge count overflow"))?;
        if edge_count > limits.max_edges {
            return Ok(stopped("alignment-hypothesis-edge-limit"));
        }
    }
    let graph = edges(&baseline.input);
    let mut facts: BTreeMap<String, u16> = baseline
        .input
        .sites
        .iter()
        .map(|site| (site.site.clone(), 0))
        .collect();
    let mut incoming = facts.clone();
    let masks: BTreeMap<_, _> = hypotheses
        .iter()
        .map(|hypothesis| (hypothesis.point.as_str(), hypothesis.rsp_residues))
        .collect();
    let relations: BTreeMap<_, _> = baseline
        .transfers
        .iter()
        .map(|transfer| (transfer.site.as_str(), transfer.relation.as_slice()))
        .collect();
    if relations.len() != facts.len() || relations.values().any(|relation| relation.len() != 16) {
        return Err(invalid("baseline transfer relation domain changed"));
    }
    let mut roots: BTreeMap<_, _> = baseline
        .input
        .roots
        .iter()
        .map(|root| (root.site.as_str(), guard::TOP))
        .collect();
    for premise in &baseline.input.premises {
        *roots
            .get_mut(premise.root.as_str())
            .ok_or_else(|| invalid("baseline root premise changed"))? &= premise.rsp_residues;
    }
    let mut pending = BTreeSet::new();
    let mut updates = 0usize;
    for (root, values) in roots {
        let eligible = values & masks.get(root).copied().unwrap_or(guard::TOP);
        updates = updates
            .checked_add(eligible.count_ones() as usize)
            .ok_or_else(|| invalid("alignment hypothesis update overflow"))?;
        if updates > limits.max_residue_updates {
            return Ok(stopped("alignment-hypothesis-residue-update-limit"));
        }
        *incoming
            .get_mut(root)
            .ok_or_else(|| invalid("baseline root outside source graph"))? |= values;
        *facts.get_mut(root).expect("root domain") |= eligible;
        if eligible != 0 {
            pending.insert(root.to_string());
        }
    }
    let mut successors: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for (source, target) in &graph {
        if !facts.contains_key(source) || !facts.contains_key(target) {
            return Err(invalid("closed baseline local edge outside source graph"));
        }
        successors
            .entry(source.as_str())
            .or_default()
            .push(target.as_str());
    }
    let started = Instant::now();
    let mut evaluations = 0usize;
    while let Some(site) = pending.pop_first() {
        if started.elapsed().as_millis() >= u128::from(limits.max_elapsed_ms) {
            return Ok(stopped("alignment-hypothesis-deadline-limit"));
        }
        let output = apply(relations[site.as_str()], facts[&site]);
        for target in successors.get(site.as_str()).into_iter().flatten() {
            if evaluations >= limits.max_transfer_evaluations {
                return Ok(stopped("alignment-hypothesis-transfer-evaluation-limit"));
            }
            evaluations = evaluations
                .checked_add(1)
                .ok_or_else(|| invalid("alignment hypothesis evaluation overflow"))?;
            *incoming.get_mut(*target).expect("edge domain") |= output;
            let eligible = output & masks.get(*target).copied().unwrap_or(guard::TOP);
            let fact = facts.get_mut(*target).expect("edge domain");
            let grown = eligible & !*fact;
            if grown != 0 {
                updates = updates
                    .checked_add(grown.count_ones() as usize)
                    .ok_or_else(|| invalid("alignment hypothesis update overflow"))?;
                if updates > limits.max_residue_updates {
                    return Ok(stopped("alignment-hypothesis-residue-update-limit"));
                }
                *fact |= eligible;
                pending.insert((*target).to_string());
            }
        }
    }
    Ok(Closure {
        facts: facts
            .into_iter()
            .map(|(site, residues)| Fact {
                incoming: incoming[&site],
                site,
                residues,
            })
            .collect(),
        stop: None,
    })
}
fn shift(values: u16, displacement: i64) -> u16 {
    (0..16).fold(0, |out, residue| {
        if values & (1u16 << residue) != 0 {
            out | (1u16 << ((residue as i64 + displacement).rem_euclid(16) as u32))
        } else {
            out
        }
    })
}
fn project(
    base: &AnalysisRequest,
    baseline: &guard::Report,
    sources: &BTreeMap<String, Recognized<'_>>,
    closure: &Closure,
) -> Result<(AnalysisRequest, Vec<Decision>), Error> {
    let facts: BTreeMap<_, _> = closure
        .facts
        .iter()
        .map(|fact| (fact.site.as_str(), fact.residues))
        .collect();
    let baseline_verdicts: BTreeMap<_, _> = baseline
        .guards
        .iter()
        .map(|decision| (decision.site.as_str(), decision.verdict))
        .collect();
    if baseline_verdicts.len() != baseline.guards.len()
        || (baseline.stop.is_none()
            && (baseline_verdicts.len() != sources.len()
                || sources
                    .keys()
                    .any(|site| !baseline_verdicts.contains_key(site.as_str()))))
    {
        return Err(invalid(
            "alignment hypothesis baseline guard decision domain changed",
        ));
    }
    let mut final_request = base.clone();
    let mut decisions = Vec::new();
    for (name, source) in sources {
        let baseline_verdict = baseline_verdicts
            .get(name.as_str())
            .copied()
            .unwrap_or(guard::Verdict::Unknown);
        let values = facts.get(name.as_str()).copied().unwrap_or(0);
        let addresses = shift(values, source.pending.displacement);
        let verdict = if closure.stop.is_some() {
            guard::Verdict::Unknown
        } else if values == 0 {
            guard::Verdict::Unreached
        } else if addresses == 1 {
            guard::Verdict::Aligned
        } else if addresses & 1 == 0 {
            guard::Verdict::Misaligned
        } else {
            guard::Verdict::Unknown
        };
        let basis = match verdict {
            guard::Verdict::Aligned if baseline_verdict == guard::Verdict::Aligned => Basis::Proved,
            guard::Verdict::Aligned => Basis::Assumed,
            guard::Verdict::Unreached => Basis::Unreachable,
            _ => Basis::Unknown,
        };
        let site = crate::bap::core_adapter::address(name)?;
        let normal_ast = if verdict == guard::Verdict::Aligned {
            let normal = super::Backend::guard_normal_projection(
                &source.normal_ast,
                &source.opcode,
                &source.bytes,
                site,
            )?;
            final_request.instructions.insert(site, normal.instruction);
            final_request.decodable.insert(site);
            Some(source.normal_ast.clone())
        } else {
            final_request.instructions.insert(
                site,
                Instruction {
                    kind: InstructionKind::Stop,
                    uses: base.locations.clone(),
                    may_defs: base.locations.clone(),
                    ..Instruction::default()
                },
            );
            final_request.decodable.remove(&site);
            None
        };
        decisions.push(Decision {
            site: name.clone(),
            baseline_verdict,
            verdict,
            basis,
            input_residues: values,
            address_residues: addresses,
            normal_ast,
        });
    }
    final_request.validate()?;
    Ok((final_request, decisions))
}

pub fn certify(
    base: &AnalysisRequest,
    baseline: &guard::Report,
    decoder: &BTreeMap<String, String>,
    sites: &[u64],
    limits: &guard::Limits,
) -> Result<(AnalysisRequest, Report), Error> {
    baseline_sources(base, baseline, limits)?;
    let sources = recognized(baseline, decoder)?;
    for source in sources.keys() {
        let address = crate::bap::core_adapter::address(source)?;
        if !base.captured.contains(&address) {
            return Err(invalid(
                "alignment hypothesis guard lacks normalized captured source",
            ));
        }
    }
    let hypotheses = make_hypotheses(baseline, decoder, sites, &sources)?;
    let closure = least_fixed_point(baseline, &hypotheses, limits)?;
    let (final_request, decisions) = project(base, baseline, &sources, &closure)?;
    let mut report = Report {
        schema: SCHEMA.into(),
        profile: PROFILE.into(),
        model_sha256: model_identity(),
        checker_sha256: checker_identity(),
        baseline_guard_sha256: digest("ariadne.alignment-hypothesis-baseline/v1", baseline)?,
        base_request: crate::bap::core_adapter::encode_request(base)?,
        hypotheses,
        facts: closure.facts,
        decisions,
        stop: closure.stop,
        limits: limits.clone(),
        final_request_sha256: json_hash(&crate::bap::core_adapter::encode_request(
            &final_request,
        )?)?,
        binding_sha256: String::new(),
    };
    report.binding_sha256 = binding(&report)?;
    evidence_limit(&report, limits.max_evidence_bytes)?;
    Ok((final_request, report))
}
pub fn validate(
    report: &Report,
    baseline: &guard::Report,
    decoder: &BTreeMap<String, String>,
    final_request: &AnalysisRequest,
    host: &guard::Limits,
) -> Result<(), Error> {
    limits_within(&report.limits, host)?;
    evidence_limit(report, host.max_evidence_bytes)?;
    if report.hypotheses.len() > host.max_sites
        || report.decisions.len() > host.max_sites
        || report.facts.len() > host.max_sites
    {
        return Err(invalid(
            "alignment hypothesis report cardinality exceeds trusted host",
        ));
    }
    if report.model_sha256 != model_identity()
        || report.checker_sha256 != checker_identity()
        || report.binding_sha256 != binding(report)?
    {
        return Err(invalid(
            "alignment hypothesis source identity or report limit",
        ));
    }
    let base = base_request(report)?;
    let sites = report
        .hypotheses
        .iter()
        .map(|hypothesis| crate::bap::core_adapter::address(&hypothesis.point))
        .collect::<Result<Vec<_>, _>>()?;
    let (expected_final, mut expected) = certify(&base, baseline, decoder, &sites, &report.limits)?;
    if report.stop.as_deref() == Some("alignment-hypothesis-deadline-limit") {
        // Clock observations are producer stop annotations. They authorize no
        // positive selection; replay still recomputes the bounded closure.
        let sources = recognized(baseline, decoder)?;
        let stopped = Closure {
            facts: Vec::new(),
            stop: report.stop.clone(),
        };
        let (stopped_final, decisions) = project(&base, baseline, &sources, &stopped)?;
        expected.facts.clear();
        expected.stop = report.stop.clone();
        expected.decisions = decisions;
        expected.final_request_sha256 =
            json_hash(&crate::bap::core_adapter::encode_request(&stopped_final)?)?;
        expected.binding_sha256 = binding(&expected)?;
        if expected != *report || stopped_final != *final_request {
            return Err(invalid("alignment hypothesis deadline report changed"));
        }
        return Ok(());
    }
    if expected != *report || expected_final != *final_request {
        return Err(invalid(
            "alignment hypothesis facts, selections, scope or final request changed",
        ));
    }
    Ok(())
}

#[cfg(test)]
#[path = "../../tests/bap/alignment_hypothesis.rs"]
mod tests;
