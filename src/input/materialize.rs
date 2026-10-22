use crate::bap::guard_admission as guard;
use crate::effects::{
    EffectQuality, InstructionEvidence, PreparationGap, PreparationIdentity, PreparationOptions,
    PreparedAnalysis,
};
use crate::input::*;
use crate::llvm_mc::AdapterError;
use crate::{
    AddressSet, AnalysisRequest, ByteSource, EdgeKind, InputKind, Instruction, InstructionKind,
    LocationSet,
};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub struct AnalysisQuery {
    pub entry_points: AddressSet,
    pub slice_seeds: AddressSet,
}

#[cfg(test)]
#[path = "../../tests/input/address_wrap_binding.rs"]
pub(crate) mod address_wrap_binding_tests;
#[cfg(test)]
#[path = "../../tests/input/common/mod.rs"]
mod common;
#[cfg(test)]
#[path = "../../tests/input/composition.rs"]
mod composition_tests;
#[cfg(test)]
#[path = "../../tests/input/guard_admission.rs"]
mod guard_admission_tests;
#[cfg(test)]
#[path = "../../tests/input/target_resolution_unit.rs"]
mod target_resolution_tests;
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize)]
pub struct PrepareLimits {
    pub max_starts: usize,
    pub max_candidates: usize,
    pub max_prefix_bytes: usize,
    pub max_decoder_batches: usize,
    pub batch_size: usize,
}
impl Default for PrepareLimits {
    fn default() -> Self {
        Self {
            max_starts: 4096,
            max_candidates: 8192,
            max_prefix_bytes: 4096 * 15,
            max_decoder_batches: 4096,
            batch_size: 128,
        }
    }
}
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct MaterializationReport {
    pub entry_points: AddressSet,
    pub slice_seeds: AddressSet,
    pub limits: PrepareLimits,
    pub attempted: AddressSet,
    pub referenced: AddressSet,
    pub unattempted_references: AddressSet,
    pub prefix_bytes: usize,
    pub decoder_batches: usize,
    pub overlapping_starts: BTreeSet<(Address, Address)>,
    pub query_identity: String,
}
/// Original publication facts for the new scalar question binding. Public
/// preparation fields remain editable for existing callers; this seal is never
/// refreshed from those fields, and it owns no analysis or reaching state.
#[derive(Clone, Debug)]
struct ScalarPreparationBinding {
    identity: PreparationIdentity,
    request_fingerprint: String,
    instructions: BTreeMap<Address, InstructionEvidence>,
    reads: BTreeMap<Address, ByteRead>,
    gaps: Vec<PreparationGap>,
    materialization: MaterializationReport,
    open_limits: OpenLimits,
    snapshot: Arc<SnapshotMetadata>,
    fault_digest: String,
}
#[derive(Clone, Debug)]
pub struct FilePreparedAnalysis {
    scalar_binding: Arc<ScalarPreparationBinding>,
    guard_input: Option<Arc<guard::GuardInput>>,
    guard_snapshot: Option<Arc<FileSnapshot>>,
    original_controls: Option<Arc<BTreeMap<Address, guard::CandidateControl>>>,
    pub(crate) guard_admission: Option<guard::Report>,
    pub(crate) target_snapshot: Option<Arc<FileSnapshot>>,
    pub(crate) target_resolution: Option<crate::bap::target_resolution::Report>,
    pub(crate) composition: Option<crate::bap::composition::Report>,
    pub(crate) refinement: BTreeMap<Address, crate::bap::refinement::TransferReceipt>,
    pub(crate) fault: Arc<super::fault_context::FaultCapture>,
    pub prepared: PreparedAnalysis,
    pub snapshot: Arc<SnapshotMetadata>,
    pub open_limits: OpenLimits,
    pub reads: BTreeMap<Address, ByteRead>,
    pub materialization: MaterializationReport,
}
impl FilePreparedAnalysis {
    pub(crate) fn checked_scalar_binding(&self) -> Result<(), crate::investigation::Error> {
        let original = &self.scalar_binding;
        if crate::investigation::request_fingerprint(&self.prepared.request)
            != original.request_fingerprint
        {
            return Err("address-wrap request changed after preparation".into());
        }
        if self.prepared.identity != original.identity
            || self.materialization != original.materialization
            || self.open_limits != original.open_limits
            || self.snapshot.as_ref() != original.snapshot.as_ref()
            || self.fault.metadata.as_ref() != original.snapshot.as_ref()
        {
            return Err("address-wrap preparation identity or metadata changed".into());
        }
        if self.prepared.instructions != original.instructions
            || self.reads != original.reads
            || self.prepared.gaps != original.gaps
        {
            return Err("address-wrap preparation evidence changed".into());
        }
        if self.fault.evidence.digest() != original.fault_digest {
            return Err("address-wrap fault observations changed after capture".into());
        }
        Ok(())
    }

