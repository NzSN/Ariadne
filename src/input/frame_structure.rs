//! Capture ownership and successful preparation boundary for structural reports.
use super::{
    FilePreparedAnalysis, FileSnapshot, FramePreparation, OpenLimits, PreparationError,
    PrepareLimits,
};
use crate::investigation::frame_structure::{
    OpenLimitsProof, PreparationLimitsProof, PreparationProof, RecoveryProofs, bind_recovery,
    frame_entry_anchor, validate_chain_policy, validate_proof_policy,
};
use crate::investigation::{
    BoundFrameRecovery, CapturedFrameChain, Error, FrameStructureDiagnostic,
    FrameStructureDiagnosticKind, FrameStructureLimits, invalid,
};
use crate::recovery::RecoveryResult;

impl FrameStructureLimits {
    pub fn open_limits(&self) -> OpenLimits {
        OpenLimits {
            max_file_bytes: self.max_file_bytes,
            max_streams: self.max_streams,
            max_records: self.max_records,
            max_metadata_bytes: self.max_metadata_bytes,
            max_capture_ranges: self.max_capture_ranges,
            max_overlap: self.max_overlap,
            max_read_bytes: self.max_read_bytes,
        }
    }
    pub fn prepare_limits(&self) -> PrepareLimits {
        PrepareLimits {
            max_starts: self.max_prepare_starts,
            max_candidates: self.max_prepare_candidates,
            max_prefix_bytes: self.max_prepare_prefix_bytes,
            max_decoder_batches: self.max_prepare_decoder_batches,
            batch_size: self.prepare_batch_size,
        }
    }
}
impl FrameStructureDiagnostic {
    pub fn from_preparation_error(frame: usize, error: &(dyn std::error::Error + 'static)) -> Self {
        if let Some(PreparationError::LimitReached { reason, progress }) =
            error.downcast_ref::<PreparationError>()
        {
            Self {
                frame,
                kind: FrameStructureDiagnosticKind::PreparationLimit,
                message: (*reason).into(),
                attempted: progress.attempted.iter().copied().collect(),
                unattempted_references: progress
                    .referenced
                    .difference(&progress.attempted)
                    .copied()
                    .collect(),
            }
        } else {
            Self::new(
                frame,
                FrameStructureDiagnosticKind::PreparationFailed,
                error.to_string(),
            )
        }
    }
}
impl FileSnapshot {
    /// Every source byte/span is reread from the owning immutable snapshot before binding.
    pub fn bind_frame_recovery(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        prepared: &FilePreparedAnalysis,
        recovery: RecoveryResult,
        limits: &FrameStructureLimits,
    ) -> Result<BoundFrameRecovery, Error> {
        limits.validate()?;
        validate_chain_policy(chain, limits)?;
        if self.metadata() != prepared.snapshot.as_ref()
            || self.metadata.snapshot_id != chain.snapshot_id
            || self.metadata.artifact_sha256 != chain.artifact_sha256
            || recovery.request() != &prepared.prepared.request
        {
            return Err(invalid(
                "structural preparation/recovery belongs to another capture or query",
            ));
        }
        self.validate_thread_frames(chain)?;
        if prepared.reads.len() > limits.max_prepare_starts
            || prepared.materialization.attempted.len() > limits.max_prepare_starts
            || prepared.materialization.referenced.len() > limits.max_prepare_candidates
            || prepared.materialization.prefix_bytes > limits.max_prepare_prefix_bytes
            || prepared.materialization.decoder_batches > limits.max_prepare_decoder_batches
        {
            return Err(invalid(
                "structural preparation progress exceeds host policy",
            ));
        }
        for (&address, read) in &prepared.reads {
            if 15 > limits.max_read_bytes || *read != self.read_prefix(address, 15)? {
                return Err(invalid(
                    "structural captured bytes or span provenance changed",
                ));
            }
        }
        let p = &prepared.materialization.limits;
        let o = &prepared.open_limits;
        let proofs = RecoveryProofs {
            alignment: None,
            guard: prepared.guard_admission().cloned(),
            target: prepared.target_resolution().cloned(),
            composition: prepared.composition().cloned(),
            decoder_records: prepared
                .prepared
                .instructions
                .iter()
                .filter_map(|(site, evidence)| {
                    evidence
                        .decoder_record
                        .as_ref()
                        .map(|record| (format!("0x{site:016x}"), record.clone()))
                })
                .collect(),
            preparation: PreparationProof {
                limits: PreparationLimitsProof {
                    max_starts: p.max_starts,
                    max_candidates: p.max_candidates,
                    max_prefix_bytes: p.max_prefix_bytes,
                    max_decoder_batches: p.max_decoder_batches,
                    batch_size: p.batch_size,
                },
                open_limits: OpenLimitsProof {
                    max_file_bytes: o.max_file_bytes,
                    max_streams: o.max_streams,
                    max_records: o.max_records,
                    max_metadata_bytes: o.max_metadata_bytes,
                    max_capture_ranges: o.max_capture_ranges,
                    max_overlap: o.max_overlap,
                    max_read_bytes: o.max_read_bytes,
                },
            },
        };
        validate_proof_policy(&proofs, limits)?;
        let context = super::investigation::capture_context(prepared)?;
        bind_recovery(chain, index, recovery, context, proofs, limits)
    }

    /// Bind a conditional product while retaining the complete baseline capture
    /// and guard/target/composition evidence unchanged. Sites never become roots.
    pub fn bind_frame_recovery_hypotheses(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        prepared: &FilePreparedAnalysis,
        sites: &[u64],
        limits: &FrameStructureLimits,
    ) -> Result<BoundFrameRecovery, Error> {
        let zero = crate::recovery::recover(
            prepared.prepared.request.clone(),
            crate::recovery::RecoveryLimits {
                max_visits: 0,
                deadline_ms: 0,
            },
        )?;
        let base = self.bind_frame_recovery(chain, index, prepared, zero, limits)?;
        crate::investigation::frame_structure::bind_alignment_hypotheses(
            chain, index, base, sites, limits,
        )
    }

