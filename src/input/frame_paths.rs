//! Capture-only frame evidence and explicit per-frame preparation.
use super::{AnalysisQuery, FilePreparedAnalysis, FileSnapshot, Platform, PrepareLimits};
use crate::investigation::frame_unwind::{FrameModule, FrameSeed, hex, recover_frames};
use crate::investigation::{
    CapturedFrameChain, Contributor, Error, FrameMemoryEvidence, FrameRecoveryLimits, Span, invalid,
};
use std::path::Path;

pub struct FramePreparation<'a> {
    pub decoder: &'a Path,
    pub config: &'a crate::bap::Config,
    pub options: &'a crate::effects::PreparationOptions,
    pub limits: PrepareLimits,
}

impl FileSnapshot {
    /// Recheck every context/unwind/stack receipt against the owning capture.
    pub fn validate_thread_frames(&self, chain: &CapturedFrameChain) -> Result<(), Error> {
        if chain.snapshot_id != self.metadata.snapshot_id
            || chain.artifact_sha256 != self.metadata.artifact_sha256
        {
            return Err(invalid("frame chain belongs to another capture"));
        }
        let expected = self.recover_thread_frames(chain.thread_id, chain.limits.clone())?;
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
        recover_frames(seed, limits, &mut |address, requested| {
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
