//! Finite post-recovery abstract stateflow for `Specs/AriadneMachineState.tla`.
//! A trusted adapter supplies state transitions; this engine only propagates
//! them and classifies the frozen structural graph relative to that relation.
use crate::{
    Address, AddressSet, Analyzer as RecoveryAnalyzer, ByteSource, Edge, EdgeSet, Location,
    LocationSet, Obligation as RecoveryObligation, Phase as RecoveryPhase,
};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct StateId(pub String);
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct AbstractValue(pub String);
pub type StateSet = BTreeSet<StateId>;
pub type ValueSet = BTreeSet<AbstractValue>;
pub type Valuation = BTreeMap<Location, ValueSet>;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Running,
    Faulted,
    Returned,
    Stopped,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum TerminalOutcome {
    Faulted,
    Returned,
    Stopped,
}
impl From<TerminalOutcome> for Status {
    fn from(value: TerminalOutcome) -> Self {
        match value {
            TerminalOutcome::Faulted => Self::Faulted,
            TerminalOutcome::Returned => Self::Returned,
            TerminalOutcome::Stopped => Self::Stopped,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AbstractState {
    pub status: Status,
    pub valuation: Valuation,
}
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Effects {
    pub uses: LocationSet,
    pub must_defs: LocationSet,
    pub may_defs: LocationSet,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct StateStep {
    pub edge: Edge,
    pub before: StateId,
    pub after: StateId,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct TerminalTransition {
    pub site: Address,
    pub before: StateId,
    pub after: StateId,
    pub outcome: TerminalOutcome,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum AdapterObligationReason {
    UnknownMemory,
    UnmodeledException,
    UnmodeledSystemCall,
    UnmodeledConcurrency,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ObligationReason {
    IncompleteSemantics,
    Adapter(AdapterObligationReason),
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct AdapterObligation {
    pub site: Address,
    pub reason: AdapterObligationReason,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Obligation {
    pub site: Address,
    pub reason: ObligationReason,
}

#[derive(Clone, Debug)]
pub struct Request {
    pub snapshot_id: String,
    pub nodes: AddressSet,
    pub structural_edges: EdgeSet,
    pub value_domain: BTreeMap<Location, ValueSet>,
    pub catalogue: BTreeMap<StateId, AbstractState>,
    pub entry_states: BTreeMap<Address, StateSet>,
    pub effects: BTreeMap<Address, Effects>,
    pub steps: BTreeSet<StateStep>,
    pub terminal_transitions: BTreeSet<TerminalTransition>,
    pub complete_sites: AddressSet,
    pub adapter_obligations: BTreeSet<AdapterObligation>,
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
        if self.snapshot_id.is_empty() {
            return Err(bad("snapshot_id", "must be nonempty"));
        }
        if self.nodes.is_empty() {
            return Err(bad("nodes", "must be nonempty"));
        }
        if self.value_domain.is_empty() || self.value_domain.values().any(BTreeSet::is_empty) {
            return Err(bad(
                "value_domain",
                "locations and domains must be nonempty",
            ));
        }
        let locations: LocationSet = self.value_domain.keys().cloned().collect();
        if self.catalogue.is_empty() {
            return Err(bad("catalogue", "must be nonempty"));
        }
        for (id, state) in &self.catalogue {
            if state.valuation.keys().cloned().collect::<LocationSet>() != locations {
                return Err(bad("catalogue", format!("valuation domain of {:?}", id)));
            }
            for (location, values) in &state.valuation {
                if values.is_empty() || !values.is_subset(&self.value_domain[location]) {
                    return Err(bad(
                        "catalogue",
                        format!("invalid values for {:?} at {location}", id),
                    ));
                }
            }
        }
        for edge in &self.structural_edges {
            if !self.nodes.contains(&edge.src)
                || !self.nodes.contains(&edge.dst)
                || !edge.kind.is_local()
            {
                return Err(bad("structural_edges", format!("invalid edge {edge:?}")));
            }
        }
        for (&site, states) in &self.entry_states {
            if !self.nodes.contains(&site) || states.is_empty() {
                return Err(bad("entry_states", format!("invalid entry at {site}")));
            }
            for id in states {
                if self.catalogue.get(id).map(|state| state.status) != Some(Status::Running) {
                    return Err(bad(
                        "entry_states",
                        format!("non-running or unknown {id:?}"),
                    ));
                }
            }
        }
        if self.effects.keys().copied().collect::<AddressSet>() != self.nodes {
            return Err(bad("effects", "must be total over nodes"));
        }
        for (&site, effects) in &self.effects {
            if !effects.uses.is_subset(&locations)
                || !effects.may_defs.is_subset(&locations)
                || !effects.must_defs.is_subset(&effects.may_defs)
            {
                return Err(bad("effects", format!("invalid effects at {site}")));
            }
        }
        for step in &self.steps {
            if !self.structural_edges.contains(&step.edge) {
                return Err(bad("steps", format!("edge absent: {:?}", step.edge)));
            }
            if self.catalogue.get(&step.before).map(|s| s.status) != Some(Status::Running)
                || self.catalogue.get(&step.after).map(|s| s.status) != Some(Status::Running)
            {
                return Err(bad("steps", format!("non-running state: {step:?}")));
            }
            self.check_frame(step.edge.src, &step.before, &step.after, "steps")?;
        }
        for transition in &self.terminal_transitions {
            if !self.nodes.contains(&transition.site)
                || self.catalogue.get(&transition.before).map(|s| s.status) != Some(Status::Running)
                || self.catalogue.get(&transition.after).map(|s| s.status)
                    != Some(transition.outcome.into())
            {
                return Err(bad(
                    "terminal_transitions",
                    format!("invalid transition: {transition:?}"),
                ));
            }
            self.check_frame(
                transition.site,
                &transition.before,
                &transition.after,
                "terminal_transitions",
            )?;
        }
        if !self.complete_sites.is_subset(&self.nodes) {
            return Err(bad("complete_sites", "must be within nodes"));
        }
        if self
            .adapter_obligations
            .iter()
            .any(|obligation| !self.nodes.contains(&obligation.site))
        {
            return Err(bad("adapter_obligations", "site outside nodes"));
        }
        Ok(())
    }

    fn check_frame(
        &self,
        site: Address,
        before: &StateId,
        after: &StateId,
        field: &'static str,
    ) -> Result<(), InvalidRequest> {
        let may_defs = &self.effects[&site].may_defs;
        let source = &self.catalogue[before].valuation;
        let destination = &self.catalogue[after].valuation;
        for location in self.value_domain.keys() {
            if !may_defs.contains(location) && source[location] != destination[location] {
                return Err(bad(
                    field,
                    format!("frame changed {location} at {site}: {before:?} -> {after:?}"),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Phase {
    Stateflow,
    Done,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnalysisState {
    pub phase: Phase,
    pub states_at: BTreeMap<Address, StateSet>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Observations {
    pub feasible_edges: EdgeSet,
    pub provably_infeasible_edges: EdgeSet,
    pub unknown_feasibility_edges: EdgeSet,
    pub reached_terminal_transitions: BTreeSet<TerminalTransition>,
    pub not_reached_nodes: AddressSet,
    pub obligations: BTreeSet<Obligation>,
}
#[derive(Debug)]
pub struct Analyzer {
    request: Request,
    state: AnalysisState,
}
impl Analyzer {
    pub fn new(request: Request) -> Result<Self, InvalidRequest> {
        request.validate()?;
        let states_at = request
            .nodes
            .iter()
            .map(|&site| {
                (
                    site,
                    request.entry_states.get(&site).cloned().unwrap_or_default(),
                )
            })
            .collect();
        Ok(Self {
            request,
            state: AnalysisState {
                phase: Phase::Stateflow,
                states_at,
            },
        })
    }
    pub fn request(&self) -> &Request {
        &self.request
    }
    pub fn state(&self) -> &AnalysisState {
        &self.state
    }
    fn incoming(&self, site: Address) -> StateSet {
        let mut incoming = self
            .request
            .entry_states
            .get(&site)
            .cloned()
            .unwrap_or_default();
        for step in &self.request.steps {
            if step.edge.dst == site && self.state.states_at[&step.edge.src].contains(&step.before)
            {
                incoming.insert(step.after.clone());
            }
        }
        incoming
    }
    /// One `Propagate(a)` at the lowest enabled VA, or one `FinishStateflow`.
    pub fn step(&mut self) -> bool {
        if self.state.phase == Phase::Done {
            return false;
        }
        for &site in &self.request.nodes {
            let incoming = self.incoming(site);
            if !incoming.is_subset(&self.state.states_at[&site]) {
                self.state
                    .states_at
                    .get_mut(&site)
                    .unwrap()
                    .extend(incoming);
                return true;
            }
        }
        self.state.phase = Phase::Done;
        true
    }
    pub fn observations(&self) -> Observations {
        let feasible_edges: EdgeSet = self
            .request
            .steps
            .iter()
            .filter(|step| self.state.states_at[&step.edge.src].contains(&step.before))
            .map(|step| step.edge)
            .collect();
        let reached_terminal_transitions = self
            .request
            .terminal_transitions
            .iter()
            .filter(|transition| {
                self.state.states_at[&transition.site].contains(&transition.before)
            })
            .cloned()
            .collect();
        let reached_sources: AddressSet = self
            .state
            .states_at
            .iter()
            .filter_map(|(&site, states)| (!states.is_empty()).then_some(site))
            .collect();
        let provably_infeasible_edges = if self.state.phase == Phase::Done {
            self.request
                .structural_edges
                .iter()
                .filter(|edge| {
                    self.request.complete_sites.contains(&edge.src)
                        && reached_sources.contains(&edge.src)
                        && !feasible_edges.contains(edge)
                })
                .copied()
                .collect()
        } else {
            EdgeSet::new()
        };
        let unknown_feasibility_edges = self
            .request
            .structural_edges
            .difference(&feasible_edges)
            .copied()
            .collect::<EdgeSet>()
            .difference(&provably_infeasible_edges)
            .copied()
            .collect();
        let not_reached_nodes = if self.state.phase == Phase::Done {
            self.request
                .nodes
                .difference(&reached_sources)
                .copied()
                .collect()
        } else {
            AddressSet::new()
        };
        let mut obligations: BTreeSet<_> = self
            .request
            .adapter_obligations
            .iter()
            .map(|obligation| Obligation {
                site: obligation.site,
                reason: ObligationReason::Adapter(obligation.reason),
            })
            .collect();
        obligations.extend(
            self.request
                .nodes
                .difference(&self.request.complete_sites)
                .map(|&site| Obligation {
                    site,
                    reason: ObligationReason::IncompleteSemantics,
                }),
        );
        Observations {
            feasible_edges,
            provably_infeasible_edges,
            unknown_feasibility_edges,
            reached_terminal_transitions,
            not_reached_nodes,
            obligations,
        }
    }
    pub fn finish(mut self) -> AnalysisResult {
        while self.step() {}
        let observations = self.observations();
        AnalysisResult {
            request: self.request,
            state: self.state,
            observations,
        }
    }
}
#[derive(Debug)]
pub struct AnalysisResult {
    request: Request,
    state: AnalysisState,
    observations: Observations,
}
impl AnalysisResult {
    pub fn request(&self) -> &Request {
        &self.request
    }
    pub fn state(&self) -> &AnalysisState {
        &self.state
    }
    pub fn observations(&self) -> &Observations {
        &self.observations
    }
}
pub fn analyze(request: Request) -> Result<AnalysisResult, InvalidRequest> {
    Ok(Analyzer::new(request)?.finish())
}

/// Trusted semantic facts supplied separately from a frozen recovery graph.
pub struct SemanticInputs {
    pub snapshot_id: String,
    pub value_domain: BTreeMap<Location, ValueSet>,
    pub catalogue: BTreeMap<StateId, AbstractState>,
    pub entry_states: BTreeMap<Address, StateSet>,
    pub steps: BTreeSet<StateStep>,
    pub terminal_transitions: BTreeSet<TerminalTransition>,
    pub complete_sites: AddressSet,
    pub adapter_obligations: BTreeSet<AdapterObligation>,
}
pub struct RecoveryContext {
    pub snapshot_id: String,
    pub full_edges: EdgeSet,
    pub byte_provenance: BTreeMap<Address, ByteSource>,
    pub recovery_obligations: BTreeSet<RecoveryObligation>,
    pub missing_slice_seeds: AddressSet,
}
pub struct RecoveryHandoff {
    pub request: Request,
    pub context: RecoveryContext,
}
#[derive(Debug)]
pub enum HandoffError {
    RecoveryNotFrozen,
    SnapshotMismatch,
    EmptyDecodedGraph,
    OpenLocalEdge(Edge),
    LocationMismatch,
    InvalidRequest(InvalidRequest),
}
impl fmt::Display for HandoffError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "invalid recovery handoff: {self:?}")
    }
}
impl Error for HandoffError {}

/// Copy the decoded, endpoint-closed local graph and effects without changing
/// the original recovery analyzer or converting its obligations into stateflow.
pub fn prepare_from_recovery(
    recovery: &RecoveryAnalyzer,
    semantics: SemanticInputs,
) -> Result<RecoveryHandoff, HandoffError> {
    if recovery.state().phase == RecoveryPhase::Recover {
        return Err(HandoffError::RecoveryNotFrozen);
    }
    if recovery.request().snapshot_id != semantics.snapshot_id {
        return Err(HandoffError::SnapshotMismatch);
    }
    let nodes = recovery.state().decoded.clone();
    if nodes.is_empty() {
        return Err(HandoffError::EmptyDecodedGraph);
    }
    let structural_edges: EdgeSet = recovery
        .state()
        .edges
        .iter()
        .filter(|edge| edge.kind.is_local())
        .copied()
        .collect();
    if let Some(edge) = structural_edges
        .iter()
        .find(|edge| !nodes.contains(&edge.src) || !nodes.contains(&edge.dst))
    {
        return Err(HandoffError::OpenLocalEdge(*edge));
    }
    if semantics
        .value_domain
        .keys()
        .cloned()
        .collect::<LocationSet>()
        != recovery.request().locations
    {
        return Err(HandoffError::LocationMismatch);
    }
    let effects = nodes
        .iter()
        .map(|&site| {
            let instruction = &recovery.request().instructions[&site];
            (
                site,
                Effects {
                    uses: instruction.uses.clone(),
                    must_defs: instruction.must_defs.clone(),
                    may_defs: instruction.may_defs.clone(),
                },
            )
        })
        .collect();
    let request = Request {
        snapshot_id: semantics.snapshot_id.clone(),
        nodes,
        structural_edges,
        value_domain: semantics.value_domain,
        catalogue: semantics.catalogue,
        entry_states: semantics.entry_states,
        effects,
        steps: semantics.steps,
        terminal_transitions: semantics.terminal_transitions,
        complete_sites: semantics.complete_sites,
        adapter_obligations: semantics.adapter_obligations,
    };
    request.validate().map_err(HandoffError::InvalidRequest)?;
    let context = RecoveryContext {
        snapshot_id: recovery.request().snapshot_id.clone(),
        full_edges: recovery.state().edges.clone(),
        byte_provenance: recovery.state().provenance.clone(),
        recovery_obligations: recovery.state().obligations.clone(),
        missing_slice_seeds: recovery
            .request()
            .slice_seeds
            .difference(&recovery.state().decoded)
            .copied()
            .collect(),
    };
    Ok(RecoveryHandoff { request, context })
}
