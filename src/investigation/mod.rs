//! Evidence-bound domain explanations above the normalized analysis result.
mod address_wrap;
mod backward_values;
mod explain;
pub(crate) mod fault_context;
#[cfg(feature = "bap")]
pub(crate) mod frame_connections;
pub(crate) mod frame_paths;
#[cfg(feature = "bap")]
pub(crate) mod frame_structure;
#[cfg(feature = "bap")]
pub use frame_connections::{
    BoundFrameConnections, CondensationEdge, ConnectionExample, ConnectionFrontier,
    ConnectionLayerStatus, ConnectionReceipt, ConnectionReceipts, ConnectionStop, ContextEdge,
    ExampleSearchStatus, FRAME_CONNECTION_SCHEMA, FrameConnectionAnalysis, FrameConnectionLimits,
    FrontierRelation, RepresentedConnection, StructuralComponent, summarize_frame_connections,
};
#[cfg(feature = "bap")]
pub use frame_structure::{
    BoundFrameRecovery, BoundFrameStructure, FRAME_STRUCTURE_PRODUCER, FRAME_STRUCTURE_SCHEMA,
    FrameStructureDiagnostic, FrameStructureDiagnosticKind, FrameStructureEdge, FrameStructureGap,
    FrameStructureGapKind, FrameStructureLimits, FrameStructureLink, FrameStructureMap,
    FrameStructureQuestion, active_frame_structure_entry, bind_frame_structure,
};
pub(crate) mod frame_unwind;
pub use frame_paths::{
    BoundFramePaths, COMPOSED_FRAME_PATH_SCHEMA, FRAME_PATH_SCHEMA, FramePathCounters,
    FramePathEdge, FramePathEdgeKind, FramePathGraphLimits, FramePathLimits, FramePathListing,
    FramePathNode, FramePathQuestion, GUARDED_FRAME_PATH_SCHEMA, LEGACY_COMPOSED_FRAME_PATH_SCHEMA,
    LEGACY_GUARDED_FRAME_PATH_SCHEMA, LEGACY_V2_COMPOSED_FRAME_PATH_SCHEMA,
    LIMITED_FRAME_PATH_SCHEMA, ListedFramePath, active_frame_entry, bind_frame_paths,
    bind_frame_paths_with_limits, list_frame_paths,
};
pub use frame_unwind::{
    CapturedFrameChain, FRAME_UNWIND_PROFILE, FrameMemoryEvidence, FrameRecoveryLimits,
    FrameRegisterEvidence, FrameTransition, RecoveredFrame,
};
#[cfg(feature = "bap")]
mod memory_refinement;
pub(crate) mod model;
#[cfg(feature = "bap")]
pub use memory_refinement::{
    BoundMemoryRefinement, MEMORY_PROVENANCE_PROFILE, MEMORY_PROVENANCE_SCHEMA, MemoryCandidate,
    MemoryDependencyDiagnostic, MemoryPair, MemoryProvenanceAssessment, MemoryRefinementLimits,
    NumericalBoundary, assess_memory_origins, modular_memory_overlap,
};
mod scalar_base_displacement;
pub(crate) mod validate;
mod zero_address;
mod zero_base_offset;
pub use address_wrap::{
    ADDRESS_WRAP_PROFILE, ADDRESS_WRAP_SCHEMA, AddressWrapArithmetic, AddressWrapAssertion,
    AddressWrapAssessment, AddressWrapClaim, AddressWrapEvidence, AddressWrapEvidenceData,
    AddressWrapKind, AddressWrapLimits, BoundAddressWrapContext, assess_address_wrap,
};
pub use backward_values::{BackwardStep, BackwardValue, ScalarTransfer, backward_preimage};
pub use explain::explain_fault_address;
pub use fault_context::{
    BoundFaultContext, FaultDatum, FaultMetadata, FaultObservation, FaultSpan,
};
#[cfg(feature = "input")]
pub(crate) use fault_context::{CapturedFaultContext, values as fault_values};
pub use model::*;
pub use validate::{BoundInvestigation, request_fingerprint};
pub use zero_address::{
    AssessedValue, AssessmentLimits, ZERO_ADDRESS_PROFILE, ZERO_ADDRESS_SCHEMA,
    ZeroAddressAssertion, ZeroAddressAssessment, ZeroAddressClaim, ZeroAddressConclusion,
    ZeroAddressEvidence, ZeroAddressEvidenceData, assess_zero_address,
};
pub use zero_base_offset::{
    BoundZeroBaseOffsetContext, ZERO_BASE_OFFSET_PROFILE, ZERO_BASE_OFFSET_SCHEMA,
    ZeroBaseOffsetAssertion, ZeroBaseOffsetAssessment, ZeroBaseOffsetClaim, ZeroBaseOffsetEvidence,
    ZeroBaseOffsetEvidenceData, ZeroBaseOffsetLimits, assess_zero_base_offset,
};
pub type Error = Box<dyn std::error::Error>;
pub(crate) fn invalid(s: impl Into<String>) -> Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, s.into()).into()
}
pub(crate) fn sha(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}
#[cfg(feature = "bap")]
pub(crate) fn guard_semantic_suffix(
    report: &crate::bap::guard_admission::Report,
) -> Result<String, Error> {
    let binding = sha(&serde_json::to_vec(report)?);
    let premises = report
        .input
        .premises
        .iter()
        .map(|p| {
            format!(
                "{:?}@{}:root={}:RSP-residue-mask=0x{:04x}:{}",
                p.origin, p.point, p.root, p.rsp_residues, p.policy,
            )
        })
        .collect::<Vec<_>>()
        .join(";");
    let scope = crate::bap::guard_admission::normal_flow_scope(report)
        .map(|scope| {
            format!(":normal-flow-scope=[{scope}]:exception-resumption-outside-local-scope")
        })
        .unwrap_or_default();
    Ok(format!(
        ":{}:{binding}:guard-premises=[{premises}]{scope}",
        report.profile
    ))
}
#[cfg(feature = "bap")]
pub(crate) fn composition_semantic_suffix(
    composition: &crate::bap::composition::Report,
    target: &crate::bap::target_resolution::Report,
    guard: &crate::bap::guard_admission::Report,
) -> Result<String, Error> {
    Ok(format!(
        "{}:{}:{}:{}:{}",
        guard_semantic_suffix(guard)?,
        composition.profile,
        composition.binding_sha256,
        target.profile,
        target.memory_premise,
    ))
}
#[cfg(feature = "bap")]
pub(crate) fn composition_capture_binding(
    composition: &crate::bap::composition::Report,
    sites: &[SiteEvidence],
) -> Result<String, Error> {
    Ok(sha(&serde_json::to_vec(&(
        crate::bap::composition::capture_domain(composition),
        sites,
        &composition.binding_sha256,
    ))?))
}
#[cfg(feature = "bap")]
pub(crate) fn guard_capture_binding(
    report: &crate::bap::guard_admission::Report,
    sites: &[SiteEvidence],
) -> Result<String, Error> {
    Ok(sha(&serde_json::to_vec(&(
        "ariadne-guarded-capture/v2",
        sites,
        sha(&serde_json::to_vec(report)?),
    ))?))
}
#[cfg(feature = "bap")]
pub(crate) fn validate_guard_capture(
    profile: &str,
    report: &crate::bap::guard_admission::Report,
    sites: &[SiteEvidence],
) -> Result<(), Error> {
    let suffix = guard_semantic_suffix(report)?;
    if profile
        .strip_suffix(&suffix)
        .and_then(|p| p.rsplit(':').next())
        != Some(guard_capture_binding(report, sites)?.as_str())
        || !sites.windows(2).all(|w| w[0].va < w[1].va)
    {
        return Err(invalid("guard full capture source binding changed"));
    }
    Ok(())
}
#[cfg(feature = "bap")]
pub(crate) fn validate_normal_flow_sources(
    report: &crate::bap::guard_admission::Report,
    request: &crate::AnalysisRequest,
    sites: &[SiteEvidence],
) -> Result<(), Error> {
    crate::bap::guard_admission::validate_normal_flow_request(&report.input, request)?;
    if !crate::bap::guard_admission::is_legacy(report)
        && sites.iter().any(|site| {
            site.semantic_status.as_deref() == Some("normal-flow-terminal")
                && crate::bap::guard_admission::terminal_receipt(&report.input, site.va).is_none()
        })
    {
        return Err(invalid("terminal status without its source certificate"));
    }
    if let Some(flow) = &report.input.normal_flow {
        for receipt in &flow.terminals {
            let va = crate::bap::core_adapter::address(&receipt.site)?;
            let site = sites
                .iter()
                .find(|s| s.va == va)
                .ok_or_else(|| invalid("terminal full capture source absent"))?;
            if !site.captured
                || site.bytes_hex != receipt.bytes_hex
                || site.quality != "opaque"
                || site.semantic_status.as_deref() != Some("normal-flow-terminal")
                || !site.accesses.is_empty()
                || [
                    "exception-exit",
                    "exception-resumption-outside-local-scope",
                    "unsupported-exception-effects",
                ]
                .iter()
                .any(|gap| !site.gaps.iter().any(|g| g == gap))
            {
                return Err(invalid(
                    "terminal capture status, scope or access effects changed",
                ));
            }
        }
    }
    Ok(())
}
#[cfg(feature = "bap")]
pub(crate) fn validate_composition_capture(
    profile: &str,
    composition: &crate::bap::composition::Report,
    target: &crate::bap::target_resolution::Report,
    guard: &crate::bap::guard_admission::Report,
    sites: &[SiteEvidence],
) -> Result<(), Error> {
    let suffix = composition_semantic_suffix(composition, target, guard)?;
    if profile
        .strip_suffix(&suffix)
        .and_then(|p| p.rsplit(':').next())
        != Some(composition_capture_binding(composition, sites)?.as_str())
        || !sites.windows(2).all(|w| w[0].va < w[1].va)
    {
        return Err(invalid("composition full capture source binding changed"));
    }
    Ok(())
}
#[cfg(feature = "bap")]
pub(crate) fn proof_binding(
    composition: Option<&crate::bap::composition::Report>,
    target: Option<&crate::bap::target_resolution::Report>,
    guard: &crate::bap::guard_admission::Report,
    request: &crate::AnalysisRequest,
) -> Result<(String, String, Option<crate::AnalysisRequest>), Error> {
    match (composition, target) {
        (Some(composition), Some(target)) => {
            crate::bap::composition::validate(composition, target, guard, request)?;
            Ok((
                crate::bap::composition::analysis_id(composition)?,
                composition_semantic_suffix(composition, target, guard)?,
                Some(crate::bap::composition::candidate_request(composition)?),
            ))
        }
        (None, None) => {
            let hash = sha(&serde_json::to_vec(
                &crate::bap::core_adapter::encode_request(request)?,
            )?);
            Ok((
                crate::bap::guard_admission::validate_final_request(&guard.input, guard, &hash)?,
                guard_semantic_suffix(guard)?,
                None,
            ))
        }
        _ => Err(invalid(
            "composition requires paired target and guard proofs",
        )),
    }
}
pub(crate) fn id(kind: &str, scope: &str, value: &impl serde::Serialize) -> String {
    format!(
        "{kind}:{}",
        sha(&serde_json::to_vec(&(kind, scope, value)).expect("owned serializable fact"))
    )
}

#[cfg(all(test, feature = "input", feature = "bap"))]
#[path = "../../tests/investigation/composition_unit.rs"]
mod composition_unit;

#[cfg(feature = "bap")]
pub(crate) mod frame_question;
#[cfg(feature = "bap")]
pub use frame_question::{
    BoundFrameQuestion, FRAME_QUESTION_REQUEST_SCHEMA, FRAME_QUESTION_SCHEMA, FrameQuestion,
    FrameQuestionAssessment, FrameQuestionEvidence, FrameQuestionKind, FrameQuestionLimits,
    FrameQuestionRequest, FrameQuestionSource, ModelWitness, QuestionLayerStatus, QuestionLayers,
    QuestionMoment, QuestionObligation, QuestionOrigin, QuestionPoint, QuestionReceipt,
    QuestionResolution, QuestionRevision, QuestionValue, QuestionVerdict, ValueConstraint,
    investigate_frame_question,
};
