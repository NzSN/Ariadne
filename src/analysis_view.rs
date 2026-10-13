//! Read-only access to an analysis owned by an admitted backend.
use crate::{AnalysisRequest, AnalysisResult, AnalysisState, Analyzer};
use std::sync::Arc;

mod sealed {
    pub trait Sealed {}
    impl Sealed for super::Analyzer {}
    impl Sealed for super::CompletedAnalysis {}
}
/// A snapshot/query-bound analysis view. External callers cannot fabricate an
/// implementation; native backends publish it only after finish and clean exit.
pub trait AnalysisView: sealed::Sealed {
    fn request(&self) -> &AnalysisRequest;
    fn state(&self) -> &AnalysisState;
    /// Retain immutable evidence without duplicating a completed backend's state.
    fn shared_state(&self) -> Arc<AnalysisState> {
        Arc::new(self.state().clone())
    }
}
impl AnalysisView for Analyzer {
    fn request(&self) -> &AnalysisRequest {
        self.request()
    }
    fn state(&self) -> &AnalysisState {
        self.state()
    }
}
/// Completed analysis retained for evidence binding and report rendering.
pub struct CompletedAnalysis {
    request: AnalysisRequest,
    state: Arc<AnalysisState>,
    snapshot_id: String,
    missing_slice_seeds: crate::AddressSet,
}
impl CompletedAnalysis {
    pub fn from_analyzer(analyzer: Analyzer) -> Self {
        let request = analyzer.request().clone();
        Self::from_result(request, analyzer.finish())
    }
    #[cfg(feature = "bap")]
    pub(crate) fn from_native(request: AnalysisRequest, result: AnalysisResult) -> Self {
        Self::from_result(request, result)
    }
    fn from_result(request: AnalysisRequest, result: AnalysisResult) -> Self {
        Self {
            request,
            state: Arc::new(result.state),
            snapshot_id: result.snapshot_id,
            missing_slice_seeds: result.missing_slice_seeds,
        }
    }
    pub fn into_result(self) -> AnalysisResult {
        AnalysisResult {
            snapshot_id: self.snapshot_id,
            state: Arc::unwrap_or_clone(self.state),
            missing_slice_seeds: self.missing_slice_seeds,
        }
    }
}
impl AnalysisView for CompletedAnalysis {
    fn request(&self) -> &AnalysisRequest {
        &self.request
    }
    fn state(&self) -> &AnalysisState {
        &self.state
    }
    fn shared_state(&self) -> Arc<AnalysisState> {
        Arc::clone(&self.state)
    }
}

#[cfg(test)]
#[path = "../tests/analysis_view/completed.rs"]
mod tests;
