//! Experimental normalized recovery protocol; no completed-result operation.
use super::{Error, invalid};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

/// Maximum inbound response frame, including its final newline.
pub const MAX_FRAME: usize = 8 * 1024 * 1024;
/// Default outbound request budget; callers may choose another positive budget.
pub const DEFAULT_MAX_REQUEST_BYTES: usize = 8 * 1024 * 1024;
pub const CAPTURED_PROFILE: &str = "captured-fixed-input/v1";
pub const TARGET_PROFILE: &str = "captured-indirect-targets/v1";
pub const LEGACY_GUARDED_PROFILE: &str = "captured-guarded-input/v1";
pub const GUARDED_PROFILE: &str = "captured-guarded-input/v2";
pub const LEGACY_COMPOSED_PROFILE: &str = "captured-guarded-targets/v1";
pub const LEGACY_V2_COMPOSED_PROFILE: &str = "captured-guarded-targets/v2";
pub const COMPOSED_PROFILE: &str = "captured-guarded-targets/v3";
pub const PROFILE: &str = "normalized-fixed-input/v1";
pub const INPUT_PROFILES: &[&str] = &[
    PROFILE,
    CAPTURED_PROFILE,
    TARGET_PROFILE,
    LEGACY_GUARDED_PROFILE,
    LEGACY_COMPOSED_PROFILE,
    LEGACY_V2_COMPOSED_PROFILE,
    GUARDED_PROFILE,
    COMPOSED_PROFILE,
];
pub fn proof_profile(profile: &str) -> bool {
    INPUT_PROFILES[2..].contains(&profile)
}
pub fn guarded_profile(profile: &str) -> bool {
    proof_profile(profile) && profile != TARGET_PROFILE
}

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
pub(crate) const MAX_BITMAP_WORDS: usize = 32 * 1024 * 1024;

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
    // Resolution receipts contain ordered edge words and repeated booleans.
    // Their strict validator owns set uniqueness; never reorder proof sequences.
    let canonical = if proof_profile(profile) {
        input.to_string()
    } else {
        normalize(input)?.to_string()
    };
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

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct DictionaryReaching {
    address: String,
    definitions_ref: usize,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct DictionaryObservation {
    phase: String,
    pending: Vec<String>,
    visited: Vec<String>,
    decoded: Vec<String>,
    provenance: Vec<Provenance>,
    edges: Vec<Edge>,
    obligations: Vec<Obligation>,
    slice: Vec<String>,
    reaching: Vec<DictionaryReaching>,
    definition_dictionary: Vec<DefinitionRow>,
    definition_sets: Vec<Vec<usize>>,
}
impl DictionaryObservation {
    pub(crate) fn expand(self) -> Result<Observation, Error> {
        use std::collections::BTreeSet;
        let mut dictionary = BTreeSet::new();
        for d in &self.definition_dictionary {
            if !dictionary.insert((&d.loc, &d.site, &d.origin)) {
                return Err(invalid("duplicate completed definition"));
            }
        }
        let mut sets = BTreeSet::new();
        for set in &self.definition_sets {
            if !sets.insert(set)
                || set.windows(2).any(|w| w[0] >= w[1])
                || set.iter().any(|n| *n >= self.definition_dictionary.len())
            {
                return Err(invalid("invalid completed definition set"));
            }
        }
        let mut links = 0usize;
        for row in &self.reaching {
            let set = self
                .definition_sets
                .get(row.definitions_ref)
                .ok_or_else(|| invalid("completed set index"))?;
            links = links
                .checked_add(set.len())
                .filter(|n| *n <= 16 * 1024 * 1024)
                .ok_or_else(|| invalid("expanded completed definition budget"))?;
        }
        let reaching = self
            .reaching
            .into_iter()
            .map(|row| Reaching {
                address: row.address,
                definitions: self.definition_sets[row.definitions_ref]
                    .iter()
                    .map(|n| self.definition_dictionary[*n].clone())
                    .collect(),
            })
            .collect();
        Ok(Observation {
            phase: self.phase,
            pending: self.pending,
            visited: self.visited,
            decoded: self.decoded,
            provenance: self.provenance,
            edges: self.edges,
            obligations: self.obligations,
            reaching,
            slice: self.slice,
        })
    }
}

/// Completion-only lossless membership. This representation is admitted under
/// physical storage limits and never expanded into a vector per logical link.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct BitmapObservation {
    phase: String,
    pending: Vec<String>,
    visited: Vec<String>,
    decoded: Vec<String>,
    provenance: Vec<Provenance>,
    edges: Vec<Edge>,
    obligations: Vec<Obligation>,
    slice: Vec<String>,
    reaching: Vec<DictionaryReaching>,
    definition_dictionary: Vec<DefinitionRow>,
    definition_bitmaps: Vec<String>,
}
pub(crate) struct BitmapMembership {
    rows: Vec<DictionaryReaching>,
    dictionary: Vec<DefinitionRow>,
    bitmaps: Vec<String>,
}
impl BitmapObservation {
    pub(crate) fn split(self) -> (Observation, BitmapMembership) {
        let reaching = self
            .reaching
            .iter()
            .map(|r| Reaching {
                address: r.address.clone(),
                definitions: vec![],
            })
            .collect();
        (
            Observation {
                phase: self.phase,
                pending: self.pending,
                visited: self.visited,
                decoded: self.decoded,
                provenance: self.provenance,
                edges: self.edges,
                obligations: self.obligations,
                slice: self.slice,
                reaching,
            },
            BitmapMembership {
                rows: self.reaching,
                dictionary: self.definition_dictionary,
                bitmaps: self.definition_bitmaps,
            },
        )
    }
}
impl BitmapMembership {
    pub(crate) fn bind(
        self,
        request: &crate::AnalysisRequest,
        state: &mut crate::AnalysisState,
    ) -> Result<(), Error> {
        use crate::{Definition, DefinitionOrigin, DefinitionSet};
        use std::collections::{BTreeSet, HashSet};
        use std::sync::Arc;
        if self.dictionary.len() > 1_000_000
            || self.rows.len() != request.addresses.len()
            || self.bitmaps.len() > self.rows.len()
        {
            return Err(invalid("compact definition universe/domain budget"));
        }
        let words = self.dictionary.len().div_ceil(64);
        if self
            .dictionary
            .iter()
            .try_fold(0usize, |n, d| n.checked_add(d.loc.len()))
            .is_none_or(|n| n > 64 * 1024 * 1024)
        {
            return Err(invalid("compact definition bytes budget"));
        }
        if words
            .checked_mul(self.rows.len())
            .is_none_or(|n| n > MAX_BITMAP_WORDS)
        {
            return Err(invalid("compact bitmap budget"));
        }
        let universe = self
            .dictionary
            .into_iter()
            .map(|d| {
                Ok(Definition {
                    loc: d.loc,
                    site: super::core_adapter::address(&d.site)?,
                    origin: match d.origin.as_str() {
                        "entry" => DefinitionOrigin::Entry,
                        "instruction" => DefinitionOrigin::Instruction,
                        _ => return Err(invalid("compact definition origin")),
                    },
                })
            })
            .collect::<Result<Vec<_>, Error>>()?;
        if universe.windows(2).any(|w| w[0] >= w[1]) {
            return Err(invalid("compact definition order/duplicate"));
        }
        let mut expected = BTreeSet::new();
        let mut expected_bytes = 0usize;
        for &a in &state.decoded {
            for loc in &request.instructions[&a].may_defs {
                expected_bytes = expected_bytes
                    .checked_add(loc.len())
                    .filter(|n| *n <= 64 * 1024 * 1024)
                    .ok_or_else(|| invalid("compact expected definition bytes budget"))?;
                expected.insert(Definition {
                    loc: loc.clone(),
                    site: a,
                    origin: DefinitionOrigin::Instruction,
                });
            }
            if request.entry_points.contains(&a) {
                for loc in &request.locations {
                    expected_bytes = expected_bytes
                        .checked_add(loc.len())
                        .filter(|n| *n <= 64 * 1024 * 1024)
                        .ok_or_else(|| invalid("compact expected definition bytes budget"))?;
                    expected.insert(Definition {
                        loc: loc.clone(),
                        site: a,
                        origin: DefinitionOrigin::Entry,
                    });
                }
            }
            if expected.len() > 1_000_000 {
                return Err(invalid("compact expected universe budget"));
            }
        }
        if !expected.iter().eq(universe.iter()) {
            return Err(invalid("compact definition universe binding"));
        }
        let universe: Arc<[Definition]> = universe.into();
        let mut unique = HashSet::new();
        let mut sets = Vec::with_capacity(self.bitmaps.len());
        for text in &self.bitmaps {
            if text.len() != universe.len().div_ceil(4) || !unique.insert(text) {
                return Err(invalid("compact bitmap size/duplicate"));
            }
            let mut membership = vec![0u64; words];
            for (n, byte) in text.bytes().enumerate() {
                let value = match byte {
                    b'0'..=b'9' => byte - b'0',
                    b'a'..=b'f' => byte - b'a' + 10,
                    _ => return Err(invalid("noncanonical compact membership")),
                };
                let offset = n * 4;
                if offset + 4 > universe.len() && u64::from(value) >> (universe.len() - offset) != 0
                {
                    return Err(invalid("compact membership padding"));
                }
                membership[offset / 64] |= u64::from(value) << (offset % 64);
            }
            sets.push(DefinitionSet::from_dense(universe.clone(), membership));
        }
        for row in self.rows {
            let address = super::core_adapter::address(&row.address)?;
            let set = sets
                .get(row.definitions_ref)
                .ok_or_else(|| invalid("compact set index"))?;
            if !state.reaching.contains_key(&address)
                || (!state.decoded.contains(&address) && !set.is_empty())
            {
                return Err(invalid("compact reaching domain"));
            }
            state.reaching.insert(address, set.clone());
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "../../tests/bap/completion_dictionary_unit.rs"]
mod dictionary_tests;
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
