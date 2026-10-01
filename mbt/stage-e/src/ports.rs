use crate::{SharedEvidence, ir_binding as ib, machine_binding as mb};
use ariadne::{EdgeKind, llvm_ir as ir, machine_state as ms};
use mirrorrust::BindingError;
use std::collections::BTreeMap;

fn unavailable() -> BindingError {
    BindingError::new("not_initialized", "initialize must run first")
}
fn finished() -> BindingError {
    BindingError::new("already_done", "step requested after completion")
}
fn edge_kind(kind: EdgeKind) -> &'static str {
    match kind {
        EdgeKind::Next => "next",
        EdgeKind::Taken => "taken",
        EdgeKind::Fallthrough => "fallthrough",
        EdgeKind::Jump => "jump",
        EdgeKind::Indirect => "indirect",
        EdgeKind::Summary => "summary",
        EdgeKind::Call => "call",
    }
}
macro_rules! edges {
    ($values:expr, $row:ident) => {
        mb::MirrorSet(
            $values
                .iter()
                .map(|edge| mb::$row {
                    field_0: edge.dst.into(),
                    field_1: edge_kind(edge.kind).into(),
                    field_2: edge.src.into(),
                })
                .collect(),
        )
    };
}

pub struct MachineStatePort {
    requests: BTreeMap<String, ms::Request>,
    case_id: String,
    analyzer: Option<ms::Analyzer>,
    evidence: SharedEvidence,
}
impl MachineStatePort {
    pub fn new(request: ms::Request, evidence: SharedEvidence) -> Self {
        Self::with_cases([("MachineStateReplay".into(), request)].into(), evidence)
    }
    pub fn with_cases(requests: BTreeMap<String, ms::Request>, evidence: SharedEvidence) -> Self {
        Self {
            requests,
            case_id: String::new(),
            analyzer: None,
            evidence,
        }
    }
    fn advance(&mut self) -> Result<(), BindingError> {
        if self.analyzer.as_mut().ok_or_else(unavailable)?.step() {
            Ok(())
        } else {
            Err(finished())
        }
    }
}
impl mb::MachineStateReplayPort for MachineStatePort {
    fn initialize(&mut self, input: mb::InitializeInput) -> Result<(), BindingError> {
        let request = self
            .requests
            .get(&input.case_id)
            .ok_or_else(|| BindingError::new("unknown_case", "unknown machine case"))?;
        self.case_id = input.case_id;
        self.evidence.borrow_mut().cases.push(self.case_id.clone());
        self.analyzer = Some(
            ms::Analyzer::new(request.clone())
                .map_err(|error| BindingError::new("invalid_request", error.to_string()))?,
        );
        self.evidence.borrow_mut().initializations += 1;
        self.evidence.borrow_mut().previous_action = None;
        self.evidence.borrow_mut().record_action("Initialize");
        Ok(())
    }
    fn propagate(&mut self) -> Result<(), BindingError> {
        self.advance()?;
        self.evidence.borrow_mut().record_action("Propagate");
        Ok(())
    }
    fn finish_stateflow(&mut self) -> Result<(), BindingError> {
        self.advance()?;
        self.evidence.borrow_mut().record_action("FinishStateflow");
        Ok(())
    }
    fn observe(&mut self) -> Result<mb::MachineStateReplayObservation, BindingError> {
        let analyzer = self.analyzer.as_ref().ok_or_else(unavailable)?;
        let state = analyzer.state();
        let views = analyzer.observations();
        let result = mb::MachineStateReplayObservation {
            case_id: self.case_id.clone(),
            phase: match state.phase {
                ms::Phase::Stateflow => "stateflow",
                ms::Phase::Done => "done",
            }
            .into(),
            snapshot_id: analyzer.request().snapshot_id.clone(),
            states_at: mb::MirrorSet(
                state
                    .states_at
                    .iter()
                    .map(|(&va, states)| mb::MiTypeO7Item {
                        field_0: mb::MirrorSet(states.iter().map(|id| id.0.clone()).collect()),
                        field_1: va.into(),
                    })
                    .collect(),
            ),
            structural_edges: edges!(analyzer.request().structural_edges, MiTypeO8Item),
            feasible_edges: edges!(views.feasible_edges, MiTypeO1Item),
            infeasible_edges: edges!(views.provably_infeasible_edges, MiTypeO2Item),
            unknown_edges: edges!(views.unknown_feasibility_edges, MiTypeO10Item),
            not_reached: mb::MirrorSet(
                views
                    .not_reached_nodes
                    .iter()
                    .map(|&va| va.into())
                    .collect(),
            ),
            terminals: mb::MirrorSet(
                views
                    .reached_terminal_transitions
                    .iter()
                    .map(|row| mb::MiTypeO9Item {
                        field_0: row.after.0.clone(),
                        field_1: row.before.0.clone(),
                        field_2: match row.outcome {
                            ms::TerminalOutcome::Faulted => "faulted",
                            ms::TerminalOutcome::Returned => "returned",
                            ms::TerminalOutcome::Stopped => "stopped",
                        }
                        .into(),
                        field_3: row.site.into(),
                    })
                    .collect(),
            ),
            obligations: mb::MirrorSet(
                views
                    .obligations
                    .iter()
                    .map(|row| mb::MiTypeO4Item {
                        field_0: match row.reason {
                            ms::ObligationReason::IncompleteSemantics => "incomplete-semantics",
                            ms::ObligationReason::Adapter(reason) => match reason {
                                ms::AdapterObligationReason::UnknownMemory => "unknown-memory",
                                ms::AdapterObligationReason::UnmodeledException => {
                                    "unmodeled-exception"
                                }
                                ms::AdapterObligationReason::UnmodeledSystemCall => {
                                    "unmodeled-system-call"
                                }
                                ms::AdapterObligationReason::UnmodeledConcurrency => {
                                    "unmodeled-concurrency"
                                }
                            },
                        }
                        .into(),
                        field_1: row.site.into(),
                    })
                    .collect(),
            ),
        };
        let mut evidence = self.evidence.borrow_mut();
        evidence.observations += 1;
        if state.phase == ms::Phase::Done {
            evidence.completed += 1;
        }
        Ok(result)
    }
}
impl Drop for MachineStatePort {
    fn drop(&mut self) {
        self.analyzer.take();
        self.evidence.borrow_mut().port_drops += 1;
    }
}