    pub fn composition(&self) -> Option<&crate::bap::composition::Report> {
        self.composition.as_ref()
    }
    pub(crate) fn validate_composition(&self) -> Result<(), crate::bap::Error> {
        if let Some(composition) = &self.composition {
            let original = self
                .original_controls
                .as_ref()
                .ok_or("composition original control capture absent")?;
            let supplied: BTreeMap<_, _> = composition
                .original_controls
                .iter()
                .map(|row| {
                    Ok((
                        crate::bap::core_adapter::address(&row.site)?,
                        row.control.clone(),
                    ))
                })
                .collect::<Result<_, crate::bap::Error>>()?;
            if supplied.len() != composition.original_controls.len() || supplied != **original {
                return Err("composition original control capture changed".into());
            }
            crate::bap::composition::validate(
                composition,
                self.target_resolution
                    .as_ref()
                    .ok_or("composition targets absent")?,
                self.guard_admission
                    .as_ref()
                    .ok_or("composition guards absent")?,
                &self.prepared.request,
            )?;
            if crate::bap::composition::analysis_id(composition)?
                != self.materialization.query_identity
            {
                return Err("composition analysis identity changed".into());
            }
        } else if self.original_controls.is_some()
            || (self.guard_admission.is_some() && self.target_resolution.is_some())
        {
            return Err("paired preparation has no composition seal".into());
        }
        Ok(())
    }
    pub fn guard_admission(&self) -> Option<&guard::Report> {
        self.guard_admission.as_ref()
    }
    pub(crate) fn validate_guard_admission(&self) -> Result<(), crate::bap::Error> {
        let Some(report) = &self.guard_admission else {
            if self.guard_input.is_some()
                || self.guard_snapshot.is_some()
                || [guard::PRODUCER_PROFILE, guard::ADVANCED_PRODUCER_PROFILE]
                    .contains(&self.prepared.identity.ruleset.as_str())
            {
                return Err("guard profile has no proof evidence".into());
            }
            return Ok(());
        };
        let input = self
            .guard_input
            .as_ref()
            .ok_or("guard original input absent")?;
        let snapshot = self
            .guard_snapshot
            .as_ref()
            .ok_or("guard immutable capture absent")?;
        guard::validate_normal_flow_request(input, &self.prepared.request)?;
        if let Some(flow) = &input.normal_flow {
            for receipt in &flow.terminals {
                let va = crate::bap::core_adapter::address(&receipt.site)?;
                let captured = snapshot.read_prefix(va, receipt.bytes_hex.len() / 2)?;
                guard::validate_terminal_capture(receipt, &captured.bytes)?;
                let evidence = self
                    .prepared
                    .instructions
                    .get(&va)
                    .ok_or("terminal capture evidence absent")?;
                if evidence.quality != EffectQuality::Opaque
                    || evidence.rule.as_deref() != Some("captured-normal-terminal/v1")
                    || evidence.semantic.as_ref().is_none_or(|s| {
                        s.status != "normal-flow-terminal"
                            || !s.gaps.iter().any(|g| g == "exception-exit")
                            || !s
                                .gaps
                                .iter()
                                .any(|g| g == "exception-resumption-outside-local-scope")
                            || !s.gaps.iter().any(|g| g == "unsupported-exception-effects")
                    })
                {
                    return Err("terminal capture effects/status changed".into());
                }
            }
        }

        if **input != report.input
            || input.snapshot != self.snapshot.snapshot_id
            || input.artifact_sha256 != self.snapshot.artifact_sha256
            || self.prepared.identity.ruleset != input.producer.projection
        {
            return Err("guard original source or snapshot changed".into());
        }
        let request = &self.prepared.request;
        let roots: Vec<_> = request
            .entry_points
            .iter()
            .map(|a| format!("0x{a:016x}"))
            .collect();
        let seeds: Vec<_> = request
            .slice_seeds
            .iter()
            .map(|a| format!("0x{a:016x}"))
            .collect();
        if input
            .roots
            .iter()
            .map(|r| r.site.clone())
            .collect::<Vec<_>>()
            != roots
            || input.seeds != seeds
            || input.preparation_sha256
                != preparation_digest(
                    &self.materialization.limits,
                    &request.locations,
                    &self.open_limits,
                    &input.policy,
                )?
            || input.query_scope_sha256
                != guard_query_scope(
                    &request.snapshot_id,
                    &AnalysisQuery {
                        entry_points: request.entry_points.clone(),
                        slice_seeds: request.slice_seeds.clone(),
                    },
                    &self.materialization.limits,
                    &input.activation,
                    &input.roots,
                )?
        {
            return Err("guard query or preparation premises changed".into());
        }
        let options = PreparationOptions::default();
        if options.catalogue.locations() != request.locations {
            return Err("guard catalogue changed".into());
        }
        for source in &input.sites {
            let va = crate::bap::core_adapter::address(&source.site)?;
            let evidence = self
                .prepared
                .instructions
                .get(&va)
                .ok_or("guard site evidence absent")?;
            let captured = snapshot.read_prefix(va, 15)?;
            let semantic_source = evidence.semantic.as_ref();
            if self.reads.get(&va) != Some(&captured)
                || source.bytes_hex
                    != evidence
                        .bytes
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
                || !captured.bytes.starts_with(&evidence.bytes)
                || (!source.bytes_hex.is_empty() && semantic_source.is_none())
                || semantic_source.is_some_and(|s| {
                    s.backend != "bap-x86-legacy" || s.fallback.is_some() || s.ast_sha256.is_none()
                })
                || evidence
                    .semantic
                    .as_ref()
                    .and_then(|s| s.ast_sha256.as_ref())
                    .is_some_and(|hash| *hash != crate::reports::sha256(source.ast.as_bytes()))
                || evidence.semantic.as_ref().is_some_and(|s| {
                    s.projection != input.producer.projection
                        || s.helper_sha256 != input.producer.helper_sha256
                        || s.runtime_sha256 != input.producer.runtime_sha256
                })
            {
                return Err("guard captured bytes or original BIL changed".into());
            }
            let actual = request
                .instructions
                .get(&va)
                .ok_or("guard summary absent")?;
            if let Some(pending) = guard::recognize_pending_for_input(input, source)? {
                let decision = report.guards.iter().find(|g| g.site == pending.site);
                let residual = decision
                    .map(|d| d.residual.as_str())
                    .or(report.stop.as_deref())
                    .ok_or("guard decision absent")?;
                let mut expected = crate::llvm_mc::PreparedSite {
                    instruction: actual.clone(),
                    evidence: evidence.clone(),
                    gaps: Vec::new(),
                    decodable: true,
                    complete_capture: true,
                };
                expected.instruction.kind = InstructionKind::Ordinary;
                expected.instruction.fall = source
                    .control
                    .fall
                    .iter()
                    .map(|s| crate::bap::core_adapter::address(s))
                    .collect::<Result<_, _>>()?;
                expected.instruction.targets.clear();
                expected.instruction.complete = source.control.complete;
                crate::bap::Backend::finalize_guard(
                    &mut expected,
                    va,
                    decision.and_then(|d| d.normal_ast.as_deref()),
                    residual,
                    &options,
                )?;
                if expected.instruction != *actual
                    || expected.decodable != request.decodable.contains(&va)
                    || expected.evidence.quality != evidence.quality
                    || expected.evidence.rule != evidence.rule
                    || expected.evidence.control != evidence.control
                    || evidence.decoder_control != Some(InstructionKind::Ordinary)
                    || expected
                        .evidence
                        .semantic
                        .as_ref()
                        .map(|s| (&s.status, &s.memory_accesses))
                        != evidence
                            .semantic
                            .as_ref()
                            .map(|s| (&s.status, &s.memory_accesses))
                {
                    return Err("guard normal selection or stopped effects changed".into());
                }
            } else if guard::CandidateControl::from_instruction(actual) != source.control {
                return Err("guard candidate control changed".into());
            }
        }
        guard::replay_report(input, report)?;
        let hash = normalized_request_digest(request)?;
        let mut checked = report.clone();
        guard::bind_final_request(input, &mut checked, &hash)?;
        let analysis_id = guard::analysis_id(&checked)?;
        if checked != *report
            || (self.composition.is_none() && analysis_id != self.materialization.query_identity)
        {
            return Err("guard final request or analysis identity changed".into());
        }
        self.validate_composition()?;
        Ok(())
    }
    pub fn target_resolution(&self) -> Option<&crate::bap::target_resolution::Report> {
        self.target_resolution.as_ref()
    }
    pub(crate) fn validate_target_resolution(&self) -> Result<(), crate::bap::Error> {
        let Some(report) = &self.target_resolution else {
            if self.composition.is_some() {
                return Err("composition target report absent".into());
            }
            return Ok(());
        };
        if self.prepared.identity.ruleset == "bap-bit-provenance-v9"
            || self.prepared.instructions.values().any(|site| {
                site.semantic
                    .as_ref()
                    .is_some_and(|semantic| semantic.projection == "bap-bit-provenance-v9")
            })
        {
            return Err("source flag extension does not admit target resolution".into());
        }
        if crate::bap::advanced_projection(&self.prepared.identity.ruleset)
            != crate::bap::target_resolution::is_advanced(report)
        {
            return Err("target report does not match source producer generation".into());
        }
        if report.snapshot != self.snapshot.snapshot_id
            || report.artifact_sha256 != self.snapshot.artifact_sha256
        {
            return Err("resolver snapshot mismatch".into());
        }
        let snapshot = self
            .target_snapshot
            .as_ref()
            .ok_or("resolver immutable snapshot absent")?;
        for read in &report.data_reads {
            let address = u64::from_str_radix(read.address.trim_start_matches("0x"), 16)?;
            if *read != control_data_read(snapshot, address, read.requested)? {
                return Err("resolver captured data or contributors changed".into());
            }
        }
        for transfer in &report.transfers {
            let va = u64::from_str_radix(transfer.site.trim_start_matches("0x"), 16)?;
            let evidence = self
                .prepared
                .instructions
                .get(&va)
                .ok_or("resolver evidence absent")?;
            if transfer.bytes_hex
                != evidence
                    .bytes
                    .iter()
                    .map(|b| format!("{b:02x}"))
                    .collect::<String>()
                || evidence
                    .semantic
                    .as_ref()
                    .and_then(|v| v.ast_sha256.as_ref())
                    != Some(&transfer.ast_sha256)
            {
                return Err("resolver semantic source mismatch".into());
            }
        }
        let candidate = self
            .composition
            .as_ref()
            .map(crate::bap::composition::candidate_request)
            .transpose()?;
        let replay = candidate.as_ref().unwrap_or(&self.prepared.request);
        crate::bap::target_resolution::validate(
            report,
            &replay.instructions,
            &replay.entry_points,
        )?;
        for row in &report.resolutions {
            let va = u64::from_str_radix(row.site.trim_start_matches("0x"), 16)?;
            let i = self
                .prepared
                .request
                .instructions
                .get(&va)
                .ok_or("resolver instruction absent")?;
            let targets: AddressSet = row
                .targets
                .iter()
                .map(|v| u64::from_str_radix(v.trim_start_matches("0x"), 16))
                .collect::<Result<_, _>>()?;
            if i.kind != InstructionKind::Indirect
                || i.targets != targets
                || i.complete != row.complete
            {
                return Err("resolver normalized target mismatch".into());
            }
        }
        self.validate_composition()?;
        Ok(())
    }
}

