use crate::model::*;
use std::cell::Cell;
use std::collections::BTreeMap;

/// Operation counts for a single deterministic analyzer run. These are
/// observations of implementation work, not an ISA or refinement certificate.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct AnalyzerMetrics {
    pub actions: u64,
    pub incoming_evaluations: u64,
    pub edge_scans: u64,
    pub transfer_evaluations: u64,
    pub max_reaching_definitions_at_site: usize,
}

/// A deterministic schedule of the specification's enabled actions. Inputs are
/// owned, validated at construction, and only exposed by shared reference.
#[derive(Debug)]
pub struct Analyzer {
    request: AnalysisRequest,
    state: AnalysisState,
    metrics: Cell<AnalyzerMetrics>,
    incoming_edges: BTreeMap<Address, EdgeSet>,
    local_successors: BTreeMap<Address, AddressSet>,
    incoming_cache: BTreeMap<Address, DefinitionSet>,
    dirty_incoming: AddressSet,
    outgoing_cache: BTreeMap<Address, DefinitionSet>,
    enabled_dataflow: AddressSet,
}

impl Analyzer {
    pub fn new(request: AnalysisRequest) -> Result<Self, InvalidRequest> {
        request.validate()?;
        let state = AnalysisState {
            pending: request.entry_points.clone(),
            provenance: request
                .addresses
                .iter()
                .map(|&a| (a, ByteSource::Unavailable))
                .collect(),
            reaching: request
                .addresses
                .iter()
                .map(|&a| (a, DefinitionSet::new()))
                .collect(),
            ..AnalysisState::default()
        };
        Ok(Self {
            request,
            state,
            metrics: Cell::new(AnalyzerMetrics::default()),
            incoming_edges: BTreeMap::new(),
            local_successors: BTreeMap::new(),
            incoming_cache: BTreeMap::new(),
            dirty_incoming: AddressSet::new(),
            outgoing_cache: BTreeMap::new(),
            enabled_dataflow: AddressSet::new(),
        })
    }

    pub fn request(&self) -> &AnalysisRequest {
        &self.request
    }

    pub fn state(&self) -> &AnalysisState {
        &self.state
    }

    pub fn metrics(&self) -> AnalyzerMetrics {
        self.metrics.get()
    }

    /// Consume a recovery prefix without running the next model action. This
    /// crate-private seam does not publish the full state as a completed result.
    pub(crate) fn into_recovery_parts(self) -> (AnalysisRequest, AnalysisState, AnalyzerMetrics) {
        debug_assert_eq!(self.state.phase, Phase::Recover);
        (self.request, self.state, self.metrics.get())
    }

