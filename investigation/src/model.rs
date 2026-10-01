use ariadne::effects::{MemoryAccessEvidence, MemoryAccessRole};
use serde::{Deserialize, Serialize};
pub(crate) mod va {
    use serde::{Deserialize, Deserializer, Serializer};
    pub fn serialize<S: Serializer>(n: &u64, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&format!("0x{n:016x}"))
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<u64, D::Error> {
        let s = String::deserialize(d)?;
        if s.len() != 18
            || !s.starts_with("0x")
            || !s[2..]
                .bytes()
                .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        {
            return Err(serde::de::Error::custom("noncanonical VA/bitvector"));
        }
        u64::from_str_radix(&s[2..], 16).map_err(serde::de::Error::custom)
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub query_id: String,
    pub request_sha256: String,
    pub semantic_profile: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressTerm {
    pub bank: u8,
    #[serde(with = "va")]
    pub coefficient: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressExpression {
    pub width: u16,
    pub terms: Vec<AddressTerm>,
    #[serde(with = "va")]
    pub constant: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AccessRole {
    Load,
    Store,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressUse {
    pub index: usize,
    pub role: AccessRole,
    pub access_width: u16,
    pub address_width: u16,
    pub expression: Option<AddressExpression>,
    pub address_inputs: Vec<String>,
    pub attribution: String,
    pub gaps: Vec<String>,
}
impl From<&MemoryAccessEvidence> for AddressUse {
    fn from(v: &MemoryAccessEvidence) -> Self {
        Self {
            index: v.index,
            role: match v.role {
                MemoryAccessRole::Load => AccessRole::Load,
                MemoryAccessRole::Store => AccessRole::Store,
            },
            access_width: v.access_width,
            address_width: v.address_width,
            expression: v.expression.as_ref().map(|e| AddressExpression {
                width: e.width,
                terms: e
                    .terms
                    .iter()
                    .map(|t| AddressTerm {
                        bank: t.bank,
                        coefficient: t.coefficient,
                    })
                    .collect(),
                constant: e.constant,
            }),
            address_inputs: v.address_inputs.iter().cloned().collect(),
            attribution: v.attribution.clone(),
            gaps: v.gaps.clone(),
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contributor {
    pub stream: u32,
    pub entry: usize,
    #[serde(with = "va")]
    pub file_offset: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Span {
    #[serde(with = "va")]
    pub va: u64,
    pub length: usize,
    pub contributors: Vec<Contributor>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SiteEvidence {
    #[serde(with = "va")]
    pub va: u64,
    pub bytes_hex: String,
    pub captured: bool,
    pub opcode: Option<String>,
    pub quality: String,
    pub semantic_status: Option<String>,
    pub helper_sha256: Option<String>,
    pub runtime_sha256: Option<String>,
    pub ast_sha256: Option<String>,
    pub projection: Option<String>,
    pub accesses: Vec<AddressUse>,
    pub spans: Vec<Span>,
    pub gaps: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecoveryGap {
    #[serde(with = "va")]
    pub site: u64,
    pub code: String,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EvidenceContext {
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub query_id: String,
    pub semantic_profile: String,
    pub sites: Vec<SiteEvidence>,
    pub recovery_gaps: Vec<RecoveryGap>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FaultAddressQuestion {
    #[serde(with = "va")]
    pub site: u64,
    pub memory_access: usize,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AnswerStatus {
    Explained,
    Partial,
    Unavailable,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Classification {
    Observed,
    DerivedUnderPremises,
    Unknown,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OriginKind {
    Entry,
    Instruction,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceRecord {
    pub id: String,
    pub scope_id: String,
    pub instruction: SiteEvidence,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Producer {
    #[serde(with = "va")]
    pub site: u64,
    pub origin: OriginKind,
    pub evidence_id: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OriginGroup {
    pub location: String,
    pub producers: Vec<Producer>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Assertion {
    CapturedInstruction {
        #[serde(with = "va")]
        site: u64,
    },
    AddressInputs {
        #[serde(with = "va")]
        site: u64,
        memory_access: usize,
    },
    PossibleOrigin {
        #[serde(with = "va")]
        at: u64,
        location: String,
        producer: Producer,
    },
    Dependency {
        #[serde(with = "va")]
        at: u64,
        location: String,
        producer: Producer,
    },
    Uncertainty {
        code: String,
        #[serde(with = "va")]
        site: u64,
    },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FactRecord {
    pub id: String,
    pub scope_id: String,
    pub assertion: Assertion,
    pub evidence_refs: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Claim {
    pub id: String,
    pub scope_id: String,
    pub classification: Classification,
    pub assertion: Assertion,
    pub fact_refs: Vec<String>,
    pub evidence_refs: Vec<String>,
    pub premises: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Gap {
    pub code: String,
    #[serde(with = "va")]
    pub site: u64,
    pub evidence_refs: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceRequirement {
    pub code: String,
    pub locations: Vec<String>,
    #[serde(with = "va")]
    pub site: u64,
    pub observation: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Explanation {
    pub schema: String,
    pub identity: Identity,
    pub scope_id: String,
    pub question: FaultAddressQuestion,
    pub status: AnswerStatus,
    pub address: Option<AddressUse>,
    pub origins: Vec<OriginGroup>,
    pub evidence: Vec<EvidenceRecord>,
    pub facts: Vec<FactRecord>,
    pub claims: Vec<Claim>,
    pub gaps: Vec<Gap>,
    pub evidence_requirements: Vec<EvidenceRequirement>,
    pub assumptions: Vec<String>,
    pub truncated: bool,
}
#[derive(Clone, Copy, Debug)]
pub struct ExplainLimits {
    pub max_evidence: usize,
    pub max_origin_links: usize,
    pub max_dependency_nodes: usize,
    pub max_claims: usize,
}
impl Default for ExplainLimits {
    fn default() -> Self {
        Self {
            max_evidence: 4096,
            max_origin_links: 32768,
            max_dependency_nodes: 8192,
            max_claims: 65536,
        }
    }
}
