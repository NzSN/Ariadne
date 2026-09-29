//! Dependency slicing over already verified, directly supplied native LLVM IR.
//! Implements the finite normalized machine of `Specs/AriadneLLVMIR.tla`;
//! constructing and verifying `.ll`/`.bc` inputs is a separate adapter task.
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct BlockId(pub String);
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct InstructionId(pub String);
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct ValueId(pub String);
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct CalleeId(pub String);

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum TerminatorKind {
    Br,
    Switch,
    IndirectBr,
    Invoke,
    CallBr,
    Ret,
    Resume,
    Unreachable,
    CatchSwitch,
    CatchRet,
    CleanupRet,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ControlEdgeKind {
    Next,
    True,
    False,
    Case,
    Default,
    Indirect,
    Normal,
    Unwind,
    Fallthrough,
    Catch,
    Cleanup,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Successor {
    pub dst: BlockId,
    pub kind: ControlEdgeKind,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct ControlEdge {
    pub src: BlockId,
    pub dst: BlockId,
    pub kind: ControlEdgeKind,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BlockInfo {
    pub terminator: InstructionId,
    pub kind: TerminatorKind,
    pub successors: BTreeSet<Successor>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ValueKind {
    Instruction,
    Argument,
    Constant,
    Global,
    External,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ValueInfo {
    pub kind: ValueKind,
    /// Total normalized table; ignored for values not defined by instructions.
    pub def_site: InstructionId,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct PhiIncoming {
    pub pred: BlockId,
    pub value: ValueId,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InstructionInfo {
    pub block: BlockId,
    pub index: u32,
    pub uses: BTreeSet<ValueId>,
    pub phi_incoming: BTreeSet<PhiIncoming>,
    pub memory_preds: BTreeSet<InstructionId>,
    pub call_targets: BTreeSet<CalleeId>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum AdapterObligationReason {
    UnsupportedInstruction,
    IncompleteSemantics,
    UnknownMemoryAlias,
    UnmodeledException,
    UnmodeledSystemCall,
    UnmodeledConcurrency,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ObligationReason {
    Adapter(AdapterObligationReason),
    CallTargets,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct AdapterObligation {
    pub site: InstructionId,
    pub reason: AdapterObligationReason,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Obligation {
    pub site: InstructionId,
    pub reason: ObligationReason,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct CallEdge {
    pub site: InstructionId,
    pub callee: CalleeId,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub artifact_id: String,
    pub module_id: String,
    pub function_id: String,
    pub verified_ir: bool,
    pub blocks: BTreeMap<BlockId, BlockInfo>,
    pub entry_block: BlockId,
    pub instructions: BTreeMap<InstructionId, InstructionInfo>,
    pub values: BTreeMap<ValueId, ValueInfo>,
    pub phi_nodes: BTreeSet<InstructionId>,
    pub call_sites: BTreeSet<InstructionId>,
    pub callees: BTreeSet<CalleeId>,
    pub complete_calls: BTreeSet<InstructionId>,
    pub adapter_obligations: BTreeSet<AdapterObligation>,
    pub slice_seeds: BTreeSet<InstructionId>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidRequest {
    pub field: &'static str,
    pub reason: String,
}
impl fmt::Display for InvalidRequest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.field, self.reason)
    }
}
impl Error for InvalidRequest {}
fn bad(field: &'static str, reason: impl Into<String>) -> InvalidRequest {
    InvalidRequest {
        field,
        reason: reason.into(),
    }
}

impl Request {
    pub fn validate(&self) -> Result<(), InvalidRequest> {
        if self.artifact_id.is_empty() || self.module_id.is_empty() || self.function_id.is_empty() {
            return Err(bad(
                "identity",
                "artifact, module and function IDs must be nonempty",
            ));
        }
        if !self.verified_ir {
            return Err(bad("verified_ir", "LLVM verification is required"));
        }
        if self.blocks.is_empty() || !self.blocks.contains_key(&self.entry_block) {
            return Err(bad(
                "blocks",
                "nonempty blocks and a selected entry required",
            ));
        }
        if self.instructions.is_empty() {
            return Err(bad("instructions", "must be nonempty"));
        }
        let mut indices = BTreeSet::new();
        for (id, info) in &self.instructions {
            if !self.blocks.contains_key(&info.block)
                || !indices.insert((info.block.clone(), info.index))
            {
                return Err(bad(
                    "instructions",
                    format!("invalid block or duplicate index: {id:?}"),
                ));
            }
            if !info.uses.is_subset(&self.values.keys().cloned().collect()) {
                return Err(bad("uses", format!("unknown operand at {id:?}")));
            }
            if !info
                .memory_preds
                .is_subset(&self.instructions.keys().cloned().collect())
            {
                return Err(bad("memory_preds", format!("unknown producer at {id:?}")));
            }
            if !info.call_targets.is_subset(&self.callees) {
                return Err(bad("call_targets", format!("unknown callee at {id:?}")));
            }
            if !self.call_sites.contains(id) && !info.call_targets.is_empty() {
                return Err(bad("call_targets", format!("non-call has targets: {id:?}")));
            }
            if !self.phi_nodes.contains(id) && !info.phi_incoming.is_empty() {
                return Err(bad(
                    "phi_incoming",
                    format!("non-phi has incoming rows: {id:?}"),
                ));
            }
        }
        let mut control_graph = BTreeSet::new();
        for (block, info) in &self.blocks {
            let Some(terminator) = self.instructions.get(&info.terminator) else {
                return Err(bad(
                    "terminator",
                    format!("missing terminator in {block:?}"),
                ));
            };
            if terminator.block != *block {
                return Err(bad(
                    "terminator",
                    format!("terminator belongs to another block: {block:?}"),
                ));
            }
            if self
                .instructions
                .values()
                .any(|i| i.block == *block && i.index > terminator.index)
            {
                return Err(bad(
                    "terminator",
                    format!("instruction after terminator: {block:?}"),
                ));
            }
            if matches!(
                info.kind,
                TerminatorKind::Ret | TerminatorKind::Resume | TerminatorKind::Unreachable
            ) && !info.successors.is_empty()
            {
                return Err(bad("terminator", format!("exit has successors: {block:?}")));
            }
            if info.kind == TerminatorKind::Invoke
                && (info
                    .successors
                    .iter()
                    .filter(|s| s.kind == ControlEdgeKind::Normal)
                    .count()
                    != 1
                    || info
                        .successors
                        .iter()
                        .filter(|s| s.kind == ControlEdgeKind::Unwind)
                        .count()
                        != 1)
            {
                return Err(bad(
                    "terminator",
                    format!("invoke needs normal/unwind: {block:?}"),
                ));
            }
            for successor in &info.successors {
                if !self.blocks.contains_key(&successor.dst) {
                    return Err(bad("successors", format!("unknown block from {block:?}")));
                }
                control_graph.insert(ControlEdge {
                    src: block.clone(),
                    dst: successor.dst.clone(),
                    kind: successor.kind,
                });
            }
        }
        let mut definition_sites = BTreeSet::new();
        for (id, info) in &self.values {
            if info.kind == ValueKind::Instruction
                && (!self.instructions.contains_key(&info.def_site)
                    || !definition_sites.insert(info.def_site.clone()))
            {
                return Err(bad(
                    "values",
                    format!("invalid or duplicate definition: {id:?}"),
                ));
            }
        }
        let instruction_ids: BTreeSet<_> = self.instructions.keys().cloned().collect();
        if !self.phi_nodes.is_subset(&instruction_ids)
            || !self.call_sites.is_subset(&instruction_ids)
            || !self.complete_calls.is_subset(&self.call_sites)
            || !self.slice_seeds.is_subset(&instruction_ids)
        {
            return Err(bad(
                "sets",
                "phi, call, completeness and seed sets must be in-domain",
            ));
        }
        for phi in &self.phi_nodes {
            let info = &self.instructions[phi];
            let predecessor_blocks: BTreeSet<_> = control_graph
                .iter()
                .filter(|edge| edge.dst == info.block)
                .map(|edge| edge.src.clone())
                .collect();
            let incoming_blocks: BTreeSet<_> = info
                .phi_incoming
                .iter()
                .map(|row| row.pred.clone())
                .collect();
            let incoming_values: BTreeSet<_> = info
                .phi_incoming
                .iter()
                .map(|row| row.value.clone())
                .collect();
            if incoming_blocks != predecessor_blocks
                || incoming_blocks.len() != info.phi_incoming.len()
                || incoming_values != info.uses
                || self.instructions.iter().any(|(other_id, other)| {
                    !self.phi_nodes.contains(other_id)
                        && other.block == info.block
                        && other.index <= info.index
                })
            {
                return Err(bad(
                    "phi_incoming",
                    format!("incomplete or unordered phi: {phi:?}"),
                ));
            }
        }
        if self
            .adapter_obligations
            .iter()
            .any(|row| !instruction_ids.contains(&row.site))
        {
            return Err(bad(
                "adapter_obligations",
                "site outside instruction domain",
            ));
        }
        Ok(())
    }
    pub fn control_graph(&self) -> BTreeSet<ControlEdge> {
        self.blocks
            .iter()
            .flat_map(|(block, info)| {
                info.successors.iter().map(move |next| ControlEdge {
                    src: block.clone(),
                    dst: next.dst.clone(),
                    kind: next.kind,
                })
            })
            .collect()
    }
    pub fn call_graph(&self) -> BTreeSet<CallEdge> {
        self.call_sites
            .iter()
            .flat_map(|site| {
                self.instructions[site]
                    .call_targets
                    .iter()
                    .map(move |callee| CallEdge {
                        site: site.clone(),
                        callee: callee.clone(),
                    })
            })
            .collect()
    }
    pub fn obligations(&self) -> BTreeSet<Obligation> {
        let mut result: BTreeSet<_> = self
            .adapter_obligations
            .iter()
            .map(|row| Obligation {
                site: row.site.clone(),
                reason: ObligationReason::Adapter(row.reason),
            })
            .collect();
        result.extend(
            self.call_sites
                .difference(&self.complete_calls)
                .map(|site| Obligation {
                    site: site.clone(),
                    reason: ObligationReason::CallTargets,
                }),
        );
        result
    }
    pub fn dependency_preds(&self, id: &InstructionId) -> BTreeSet<InstructionId> {
        let info = &self.instructions[id];
        let mut result = info.memory_preds.clone();
        for value in &info.uses {
            let source = &self.values[value];
            if source.kind == ValueKind::Instruction {
                result.insert(source.def_site.clone());
            }
        }
        result
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Slice,
    Done,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnalysisState {
    pub phase: Phase,
    pub slice: BTreeSet<InstructionId>,
}
#[derive(Debug)]
pub struct Analyzer {
    request: Request,
    state: AnalysisState,
}
impl Analyzer {
    pub fn new(request: Request) -> Result<Self, InvalidRequest> {
        request.validate()?;
        let state = AnalysisState {
            phase: Phase::Slice,
            slice: request.slice_seeds.clone(),
        };
        Ok(Self { request, state })
    }
    pub fn request(&self) -> &Request {
        &self.request
    }
    pub fn state(&self) -> &AnalysisState {
        &self.state
    }
    pub fn step(&mut self) -> bool {
        if self.state.phase == Phase::Done {
            return false;
        }
        let predecessors: BTreeSet<_> = self
            .state
            .slice
            .iter()
            .flat_map(|id| self.request.dependency_preds(id))
            .collect();
        if predecessors.is_subset(&self.state.slice) {
            self.state.phase = Phase::Done;
        } else {
            self.state.slice.extend(predecessors);
        }
        true
    }
    pub fn finish(mut self) -> AnalysisResult {
        while self.step() {}
        AnalysisResult {
            request: self.request,
            state: self.state,
        }
    }
}
#[derive(Debug)]
pub struct AnalysisResult {
    request: Request,
    state: AnalysisState,
}
impl AnalysisResult {
    pub fn request(&self) -> &Request {
        &self.request
    }
    pub fn state(&self) -> &AnalysisState {
        &self.state
    }
}
pub fn analyze(request: Request) -> Result<AnalysisResult, InvalidRequest> {
    Ok(Analyzer::new(request)?.finish())
}