pub(crate) fn query_identity(
    snapshot: &str,
    query: &AnalysisQuery,
    limits: &PrepareLimits,
    target_limits: Option<&crate::bap::target_resolution::Limits>,
) -> Result<String, PreparationError> {
    use sha2::{Digest, Sha256};
    let mut digest = Sha256::new();
    digest.update(b"ariadne-minidump-query-v1\0");
    digest.update(snapshot.as_bytes());
    for set in [&query.entry_points, &query.slice_seeds] {
        digest.update((set.len() as u64).to_le_bytes());
        for a in set {
            digest.update(a.to_le_bytes());
        }
    }
    for n in [
        limits.max_starts,
        limits.max_candidates,
        limits.max_prefix_bytes,
        limits.max_decoder_batches,
        limits.batch_size,
    ] {
        digest.update((n as u64).to_le_bytes());
    }
    if let Some(limits) = target_limits {
        digest.update(crate::bap::target_resolution::PROFILE.as_bytes());
        digest.update(crate::bap::target_resolution::MEMORY_PREMISE.as_bytes());
        digest.update(
            serde_json::to_vec(limits).map_err(|e| PreparationError::Backend(e.to_string()))?,
        );
    }
    Ok(format!("{:x}", digest.finalize()))
}

pub(crate) fn control_data_read(
    snapshot: &FileSnapshot,
    address: u64,
    length: usize,
) -> Result<crate::bap::target_resolution::DataRead, crate::bap::Error> {
    use crate::bap::target_resolution::{Contributor, DataRead, Span};
    let read = snapshot.read_prefix(address, length)?;
    Ok(DataRead {
        address: format!("0x{address:016x}"),
        requested: length,
        bytes_hex: read.bytes.iter().map(|b| format!("{b:02x}")).collect(),
        spans: read
            .spans
            .iter()
            .map(|span| Span {
                address: format!("0x{:016x}", span.address),
                length: span.length,
                contributors: span
                    .contributors
                    .iter()
                    .map(|c| Contributor {
                        stream: c.stream,
                        entry: c.entry,
                        file_offset: c.file_offset,
                    })
                    .collect(),
            })
            .collect(),
        conflict_sources: read
            .conflict_sources
            .iter()
            .map(|c| Contributor {
                stream: c.stream,
                entry: c.entry,
                file_offset: c.file_offset,
            })
            .collect(),
        stop: format!("{:?}", read.stop),
    })
}
#[derive(Debug)]
pub enum PreparationError {
    Input(InputError),
    Decoder(AdapterError),
    InvalidQuery(&'static str),
    Backend(String),
    LimitReached {
        reason: &'static str,
        progress: Box<MaterializationReport>,
    },
}
impl fmt::Display for PreparationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Input(e) => write!(f, "{e}"),
            Self::Decoder(e) => write!(f, "{e}"),
            Self::InvalidQuery(e) => write!(f, "invalid query: {e}"),
            Self::Backend(e) => write!(f, "semantic backend: {e}"),
            Self::LimitReached { reason, .. } => write!(f, "materialization limit: {reason}"),
        }
    }
}
impl std::error::Error for PreparationError {}
impl From<InputError> for PreparationError {
    fn from(e: InputError) -> Self {
        Self::Input(e)
    }
}
impl From<AdapterError> for PreparationError {
    fn from(e: AdapterError) -> Self {
        Self::Decoder(e)
    }
}
fn limit(reason: &'static str, p: &MaterializationReport) -> PreparationError {
    PreparationError::LimitReached {
        reason,
        progress: Box::new(p.clone()),
    }
}

fn edges(instruction: &Instruction) -> Vec<(Address, EdgeKind)> {
    let mut result = Vec::new();
    let (fall, targets) = match instruction.kind {
        InstructionKind::Ordinary => (Some(EdgeKind::Next), None),
        InstructionKind::Conditional => (Some(EdgeKind::Fallthrough), Some(EdgeKind::Taken)),
        InstructionKind::Jump => (None, Some(EdgeKind::Jump)),
        InstructionKind::Indirect => (None, Some(EdgeKind::Indirect)),
        InstructionKind::Call => (Some(EdgeKind::Summary), Some(EdgeKind::Call)),
        InstructionKind::Return | InstructionKind::Stop => (None, None),
    };
    if let Some(kind) = fall {
        result.extend(instruction.fall.iter().map(|a| (*a, kind)));
    }
    if let Some(kind) = targets {
        result.extend(instruction.targets.iter().map(|a| (*a, kind)));
    }
    result
}
fn placeholder() -> InstructionEvidence {
    InstructionEvidence {
        bytes: Vec::new(),
        source: ByteSource::Unavailable,
        opcode: None,
        length: 0,
        operands: Vec::new(),
        rule: None,
        control: None,
        quality: EffectQuality::Unavailable,
        undefined_flags: LocationSet::new(),
        decoder_record: None,
        decoded_address: None,
        decoder_control: None,
        semantic: None,
    }
}

enum PreparationExtension {
    None,
    Refinement,
    TargetResolution(crate::bap::target_resolution::Limits),
    GuardAdmission(GuardPreparation),
    GuardAndTargets(GuardPreparation, crate::bap::target_resolution::Limits),
    QuestionTargets(
        GuardPreparation,
        crate::bap::target_resolution::Limits,
        crate::bap::target_resolution::QuestionTargetSchedule,
    ),
}

pub(crate) struct GuardPreparation {
    pub limits: guard::Limits,
    pub activation: guard::Activation,
    pub roots: Vec<guard::Root>,
    pub premises: Vec<guard::Premise>,
    pub query_scope_sha256: String,
    pub producer: Option<guard::Producer>,
}

pub(crate) fn guard_query_scope(
    snapshot: &str,
    query: &AnalysisQuery,
    limits: &PrepareLimits,
    activation: &guard::Activation,
    roots: &[guard::Root],
) -> Result<String, PreparationError> {
    let old = query_identity(snapshot, query, limits, None)?;
    Ok(crate::reports::sha256(
        &serde_json::to_vec(&(old, activation, roots))
            .map_err(|e| PreparationError::Backend(e.to_string()))?,
    ))
}

fn preparation_digest(
    limits: &PrepareLimits,
    locations: &LocationSet,
    open_limits: &OpenLimits,
    profile: &str,
) -> Result<String, crate::bap::Error> {
    Ok(crate::reports::sha256(&serde_json::to_vec(
        &serde_json::json!({
            "limits": limits, "locations": locations,
            "open_limits": {
                "max_file_bytes": open_limits.max_file_bytes,
                "max_streams": open_limits.max_streams,
                "max_records": open_limits.max_records,
                "max_metadata_bytes": open_limits.max_metadata_bytes,
                "max_capture_ranges": open_limits.max_capture_ranges,
                "max_overlap": open_limits.max_overlap,
                "max_read_bytes": open_limits.max_read_bytes,
            },
            "profile": profile,
        }),
    )?))
}

fn normalized_request_digest(request: &AnalysisRequest) -> Result<String, crate::bap::Error> {
    Ok(crate::reports::sha256(&serde_json::to_vec(
        &crate::bap::core_adapter::encode_request(request)?,
    )?))
}

