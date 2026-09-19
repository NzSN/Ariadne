//! Domain adapter for the compiler-generated port. It receives typed public
//! inputs and returns typed observations of the real Analyzer.

use std::cell::RefCell;
use std::rc::Rc;

use ariadne::*;
use mirrorrust::BindingError;
use num_bigint::BigInt;

use crate::Evidence;
use crate::generated::{
    AriadneReplayObservation, AriadneReplayPort, InitializeInput, MiTypeO1Item as EdgeRow,
    MiTypeO3Item as ObligationRow, MiTypeO6Item as ProvenanceRow, MiTypeO7Item as ReachingRow,
    MiTypeO7ItemF0Item as DefinitionRow, MirrorSet,
};

pub(crate) struct Adapter {
    analyzer: Option<Analyzer>,
    fixture: String,
    evidence: Rc<RefCell<Evidence>>,
}

impl Adapter {
    pub(crate) fn new(evidence: Rc<RefCell<Evidence>>) -> Self {
        Self {
            analyzer: None,
            fixture: String::new(),
            evidence,
        }
    }

    fn advance(&mut self, stable_action: &'static str) -> Result<(), BindingError> {
        let analyzer = self
            .analyzer
            .as_mut()
            .ok_or_else(|| BindingError::new("not_initialized", "initialize must run first"))?;
        if !analyzer.step() {
            return Err(BindingError::new(
                "already_done",
                "step requested after completion",
            ));
        }
        self.evidence.borrow_mut().record_action(stable_action);
        Ok(())
    }
}

impl AriadneReplayPort for Adapter {
    fn initialize(&mut self, input: InitializeInput) -> Result<(), BindingError> {
        let request = crate::fixtures::request(&input.fixture)
            .map_err(|e| BindingError::new("invalid_fixture", e))?;
        self.analyzer = Some(
            Analyzer::new(request)
                .map_err(|e| BindingError::new("invalid_request", e.to_string()))?,
        );
        self.fixture = input.fixture;
        let mut evidence = self.evidence.borrow_mut();
        evidence.fixtures.push(self.fixture.clone());
        evidence.previous_action = None;
        Ok(())
    }

    fn visit(&mut self) -> Result<(), BindingError> {
        self.advance("Visit")
    }
    fn finish_recovery(&mut self) -> Result<(), BindingError> {
        self.advance("FinishRecovery")
    }
    fn propagate(&mut self) -> Result<(), BindingError> {
        self.advance("Propagate")
    }
    fn finish_dataflow(&mut self) -> Result<(), BindingError> {
        self.advance("FinishDataflow")
    }
    fn expand_slice(&mut self) -> Result<(), BindingError> {
        self.advance("ExpandSlice")
    }
    fn finish_slice(&mut self) -> Result<(), BindingError> {
        self.advance("FinishSlice")
    }

    fn observe(&mut self) -> Result<AriadneReplayObservation, BindingError> {
        let state = self
            .analyzer
            .as_ref()
            .ok_or_else(|| BindingError::new("not_initialized", "initialize must run first"))?
            .state();
        // Application-to-model mapping only. Generated NativeCodec implementations
        // own wire keys, value encoding, and shape/uniqueness validation.
        let observation = AriadneReplayObservation {
            fixture_id: self.fixture.clone(),
            phase: match state.phase {
                Phase::Recover => "recover",
                Phase::Dataflow => "dataflow",
                Phase::Slice => "slice",
                Phase::Done => "done",
            }
            .into(),
            pending: addresses(&state.pending),
            visited: addresses(&state.visited),
            decoded: addresses(&state.decoded),
            slice: addresses(&state.slice),
            edges: MirrorSet(
                state
                    .edges
                    .iter()
                    .map(|e| EdgeRow {
                        field_0: e.dst.into(),
                        field_1: match e.kind {
                            EdgeKind::Next => "next",
                            EdgeKind::Taken => "taken",
                            EdgeKind::Fallthrough => "fallthrough",
                            EdgeKind::Jump => "jump",
                            EdgeKind::Indirect => "indirect",
                            EdgeKind::Summary => "summary",
                            EdgeKind::Call => "call",
                        }
                        .into(),
                        field_2: e.src.into(),
                    })
                    .collect(),
            ),
            obligations: MirrorSet(
                state
                    .obligations
                    .iter()
                    .map(|o| ObligationRow {
                        field_0: match o.reason {
                            ObligationReason::Unavailable => "unavailable",
                            ObligationReason::DecodeFailed => "decode-failed",
                            ObligationReason::IndirectTargets => "indirect-targets",
                            ObligationReason::CallTargets => "call-targets",
                        }
                        .into(),
                        field_1: o.site.into(),
                    })
                    .collect(),
            ),
            provenance: MirrorSet(
                state
                    .provenance
                    .iter()
                    .map(|(&a, source)| ProvenanceRow {
                        field_0: match source {
                            ByteSource::Captured => "captured",
                            ByteSource::File => "file",
                            ByteSource::Unavailable => "unavailable",
                        }
                        .into(),
                        field_1: a.into(),
                    })
                    .collect(),
            ),
            reaching: MirrorSet(
                state
                    .reaching
                    .iter()
                    .map(|(&a, definitions)| ReachingRow {
                        field_0: MirrorSet(
                            definitions
                                .iter()
                                .map(|d| DefinitionRow {
                                    field_0: d.loc.clone(),
                                    field_1: match d.origin {
                                        DefinitionOrigin::Entry => "entry",
                                        DefinitionOrigin::Instruction => "instruction",
                                    }
                                    .into(),
                                    field_2: d.site.into(),
                                })
                                .collect(),
                        ),
                        field_1: a.into(),
                    })
                    .collect(),
            ),
        };
        let mut evidence = self.evidence.borrow_mut();
        evidence.observations += 1;
        if state.phase == Phase::Done {
            evidence.completed += 1;
        }
        Ok(observation)
    }
}

impl Drop for Adapter {
    fn drop(&mut self) {
        // The generated LocalBinding owns this port. Its disposal callback is
        // a no-op, so record actual release after the Analyzer has been dropped.
        drop(self.analyzer.take());
        self.evidence.borrow_mut().port_drops += 1;
    }
}

fn addresses(values: &AddressSet) -> MirrorSet<BigInt> {
    MirrorSet(values.iter().copied().map(BigInt::from).collect())
}
