//! Verified native LLVM IR input for the separate `ariadne::llvm_ir` machine.
//! The LLVM 20 helper parses/verifies an owned byte snapshot; this crate binds
//! the normalized rows to that snapshot before the dependency-slice engine runs.
use ariadne::llvm_ir as model;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;
use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::Command;

pub const MAX_IR_BYTES: usize = 32 * 1024 * 1024;
pub const MAX_PROTOCOL_BYTES: usize = 32 * 1024 * 1024;
pub const NATIVE_VERSION: &str = "Ariadne native LLVM IR 20.1.2";

#[derive(Debug)]
pub enum AdapterError {
    Io(std::io::Error),
    Native(String),
    Protocol(String),
    InvalidRequest(model::InvalidRequest),
}
impl fmt::Display for AdapterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(error) => write!(f, "IR I/O: {error}"),
            Self::Native(error) => write!(f, "LLVM IR helper: {error}"),
            Self::Protocol(error) => write!(f, "LLVM IR protocol: {error}"),
            Self::InvalidRequest(error) => write!(f, "normalized IR: {error}"),
        }
    }
}
impl Error for AdapterError {}
impl From<std::io::Error> for AdapterError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}
fn protocol(message: impl Into<String>) -> AdapterError {
    AdapterError::Protocol(message.into())
}
fn required<'a>(value: &'a Value, field: &str) -> Result<&'a Value, AdapterError> {
    value
        .get(field)
        .ok_or_else(|| protocol(format!("missing {field}")))
}
fn string(value: &Value, field: &str) -> Result<String, AdapterError> {
    required(value, field)?
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| protocol(format!("{field} must be a string")))
}
fn array<'a>(value: &'a Value, field: &str) -> Result<&'a Vec<Value>, AdapterError> {
    required(value, field)?
        .as_array()
        .ok_or_else(|| protocol(format!("{field} must be an array")))
}
fn strings(value: &Value, field: &str) -> Result<Vec<String>, AdapterError> {
    array(value, field)?
        .iter()
        .map(|item| {
            item.as_str()
                .map(str::to_owned)
                .ok_or_else(|| protocol(format!("{field} contains a non-string")))
        })
        .collect()
}
fn block(name: String) -> model::BlockId {
    model::BlockId(name)
}
fn instruction(name: String) -> model::InstructionId {
    model::InstructionId(name)
}
fn value(name: String) -> model::ValueId {
    model::ValueId(name)
}
fn callee(name: String) -> model::CalleeId {
    model::CalleeId(name)
}
fn term_kind(text: &str) -> Result<model::TerminatorKind, AdapterError> {
    use model::TerminatorKind::*;
    Ok(match text {
        "br" => Br,
        "switch" => Switch,
        "indirectbr" => IndirectBr,
        "invoke" => Invoke,
        "callbr" => CallBr,
        "ret" => Ret,
        "resume" => Resume,
        "unreachable" => Unreachable,
        "catchswitch" => CatchSwitch,
        "catchret" => CatchRet,
        "cleanupret" => CleanupRet,
        _ => return Err(protocol(format!("unknown terminator: {text}"))),
    })
}
fn edge_kind(text: &str) -> Result<model::ControlEdgeKind, AdapterError> {
    use model::ControlEdgeKind::*;
    Ok(match text {
        "next" => Next,
        "true" => True,
        "false" => False,
        "case" => Case,
        "default" => Default,
        "indirect" => Indirect,
        "normal" => Normal,
        "unwind" => Unwind,
        "fallthrough" => Fallthrough,
        "catch" => Catch,
        "cleanup" => Cleanup,
        _ => return Err(protocol(format!("unknown edge kind: {text}"))),
    })
}
fn value_kind(text: &str) -> Result<model::ValueKind, AdapterError> {
    use model::ValueKind::*;
    Ok(match text {
        "instruction" => Instruction,
        "argument" => Argument,
        "constant" => Constant,
        "global" => Global,
        "external" => External,
        _ => return Err(protocol(format!("unknown value kind: {text}"))),
    })
}
fn obligation_reason(text: &str) -> Result<model::AdapterObligationReason, AdapterError> {
    use model::AdapterObligationReason::*;
    Ok(match text {
        "unsupported-instruction" => UnsupportedInstruction,
        "incomplete-semantics" => IncompleteSemantics,
        "unknown-memory-alias" => UnknownMemoryAlias,
        "unmodeled-exception" => UnmodeledException,
        "unmodeled-system-call" => UnmodeledSystemCall,
        "unmodeled-concurrency" => UnmodeledConcurrency,
        _ => return Err(protocol(format!("unknown obligation: {text}"))),
    })
}
fn unique<K: Ord, V>(
    map: &mut BTreeMap<K, V>,
    key: K,
    value: V,
    label: &str,
) -> Result<(), AdapterError> {
    if map.insert(key, value).is_some() {
        return Err(protocol(format!("duplicate {label}")));
    }
    Ok(())
}
fn unique_set<T: Ord>(
    values: impl IntoIterator<Item = T>,
    label: &str,
) -> Result<BTreeSet<T>, AdapterError> {
    let mut result = BTreeSet::new();
    for value in values {
        if !result.insert(value) {
            return Err(protocol(format!("duplicate {label}")));
        }
    }
    Ok(result)
}