    /// Structural preparation always retains complete guarded BIL source proofs.
    /// The default supplies no ABI alignment premise.
    #[allow(clippy::too_many_arguments)]
    pub fn prepare_frame_structure(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        parent: Option<&BoundFrameRecovery>,
        setup: &FramePreparation<'_>,
        assume_windows_call_entry: bool,
        guard_limits: crate::bap::guard_admission::Limits,
        target_limits: Option<crate::bap::target_resolution::Limits>,
    ) -> Result<FilePreparedAnalysis, Error> {
        self.prepare_frame_structure_inner(
            chain,
            index,
            entry,
            parent,
            setup,
            assume_windows_call_entry,
            guard_limits,
            target_limits,
            None,
        )
    }
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn prepare_frame_structure_question(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        parent: Option<&BoundFrameRecovery>,
        setup: &FramePreparation<'_>,
        assume_windows_call_entry: bool,
        guard_limits: crate::bap::guard_admission::Limits,
        target_limits: crate::bap::target_resolution::Limits,
        schedule: crate::bap::target_resolution::QuestionTargetSchedule,
    ) -> Result<FilePreparedAnalysis, Error> {
        self.prepare_frame_structure_inner(
            chain,
            index,
            entry,
            parent,
            setup,
            assume_windows_call_entry,
            guard_limits,
            Some(target_limits),
            Some(schedule),
        )
    }
    #[allow(clippy::too_many_arguments)]
    fn prepare_frame_structure_inner(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        parent: Option<&BoundFrameRecovery>,
        setup: &FramePreparation<'_>,
        assume_windows_call_entry: bool,
        guard_limits: crate::bap::guard_admission::Limits,
        target_limits: Option<crate::bap::target_resolution::Limits>,
        schedule: Option<crate::bap::target_resolution::QuestionTargetSchedule>,
    ) -> Result<FilePreparedAnalysis, Error> {
        use crate::bap::guard_admission as guard;
        if self.metadata.platform != super::Platform::Windows {
            return Err(invalid(
                "structural v1 requires captured Windows AMD64 frames",
            ));
        }
        self.validate_thread_frames(chain)?;
        let frame = chain
            .frames
            .get(index)
            .ok_or_else(|| invalid("structural frame outside recovered chain"))?;
        if assume_windows_call_entry
            && frame.transition
                == Some(crate::investigation::frame_unwind::FrameTransition::MachineFrame)
        {
            return Err(invalid(
                "machine-frame activation cannot supply a normal-call entry premise",
            ));
        }
        if let Some(begin) = frame.function_begin {
            if begin != entry {
                return Err(invalid(
                    "structural root differs from captured function entry",
                ));
            }
        } else {
            let parent = parent.ok_or_else(|| {
                invalid("leaf structural root requires an independently bound parent")
            })?;
            if crate::investigation::active_frame_structure_entry(chain, index, parent)? != entry {
                return Err(invalid(
                    "structural leaf root differs from reached parent call",
                ));
            }
        }
        guard_limits.validate()?;
        let query = super::AnalysisQuery {
            entry_points: [entry].into(),
            slice_seeds: Default::default(),
        };
        let activation = guard::Activation {
            thread_id: chain.thread_id,
            frame_activation: format!("{}:{index}:0x{:016x}", chain.chain_id, frame.sp),
        };
        let anchor_sha256 = frame_entry_anchor(chain, index, entry)?;
        let roots = vec![guard::Root {
            site: format!("0x{entry:016x}"),
            function_entry: true,
            anchor_sha256: anchor_sha256.clone(),
        }];
        let query_scope_sha256 = super::materialize::guard_query_scope(
            &self.metadata.snapshot_id,
            &query,
            &setup.limits,
            &activation,
            &roots,
        )?;
        let premises = if assume_windows_call_entry {
            vec![guard::Premise {
                origin: guard::PremiseOrigin::AbiNormalCall,
                snapshot: self.metadata.snapshot_id.clone(),
                query_scope_sha256: query_scope_sha256.clone(),
                root: format!("0x{entry:016x}"),
                point: format!("0x{entry:016x}"),
                activation: activation.clone(),
                policy: guard::ABI_POLICY.into(),
                evidence_sha256: crate::reports::sha256(&serde_json::to_vec(&(
                    guard::ABI_POLICY,
                    &anchor_sha256,
                    &query_scope_sha256,
                    8u8,
                ))?),
                rsp_residues: 1 << 8,
                rsp_value: None,
            }]
        } else {
            Vec::new()
        };
        let guard = super::materialize::GuardPreparation {
            limits: guard_limits,
            activation,
            roots,
            premises,
            query_scope_sha256,
            producer: None,
        };
        Ok(
            if let (Some(target_limits), Some(schedule)) = (target_limits.as_ref(), schedule) {
                self.prepare_bap_question_targets(
                    &query,
                    setup.decoder,
                    setup.config,
                    setup.options,
                    setup.limits.clone(),
                    guard,
                    target_limits.clone(),
                    schedule,
                )?
            } else if let Some(target_limits) = target_limits {
                self.prepare_bap_guarded_targets(
                    &query,
                    setup.decoder,
                    setup.config,
                    setup.options,
                    setup.limits.clone(),
                    guard,
                    target_limits,
                )?
            } else {
                self.prepare_bap_guarded(
                    &query,
                    setup.decoder,
                    setup.config,
                    setup.options,
                    setup.limits.clone(),
                    guard,
                )?
            },
        )
    }
}
