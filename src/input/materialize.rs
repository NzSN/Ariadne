use crate::effects::{EffectQuality, InstructionEvidence, PreparationOptions, PreparedAnalysis};
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
#[path = "../../tests/input/target_resolution_unit.rs"]
mod target_resolution_tests;
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
    pub(crate) target_snapshot: Option<Arc<FileSnapshot>>,
    pub(crate) target_resolution: Option<crate::bap::target_resolution::Report>,
    pub(crate) refinement: BTreeMap<Address, crate::bap::refinement::TransferReceipt>,
    pub(crate) fault: Arc<super::fault_context::FaultCapture>,
    pub prepared: PreparedAnalysis,
    pub snapshot: Arc<SnapshotMetadata>,
    pub open_limits: OpenLimits,
    pub reads: BTreeMap<Address, ByteRead>,
    pub materialization: MaterializationReport,
}
impl FilePreparedAnalysis {
    pub fn target_resolution(&self) -> Option<&crate::bap::target_resolution::Report> {
        self.target_resolution.as_ref()
    }
    pub(crate) fn validate_target_resolution(&self) -> Result<(), crate::bap::Error> {
        let Some(report) = &self.target_resolution else {
            return Ok(());
        };
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
        crate::bap::target_resolution::validate(
            report,
            &self.prepared.request.instructions,
            &self.prepared.request.entry_points,
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

fn control_data_read(
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
}

/// Own the resolver's fixed point separately from instruction-byte discovery.
/// Graph expansion is monotone; old path witnesses remain valid, but their
/// coverage certificates must be checked against the expanded graph.
struct TargetResolutionCoordinator<'a> {
    limits: &'a crate::bap::target_resolution::Limits,
    transfers: BTreeMap<Address, crate::bap::target_resolution::Transfer>,
    report: Option<crate::bap::target_resolution::Report>,
    rounds: usize,
}

impl<'a> TargetResolutionCoordinator<'a> {
    fn new(limits: &'a crate::bap::target_resolution::Limits) -> Self {
        Self {
            limits,
            transfers: BTreeMap::new(),
            report: None,
            rounds: 0,
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
        let instructions: BTreeMap<_, _> = sites
            .iter()
            .map(|(&a, s)| (a, s.instruction.clone()))
            .collect();
        let round_limit = self.rounds >= self.limits.max_rounds;
        let mut resolved = if round_limit && self.report.is_some() {
            self.report.take().expect("previous report checked")
        } else {
            let mut limits = self.limits.clone();
            if round_limit {
                limits.max_steps = 0;
            }
            resolver::resolve(
                &snapshot.metadata.snapshot_id,
                &snapshot.metadata.artifact_sha256,
                &instructions,
                roots,
                &self.transfers,
                &limits,
                |a, n| control_data_read(snapshot, a, n),
            )
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
        resolved.graph_sha256 = resolver::graph_digest(&instructions, roots)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        resolver::validate(&resolved, &instructions, roots)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        let stopped = round_limit || resolved.stop.is_some();
        if stopped {
            for site in sites.values_mut() {
                if site.instruction.kind == InstructionKind::Indirect {
                    site.instruction.complete = false;
                }
            }
        }
        let mut changed = false;
        for row in &resolved.resolutions {
            let address = parse_target_address(&row.site)?;
            let site = sites
                .get_mut(&address)
                .ok_or(PreparationError::InvalidQuery("resolver site absent"))?;
            site.instruction.complete = row.complete;
            for value in &row.targets {
                let target = parse_target_address(value)?;
                changed |= site.instruction.targets.insert(target);
                materialization.referenced.insert(target);
                if materialization.referenced.len() > materialization.limits.max_candidates {
                    return Err(limit("candidate addresses", materialization));
                }
                if !materialization.attempted.contains(&target) {
                    pending.insert(target);
                }
            }
        }
        self.report = Some(resolved);
        Ok(stopped || (!changed && pending.is_empty()))
    }

    fn downgrade(report: &mut crate::bap::target_resolution::Report, reason: &str) {
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

    fn prepare_bap(
        &self,
        query: &AnalysisQuery,
        decoder: &Path,
        config: &crate::bap::Config,
        options: &PreparationOptions,
        limits: PrepareLimits,
        extension: PreparationExtension,
    ) -> Result<FilePreparedAnalysis, PreparationError> {
        let (refinement, target_limits) = match extension {
            PreparationExtension::None => (false, None),
            PreparationExtension::Refinement => (true, None),
            PreparationExtension::TargetResolution(limits) => (false, Some(limits)),
        };
        let mut backend = crate::bap::Backend::new(config.clone(), decoder)
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        if refinement {
            backend.enable_refinement();
        }
        if target_limits.is_some() {
            backend.enable_target_resolution();
        }
        let mut prepared = self.prepare_materialization(
            query,
            options,
            limits,
            target_limits.as_ref(),
            |s, c, o, t| {
                let batch = backend
                    .prepare(s, c, o, t)
                    .map_err(|e| PreparationError::Backend(e.to_string()))?;
                Ok((batch, backend.take_target_transfers()))
            },
        )?;
        prepared.refinement = backend.take_refinement();
        backend
            .finish()
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
        let mut identity = None;
        let mut resolver = target_limits.map(TargetResolutionCoordinator::new);
        loop {
            if pending.is_empty() {
                let Some(resolver) = &mut resolver else {
                    break;
                };
                if resolver.advance(
                    self,
                    &query.entry_points,
                    &mut sites,
                    &mut pending,
                    &mut report,
                )? {
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
            let (prepared, batch_transfers) = preparer(
                &self.metadata.snapshot_id,
                &candidates,
                options,
                self.metadata.platform.decoder_target(),
            )?;
            if let Some(resolver) = &mut resolver {
                resolver.transfers.extend(batch_transfers);
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
        let mut target_resolution = resolver.and_then(|resolver| resolver.report);
        if let Some(resolved) = &mut target_resolution {
            resolved.graph_sha256 = crate::bap::target_resolution::graph_digest(
                &request.instructions,
                &request.entry_points,
            )
            .map_err(|e| PreparationError::Backend(e.to_string()))?;
        }
        Ok(FilePreparedAnalysis {
            target_snapshot: target_limits.map(|_| Arc::new(self.clone())),
            target_resolution,
            refinement: BTreeMap::new(),
            fault: self.fault.clone(),
            prepared: PreparedAnalysis {
                request,
                instructions: evidence,
                gaps,
                identity: identity.expect("nonempty roots"),
            },
            snapshot: self.metadata.clone(),
            open_limits: self.limits.clone(),
            reads,
            materialization: report,
        })
    }
}
