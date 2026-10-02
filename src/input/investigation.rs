//! Bind capture/preparation provenance to the exact completed normalized query.
use crate::input::{FilePreparedAnalysis, ReadStop};
use crate::investigation::{
    BoundInvestigation, Contributor, EvidenceContext, RecoveryGap, SiteEvidence, Span,
};
use crate::{Analyzer, ByteSource, effects::EffectQuality};
use sha2::{Digest, Sha256};
pub fn bind_investigation(
    prepared: &FilePreparedAnalysis,
    analyzer: &Analyzer,
) -> Result<BoundInvestigation, crate::investigation::Error> {
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
        recovery_gaps: analyzer
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
            .collect(),
    };
    BoundInvestigation::new(analyzer, request, context)
}
