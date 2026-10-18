use crate::investigation::{Error, FramePathEdgeKind, FrameStructureLimits, invalid};
use serde::{Deserialize, Serialize};
pub const FRAME_QUESTION_SCHEMA: &str = "ariadne.frame-question/v1";
pub const FRAME_QUESTION_REQUEST_SCHEMA: &str = "ariadne.frame-question-request/v1";
pub(crate) const ALGORITHM: &str = "frame-question-bits-prefix-fair/v1";
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameQuestionLimits {
    pub structural: FrameStructureLimits,
    pub max_input_bytes: usize,
    pub max_output_bytes: usize,
    pub max_source_bytes: usize,
    pub max_proof_bytes: usize,
    pub max_tasks: usize,
    pub max_queue_bytes: usize,
    pub quantum: usize,
    pub resolver_work: u64,
    pub constraint_work: u64,
    pub numerical_work: u64,
    pub origin_work: u64,
    pub max_states: usize,
    pub max_values: usize,
    pub max_expression_nodes: usize,
    pub max_expression_depth: usize,
    pub max_candidates: usize,
    pub max_pair_checks: usize,
    pub max_proofs: usize,
    pub max_revisions: usize,
    pub max_core_links: usize,
    pub deadline_ms: u64,
    pub total_deadline_ms: u64,
}
impl Default for FrameQuestionLimits {
    fn default() -> Self {
        Self {
            structural: FrameStructureLimits::default(),
            max_input_bytes: 1024 * 1024 * 1024,
            max_output_bytes: 1024 * 1024 * 1024,
            max_source_bytes: 512 * 1024 * 1024,
            max_proof_bytes: 64 * 1024 * 1024,
            max_tasks: 8192,
            max_queue_bytes: 16 * 1024 * 1024,
            quantum: 256,
            resolver_work: 1_048_576,
            constraint_work: 1_048_576,
            numerical_work: 1_048_576,
            origin_work: 1_048_576,
            max_states: 65536,
            max_values: 256,
            max_expression_nodes: 8192,
            max_expression_depth: 64,
            max_candidates: 4096,
            max_pair_checks: 65536,
            max_proofs: 4096,
            max_revisions: 4,
            max_core_links: 2_000_000,
            deadline_ms: 10_000,
            total_deadline_ms: 30_000,
        }
    }
}
impl FrameQuestionLimits {
    pub fn validate(&self) -> Result<(), Error> {
        self.structural.validate()?;
        if self.quantum == 0 {
            return Err(invalid("question quantum must be positive"));
        }
        Ok(())
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QuestionMoment {
    Before,
    After,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionPoint {
    pub frame: usize,
    #[serde(with = "crate::investigation::model::va")]
    pub site: u64,
    pub moment: QuestionMoment,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ValueConstraint {
    pub point: QuestionPoint,
    pub bank: u8,
    pub width: u16,
    #[serde(with = "crate::investigation::model::va")]
    pub mask: u64,
    #[serde(with = "crate::investigation::model::va")]
    pub value: u64,
}
impl ValueConstraint {
    pub(crate) fn validate(&self) -> Result<(), Error> {
        if self.bank >= 16 || self.width != 64 || self.mask == 0 || self.value & !self.mask != 0 {
            return Err(invalid(
                "question requires canonical whole-GPR masked constraints",
            ));
        }
        Ok(())
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum FrameQuestionKind {
    Alternative {
        frame: usize,
        #[serde(with = "crate::investigation::model::va")]
        site: u64,
        #[serde(with = "crate::investigation::model::va")]
        destination: u64,
        edge_kind: FramePathEdgeKind,
        endpoint: ValueConstraint,
    },
    FaultDependency {
        frame: usize,
        #[serde(with = "crate::investigation::model::va")]
        site: u64,
        access: usize,
        #[serde(with = "crate::investigation::frame_unwind::optional_address")]
        load: Option<u64>,
        #[serde(with = "crate::investigation::frame_unwind::optional_address")]
        focus_writer: Option<u64>,
    },
}
impl FrameQuestionKind {
    pub fn frame(&self) -> usize {
        match self {
            Self::Alternative { frame, .. } | Self::FaultDependency { frame, .. } => *frame,
        }
    }
    pub fn site(&self) -> u64 {
        match self {
            Self::Alternative { site, .. } | Self::FaultDependency { site, .. } => *site,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameQuestion {
    pub question: FrameQuestionKind,
    #[serde(default)]
    pub conditions: Vec<ValueConstraint>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameQuestionRequest {
    pub schema: String,
    pub from_frame: usize,
    pub to_frame: usize,
    pub question: FrameQuestion,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QuestionVerdict {
    Unknown,
    RefutedUnderModel,
    PossibleUnderModel,
    PremiseConflict,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QuestionLayerStatus {
    Finished,
    WorkStopped,
    Unavailable,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionReceipt {
    pub status: QuestionLayerStatus,
    pub work: u64,
    pub elapsed_ms: u64,
    pub reason: Option<String>,
}
impl Default for QuestionReceipt {
    fn default() -> Self {
        Self {
            status: QuestionLayerStatus::Unavailable,
            work: 0,
            elapsed_ms: 0,
            reason: Some("not-applicable".into()),
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionLayers {
    pub frame_binding: QuestionReceipt,
    pub structural_recovery: QuestionReceipt,
    pub connections: QuestionReceipt,
    pub resolution: QuestionReceipt,
    pub feasibility: QuestionReceipt,
    pub values: QuestionReceipt,
    pub origins: QuestionReceipt,
    pub execution_evidence: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionObligation {
    pub frame: usize,
    #[serde(with = "crate::investigation::frame_unwind::optional_address")]
    pub site: Option<u64>,
    pub kind: String,
    pub requirement: String,
    pub band: usize,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionValue {
    pub point: QuestionPoint,
    pub bank: u8,
    pub value: crate::investigation::BackwardValue,
    pub classification: String,
    #[serde(with = "crate::investigation::frame_unwind::address_list")]
    pub context: Vec<u64>,
    pub reason: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionOrigin {
    #[serde(with = "crate::investigation::frame_unwind::optional_address")]
    pub load_site: Option<u64>,
    #[serde(with = "crate::investigation::frame_unwind::optional_address")]
    pub site: Option<u64>,
    pub kind: String,
    pub disposition: String,
    pub reason: String,
    pub pairs: Vec<crate::investigation::MemoryPair>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelWitness {
    pub frame: usize,
    #[serde(with = "crate::investigation::frame_unwind::address_list")]
    pub nodes: Vec<u64>,
    #[serde(with = "word_map")]
    pub initial_values: std::collections::BTreeMap<String, u64>,
    pub selected_edge_index: usize,
    pub profile: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionRevision {
    pub source_fingerprint: String,
    pub parent: Option<String>,
    pub changed_frames: Vec<usize>,
    pub invalidated_prior_conclusions: bool,
    pub conditional_on: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct QuestionResolution {
    pub frame: usize,
    pub source_fingerprint: String,
    pub report: crate::bap::target_resolution::Report,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameQuestionAssessment {
    pub algorithm: String,
    pub scope_id: String,
    pub elapsed_total_ms: u64,
    pub question: FrameQuestion,
    pub limits: FrameQuestionLimits,
    pub revisions: Vec<QuestionRevision>,
    pub conditional_on: Vec<String>,
    pub layers: QuestionLayers,
    pub resolution: Option<QuestionResolution>,
    pub verdict: QuestionVerdict,
    pub witness: Option<ModelWitness>,
    pub values: Vec<QuestionValue>,
    pub origins: Vec<QuestionOrigin>,
    pub candidate_count: Option<usize>,
    pub candidate_universe_sha256: Option<String>,
    pub obligations: Vec<QuestionObligation>,
    pub serviced_tasks: Vec<String>,
    pub premises: Vec<String>,
}

mod word_map {
    use serde::{Deserialize, Serialize};
    use std::collections::BTreeMap;
    #[derive(Serialize, Deserialize)]
    struct Word(#[serde(with = "crate::investigation::model::va")] u64);
    pub fn serialize<S: serde::Serializer>(
        v: &BTreeMap<String, u64>,
        s: S,
    ) -> Result<S::Ok, S::Error> {
        v.iter()
            .map(|(k, v)| (k.clone(), Word(*v)))
            .collect::<BTreeMap<_, _>>()
            .serialize(s)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(
        d: D,
    ) -> Result<BTreeMap<String, u64>, D::Error> {
        Ok(BTreeMap::<String, Word>::deserialize(d)?
            .into_iter()
            .map(|(k, v)| (k, v.0))
            .collect())
    }
}

impl FrameQuestionRequest {
    pub fn validate(&self, limits: &FrameQuestionLimits) -> Result<(), Error> {
        limits.validate()?;
        if self.schema != FRAME_QUESTION_REQUEST_SCHEMA
            || self.from_frame < self.to_frame
            || self.from_frame >= limits.structural.max_frames
        {
            return Err(invalid("invalid frame question schema/range"));
        }
        if self.question.conditions.len() > limits.max_proofs {
            return Err(invalid("question condition count cap"));
        }
        let mut points = self.question.conditions.iter().collect::<Vec<_>>();
        if let FrameQuestionKind::Alternative {
            endpoint,
            edge_kind,
            ..
        } = &self.question.question
        {
            if *edge_kind == FramePathEdgeKind::Call {
                return Err(invalid("call-context is not a local alternative"));
            }
            points.push(endpoint);
        }
        if self.question.question.frame() < self.to_frame
            || self.question.question.frame() > self.from_frame
        {
            return Err(invalid("question selector frame outside requested range"));
        }
        for c in points {
            c.validate()?;
            if c.point.frame < self.to_frame || c.point.frame > self.from_frame {
                return Err(invalid("question predicate frame outside requested range"));
            }
        }
        Ok(())
    }
}
