//! One bounded, source-owned investigator question above immutable frame maps.
mod alternative;
mod dependencies;
mod meter;
mod model;
mod resolution;
mod semantics;
use super::frame_connections::{digest, source_fingerprint};
use crate::investigation::{
    BoundFrameConnections, BoundFrameStructure, Error, FaultDatum, FaultMetadata,
    FrameConnectionAnalysis, invalid,
};
use crate::{AnalysisView, CompletedAnalysis};
use meter::{finished, unavailable};
pub use model::*;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::time::Instant;
enum Carrier {
    Structure(Box<BoundFrameStructure>),
    Connections(Box<BoundFrameConnections>),
}
/// Owns an existing validated source, without copying its proof dictionary.
pub struct FrameQuestionSource {
    carrier: Carrier,
}
impl From<BoundFrameStructure> for FrameQuestionSource {
    fn from(s: BoundFrameStructure) -> Self {
        Self {
            carrier: Carrier::Structure(Box::new(s)),
        }
    }
}
impl From<BoundFrameConnections> for FrameQuestionSource {
    fn from(s: BoundFrameConnections) -> Self {
        Self {
            carrier: Carrier::Connections(Box::new(s)),
        }
    }
}
impl FrameQuestionSource {
    pub fn structure(&self) -> &BoundFrameStructure {
        match &self.carrier {
            Carrier::Structure(s) => s,
            Carrier::Connections(s) => s.source(),
        }
    }
    pub fn connections(&self) -> Option<&FrameConnectionAnalysis> {
        match &self.carrier {
            Carrier::Structure(_) => None,
            Carrier::Connections(s) => Some(s.analysis()),
        }
    }
    pub(crate) fn publication(&self) -> Result<(String, String), Error> {
        match &self.carrier {
            Carrier::Structure(s) => Ok((
                "structure".into(),
                crate::reports::frame_structure::render_json(s)?,
            )),
            Carrier::Connections(s) => Ok((
                "connections".into(),
                crate::reports::frame_connections::render_json(s)?,
            )),
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct FaultEvidence {
    pub metadata: FaultMetadata,
    pub data: Vec<FaultDatum>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct FrameImport {
    pub frame: usize,
    pub request_sha256: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct QuestionRead {
    pub frame: usize,
    pub read: crate::bap::target_resolution::DataRead,
}
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct EvidenceData {
    pub fault: Option<FaultEvidence>,
    pub completed_frames: Vec<FrameImport>,
    pub control_reads: Vec<QuestionRead>,
}
/// The provider is crate-sealed and every returned source is admitted separately.
pub(crate) trait SourceProvider {
    fn read(
        &self,
        address: u64,
        length: usize,
    ) -> Result<crate::bap::target_resolution::DataRead, Error>;
    fn extend(
        &mut self,
        source: &BoundFrameStructure,
        question: &FrameQuestion,
        limits: &FrameQuestionLimits,
    ) -> Result<Option<BoundFrameStructure>, Error>;
}
#[derive(Default)]
pub struct FrameQuestionEvidence {
    pub(crate) data: EvidenceData,
    pub(crate) completed: BTreeMap<usize, CompletedAnalysis>,
    pub(crate) provider: Option<Box<dyn SourceProvider>>,
    pub(crate) supplied_revisions: Vec<BoundFrameStructure>,
}
impl FrameQuestionEvidence {
    pub fn with_revision(mut self, source: BoundFrameStructure) -> Self {
        self.supplied_revisions.push(source);
        self
    }

    /// The sealed AnalysisView implementation and exact original request bind reuse.
    pub fn with_completed_frame(
        mut self,
        source: &BoundFrameStructure,
        frame: usize,
        analysis: CompletedAnalysis,
    ) -> Result<Self, Error> {
        if frame < source.question().to_frame || frame > source.question().from_frame {
            return Err(invalid(
                "completed import outside selected activation range",
            ));
        }
        let expected = source
            .recoveries()
            .iter()
            .find(|(i, _)| *i == frame)
            .ok_or_else(|| invalid("completed import outside source"))?;
        if analysis.request() != expected.1.request()
            || analysis.state().phase != crate::Phase::Done
        {
            return Err(invalid("completed frame import query/state mismatch"));
        }
        if self.completed.contains_key(&frame) {
            return Err(invalid("duplicate completed frame import"));
        }
        self.data.completed_frames.push(FrameImport {
            frame,
            request_sha256: super::request_fingerprint(analysis.request()),
        });
        self.data.completed_frames.sort_by_key(|i| i.frame);
        self.completed.insert(frame, analysis);
        Ok(self)
    }
    pub(crate) fn validate(
        &self,
        source: &BoundFrameStructure,
        limits: &FrameQuestionLimits,
    ) -> Result<(), Error> {
        if self.data.completed_frames.len() > limits.structural.max_frames
            || serde_json::to_vec(&self.data)?.len() > limits.max_proof_bytes
        {
            return Err(invalid("question evidence input cap"));
        }
        if !self
            .data
            .completed_frames
            .windows(2)
            .all(|w| w[0].frame < w[1].frame)
        {
            return Err(invalid("question frame imports are not unique/canonical"));
        }
        for import in &self.data.completed_frames {
            if import.frame < source.question().to_frame
                || import.frame > source.question().from_frame
            {
                return Err(invalid(
                    "completed receipt outside selected activation range",
                ));
            }
            let r = source
                .recoveries()
                .iter()
                .find(|(i, _)| *i == import.frame)
                .ok_or_else(|| invalid("imported frame absent"))?;
            if super::request_fingerprint(r.1.request()) != import.request_sha256 {
                return Err(invalid("imported frame request binding changed"));
            }
            if let Some(a) = self.completed.get(&import.frame) {
                if a.request() != r.1.request() || a.state().phase != crate::Phase::Done {
                    return Err(invalid("imported frame state changed"));
                }
            }
        }
        if self.data.control_reads.len() > limits.max_tasks {
            return Err(invalid("question control-read count cap"));
        }
        for r in &self.data.control_reads {
            if r.frame < source.question().to_frame || r.frame > source.question().from_frame {
                return Err(invalid("control read outside selected activation range"));
            }
            crate::bap::target_resolution::validate_data_read(&r.read)?;
            for span in &r.read.spans {
                for c in &span.contributors {
                    if c.file_offset
                        .checked_add(span.length as u64)
                        .is_none_or(|n| n > source.chain().artifact_bytes() as u64)
                    {
                        return Err(invalid("question control contributor outside capture"));
                    }
                }
            }
        }
        if let Some(f) = &self.data.fault {
            super::fault_context::validate_context(&f.metadata, &f.data, true)?;
            if f.metadata.snapshot_id != source.chain().snapshot_id
                || f.metadata.artifact_sha256 != source.chain().artifact_sha256
                || f.metadata.artifact_bytes != source.chain().artifact_bytes() as u64
            {
                return Err(invalid("question fault witness belongs to another capture"));
            }
            let fields = super::fault_context::values(&f.data);
            if fields.get("thread_id").copied() != Some(u64::from(source.chain().thread_id))
                || fields.get("reg:rip").copied() != source.chain().frames.first().map(|f| f.pc)
            {
                return Err(invalid(
                    "question fault thread/context differs from captured activation",
                ));
            }
            if let Some(top) = source.chain().frames.first() {
                for (name, value) in &top.registers {
                    if let Some(observed) = fields.get(format!("reg:{name}").as_str()) {
                        if *observed != *value {
                            return Err(invalid("fault register differs from source observation"));
                        }
                    }
                }
            }
        }
        Ok(())
    }
}
pub struct BoundFrameQuestion {
    source: FrameQuestionSource,
    revisions: Vec<BoundFrameStructure>,
    evidence: EvidenceData,
    assessment: FrameQuestionAssessment,
}
impl BoundFrameQuestion {
    pub fn source(&self) -> &FrameQuestionSource {
        &self.source
    }
    pub fn revisions(&self) -> &[BoundFrameStructure] {
        &self.revisions
    }
    pub fn assessment(&self) -> &FrameQuestionAssessment {
        &self.assessment
    }
    pub(crate) fn evidence(&self) -> &EvidenceData {
        &self.evidence
    }
}
fn condition_conflict(source: &BoundFrameStructure, q: &FrameQuestion) -> bool {
    for (i, c) in q.conditions.iter().enumerate() {
        if q.conditions[..i].iter().any(|p| {
            p.point == c.point && p.bank == c.bank && ((p.value ^ c.value) & p.mask & c.mask) != 0
        }) {
            return true;
        }
        if c.point.frame == 0
            && c.point.moment == QuestionMoment::Before
            && let Some(top) = source.chain().frames.first()
            && c.point.site == top.pc
        {
            let name =
                crate::bap::target_resolution::question_semantics::bank_name(c.bank).to_lowercase();
            if top
                .register_evidence
                .get(&name)
                .is_some_and(|e| e.classification == super::Classification::Observed)
                && top
                    .registers
                    .get(&name)
                    .is_some_and(|value| value & c.mask != c.value)
            {
                return true;
            }
        }
    }
    false
}
fn validate_question(
    source: &BoundFrameStructure,
    q: &FrameQuestion,
    limits: &FrameQuestionLimits,
) -> Result<(), Error> {
    limits.validate()?;
    let frame = q.question.frame();
    let range = source.question();
    if frame < range.to_frame || frame > range.from_frame {
        return Err(invalid("question frame outside selected source range"));
    }
    if q.conditions.len() > limits.max_proofs {
        return Err(invalid("question condition count cap"));
    }
    let check_point = |point: &QuestionPoint| -> Result<(), Error> {
        if point.frame < range.to_frame || point.frame > range.from_frame {
            return Err(invalid("question point frame outside source"));
        }
        if let Some((_, r)) = source.recoveries().iter().find(|(i, _)| *i == point.frame) {
            if !r.request().addresses.contains(&point.site) {
                return Err(invalid("question selector is not an existing source site"));
            }
        }
        Ok(())
    };
    check_point(&QuestionPoint {
        frame,
        site: q.question.site(),
        moment: QuestionMoment::Before,
    })?;
    for c in &q.conditions {
        c.validate()?;
        check_point(&c.point)?;
    }
    if let FrameQuestionKind::Alternative {
        endpoint,
        edge_kind,
        ..
    } = &q.question
    {
        if *edge_kind == super::FramePathEdgeKind::Call {
            return Err(invalid("call-context is not a local alternative"));
        }
        endpoint.validate()?;
        check_point(&endpoint.point)?;
    }
    if let FrameQuestionKind::FaultDependency {
        load: Some(site), ..
    } = &q.question
    {
        check_point(&QuestionPoint {
            frame,
            site: *site,
            moment: QuestionMoment::Before,
        })?;
    }
    if let FrameQuestionKind::FaultDependency {
        site, access, load, ..
    } = &q.question
    {
        if let Some((_, r)) = source.recoveries().iter().find(|(i, _)| *i == frame) {
            if let Some(s) = r.context().sites.iter().find(|s| s.va == *site)
                && s.semantic_status.as_deref() == Some("projected")
                && s.accesses.get(*access).is_none()
            {
                return Err(invalid("selected fault access does not exist"));
            }
            if let Some(load) = load
                && let Some(s) = r.context().sites.iter().find(|s| s.va == *load)
                && s.semantic_status.as_deref() == Some("projected")
                && !s.accesses.iter().any(|a| a.role == super::AccessRole::Load)
            {
                return Err(invalid("selected dependency instruction is not a load"));
            }
        }
    }
    Ok(())
}
fn hypothesis_declarations(
    h: &[crate::bap::alignment_hypothesis::Hypothesis],
) -> Result<Vec<serde_json::Value>, Error> {
    let mut out = Vec::new();
    for item in h {
        let mut value = serde_json::to_value(item)?;
        for key in [
            "id",
            "query_scope_sha256",
            "pending_relation_sha256",
            "candidate_epoch",
        ] {
            value
                .as_object_mut()
                .expect("hypothesis object")
                .remove(key);
        }
        out.push(value);
    }
    Ok(out)
}
fn revision(
    parent: &BoundFrameStructure,
    next: &BoundFrameStructure,
    limits: &FrameQuestionLimits,
) -> Result<Vec<usize>, Error> {
    if parent.chain() != next.chain() || parent.question() != next.question() {
        return Err(invalid(
            "question source revision changed snapshot/activation/range",
        ));
    }
    let mut changed = Vec::new();
    for (frame, old) in parent.recoveries() {
        let new = next
            .recoveries()
            .iter()
            .find(|(i, _)| i == frame)
            .ok_or_else(|| invalid("source revision dropped frame"))?;
        if old.request().entry_points != new.1.request().entry_points {
            return Err(invalid("source revision changed recovery roots"));
        }
        for s in &old.context().sites {
            if let Some(n) = new.1.context().sites.iter().find(|n| n.va == s.va) {
                if s.captured
                    && (!n.captured
                        || s.bytes_hex != n.bytes_hex
                        || s.ast_sha256 != n.ast_sha256
                        || s.helper_sha256 != n.helper_sha256
                        || s.runtime_sha256 != n.runtime_sha256)
                {
                    return Err(invalid(
                        "revision common-site bytes/semantic provenance changed",
                    ));
                }
            } else {
                return Err(invalid("source revision dropped a prepared site"));
            }
        }
        if !old
            .recovery()
            .state()
            .decoded
            .is_subset(&new.1.recovery().state().decoded)
        {
            return Err(invalid("source revision regressed represented control"));
        }
        let old_h = old.alignment_hypotheses().map(|r| &r.hypotheses);
        let new_h = new.1.alignment_hypotheses().map(|r| &r.hypotheses);
        if old_h.is_some() != new_h.is_some() {
            return Err(invalid("source revision stripped conditional hypotheses"));
        }
        // Exact declaration validation is additional to regenerated proof IDs.
        if let (Some(a), Some(b)) = (old_h, new_h) {
            if hypothesis_declarations(a)? != hypothesis_declarations(b)? {
                return Err(invalid("source revision changed hypothesis declarations"));
            }
        }
        if old.request() != new.1.request() || old.recovery().state() != new.1.recovery().state() {
            changed.push(*frame);
        }
    }
    if next.frames().len() > limits.structural.max_frames {
        return Err(invalid("revision frame host cap"));
    }
    Ok(changed)
}
/// Zero limits remain actual stops. Every trusted result owns its immutable sources.
pub fn investigate_frame_question(
    source: impl Into<FrameQuestionSource>,
    question: FrameQuestion,
    mut evidence: FrameQuestionEvidence,
    limits: FrameQuestionLimits,
) -> Result<BoundFrameQuestion, Error> {
    let source = source.into();
    validate_question(source.structure(), &question, &limits)?;
    evidence.validate(source.structure(), &limits)?;
    let revisions = std::mem::take(&mut evidence.supplied_revisions);
    compute(source, revisions, question, &mut evidence, limits, None)
}
pub(crate) fn replay_question(
    source: FrameQuestionSource,
    revisions: Vec<BoundFrameStructure>,
    data: EvidenceData,
    expected: &FrameQuestionAssessment,
    host: &FrameQuestionLimits,
) -> Result<BoundFrameQuestion, Error> {
    validate_question(source.structure(), &expected.question, &expected.limits)?;
    let mut evidence = FrameQuestionEvidence {
        data,
        ..Default::default()
    };
    evidence.validate(source.structure(), host)?;
    // Reconstruct trusted completed imports from their exact original requests.
    for import in evidence
        .data
        .completed_frames
        .clone()
        .into_iter()
        .filter(|i| i.frame == expected.question.question.frame())
    {
        let r = source
            .structure()
            .recoveries()
            .iter()
            .find(|(i, _)| *i == import.frame)
            .ok_or_else(|| invalid("replay import absent"))?;
        let a = dependencies::complete_frame(r.1.request(), host, None, Instant::now())?
            .0
            .ok_or_else(|| invalid("verifier could not replay completed callee"))?;
        evidence.completed.insert(import.frame, a);
    }
    let result = compute(
        source,
        revisions,
        expected.question.clone(),
        &mut evidence,
        expected.limits.clone(),
        Some(expected),
    )?;
    if &result.assessment != expected {
        return Err(invalid(
            "frame question assessment differs from checked replay",
        ));
    }
    Ok(result)
}
fn compute(
    source: FrameQuestionSource,
    mut revisions: Vec<BoundFrameStructure>,
    question: FrameQuestion,
    evidence: &mut FrameQuestionEvidence,
    limits: FrameQuestionLimits,
    replay: Option<&FrameQuestionAssessment>,
) -> Result<BoundFrameQuestion, Error> {
    let selected = question.question.frame();
    evidence.completed.retain(|frame, _| *frame == selected);
    evidence
        .data
        .completed_frames
        .retain(|import| import.frame == selected);
    let total = Instant::now();
    let mut parent = source.structure();
    let mut revision_notes = Vec::new();
    let base_id = source_fingerprint(parent, limits.max_source_bytes)?;
    revision_notes.push(QuestionRevision {
        source_fingerprint: base_id,
        parent: None,
        changed_frames: Vec::new(),
        invalidated_prior_conclusions: false,
        conditional_on: parent.hypothesis_ids(),
    });
    if revisions.len() > limits.max_revisions {
        return Err(invalid("question source revision count cap"));
    }
    for next in &revisions {
        validate_question(next, &question, &limits)?;
        let changed = revision(parent, next, &limits)?;
        if changed.is_empty() {
            return Err(invalid("nonprogressive replay source revision"));
        }
        let parent_id = revision_notes
            .last()
            .expect("base revision")
            .source_fingerprint
            .clone();
        revision_notes.push(QuestionRevision {
            source_fingerprint: source_fingerprint(next, limits.max_source_bytes)?,
            parent: Some(parent_id),
            changed_frames: changed,
            invalidated_prior_conclusions: true,
            conditional_on: next.hypothesis_ids(),
        });
        parent = next;
    }
    if !revisions.is_empty() {
        evidence.completed.clear();
    }
    if replay.is_none() {
        for _ in revisions.len()..limits.max_revisions {
            let current = revisions.last().unwrap_or_else(|| source.structure());
            let Some(provider) = evidence.provider.as_mut() else {
                break;
            };
            let Some(next) = provider.extend(current, &question, &limits)? else {
                break;
            };
            let changed = revision(current, &next, &limits)?;
            if changed.is_empty() {
                break;
            }
            validate_question(&next, &question, &limits)?;
            let parent_id = revision_notes
                .last()
                .expect("base revision")
                .source_fingerprint
                .clone();
            revision_notes.push(QuestionRevision {
                source_fingerprint: source_fingerprint(&next, limits.max_source_bytes)?,
                parent: Some(parent_id),
                changed_frames: changed,
                invalidated_prior_conclusions: true,
                conditional_on: next.hypothesis_ids(),
            });
            revisions.push(next);
            evidence.completed.clear();
            if total.elapsed().as_millis() >= u128::from(limits.total_deadline_ms) {
                break;
            }
        }
    }
    let current = revisions.last().unwrap_or_else(|| source.structure());
    let frame = question.question.frame();
    let conditional_on = current.hypothesis_ids();
    let mut layers = QuestionLayers {
        frame_binding: finished(),
        structural_recovery: finished(),
        connections: unavailable("not-requested"),
        resolution: unavailable("no-resolver-work"),
        feasibility: unavailable("not-applicable"),
        values: unavailable("not-applicable"),
        origins: unavailable("not-applicable"),
        execution_evidence: "not_supplied".into(),
    };
    if current.links().iter().any(|l| !l.admitted)
        || current.chain().frames.len() <= current.question().from_frame
    {
        layers.frame_binding = unavailable("missing-or-ambiguous-frame-relations");
    }
    if current
        .frames()
        .iter()
        .any(|m| !m.auxiliary && !m.recovery_drained)
        || current.frames().is_empty()
    {
        layers.structural_recovery = unavailable("partial-structural-prefix");
    }
    if let Some(view) = source.connections() {
        layers.connections = QuestionReceipt {
            status: if revisions.is_empty()
                && view.graph_status == super::ConnectionLayerStatus::CompleteForRepresentedGraph
            {
                QuestionLayerStatus::Finished
            } else {
                QuestionLayerStatus::Unavailable
            },
            work: 0,
            elapsed_ms: 0,
            reason: if revisions.is_empty() {
                Some("inherited-independent-layers".into())
            } else {
                Some("source-revised-old-connections-preserved-as-context".into())
            },
        };
    }
    let mut obligations = Vec::new();
    for m in current.frames().iter().filter(|m| !m.auxiliary) {
        for gap in &m.gaps {
            obligations.push(QuestionObligation {frame:m.frame,site:Some(gap.site),kind:format!("source:{:?}",gap.kind),requirement:"Retain the original frontier; supply same-capture bytes, admitted semantics or checked coverage as applicable.".into(),band:2});
        }
    }
    let mut resolution_result = None;
    let mut verdict = QuestionVerdict::Unknown;
    let mut witness = None;
    let mut values = Vec::new();
    let mut origins = Vec::new();
    let mut candidate_count = None;
    let mut universe = None;
    let mut serviced = Vec::new();
    if condition_conflict(current, &question) {
        verdict = QuestionVerdict::PremiseConflict;
        layers.feasibility = finished();
        obligations.push(QuestionObligation {frame,site:Some(question.question.site()),kind:"premise-conflict".into(),requirement:"Reconcile incompatible point-specific premises with the captured observation; no exclusions follow from contradictory premises.".into(),band:0});
    } else if current.recoveries().iter().any(|(i, _)| *i == frame) {
        let sem = semantics::materialize(current, frame, &limits)?;
        let result = resolution::assess(
            current,
            &question,
            evidence,
            &sem,
            &limits,
            total,
            replay.map(|r| &r.layers.resolution),
        )?;
        layers.resolution = result.receipt;
        resolution_result = result.resolution;
        serviced.extend(result.serviced);
        obligations.extend(result.obligations);
        match &question.question {
            FrameQuestionKind::Alternative { .. } => {
                let result = alternative::assess(
                    current,
                    &question,
                    &sem,
                    &limits,
                    total,
                    replay.map(|r| &r.layers.feasibility),
                );
                verdict = result.verdict;
                witness = result.witness;
                layers.feasibility = result.receipt;
                serviced.extend(result.serviced);
                if let Some(reason) = result.reason {
                    obligations.push(QuestionObligation {frame,site:Some(question.question.site()),kind:reason,requirement:"Provide the named point-specific input, supported relation or complete incoming-control coverage; a path sample is insufficient.".into(),band:0});
                }
            }
            FrameQuestionKind::FaultDependency { .. } => {
                let result = dependencies::assess(
                    current, &question, evidence, &sem, &limits, total, replay,
                )?;
                layers.values = result.value_receipt;
                layers.origins = result.origin_receipt;
                values = result.values;
                origins = result.origins;
                candidate_count = result.candidate_count;
                universe = result.universe;
                serviced.extend(result.serviced);
                obligations.extend(result.obligations);
            }
        }
    } else {
        obligations.push(QuestionObligation {
            frame,
            site: Some(question.question.site()),
            kind: "missing-frame-recovery".into(),
            requirement: "An admitted structural map for the selected activation is required."
                .into(),
            band: 0,
        });
    }

    evidence.provider = None;
    let scope_id = digest(
        &(
            ALGORITHM,
            &revision_notes,
            &question,
            &evidence.data,
            &limits,
        ),
        limits.max_source_bytes,
    )?;
    let assessment=FrameQuestionAssessment {algorithm:ALGORITHM.into(),scope_id,elapsed_total_ms:replay.map_or_else(||u64::try_from(total.elapsed().as_millis()).unwrap_or(u64::MAX),|r|r.elapsed_total_ms),question,limits,revisions:revision_notes,conditional_on,layers,resolution:resolution_result,verdict,witness,values,origins,candidate_count,candidate_universe_sha256:universe,obligations,serviced_tasks:serviced,premises:vec!["All witnesses, refutations and exclusions are relative to the declared normal-flow scalar model and exact source revision.".into(),"Captured observations apply before the faulting instruction; earlier facts are derived under explicit producer/context premises.".into(),"Unknown frontiers, entry memory, opaque effects and external interference remain alternatives; examples do not establish writer coverage.".into(),"No execution recording, executed writer, iteration count, lifetime violation or root cause is established.".into()]};
    if serde_json::to_vec(&assessment)?.len() > assessment.limits.max_proof_bytes {
        return Err(invalid("question assessment proof byte cap"));
    }
    Ok(BoundFrameQuestion {
        source,
        revisions,
        evidence: evidence.data.clone(),
        assessment,
    })
}

#[cfg(all(test, feature = "input"))]
#[path = "../../tests/investigation/frame_question.rs"]
mod tests;
