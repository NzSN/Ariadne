//! Capture-only frame evidence and explicit per-frame preparation.
use super::{AnalysisQuery, FilePreparedAnalysis, FileSnapshot, Platform, PrepareLimits};
use crate::investigation::frame_unwind::{FrameModule, FrameSeed, hex, recover_frames};
use crate::investigation::{
    CapturedFrameChain, Contributor, Error, FRAME_UNWIND_PROFILE, FrameMemoryEvidence,
    FrameRecoveryLimits, Span, invalid,
};
use std::path::Path;

pub struct FramePreparation<'a> {
    pub decoder: &'a Path,
    pub config: &'a crate::bap::Config,
    pub options: &'a crate::effects::PreparationOptions,
    pub limits: PrepareLimits,
}

impl FileSnapshot {
    /// Bind the opt-in normal-call assumption to an unwind-validated function
    /// entry in one physical activation. The captured SP is only an activation
    /// identifier; it supplies no earlier entry residue.
    pub(crate) fn frame_guard_preparation(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        limits: &PrepareLimits,
        guard_limits: crate::bap::guard_admission::Limits,
    ) -> Result<(AnalysisQuery, super::materialize::GuardPreparation), Error> {
        use crate::bap::guard_admission as guard;
        if self.metadata.platform != Platform::Windows {
            return Err(invalid(
                "normal-call entry assumption requires Windows AMD64",
            ));
        }
        self.validate_thread_frames(chain)?;
        let frame = chain
            .frames
            .get(index)
            .ok_or_else(|| invalid("frame index outside recovered chain"))?;
        if frame.function_begin != Some(entry) {
            return Err(invalid(
                "normal-call entry assumption requires validated function_begin",
            ));
        }
        guard_limits.validate()?;
        let query = AnalysisQuery {
            entry_points: [entry].into(),
            slice_seeds: Default::default(),
        };
        let activation = guard::Activation {
            thread_id: chain.thread_id,
            frame_activation: format!("{}:{index}:0x{:016x}", chain.chain_id, frame.sp),
        };
        let anchor_sha256 = crate::reports::sha256(&serde_json::to_vec(&(
            "captured-frame-function-entry/v1",
            &chain.chain_id,
            index,
            frame.function_begin,
            frame.function_end,
            &activation,
        ))?);
        let roots = vec![guard::Root {
            site: format!("0x{entry:016x}"),
            function_entry: true,
            anchor_sha256: anchor_sha256.clone(),
        }];
        let query_scope_sha256 = super::materialize::guard_query_scope(
            &self.metadata.snapshot_id,
            &query,
            limits,
            &activation,
            &roots,
        )?;
        let evidence_sha256 = crate::reports::sha256(&serde_json::to_vec(&(
            guard::ABI_POLICY,
            &anchor_sha256,
            &query_scope_sha256,
            8u8,
        ))?);
        let premise = guard::Premise {
            origin: guard::PremiseOrigin::AbiNormalCall,
            snapshot: self.metadata.snapshot_id.clone(),
            query_scope_sha256: query_scope_sha256.clone(),
            root: format!("0x{entry:016x}"),
            point: format!("0x{entry:016x}"),
            activation: activation.clone(),
            policy: guard::ABI_POLICY.into(),
            evidence_sha256,
            rsp_residues: 1 << 8,
            rsp_value: None,
        };
        Ok((
            query,
            super::materialize::GuardPreparation {
                limits: guard_limits,
                activation,
                roots,
                premises: vec![premise],
                query_scope_sha256,
                producer: None,
            },
        ))
    }

    pub fn prepare_frame_with_bap_assuming_windows_call_entry(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        setup: &FramePreparation<'_>,
        guard_limits: crate::bap::guard_admission::Limits,
    ) -> Result<FilePreparedAnalysis, Error> {
        let (query, guard) =
            self.frame_guard_preparation(chain, index, entry, &setup.limits, guard_limits)?;
        Ok(self.prepare_bap_guarded(
            &query,
            setup.decoder,
            setup.config,
            setup.options,
            setup.limits.clone(),
            guard,
        )?)
    }

