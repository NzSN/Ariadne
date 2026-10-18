use super::model::{FrameQuestionLimits, QuestionLayerStatus, QuestionReceipt};
use std::time::Instant;
pub(crate) struct Meter<'a> {
    pub work: u64,
    cap: u64,
    started: Instant,
    total: Instant,
    limits: &'a FrameQuestionLimits,
    replay: Option<&'a QuestionReceipt>,
}
impl<'a> Meter<'a> {
    pub(crate) fn new(
        cap: u64,
        limits: &'a FrameQuestionLimits,
        total: Instant,
        replay: Option<&'a QuestionReceipt>,
    ) -> Self {
        Self {
            work: 0,
            cap,
            started: Instant::now(),
            total,
            limits,
            replay,
        }
    }
    pub(crate) fn resume(
        cap: u64,
        work: u64,
        limits: &'a FrameQuestionLimits,
        total: Instant,
        replay: Option<&'a QuestionReceipt>,
    ) -> Self {
        let mut m = Self::new(cap, limits, total, replay);
        m.work = work;
        m
    }
    pub(crate) fn tick(&mut self) -> Result<(), String> {
        self.charge(1)
    }
    pub(crate) fn charge(&mut self, count: u64) -> Result<(), String> {
        if count > self.cap.saturating_sub(self.work) {
            return Err("work-limit".into());
        }
        let reason = if let Some(r) = self.replay {
            r.reason
                .as_deref()
                .filter(|s| matches!(*s, "deadline" | "total-deadline"))
                .filter(|_| self.work >= r.work)
        } else if self.total.elapsed().as_millis() >= u128::from(self.limits.total_deadline_ms) {
            Some("total-deadline")
        } else if self.started.elapsed().as_millis() >= u128::from(self.limits.deadline_ms) {
            Some("deadline")
        } else {
            None
        };
        if let Some(r) = reason {
            return Err(r.into());
        }
        self.work += count;
        Ok(())
    }
    pub(crate) fn remaining(&self) -> u64 {
        self.cap.saturating_sub(self.work)
    }
    pub(crate) fn finish(&self, stop: Option<String>) -> QuestionReceipt {
        QuestionReceipt {
            status: if stop.is_some() {
                QuestionLayerStatus::WorkStopped
            } else {
                QuestionLayerStatus::Finished
            },
            work: self.work,
            elapsed_ms: self.replay.map_or_else(
                || u64::try_from(self.started.elapsed().as_millis()).unwrap_or(u64::MAX),
                |r| r.elapsed_ms,
            ),
            reason: stop,
        }
    }
}
pub(crate) fn unavailable(reason: impl Into<String>) -> QuestionReceipt {
    QuestionReceipt {
        reason: Some(reason.into()),
        ..QuestionReceipt::default()
    }
}
pub(crate) fn finished() -> QuestionReceipt {
    QuestionReceipt {
        status: QuestionLayerStatus::Finished,
        work: 0,
        elapsed_ms: 0,
        reason: None,
    }
}