fn request_from_sites(
    snapshot: &str,
    query: &AnalysisQuery,
    referenced: &AddressSet,
    options: &PreparationOptions,
    sites: &BTreeMap<Address, crate::llvm_mc::PreparedSite>,
) -> AnalysisRequest {
    let mut request = AnalysisRequest {
        snapshot_id: snapshot.into(),
        addresses: referenced.clone(),
        locations: options.catalogue.locations(),
        entry_points: query.entry_points.clone(),
        slice_seeds: query.slice_seeds.clone(),
        input_kind: InputKind::Dump,
        ..AnalysisRequest::default()
    };
    for (&va, site) in sites {
        request.instructions.insert(va, site.instruction.clone());
        if site.decodable {
            request.decodable.insert(va);
        }
        if site.complete_capture {
            request.captured.insert(va);
        }
    }
    for &va in referenced {
        request.instructions.entry(va).or_default();
    }
    request
}

/// Includes completeness, barriers and transfer facts rather than merely
/// newly added edges. The immutable scope is checked separately by its owner.
fn candidate_fingerprint(
    sites: &BTreeMap<Address, crate::llvm_mc::PreparedSite>,
    sources: &BTreeMap<Address, guard::CandidateSite>,
    transfers: Option<&BTreeMap<Address, crate::bap::target_resolution::Transfer>>,
) -> Result<String, PreparationError> {
    let rows: Vec<_> = sites
        .iter()
        .map(|(&va, site)| {
            let i = &site.instruction;
            serde_json::json!({
                "site": format!("0x{va:016x}"),
                "control": guard::CandidateControl::from_instruction(i),
                "uses": i.uses, "may_defs": i.may_defs, "must_defs": i.must_defs,
                "decodable": site.decodable, "captured": site.complete_capture,
                "bytes": site.evidence.bytes,
                "ast_sha256": site.evidence.semantic.as_ref().and_then(|s| s.ast_sha256.as_ref()),
            })
        })
        .collect();
    let bytes = serde_json::to_vec(&(rows, sources, transfers))
        .map_err(|e| PreparationError::Backend(e.to_string()))?;
    Ok(crate::reports::sha256(&bytes))
}

fn candidate_fingerprint_with_terminals(
    sites: &BTreeMap<Address, crate::llvm_mc::PreparedSite>,
    sources: &BTreeMap<Address, guard::CandidateSite>,
    transfers: Option<&BTreeMap<Address, crate::bap::target_resolution::Transfer>>,
    terminals: &BTreeMap<Address, guard::TerminalReceipt>,
) -> Result<String, PreparationError> {
    let previous = candidate_fingerprint(sites, sources, transfers)?;
    let bytes = serde_json::to_vec(&(previous, terminals))
        .map_err(|e| PreparationError::Backend(e.to_string()))?;
    Ok(crate::reports::sha256(&bytes))
}

fn advance_candidate_epoch(
    fingerprint: String,
    previous: &mut Option<String>,
    epoch: &mut u64,
) -> Result<(), PreparationError> {
    if previous.as_ref() != Some(&fingerprint) {
        *epoch = epoch
            .checked_add(1)
            .ok_or(PreparationError::InvalidQuery("candidate epoch overflow"))?;
        *previous = Some(fingerprint);
    }
    Ok(())
}

fn check_guard_graph_limits(
    sites: &BTreeMap<Address, crate::llvm_mc::PreparedSite>,
    setup: &GuardPreparation,
    report: &MaterializationReport,
) -> Result<(), PreparationError> {
    if sites.len() > setup.limits.max_sites {
        return Err(limit("guard candidate sites", report));
    }
    let edge_count = sites
        .values()
        .try_fold(0usize, |n, site| {
            n.checked_add(edges(&site.instruction).len())
        })
        .ok_or_else(|| limit("guard candidate edges", report))?;
    if edge_count > setup.limits.max_edges {
        return Err(limit("guard candidate edges", report));
    }
    Ok(())
}

/// Own the resolver's fixed point separately from instruction-byte discovery.
/// Graph expansion is monotone; old path witnesses remain valid, but their
/// coverage certificates must be checked against the expanded graph.
struct TargetResolutionCoordinator<'a> {
    limits: &'a crate::bap::target_resolution::Limits,
    transfers: BTreeMap<Address, crate::bap::target_resolution::Transfer>,
    report: Option<crate::bap::target_resolution::Report>,
    rounds: usize,
    candidate_mode: bool,
    question_schedule: Option<crate::bap::target_resolution::QuestionTargetSchedule>,
}

impl<'a> TargetResolutionCoordinator<'a> {
    fn new(limits: &'a crate::bap::target_resolution::Limits) -> Self {
        Self {
            limits,
            transfers: BTreeMap::new(),
            report: None,
            rounds: 0,
            candidate_mode: false,
            question_schedule: None,
        }
    }

    fn advance(
        &mut self,
        snapshot: &FileSnapshot,
        roots: &AddressSet,
        sites: &mut BTreeMap<Address, crate::llvm_mc::PreparedSite>,
        pending: &mut AddressSet,
        materialization: &mut MaterializationReport,
    ) -> Result<bool, PreparationError> {
        use crate::bap::target_resolution as resolver;
        let mut instructions: BTreeMap<_, _> = sites
            .iter()
            .map(|(&a, s)| (a, s.instruction.clone()))
            .collect();
        // The published request retains every represented endpoint, including
        // non-followed call targets and slice seeds that are not discovery
        // roots. Bind target proofs to that same domain from the outset.
        for &address in &materialization.referenced {
            instructions.entry(address).or_default();
        }
        let round_limit = self.rounds >= self.limits.max_rounds;
        let mut resolved = if round_limit && self.report.is_some() {
            self.report.take().expect("previous report checked")
        } else {
            let mut limits = self.limits.clone();
            if round_limit {
                limits.max_steps = 0;
            }
            if let Some(schedule) = self
                .question_schedule
                .as_ref()
                .filter(|_| self.candidate_mode)
            {
                resolver::resolve_question(
                    &snapshot.metadata.snapshot_id,
                    &snapshot.metadata.artifact_sha256,
                    &instructions,
                    roots,
                    &self.transfers,
                    &limits,
                    schedule,
                    |a, n| control_data_read(snapshot, a, n),
                )
            } else {
                let resolve = if self.candidate_mode {
                    resolver::resolve_candidate
                } else {
                    resolver::resolve
                };
                resolve(
                    &snapshot.metadata.snapshot_id,
                    &snapshot.metadata.artifact_sha256,
                    &instructions,
                    roots,
                    &self.transfers,
                    &limits,
                    |a, n| control_data_read(snapshot, a, n),
                )
            }
            .map_err(|e| PreparationError::Backend(e.to_string()))?
        };
        resolved.limits = self.limits.clone();
        if round_limit {
            // The empty evidence-limit envelope is deliberately allowed even
            // when the caller cannot afford the fixed receipt header.
            if resolved.stop.as_deref() != Some("resolution-evidence-limit") {
                Self::downgrade(&mut resolved, "discovery-round-limit");
            }
        } else {
            self.rounds += 1;
            if let Some(previous) = self.report.take() {
                resolved = Self::retain_witnesses(previous, resolved, &instructions, roots)?;
            }
        }
        resolved.graph_sha256 = resolver::report_graph_digest(&resolved, &instructions, roots)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        resolver::validate(&resolved, &instructions, roots)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        let stopped = round_limit || resolved.stop.is_some();
        let before: BTreeMap<_, _> = sites
            .iter()
            .map(|(&va, site)| (va, site.instruction.clone()))
            .collect();
        if stopped {
            for site in sites.values_mut() {
                if site.instruction.kind == InstructionKind::Indirect {
                    site.instruction.complete = false;
                }
            }
        }
        for row in &resolved.resolutions {
            let address = parse_target_address(&row.site)?;
            let site = sites
                .get_mut(&address)
                .ok_or(PreparationError::InvalidQuery("resolver site absent"))?;
            site.instruction.complete = row.complete;
            for value in &row.targets {
                let target = parse_target_address(value)?;
                site.instruction.targets.insert(target);
                materialization.referenced.insert(target);
                if materialization.referenced.len() > materialization.limits.max_candidates {
                    return Err(limit("candidate addresses", materialization));
                }
                if !materialization.attempted.contains(&target) {
                    pending.insert(target);
                }
            }
        }
        // Completeness downgrades/upgrades are proof-relevant even when no
        // destination is added. Such changes require another closure round.
        let changed = before.iter().any(|(va, old)| sites[va].instruction != *old);
        self.report = Some(resolved);
        Ok(if self.candidate_mode {
            pending.is_empty() && (stopped || !changed)
        } else {
            stopped || (!changed && pending.is_empty())
        })
    }

