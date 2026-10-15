//! Evidence-bound domain explanations above the normalized analysis result.
mod backward_values;
mod explain;
mod fault_context;
pub(crate) mod frame_paths;
pub(crate) mod frame_unwind;
pub use frame_paths::{
    BoundFramePaths, COMPOSED_FRAME_PATH_SCHEMA, FRAME_PATH_SCHEMA, FramePathCounters,
    FramePathEdge, FramePathEdgeKind, FramePathLimits, FramePathListing, FramePathNode,
    FramePathQuestion, GUARDED_FRAME_PATH_SCHEMA, LEGACY_COMPOSED_FRAME_PATH_SCHEMA,
    ListedFramePath, active_frame_entry, bind_frame_paths, list_frame_paths,
};
pub use frame_unwind::{
    CapturedFrameChain, FRAME_UNWIND_PROFILE, FrameMemoryEvidence, FrameRecoveryLimits,
    FrameRegisterEvidence, RecoveredFrame,
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
pub(crate) mod validate;
mod zero_address;
mod zero_base_offset;
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
    Ok(format!(
        ":{}:{binding}:guard-premises=[{premises}]",
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
        if crate::bap::composition::is_legacy(composition) {
            "ariadne-composed-capture/v1"
        } else {
            "ariadne-composed-capture/v2"
        },
        sites,
        &composition.binding_sha256,
    ))?))
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
