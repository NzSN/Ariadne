use super::{meter::Meter, model::*, semantics::Semantics};
use crate::bap::target_resolution::question_semantics::{Bits, Environment, bank_name};
use crate::bap::work_schedule::FairQueue;
use crate::investigation::{BoundFrameStructure, FramePathEdgeKind, FrameStructureGapKind};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::time::Instant;
pub(crate) struct AlternativeResult {
    pub verdict: QuestionVerdict,
    pub witness: Option<ModelWitness>,
    pub receipt: QuestionReceipt,
    pub serviced: Vec<String>,
    pub reason: Option<String>,
}
#[derive(Clone)]
struct Work {
    site: u64,
    selected: bool,
    env: Environment,
    path: Vec<u64>,
    edge_index: Option<usize>,
    inputs: BTreeMap<String, u64>,
    exact: bool,
}
fn facts(
    env: &mut Environment,
    conditions: &[ValueConstraint],
    frame: usize,
    site: u64,
    moment: QuestionMoment,
) -> bool {
    for c in conditions
        .iter()
        .filter(|c| c.point.frame == frame && c.point.site == site && c.point.moment == moment)
    {
        let name = bank_name(c.bank);
        let old = env.get(&name).copied().unwrap_or(Bits::top(64));
        let Some(value) = old.meet(c.mask, c.value) else {
            return false;
        };
        env.insert(name, value);
    }
    true
}
fn matches(env: &Environment, c: &ValueConstraint) -> bool {
    env.get(&bank_name(c.bank))
        .copied()
        .unwrap_or(Bits::top(64))
        .meet(c.mask, c.value)
        .is_some()
}
fn join(old: &mut Environment, new: &Environment) -> bool {
    let keys: BTreeSet<_> = old.keys().chain(new.keys()).cloned().collect();
    let before = old.clone();
    for key in keys {
        let width = old
            .get(&key)
            .or_else(|| new.get(&key))
            .expect("union key")
            .width;
        let a = old.get(&key).copied().unwrap_or(Bits::top(width));
        let b = new.get(&key).copied().unwrap_or(Bits::top(width));
        let n = a.join(b);
        if n.known == 0 {
            old.remove(&key);
        } else {
            old.insert(key, n);
        }
    }
    *old != before
}
pub(super) fn advance(
    env: &Environment,
    instruction: &crate::Instruction,
    transfer: Option<&crate::bap::target_resolution::Transfer>,
    meter: &mut Meter<'_>,
    limits: &FrameQuestionLimits,
) -> Result<(Environment, Option<bool>, Option<u64>, bool), String> {
    let mut left = meter.remaining().min(limits.max_expression_nodes as u64);
    let before = left;
    let condition = transfer
        .and_then(|t| t.question_condition(env, &mut left, limits.max_expression_depth))
        .and_then(Bits::number)
        .map(|n| n != 0);
    let target = transfer
        .and_then(|t| t.question_target(env, &mut left, limits.max_expression_depth))
        .and_then(Bits::number);
    let outputs =
        transfer.and_then(|t| t.question_outputs(env, &mut left, limits.max_expression_depth));
    meter.charge(before - left)?;
    if left == 0 {
        return Err("expression-work-limit".into());
    }
    let mut result = env.clone();
    let mut exact = outputs.is_some();
    for bank in 0..16 {
        let name = bank_name(bank);
        let bytes = crate::effects::RegisterView::new(bank, 0, 64)
            .expect("GPR")
            .reads();
        if bytes.iter().any(|b| instruction.may_defs.contains(b)) {
            let old = env.get(&name).copied().unwrap_or(Bits::top(64));
            let mut next = outputs
                .as_ref()
                .and_then(|o| o.get(&name))
                .copied()
                .filter(|v| v.width == 64)
                .unwrap_or(Bits::top(64));
            if !bytes.is_subset(&instruction.must_defs) {
                next = next.join(old);
            }
            if next.number().is_none() {
                exact = false;
            }
            result.insert(name, next);
        }
    }
    // Flags are transported only through explicit normalized definitions.
    for flag in ["CF", "ZF"] {
        result.remove(flag);
        if let Some(n) = outputs.as_ref().and_then(|v| v.get(flag)) {
            result.insert(flag.into(), *n);
        }
    }
    Ok((result, condition, target, exact))
}
fn acyclic(
    nodes: &BTreeSet<u64>,
    edges: &BTreeMap<u64, Vec<(u64, FramePathEdgeKind)>>,
    meter: &mut Meter<'_>,
) -> Result<bool, String> {
    let mut degree: BTreeMap<_, usize> = nodes.iter().map(|n| (*n, 0)).collect();
    for outgoing in edges.values() {
        for (dst, _) in outgoing {
            *degree.get_mut(dst).expect("represented target") += 1;
        }
    }
    let mut queue: VecDeque<_> = degree
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(n, _)| *n)
        .collect();
    let mut seen = 0;
    while let Some(node) = queue.pop_front() {
        meter.tick()?;
        seen += 1;
        for (dst, _) in edges.get(&node).into_iter().flatten() {
            let count = degree.get_mut(dst).expect("represented target");
            *count -= 1;
            if *count == 0 {
                queue.push_back(*dst);
            }
        }
    }
    Ok(seen == nodes.len())
}
pub(crate) fn assess(
    source: &BoundFrameStructure,
    q: &FrameQuestion,
    sem: &Semantics,
    limits: &FrameQuestionLimits,
    total: Instant,
    replay: Option<&QuestionReceipt>,
) -> AlternativeResult {
    let mut meter = Meter::new(limits.constraint_work, limits, total, replay);
    let mut serviced = Vec::new();
    let FrameQuestionKind::Alternative {
        frame,
        site,
        destination,
        edge_kind,
        endpoint,
    } = &q.question
    else {
        unreachable!()
    };
    let unavailable = |reason: &str| AlternativeResult {
        verdict: QuestionVerdict::Unknown,
        witness: None,
        receipt: super::meter::unavailable(reason),
        serviced: Vec::new(),
        reason: Some(reason.into()),
    };
    if *frame == 0
        && (endpoint.point.site == source.chain().frames[0].pc
            && endpoint.point.moment == QuestionMoment::After
            || q.conditions.iter().any(|c| {
                c.point.frame == 0
                    && c.point.site == source.chain().frames[0].pc
                    && c.point.moment == QuestionMoment::After
            }))
    {
        return unavailable("captured-point-normal-transfer-unavailable");
    }
    if endpoint.point.frame != *frame || q.conditions.iter().any(|c| c.point.frame != *frame) {
        return unavailable("cross-frame-value-relation-unavailable");
    }
    let Some(recovery) = source
        .recoveries()
        .iter()
        .find(|(i, _)| i == frame)
        .map(|(_, r)| r)
    else {
        return unavailable("missing-frame-recovery");
    };
    let Some(map) = source
        .frames()
        .iter()
        .find(|m| m.frame == *frame && !m.auxiliary)
    else {
        return unavailable("missing-frame-map");
    };
    if !recovery.recovery().state().decoded.contains(site) {
        return unavailable("selected-site-not-reached");
    }
    let root = map.entry;
    let mut conditions = q.conditions.clone();
    // Every observed GPR at the captured point constrains a concrete witness.
    if *frame == 0 {
        let captured = &source.chain().frames[0];
        for bank in 0..16 {
            let key = bank_name(bank).to_lowercase();
            if captured
                .register_evidence
                .get(&key)
                .is_some_and(|e| e.classification == crate::investigation::Classification::Observed)
                && let Some(&value) = captured.registers.get(&key)
            {
                for c in q.conditions.iter().filter(|c| {
                    c.point.site == captured.pc
                        && c.point.moment == QuestionMoment::Before
                        && c.bank == bank
                }) {
                    if value & c.mask != c.value {
                        return AlternativeResult {
                            verdict: QuestionVerdict::PremiseConflict,
                            witness: None,
                            receipt: meter.finish(None),
                            serviced,
                            reason: Some("condition-conflicts-with-observation".into()),
                        };
                    }
                }
                conditions.push(ValueConstraint {
                    point: QuestionPoint {
                        frame: *frame,
                        site: captured.pc,
                        moment: QuestionMoment::Before,
                    },
                    bank,
                    width: 64,
                    mask: u64::MAX,
                    value,
                });
            }
        }
    }
    for (i, c) in conditions.iter().enumerate() {
        if conditions[..i].iter().any(|p| {
            p.point == c.point && p.bank == c.bank && ((p.value ^ c.value) & p.mask & c.mask) != 0
        }) {
            return AlternativeResult {
                verdict: QuestionVerdict::PremiseConflict,
                witness: None,
                receipt: meter.finish(None),
                serviced,
                reason: Some("inconsistent-premises".into()),
            };
        }
    }
    if recovery.request().entry_points.len() != 1 {
        return unavailable("multiple-local-roots-unavailable");
    }
    let graph_cost = map
        .nodes
        .len()
        .saturating_add(map.edges.len())
        .saturating_add(map.gaps.len());
    if let Err(reason) = meter.charge(graph_cost as u64) {
        return AlternativeResult {
            verdict: QuestionVerdict::Unknown,
            witness: None,
            receipt: meter.finish(Some(reason.clone())),
            serviced,
            reason: Some(reason),
        };
    }
    let activation = &source.chain().frames[*frame];
    let nodes: BTreeSet<_> = map
        .nodes
        .iter()
        .filter(|s| {
            activation.function_begin.is_none_or(|b| s.va >= b)
                && activation.function_end.is_none_or(|e| {
                    u128::from(s.va) + (s.bytes_hex.len() / 2) as u128 <= u128::from(e)
                })
        })
        .map(|s| s.va)
        .collect();
    let mut edges: BTreeMap<u64, Vec<(u64, FramePathEdgeKind)>> = BTreeMap::new();
    let mut closed = map.recovery_drained;
    for e in &map.edges {
        if e.kind != FramePathEdgeKind::Call {
            if nodes.contains(&e.src.site) && nodes.contains(&e.dst.site) {
                edges
                    .entry(e.src.site)
                    .or_default()
                    .push((e.dst.site, e.kind));
            } else {
                closed = false;
            }
        }
    }
    for e in edges.values_mut() {
        e.sort();
        e.dedup();
    }
    if map.gaps.iter().any(|g| {
        matches!(
            g.kind,
            FrameStructureGapKind::PendingLocalWork
                | FrameStructureGapKind::DecodeFailed
                | FrameStructureGapKind::UnavailableBytes
                | FrameStructureGapKind::UnknownIndirectTarget
                | FrameStructureGapKind::OutsideFunction
                | FrameStructureGapKind::UnresolvedGuard
        )
    }) {
        closed = false;
    }
    let cyclic = match acyclic(&nodes, &edges, &mut meter) {
        Ok(covered) => {
            closed &= covered;
            !covered
        }
        Err(reason) => {
            return AlternativeResult {
                verdict: QuestionVerdict::Unknown,
                witness: None,
                receipt: meter.finish(Some(reason.clone())),
                serviced,
                reason: Some(reason),
            };
        }
    };
    let mut initial = Environment::new();
    if let Some(guard) = &recovery.proofs().guard {
        for p in &guard.input.premises {
            if p.point == format!("0x{root:016x}") {
                let mut possibilities =
                    (0..16)
                        .filter(|n| p.rsp_residues & (1 << n) != 0)
                        .map(|n| Bits {
                            width: 64,
                            known: 15,
                            value: n,
                        });
                if let Some(first) = possibilities.next() {
                    initial.insert("RSP".into(), possibilities.fold(first, Bits::join));
                }
            }
        }
    }
    if !facts(
        &mut initial,
        &conditions,
        *frame,
        root,
        QuestionMoment::Before,
    ) {
        return AlternativeResult {
            verdict: QuestionVerdict::PremiseConflict,
            witness: None,
            receipt: meter.finish(None),
            serviced,
            reason: Some("root-condition-conflicts-with-ABI-premise".into()),
        };
    }
    // A query predicate can be transported to the root only with complete
    // no-write coverage over every represented predecessor of that point.
    let mut incoming: BTreeMap<u64, Vec<u64>> = BTreeMap::new();
    for (src, outgoing) in &edges {
        for (dst, _) in outgoing {
            incoming.entry(*dst).or_default().push(*src);
        }
    }
    let mut prefix = BTreeSet::new();
    let mut pending = vec![endpoint.point.site];
    while let Some(dst) = pending.pop() {
        if prefix.insert(dst) {
            if let Err(reason) = meter.tick() {
                return AlternativeResult {
                    verdict: QuestionVerdict::Unknown,
                    witness: None,
                    receipt: meter.finish(Some(reason.clone())),
                    serviced,
                    reason: Some(reason),
                };
            }
            pending.extend(incoming.get(&dst).into_iter().flatten().copied());
        }
    }
    let bytes = crate::effects::RegisterView::new(endpoint.bank, 0, 64)
        .expect("GPR")
        .reads();
    let preserved = prefix.contains(&root)
        && prefix.iter().all(|va| {
            if *va == endpoint.point.site && endpoint.point.moment == QuestionMoment::Before {
                true
            } else {
                recovery
                    .request()
                    .instructions
                    .get(va)
                    .is_some_and(|i| bytes.is_disjoint(&i.may_defs))
            }
        });
    if preserved {
        let name = bank_name(endpoint.bank);
        let old = initial.get(&name).copied().unwrap_or(Bits::top(64));
        if let Some(value) = old.meet(endpoint.mask, endpoint.value) {
            initial.insert(name, value);
        } else {
            return AlternativeResult {
                verdict: if closed {
                    QuestionVerdict::RefutedUnderModel
                } else {
                    QuestionVerdict::Unknown
                },
                witness: None,
                receipt: meter.finish(None),
                serviced,
                reason: if closed {
                    None
                } else {
                    Some("incomplete-control-coverage".into())
                },
            };
        }
    }
    if limits.max_tasks == 0 || limits.max_queue_bytes < 2048 {
        return AlternativeResult {
            verdict: QuestionVerdict::Unknown,
            witness: None,
            receipt: meter.finish(Some("question-queue-limit".into())),
            serviced,
            reason: Some("question-queue-limit".into()),
        };
    }
    let mut queue = FairQueue::default();
    let mut abstract_states: BTreeMap<(u64, bool), Environment> = BTreeMap::new();
    queue.push(
        0,
        Work {
            site: root,
            selected: false,
            env: initial.clone(),
            path: Vec::new(),
            edge_index: None,
            inputs: BTreeMap::new(),
            exact: false,
        },
    );
    abstract_states.insert((root, false), initial.clone());
    let mut choices = BTreeSet::from([0u64, 1, 2, 8, u64::MAX]);
    choices.insert(endpoint.value);
    for c in &conditions {
        choices.insert(c.value);
    }
    for value in choices.into_iter().take(limits.max_values) {
        let mut env = Environment::new();
        for b in 0..16 {
            let n = bank_name(b);
            let selected = initial.get(&n).copied().unwrap_or(Bits::top(64));
            let v = (value & !selected.known) | selected.value;
            env.insert(n, Bits::exact(64, v));
        }
        env.insert("CF".into(), Bits::exact(1, 0));
        env.insert("ZF".into(), Bits::exact(1, 0));
        if !facts(&mut env, &conditions, *frame, root, QuestionMoment::Before) {
            continue;
        }
        let inputs = env
            .iter()
            .filter_map(|(n, v)| v.number().map(|v| (n.clone(), v)))
            .collect();
        queue.push(
            1,
            Work {
                site: root,
                selected: false,
                env,
                path: Vec::new(),
                edge_index: None,
                inputs,
                exact: !source.is_conditional(),
            },
        );
    }
    let mut capture_boundary = false;
    let mut abstract_endpoint = false;
    let mut witness = None;
    let mut stop = None;
    let mut states = 0usize;
    while let Some((band, mut task)) = queue.pop() {
        if let Err(r) = meter.tick() {
            stop = Some(r);
            break;
        }
        states += 1;
        if states > limits.max_states
            || queue.len() > limits.max_tasks
            || queue.len().saturating_mul(2048) > limits.max_queue_bytes
        {
            stop = Some("state-or-queue-limit".into());
            break;
        }
        if serviced.len() < limits.max_proofs {
            serviced.push(format!("{band}:0x{:x}", task.site));
        }
        if task.path.contains(&task.site) {
            closed = false;
            continue;
        }
        if task.path.len() >= limits.max_expression_depth {
            if band == 0 {
                stop = Some("path-depth-limit".into());
            }
            continue;
        }
        if !facts(
            &mut task.env,
            &conditions,
            *frame,
            task.site,
            QuestionMoment::Before,
        ) {
            continue;
        }
        task.path.push(task.site);
        let endpoint_here =
            task.site == endpoint.point.site && endpoint.point.moment == QuestionMoment::Before;
        if endpoint_here && task.selected && matches(&task.env, endpoint) {
            if band == 0 {
                abstract_endpoint = true;
            } else if conditions.iter().all(|c| {
                task.path.contains(&c.point.site)
                    && (c.point.site != task.site || c.point.moment == QuestionMoment::Before)
            }) && task.exact
                && task.env.get(&bank_name(endpoint.bank)).is_some_and(|v| {
                    v.number()
                        .is_some_and(|n| n & endpoint.mask == endpoint.value)
                })
            {
                witness = Some(ModelWitness {
                    frame: *frame,
                    nodes: task.path.clone(),
                    initial_values: task.inputs.clone(),
                    selected_edge_index: task.edge_index.expect("selected edge"),
                    profile: "normal-flow-GPR-bit-projection/v1".into(),
                });
            }
        }
        if witness.is_some() {
            break;
        }
        if *frame == 0 && task.site == source.chain().frames[0].pc {
            capture_boundary = true;
            closed = false;
            continue;
        }
        let Some(instruction) = recovery.request().instructions.get(&task.site) else {
            closed = false;
            continue;
        };
        let (mut after, condition, target, exact) = match advance(
            &task.env,
            instruction,
            sem.transfers.get(&task.site),
            &mut meter,
            limits,
        ) {
            Ok(v) => v,
            Err(r) => {
                stop = Some(r);
                break;
            }
        };
        task.exact &= exact;
        if !facts(
            &mut after,
            &conditions,
            *frame,
            task.site,
            QuestionMoment::After,
        ) {
            continue;
        }
        if task.site == endpoint.point.site
            && endpoint.point.moment == QuestionMoment::After
            && task.selected
            && matches(&after, endpoint)
        {
            if band == 0 {
                abstract_endpoint = true;
            } else if conditions.iter().all(|c| task.path.contains(&c.point.site))
                && task.exact
                && after.get(&bank_name(endpoint.bank)).is_some_and(|v| {
                    v.number()
                        .is_some_and(|n| n & endpoint.mask == endpoint.value)
                })
            {
                witness = Some(ModelWitness {
                    frame: *frame,
                    nodes: task.path.clone(),
                    initial_values: task.inputs.clone(),
                    selected_edge_index: task.edge_index.expect("selected edge"),
                    profile: "normal-flow-GPR-bit-projection/v1".into(),
                });
                break;
            }
        }
        for &(dst, kind) in edges.get(&task.site).into_iter().flatten() {
            if task.path.contains(&dst) {
                closed = false;
                continue;
            }
            if kind == FramePathEdgeKind::Indirect {
                if let Some(target) = target {
                    if dst != target {
                        continue;
                    }
                } else if band == 1 {
                    continue;
                }
            }
            if matches!(
                kind,
                FramePathEdgeKind::Taken | FramePathEdgeKind::Fallthrough
            ) {
                if let Some(c) = condition {
                    if c != (kind == FramePathEdgeKind::Taken) {
                        continue;
                    }
                } else if band == 1 {
                    continue;
                }
            }
            let selected =
                task.selected || (task.site == *site && dst == *destination && kind == *edge_kind);
            let edge_index = if !task.selected && selected {
                Some(task.path.len() - 1)
            } else {
                task.edge_index
            };
            if band == 0 {
                if let Some(old) = abstract_states.get_mut(&(dst, selected)) {
                    if !join(old, &after) {
                        continue;
                    }
                } else {
                    abstract_states.insert((dst, selected), after.clone());
                }
            } else if task.path.contains(&dst) {
                continue;
            }
            queue.push(
                band,
                Work {
                    site: dst,
                    selected,
                    env: if band == 0 {
                        abstract_states[&(dst, selected)].clone()
                    } else {
                        after.clone()
                    },
                    path: task.path.clone(),
                    edge_index,
                    inputs: task.inputs.clone(),
                    exact: task.exact,
                },
            );
        }
    }
    let verdict = if witness.is_some() {
        QuestionVerdict::PossibleUnderModel
    } else if stop.is_none() && closed && !abstract_endpoint {
        QuestionVerdict::RefutedUnderModel
    } else {
        QuestionVerdict::Unknown
    };
    let reason = if verdict == QuestionVerdict::Unknown {
        Some(
            if stop.is_some() {
                "question-work-stopped"
            } else if capture_boundary {
                "captured-point-normal-transfer-unavailable"
            } else if cyclic {
                "cyclic-value-coverage-unavailable"
            } else if !closed {
                "incomplete-control-coverage"
            } else {
                "no-coherent-model-witness"
            }
            .into(),
        )
    } else {
        None
    };
    AlternativeResult {
        verdict,
        witness,
        receipt: meter.finish(stop),
        serviced,
        reason,
    }
}
