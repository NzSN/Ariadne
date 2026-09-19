use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

/// A semantic virtual address, never a file offset or compact node ID.
/// Implements the subset of TLA+ nonnegative addresses representable in 64 bits.
pub type Address = u64;
pub type Location = String;
pub type AddressSet = BTreeSet<Address>;
pub type LocationSet = BTreeSet<Location>;
pub type EdgeSet = BTreeSet<Edge>;
pub type DefinitionSet = BTreeSet<Definition>;
pub type ObligationSet = BTreeSet<Obligation>;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum InputKind {
    #[default]
    Binary,
    Dump,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum InstructionKind {
    Ordinary,
    Conditional,
    Jump,
    Indirect,
    Call,
    Return,
    #[default]
    Stop,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ByteSource {
    Captured,
    File,
    Unavailable,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum EdgeKind {
    Next,
    Taken,
    Fallthrough,
    Jump,
    Indirect,
    Summary,
    Call,
}

impl EdgeKind {
    /// The specification's explicit local-edge allowlist.
    pub fn is_local(self) -> bool {
        matches!(
            self,
            Self::Next
                | Self::Taken
                | Self::Fallthrough
                | Self::Jump
                | Self::Indirect
                | Self::Summary
        )
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ObligationReason {
    Unavailable,
    DecodeFailed,
    IndirectTargets,
    CallTargets,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum DefinitionOrigin {
    Entry,
    Instruction,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Phase {
    #[default]
    Recover,
    Dataflow,
    Slice,
    Done,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct AddressIdentity {
    pub snapshot: String,
    pub va: Address,
}

/// A trusted normalized semantic summary. Only definite writes kill origins.
/// `complete` certifies the target set of an indirect jump or call.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Instruction {
    pub kind: InstructionKind,
    pub fall: AddressSet,
    pub targets: AddressSet,
    pub complete: bool,
    pub uses: LocationSet,
    pub must_defs: LocationSet,
    pub may_defs: LocationSet,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Edge {
    pub src: Address,
    pub dst: Address,
    pub kind: EdgeKind,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Obligation {
    pub site: Address,
    pub reason: ObligationReason,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Definition {
    pub loc: Location,
    pub site: Address,
    pub origin: DefinitionOrigin,
}

/// Fixed inputs from `Specs/Ariadne.tla`. Every field belongs to one snapshot.
/// `instructions` is total over `addresses`, including undecodable placeholders.
/// An empty default request is invalid until its required fields are populated.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct AnalysisRequest {
    pub snapshot_id: String,
    pub addresses: AddressSet,
    pub locations: LocationSet,
    pub entry_points: AddressSet,
    pub slice_seeds: AddressSet,
    pub input_kind: InputKind,
    pub captured: AddressSet,
    pub file_backed: AddressSet,
    pub trusted_fallback: AddressSet,
    pub decodable: AddressSet,
    pub instructions: BTreeMap<Address, Instruction>,
}

/// A violation of the model's input contract, detected before analysis starts.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidRequest {
    pub field: &'static str,
    pub address: Option<Address>,
    pub reason: &'static str,
}

impl fmt::Display for InvalidRequest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(address) = self.address {
            write!(f, "instruction at VA {address}: ")?;
        }
        write!(f, "{} {}", self.field, self.reason)
    }
}

impl Error for InvalidRequest {}

impl AnalysisRequest {
    /// Check `ASSUME` and the shared machine contract. This validates shape,
    /// not the accuracy of byte providers, decoding, semantics, or aliasing.
    pub fn validate(&self) -> Result<(), InvalidRequest> {
        let require = |condition, field, reason| {
            if condition {
                Ok(())
            } else {
                Err(InvalidRequest {
                    field,
                    address: None,
                    reason,
                })
            }
        };
        require(
            !self.snapshot_id.is_empty(),
            "snapshot_id",
            "must be nonempty",
        )?;
        require(!self.addresses.is_empty(), "addresses", "must be nonempty")?;
        require(
            !self.entry_points.is_empty(),
            "entry_points",
            "must be nonempty",
        )?;
        for (field, addresses) in [
            ("entry_points", &self.entry_points),
            ("slice_seeds", &self.slice_seeds),
            ("captured", &self.captured),
            ("file_backed", &self.file_backed),
            ("decodable", &self.decodable),
        ] {
            require(
                addresses.is_subset(&self.addresses),
                field,
                "must be a subset of addresses",
            )?;
        }
        require(
            self.trusted_fallback.is_subset(&self.file_backed),
            "trusted_fallback",
            "must be a subset of file_backed",
        )?;
        require(
            self.instructions.len() == self.addresses.len()
                && self
                    .addresses
                    .iter()
                    .all(|a| self.instructions.contains_key(a)),
            "instructions",
            "must have exactly the addresses domain",
        )?;

        for (&address, instruction) in &self.instructions {
            let require = |condition, field, reason| {
                if condition {
                    Ok(())
                } else {
                    Err(InvalidRequest {
                        field,
                        address: Some(address),
                        reason,
                    })
                }
            };
            require(
                instruction.fall.is_subset(&self.addresses),
                "fall",
                "must be a subset of addresses",
            )?;
            require(
                instruction.targets.is_subset(&self.addresses),
                "targets",
                "must be a subset of addresses",
            )?;
            require(
                instruction.uses.is_subset(&self.locations),
                "uses",
                "must be a subset of locations",
            )?;
            require(
                instruction.must_defs.is_subset(&instruction.may_defs),
                "must_defs",
                "must be a subset of may_defs",
            )?;
            require(
                instruction.may_defs.is_subset(&self.locations),
                "may_defs",
                "must be a subset of locations",
            )?;
            let has_continuation = matches!(
                instruction.kind,
                InstructionKind::Ordinary | InstructionKind::Conditional | InstructionKind::Call
            );
            require(
                instruction.fall.len() == usize::from(has_continuation),
                "fall",
                "must contain one continuation for ordinary/conditional/call, zero otherwise",
            )?;
            match instruction.kind {
                InstructionKind::Ordinary | InstructionKind::Return | InstructionKind::Stop => {
                    require(
                        instruction.targets.is_empty(),
                        "targets",
                        "must be empty for ordinary/return/stop",
                    )?;
                }
                InstructionKind::Conditional | InstructionKind::Jump => {
                    require(
                        instruction.targets.len() == 1,
                        "targets",
                        "must contain exactly one branch target",
                    )?;
                }
                InstructionKind::Indirect | InstructionKind::Call => {}
            }
        }
        Ok(())
    }
}

/// The complete TLA+ variable tuple, exposed by shared reference during analysis.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct AnalysisState {
    pub phase: Phase,
    pub pending: AddressSet,
    pub visited: AddressSet,
    pub decoded: AddressSet,
    pub provenance: BTreeMap<Address, ByteSource>,
    pub edges: EdgeSet,
    pub obligations: ObligationSet,
    pub reaching: BTreeMap<Address, DefinitionSet>,
    pub slice: AddressSet,
}

/// An owned completed result. Completion may still leave unresolved obligations.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnalysisResult {
    pub snapshot_id: String,
    pub state: AnalysisState,
    pub missing_slice_seeds: AddressSet,
}

impl AnalysisResult {
    pub fn identity_of(&self, address: Address) -> AddressIdentity {
        AddressIdentity {
            snapshot: self.snapshot_id.clone(),
            va: address,
        }
    }

    pub fn local_graph(&self) -> impl Iterator<Item = &Edge> {
        self.state.edges.iter().filter(|edge| edge.kind.is_local())
    }

    pub fn call_graph(&self) -> impl Iterator<Item = &Edge> {
        self.state
            .edges
            .iter()
            .filter(|edge| edge.kind == EdgeKind::Call)
    }

    /// Relative to this request and traversal policy. Does not imply that all
    /// real paths, callees, or requested slice seeds have been recovered.
    pub fn scope_closed(&self) -> bool {
        self.state.phase == Phase::Done && self.state.obligations.is_empty()
    }
}