    /// Perform one `Next` action, choosing the lowest eligible VA when the
    /// specification leaves scheduling open. Returns false only in `Done`.
    pub fn step(&mut self) -> bool {
        if self.state.phase == Phase::Done {
            return false;
        }
        let mut metrics = self.metrics.get();
        metrics.actions += 1;
        self.metrics.set(metrics);
        match self.state.phase {
            Phase::Recover => {
                if let Some(&address) = self.state.pending.first() {
                    self.visit(address);
                } else {
                    // Recovery freezes the graph. Index it once without
                    // changing the visible FinishRecovery action.
                    for &edge in &self.state.edges {
                        self.incoming_edges
                            .entry(edge.dst)
                            .or_default()
                            .insert(edge);
                        if edge.kind.is_local() {
                            self.local_successors
                                .entry(edge.src)
                                .or_default()
                                .insert(edge.dst);
                        }
                    }
                    self.dirty_incoming = self.state.decoded.clone();
                    for &address in &self.state.decoded {
                        let instruction = &self.request.instructions[&address];
                        self.outgoing_cache.insert(
                            address,
                            instruction
                                .may_defs
                                .iter()
                                .map(|loc| Definition {
                                    loc: loc.clone(),
                                    site: address,
                                    origin: DefinitionOrigin::Instruction,
                                })
                                .collect(),
                        );
                    }
                    self.state.phase = Phase::Dataflow; // FinishRecovery
                }
            }
            Phase::Dataflow => {
                while let Some(address) = self.dirty_incoming.pop_first() {
                    let incoming = self.incoming(address);
                    if !incoming.is_subset(&self.state.reaching[&address]) {
                        self.enabled_dataflow.insert(address);
                    } else {
                        self.enabled_dataflow.remove(&address);
                    }
                    self.incoming_cache.insert(address, incoming);
                }
                if let Some(address) = self.enabled_dataflow.pop_first() {
                    let (mut delta, size) = {
                        let incoming = &self.incoming_cache[&address];
                        let reaching = self
                            .state
                            .reaching
                            .get_mut(&address)
                            .expect("validated domain");
                        let delta: DefinitionSet = incoming.difference(reaching).cloned().collect();
                        reaching.extend(delta.iter().cloned());
                        (delta, reaching.len())
                    };
                    let instruction = &self.request.instructions[&address];
                    delta.retain(|d| {
                        !instruction.must_defs.contains(&d.loc)
                            && !self.outgoing_cache[&address].contains(d)
                    });
                    self.outgoing_cache
                        .get_mut(&address)
                        .expect("decoded outgoing cache")
                        .extend(delta.iter().cloned());
                    let mut metrics = self.metrics.get();
                    metrics.max_reaching_definitions_at_site =
                        metrics.max_reaching_definitions_at_site.max(size);
                    if let Some(successors) = self.local_successors.get(&address) {
                        for &destination in successors.intersection(&self.state.decoded) {
                            if delta
                                .iter()
                                .any(|d| !self.state.reaching[&destination].contains(d))
                            {
                                self.enabled_dataflow.insert(destination);
                            }
                            self.incoming_cache
                                .get_mut(&destination)
                                .expect("decoded incoming cache")
                                .extend(delta.iter().cloned());
                            metrics.incoming_evaluations += 1;
                            metrics.transfer_evaluations += 1;
                            metrics.edge_scans += 1;
                        }
                    }
                    self.metrics.set(metrics);
                    return true;
                }
                // Bottom initialization and monotone union maintain
                // reaching[a] subseteq Incoming(a). No growth means equality.
                self.state.phase = Phase::Slice; // FinishDataflow
                self.state.slice = self
                    .request
                    .slice_seeds
                    .intersection(&self.state.decoded)
                    .copied()
                    .collect();
            }
            Phase::Slice => {
                let predecessors = self.slice_predecessors();
                if predecessors.is_subset(&self.state.slice) {
                    self.state.phase = Phase::Done; // FinishSlice
                } else {
                    self.state.slice.extend(predecessors); // ExpandSlice
                }
            }
            Phase::Done => unreachable!("handled before action counting"),
        }
        true
    }

    /// Consume the analyzer, run any remaining actions, and return an owned
    /// completed result. Local/call graphs are derived from one stored edge set.
    pub fn finish(mut self) -> AnalysisResult {
        let limits = crate::CompletionLimits {
            max_actions: u64::MAX,
            max_elapsed: std::time::Duration::MAX,
            ..crate::CompletionLimits::default()
        };
        // Resource-policy refusal falls back to the existing unbounded API.
        // No partial compact result is published or interpreted as complete.
        let _ = self.complete(limits);
        while self.step() {}
        self.into_result()
    }

    /// Complete under explicit total-action, workspace and elapsed limits.
    /// Ordinary step/replay scheduling is independent of completion scheduling.
    pub fn finish_bounded(
        mut self,
        limits: crate::CompletionLimits,
    ) -> Result<(AnalysisResult, AnalyzerMetrics), crate::CompletionError> {
        self.complete(limits)?;
        let metrics = self.metrics();
        Ok((self.into_result(), metrics))
    }

    fn complete(&mut self, limits: crate::CompletionLimits) -> Result<(), crate::CompletionError> {
        let started = std::time::Instant::now();
        if self.metrics().actions > limits.max_actions {
            return Err(crate::CompletionError {
                reason: "action budget",
                actions: self.metrics().actions,
            });
        }
        while self.state.phase == Phase::Recover {
            crate::completion::check(limits, started, self.metrics().actions)?;
            self.step();
        }
        if self.state.phase == Phase::Dataflow {
            let mut metrics = self.metrics();
            crate::completion::dataflow(
                &self.request,
                &mut self.state,
                &mut metrics,
                limits,
                started,
            )?;
            self.metrics.set(metrics);
            self.dirty_incoming.clear();
            self.enabled_dataflow.clear();
            self.incoming_cache.clear();
            self.outgoing_cache.clear();
        }
        while self.state.phase != Phase::Done {
            crate::completion::check(limits, started, self.metrics().actions)?;
            self.step();
        }
        Ok(())
    }

    fn into_result(self) -> AnalysisResult {
        AnalysisResult {
            snapshot_id: self.request.snapshot_id,
            missing_slice_seeds: self
                .request
                .slice_seeds
                .difference(&self.state.decoded)
                .copied()
                .collect(),
            state: self.state,
        }
    }

