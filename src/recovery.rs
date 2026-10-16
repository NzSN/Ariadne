//! Bounded control-flow recovery before the `FinishRecovery` action.
//!
//! A recovered prefix remains in `Recover`, including when its pending set is
//! empty. It supplies no reaching definitions, slice or completed-analysis view.

use crate::{
    AddressSet, AnalysisRequest, Analyzer, AnalyzerMetrics, ByteSource, EdgeSet, InvalidRequest,
    ObligationSet, Phase,
};
use std::collections::BTreeMap;
use std::error::Error;
use std::fmt;
use std::time::Instant;

/// Cooperative producer limits. Zero is a real limit, not an unlimited marker.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RecoveryLimits {
    pub max_visits: u64,
    pub deadline_ms: u64,
}

/// Why the producer stopped before performing another `Visit` action.
/// Queue exhaustion has priority over either resource limit.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecoveryStop {
    Drained,
    VisitLimit,
    Deadline,
}

/// Work performed by the recovery producer, with a separate clock observation.
/// Replaying this receipt validates the prefix, not the reported wall clock.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RecoveryReceipt {
    pub visits: u64,
    pub elapsed_ms: u64,
    pub stop: RecoveryStop,
}

/// Only the control projection of a recovery prefix. Access through a result is
/// immutable; there is no dataflow or slicing state in this type.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RecoveryState {
    pub pending: AddressSet,
    pub visited: AddressSet,
    pub decoded: AddressSet,
    pub provenance: BTreeMap<u64, ByteSource>,
    pub edges: EdgeSet,
    pub obligations: ObligationSet,
}

impl RecoveryState {
    /// A drained recovery prefix has not executed `FinishRecovery`.
    pub fn phase(&self) -> Phase {
        Phase::Recover
    }
}

/// A privately constructed immutable request, control projection and receipt.
/// This type deliberately does not implement `AnalysisView`.
///
/// ```compile_fail
/// use ariadne::{AnalysisView, recovery::RecoveryResult};
/// fn completed_view(result: &RecoveryResult) -> &dyn AnalysisView {
///     result
/// }
/// ```
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RecoveryResult {
    request: AnalysisRequest,
    state: RecoveryState,
    limits: RecoveryLimits,
    receipt: RecoveryReceipt,
    metrics: AnalyzerMetrics,
}

impl RecoveryResult {
    pub fn request(&self) -> &AnalysisRequest {
        &self.request
    }

    pub fn state(&self) -> &RecoveryState {
        &self.state
    }

    pub fn limits(&self) -> &RecoveryLimits {
        &self.limits
    }

    pub fn receipt(&self) -> &RecoveryReceipt {
        &self.receipt
    }

    pub fn metrics(&self) -> AnalyzerMetrics {
        self.metrics
    }

    fn from_analyzer(analyzer: Analyzer, limits: RecoveryLimits, receipt: RecoveryReceipt) -> Self {
        let (request, state, metrics) = analyzer.into_recovery_parts();
        Self {
            request,
            state: RecoveryState {
                pending: state.pending,
                visited: state.visited,
                decoded: state.decoded,
                provenance: state.provenance,
                edges: state.edges,
                obligations: state.obligations,
            },
            limits,
            receipt,
            metrics,
        }
    }
}

/// Validate the request and perform only deterministic `Visit` actions. Limits
/// are checked before the next visit; one admitted visit may exceed the time
/// limit. Request validation is not covered by this cooperative deadline.
pub fn recover(
    request: AnalysisRequest,
    limits: RecoveryLimits,
) -> Result<RecoveryResult, InvalidRequest> {
    let mut analyzer = Analyzer::new(request)?;
    let started = Instant::now();
    let mut visits = 0;
    let (stop, elapsed_ms) = loop {
        let elapsed_ms = u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX);
        if analyzer.state().pending.is_empty() {
            break (RecoveryStop::Drained, elapsed_ms);
        }
        if visits >= limits.max_visits {
            break (RecoveryStop::VisitLimit, elapsed_ms);
        }
        if elapsed_ms >= limits.deadline_ms {
            break (RecoveryStop::Deadline, elapsed_ms);
        }
        // A nonempty pending queue ensures this action is Visit, never
        // FinishRecovery (which initializes the dataflow caches).
        analyzer.step();
        visits += 1;
    };
    Ok(RecoveryResult::from_analyzer(
        analyzer,
        limits,
        RecoveryReceipt {
            visits,
            elapsed_ms,
            stop,
        },
    ))
}

/// Failure to validate an exact producer prefix within the verifier's own cap.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RecoveryReplayError {
    InvalidRequest(InvalidRequest),
    ReplayLimit,
    InvalidReceipt(&'static str),
}

impl fmt::Display for RecoveryReplayError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidRequest(error) => write!(f, "{error}"),
            Self::ReplayLimit => write!(f, "recovery receipt exceeds the host replay visit limit"),
            Self::InvalidReceipt(reason) => write!(f, "invalid recovery receipt: {reason}"),
        }
    }
}

impl Error for RecoveryReplayError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::InvalidRequest(error) => Some(error),
            Self::ReplayLimit | Self::InvalidReceipt(_) => None,
        }
    }
}

/// Replay the exact deterministic visit prefix recorded by the producer. The
/// host cap is independent of the producer's declared limits and is checked
/// before constructing an analyzer. Clock consistency checks cannot establish
/// that the producer actually measured the reported elapsed time.
pub fn replay_recovery(
    request: AnalysisRequest,
    limits: RecoveryLimits,
    receipt: RecoveryReceipt,
    max_replay_visits: u64,
) -> Result<RecoveryResult, RecoveryReplayError> {
    if receipt.visits > max_replay_visits {
        return Err(RecoveryReplayError::ReplayLimit);
    }
    let invalid = RecoveryReplayError::InvalidReceipt;
    if receipt.visits > limits.max_visits {
        return Err(invalid("visit count exceeds the producer limit"));
    }
    if limits.deadline_ms == 0 && receipt.visits != 0 {
        return Err(invalid("a zero deadline cannot admit a visit"));
    }
    let mut analyzer = Analyzer::new(request).map_err(RecoveryReplayError::InvalidRequest)?;
    for _ in 0..receipt.visits {
        if analyzer.state().pending.is_empty() {
            return Err(invalid("visit count extends beyond the drained queue"));
        }
        analyzer.step();
    }
    let expected_stop = if analyzer.state().pending.is_empty() {
        RecoveryStop::Drained
    } else if receipt.visits == limits.max_visits {
        RecoveryStop::VisitLimit
    } else {
        if receipt.elapsed_ms < limits.deadline_ms {
            return Err(invalid("deadline stop precedes the declared deadline"));
        }
        RecoveryStop::Deadline
    };
    if receipt.stop != expected_stop {
        return Err(invalid("stop does not match the exact recovered prefix"));
    }
    Ok(RecoveryResult::from_analyzer(analyzer, limits, receipt))
}