    fn downgrade(report: &mut crate::bap::target_resolution::Report, reason: &str) {
        crate::bap::target_resolution::invalidate_loop_coverage(report, reason);
        report.stop = Some(reason.into());
        for row in &mut report.resolutions {
            row.complete = false;
        }
    }

    fn retain_witnesses(
        mut previous: crate::bap::target_resolution::Report,
        mut current: crate::bap::target_resolution::Report,
        instructions: &BTreeMap<Address, Instruction>,
        roots: &AddressSet,
    ) -> Result<crate::bap::target_resolution::Report, PreparationError> {
        use crate::bap::target_resolution as resolver;
        let missing_previous_targets = previous.resolutions.iter().any(|old| {
            old.targets.iter().any(|target| {
                !current
                    .resolutions
                    .iter()
                    .any(|new| new.site == old.site && new.targets.contains(target))
            })
        });
        if !missing_previous_targets {
            return Ok(current);
        }

        // New candidates are admitted atomically with their complete receipts.
        // If their union does not fit, retain the previously admitted payload
        // and stop without adding edges that would lack a surviving witness.
        resolver::invalidate_loop_coverage(&mut previous, "loop-coverage-graph-changed");
        previous.graph_sha256 = current.graph_sha256.clone();
        Self::downgrade(&mut previous, "resolution-retention-limit");
        if current.stop.is_none() {
            for old in &previous.resolutions {
                if let Some(new) = current.resolutions.iter_mut().find(|r| r.site == old.site) {
                    let missing = old.targets.iter().any(|t| !new.targets.contains(t));
                    if !missing {
                        continue;
                    }
                    new.complete = false;
                    // A merged prefix domain needs fresh coverage evidence.
                    if new.coverage.is_some() {
                        new.coverage = Some(resolver::CoverageEvidence::ExistingPrefixTree {
                            path_receipt_refs: Vec::new(),
                        });
                    }
                    for old_path in &old.paths {
                        if let Some(path) = new.paths.iter_mut().find(|path| {
                            path.root == old_path.root
                                && path.reverse_path == old_path.reverse_path
                                && path.reverse_edges == old_path.reverse_edges
                        }) {
                            let mut expected = old_path.clone();
                            expected.entries = path.entries.clone();
                            if expected != *path {
                                return Err(PreparationError::InvalidQuery(
                                    "resolver path semantics changed during discovery",
                                ));
                            }
                            for entry in &old_path.entries {
                                if !path.entries.contains(entry) {
                                    path.entries.push(entry.clone());
                                }
                            }
                            path.entries.sort_by_key(|entry| entry.index);
                        } else {
                            new.paths.push(old_path.clone());
                        }
                    }
                    new.targets.extend(old.targets.iter().cloned());
                    new.targets.sort();
                    new.targets.dedup();
                } else {
                    current.resolutions.push(old.clone());
                }
            }
            current.resolutions.sort_by(|a, b| a.site.cmp(&b.site));
            for row in &mut current.resolutions {
                if let Some(resolver::CoverageEvidence::ExistingPrefixTree { path_receipt_refs }) =
                    &mut row.coverage
                {
                    *path_receipt_refs = (0..row.paths.len()).collect();
                }
            }
            for read in &previous.data_reads {
                if !current.data_reads.contains(read) {
                    current.data_reads.push(read.clone());
                }
            }
            current
                .data_reads
                .sort_by(|a, b| (&a.address, a.requested).cmp(&(&b.address, b.requested)));
            for transfer in &previous.transfers {
                if !current.transfers.contains(transfer) {
                    current.transfers.push(transfer.clone());
                }
            }
            current.transfers.sort_by(|a, b| a.site.cmp(&b.site));
            if Self::within_retention_budget(&current)? {
                // Only capacity exhaustion permits retaining the old payload.
                // A fitting merge with invalid evidence is a hard error.
                resolver::validate(&current, instructions, roots)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?;
                return Ok(current);
            }
        }
        resolver::validate(&previous, instructions, roots)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        Ok(previous)
    }

    fn within_retention_budget(
        report: &crate::bap::target_resolution::Report,
    ) -> Result<bool, PreparationError> {
        let targets: BTreeSet<_> = report.resolutions.iter().flat_map(|r| &r.targets).collect();
        let reads: BTreeSet<_> = report
            .data_reads
            .iter()
            .map(|read| (&read.address, read.requested))
            .collect();
        let bytes = reads
            .iter()
            .try_fold(0usize, |n, (_, size)| n.checked_add(*size));
        Ok(targets.len() <= report.limits.max_targets
            && bytes.is_some_and(|n| n <= report.limits.max_read_bytes)
            && crate::bap::target_resolution::within_evidence_budget(report)
                .map_err(|e| PreparationError::Backend(e.to_string()))?)
    }
}

fn parse_target_address(address: &str) -> Result<Address, PreparationError> {
    u64::from_str_radix(address.trim_start_matches("0x"), 16)
        .map_err(|e| PreparationError::Backend(e.to_string()))
}

impl FileSnapshot {
    /// Acquire only root-reachable local instruction starts, then freeze inputs.
    /// Seeds do not become roots. Exhaustion returns diagnostics, never a partial
    /// request mislabeled as a completed construction.
    pub fn prepare(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        options: &PreparationOptions,
        limits: PrepareLimits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        self.prepare_with_bap(
            query,
            decoder,
            &crate::bap::Config::from_env(),
            options,
            limits,
        )
    }

