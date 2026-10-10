//! Experimental normalized recovery protocol; no completed-result operation.
use super::{Error, invalid};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub const MAX_FRAME: usize = 8 * 1024 * 1024;
pub const CAPTURED_PROFILE: &str = "captured-fixed-input/v1";
pub const PROFILE: &str = "normalized-fixed-input/v1";
pub const RECOVERY_OPERATIONS: &[&str] = &[
    "initialize",
    "advance:Visit",
    "advance:FinishRecovery",
    "advance:Propagate",
    "advance:FinishDataflow",
    "advance:ExpandSlice",
    "advance:FinishSlice",
    "advance:FinishStateflow",
    "step",
    "observe",
    "finish",
    "reset",
    "run-batch",
    "result-page",
    "result-close",
];
pub const MAX_COMPLETED_BYTES: usize = 256 * 1024 * 1024;
pub const COMPLETION_PAGE_BYTES: usize = 256 * 1024;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct CompletionResponse {
    pub schema: String,
    pub session: String,
    pub snapshot: String,
    pub query: String,
    pub family: String,
    pub sequence: u64,
    pub generation: u64,
    pub action_index: u64,
    pub advanced: u64,
    pub done: bool,
    pub closed: bool,
    pub offset: usize,
    pub total_bytes: usize,
    pub checksum: String,
    pub result_sequence: u64,
    pub data_hex: String,
    pub error: Option<SemanticError>,
}

pub(crate) fn completion_checksum(bytes: &[u8]) -> String {
    let hash = bytes.iter().fold(0xcbf29ce484222325_u64, |hash, byte| {
        (hash ^ u64::from(*byte)).wrapping_mul(0x100000001b3)
    });
    format!("{hash:016x}")
}

/// Canonical query identity. Arrays in this profile are sets or map-row sets.
pub fn query_digest(snapshot: &str, input: &Value) -> Result<String, Error> {
    family_query_digest(snapshot, "recovery", input)
}
pub fn family_query_digest(snapshot: &str, family: &str, input: &Value) -> Result<String, Error> {
    profile_query_digest(snapshot, family, PROFILE, input)
}
pub fn profile_query_digest(
    snapshot: &str,
    family: &str,
    profile: &str,
    input: &Value,
) -> Result<String, Error> {
    fn normalize(value: &Value) -> Result<Value, Error> {
        Ok(match value {
            Value::Array(xs) => {
                let mut xs = xs.iter().map(normalize).collect::<Result<Vec<_>, _>>()?;
                xs.sort_by_cached_key(Value::to_string);
                if xs.windows(2).any(|w| w[0] == w[1]) {
                    return Err(invalid("duplicate canonical set/map row"));
                }
                Value::Array(xs)
            }
            Value::Object(xs) => Value::Object(
                xs.iter()
                    .map(|(k, v)| Ok((k.clone(), normalize(v)?)))
                    .collect::<Result<_, Error>>()?,
            ),
            _ => value.clone(),
        })
    }
    let canonical = normalize(input)?.to_string();
    let mut digest = Sha256::new();
    digest.update(b"ariadne.bap-core-query/v1\0");
    for part in [snapshot, family, profile, &canonical] {
        digest.update((part.len() as u64).to_be_bytes());
        digest.update(part.as_bytes());
    }
    Ok(format!("{:x}", digest.finalize()))
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Observation {
    pub phase: String,
    pub pending: Vec<String>,
    pub visited: Vec<String>,
    pub decoded: Vec<String>,
    pub provenance: Vec<Provenance>,
    pub edges: Vec<Edge>,
    pub obligations: Vec<Obligation>,
    pub reaching: Vec<Reaching>,
    pub slice: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Provenance {
    pub address: String,
    pub source: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Edge {
    pub src: String,
    pub dst: String,
    pub kind: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Obligation {
    pub site: String,
    pub reason: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Reaching {
    pub address: String,
    pub definitions: Vec<DefinitionRow>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct DefinitionRow {
    pub loc: String,
    pub site: String,
    pub origin: String,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Attribution {
    #[serde(default)]
    pub evidence: Option<Value>,
    pub term: String,
    pub class: String,
    pub origin: String,
    pub snapshot: String,
    pub va: Option<String>,
    pub parents: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct FamilyResponse<O> {
    pub schema: String,
    pub session: String,
    pub snapshot: String,
    pub query: String,
    pub family: String,
    pub sequence: u64,
    pub generation: u64,
    pub action_index: u64,
    pub changed: bool,
    pub observation: O,
    pub attribution: Vec<Attribution>,
    pub error: Option<SemanticError>,
    pub result: Option<CompletedResult>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct CompletedResult {
    pub snapshot: String,
    pub missing_slice_seeds: Option<Vec<String>>,
}
pub type Response = FamilyResponse<Observation>;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct StateflowObservation {
    pub phase: String,
    pub states_at: Vec<StatesAt>,
    pub structural_edges: Vec<Edge>,
    pub feasible_edges: Vec<Edge>,
    pub provably_infeasible_edges: Vec<Edge>,
    pub unknown_feasibility_edges: Vec<Edge>,
    pub reached_terminal_transitions: Vec<TerminalRow>,
    pub not_reached_nodes: Vec<String>,
    pub obligations: Vec<Obligation>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct StatesAt {
    pub address: String,
    pub states: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct TerminalRow {
    pub site: String,
    pub before: String,
    pub after: String,
    pub outcome: String,
}

pub trait FamilyObservation: serde::de::DeserializeOwned + Clone + PartialEq {
    const FAMILY: &'static str;
    fn phase(&self) -> &str;
    fn validate_shape(&self) -> Result<(), Error>;
}
impl FamilyObservation for Observation {
    const FAMILY: &'static str = "recovery";
    fn phase(&self) -> &str {
        &self.phase
    }
    fn validate_shape(&self) -> Result<(), Error> {
        if !["recover", "dataflow", "slice", "done"].contains(&self.phase.as_str())
            || (self.phase != "recover" && !self.pending.is_empty())
            || (matches!(self.phase.as_str(), "recover" | "dataflow") && !self.slice.is_empty())
            || (self.phase == "recover"
                && self.reaching.iter().any(|row| !row.definitions.is_empty()))
        {
            return Err(invalid("core invalid phase/state"));
        }
        Ok(())
    }
}
impl FamilyObservation for StateflowObservation {
    const FAMILY: &'static str = "stateflow";
    fn phase(&self) -> &str {
        &self.phase
    }
    fn validate_shape(&self) -> Result<(), Error> {
        if !["stateflow", "done"].contains(&self.phase.as_str())
            || (self.phase != "done"
                && (!self.provably_infeasible_edges.is_empty()
                    || !self.not_reached_nodes.is_empty()))
        {
            return Err(invalid("stateflow invalid phase/feasibility"));
        }
        Ok(())
    }
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticError {
    pub kind: String,
    pub message: String,
}
