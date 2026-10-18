use super::{
    FrameQuestionEvidence,
    meter::{Meter, unavailable},
    model::*,
    semantics::Semantics,
};
use crate::investigation::{
    BackwardValue, BoundFrameStructure, Error, FaultAddressQuestion, invalid,
};
use crate::{AnalysisRequest, AnalysisView, Analyzer, CompletedAnalysis};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::time::Instant;
pub(crate) struct DependencyResult {
    pub values: Vec<QuestionValue>,
    pub origins: Vec<QuestionOrigin>,
    pub candidate_count: Option<usize>,
    pub universe: Option<String>,
    pub value_receipt: QuestionReceipt,
    pub origin_receipt: QuestionReceipt,
    pub serviced: Vec<String>,
    pub obligations: Vec<QuestionObligation>,
}
pub(crate) fn complete_frame(
    request: &AnalysisRequest,
    limits: &FrameQuestionLimits,
    replay: Option<&QuestionReceipt>,
    total: Instant,
) -> Result<(Option<CompletedAnalysis>, QuestionReceipt), Error> {
    let mut meter = Meter::new(limits.origin_work, limits, total, replay);
    let mut a = Analyzer::new(request.clone())?;
    let mut stop = None;
    while a.state().phase != crate::Phase::Done {
        if let Err(r) = meter.tick() {
            stop = Some(r);
            break;
        }
        a.step();
        if meter.work % (limits.quantum as u64) == 0 {
            let count = a
                .state()
                .reaching
                .values()
                .try_fold(0usize, |n, s| n.checked_add(s.len()));
            if count.is_none_or(|n| n > limits.max_core_links) {
                stop = Some("callee-reaching-link-limit".into());
                break;
            }
        }
    }
    let result = if stop.is_none() {
        Some(CompletedAnalysis::from_analyzer(a))
    } else {
        None
    };
    Ok((result, meter.finish(stop)))
}
fn numerical(
    source: &BoundFrameStructure,
    q: &FrameQuestion,
    evidence: &FrameQuestionEvidence,
    sem: &Semantics,
    limits: &FrameQuestionLimits,
    total: Instant,
    replay: Option<&QuestionReceipt>,
) -> Result<(Vec<QuestionValue>, QuestionReceipt), Error> {
    let FrameQuestionKind::FaultDependency {
        frame,
        site,
        access,
        load,
        ..
    } = &q.question
    else {
        unreachable!()
    };
    let Some(fault) = &evidence.data.fault else {
        return Ok((Vec::new(), unavailable("fault-witness-unavailable")));
    };
    let r = &source
        .recoveries()
        .iter()
        .find(|(i, _)| i == frame)
        .ok_or_else(|| invalid("value frame absent"))?
        .1;
    let fields = super::super::fault_context::values(&fault.data);
    if *frame != 0
        || fields.get("thread_id").copied() != Some(u64::from(source.chain().thread_id))
        || fields.get("reg:rip").copied() != Some(*site)
    {
        return Ok((Vec::new(), unavailable("fault-thread-or-point-mismatch")));
    }
    let Some((rip, mut seeds)) = super::super::memory_refinement::frame_fault_seeds(
        r.request(),
        &r.context().sites,
        &fault.metadata,
        &fault.data,
        FaultAddressQuestion {
            site: *site,
            memory_access: *access,
        },
    ) else {
        return Ok((
            Vec::new(),
            unavailable("fault-access-seed-profile-unavailable"),
        ));
    };
    for s in r
        .context()
        .sites
        .iter()
        .filter(|s| load.is_none_or(|va| s.va == va))
    {
        for access in s
            .accesses
            .iter()
            .filter(|a| a.role == crate::investigation::AccessRole::Load)
        {
            if let Some(expr) = &access.expression {
                for term in &expr.terms {
                    let name = format!(
                        "reg:{}",
                        crate::bap::target_resolution::question_semantics::bank_name(term.bank)
                            .to_lowercase()
                    );
                    if let Some(&value) = fields.get(name.as_str()) {
                        seeds.insert(term.bank, value);
                    }
                }
            }
        }
    }
    let mut queue = VecDeque::new();
    let mut results = Vec::new();
    let mut meter = Meter::new(limits.numerical_work, limits, total, replay);
    let mut stop = None;
    for (bank, value) in seeds {
        queue.push_back((
            rip,
            bank,
            BackwardValue::Exact { width: 64, value },
            vec![rip],
        ));
    }
    let mut predecessors: BTreeMap<u64, BTreeSet<u64>> = BTreeMap::new();
    for e in &r.recovery().state().edges {
        if e.kind.is_local()
            && r.recovery().state().decoded.contains(&e.src)
            && r.recovery().state().decoded.contains(&e.dst)
        {
            predecessors.entry(e.dst).or_default().insert(e.src);
        }
    }
    let mut memo = BTreeSet::new();
    while let Some((here, bank, value, path)) = queue.pop_front() {
        if let Err(reason) = meter.tick() {
            stop = Some(reason);
            break;
        }
        if results.len() >= limits.max_proofs
            || queue.len() > limits.max_tasks
            || queue.len().saturating_mul(2048) > limits.max_queue_bytes
        {
            stop = Some("value-queue-or-proof-limit".into());
            break;
        }
        let key = super::digest(&(here, bank, &value, &path), limits.max_proof_bytes)?;
        if !memo.insert(key) {
            continue;
        }
        results.push(QuestionValue {
            point: QuestionPoint {
                frame: *frame,
                site: here,
                moment: QuestionMoment::Before,
            },
            bank,
            value: value.clone(),
            classification: if path.len() == 1 {
                "observed"
            } else {
                "derived_under_premises"
            }
            .into(),
            context: path.clone(),
            reason: None,
        });
        if path.len() >= limits.max_expression_depth {
            results.last_mut().expect("fact").reason = Some("value-prefix-depth-limit".into());
            stop = Some("value-prefix-depth-limit".into());
            continue;
        }
        let Some(preds) = predecessors.get(&here) else {
            results.last_mut().expect("fact").reason = Some("entry-or-unrecovered-prefix".into());
            continue;
        };
        for &pred in preds {
            if let Err(reason) = meter.tick() {
                stop = Some(reason);
                break;
            }
            if path.contains(&pred) {
                results.push(QuestionValue {
                    point: QuestionPoint {
                        frame: *frame,
                        site: pred,
                        moment: QuestionMoment::After,
                    },
                    bank,
                    value: value.clone(),
                    classification: "derived_under_premises".into(),
                    context: path.clone(),
                    reason: Some("cyclic-instance-scope".into()),
                });
                continue;
            }
            let mut context = path.clone();
            context.push(pred);
            let i = &r.request().instructions[&pred];
            let bytes = crate::effects::RegisterView::new(bank, 0, 64)
                .expect("GPR")
                .reads();
            let written = bytes.iter().any(|b| i.may_defs.contains(b));
            if !written {
                queue.push_back((pred, bank, value.clone(), context));
                continue;
            }
            results.push(QuestionValue {
                point: QuestionPoint {
                    frame: *frame,
                    site: pred,
                    moment: QuestionMoment::After,
                },
                bank,
                value: value.clone(),
                classification: "derived_under_premises".into(),
                context: context.clone(),
                reason: Some("selected-producer-postcondition".into()),
            });
            if !bytes.is_subset(&i.must_defs) {
                results.last_mut().expect("fact").reason =
                    Some("possible-or-partial-write-instance".into());
                continue;
            }
            if let Some(expr) = sem.receipts.get(&pred).and_then(|r| r.outputs.get(&bank)) {
                let (before, reason) = super::super::memory_refinement::inverse_expression(
                    &value,
                    expr,
                    bank,
                    0,
                    limits.max_expression_depth.min(limits.max_expression_nodes),
                )?;
                if let Some((next, v)) = before {
                    if let Some(reason) = reason {
                        results.push(QuestionValue {
                            point: QuestionPoint {
                                frame: *frame,
                                site: pred,
                                moment: QuestionMoment::Before,
                            },
                            bank: next,
                            value: v,
                            classification: "derived_under_premises".into(),
                            context,
                            reason: Some(reason),
                        });
                    } else {
                        queue.push_back((pred, next, v, context));
                    }
                } else {
                    results.last_mut().expect("producer fact").reason =
                        Some(reason.unwrap_or_else(|| "unsupported-inverse".into()));
                }
            } else {
                results.last_mut().expect("producer fact").reason =
                    Some("transfer-unavailable".into());
            }
        }
        if stop.is_some() {
            break;
        }
    }
    Ok((results, meter.finish(stop)))
}
pub(crate) fn assess(
    source: &BoundFrameStructure,
    q: &FrameQuestion,
    evidence: &mut FrameQuestionEvidence,
    sem: &Semantics,
    limits: &FrameQuestionLimits,
    total: Instant,
    replay: Option<&FrameQuestionAssessment>,
) -> Result<DependencyResult, Error> {
    let FrameQuestionKind::FaultDependency {
        frame,
        site,
        access,
        load,
        ..
    } = &q.question
    else {
        unreachable!()
    };
    let (values, value_receipt) = numerical(
        source,
        q,
        evidence,
        sem,
        limits,
        total,
        replay.map(|r| &r.layers.values),
    )?;
    let mut out=DependencyResult {values,origins:vec![QuestionOrigin {load_site:*load,site:None,kind:"external_interference".into(),disposition:"unresolved".into(),reason:"No original-interval synchronization or absence-of-interference evidence is supplied.".into(),pairs:Vec::new()}],candidate_count:None,universe:None,value_receipt,origin_receipt:unavailable("origin-collection-unavailable"),serviced:Vec::new(),obligations:Vec::new()};
    let r = &source
        .recoveries()
        .iter()
        .find(|(i, _)| i == frame)
        .ok_or_else(|| invalid("origin frame absent"))?
        .1;
    let (analysis, receipt) = if let Some(a) = evidence.completed.remove(frame) {
        if a.request() != r.request() || a.state().phase != crate::Phase::Done {
            return Err(invalid("completed callee import changed source request"));
        }
        (Some(a), super::meter::finished())
    } else {
        complete_frame(
            r.request(),
            limits,
            replay.map(|v| &v.layers.origins),
            total,
        )?
    };
    out.origin_receipt = receipt;
    let Some(analysis) = analysis else {
        out.obligations.push(QuestionObligation {frame:*frame,site:Some(*site),kind:"callee-completion-stopped".into(),requirement:"Supply an exact compatible completed callee or increase its independent action/link budget; full caller completion is unnecessary.".into(),band:1});
        return Ok(out);
    };
    if !analysis.state().decoded.contains(site) {
        out.origin_receipt = unavailable("fault-site-not-in-completed-local-graph");
        return Ok(out);
    }
    let mut meter = Meter::resume(
        limits.origin_work,
        out.origin_receipt.work,
        limits,
        total,
        replay.map(|r| &r.layers.origins),
    );
    let mut loads = BTreeSet::new();
    if let Some(load) = load {
        loads.insert(*load);
    } else {
        let sites: BTreeMap<_, _> = r.context().sites.iter().map(|s| (s.va, s)).collect();
        let selected = sites
            .get(site)
            .ok_or_else(|| invalid("fault site evidence absent"))?
            .accesses
            .get(*access)
            .ok_or_else(|| invalid("fault access index absent"))?;
        if selected.role == crate::investigation::AccessRole::Load {
            loads.insert(*site);
        }
        let mut pending: Vec<_> = selected
            .address_inputs
            .iter()
            .map(|loc| (*site, loc.clone()))
            .collect();
        let mut seen = BTreeSet::new();
        while let Some((point, loc)) = pending.pop() {
            if let Err(reason) = meter.tick() {
                out.origin_receipt = meter.finish(Some(reason));
                return Ok(out);
            }
            if !seen.insert((point, loc.clone())) {
                continue;
            }
            for d in analysis
                .state()
                .reaching
                .get(&point)
                .into_iter()
                .flatten()
                .filter(|d| d.loc == loc && d.origin == crate::DefinitionOrigin::Instruction)
            {
                if let Err(reason) = meter.tick() {
                    out.origin_receipt = meter.finish(Some(reason));
                    return Ok(out);
                }
                if sites.get(&d.site).is_some_and(|s| {
                    s.accesses
                        .iter()
                        .any(|a| a.role == crate::investigation::AccessRole::Load)
                }) {
                    loads.insert(d.site);
                } else if let Some(i) = r.request().instructions.get(&d.site) {
                    for used in &i.uses {
                        if used != "memory:any" {
                            pending.push((d.site, used.clone()));
                        }
                    }
                }
            }
            if seen.len() > limits.max_states
                || pending.len() > limits.max_tasks
                || pending.len().saturating_mul(256) > limits.max_queue_bytes
            {
                out.origin_receipt = meter.finish(Some("origin-dependency-queue-limit".into()));
                return Ok(out);
            }
        }
    }
    if loads.is_empty() {
        out.candidate_count = Some(0);
        out.universe = Some(super::digest(&Vec::<u64>::new(), limits.max_proof_bytes)?);
        out.origin_receipt = meter.finish(None);
        out.origin_receipt.reason = Some("no-admitted-load-producer".into());
        return Ok(out);
    }
    let mut bound =
        super::super::BoundInvestigation::new(&analysis, r.request(), r.context().clone())?;
    bound.guard_admission = r.proofs().guard.clone();
    bound.target_resolution = r.proofs().target.clone();
    bound.composition = r.proofs().composition.clone();
    let fault =
        evidence
            .data
            .fault
            .as_ref()
            .map(|f| super::super::fault_context::CapturedFaultContext {
                metadata: f.metadata.clone(),
                data: f.data.clone(),
            });
    let bound = super::super::BoundMemoryRefinement::new(bound, sem.receipts.clone(), fault)?;
    let mut total_candidates = 0usize;
    let mut originals = Vec::new();
    let mut pair_checks = 0usize;
    let mut stop = None;
    for load in loads {
        let Some(site) = r.context().sites.iter().find(|s| s.va == load) else {
            return Err(invalid("selected load evidence absent"));
        };
        let indices: Vec<_> = site
            .accesses
            .iter()
            .filter(|a| a.role == crate::investigation::AccessRole::Load)
            .map(|a| a.index)
            .collect();
        if indices.is_empty() {
            return Err(invalid(
                "selected dependency instruction has no admitted load",
            ));
        }
        let mut universe = Vec::new();
        for d in analysis
            .state()
            .reaching
            .get(&load)
            .into_iter()
            .flatten()
            .filter(|d| d.loc == "memory:any")
        {
            if let Err(reason) = meter.tick() {
                stop = Some(reason);
                break;
            }
            universe.push((d.site, d.origin));
        }
        if stop.is_some() {
            break;
        }
        for index in indices {
            total_candidates = total_candidates
                .checked_add(universe.len())
                .ok_or_else(|| invalid("origin count overflow"))?;
            originals.push((
                load,
                index,
                universe
                    .iter()
                    .map(|(va, origin)| (*va, *origin == crate::DefinitionOrigin::Entry))
                    .collect::<Vec<_>>(),
            ));
            if total_candidates > limits.max_candidates {
                stop = Some("complete-candidate-universe-exceeds-table-cap".into());
                continue;
            }
            // Reserve a conservative finite cost before invoking the existing all-instance checker.
            // A stopped refinement keeps every original candidate, with no new exclusion.
            let pairs = universe
                .iter()
                .map(|(va, _)| {
                    r.context()
                        .sites
                        .iter()
                        .find(|s| s.va == *va)
                        .map_or(0, |s| {
                            s.accesses
                                .iter()
                                .filter(|a| a.role == crate::investigation::AccessRole::Store)
                                .count()
                        })
                })
                .sum::<usize>();
            let permitted = pairs.min(limits.max_pair_checks.saturating_sub(pair_checks));
            let nodes = analysis.state().decoded.len();
            let unit = nodes
                .saturating_mul(nodes.saturating_add(1))
                .saturating_add(1);
            let cost = universe
                .len()
                .saturating_add(nodes)
                .saturating_add(permitted.saturating_mul(unit));
            let charged = meter.charge(u64::try_from(cost).unwrap_or(u64::MAX));
            if let Err(reason) = charged {
                stop = Some(reason);
                for (va, origin) in &universe {
                    out.origins.push(QuestionOrigin {
                        load_site: Some(load),
                        site: Some(*va),
                        kind: if *origin == crate::DefinitionOrigin::Entry {
                            "entry"
                        } else {
                            "instruction"
                        }
                        .into(),
                        disposition: "unresolved".into(),
                        reason: "origin-refinement-work-stopped".into(),
                        pairs: Vec::new(),
                    });
                }
                continue;
            }
            let assessment = super::super::assess_memory_origins(
                &bound,
                FaultAddressQuestion {
                    site: load,
                    memory_access: index,
                },
                super::super::MemoryRefinementLimits {
                    max_candidates: universe.len(),
                    max_pair_checks: permitted,
                    max_numerical_tasks: 0,
                    max_alternatives: 0,
                    max_expression_nodes: limits.max_expression_nodes,
                    max_expression_depth: limits.max_expression_depth,
                },
            )?;
            if !assessment.available {
                for (va, origin) in &universe {
                    out.origins.push(QuestionOrigin {
                        load_site: Some(load),
                        site: Some(*va),
                        kind: if *origin == crate::DefinitionOrigin::Entry {
                            "entry"
                        } else {
                            "instruction"
                        }
                        .into(),
                        disposition: "unresolved".into(),
                        reason: "unsupported-load-address-or-input-cap".into(),
                        pairs: Vec::new(),
                    });
                }
                continue;
            }
            for c in assessment.candidates {
                pair_checks = pair_checks.saturating_add(c.pairs.len());
                out.origins.push(QuestionOrigin {
                    load_site: Some(load),
                    site: Some(c.site),
                    kind: match c.origin {
                        crate::investigation::OriginKind::Entry => "entry",
                        crate::investigation::OriginKind::Instruction => "instruction",
                    }
                    .into(),
                    disposition: c.disposition,
                    reason: c.reason,
                    pairs: c.pairs,
                });
            }
            if assessment.gaps.iter().any(|s| s == "access-pair-budget") {
                stop = Some("writer-pair-budget".into());
            }
        }
    }
    if !matches!(
        stop.as_deref(),
        Some("work-limit" | "deadline" | "total-deadline")
    ) {
        out.candidate_count = Some(total_candidates);
        out.universe = Some(super::digest(&originals, limits.max_proof_bytes)?);
    } else if !originals.is_empty() {
        out.candidate_count = None;
    }
    out.origin_receipt = meter.finish(stop);
    if !r.recovery().state().obligations.is_empty() {
        out.origins.push(QuestionOrigin {load_site:*load,site:None,kind:"open_control_or_effects".into(),disposition:"unresolved".into(),reason:"Source recovery obligations can hide additional origins; no global writer coverage is claimed.".into(),pairs:Vec::new()});
    }
    if out.origins.len() > limits.max_candidates.saturating_add(2) {
        out.origins.retain(|o| o.site.is_none());
        out.origin_receipt = unavailable("candidate-table-cap");
    }
    Ok(out)
}
