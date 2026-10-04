//! Typed stateflow wire projection. Propagation and feasibility classification
//! are computed only by the native helper.
use super::core_adapter::{address, hex};
use super::core_protocol::{Edge as EdgeRow, StateflowObservation};
use super::core_session::{CoreConfig, StateflowSession};
use super::{Error, invalid};
use crate::machine_state as ms;
use crate::{AddressSet, Edge, EdgeKind, EdgeSet};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

fn kind(k: EdgeKind) -> &'static str {
    match k {
        EdgeKind::Next => "next",
        EdgeKind::Taken => "taken",
        EdgeKind::Fallthrough => "fallthrough",
        EdgeKind::Jump => "jump",
        EdgeKind::Indirect => "indirect",
        EdgeKind::Summary => "summary",
        EdgeKind::Call => "call",
    }
}
fn status(s: ms::Status) -> &'static str {
    match s {
        ms::Status::Running => "running",
        ms::Status::Faulted => "faulted",
        ms::Status::Returned => "returned",
        ms::Status::Stopped => "stopped",
    }
}
fn outcome(o: ms::TerminalOutcome) -> &'static str {
    status(o.into())
}
fn adapter_reason(r: ms::AdapterObligationReason) -> &'static str {
    match r {
        ms::AdapterObligationReason::UnknownMemory => "unknown-memory",
        ms::AdapterObligationReason::UnmodeledException => "unmodeled-exception",
        ms::AdapterObligationReason::UnmodeledSystemCall => "unmodeled-system-call",
        ms::AdapterObligationReason::UnmodeledConcurrency => "unmodeled-concurrency",
    }
}
fn values(s: &ms::ValueSet) -> Vec<&str> {
    s.iter().map(|v| v.0.as_str()).collect()
}
fn ids(s: &ms::StateSet) -> Vec<&str> {
    s.iter().map(|v| v.0.as_str()).collect()
}
pub fn encode_request(r: &ms::Request) -> Result<Value, Error> {
    r.validate()?;
    let effects = |which: u8| {
        r.effects
            .iter()
            .map(|(&a, e)| {
                json!({"address":hex(a),"locations":match which {
        0=>&e.uses,1=>&e.may_defs,_=>&e.must_defs}})
            })
            .collect::<Vec<_>>()
    };
    Ok(
        json!({"snapshot":r.snapshot_id,"nodes":r.nodes.iter().copied().map(hex).collect::<Vec<_>>(),
            "entry_points":r.entry_states.keys().copied().map(hex).collect::<Vec<_>>(),
            "locations":r.value_domain.keys().collect::<Vec<_>>(),
            "value_domain":r.value_domain.iter().map(|(l,s)|json!({"location":l,"values":values(s)})).collect::<Vec<_>>(),
            "state_ids":r.catalogue.keys().map(|s|&s.0).collect::<Vec<_>>(),
            "valuation":r.catalogue.iter().map(|(id,s)|json!({"state":id.0,"values":s.valuation.iter()
                .map(|(l,v)|json!({"location":l,"values":values(v)})).collect::<Vec<_>>()})).collect::<Vec<_>>(),
            "state_status":r.catalogue.iter().map(|(id,s)|json!({"state":id.0,"status":status(s.status)})).collect::<Vec<_>>(),
            "initial_states":r.nodes.iter().map(|a|json!({"address":hex(*a),"states":r.entry_states.get(a).map(ids).unwrap_or_default()})).collect::<Vec<_>>(),
            "structural_edges":r.structural_edges.iter().map(|e|json!({"src":hex(e.src),"dst":hex(e.dst),"kind":kind(e.kind)})).collect::<Vec<_>>(),
            "uses":effects(0),"may_defs":effects(1),"must_defs":effects(2),
            "state_steps":r.steps.iter().map(|s|json!({"src":hex(s.edge.src),"dst":hex(s.edge.dst),"kind":kind(s.edge.kind),
                "before":s.before.0,"after":s.after.0})).collect::<Vec<_>>(),
            "terminal_transitions":r.terminal_transitions.iter().map(|t|json!({"site":hex(t.site),"before":t.before.0,"after":t.after.0,
                "outcome":outcome(t.outcome)})).collect::<Vec<_>>(),
            "complete_sites":r.complete_sites.iter().copied().map(hex).collect::<Vec<_>>(),
            "adapter_obligations":r.adapter_obligations.iter().map(|o|json!({"site":hex(o.site),"reason":adapter_reason(o.reason)})).collect::<Vec<_>>()
        }),
    )
}
fn edges(rows: &[EdgeRow], domain: &EdgeSet) -> Result<EdgeSet, Error> {
    let mut result = EdgeSet::new();
    for row in rows {
        let kind = match row.kind.as_str() {
            "next" => EdgeKind::Next,
            "taken" => EdgeKind::Taken,
            "fallthrough" => EdgeKind::Fallthrough,
            "jump" => EdgeKind::Jump,
            "indirect" => EdgeKind::Indirect,
            "summary" => EdgeKind::Summary,
            _ => return Err(invalid("native stateflow nonlocal edge")),
        };
        let edge = Edge {
            src: address(&row.src)?,
            dst: address(&row.dst)?,
            kind,
        };
        if !domain.contains(&edge) || !result.insert(edge) {
            return Err(invalid("native stateflow edge domain/duplicate"));
        }
    }
    Ok(result)
}
pub fn decode(
    r: &ms::Request,
    o: &StateflowObservation,
) -> Result<(ms::AnalysisState, ms::Observations), Error> {
    let phase = match o.phase.as_str() {
        "stateflow" => ms::Phase::Stateflow,
        "done" => ms::Phase::Done,
        _ => return Err(invalid("native stateflow phase")),
    };
    let mut states_at = BTreeMap::new();
    for row in &o.states_at {
        let a = address(&row.address)?;
        let mut states = ms::StateSet::new();
        for name in &row.states {
            let id = ms::StateId(name.clone());
            if r.catalogue
                .get(&id)
                .is_none_or(|s| s.status != ms::Status::Running)
                || !states.insert(id)
            {
                return Err(invalid("native stateflow invalid/duplicate state ID"));
            }
        }
        if !r.nodes.contains(&a) || states_at.insert(a, states).is_some() {
            return Err(invalid("native states-at domain/duplicate"));
        }
    }
    if states_at.keys().copied().collect::<AddressSet>() != r.nodes {
        return Err(invalid("native states-at not total"));
    }
    let structural = edges(&o.structural_edges, &r.structural_edges)?;
    let feasible_edges = edges(&o.feasible_edges, &structural)?;
    let provably_infeasible_edges = edges(&o.provably_infeasible_edges, &structural)?;
    let unknown_feasibility_edges = edges(&o.unknown_feasibility_edges, &structural)?;
    if structural != r.structural_edges
        || !feasible_edges.is_disjoint(&provably_infeasible_edges)
        || structural
            .difference(&feasible_edges)
            .copied()
            .collect::<EdgeSet>()
            .difference(&provably_infeasible_edges)
            .copied()
            .collect::<EdgeSet>()
            != unknown_feasibility_edges
    {
        return Err(invalid("native structural graph/feasibility partition"));
    }
    for e in &provably_infeasible_edges {
        if phase != ms::Phase::Done
            || !r.complete_sites.contains(&e.src)
            || states_at[&e.src].is_empty()
        {
            return Err(invalid(
                "native infeasibility lacks reached complete source",
            ));
        }
    }
    let mut reached_terminal_transitions = BTreeSet::new();
    for row in &o.reached_terminal_transitions {
        let outcome = match row.outcome.as_str() {
            "faulted" => ms::TerminalOutcome::Faulted,
            "returned" => ms::TerminalOutcome::Returned,
            "stopped" => ms::TerminalOutcome::Stopped,
            _ => return Err(invalid("native terminal outcome")),
        };
        let t = ms::TerminalTransition {
            site: address(&row.site)?,
            before: ms::StateId(row.before.clone()),
            after: ms::StateId(row.after.clone()),
            outcome,
        };
        if !r.terminal_transitions.contains(&t)
            || !states_at[&t.site].contains(&t.before)
            || !reached_terminal_transitions.insert(t)
        {
            return Err(invalid("native terminal binding/duplicate"));
        }
    }
    let mut not_reached_nodes = AddressSet::new();
    for a in &o.not_reached_nodes {
        let a = address(a)?;
        if !r.nodes.contains(&a) || !states_at[&a].is_empty() || !not_reached_nodes.insert(a) {
            return Err(invalid("native not-reached node"));
        }
    }
    let mut obligations = BTreeSet::new();
    for row in &o.obligations {
        let site = address(&row.site)?;
        let reason = match row.reason.as_str() {
            "incomplete-semantics" => ms::ObligationReason::IncompleteSemantics,
            "unknown-memory" => {
                ms::ObligationReason::Adapter(ms::AdapterObligationReason::UnknownMemory)
            }
            "unmodeled-exception" => {
                ms::ObligationReason::Adapter(ms::AdapterObligationReason::UnmodeledException)
            }
            "unmodeled-system-call" => {
                ms::ObligationReason::Adapter(ms::AdapterObligationReason::UnmodeledSystemCall)
            }
            "unmodeled-concurrency" => {
                ms::ObligationReason::Adapter(ms::AdapterObligationReason::UnmodeledConcurrency)
            }
            _ => return Err(invalid("native stateflow obligation")),
        };
        if !r.nodes.contains(&site) || !obligations.insert(ms::Obligation { site, reason }) {
            return Err(invalid("native obligation domain/duplicate"));
        }
    }
    Ok((
        ms::AnalysisState { phase, states_at },
        ms::Observations {
            feasible_edges,
            provably_infeasible_edges,
            unknown_feasibility_edges,
            reached_terminal_transitions,
            not_reached_nodes,
            obligations,
        },
    ))
}
pub struct NativeStateflow {
    request: ms::Request,
    state: ms::AnalysisState,
    observations: ms::Observations,
    session: StateflowSession,
    actions: u64,
    closed: bool,
}
impl NativeStateflow {
    pub fn new(config: &CoreConfig, token: &str, request: ms::Request) -> Result<Self, Error> {
        let input = encode_request(&request)?;
        let (session, response) =
            StateflowSession::start(config, token, &request.snapshot_id, &input)?;
        if response.error.is_some() {
            return Err(invalid("native stateflow initialize rejected"));
        }
        let (state, observations) = decode(&request, &response.observation)?;
        Ok(Self {
            request,
            state,
            observations,
            session,
            actions: 0,
            closed: false,
        })
    }
    pub fn request(&self) -> &ms::Request {
        &self.request
    }
    pub fn state(&self) -> &ms::AnalysisState {
        &self.state
    }
    pub fn observations(&self) -> &ms::Observations {
        &self.observations
    }
    pub fn step(&mut self) -> Result<bool, Error> {
        self.step_payload(json!({}))
    }
    pub fn advance_named(&mut self, action: &str) -> Result<(), Error> {
        if !self.step_payload(json!({"action":action}))? {
            return Err(invalid("stateflow action after done"));
        }
        Ok(())
    }
    fn step_payload(&mut self, payload: Value) -> Result<bool, Error> {
        if self.state.phase == ms::Phase::Done {
            return Ok(false);
        }
        if self.actions >= 1_000_000 {
            return Err(invalid("stateflow action budget exhausted"));
        }
        let response = self.session.request("step", payload)?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        let (state, observations) = decode(&self.request, &response.observation)?;
        self.state = state;
        self.observations = observations;
        self.actions = response.action_index;
        Ok(true)
    }
    pub fn observe(&mut self) -> Result<(), Error> {
        let response = self.session.request("observe", json!({}))?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        let (state, observations) = decode(&self.request, &response.observation)?;
        self.state = state;
        self.observations = observations;
        Ok(())
    }
    pub fn close(&mut self) -> Result<(), Error> {
        if !self.closed {
            self.session.request("reset", json!({}))?;
            self.closed = true;
        }
        Ok(())
    }
    pub fn finish(mut self) -> Result<ms::AnalysisResult, Error> {
        while self.step()? {}
        let response = self.session.request("finish", json!({}))?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        let (state, observations) = decode(&self.request, &response.observation)?;
        if state != self.state
            || observations != self.observations
            || response
                .result
                .is_none_or(|r| r.missing_slice_seeds.is_some())
        {
            return Err(invalid("native stateflow finish mutated/unbound result"));
        }
        self.session.request("reset", json!({}))?;
        Ok(ms::AnalysisResult::from_native(
            self.request,
            state,
            observations,
        ))
    }
}
