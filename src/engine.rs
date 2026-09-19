use crate::model::*;

/// A deterministic schedule of the specification's enabled actions. Inputs are
/// owned, validated at construction, and only exposed by shared reference.
#[derive(Debug)]
pub struct Analyzer {
    request: AnalysisRequest,
    state: AnalysisState,
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
        Ok(Self { request, state })
    }

    pub fn request(&self) -> &AnalysisRequest {
        &self.request
    }

    pub fn state(&self) -> &AnalysisState {
        &self.state
    }

    /// Perform one `Next` action, choosing the lowest eligible VA when the
    /// specification leaves scheduling open. Returns false only in `Done`.
    pub fn step(&mut self) -> bool {
        match self.state.phase {
            Phase::Recover => {
                if let Some(&address) = self.state.pending.first() {
                    self.visit(address);
                } else {
                    self.state.phase = Phase::Dataflow; // FinishRecovery
                }
            }
            Phase::Dataflow => {
                for &address in &self.state.decoded {
                    let incoming = self.incoming(address);
                    let reaching = self
                        .state
                        .reaching
                        .get_mut(&address)
                        .expect("validated domain");
                    if !incoming.is_subset(reaching) {
                        reaching.extend(incoming); // Propagate
                        return true;
                    }
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
            Phase::Done => return false,
        }
        true
    }

    /// Consume the analyzer, run any remaining actions, and return an owned
    /// completed result. Local/call graphs are derived from one stored edge set.
    pub fn finish(mut self) -> AnalysisResult {
        while self.step() {}
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
        let mut incoming = DefinitionSet::new();
        if self.request.entry_points.contains(&address) {
            incoming.extend(self.request.locations.iter().map(|loc| Definition {
                loc: loc.clone(),
                site: address,
                origin: DefinitionOrigin::Entry,
            }));
        }
        for edge in &self.state.edges {
            if edge.dst != address
                || !edge.kind.is_local()
                || !self.state.decoded.contains(&edge.src)
            {
                continue;
            }
            let predecessor = &self.request.instructions[&edge.src];
            incoming.extend(
                self.state.reaching[&edge.src]
                    .iter()
                    .filter(|definition| !predecessor.must_defs.contains(&definition.loc))
                    .cloned(),
            );
            incoming.extend(predecessor.may_defs.iter().map(|loc| Definition {
                loc: loc.clone(),
                site: edge.src,
                origin: DefinitionOrigin::Instruction,
            }));
        }
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
