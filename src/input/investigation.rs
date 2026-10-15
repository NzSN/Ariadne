//! Bind capture/preparation provenance to the exact completed normalized query.
use crate::input::{FilePreparedAnalysis, ReadStop};
use crate::investigation::{
    BoundInvestigation, Contributor, EvidenceContext, RecoveryGap, SiteEvidence, Span,
};
use crate::{AnalysisView, ByteSource, effects::EffectQuality};
pub(crate) fn validate_opaque_ordinary(
    prepared: &FilePreparedAnalysis,
) -> Result<(), crate::investigation::Error> {
    let request = &prepared.prepared.request;
    for (&va, e) in &prepared.prepared.instructions {
        if let Some(s) = &e.semantic
            && (s.status == "opaque-ordinary"
                || matches!(
                    e.rule.as_deref(),
                    Some("bap-opaque-ordinary-v3" | "bap-opaque-ordinary-v4")
                )
                || s.gaps.iter().any(|g| g == "unsupported-data-effects"))
        {
            let instruction = request
                .instructions
                .get(&va)
                .ok_or("missing opaque summary")?;
            let next = va
                .checked_add(u64::from(e.length))
                .ok_or("opaque next VA overflow")?;
            if s.status != "opaque-ordinary"
                || !crate::bap::known_projection(&s.projection)
                || s.ast_sha256.is_none()
                || s.fallback.is_some()
                || e.quality != EffectQuality::Opaque
                || e.rule.as_deref()
                    != Some(match s.projection.as_str() {
                        "bap-bit-provenance-v3" => "bap-opaque-ordinary-v3",
                        // The finite ordinary summary is unchanged across
                        // vector, guard, and shift-count producer profiles.
                        "bap-bit-provenance-v4"
                        | "bap-bit-provenance-v5"
                        | "bap-bit-provenance-v6"
                        | "bap-bit-provenance-v7" => crate::bap::OPAQUE_ORDINARY_RULE,
                        _ => "",
                    })
                || e.length == 0
                || !request.decodable.contains(&va)
                || instruction.kind != crate::InstructionKind::Ordinary
                || instruction.fall != [next].into()
                || !instruction.targets.is_empty()
                || !instruction.complete
                || instruction.uses != request.locations
                || instruction.may_defs != request.locations
                || !instruction.must_defs.is_empty()
                || !s.gaps.iter().any(|g| g == "unsupported-data-effects")
                || !prepared.prepared.gaps.iter().any(|g| {
                    g.address == va && g.reason == crate::effects::GapReason::OpaqueEffects
                })
            {
                return Err("invalid opaque ordinary evidence/summary binding".into());
            }
        }
    }
    Ok(())
}
pub(crate) fn capture_context(
    prepared: &FilePreparedAnalysis,
) -> Result<EvidenceContext, crate::investigation::Error> {
    validate_opaque_ordinary(prepared)?;
    prepared.validate_target_resolution()?;
    prepared.validate_guard_admission()?;
    let report = &prepared.materialization;
    let request = &prepared.prepared.request;
    if prepared.snapshot.snapshot_id != request.snapshot_id
        || report.entry_points != request.entry_points
        || report.slice_seeds != request.slice_seeds
    {
        return Err("prepared query metadata mismatch".into());
    }
    let expected_query = if let Some(composition) = prepared.composition() {
        crate::bap::composition::analysis_id(composition)?
    } else if let Some(guard) = prepared.guard_admission() {
        crate::bap::guard_admission::analysis_id(guard)?
    } else {
        super::materialize::query_identity(
            &request.snapshot_id,
            &super::AnalysisQuery {
                entry_points: report.entry_points.clone(),
                slice_seeds: report.slice_seeds.clone(),
            },
            &report.limits,
            prepared.target_resolution.as_ref().map(|r| &r.limits),
        )?
    };
    if expected_query != report.query_identity {
        return Err("query identity or resource limits changed".into());
    }
    let mut sites = Vec::new();
    for (&va, e) in &prepared.prepared.instructions {
        let read = prepared.reads.get(&va);
        let mut gaps: Vec<String> = prepared
            .prepared
            .gaps
            .iter()
            .filter(|g| g.address == va)
            .map(|g| format!("{:?}", g.reason))
            .collect();
        if let Some(read) = read {
            if !read.bytes.starts_with(&e.bytes) {
                return Err("instruction bytes do not match captured read".into());
            }
            match read.stop {
                ReadStop::ConflictingCapture(_) => gaps.push("conflicting-capture".into()),
                ReadStop::NotCaptured(_) if e.length == 0 => {
                    gaps.push("missing-capture".into());
                }
                _ => {}
            }
        } else if e.source == ByteSource::Captured && !e.bytes.is_empty() {
            return Err("captured instruction has no reader evidence".into());
        }
        let semantic = e.semantic.as_ref();
        if let Some(s) = semantic {
            gaps.extend(s.gaps.clone());
        }
        sites.push(SiteEvidence {
            va,
            bytes_hex: e.bytes.iter().map(|b| format!("{b:02x}")).collect(),
            captured: e.source == ByteSource::Captured,
            opcode: e.opcode.clone(),
            quality: match e.quality {
                EffectQuality::Reviewed => "reviewed",
                EffectQuality::ExternalLifted => "external_lift",
                EffectQuality::Opaque => "opaque",
                EffectQuality::Unavailable => "unavailable",
            }
            .into(),
            semantic_status: semantic.map(|s| s.status.clone()),
            helper_sha256: semantic.map(|s| s.helper_sha256.clone()),
            runtime_sha256: semantic.map(|s| s.runtime_sha256.clone()),
            ast_sha256: semantic.and_then(|s| s.ast_sha256.clone()),
            projection: semantic.map(|s| s.projection.clone()),
            accesses: semantic
                .map(|s| {
                    s.memory_accesses
                        .iter()
                        .map(crate::investigation::AddressUse::from)
                        .collect()
                })
                .unwrap_or_default(),
            spans: read
                .map(|r| {
                    r.spans
                        .iter()
                        .map(|s| Span {
                            va: s.address,
                            length: s.length,
                            contributors: s
                                .contributors
                                .iter()
                                .map(|c| Contributor {
                                    stream: c.stream,
                                    entry: c.entry,
                                    file_offset: c.file_offset,
                                })
                                .collect(),
                        })
                        .collect()
                })
                .unwrap_or_default(),
            gaps,
        });
    }
    let identity = &prepared.prepared.identity;
    let tool_facts: Vec<_> = sites
        .iter()
        .map(|s| {
            (
                &s.va,
                &s.helper_sha256,
                &s.runtime_sha256,
                &s.ast_sha256,
                &s.projection,
            )
        })
        .collect();
    let guard_binding = prepared.guard_admission().map(|guard| {
        crate::reports::sha256(&serde_json::to_vec(guard).expect("serializable guard report"))
    });
    let tool_binding = if let Some(composition) = prepared.composition() {
        crate::investigation::composition_capture_binding(composition, &sites)?
    } else if let Some(binding) = &guard_binding {
        crate::reports::sha256(&serde_json::to_vec(&(&tool_facts, binding))?)
    } else {
        crate::reports::sha256(&serde_json::to_vec(&tool_facts)?)
    };
    let context = EvidenceContext {
        snapshot_id: request.snapshot_id.clone(),
        artifact_sha256: prepared.snapshot.artifact_sha256.clone(),
        query_id: report.query_identity.clone(),
        semantic_profile: format!(
            "{}:{}:{}:{}:{}:{}{}",
            identity.target,
            identity.decoder,
            identity.protocol,
            identity.ruleset,
            identity.catalogue,
            tool_binding,
            if let Some(composition) = prepared.composition() {
                crate::investigation::composition_semantic_suffix(
                    composition,
                    prepared
                        .target_resolution
                        .as_ref()
                        .ok_or("composition target proof absent")?,
                    prepared
                        .guard_admission()
                        .ok_or("composition guard proof absent")?,
                )?
            } else if let Some(guard) = prepared.guard_admission() {
                crate::investigation::guard_semantic_suffix(guard)?
            } else if prepared.target_resolution.is_some() {
                format!(
                    ":{}:{}",
                    crate::bap::target_resolution::PROFILE,
                    crate::bap::target_resolution::MEMORY_PREMISE
                )
            } else {
                String::new()
            }
        ),
        sites,
        recovery_gaps: Vec::new(),
    };
    if context.sites.len() != request.addresses.len()
        || context.sites.iter().any(|s| {
            !request.addresses.contains(&s.va) || !crate::investigation::validate::site_valid(s)
        })
    {
        return Err("capture evidence domain or shape mismatch".into());
    }
    Ok(context)
}

