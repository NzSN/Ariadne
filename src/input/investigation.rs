//! Bind capture/preparation provenance to the exact completed normalized query.
use crate::input::{FilePreparedAnalysis, ReadStop};
use crate::investigation::{
    BoundInvestigation, Contributor, EvidenceContext, RecoveryGap, SiteEvidence, Span,
};
use crate::{AnalysisView, ByteSource, effects::EffectQuality};
use sha2::{Digest, Sha256};
pub(crate) fn validate_opaque_ordinary(
    prepared: &FilePreparedAnalysis,
) -> Result<(), crate::investigation::Error> {
    let request = &prepared.prepared.request;
    for (&va, e) in &prepared.prepared.instructions {
        if let Some(s) = &e.semantic
            && (s.status == "opaque-ordinary"
                || e.rule.as_deref() == Some("bap-opaque-ordinary-v3")
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
                || s.projection != "bap-bit-provenance-v3"
                || s.ast_sha256.is_none()
                || s.fallback.is_some()
                || e.quality != EffectQuality::Opaque
                || e.rule.as_deref() != Some("bap-opaque-ordinary-v3")
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
    let report = &prepared.materialization;
    let request = &prepared.prepared.request;
    if prepared.snapshot.snapshot_id != request.snapshot_id
        || report.entry_points != request.entry_points
        || report.slice_seeds != request.slice_seeds
    {
        return Err("prepared query metadata mismatch".into());
    }
    let mut digest = Sha256::new();
    digest.update(b"ariadne-minidump-query-v1\0");
    digest.update(request.snapshot_id.as_bytes());
    for set in [&report.entry_points, &report.slice_seeds] {
        digest.update((set.len() as u64).to_le_bytes());
        for a in set {
            digest.update(a.to_le_bytes());
        }
    }
    let l = &report.limits;
    for n in [
        l.max_starts,
        l.max_candidates,
        l.max_prefix_bytes,
        l.max_decoder_batches,
        l.batch_size,
    ] {
        digest.update((n as u64).to_le_bytes());
    }
    if format!("{:x}", digest.finalize()) != report.query_identity {
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
    let tool_binding = crate::reports::sha256(&serde_json::to_vec(&tool_facts)?);
    let context = EvidenceContext {
        snapshot_id: request.snapshot_id.clone(),
        artifact_sha256: prepared.snapshot.artifact_sha256.clone(),
        query_id: report.query_identity.clone(),
        semantic_profile: format!(
            "{}:{}:{}:{}:{}:{}",
            identity.target,
            identity.decoder,
            identity.protocol,
            identity.ruleset,
            identity.catalogue,
            tool_binding
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
    BoundInvestigation::new(analyzer, request, context)
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
