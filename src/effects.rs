//! Reviewed normal-continuation effects, independent of full ISA-step acceptance.
mod locations;
mod rules;

use crate::{Address, AnalysisRequest, ByteSource, InstructionKind, LocationSet};
pub use locations::{Catalogue, RegisterView};
pub(crate) use rules::summarize;
use std::collections::BTreeMap;

pub const RULESET: &str = "user64-effects-v1.0";

/// Fixed long64 user-mode environment: ordinary RAM, CET disabled, no
/// asynchronous/exception-handler edges or concurrent interference.
#[derive(Clone, Debug, Default)]
pub struct PreparationOptions {
    pub catalogue: Catalogue,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Operand {
    /// LLVM x86 condition selector, 0..15; mapping is reviewed with Jcc rules.
    Condition(u8),
    Register(RegisterView),
    Immediate {
        bits: u64,
        encoded_width: u8,
        semantic_width: u8,
        sign_extend: bool,
    },
    Memory {
        base: Option<RegisterView>,
        index: Option<RegisterView>,
        scale: u8,
        displacement: i64,
        address_width: u8,
        access_width: u8,
        next_ip: Option<Address>,
    },
    Relative {
        displacement: i64,
        target: Address,
        encoded_width: u8,
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EffectQuality {
    Reviewed,
    Opaque,
    Unavailable,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GapReason {
    MissingBytes,
    InvalidEncoding,
    UnsupportedControl,
    OpaqueEffects,
    UndefinedFlags,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PreparationGap {
    pub address: Address,
    pub reason: GapReason,
}
#[derive(Clone, Debug)]
pub struct InstructionEvidence {
    pub bytes: Vec<u8>,
    pub source: ByteSource,
    pub opcode: Option<String>,
    pub length: u8,
    pub operands: Vec<Operand>,
    pub rule: Option<String>,
    pub control: Option<InstructionKind>,
    pub quality: EffectQuality,
    pub undefined_flags: LocationSet,
    /// Raw LLVM facts are retained for inspection; they do not justify kills.
    pub decoder_record: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PreparationIdentity {
    pub target: String,
    pub decoder: String,
    pub protocol: u8,
    pub ruleset: String,
    pub catalogue: String,
}
#[derive(Clone, Debug)]
pub struct PreparedAnalysis {
    pub request: AnalysisRequest,
    pub instructions: BTreeMap<Address, InstructionEvidence>,
    pub gaps: Vec<PreparationGap>,
    pub identity: PreparationIdentity,
}

pub(crate) struct Summary {
    pub rule: String,
    pub operands: Vec<Operand>,
    pub kind: InstructionKind,
    pub uses: LocationSet,
    pub may_defs: LocationSet,
    pub must_defs: LocationSet,
    pub undefined: LocationSet,
    pub quality: EffectQuality,
}