pub struct LLVMIRPort {
    requests: BTreeMap<String, ir::Request>,
    case_id: String,
    analyzer: Option<ir::Analyzer>,
    evidence: SharedEvidence,
}
impl LLVMIRPort {
    pub fn new(request: ir::Request, evidence: SharedEvidence) -> Self {
        Self::with_cases([("LLVMIRReplay".into(), request)].into(), evidence)
    }
    pub fn with_cases(requests: BTreeMap<String, ir::Request>, evidence: SharedEvidence) -> Self {
        Self {
            requests,
            case_id: String::new(),
            analyzer: None,
            evidence,
        }
    }
    fn advance(&mut self) -> Result<(), BindingError> {
        if self.analyzer.as_mut().ok_or_else(unavailable)?.step() {
            Ok(())
        } else {
            Err(finished())
        }
    }
}
fn ir_edge_kind(kind: ir::ControlEdgeKind) -> &'static str {
    match kind {
        ir::ControlEdgeKind::Next => "next",
        ir::ControlEdgeKind::True => "true",
        ir::ControlEdgeKind::False => "false",
        ir::ControlEdgeKind::Case => "case",
        ir::ControlEdgeKind::Default => "default",
        ir::ControlEdgeKind::Indirect => "indirect",
        ir::ControlEdgeKind::Normal => "normal",
        ir::ControlEdgeKind::Unwind => "unwind",
        ir::ControlEdgeKind::Fallthrough => "fallthrough",
        ir::ControlEdgeKind::Catch => "catch",
        ir::ControlEdgeKind::Cleanup => "cleanup",
    }
}
impl ib::LLVMIRReplayPort for LLVMIRPort {
    fn initialize(&mut self, input: ib::InitializeInput) -> Result<(), BindingError> {
        let request = self
            .requests
            .get(&input.case_id)
            .ok_or_else(|| BindingError::new("unknown_case", "unknown IR case"))?;
        self.case_id = input.case_id;
        self.evidence.borrow_mut().cases.push(self.case_id.clone());
        self.analyzer = Some(
            ir::Analyzer::new(request.clone())
                .map_err(|error| BindingError::new("invalid_request", error.to_string()))?,
        );
        self.evidence.borrow_mut().initializations += 1;
        self.evidence.borrow_mut().previous_action = None;
        self.evidence.borrow_mut().record_action("Initialize");
        Ok(())
    }
    fn expand_slice(&mut self) -> Result<(), BindingError> {
        self.advance()?;
        self.evidence.borrow_mut().record_action("ExpandSlice");
        Ok(())
    }
    fn finish_slice(&mut self) -> Result<(), BindingError> {
        self.advance()?;
        self.evidence.borrow_mut().record_action("FinishSlice");
        Ok(())
    }
    fn observe(&mut self) -> Result<ib::LLVMIRReplayObservation, BindingError> {
        let analyzer = self.analyzer.as_ref().ok_or_else(unavailable)?;
        let request = analyzer.request();
        let state = analyzer.state();
        let result = ib::LLVMIRReplayObservation {
            case_id: self.case_id.clone(),
            artifact_id: request.artifact_id.clone(),
            module_id: request.module_id.clone(),
            function_id: request.function_id.clone(),
            phase: match state.phase {
                ir::Phase::Slice => "slice",
                ir::Phase::Done => "done",
            }
            .into(),
            slice: ib::MirrorSet(state.slice.iter().map(|id| id.0.clone()).collect()),
            control_graph: ib::MirrorSet(
                request
                    .control_graph()
                    .iter()
                    .map(|edge| ib::MiTypeO3Item {
                        field_0: edge.dst.0.clone(),
                        field_1: ir_edge_kind(edge.kind).into(),
                        field_2: edge.src.0.clone(),
                    })
                    .collect(),
            ),
            call_graph: ib::MirrorSet(
                request
                    .call_graph()
                    .iter()
                    .map(|edge| ib::MiTypeO1Item {
                        field_0: edge.callee.0.clone(),
                        field_1: "call".into(),
                        field_2: edge.site.0.clone(),
                    })
                    .collect(),
            ),
            dependency_preds: ib::MirrorMap(
                request
                    .instructions
                    .keys()
                    .map(|id| {
                        (
                            id.0.clone(),
                            ib::MirrorSet(
                                request
                                    .dependency_preds(id)
                                    .iter()
                                    .map(|pred| pred.0.clone())
                                    .collect(),
                            ),
                        )
                    })
                    .collect(),
            ),
            obligations: ib::MirrorSet(
                request
                    .obligations()
                    .iter()
                    .map(|row| ib::MiTypeO7Item {
                        field_0: match row.reason {
                            ir::ObligationReason::CallTargets => "call-targets",
                            ir::ObligationReason::Adapter(reason) => match reason {
                                ir::AdapterObligationReason::UnsupportedInstruction => {
                                    "unsupported-instruction"
                                }
                                ir::AdapterObligationReason::IncompleteSemantics => {
                                    "incomplete-semantics"
                                }
                                ir::AdapterObligationReason::UnknownMemoryAlias => {
                                    "unknown-memory-alias"
                                }
                                ir::AdapterObligationReason::UnmodeledException => {
                                    "unmodeled-exception"
                                }
                                ir::AdapterObligationReason::UnmodeledSystemCall => {
                                    "unmodeled-system-call"
                                }
                                ir::AdapterObligationReason::UnmodeledConcurrency => {
                                    "unmodeled-concurrency"
                                }
                            },
                        }
                        .into(),
                        field_1: row.site.0.clone(),
                    })
                    .collect(),
            ),
        };
        let mut evidence = self.evidence.borrow_mut();
        evidence.observations += 1;
        if state.phase == ir::Phase::Done {
            evidence.completed += 1;
        }
        Ok(result)
    }
}
impl Drop for LLVMIRPort {
    fn drop(&mut self) {
        self.analyzer.take();
        self.evidence.borrow_mut().port_drops += 1;
    }
}
