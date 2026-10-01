//! Typed MirrorRust ports for the independent Stage E analysis engines.
pub mod fixtures_ir;
pub mod fixtures_machine;
mod ports;
pub use ports::{LLVMIRPort, MachineStatePort};

// The compiler owns these bytes; freshness is checked by prepare.py --check.
#[rustfmt::skip]
#[allow(dead_code, unused_variables)]
#[path = "../generated/machine_state/MachineStateReplayMirror.generated.rs"]
pub mod machine_binding;
#[rustfmt::skip]
#[allow(dead_code, unused_variables)]
#[path = "../generated/llvm_ir/LLVMIRReplayMirror.generated.rs"]
pub mod ir_binding;

use mirrorrust::{
    BindingError, CompiledAdapterKey, CompiledAdapterRegistration, GeneratedModelInterface,
    STATE_COMPUTER_CONTRACT_VERSION, SemanticDigest,
};
use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

pub const TARGET: &str = "mirrorrust-v1";

#[derive(Clone, Copy, Debug)]
pub enum Engine {
    MachineState,
    LLVMIR,
}

impl Engine {
    pub fn metadata(self) -> GeneratedModelInterface {
        match self {
            Self::MachineState => machine_binding::model_interface(),
            Self::LLVMIR => ir_binding::model_interface(),
        }
    }
    pub fn adapter_id(self) -> &'static str {
        match self {
            Self::MachineState => "ariadne.machine-state/v1",
            Self::LLVMIR => "ariadne.llvm-ir/v1",
        }
    }
    pub fn contract(self) -> &'static str {
        match self {
            Self::MachineState => machine_binding::CONTRACT_JSON,
            Self::LLVMIR => ir_binding::CONTRACT_JSON,
        }
    }
}

#[derive(Default, Debug)]
pub struct Evidence {
    pub factories: usize,
    pub port_drops: usize,
    pub initializations: usize,
    pub observations: usize,
    pub completed: usize,
    pub cases: Vec<String>,
    pub pairs: BTreeMap<String, usize>,
    pub previous_action: Option<&'static str>,
    pub actions: BTreeMap<&'static str, usize>,
}
impl Evidence {
    pub fn record_action(&mut self, action: &'static str) {
        *self.actions.entry(action).or_default() += 1;
        if let Some(previous) = self.previous_action {
            *self
                .pairs
                .entry(format!("{previous}->{action}"))
                .or_default() += 1;
        }
        self.previous_action = Some(action);
    }
}
pub type SharedEvidence = Rc<RefCell<Evidence>>;

fn key(engine: Engine, digest: SemanticDigest) -> CompiledAdapterKey {
    CompiledAdapterKey {
        semantic_digest: digest,
        adapter_id: engine.adapter_id().into(),
        target_profile: TARGET.into(),
        state_computer_contract_version: STATE_COMPUTER_CONTRACT_VERSION.into(),
    }
}

pub fn machine_state_registration(
    request: ariadne::machine_state::Request,
    evidence: SharedEvidence,
) -> Result<CompiledAdapterRegistration, mirrorrust::NegotiatedError> {
    machine_state_cases_registration([("MachineStateReplay".into(), request)].into(), evidence)
}
pub fn machine_state_cases_registration(
    requests: BTreeMap<String, ariadne::machine_state::Request>,
    evidence: SharedEvidence,
) -> Result<CompiledAdapterRegistration, mirrorrust::NegotiatedError> {
    let digest = SemanticDigest::from_hex(machine_binding::SEMANTIC_DIGEST)?;
    Ok(CompiledAdapterRegistration {
        key: key(Engine::MachineState, digest),
        factory: Box::new(move |matched| {
            if matched.semantic_digest() != digest {
                return Err(BindingError::new(
                    "digest_mismatch",
                    "unexpected matched context",
                ));
            }
            evidence.borrow_mut().factories += 1;
            machine_binding::bind_machine_state_replay(
                MachineStatePort::with_cases(requests.clone(), evidence.clone()),
                matched.effective_config(),
            )?
            .into_local_binding()
        }),
    })
}

pub fn llvm_ir_registration(
    request: ariadne::llvm_ir::Request,
    evidence: SharedEvidence,
) -> Result<CompiledAdapterRegistration, mirrorrust::NegotiatedError> {
    llvm_ir_cases_registration([("LLVMIRReplay".into(), request)].into(), evidence)
}
pub fn llvm_ir_cases_registration(
    requests: BTreeMap<String, ariadne::llvm_ir::Request>,
    evidence: SharedEvidence,
) -> Result<CompiledAdapterRegistration, mirrorrust::NegotiatedError> {
    let digest = SemanticDigest::from_hex(ir_binding::SEMANTIC_DIGEST)?;
    Ok(CompiledAdapterRegistration {
        key: key(Engine::LLVMIR, digest),
        factory: Box::new(move |matched| {
            if matched.semantic_digest() != digest {
                return Err(BindingError::new(
                    "digest_mismatch",
                    "unexpected matched context",
                ));
            }
            evidence.borrow_mut().factories += 1;
            ir_binding::bind_l_l_v_m_i_r_replay(
                LLVMIRPort::with_cases(requests.clone(), evidence.clone()),
                matched.effective_config(),
            )?
            .into_local_binding()
        }),
    })
}