    fn source(&self, address: Address) -> ByteSource {
        match self.request.input_kind {
            InputKind::Binary if self.request.file_backed.contains(&address) => ByteSource::File,
            InputKind::Binary => ByteSource::Unavailable,
            InputKind::Dump if self.request.captured.contains(&address) => ByteSource::Captured,
            InputKind::Dump if self.request.trusted_fallback.contains(&address) => ByteSource::File,
            InputKind::Dump => ByteSource::Unavailable,
        }
    }

    fn instruction_edges(&self, address: Address) -> EdgeSet {
        let instruction = &self.request.instructions[&address];
        let mut edges = EdgeSet::new();
        let mut add = |destinations: &AddressSet, kind| {
            edges.extend(destinations.iter().map(|&dst| Edge {
                src: address,
                dst,
                kind,
            }));
        };
        match instruction.kind {
            InstructionKind::Ordinary => add(&instruction.fall, EdgeKind::Next),
            InstructionKind::Conditional => {
                add(&instruction.targets, EdgeKind::Taken);
                add(&instruction.fall, EdgeKind::Fallthrough);
            }
            InstructionKind::Jump => add(&instruction.targets, EdgeKind::Jump),
            InstructionKind::Indirect => add(&instruction.targets, EdgeKind::Indirect),
            InstructionKind::Call => {
                add(&instruction.targets, EdgeKind::Call);
                add(&instruction.fall, EdgeKind::Summary);
            }
            InstructionKind::Return | InstructionKind::Stop => {}
        }
        edges
    }

    fn visit(&mut self, address: Address) {
        self.state.visited.insert(address);
        self.state.pending.remove(&address);
        let source = self.source(address);
        if source == ByteSource::Unavailable || !self.request.decodable.contains(&address) {
            self.state.obligations.insert(Obligation {
                site: address,
                reason: if source == ByteSource::Unavailable {
                    ObligationReason::Unavailable
                } else {
                    ObligationReason::DecodeFailed
                },
            });
            return;
        }

        self.state.decoded.insert(address);
        self.state.provenance.insert(address, source);
        for edge in self.instruction_edges(address) {
            self.state.edges.insert(edge);
            // visited already includes address; self-loops cannot requeue it.
            if edge.kind.is_local() && !self.state.visited.contains(&edge.dst) {
                self.state.pending.insert(edge.dst);
            }
        }
        let instruction = &self.request.instructions[&address];
        if !instruction.complete {
            let reason = match instruction.kind {
                InstructionKind::Indirect => Some(ObligationReason::IndirectTargets),
                InstructionKind::Call => Some(ObligationReason::CallTargets),
                _ => None,
            };
            if let Some(reason) = reason {
                self.state.obligations.insert(Obligation {
                    site: address,
                    reason,
                });
            }
        }
    }

    fn incoming(&self, address: Address) -> DefinitionSet {
        let mut metrics = self.metrics.get();
        metrics.incoming_evaluations += 1;
        let mut incoming = DefinitionSet::new();
        if self.request.entry_points.contains(&address) {
            incoming.extend(self.request.locations.iter().map(|loc| Definition {
                loc: loc.clone(),
                site: address,
                origin: DefinitionOrigin::Entry,
            }));
        }
        for edge in self.incoming_edges.get(&address).into_iter().flatten() {
            metrics.edge_scans += 1;
            if edge.dst != address
                || !edge.kind.is_local()
                || !self.state.decoded.contains(&edge.src)
            {
                continue;
            }
            metrics.transfer_evaluations += 1;
            incoming.extend(self.outgoing_cache[&edge.src].iter().cloned());
        }
        self.metrics.set(metrics);
        incoming
    }

    fn slice_predecessors(&self) -> AddressSet {
        self.state
            .slice
            .iter()
            .flat_map(|address| {
                let uses = &self.request.instructions[address].uses;
                self.state.reaching[address]
                    .iter()
                    .filter(|definition| {
                        definition.origin == DefinitionOrigin::Instruction
                            && uses.contains(&definition.loc)
                    })
                    .map(|definition| definition.site)
            })
            .collect()
    }
}

/// Validate and analyze one immutable request to completion.
pub fn analyze(request: AnalysisRequest) -> Result<AnalysisResult, InvalidRequest> {
    Ok(Analyzer::new(request)?.finish())
}