/// Parse the helper's bounded, versioned output, then validate all model facts.
pub fn parse_verified_output(
    bytes: &[u8],
    artifact_sha256: &str,
    seeds: BTreeSet<model::InstructionId>,
) -> Result<model::Request, AdapterError> {
    if bytes.len() > MAX_PROTOCOL_BYTES {
        return Err(protocol("helper output too large"));
    }
    if !artifact_sha256.bytes().all(|b| b.is_ascii_hexdigit()) || artifact_sha256.len() != 64 {
        return Err(protocol("invalid artifact SHA-256"));
    }
    let root: Value = serde_json::from_slice(bytes).map_err(|e| protocol(e.to_string()))?;
    if string(&root, "schema")? != "ariadne-native-ir-v1"
        || string(&root, "llvm_version")? != "20.1.2"
        || required(&root, "verified_ir")?.as_bool() != Some(true)
    {
        return Err(protocol("schema, LLVM version or verifier result mismatch"));
    }
    let mut blocks = BTreeMap::new();
    for row in array(&root, "blocks")? {
        let mut successors = BTreeSet::new();
        for successor in array(row, "successors")? {
            if !successors.insert(model::Successor {
                dst: block(string(successor, "dst")?),
                kind: edge_kind(&string(successor, "kind")?)?,
            }) {
                return Err(protocol("duplicate successor"));
            }
        }
        unique(
            &mut blocks,
            block(string(row, "id")?),
            model::BlockInfo {
                terminator: instruction(string(row, "terminator")?),
                kind: term_kind(&string(row, "kind")?)?,
                successors,
            },
            "block",
        )?;
    }
    let mut instructions = BTreeMap::new();
    for row in array(&root, "instructions")? {
        let index = required(row, "index")?
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| protocol("instruction index outside u32"))?;
        let phi_incoming = unique_set(
            array(row, "phi_incoming")?
                .iter()
                .map(|phi| {
                    Ok(model::PhiIncoming {
                        pred: block(string(phi, "pred")?),
                        value: value(string(phi, "value")?),
                    })
                })
                .collect::<Result<Vec<_>, AdapterError>>()?,
            "phi incoming",
        )?;
        unique(
            &mut instructions,
            instruction(string(row, "id")?),
            model::InstructionInfo {
                block: block(string(row, "block")?),
                index,
                uses: strings(row, "uses")?.into_iter().map(value).collect(),
                phi_incoming,
                memory_preds: unique_set(
                    strings(row, "memory_preds")?.into_iter().map(instruction),
                    "memory predecessor",
                )?,
                call_targets: unique_set(
                    strings(row, "call_targets")?.into_iter().map(callee),
                    "call target",
                )?,
            },
            "instruction",
        )?;
    }
    let mut values = BTreeMap::new();
    for row in array(&root, "values")? {
        unique(
            &mut values,
            value(string(row, "id")?),
            model::ValueInfo {
                kind: value_kind(&string(row, "kind")?)?,
                def_site: instruction(string(row, "def_site")?),
            },
            "value",
        )?;
    }
    let adapter_obligations = unique_set(
        array(&root, "obligations")?
            .iter()
            .map(|row| {
                Ok(model::AdapterObligation {
                    site: instruction(string(row, "site")?),
                    reason: obligation_reason(&string(row, "reason")?)?,
                })
            })
            .collect::<Result<Vec<_>, AdapterError>>()?,
        "adapter obligation",
    )?;
    let request = model::Request {
        artifact_id: format!(
            "llvm-ir-artifact-v1:{}",
            artifact_sha256.to_ascii_lowercase()
        ),
        module_id: format!("module:{}", artifact_sha256.to_ascii_lowercase()),
        function_id: string(&root, "function_id")?,
        verified_ir: true,
        blocks,
        entry_block: block(string(&root, "entry_block")?),
        instructions,
        values,
        phi_nodes: unique_set(
            strings(&root, "phi_nodes")?.into_iter().map(instruction),
            "phi node",
        )?,
        call_sites: unique_set(
            strings(&root, "call_sites")?.into_iter().map(instruction),
            "call site",
        )?,
        callees: unique_set(strings(&root, "callees")?.into_iter().map(callee), "callee")?,
        complete_calls: unique_set(
            strings(&root, "complete_calls")?
                .into_iter()
                .map(instruction),
            "complete call",
        )?,
        adapter_obligations,
        slice_seeds: seeds,
    };
    request.validate().map_err(AdapterError::InvalidRequest)?;
    Ok(request)
}

/// Hash owned bytes, ask the pinned helper to parse and verify that byte
/// snapshot, then admit only a fully validated normalized model request.
pub fn open_verified_ir(
    path: &Path,
    helper: &Path,
    function: &str,
    seeds: BTreeSet<model::InstructionId>,
) -> Result<model::Request, AdapterError> {
    let version = Command::new(helper).arg("--version").output()?;
    if !version.status.success()
        || String::from_utf8_lossy(&version.stdout).trim() != NATIVE_VERSION
    {
        return Err(AdapterError::Native(
            "expected pinned LLVM 20.1.2 helper".into(),
        ));
    }
    let metadata = fs::metadata(path)?;
    if metadata.len() > MAX_IR_BYTES as u64 {
        return Err(protocol("IR artifact too large"));
    }
    let bytes = fs::read(path)?;
    if bytes.len() > MAX_IR_BYTES {
        return Err(protocol("IR artifact too large"));
    }
    let hash = format!("{:x}", Sha256::digest(&bytes));
    let mut snapshot = tempfile::Builder::new()
        .prefix("ariadne-ir-")
        .suffix(".ll")
        .tempfile()?;
    snapshot.write_all(&bytes)?;
    snapshot.as_file().sync_all()?;
    let output = Command::new(helper)
        .arg(snapshot.path())
        .arg(function)
        .output()?;
    if !output.status.success() {
        return Err(AdapterError::Native(
            String::from_utf8_lossy(&output.stderr).into_owned(),
        ));
    }
    parse_verified_output(&output.stdout, &hash, seeds)
}
