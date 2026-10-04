//! Read-only access to an analysis owned by an admitted backend.
use crate::{AnalysisRequest, AnalysisResult, AnalysisState, Analyzer};

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
    result: AnalysisResult,
}
impl CompletedAnalysis {
    pub fn from_analyzer(analyzer: Analyzer) -> Self {
        let request = analyzer.request().clone();
        Self {
            request,
            result: analyzer.finish(),
        }
    }
    #[cfg(feature = "bap")]
    pub(crate) fn from_native(request: AnalysisRequest, result: AnalysisResult) -> Self {
        Self { request, result }
    }
    pub fn into_result(self) -> AnalysisResult {
        self.result
    }
}
impl AnalysisView for CompletedAnalysis {
    fn request(&self) -> &AnalysisRequest {
        &self.request
    }
    fn state(&self) -> &AnalysisState {
        &self.result.state
    }
}
