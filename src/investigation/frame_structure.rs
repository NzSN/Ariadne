//! Evidence-bound recovery prefixes. These values never represent completed dataflow.
use super::frame_unwind::FrameTransition;
use super::{
    CapturedFrameChain, Error, EvidenceContext, FramePathEdgeKind, FramePathNode, Identity,
    SiteEvidence, invalid,
};
use crate::recovery::{RecoveryLimits, RecoveryResult};
use crate::{AnalysisRequest, EdgeKind, InstructionKind};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FRAME_STRUCTURE_SCHEMA: &str = "ariadne.frame-structure/v1";
pub const FRAME_STRUCTURE_PRODUCER: &str = "rust-recovery/v1";
pub const CONDITIONAL_FRAME_STRUCTURE_SCHEMA: &str = "ariadne.frame-structure/v2";
pub const CONDITIONAL_FRAME_STRUCTURE_PRODUCER: &str = "rust-recovery-alignment-hypotheses/v1";

/// Independent finite policies. Zero budgets reject work or produce a zero-Visit prefix.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureLimits {
    pub max_input_bytes: usize,
    pub max_output_bytes: usize,
    pub max_owned_bytes: usize,
    pub max_proof_bytes: usize,
    pub max_replay_visits: usize,
    pub max_replay_work: usize,
    pub max_dictionary_entries: usize,
    pub max_dictionary_depth: usize,
    pub max_frames: usize,
    pub max_graph_nodes: usize,
    pub max_graph_edges: usize,
    pub max_runtime_entries: usize,
    pub max_unwind_read_bytes: usize,
    pub max_stack_adjustment: u64,
    pub max_file_bytes: usize,
    pub max_metadata_bytes: usize,
    pub max_streams: usize,
    pub max_records: usize,
    pub max_overlap: usize,
    pub max_capture_ranges: usize,
    pub max_read_bytes: usize,
    pub max_prepare_starts: usize,
    pub max_prepare_candidates: usize,
    pub max_prepare_prefix_bytes: usize,
    pub max_prepare_decoder_batches: usize,
    pub prepare_batch_size: usize,
    pub recovery_max_visits: usize,
    pub recovery_deadline_ms: u64,
    pub guard: crate::bap::guard_admission::Limits,
    pub target: crate::bap::target_resolution::Limits,
}
impl Default for FrameStructureLimits {
    fn default() -> Self {
        Self {
            max_input_bytes: 512 * 1024 * 1024,
            max_output_bytes: 512 * 1024 * 1024,
            max_owned_bytes: 256 * 1024 * 1024,
            max_proof_bytes: 256 * 1024 * 1024,
            max_replay_visits: 1_000_000,
            max_replay_work: 16_000_000,
            max_dictionary_entries: 2_000_000,
            max_dictionary_depth: 256,
            max_frames: 128,
            max_graph_nodes: 65_536,
            max_graph_edges: 262_144,
            max_runtime_entries: 1_048_576,
            max_unwind_read_bytes: 16 * 1024 * 1024,
            max_stack_adjustment: 16 * 1024 * 1024,
            max_file_bytes: 8 * 1024 * 1024 * 1024,
            max_metadata_bytes: 64 * 1024 * 1024,
            max_streams: 1024,
            max_records: 131_072,
            max_overlap: 128,
            max_capture_ranges: 262_144,
            max_read_bytes: 16 * 1024 * 1024,
            max_prepare_starts: 65_536,
            max_prepare_candidates: 131_072,
            max_prepare_prefix_bytes: 1024 * 1024,
            max_prepare_decoder_batches: 65_536,
            prepare_batch_size: 128,
            recovery_max_visits: 65_536,
            recovery_deadline_ms: 60_000,
            guard: crate::bap::guard_admission::Limits {
                max_sites: 65_536,
                max_edges: 262_144,
                max_evidence_bytes: 256 * 1024 * 1024,
                max_residue_updates: 4_194_304,
                max_transfer_evaluations: 67_108_864,
                max_closure_rounds: 32_768,
                max_elapsed_ms: 120_000,
            },
            target: crate::bap::target_resolution::Limits {
                max_entries: 65_536,
                max_evidence_bytes: 256 * 1024 * 1024,
                max_values: 4096,
                max_steps: 2_097_152,
                max_path_steps: 512,
                max_rounds: 64,
                max_elapsed_ms: 120_000,
                max_targets: 65_536,
                max_read_bytes: 16 * 1024 * 1024,
            },
        }
    }
}
impl FrameStructureLimits {
    pub fn validate(&self) -> Result<(), Error> {
        self.guard.validate()?;
        self.target.validate()?;
        if self.prepare_batch_size == 0 {
            return Err(invalid(
                "structural preparation batch size must be positive",
            ));
        }
        Ok(())
    }
    pub fn recovery_limits(&self) -> RecoveryLimits {
        RecoveryLimits {
            max_visits: self.recovery_max_visits as u64,
            deadline_ms: self.recovery_deadline_ms,
        }
    }
    pub fn unwind_limits(&self) -> super::FrameRecoveryLimits {
        super::FrameRecoveryLimits {
            max_frames: self.max_frames,
            max_runtime_entries: self.max_runtime_entries,
            max_read_bytes: self.max_unwind_read_bytes,
            max_stack_adjustment: self.max_stack_adjustment,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureQuestion {
    pub from_frame: usize,
    pub to_frame: usize,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct RecoveryProofs {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub alignment: Option<crate::bap::alignment_hypothesis::Report>,
    pub guard: Option<crate::bap::guard_admission::Report>,
    pub target: Option<crate::bap::target_resolution::Report>,
    pub composition: Option<crate::bap::composition::Report>,
    pub decoder_records: BTreeMap<String, String>,
    pub preparation: PreparationProof,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PreparationLimitsProof {
    pub max_starts: usize,
    pub max_candidates: usize,
    pub max_prefix_bytes: usize,
    pub max_decoder_batches: usize,
    pub batch_size: usize,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct OpenLimitsProof {
    pub max_file_bytes: usize,
    pub max_streams: usize,
    pub max_records: usize,
    pub max_metadata_bytes: usize,
    pub max_capture_ranges: usize,
    pub max_overlap: usize,
    pub max_read_bytes: usize,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PreparationProof {
    pub limits: PreparationLimitsProof,
    pub open_limits: OpenLimitsProof,
}

pub(crate) fn validate_chain_policy(
    chain: &CapturedFrameChain,
    limits: &FrameStructureLimits,
) -> Result<(), Error> {
    if chain.artifact_bytes() > limits.max_file_bytes
        || chain.frames.len() > limits.max_frames
        || chain.limits.max_frames > limits.max_frames
        || chain.limits.max_runtime_entries > limits.max_runtime_entries
        || chain.limits.max_read_bytes > limits.max_unwind_read_bytes
        || chain.limits.max_stack_adjustment > limits.max_stack_adjustment
        || chain.read_bytes > limits.max_unwind_read_bytes
    {
        return Err(invalid("captured frame chain exceeds host unwind policy"));
    }
    Ok(())
}

pub(crate) fn validate_proof_policy(
    proofs: &RecoveryProofs,
    limits: &FrameStructureLimits,
) -> Result<(), Error> {
    let guard = proofs
        .guard
        .as_ref()
        .ok_or_else(|| invalid("structural report requires complete guard source evidence"))?;
    proof_policy(&guard.input.limits, &limits.guard)?;
    if let Some(alignment) = &proofs.alignment {
        proof_policy(&alignment.limits, &limits.guard)?;
    }
    if let Some(target) = &proofs.target {
        proof_policy(&target.limits, &limits.target)?;
    }
    let p = &proofs.preparation;
    let host = PreparationLimitsProof {
        max_starts: limits.max_prepare_starts,
        max_candidates: limits.max_prepare_candidates,
        max_prefix_bytes: limits.max_prepare_prefix_bytes,
        max_decoder_batches: limits.max_prepare_decoder_batches,
        batch_size: limits.prepare_batch_size,
    };
    proof_policy(&p.limits, &host)?;
    let host = OpenLimitsProof {
        max_file_bytes: limits.max_file_bytes,
        max_streams: limits.max_streams,
        max_records: limits.max_records,
        max_metadata_bytes: limits.max_metadata_bytes,
        max_capture_ranges: limits.max_capture_ranges,
        max_overlap: limits.max_overlap,
        max_read_bytes: limits.max_read_bytes,
    };
    proof_policy(&p.open_limits, &host)?;
    if p.limits.batch_size == 0 {
        return Err(invalid("preparation proof batch size must be positive"));
    }
    Ok(())
}

fn validate_preparation_proof(
    request: &AnalysisRequest,
    proofs: &RecoveryProofs,
) -> Result<(), Error> {
    use sha2::{Digest, Sha256};
    let guard = proofs.guard.as_ref().expect("guard present");
    let mut digest = Sha256::new();
    digest.update(b"ariadne-minidump-query-v1\0");
    digest.update(request.snapshot_id.as_bytes());
    for set in [&request.entry_points, &request.slice_seeds] {
        digest.update((set.len() as u64).to_le_bytes());
        for address in set {
            digest.update(address.to_le_bytes());
        }
    }
    let p = &proofs.preparation.limits;
    for value in [
        p.max_starts,
        p.max_candidates,
        p.max_prefix_bytes,
        p.max_decoder_batches,
        p.batch_size,
    ] {
        digest.update((value as u64).to_le_bytes());
    }
    let query_identity = format!("{:x}", digest.finalize());
    let scope = super::sha(&serde_json::to_vec(&(
        query_identity,
        &guard.input.activation,
        &guard.input.roots,
    ))?);
    let preparation = super::sha(&serde_json::to_vec(&serde_json::json!({
        "limits":p,"locations":request.locations,"open_limits":proofs.preparation.open_limits,
        "profile":guard.input.policy,
    }))?);
    if scope != guard.input.query_scope_sha256 || preparation != guard.input.preparation_sha256 {
        return Err(invalid(
            "structural preparation/query resource provenance changed",
        ));
    }
    Ok(())
}

/// Privately constructed from the final normalized request and captured proof sources.
#[derive(Clone)]
pub struct BoundFrameRecovery {
    recovery: RecoveryResult,
    context: EvidenceContext,
    proofs: RecoveryProofs,
    identity: Identity,
}
impl BoundFrameRecovery {
    pub fn alignment_hypotheses(&self) -> Option<&crate::bap::alignment_hypothesis::Report> {
        self.proofs.alignment.as_ref()
    }
    pub fn recovery(&self) -> &RecoveryResult {
        &self.recovery
    }
    pub fn request(&self) -> &AnalysisRequest {
        self.recovery.request()
    }
    pub fn context(&self) -> &EvidenceContext {
        &self.context
    }
    pub fn identity(&self) -> &Identity {
        &self.identity
    }
    pub(crate) fn proofs(&self) -> &RecoveryProofs {
        &self.proofs
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameStructureGapKind {
    PendingLocalWork,
    DecodeFailed,
    UnavailableBytes,
    UnknownIndirectTarget,
    UnknownCallTarget,
    UnresolvedGuard,
    OpaqueCallContext,
    OutsideFunction,
    UnsupportedEffects,
    ExceptionExit,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureGap {
    pub kind: FrameStructureGapKind,
    #[serde(with = "super::model::va")]
    pub site: u64,
    #[serde(with = "super::frame_unwind::optional_address")]
    pub destination: Option<u64>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureEdge {
    pub src: FramePathNode,
    pub dst: FramePathNode,
    pub kind: FramePathEdgeKind,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureMap {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub conditional_on: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub alignment_decisions: Vec<crate::bap::alignment_hypothesis::Decision>,
    pub frame: usize,
    pub auxiliary: bool,
    pub identity: Identity,
    #[serde(with = "super::model::va")]
    pub entry: u64,
    pub nodes: Vec<SiteEvidence>,
    pub edges: Vec<FrameStructureEdge>,
    pub gaps: Vec<FrameStructureGap>,
    pub recovery_drained: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameStructureDiagnosticKind {
    MissingFrame,
    MissingEntry,
    PreparationFailed,
    PreparationLimit,
    MissingRecovery,
    MissingActiveCall,
    AmbiguousActiveCall,
    UnavailableLinkEndpoint,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureDiagnostic {
    pub frame: usize,
    pub kind: FrameStructureDiagnosticKind,
    pub message: String,
    #[serde(with = "super::frame_unwind::address_list")]
    pub attempted: Vec<u64>,
    #[serde(with = "super::frame_unwind::address_list")]
    pub unattempted_references: Vec<u64>,
}
impl FrameStructureDiagnostic {
    pub fn new(
        frame: usize,
        kind: FrameStructureDiagnosticKind,
        message: impl Into<String>,
    ) -> Self {
        Self {
            frame,
            kind,
            message: message.into(),
            attempted: Vec::new(),
            unattempted_references: Vec::new(),
        }
    }
}

/// A relation between captured adjacent activations; CALL is admitted only with a reached E8 witness.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameStructureLink {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub conditional_on: Vec<String>,
    pub caller: usize,
    pub child: usize,
    #[serde(with = "super::frame_unwind::optional_address")]
    pub call_site: Option<u64>,
    #[serde(with = "super::frame_unwind::optional_address")]
    pub child_entry: Option<u64>,
    #[serde(with = "super::model::va")]
    pub continuation: u64,
    pub admitted: bool,
}
pub struct BoundFrameStructure {
    chain: CapturedFrameChain,
    question: FrameStructureQuestion,
    limits: FrameStructureLimits,
    recoveries: Vec<(usize, BoundFrameRecovery)>,
    frames: Vec<FrameStructureMap>,
    links: Vec<FrameStructureLink>,
    diagnostics: Vec<FrameStructureDiagnostic>,
}
impl BoundFrameStructure {
    pub fn hypothesis_ids(&self) -> Vec<String> {
        let mut ids: Vec<_> = self
            .recoveries
            .iter()
            .flat_map(|(_, bound)| bound.alignment_hypotheses())
            .flat_map(|report| report.hypotheses.iter().map(|h| h.id.clone()))
            .collect();
        ids.sort();
        ids.dedup();
        ids
    }
    pub fn is_conditional(&self) -> bool {
        self.recoveries
            .iter()
            .any(|(_, bound)| bound.alignment_hypotheses().is_some())
    }
    pub fn chain(&self) -> &CapturedFrameChain {
        &self.chain
    }
    pub fn question(&self) -> &FrameStructureQuestion {
        &self.question
    }
    pub fn limits(&self) -> &FrameStructureLimits {
        &self.limits
    }
    pub fn recoveries(&self) -> &[(usize, BoundFrameRecovery)] {
        &self.recoveries
    }
    pub fn frames(&self) -> &[FrameStructureMap] {
        &self.frames
    }
    pub fn links(&self) -> &[FrameStructureLink] {
        &self.links
    }
    pub fn diagnostics(&self) -> &[FrameStructureDiagnostic] {
        &self.diagnostics
    }
}

fn proof_policy(producer: &impl Serialize, host: &impl Serialize) -> Result<(), Error> {
    let producer = serde_json::to_value(producer)?;
    let host = serde_json::to_value(host)?;
    for (key, value) in producer
        .as_object()
        .ok_or_else(|| invalid("proof policy shape"))?
    {
        if value
            .as_u64()
            .ok_or_else(|| invalid("proof policy unsigned field"))?
            > host[key]
                .as_u64()
                .ok_or_else(|| invalid("host proof policy field"))?
        {
            return Err(invalid(format!(
                "structural proof policy exceeds host: {key}"
            )));
        }
    }
    Ok(())
}

fn validate_sources(
    chain: &CapturedFrameChain,
    frame: usize,
    request: &AnalysisRequest,
    context: &EvidenceContext,
    proofs: &RecoveryProofs,
    limits: &FrameStructureLimits,
) -> Result<Identity, Error> {
    if let Some(alignment) = &proofs.alignment {
        limits.validate()?;
        validate_proof_policy(proofs, limits)?;
        if serde_json::to_vec(proofs)?.len() > limits.max_proof_bytes
            || serde_json::to_vec(&alignment.base_request)?.len() > limits.max_owned_bytes
        {
            return Err(invalid("conditional alignment base/proof byte policy"));
        }
        let base_request = crate::bap::alignment_hypothesis::base_request(alignment)?;
        let mut base_proofs = proofs.clone();
        base_proofs.alignment = None;
        let mut identity =
            validate_sources(chain, frame, &base_request, context, &base_proofs, limits)?;
        if alignment.hypotheses.is_empty()
            || alignment.hypotheses.len() > limits.max_graph_nodes
            || request.addresses.len() > limits.max_graph_nodes
            || serde_json::to_vec(proofs)?.len() > limits.max_proof_bytes
        {
            return Err(invalid("conditional alignment hypothesis/proof policy"));
        }
        crate::bap::alignment_hypothesis::validate(
            alignment,
            proofs.guard.as_ref().expect("base guard validated"),
            &proofs.decoder_records,
            request,
            &limits.guard,
        )?;
        let conditional = crate::bap::alignment_hypothesis::analysis_id(alignment)?;
        identity.query_id = super::sha(&serde_json::to_vec(&(
            "ariadne.conditional-frame-query/v1",
            &identity.query_id,
            &conditional,
        ))?);
        identity.request_sha256 = super::request_fingerprint(request);
        identity.semantic_profile = format!(
            "{}:conditional-alignment-hypotheses=[{}]",
            identity.semantic_profile, conditional
        );
        return Ok(identity);
    }
    limits.validate()?;
    validate_chain_policy(chain, limits)?;
    validate_proof_policy(proofs, limits)?;
    request.validate()?;
    let activation = chain
        .frames
        .get(frame)
        .ok_or_else(|| invalid("structural frame outside chain"))?;
    if chain.frames.len() > limits.max_frames
        || request.addresses.len() > limits.max_graph_nodes
        || request.entry_points.len() != 1
        || request.snapshot_id != chain.snapshot_id
        || context.snapshot_id != chain.snapshot_id
        || context.artifact_sha256 != chain.artifact_sha256
        || request.input_kind != crate::InputKind::Dump
        || !request.file_backed.is_empty()
        || !request.trusted_fallback.is_empty()
        || !super::validate::digest(&context.query_id)
        || !super::validate::digest(&context.artifact_sha256)
        || !context.recovery_gaps.is_empty()
        || context.sites.len() != request.addresses.len()
        || !context.sites.windows(2).all(|pair| pair[0].va < pair[1].va)
        || context
            .sites
            .iter()
            .any(|site| !request.addresses.contains(&site.va) || !super::validate::site_valid(site))
    {
        return Err(invalid(
            "structural capture/request identity or source domain changed",
        ));
    }
    validate_capture_membership_and_extents(chain, request, context, proofs)?;
    let normalized = crate::bap::core_adapter::encode_request(request)?;
    if serde_json::to_vec(&(&normalized, &context.sites))?.len() > limits.max_owned_bytes
        || serde_json::to_vec(proofs)?.len() > limits.max_proof_bytes
    {
        return Err(invalid("structural owned source/proof byte budget"));
    }
    let report = proofs
        .guard
        .as_ref()
        .ok_or_else(|| invalid("structural report requires complete guard source evidence"))?;
    validate_preparation_proof(request, proofs)?;
    if proofs.composition.is_none() && proofs.target.is_some() {
        return Err(invalid(
            "structural paired target proof requires composition",
        ));
    }
    let entry = *request.entry_points.first().expect("checked root");
    let expected_anchor = frame_entry_anchor(chain, frame, entry)?;
    if report.input.roots.len() != 1
        || report.input.roots[0].anchor_sha256 != expected_anchor
        || report.input.seeds
            != request
                .slice_seeds
                .iter()
                .map(|site| format!("0x{site:016x}"))
                .collect::<Vec<_>>()
        || activation
            .function_begin
            .is_some_and(|value| value != entry)
    {
        return Err(invalid("structural frame entry anchor changed"));
    }
    let identity = Identity {
        snapshot_id: context.snapshot_id.clone(),
        artifact_sha256: context.artifact_sha256.clone(),
        query_id: context.query_id.clone(),
        request_sha256: super::request_fingerprint(request),
        semantic_profile: context.semantic_profile.clone(),
    };
    super::frame_paths::validate_frame_recovery_sources(
        chain,
        frame,
        entry,
        &identity,
        normalized,
        context.sites.clone(),
        report.clone(),
        proofs.composition.clone(),
        proofs.target.clone(),
        &proofs.decoder_records,
    )?;
    validate_source_effects(request, context, proofs)?;
    Ok(identity)
}

pub(crate) fn bind_alignment_hypotheses(
    chain: &CapturedFrameChain,
    frame: usize,
    base: BoundFrameRecovery,
    sites: &[u64],
    limits: &FrameStructureLimits,
) -> Result<BoundFrameRecovery, Error> {
    if sites.is_empty() || sites.len() > limits.max_graph_nodes || base.proofs.alignment.is_some() {
        return Err(invalid(
            "alignment hypothesis collection must be nonempty and bounded",
        ));
    }
    let (request, report) = crate::bap::alignment_hypothesis::certify(
        base.request(),
        base.proofs.guard.as_ref().expect("bound guard"),
        &base.proofs.decoder_records,
        sites,
        &limits.guard,
    )?;
    let mut proofs = base.proofs;
    proofs.alignment = Some(report);
    let recovery = crate::recovery::recover(request, limits.recovery_limits())?;
    bind_recovery(chain, frame, recovery, base.context, proofs, limits)
}

fn validate_capture_membership_and_extents(
    chain: &CapturedFrameChain,
    request: &AnalysisRequest,
    context: &EvidenceContext,
    proofs: &RecoveryProofs,
) -> Result<(), Error> {
    let artifact_bytes = chain.artifact_bytes() as u64;
    let extent = |address: u64, length: usize, offset: u64| -> Result<(), Error> {
        let length =
            u64::try_from(length).map_err(|_| invalid("capture span length representation"))?;
        if u128::from(address) + u128::from(length) > u128::from(u64::MAX) + 1
            || offset
                .checked_add(length)
                .is_none_or(|end| end > artifact_bytes)
        {
            return Err(invalid(
                "captured evidence span exceeds address or artifact extent",
            ));
        }
        Ok(())
    };
    let mut captured = crate::AddressSet::new();
    for site in &context.sites {
        let mut span_end = u128::from(site.va);
        for span in &site.spans {
            if span.length == 0 || span.contributors.is_empty() || u128::from(span.va) != span_end {
                return Err(invalid(
                    "captured instruction read spans are not a contiguous prefix",
                ));
            }
            span_end += span.length as u128;
            if span_end > u128::from(site.va) + 15 {
                return Err(invalid(
                    "captured instruction read spans exceed decode prefix",
                ));
            }
            for contributor in &span.contributors {
                extent(span.va, span.length, contributor.file_offset)?;
            }
        }
        if site.captured {
            if site.bytes_hex.is_empty() {
                return Err(invalid(
                    "captured instruction source has no captured prefix",
                ));
            }
            let name = format!("0x{:016x}", site.va);
            let record = proofs
                .decoder_records
                .get(&name)
                .ok_or_else(|| invalid("captured source lacks its mandatory decode receipt"))?;
            let decoded = crate::llvm_mc::protocol::parse(record)?.decoded;
            if decoded.status != "invalid" || site.bytes_hex.len() / 2 >= 15 {
                captured.insert(site.va);
            }
        } else if !site.spans.is_empty() || !site.bytes_hex.is_empty() {
            return Err(invalid(
                "unavailable instruction source carries captured bytes or spans",
            ));
        }
        let decoded_status = matches!(
            site.semantic_status.as_deref(),
            Some("projected" | "opaque-ordinary" | "opaque-call-return" | "normal-flow-terminal")
        );
        if request.decodable.contains(&site.va) != decoded_status {
            return Err(invalid(
                "captured semantic admission differs from normalized decodable membership",
            ));
        }
    }
    if captured != request.captured {
        return Err(invalid(
            "normalized captured membership differs from decoder/capture receipts",
        ));
    }
    if let Some(target) = &proofs.target {
        for read in &target.data_reads {
            for span in &read.spans {
                let address = crate::bap::core_adapter::address(&span.address)?;
                for contributor in &span.contributors {
                    extent(address, span.length, contributor.file_offset)?;
                }
            }
            if read
                .conflict_sources
                .iter()
                .any(|source| source.file_offset >= artifact_bytes)
            {
                return Err(invalid(
                    "captured control-data conflict source exceeds artifact extent",
                ));
            }
        }
    }
    Ok(())
}

fn validate_source_effects(
    request: &AnalysisRequest,
    context: &EvidenceContext,
    proofs: &RecoveryProofs,
) -> Result<(), Error> {
    let report = proofs.guard.as_ref().expect("guard checked");
    let sites: BTreeMap<_, _> = context.sites.iter().map(|site| (site.va, site)).collect();
    let candidates: BTreeMap<_, _> = report
        .input
        .sites
        .iter()
        .map(|source| (source.site.as_str(), source))
        .collect();
    let candidate_addresses = candidates
        .keys()
        .map(|name| crate::bap::core_adapter::address(name))
        .collect::<Result<crate::AddressSet, _>>()?;
    if candidates.len() != report.input.sites.len()
        || !candidate_addresses.is_subset(&request.addresses)
    {
        return Err(invalid(
            "structural guarded source domain is invalid or duplicated",
        ));
    }
    for address in request.addresses.difference(&candidate_addresses) {
        let site = sites[address];
        if request.instructions[address] != crate::Instruction::default()
            || request.decodable.contains(address)
            || request.captured.contains(address)
            || site.captured
            || !site.bytes_hex.is_empty()
            || site.quality != "unavailable"
            || site.opcode.is_some()
            || site.semantic_status.is_some()
            || site.ast_sha256.is_some()
            || site.helper_sha256.is_some()
            || site.runtime_sha256.is_some()
            || site.projection.is_some()
            || !site.accesses.is_empty()
            || !site.spans.is_empty()
        {
            return Err(invalid(
                "unqueued control reference acquired captured semantics",
            ));
        }
    }
    for (name, record) in &proofs.decoder_records {
        let address = crate::bap::core_adapter::address(name)?;
        let site = sites
            .get(&address)
            .ok_or_else(|| invalid("decoder receipt outside captured source domain"))?;
        let raw = crate::llvm_mc::protocol::parse(record)?;
        let opcode = (raw.opcode != "-").then_some(raw.opcode.as_str());
        if site.opcode.as_deref() != opcode
            || raw.decoded.address != address
            || (raw.decoded.status != "invalid"
                && raw.decoded.length != (site.bytes_hex.len() / 2) as u64)
        {
            return Err(invalid(
                "decoder opcode/address/extent differs from captured source",
            ));
        }
        if let Some(source) = candidates.get(name.as_str())
            && source.control.kind != crate::bap::guard_admission::ControlKind::Stop
        {
            let kind = raw
                .decoded
                .kind
                .ok_or_else(|| invalid("admitted captured source lacks decoded control"))?;
            if source.control.kind
                != crate::bap::guard_admission::CandidateControl::from_instruction(
                    &crate::Instruction {
                        kind,
                        ..Default::default()
                    },
                )
                .kind
            {
                return Err(invalid(
                    "captured candidate kind differs from decode reference",
                ));
            }
            if let Some(target) = raw.decoded.target
                && source.control.targets != [format!("0x{target:016x}")]
            {
                return Err(invalid(
                    "direct captured candidate target differs from decode reference",
                ));
            }
        }
    }
    for source in &report.input.sites {
        let address = crate::bap::core_adapter::address(&source.site)?;
        let site = sites
            .get(&address)
            .ok_or_else(|| invalid("effect source outside domain"))?;
        let actual = &request.instructions[&address];
        if crate::bap::guard_admission::recognize_pending_for_input(&report.input, source)?
            .is_some()
        {
            continue;
        }
        if !request.decodable.contains(&address) && *actual == crate::Instruction::default() {
            continue;
        }
        if site.quality == "opaque" || !request.decodable.contains(&address) {
            if actual.uses != request.locations
                || actual.may_defs != request.locations
                || !actual.must_defs.is_empty()
            {
                return Err(invalid(
                    "opaque captured source changed conservative effects",
                ));
            }
            continue;
        }
        if site.semantic_status.as_deref() != Some("projected") {
            return Err(invalid(
                "structural admitted source has unsupported semantic status",
            ));
        }
        let record = proofs
            .decoder_records
            .get(&source.site)
            .ok_or_else(|| invalid("projected source missing decoded operand receipt"))?;
        let raw = crate::llvm_mc::protocol::parse(record)?;
        let fields: Vec<_> = record.split_ascii_whitespace().collect();
        let operands = fields
            .get(2)
            .ok_or_else(|| invalid("decoder operand count absent"))?
            .parse::<usize>()?;
        let definitions = fields
            .get(3 + operands)
            .ok_or_else(|| invalid("decoder definitions absent"))?
            .parse::<usize>()?;
        let destination = if definitions > 0 {
            fields
                .get(3)
                .and_then(|field| field.strip_prefix("r:"))
                .and_then(crate::effects::RegisterView::parse)
        } else {
            None
        };
        let bil: Vec<crate::bap::ast::Stmt> = serde_json::from_str(&source.ast)?;
        let mut projection = crate::bap::projection::project_with_destination(
            &bil,
            &raw.opcode,
            &super::frame_unwind::unhex(&source.bytes_hex)?,
            address,
            destination.as_ref(),
        )?;
        if ["TEST64rr", "TEST8rr", "XOR64rr"].contains(&raw.opcode.as_str()) {
            projection.must_defs.remove("flag:af");
        }
        if actual.uses != projection.uses
            || actual.may_defs != projection.may_defs
            || actual.must_defs != projection.must_defs
            || site.accesses
                != crate::bap::address::extract(&bil, address)
                    .iter()
                    .map(super::AddressUse::from)
                    .collect::<Vec<_>>()
        {
            return Err(invalid("structural captured BIL effect projection changed"));
        }
    }
    Ok(())
}

pub(crate) fn frame_entry_anchor(
    chain: &CapturedFrameChain,
    index: usize,
    entry: u64,
) -> Result<String, Error> {
    let frame = chain
        .frames
        .get(index)
        .ok_or_else(|| invalid("frame entry outside chain"))?;
    let activation = crate::bap::guard_admission::Activation {
        thread_id: chain.thread_id,
        frame_activation: format!("{}:{index}:0x{:016x}", chain.chain_id, frame.sp),
    };
    if frame.function_begin.is_some() {
        Ok(super::sha(&serde_json::to_vec(&(
            "captured-frame-function-entry/v1",
            &chain.chain_id,
            index,
            frame.function_begin,
            frame.function_end,
            &activation,
        ))?))
    } else if frame.transition == Some(FrameTransition::MachineFrame) {
        Err(invalid("machine-frame transition has no parent-call entry"))
    } else {
        Ok(super::sha(&serde_json::to_vec(&(
            "captured-frame-parent-call-entry/v1",
            &chain.chain_id,
            index,
            entry,
            &activation,
        ))?))
    }
}

pub(crate) fn bind_recovery(
    chain: &CapturedFrameChain,
    frame: usize,
    recovery: RecoveryResult,
    context: EvidenceContext,
    proofs: RecoveryProofs,
    limits: &FrameStructureLimits,
) -> Result<BoundFrameRecovery, Error> {
    if recovery.limits().max_visits > limits.recovery_max_visits as u64
        || recovery.limits().deadline_ms > limits.recovery_deadline_ms
        || recovery.state().edges.len() > limits.max_graph_edges
    {
        return Err(invalid("structural producer recovery policy exceeds host"));
    }
    let identity = validate_sources(chain, frame, recovery.request(), &context, &proofs, limits)?;
    Ok(BoundFrameRecovery {
        recovery,
        context,
        proofs,
        identity,
    })
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn replay_frame_recovery(
    chain: &CapturedFrameChain,
    frame: usize,
    request: AnalysisRequest,
    context: EvidenceContext,
    proofs: RecoveryProofs,
    receipt: crate::recovery::RecoveryReceipt,
    producer_limits: RecoveryLimits,
    host_limits: &FrameStructureLimits,
) -> Result<BoundFrameRecovery, Error> {
    // Expensive proof replay happens only after independent host resource and source checks.
    if producer_limits.max_visits > host_limits.recovery_max_visits as u64
        || producer_limits.deadline_ms > host_limits.recovery_deadline_ms
        || receipt.visits > host_limits.max_replay_visits as u64
    {
        return Err(invalid("structural replay/producer budget"));
    }
    let identity = validate_sources(chain, frame, &request, &context, &proofs, host_limits)?;
    let recovery = crate::recovery::replay_recovery(
        request,
        producer_limits,
        receipt,
        host_limits.max_replay_visits as u64,
    )?;
    if recovery.state().edges.len() > host_limits.max_graph_edges {
        return Err(invalid("structural recovery edge budget"));
    }
    Ok(BoundFrameRecovery {
        recovery,
        context,
        proofs,
        identity,
    })
}

fn active_calls(
    chain: &CapturedFrameChain,
    child: usize,
    parent: &BoundFrameRecovery,
) -> Result<Vec<(u64, u64)>, Error> {
    let younger = chain
        .frames
        .get(child)
        .ok_or_else(|| invalid("child frame outside chain"))?;
    if younger.transition == Some(FrameTransition::MachineFrame) {
        return Err(invalid("machine-frame transition has no active call entry"));
    }
    let older = chain
        .frames
        .get(
            child
                .checked_add(1)
                .ok_or_else(|| invalid("frame index overflow"))?,
        )
        .ok_or_else(|| invalid("caller frame unavailable"))?;
    if parent.identity.snapshot_id != chain.snapshot_id
        || parent.identity.artifact_sha256 != chain.artifact_sha256
    {
        return Err(invalid("active caller belongs to another snapshot"));
    }
    let activation = parent
        .proofs
        .guard
        .as_ref()
        .ok_or_else(|| invalid("active caller lacks bound activation proof"))?;
    if activation.input.activation.thread_id != chain.thread_id
        || activation.input.activation.frame_activation
            != format!("{}:{}:0x{:016x}", chain.chain_id, child + 1, older.sp)
    {
        return Err(invalid(
            "active caller belongs to another physical activation",
        ));
    }
    let sites: BTreeMap<_, _> = parent
        .context
        .sites
        .iter()
        .map(|site| (site.va, site))
        .collect();
    Ok(parent
        .recovery
        .state()
        .decoded
        .iter()
        .filter_map(|site| {
            if older.function_begin.is_some_and(|begin| *site < begin)
                || older
                    .function_end
                    .is_some_and(|end| u128::from(*site) + 5 > u128::from(end))
            {
                return None;
            }
            let instruction = &parent.request().instructions[site];
            super::frame_paths::captured_call_target(
                sites.get(site)?,
                instruction.kind == InstructionKind::Call,
                &instruction.fall.iter().copied().collect::<Vec<_>>(),
                &instruction.targets.iter().copied().collect::<Vec<_>>(),
                older.pc,
            )
            .filter(|target| younger.function_begin.is_none_or(|entry| entry == *target))
            .map(|target| (*site, target))
        })
        .collect())
}
pub fn active_frame_structure_entry(
    chain: &CapturedFrameChain,
    child: usize,
    parent: &BoundFrameRecovery,
) -> Result<u64, Error> {
    chain.validate()?;
    let calls = active_calls(chain, child, parent)?;
    if calls.len() != 1 {
        return Err(invalid("missing-or-ambiguous-active-direct-call"));
    }
    Ok(calls[0].1)
}

/// Only ancestors needed to reach an independently rooted caller can supply
/// auxiliary entry evidence. Missing preparation leaves the other maps useful.
fn auxiliary_frame_ceiling(chain: &CapturedFrameChain, question: &FrameStructureQuestion) -> usize {
    let mut oldest = question.from_frame;
    while chain.frames.get(oldest).is_some_and(|frame| {
        frame.function_begin.is_none() && frame.transition != Some(FrameTransition::MachineFrame)
    }) {
        let Some(parent) = oldest
            .checked_add(1)
            .filter(|parent| *parent < chain.frames.len())
        else {
            break;
        };
        oldest = parent;
    }
    oldest
}

fn frame_link(
    chain: &CapturedFrameChain,
    child: usize,
    parent: Option<&BoundFrameRecovery>,
    younger: Option<&BoundFrameRecovery>,
) -> Result<(FrameStructureLink, Option<FrameStructureDiagnostic>), Error> {
    let caller = child
        .checked_add(1)
        .ok_or_else(|| invalid("frame link index overflow"))?;
    let continuation = chain
        .frames
        .get(caller)
        .ok_or_else(|| invalid("frame link caller unavailable"))?
        .pc;
    let mut link = FrameStructureLink {
        conditional_on: Vec::new(),
        caller,
        child,
        call_site: None,
        child_entry: None,
        continuation,
        admitted: false,
    };
    if chain.frames[child].transition == Some(FrameTransition::MachineFrame) {
        return Ok((
            link,
            Some(FrameStructureDiagnostic::new(
                child,
                FrameStructureDiagnosticKind::UnavailableLinkEndpoint,
                "machine-frame transition restores an interrupted PC; no ordinary call link is implied",
            )),
        ));
    }
    let Some(parent) = parent else {
        return Ok((link, None));
    };
    let calls = active_calls(chain, child, parent)?;
    if calls.len() != 1 {
        return Ok((
            link,
            Some(FrameStructureDiagnostic::new(
                child,
                if calls.len() > 1 {
                    FrameStructureDiagnosticKind::AmbiguousActiveCall
                } else {
                    FrameStructureDiagnosticKind::MissingActiveCall
                },
                "captured activation relation lacks a unique reached matching E8 call",
            )),
        ));
    }
    link.call_site = Some(calls[0].0);
    link.child_entry = Some(calls[0].1);
    if younger.is_some_and(|bound| bound.request().entry_points != [calls[0].1].into()) {
        return Ok((
            link,
            Some(FrameStructureDiagnostic::new(
                child,
                FrameStructureDiagnosticKind::MissingActiveCall,
                "reached parent E8 target differs from the child's bound root",
            )),
        ));
    }
    if younger.is_none_or(|bound| !bound.recovery.state().decoded.contains(&calls[0].1)) {
        return Ok((
            link,
            Some(FrameStructureDiagnostic::new(
                child,
                FrameStructureDiagnosticKind::UnavailableLinkEndpoint,
                "captured E8 anchor is known; child entry has not been admitted by recovery",
            )),
        ));
    }
    link.admitted = true;
    Ok((link, None))
}

pub fn bind_frame_structure(
    chain: CapturedFrameChain,
    question: FrameStructureQuestion,
    mut recoveries: Vec<(usize, BoundFrameRecovery)>,
    mut diagnostics: Vec<FrameStructureDiagnostic>,
    limits: FrameStructureLimits,
) -> Result<BoundFrameStructure, Error> {
    limits.validate()?;
    validate_chain_policy(&chain, &limits)?;
    chain.validate()?;
    if question.from_frame < question.to_frame
        || question.from_frame >= limits.max_frames
        || chain.frames.len() > limits.max_frames
        || recoveries.len() > limits.max_frames
        || diagnostics.len() > limits.max_frames.saturating_mul(4)
    {
        return Err(invalid("invalid structural question or frame policy"));
    }
    recoveries.sort_by_key(|(index, _)| *index);
    if recoveries.windows(2).any(|pair| pair[0].0 == pair[1].0) {
        return Err(invalid("duplicate structural frame recovery"));
    }
    let oldest = auxiliary_frame_ceiling(&chain, &question);
    let permitted = |index: usize| index >= question.to_frame && index <= oldest;
    if recoveries.iter().any(|(index, _)| !permitted(*index))
        || diagnostics.iter().any(|diagnostic| {
            !permitted(diagnostic.frame)
                || diagnostic.message.len() > limits.max_owned_bytes
                || !diagnostic
                    .attempted
                    .windows(2)
                    .all(|pair| pair[0] < pair[1])
                || !diagnostic
                    .unattempted_references
                    .windows(2)
                    .all(|pair| pair[0] < pair[1])
                || diagnostic.attempted.iter().any(|site| {
                    diagnostic
                        .unattempted_references
                        .binary_search(site)
                        .is_ok()
                })
                || diagnostic.attempted.len() > limits.max_prepare_starts
                || diagnostic.unattempted_references.len() > limits.max_prepare_candidates
        })
    {
        return Err(invalid(
            "structural diagnostic or auxiliary frame scope invalid",
        ));
    }
    let mut nodes = 0usize;
    let mut edges = 0usize;
    let mut visits = 0usize;
    let mut owned = 0usize;
    let mut proof_bytes = 0usize;
    let mut frames = Vec::new();
    for (index, bound) in &recoveries {
        // Construction may have used a different policy or activation; aggregation rechecks both.
        let identity = validate_sources(
            &chain,
            *index,
            bound.request(),
            &bound.context,
            &bound.proofs,
            &limits,
        )?;
        if identity != bound.identity {
            return Err(invalid("structural recovery identity changed"));
        }
        nodes = nodes
            .checked_add(bound.request().addresses.len())
            .ok_or_else(|| invalid("structural node count overflow"))?;
        edges = edges
            .checked_add(bound.recovery.state().edges.len())
            .ok_or_else(|| invalid("structural edge count overflow"))?;
        visits = visits
            .checked_add(bound.recovery.receipt().visits as usize)
            .ok_or_else(|| invalid("structural visit count overflow"))?;
        owned = owned
            .checked_add(
                serde_json::to_vec(&(
                    crate::bap::core_adapter::encode_request(bound.request())?,
                    &bound.context.sites,
                ))?
                .len(),
            )
            .ok_or_else(|| invalid("structural owned bytes overflow"))?;
        if let Some(alignment) = &bound.proofs.alignment {
            owned = owned
                .checked_add(serde_json::to_vec(&alignment.base_request)?.len())
                .ok_or_else(|| invalid("structural base request byte overflow"))?;
        }
        proof_bytes = proof_bytes
            .checked_add(serde_json::to_vec(&bound.proofs)?.len())
            .ok_or_else(|| invalid("structural proof bytes overflow"))?;
        if nodes > limits.max_graph_nodes
            || edges > limits.max_graph_edges
            || visits > limits.max_replay_visits
            || owned > limits.max_owned_bytes
            || proof_bytes > limits.max_proof_bytes
        {
            return Err(invalid("aggregate structural resource budget"));
        }
        frames.push(frame_map(
            &chain,
            *index,
            bound,
            *index < question.to_frame || *index > question.from_frame,
        )?);
    }
    let indexed: BTreeMap<_, _> = recoveries
        .iter()
        .map(|(index, bound)| (*index, bound))
        .collect();
    // Derived availability/link diagnostics are recomputed, never accepted as evidence.
    diagnostics.retain(|diagnostic| {
        matches!(
            diagnostic.kind,
            FrameStructureDiagnosticKind::PreparationFailed
                | FrameStructureDiagnosticKind::PreparationLimit
                | FrameStructureDiagnosticKind::MissingEntry
        )
    });
    if diagnostics.iter().any(|diagnostic| {
        indexed.contains_key(&diagnostic.frame)
            || chain.frames.get(diagnostic.frame).is_none()
            || (diagnostic.kind == FrameStructureDiagnosticKind::MissingEntry
                && chain.frames[diagnostic.frame].function_begin.is_some())
    }) {
        return Err(invalid(
            "preparation diagnostic contradicts admitted activation evidence",
        ));
    }
    // A leaf root is justified only by a separately bound reached parent call.
    for (index, bound) in &recoveries {
        if chain.frames[*index].function_begin.is_none() {
            let parent = indexed
                .get(
                    &index
                        .checked_add(1)
                        .ok_or_else(|| invalid("frame index overflow"))?,
                )
                .ok_or_else(|| invalid("leaf recovery lacks independently bound parent witness"))?;
            if active_frame_structure_entry(&chain, *index, parent)?
                != *bound
                    .request()
                    .entry_points
                    .first()
                    .expect("validated root")
            {
                return Err(invalid("leaf entry differs from parent active call"));
            }
        }
    }
    for index in question.to_frame..=question.from_frame {
        if !indexed.contains_key(&index)
            && !diagnostics
                .iter()
                .any(|diagnostic| diagnostic.frame == index)
        {
            diagnostics.push(FrameStructureDiagnostic::new(
                index,
                if index >= chain.frames.len() {
                    FrameStructureDiagnosticKind::MissingFrame
                } else {
                    FrameStructureDiagnosticKind::MissingRecovery
                },
                "no admitted structural map for selected activation",
            ));
        }
    }
    let mut links = Vec::new();
    for child in question.to_frame..question.from_frame {
        if chain.frames.get(child + 1).is_none() {
            continue;
        }
        let (link, diagnostic) = frame_link(
            &chain,
            child,
            indexed.get(&(child + 1)).copied(),
            indexed.get(&child).copied(),
        )?;
        if let Some(diagnostic) = diagnostic {
            diagnostics.push(diagnostic);
        }
        links.push(link);
    }
    diagnostics.sort();
    diagnostics.dedup();
    let mut hypotheses: Vec<_> = recoveries
        .iter()
        .flat_map(|(_, bound)| bound.alignment_hypotheses())
        .flat_map(|report| report.hypotheses.iter().map(|h| h.id.clone()))
        .collect();
    hypotheses.sort();
    hypotheses.dedup();
    if hypotheses.len() > limits.max_graph_nodes {
        return Err(invalid("aggregate alignment hypothesis count policy"));
    }
    for frame in &mut frames {
        frame.conditional_on = hypotheses.clone();
    }
    for link in &mut links {
        link.conditional_on = hypotheses.clone();
    }
    Ok(BoundFrameStructure {
        chain,
        question,
        limits,
        recoveries,
        frames,
        links,
        diagnostics,
    })
}

fn frame_map(
    chain: &CapturedFrameChain,
    index: usize,
    bound: &BoundFrameRecovery,
    auxiliary: bool,
) -> Result<FrameStructureMap, Error> {
    let activation = &chain.frames[index];
    let in_function = |site: u64| {
        activation.function_begin.is_none_or(|entry| site >= entry)
            && activation.function_end.is_none_or(|end| site < end)
    };
    let state = bound.recovery.state();
    let mut gaps = state
        .pending
        .iter()
        .map(|site| FrameStructureGap {
            kind: FrameStructureGapKind::PendingLocalWork,
            site: *site,
            destination: None,
        })
        .collect::<Vec<_>>();
    for obligation in &state.obligations {
        let guard = bound
            .context
            .sites
            .iter()
            .find(|site| site.va == obligation.site)
            .is_some_and(|site| site.semantic_status.as_deref() == Some("guard-not-admitted"));
        gaps.push(FrameStructureGap {
            site: obligation.site,
            destination: None,
            kind: if guard {
                FrameStructureGapKind::UnresolvedGuard
            } else {
                match obligation.reason {
                    crate::ObligationReason::Unavailable => FrameStructureGapKind::UnavailableBytes,
                    crate::ObligationReason::DecodeFailed => FrameStructureGapKind::DecodeFailed,
                    crate::ObligationReason::IndirectTargets => {
                        FrameStructureGapKind::UnknownIndirectTarget
                    }
                    crate::ObligationReason::CallTargets => {
                        FrameStructureGapKind::UnknownCallTarget
                    }
                }
            },
        });
    }
    for edge in &state.edges {
        if edge.kind.is_local() && in_function(edge.src) && !in_function(edge.dst) {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::OutsideFunction,
                site: edge.src,
                destination: Some(edge.dst),
            });
        }
        if edge.kind == EdgeKind::Call {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::OpaqueCallContext,
                site: edge.src,
                destination: Some(edge.dst),
            });
        }
    }
    for site in &bound.context.sites {
        if !state.decoded.contains(&site.va) {
            continue;
        }
        if !in_function(site.va)
            || activation.function_end.is_some_and(|end| {
                u128::from(site.va) + (site.bytes_hex.len() / 2) as u128 > u128::from(end)
            })
        {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::OutsideFunction,
                site: site.va,
                destination: None,
            });
        }
        if site.semantic_status.as_deref() == Some("opaque-ordinary") {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::UnsupportedEffects,
                site: site.va,
                destination: None,
            });
        }
        if site.semantic_status.as_deref() == Some("normal-flow-terminal") {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::ExceptionExit,
                site: site.va,
                destination: None,
            });
        }
        if bound.request().instructions[&site.va].kind == InstructionKind::Return {
            gaps.push(FrameStructureGap {
                kind: FrameStructureGapKind::OpaqueCallContext,
                site: site.va,
                destination: None,
            });
        }
    }
    Ok(FrameStructureMap {
        conditional_on: Vec::new(),
        alignment_decisions: bound
            .alignment_hypotheses()
            .map(|r| r.decisions.clone())
            .unwrap_or_default(),
        frame: index,
        auxiliary,
        identity: bound.identity.clone(),
        entry: *bound
            .request()
            .entry_points
            .first()
            .expect("validated root"),
        nodes: bound
            .context
            .sites
            .iter()
            .filter(|site| state.decoded.contains(&site.va))
            .cloned()
            .collect(),
        edges: state
            .edges
            .iter()
            .map(|edge| FrameStructureEdge {
                src: FramePathNode {
                    frame: index,
                    site: edge.src,
                },
                dst: FramePathNode {
                    frame: index,
                    site: edge.dst,
                },
                kind: edge.kind.into(),
            })
            .collect(),
        gaps,
        recovery_drained: state.pending.is_empty(),
    })
}

#[cfg(all(test, feature = "input"))]
#[path = "../../tests/investigation/frame_structure.rs"]
pub(super) mod tests;
