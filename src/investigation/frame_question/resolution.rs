use super::{
    FrameQuestionEvidence, QuestionRead,
    meter::{Meter, unavailable},
    model::*,
    semantics::Semantics,
};
use crate::bap::target_resolution::{self as target, DataRead, QuestionTargetSchedule};
use crate::investigation::{BoundFrameStructure, Error, invalid};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;
pub(crate) struct ResolutionResult {
    pub resolution: Option<QuestionResolution>,
    pub receipt: QuestionReceipt,
    pub serviced: Vec<String>,
    pub obligations: Vec<QuestionObligation>,
}
pub(crate) fn assess(
    source: &BoundFrameStructure,
    q: &FrameQuestion,
    evidence: &mut FrameQuestionEvidence,
    sem: &Semantics,
    limits: &FrameQuestionLimits,
    total: Instant,
    replay: Option<&QuestionReceipt>,
) -> Result<ResolutionResult, Error> {
    let frame = q.question.frame();
    let r = &source
        .recoveries()
        .iter()
        .find(|(i, _)| *i == frame)
        .ok_or_else(|| invalid("resolution frame absent"))?
        .1;
    let request = if let Some(c) = &r.proofs().composition {
        crate::bap::composition::candidate_request(c)?
    } else {
        r.request().clone()
    };
    if !request
        .instructions
        .values()
        .any(|i| i.kind == crate::InstructionKind::Indirect)
    {
        return Ok(ResolutionResult {
            resolution: None,
            receipt: unavailable("no-indirect-dispatch"),
            serviced: Vec::new(),
            obligations: Vec::new(),
        });
    }
    let mut meter = Meter::new(limits.resolver_work, limits, total, replay);
    if let Err(reason) = meter.charge(0) {
        return Ok(ResolutionResult {
            resolution: None,
            receipt: meter.finish(Some(reason)),
            serviced: Vec::new(),
            obligations: Vec::new(),
        });
    }
    if limits.resolver_work == 0 {
        return Ok(ResolutionResult {
            resolution: None,
            receipt: meter.finish(Some("work-limit".into())),
            serviced: Vec::new(),
            obligations: Vec::new(),
        });
    }
    let mut policy = limits.structural.target.clone();
    policy.max_steps = usize::try_from(limits.resolver_work)
        .unwrap_or(usize::MAX)
        .min(policy.max_steps);
    policy.max_elapsed_ms = policy.max_elapsed_ms.min(limits.deadline_ms);
    let declared = policy.clone();
    if let Some(receipt) = replay {
        // The core checks deadlines only between deterministic prefix operations.
        policy.max_elapsed_ms = u64::MAX;
        if receipt.reason.as_deref() == Some("deadline")
            || receipt.reason.as_deref() == Some("total-deadline")
        {
            policy.max_steps = receipt.work as usize;
        }
    }
    let schedule = QuestionTargetSchedule {
        priority: BTreeSet::from([q.question.site()]),
        quantum: limits.quantum,
        deadline: if replay.is_some() {
            None
        } else {
            total.checked_add(std::time::Duration::from_millis(limits.total_deadline_ms))
        },
        work: std::cell::Cell::new(0),
        service: std::cell::RefCell::new(Vec::new()),
    };
    let mut reads: BTreeMap<(String, usize), DataRead> = r
        .proofs()
        .target
        .as_ref()
        .map(|t| {
            t.data_reads
                .iter()
                .cloned()
                .map(|r| ((r.address.clone(), r.requested), r))
                .collect()
        })
        .unwrap_or_default();
    for record in evidence
        .data
        .control_reads
        .iter()
        .filter(|v| v.frame == frame)
    {
        reads.insert(
            (record.read.address.clone(), record.read.requested),
            record.read.clone(),
        );
    }
    let start = Instant::now();
    let mut report = target::resolve_question(
        &source.chain().snapshot_id,
        &source.chain().artifact_sha256,
        &request.instructions,
        &request.entry_points,
        &sem.transfers,
        &policy,
        &schedule,
        |address, length| {
            let key = (format!("0x{address:016x}"), length);
            if let Some(read) = reads.get(&key) {
                return Ok(read.clone());
            }
            let read = if evidence.data.control_reads.len() >= limits.max_tasks {
                DataRead {
                    address: key.0.clone(),
                    requested: length,
                    bytes_hex: String::new(),
                    spans: Vec::new(),
                    conflict_sources: Vec::new(),
                    stop: "Hole".into(),
                }
            } else if let Some(provider) = evidence.provider.as_ref() {
                provider.read(address, length)?
            } else {
                DataRead {
                    address: key.0.clone(),
                    requested: length,
                    bytes_hex: String::new(),
                    spans: Vec::new(),
                    conflict_sources: Vec::new(),
                    stop: "Hole".into(),
                }
            };
            reads.insert(key, read.clone());
            if evidence.data.control_reads.len() < limits.max_tasks {
                evidence.data.control_reads.push(QuestionRead {
                    frame,
                    read: read.clone(),
                });
            }
            Ok(read)
        },
    )?;
    report.limits = declared;
    target::validate(&report, &request.instructions, &request.entry_points)?;
    meter.work = schedule.work.get() as u64;
    let stopped = report.resolutions.iter().any(|r| {
        r.unresolved
            .iter()
            .any(|s| s.contains("work-limit") || s.contains("frontier-limit"))
    });
    let stop = if let Some(r) = replay {
        r.reason
            .clone()
            .filter(|s| matches!(s.as_str(), "deadline" | "total-deadline" | "work-limit"))
    } else if stopped {
        Some(
            if total.elapsed().as_millis() >= u128::from(limits.total_deadline_ms) {
                "total-deadline"
            } else if start.elapsed().as_millis() >= u128::from(limits.deadline_ms) {
                "deadline"
            } else {
                "work-limit"
            }
            .into(),
        )
    } else {
        None
    };
    let mut obligations = Vec::new();
    for row in &report.resolutions {
        for reason in &row.unresolved {
            obligations.push(QuestionObligation {frame,site:Some(u64::from_str_radix(row.site.trim_start_matches("0x"),16)?),kind:reason.clone(),requirement:"Supply the missing same-capture control bytes, supported target expression, complete incoming coverage or independent resolver budget.".into(),band:if row.site==format!("0x{:016x}",q.question.site()){0}else{2}});
        }
    }
    let serviced = schedule
        .service
        .into_inner()
        .into_iter()
        .take(limits.max_proofs)
        .map(|s| format!("resolve:{frame}:0x{s:x}"))
        .collect();
    evidence.data.control_reads.sort_by(|a, b| {
        (a.frame, &a.read.address, a.read.requested).cmp(&(
            b.frame,
            &b.read.address,
            b.read.requested,
        ))
    });
    evidence.data.control_reads.dedup_by(|a, b| {
        a.frame == b.frame
            && a.read.address == b.read.address
            && a.read.requested == b.read.requested
    });
    Ok(ResolutionResult {
        resolution: Some(QuestionResolution {
            frame,
            source_fingerprint: super::source_fingerprint(source, limits.max_source_bytes)?,
            report,
        }),
        receipt: meter.finish(stop),
        serviced,
        obligations,
    })
}
