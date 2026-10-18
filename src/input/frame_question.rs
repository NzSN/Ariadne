//! Capture-owned question evidence. Reader/preparer handles never leave results.
use super::{FileSnapshot, FramePreparation};
use crate::bap::target_resolution::{DataRead, QuestionTargetSchedule};
use crate::investigation::frame_question::{FaultEvidence, SourceProvider};
use crate::investigation::{
    BoundFrameStructure, Error, FrameQuestion, FrameQuestionEvidence, FrameQuestionKind,
    FrameQuestionLimits, FrameStructureQuestion, bind_frame_structure,
};
use std::path::PathBuf;
use std::time::Instant;
struct CaptureProvider {
    snapshot: FileSnapshot,
    decoder: PathBuf,
    config: crate::bap::Config,
    options: crate::effects::PreparationOptions,
}
impl SourceProvider for CaptureProvider {
    fn read(&self, address: u64, length: usize) -> Result<DataRead, Error> {
        super::materialize::control_data_read(&self.snapshot, address, length)
    }
    fn extend(
        &mut self,
        source: &BoundFrameStructure,
        question: &FrameQuestion,
        limits: &FrameQuestionLimits,
    ) -> Result<Option<BoundFrameStructure>, Error> {
        let frame = question.question.frame();
        let Some((_, old)) = source.recoveries().iter().find(|(i, _)| *i == frame) else {
            return Ok(None);
        };
        let needed = !old
            .recovery()
            .state()
            .decoded
            .contains(&question.question.site())
            || matches!(question.question, FrameQuestionKind::Alternative { .. })
                && old
                    .request()
                    .instructions
                    .get(&question.question.site())
                    .is_some_and(|i| i.kind == crate::InstructionKind::Indirect)
                && old.proofs().target.as_ref().is_some_and(|t| {
                    t.resolutions.iter().any(|r| {
                        r.site == format!("0x{:016x}", question.question.site()) && !r.complete
                    })
                });
        if !needed {
            return Ok(None);
        }
        if self.snapshot.metadata().snapshot_id != source.chain().snapshot_id
            || self.snapshot.metadata().artifact_sha256 != source.chain().artifact_sha256
        {
            return Err("question provider capture changed".into());
        }
        let policy = limits.structural.clone();
        let Some(&entry) = old.request().entry_points.first() else {
            return Ok(None);
        };
        let setup = FramePreparation {
            decoder: &self.decoder,
            config: &self.config,
            options: &self.options,
            limits: policy.prepare_limits(),
        };
        let parent = source
            .recoveries()
            .iter()
            .find(|(i, _)| *i == frame + 1)
            .map(|(_, r)| r);
        let abi = old.proofs().guard.as_ref().is_some_and(|g| {
            g.input
                .premises
                .iter()
                .any(|p| p.origin == crate::bap::guard_admission::PremiseOrigin::AbiNormalCall)
        });
        let mut guard = policy.guard.clone();
        guard.max_elapsed_ms = guard.max_elapsed_ms.min(limits.deadline_ms);
        let mut targets = policy.target.clone();
        targets.max_steps = targets.max_steps.min(limits.resolver_work as usize);
        targets.max_elapsed_ms = targets.max_elapsed_ms.min(limits.deadline_ms);
        let schedule = QuestionTargetSchedule {
            priority: [question.question.site()].into(),
            quantum: limits.quantum,
            deadline: Instant::now()
                .checked_add(std::time::Duration::from_millis(limits.total_deadline_ms)),
            work: std::cell::Cell::new(0),
            service: std::cell::RefCell::new(Vec::new()),
        };
        let prepared = self.snapshot.prepare_frame_structure_question(
            source.chain(),
            frame,
            entry,
            parent,
            &setup,
            abi,
            guard,
            targets,
            schedule,
        )?;
        let replacement = if let Some(h) = old.alignment_hypotheses() {
            let sites = h
                .hypotheses
                .iter()
                .map(|h| u64::from_str_radix(h.point.trim_start_matches("0x"), 16))
                .collect::<Result<Vec<_>, _>>()?;
            self.snapshot.bind_frame_recovery_hypotheses(
                source.chain(),
                frame,
                &prepared,
                &sites,
                &policy,
            )?
        } else {
            let recovery = crate::recovery::recover(
                prepared.prepared.request.clone(),
                policy.recovery_limits(),
            )?;
            self.snapshot.bind_frame_recovery(
                source.chain(),
                frame,
                &prepared,
                recovery,
                &policy,
            )?
        };
        let mut rows = Vec::new();
        // Copies here create a separately admitted revision, not an interface copy.
        for (i, r) in source.recoveries() {
            if *i != frame {
                rows.push((*i, r.clone()));
            }
        }
        rows.push((frame, replacement));
        let next = bind_frame_structure(
            source.chain().clone(),
            FrameStructureQuestion {
                from_frame: source.question().from_frame,
                to_frame: source.question().to_frame,
            },
            rows,
            source.diagnostics().to_vec(),
            policy,
        )?;
        Ok(Some(next))
    }
}
impl FileSnapshot {
    pub fn frame_question_evidence(
        &self,
        source: &BoundFrameStructure,
        setup: &FramePreparation<'_>,
    ) -> Result<FrameQuestionEvidence, Error> {
        if self.metadata().snapshot_id != source.chain().snapshot_id
            || self.metadata().artifact_sha256 != source.chain().artifact_sha256
        {
            return Err("question evidence provider belongs to another capture".into());
        }
        self.validate_thread_frames(source.chain())?;
        let mut out = FrameQuestionEvidence::default();
        let f = &self.fault.evidence;
        let fields = crate::investigation::fault_context::values(&f.data);
        if fields.get("thread_id").copied() == Some(u64::from(source.chain().thread_id))
            && fields.get("reg:rip").copied() == source.chain().frames.first().map(|f| f.pc)
        {
            out.data.fault = Some(FaultEvidence {
                metadata: f.metadata.clone(),
                data: f.data.clone(),
            });
        }
        out.provider = Some(Box::new(CaptureProvider {
            snapshot: self.clone(),
            decoder: setup.decoder.to_path_buf(),
            config: setup.config.clone(),
            options: setup.options.clone(),
        }));
        Ok(out)
    }
}