pub fn bind_investigation(
    prepared: &FilePreparedAnalysis,
    analyzer: &dyn AnalysisView,
) -> Result<BoundInvestigation, crate::investigation::Error> {
    let request = &prepared.prepared.request;
    let mut context = capture_context(prepared)?;
    context.recovery_gaps = analyzer
        .state()
        .obligations
        .iter()
        .map(|o| RecoveryGap {
            site: o.site,
            code: format!("recovery:{:?}", o.reason),
        })
        .chain(
            request
                .slice_seeds
                .difference(&analyzer.state().decoded)
                .map(|&site| RecoveryGap {
                    site,
                    code: "missing-seed".into(),
                }),
        )
        .collect();
    let mut bound = BoundInvestigation::new(analyzer, request, context)?;
    bound.guard_admission = prepared.guard_admission().cloned();
    bound.composition = prepared.composition().cloned();
    bound.target_resolution = prepared.target_resolution.clone();
    Ok(bound)
}

pub fn bind_memory_refinement(
    prepared: &FilePreparedAnalysis,
    analyzer: &dyn AnalysisView,
) -> Result<crate::investigation::BoundMemoryRefinement, crate::investigation::Error> {
    crate::investigation::BoundMemoryRefinement::new(
        bind_investigation(prepared, analyzer)?,
        prepared.refinement.clone(),
        Some(prepared.fault.evidence.clone()),
    )
}