    /// The sole production semantic backend; the decoder is an independent reference.
    pub fn prepare_with_bap(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::None,
        )
    }

    /// Opt-in transfer evidence; discovery, query identity and effects are unchanged.
    pub fn prepare_with_bap_refinement(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::Refinement,
        )
    }

    /// Opt-in predicate checking with no entry residue assumptions. Each root
    /// starts at top; selecting this profile alone cannot prove alignment.
    pub fn prepare_with_bap_guard_admission(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        guard_limits: guard::Limits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        let activation = guard::Activation {
            thread_id: 0,
            frame_activation: "explicit-local-query/v1".into(),
        };
        let roots: Vec<_> = query
            .entry_points
            .iter()
            .map(|a| guard::Root {
                site: format!("0x{a:016x}"),
                function_entry: false,
                anchor_sha256: crate::reports::sha256(
                    format!("explicit-root/v1:{}:{a:016x}", self.metadata.snapshot_id).as_bytes(),
                ),
            })
            .collect();
        let query_scope_sha256 = guard_query_scope(
            &self.metadata.snapshot_id,
            query,
            &limits,
            &activation,
            &roots,
        )?;
        self.prepare_bap_guarded(
            query,
            decoder,
            config,
            options,
            limits,
            GuardPreparation {
                limits: guard_limits,
                activation,
                roots,
                premises: Vec::new(),
                query_scope_sha256,
                producer: None,
            },
        )
    }

    pub(crate) fn prepare_bap_guarded(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        guard: GuardPreparation,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        guard
            .limits
            .validate()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::GuardAdmission(guard),
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn prepare_bap_guarded_targets(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        guard: GuardPreparation,
        target_limits: crate::bap::target_resolution::Limits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        guard
            .limits
            .validate()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        target_limits
            .validate()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::GuardAndTargets(guard, target_limits),
        )
    }

    /// Opt-in captured control data semantics; roots and slice seeds are unchanged.
    pub fn prepare_with_bap_target_resolution(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        target_limits: crate::bap::target_resolution::Limits,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        target_limits
            .validate()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::TargetResolution(target_limits),
        )
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn prepare_bap_question_targets(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        guard: GuardPreparation,
        target_limits: crate::bap::target_resolution::Limits,
        schedule: crate::bap::target_resolution::QuestionTargetSchedule,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        self.prepare_bap(
            query,
            decoder,
            config,
            options,
            limits,
            PreparationExtension::QuestionTargets(guard, target_limits, schedule),
        )
    }

    fn prepare_bap(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        extension: PreparationExtension,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        let mut question_schedule = None;
        let (refinement, target_limits, mut guard_setup) = match extension {
            PreparationExtension::None => (false, None, None),
            PreparationExtension::Refinement => (true, None, None),
            PreparationExtension::TargetResolution(limits) => (false, Some(limits), None),
            PreparationExtension::GuardAdmission(setup) => (false, None, Some(setup)),
            PreparationExtension::QuestionTargets(setup, limits, schedule) => {
                question_schedule = Some(schedule);
                (false, Some(limits), Some(setup))
            }
            PreparationExtension::GuardAndTargets(setup, limits) => {
                (false, Some(limits), Some(setup))
            }
        };
        if config.source_extension.is_some()
            && config.source_extension_mode != crate::bap::SourceExtensionMode::Advanced
            && (refinement || target_limits.is_some() || guard_setup.is_some())
        {
            return Err(PreparationError::Backend(
                "source flag extension does not admit guards, target resolution or refinement"
                    .into(),
            ));
        }
        let mut backend = crate::bap::Backend::new(config.clone(), decoder)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        backend
            .set_query_site_limit(limits.max_starts)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        if refinement {
            backend.enable_refinement();
        }
        if target_limits.is_some() {
            backend.enable_target_resolution();
        }
        if let Some(setup) = &mut guard_setup {
            backend.enable_guard_admission();
            setup.producer = Some(backend.guard_producer());
        }
        let mut prepared = self.prepare_materialization_with_terminals(
            query,
            options,
            limits,
            target_limits.as_ref(),
            guard_setup.as_ref(),
            question_schedule.as_ref(),
            |s, c, o, t| {
                let batch = backend
                    .prepare(s, c, o, t)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?;
                Ok((
                    batch,
                    backend.take_target_transfers(),
                    backend.take_guard_sites(),
                    backend.take_terminal_receipts(),
                ))
            },
        )?;
        prepared.refinement = backend.take_refinement();
        backend
            .finish()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        prepared
            .validate_target_resolution()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        prepared
            .validate_guard_admission()
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        Ok(prepared)
    }

    /// Backend-neutral materialization. Reader-owned captured bytes, local
    /// discovery, query limits and evidence stay identical across preparers.
    pub fn prepare_with_preparer<F>(
        &self,
        query: &AnalysisQuery,
        options: &PreparationOptions,
        limits: PrepareLimits,
        mut preparer: F,
    ) -> Result<FilePreparedAnalysis, PreparationError>
    where
        F: FnMut(
            &str,
            &BTreeMap<Address, Option<Vec<u8>>>,
            &PreparationOptions,
            crate::llvm_mc::DecoderTarget,
        ) -> Result<crate::llvm_mc::PreparedBatch, PreparationError>,
    {
        self.prepare_materialization(query, options, limits, None, |s, c, o, t| {
            preparer(s, c, o, t).map(|batch| (batch, BTreeMap::new()))
        })
    }

    fn prepare_materialization<F>(
        &self,
        query: &AnalysisQuery,
        options: &PreparationOptions,
        limits: PrepareLimits,
        target_limits: Option<&crate::bap::target_resolution::Limits>,
        mut preparer: F,
    ) -> Result<FilePreparedAnalysis, PreparationError>
    where
        F: FnMut(
            &str,
            &BTreeMap<Address, Option<Vec<u8>>>,
            &PreparationOptions,
            crate::llvm_mc::DecoderTarget,
        ) -> Result<
            (
                crate::llvm_mc::PreparedBatch,
                BTreeMap<Address, crate::bap::target_resolution::Transfer>,
            ),
            PreparationError,
        >,
    {
        self.prepare_materialization_guarded_scheduled(
            query,
            options,
            limits,
            target_limits,
            None,
            None,
            |s, c, o, t| {
                preparer(s, c, o, t).map(|(batch, transfers)| (batch, transfers, BTreeMap::new()))
            },
        )
    }

    #[cfg(test)]
    fn prepare_materialization_guarded<F>(
        &self,
        query: &AnalysisQuery,
        options: &PreparationOptions,
        limits: PrepareLimits,
        target_limits: Option<&crate::bap::target_resolution::Limits>,
        guard_setup: Option<&GuardPreparation>,
        preparer: F,
    ) -> Result<FilePreparedAnalysis, PreparationError>
    where
        F: FnMut(
            &str,
            &BTreeMap<Address, Option<Vec<u8>>>,
            &PreparationOptions,
            crate::llvm_mc::DecoderTarget,
        ) -> Result<
            (
                crate::llvm_mc::PreparedBatch,
                BTreeMap<Address, crate::bap::target_resolution::Transfer>,
                BTreeMap<Address, guard::CandidateSite>,
            ),
            PreparationError,
        >,
    {
        self.prepare_materialization_guarded_scheduled(
            query,
            options,
            limits,
            target_limits,
            guard_setup,
            None,
            preparer,
        )
    }

    #[allow(clippy::too_many_arguments)]
    fn prepare_materialization_guarded_scheduled<F>(
        &self,
        query: &AnalysisQuery,
        options: &PreparationOptions,
        limits: PrepareLimits,
        target_limits: Option<&crate::bap::target_resolution::Limits>,
        guard_setup: Option<&GuardPreparation>,
        question_schedule: Option<&crate::bap::target_resolution::QuestionTargetSchedule>,
        mut preparer: F,
    ) -> Result<FilePreparedAnalysis, PreparationError>
    where
        F: FnMut(
            &str,
            &BTreeMap<Address, Option<Vec<u8>>>,
            &PreparationOptions,
            crate::llvm_mc::DecoderTarget,
        ) -> Result<
            (
                crate::llvm_mc::PreparedBatch,
                BTreeMap<Address, crate::bap::target_resolution::Transfer>,
                BTreeMap<Address, guard::CandidateSite>,
            ),
            PreparationError,
        >,
    {
        self.prepare_materialization_with_terminals(
            query,
            options,
            limits,
            target_limits,
            guard_setup,
            question_schedule,
            |s, c, o, t| {
                preparer(s, c, o, t)
                    .map(|(batch, transfers, sources)| (batch, transfers, sources, BTreeMap::new()))
            },
        )
    }

    #[allow(clippy::too_many_arguments)]
    fn prepare_materialization_with_terminals<F>(
        &self,
        query: &AnalysisQuery,
        options: &PreparationOptions,
        limits: PrepareLimits,
        target_limits: Option<&crate::bap::target_resolution::Limits>,
        guard_setup: Option<&GuardPreparation>,
        question_schedule: Option<&crate::bap::target_resolution::QuestionTargetSchedule>,
        mut preparer: F,
    ) -> Result<FilePreparedAnalysis, PreparationError>
    where
        F: FnMut(
            &str,
            &BTreeMap<Address, Option<Vec<u8>>>,
            &PreparationOptions,
            crate::llvm_mc::DecoderTarget,
        ) -> Result<
            (
                crate::llvm_mc::PreparedBatch,
                BTreeMap<Address, crate::bap::target_resolution::Transfer>,
                BTreeMap<Address, guard::CandidateSite>,
                BTreeMap<Address, guard::TerminalReceipt>,
            ),
            PreparationError,
        >,
    {
        if query.entry_points.is_empty() || limits.batch_size == 0 {
            return Err(PreparationError::InvalidQuery(
                "nonempty roots and positive batch_size required",
            ));
        }
        if self.limits.max_read_bytes < 15 {
            return Err(PreparationError::InvalidQuery(
                "snapshot read limit must allow 15 instruction bytes",
            ));
        }
        if let Some(setup) = guard_setup
            && setup.query_scope_sha256
                != guard_query_scope(
                    &self.metadata.snapshot_id,
                    query,
                    &limits,
                    &setup.activation,
                    &setup.roots,
                )?
        {
            return Err(PreparationError::InvalidQuery(
                "guard premise scope differs from actual query or limits",
            ));
        }
        let query_identity =
            query_identity(&self.metadata.snapshot_id, query, &limits, target_limits)?;
        let mut report = MaterializationReport {
            entry_points: query.entry_points.clone(),
            slice_seeds: query.slice_seeds.clone(),
            limits: limits.clone(),
            referenced: query
                .entry_points
                .union(&query.slice_seeds)
                .copied()
                .collect(),
            query_identity,
            ..MaterializationReport::default()
        };
        if report.referenced.len() > limits.max_candidates {
            return Err(limit("candidate addresses", &report));
        }
        let mut pending = query.entry_points.clone();
        let mut reads = BTreeMap::new();
        let mut sites = BTreeMap::new();
        let mut guard_sites = BTreeMap::new();
        let mut terminal_receipts = BTreeMap::new();
        let mut guard_bytes = 0usize;
        let mut identity = None;
        let mut resolver = target_limits.map(TargetResolutionCoordinator::new);
        if let Some(r) = &mut resolver {
            r.question_schedule = question_schedule.cloned();
        }
        let combined = target_limits.is_some() && guard_setup.is_some();
        if let Some(resolver) = &mut resolver {
            resolver.candidate_mode = combined;
        }
        let mut candidate_epoch = 0u64;
        let mut candidate_state = None;
        loop {
            if pending.is_empty() {
                let Some(resolver) = &mut resolver else {
                    break;
                };
                let closed = resolver.advance(
                    self,
                    &query.entry_points,
                    &mut sites,
                    &mut pending,
                    &mut report,
                )?;
                if let Some(setup) = guard_setup {
                    check_guard_graph_limits(&sites, setup, &report)?;
                }
                if combined {
                    advance_candidate_epoch(
                        candidate_fingerprint_with_terminals(
                            &sites,
                            &guard_sites,
                            Some(&resolver.transfers),
                            &terminal_receipts,
                        )?,
                        &mut candidate_state,
                        &mut candidate_epoch,
                    )?;
                }
                if closed {
                    break;
                }
                if pending.is_empty() {
                    continue;
                }
            }
            if report.attempted.len() >= limits.max_starts {
                return Err(limit("instruction starts", &report));
            }
            if report.decoder_batches >= limits.max_decoder_batches {
                return Err(limit("decoder batches", &report));
            }
            let n = limits
                .batch_size
                .min(limits.max_starts - report.attempted.len());
            let batch: Vec<_> = pending.iter().take(n).copied().collect();
            let mut candidates = BTreeMap::new();
            for a in batch {
                pending.remove(&a);
                let read = self.read_prefix(a, 15)?;
                report.prefix_bytes = report
                    .prefix_bytes
                    .checked_add(read.bytes.len())
                    .ok_or_else(|| limit("prefix bytes", &report))?;
                if report.prefix_bytes > limits.max_prefix_bytes {
                    return Err(limit("prefix bytes", &report));
                }
                candidates.insert(a, (!read.bytes.is_empty()).then(|| read.bytes.clone()));
                reads.insert(a, read);
                report.attempted.insert(a);
            }
            let (prepared, batch_transfers, batch_guards, batch_terminals) = preparer(
                &self.metadata.snapshot_id,
                &candidates,
                options,
                self.metadata.platform.decoder_target(),
            )?;
            if let Some(resolver) = &mut resolver {
                resolver.transfers.extend(batch_transfers);
            }
            if guard_setup.is_none() && !batch_terminals.is_empty() {
                return Err(PreparationError::InvalidQuery(
                    "terminal evidence without guarded preparation",
                ));
            }
            for (va, receipt) in batch_terminals {
                let source = batch_guards.get(&va).ok_or(PreparationError::InvalidQuery(
                    "terminal source absent from batch",
                ))?;
                if !prepared.sites.contains_key(&va)
                    || terminal_receipts.contains_key(&va)
                    || !guard::terminal_valid(source, &receipt)
                        .map_err(|e| PreparationError::Backend(e.to_string()))?
                {
                    return Err(PreparationError::InvalidQuery(
                        "terminal evidence domain or source changed",
                    ));
                }
                let captured = self.read_prefix(va, receipt.bytes_hex.len() / 2)?;
                guard::validate_terminal_capture(&receipt, &captured.bytes)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?;
                terminal_receipts.insert(va, receipt);
            }
            if let Some(setup) = guard_setup {
                for (va, source) in batch_guards {
                    if !prepared.sites.contains_key(&va) || guard_sites.contains_key(&va) {
                        return Err(PreparationError::InvalidQuery(
                            "guard source outside batch or duplicate",
                        ));
                    }
                    guard_bytes = guard_bytes
                        .checked_add(source.ast.len())
                        .filter(|n| *n <= setup.limits.max_evidence_bytes)
                        .ok_or_else(|| limit("guard evidence bytes", &report))?;
                    guard_sites.insert(va, source);
                }
            }
            report.decoder_batches += 1;
            if identity.as_ref().is_some_and(|i| *i != prepared.identity) {
                return Err(PreparationError::InvalidQuery(
                    "decoder identity changed between batches",
                ));
            }
            identity = Some(prepared.identity);
            for (a, site) in prepared.sites {
                if site.decodable {
                    for (dst, kind) in edges(&site.instruction) {
                        report.referenced.insert(dst);
                        if report.referenced.len() > limits.max_candidates {
                            return Err(limit("candidate addresses", &report));
                        }
                        if kind.is_local() && !report.attempted.contains(&dst) {
                            pending.insert(dst);
                        }
                    }
                }
                sites.insert(a, site);
            }
            if let Some(setup) = guard_setup {
                check_guard_graph_limits(&sites, setup, &report)?;
            }
            if combined {
                advance_candidate_epoch(
                    candidate_fingerprint_with_terminals(
                        &sites,
                        &guard_sites,
                        resolver.as_ref().map(|r| &r.transfers),
                        &terminal_receipts,
                    )?,
                    &mut candidate_state,
                    &mut candidate_epoch,
                )?;
            }
        }
        let candidate = combined.then(|| {
            request_from_sites(
                &self.metadata.snapshot_id,
                query,
                &report.referenced,
                options,
                &sites,
            )
        });
        let mut original_controls = BTreeMap::new();
        let mut guard_admission = None;
        let mut guard_input = None;
        if let Some(setup) = guard_setup {
            let mut barriers = BTreeSet::new();
            for (&va, site) in &sites {
                let source = guard_sites
                    .entry(va)
                    .or_insert_with(|| guard::CandidateSite {
                        site: format!("0x{va:016x}"),
                        bytes_hex: site
                            .evidence
                            .bytes
                            .iter()
                            .map(|b| format!("{b:02x}"))
                            .collect(),
                        ast: "[]".into(),
                        control: guard::CandidateControl::from_instruction(&site.instruction),
                        opaque: true,
                    });
                if combined {
                    original_controls.insert(va, source.control.clone());
                    // Resolver augmentation is a separately retained receipt.
                    // Guard flow uses the stable effective candidate graph.
                    source.control = guard::CandidateControl::from_instruction(&site.instruction);
                }
                if !site.decodable
                    || (site.instruction.kind == InstructionKind::Stop
                        && !terminal_receipts.contains_key(&va))
                    || (site.instruction.kind == InstructionKind::Indirect
                        && !site.instruction.complete)
                {
                    barriers.insert(source.site.clone());
                }
            }
            let mut normal_flow = guard::NormalFlowEvidence::empty();
            normal_flow.terminals = terminal_receipts.into_values().collect();
            let input = guard::GuardInput {
                normal_flow: Some(normal_flow),
                snapshot: self.metadata.snapshot_id.clone(),
                artifact_sha256: self.metadata.artifact_sha256.clone(),
                query_scope_sha256: setup.query_scope_sha256.clone(),
                preparation_sha256: preparation_digest(
                    &limits,
                    &options.catalogue.locations(),
                    &self.limits,
                    if setup
                        .producer
                        .as_ref()
                        .is_some_and(|p| p.projection == guard::ADVANCED_PRODUCER_PROFILE)
                    {
                        guard::ADVANCED_PROFILE
                    } else {
                        guard::PROFILE
                    },
                )
                .map_err(|e| PreparationError::Backend(e.to_string()))?,
                platform: match self.metadata.platform {
                    Platform::Windows => "windows-amd64",
                    Platform::Linux => "linux-amd64",
                }
                .into(),
                roots: setup.roots.clone(),
                seeds: query
                    .slice_seeds
                    .iter()
                    .map(|a| format!("0x{a:016x}"))
                    .collect(),
                activation: setup.activation.clone(),
                premises: setup.premises.clone(),
                producer: setup
                    .producer
                    .clone()
                    .ok_or(PreparationError::InvalidQuery("guard producer absent"))?,
                policy: if setup
                    .producer
                    .as_ref()
                    .is_some_and(|p| p.projection == guard::ADVANCED_PRODUCER_PROFILE)
                {
                    guard::ADVANCED_PROFILE
                } else {
                    guard::PROFILE
                }
                .into(),
                model_version: guard::MODEL_VERSION.into(),
                model_sha256: guard::model_identity(),
                limits: setup.limits.clone(),
                candidate_epoch: if combined { candidate_epoch } else { 1 },
                closure_complete: true,
                barriers: barriers.into_iter().collect(),
                sites: guard_sites.into_values().collect(),
            };
            let mut certified = guard::certify_guards(&input)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            guard::replay_report(&input, &certified)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            for source in &input.sites {
                if guard::recognize_pending_for_input(&input, source)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?
                    .is_none()
                {
                    continue;
                }
                let decision = certified.guards.iter().find(|g| g.site == source.site);
                let residual = decision
                    .map(|d| d.residual.as_str())
                    .or(certified.stop.as_deref())
                    .ok_or(PreparationError::InvalidQuery("guard decision absent"))?;
                let va = crate::bap::core_adapter::address(&source.site)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?;
                let site = sites
                    .get_mut(&va)
                    .ok_or(PreparationError::InvalidQuery("guard site absent"))?;
                crate::bap::Backend::finalize_guard(
                    site,
                    va,
                    decision.and_then(|d| d.normal_ast.as_deref()),
                    residual,
                    options,
                )
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            }
            // The final normalized request is built next. Receipts bind that
            // request before its distinct analysis identity is published.
            certified.final_request_sha256 = None;
            guard_input = Some(Arc::new(input));
            guard_admission = Some(certified);
        }
        report.unattempted_references = report
            .referenced
            .difference(&report.attempted)
            .copied()
            .collect();
        let request = request_from_sites(
            &self.metadata.snapshot_id,
            query,
            &report.referenced,
            options,
            &sites,
        );
        let mut evidence = BTreeMap::new();
        let mut gaps = Vec::new();
        for (a, site) in sites {
            evidence.insert(a, site.evidence);
            gaps.extend(site.gaps);
        }
        for &a in &request.addresses {
            evidence.entry(a).or_insert_with(placeholder);
        }
        for &a in &request.decodable {
            if let Some(end) = a.checked_add(evidence[&a].length as u64) {
                for &b in request
                    .decodable
                    .range((std::ops::Bound::Excluded(a), std::ops::Bound::Excluded(end)))
                {
                    report.overlapping_starts.insert((a, b));
                }
            }
        }
        gaps.sort_by_key(|g| g.address);
        request
            .validate()
            .map_err(|e| PreparationError::Decoder(AdapterError::InvalidRequest(e)))?;
        let mut target_resolution = resolver.and_then(|resolver| resolver.report);
        if identity
            .as_ref()
            .is_some_and(|i| crate::bap::advanced_projection(&i.ruleset))
            && let Some(resolved) = &mut target_resolution
        {
            crate::bap::target_resolution::promote_advanced(resolved)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
        }
        if let Some(resolved) = &mut target_resolution {
            let replay = candidate.as_ref().unwrap_or(&request);
            let graph = crate::bap::target_resolution::report_graph_digest(
                resolved,
                &replay.instructions,
                &replay.entry_points,
            )
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
            if graph != resolved.graph_sha256 && resolved.resolutions.iter().any(|r| {
                matches!(
                    r.coverage,
                    Some(crate::bap::target_resolution::CoverageEvidence::InductiveDispatch { .. })
                )
            }) {
                return Err(PreparationError::InvalidQuery(
                    "loop coverage graph changed before publication",
                ));
            }
            resolved.graph_sha256 = graph;
            crate::bap::target_resolution::validate(
                resolved,
                &replay.instructions,
                &replay.entry_points,
            )
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        }
        if let Some(certified) = &mut guard_admission {
            let hash = normalized_request_digest(&request)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            guard::bind_final_request(guard_input.as_ref().expect("guard input"), certified, &hash)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            report.query_identity = guard::analysis_id(certified)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
        }
        let composition = if let Some(candidate) = &candidate {
            let composed = crate::bap::composition::seal(
                candidate,
                &original_controls,
                candidate_epoch,
                target_resolution
                    .as_ref()
                    .ok_or(PreparationError::InvalidQuery(
                        "combined target report absent",
                    ))?,
                guard_admission
                    .as_ref()
                    .ok_or(PreparationError::InvalidQuery(
                        "combined guard report absent",
                    ))?,
                &request,
            )
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
            report.query_identity = crate::bap::composition::analysis_id(&composed)
                .map_err(|e| PreparationError::Backend(e.to_string()))?;
            Some(composed)
        } else {
            None
        };
        let prepared = PreparedAnalysis {
            request,
            instructions: evidence,
            gaps,
            identity: identity.expect("nonempty roots"),
        };
        let scalar_binding = Arc::new(ScalarPreparationBinding {
            identity: prepared.identity.clone(),
            request_fingerprint: crate::investigation::request_fingerprint(&prepared.request),
            instructions: prepared.instructions.clone(),
            reads: reads.clone(),
            gaps: prepared.gaps.clone(),
            materialization: report.clone(),
            open_limits: self.limits.clone(),
            snapshot: self.metadata.clone(),
            fault_digest: self.fault.evidence.digest(),
        });
        Ok(FilePreparedAnalysis {
            scalar_binding,
            guard_input,
            guard_snapshot: guard_setup.map(|_| Arc::new(self.clone())),
            original_controls: combined.then(|| Arc::new(original_controls)),
            guard_admission,
            target_snapshot: target_limits.map(|_| Arc::new(self.clone())),
            target_resolution,
            composition,
            refinement: BTreeMap::new(),
            fault: self.fault.clone(),
            prepared,
            snapshot: self.metadata.clone(),
            open_limits: self.limits.clone(),
            reads,
            materialization: report,
        })
    }
}
