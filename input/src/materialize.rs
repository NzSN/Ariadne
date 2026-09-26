use crate::*;
use ariadne::effects::{EffectQuality, InstructionEvidence, PreparationOptions, PreparedAnalysis};
use ariadne::llvm_mc::{AdapterError, prepare_captured_batch};
use ariadne::{
    AddressSet, AnalysisRequest, ByteSource, EdgeKind, InputKind, Instruction, InstructionKind,
    LocationSet,
};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub struct AnalysisQuery {
    pub entry_points: AddressSet,
    pub slice_seeds: AddressSet,
}
#[derive(Clone, Debug)]
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
#[derive(Clone, Debug, Default)]
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
#[derive(Clone, Debug)]
pub struct FilePreparedAnalysis {
    pub prepared: PreparedAnalysis,
    pub snapshot: Arc<SnapshotMetadata>,
    pub reads: BTreeMap<Address, ByteRead>,
    pub materialization: MaterializationReport,
}
#[derive(Debug)]
pub enum PreparationError {
    Input(InputError),
    Decoder(AdapterError),
    InvalidQuery(&'static str),
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
    }
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
        use sha2::{Digest, Sha256};
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
        let mut digest = Sha256::new();
        digest.update(b"ariadne-minidump-query-v1\0");
        digest.update(self.metadata.snapshot_id.as_bytes());
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
        let mut report = MaterializationReport {
            entry_points: query.entry_points.clone(),
            slice_seeds: query.slice_seeds.clone(),
            limits: limits.clone(),
            referenced: query
                .entry_points
                .union(&query.slice_seeds)
                .copied()
                .collect(),
            query_identity: format!("{:x}", digest.finalize()),
            ..MaterializationReport::default()
        };
        if report.referenced.len() > limits.max_candidates {
            return Err(limit("candidate addresses", &report));
        }
        let mut pending = query.entry_points.clone();
        let mut reads = BTreeMap::new();
        let mut sites = BTreeMap::new();
        let mut identity = None;
        while !pending.is_empty() {
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
            let prepared = prepare_captured_batch(
                &self.metadata.snapshot_id,
                &candidates,
                decoder,
                options,
                self.metadata.platform.decoder_target(),
            )?;
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
        }
        report.unattempted_references = report
            .referenced
            .difference(&report.attempted)
            .copied()
            .collect();
        let mut request = AnalysisRequest {
            snapshot_id: self.metadata.snapshot_id.clone(),
            addresses: report.referenced.clone(),
            locations: options.catalogue.locations(),
            entry_points: query.entry_points.clone(),
            slice_seeds: query.slice_seeds.clone(),
            input_kind: InputKind::Dump,
            ..AnalysisRequest::default()
        };
        let mut evidence = BTreeMap::new();
        let mut gaps = Vec::new();
        for (a, site) in sites {
            if site.decodable {
                request.decodable.insert(a);
            }
            if site.complete_capture {
                request.captured.insert(a);
            }
            request.instructions.insert(a, site.instruction);
            evidence.insert(a, site.evidence);
            gaps.extend(site.gaps);
        }
        for &a in &request.addresses {
            request.instructions.entry(a).or_default();
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
        Ok(FilePreparedAnalysis {
            prepared: PreparedAnalysis {
                request,
                instructions: evidence,
                gaps,
                identity: identity.expect("nonempty roots"),
            },
            snapshot: self.metadata.clone(),
            reads,
            materialization: report,
        })
    }
}