    /// Jointly recover captured indirect targets and check normal alignment
    /// paths under the same validated physical Windows activation.
    pub fn prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        setup: &FramePreparation<'_>,
        guard_limits: crate::bap::guard_admission::Limits,
        target_limits: crate::bap::target_resolution::Limits,
    ) -> Result<FilePreparedAnalysis, Error> {
        let (query, guard) =
            self.frame_guard_preparation(chain, index, entry, &setup.limits, guard_limits)?;
        Ok(self.prepare_bap_guarded_targets(
            &query,
            setup.decoder,
            setup.config,
            setup.options,
            setup.limits.clone(),
            guard,
            target_limits,
        )?)
    }

    /// Recheck every context/unwind/stack receipt against the owning capture.
    pub fn validate_thread_frames(&self, chain: &CapturedFrameChain) -> Result<(), Error> {
        if chain.snapshot_id != self.metadata.snapshot_id
            || chain.artifact_sha256 != self.metadata.artifact_sha256
        {
            return Err(invalid("frame chain belongs to another capture"));
        }
        let expected = self.recover_thread_frames_with_profile(
            chain.thread_id,
            chain.limits.clone(),
            &chain.profile,
        )?;
        if expected != *chain {
            return Err(invalid("frame evidence differs from owning capture"));
        }
        Ok(())
    }
    pub fn recover_thread_frames(
        &self,
        thread_id: u32,
        limits: FrameRecoveryLimits,
    ) -> Result<CapturedFrameChain, Error> {
        self.recover_thread_frames_with_profile(thread_id, limits, FRAME_UNWIND_PROFILE)
    }
    fn recover_thread_frames_with_profile(
        &self,
        thread_id: u32,
        limits: FrameRecoveryLimits,
        profile: &str,
    ) -> Result<CapturedFrameChain, Error> {
        let stream = self
            .metadata
            .streams
            .iter()
            .find(|s| s.kind == 3)
            .ok_or_else(|| invalid("thread-list-required-for-frame-recovery"))?;
        let start = stream.file_offset as usize;
        let len = stream.size as usize;
        let data = &self.bytes[start..start + len];
        let count =
            u32::from_le_bytes(data[..4].try_into().expect("validated thread list")) as usize;
        let padding = len - count * 48;
        let record = data[padding..]
            .chunks_exact(48)
            .find(|r| u32::from_le_bytes(r[..4].try_into().expect("record")) == thread_id)
            .ok_or_else(|| invalid("thread id is outside capture"))?;
        let (context_stream, offset, size) = if self
            .metadata
            .exception
            .as_ref()
            .is_some_and(|e| e.thread_id == thread_id)
        {
            let ex = self
                .metadata
                .streams
                .iter()
                .find(|s| s.kind == 6)
                .ok_or_else(|| invalid("missing exception stream"))?;
            let b =
                &self.bytes[ex.file_offset as usize..ex.file_offset as usize + ex.size as usize];
            (
                6,
                u32::from_le_bytes(b[164..168].try_into().expect("validated exception")),
                u32::from_le_bytes(b[160..164].try_into().expect("validated exception")),
            )
        } else {
            (
                3,
                u32::from_le_bytes(record[44..48].try_into().expect("thread context")),
                u32::from_le_bytes(record[40..44].try_into().expect("thread context")),
            )
        };
        if size < 1232 {
            return Err(invalid("missing-or-truncated-frame-context"));
        }
        let context = self
            .bytes
            .get(offset as usize..offset as usize + 1232)
            .ok_or_else(|| invalid("frame context outside artifact"))?;
        let seed = FrameSeed {
            snapshot_id: self.metadata.snapshot_id.clone(),
            artifact_sha256: self.metadata.artifact_sha256.clone(),
            artifact_bytes: self.bytes.len(),
            platform: if self.metadata.platform == Platform::Windows {
                "windows-amd64"
            } else {
                "linux-amd64"
            }
            .into(),
            thread_id,
            context_stream,
            context_offset: u64::from(offset),
            context_hex: hex(context),
            thread_record_hex: hex(record),
            modules: self
                .metadata
                .modules
                .iter()
                .map(|m| FrameModule {
                    base: m.base,
                    size: m.size,
                    timestamp: m.timestamp,
                    checksum: m.checksum,
                })
                .collect(),
        };
        recover_frames(seed, limits, profile, &mut |address, requested| {
            let read = self.read_prefix(address, requested)?;
            Ok(FrameMemoryEvidence {
                address,
                requested,
                bytes_hex: hex(&read.bytes),
                spans: read
                    .spans
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
                    .collect(),
            })
        })
    }

    /// A new, explicitly rooted preparation for one validated activation.
    pub fn prepare_frame_with_bap(
        &self,
        chain: &CapturedFrameChain,
        index: usize,
        entry: u64,
        setup: &FramePreparation<'_>,
    ) -> Result<FilePreparedAnalysis, Error> {
        if chain.snapshot_id != self.metadata.snapshot_id
            || chain.artifact_sha256 != self.metadata.artifact_sha256
        {
            return Err(invalid("frame chain belongs to another capture"));
        }
        self.validate_thread_frames(chain)?;
        let frame = chain
            .frames
            .get(index)
            .ok_or_else(|| invalid("frame index outside recovered chain"))?;
        if frame.function_begin.is_some_and(|begin| begin != entry) {
            return Err(invalid("frame entry disagrees with unwind function"));
        }
        let query = AnalysisQuery {
            entry_points: [entry].into(),
            slice_seeds: Default::default(),
        };
        Ok(self.prepare_with_bap(
            &query,
            setup.decoder,
            setup.config,
            setup.options,
            setup.limits.clone(),
        )?)
    }
}