/// Bind only reader-owned fault observations to the exact completed query.
pub fn bind_fault_context(
    prepared: &FilePreparedAnalysis,
    analyzer: &dyn AnalysisView,
) -> Result<crate::investigation::BoundFaultContext, crate::investigation::Error> {
    if prepared.snapshot.as_ref() != prepared.fault.metadata.as_ref() {
        return Err("fault metadata changed after capture".into());
    }
    let analysis = bind_investigation(prepared, analyzer)?;
    crate::investigation::BoundFaultContext::new(analysis, prepared.fault.evidence.clone())
}

/// Bind the selected decoded base receipt without another decoder/solver launch.
pub fn bind_zero_base_offset(
    prepared: &FilePreparedAnalysis,
    analyzer: &dyn AnalysisView,
    question: crate::investigation::FaultAddressQuestion,
) -> Result<crate::investigation::BoundZeroBaseOffsetContext, crate::investigation::Error> {
    let fault = bind_fault_context(prepared, analyzer)?;
    let site = prepared
        .prepared
        .instructions
        .get(&question.site)
        .ok_or("question site is outside this query")?;
    if let Some(r) = &site.decoded_address {
        if Some(r.raw_record.as_str()) != site.decoder_record.as_deref()
            || r.length != site.length
            || r.bytes_hex
                != site
                    .bytes
                    .iter()
                    .map(|b| format!("{b:02x}"))
                    .collect::<String>()
        {
            return Err("decoded receipt differs from preparation".into());
        }
    }
    crate::investigation::BoundZeroBaseOffsetContext::new(
        fault,
        question,
        site.decoded_address.clone(),
    )
}
