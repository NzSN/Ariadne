//! One bounded numeric hypothesis; it never changes recovery or producer facts.
use super::fault_context::{CapturedFaultContext, GPRS, validate_context, values};
use super::validate::{digest, site_valid};
use super::{
    AccessRole, BoundFaultContext, Classification, Error, FaultAddressQuestion, FaultDatum,
    FaultMetadata, Identity, SiteEvidence, id, invalid, sha,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const ZERO_ADDRESS_SCHEMA: &str = "ariadne.zero-address-assessment/v1";
pub const ZERO_ADDRESS_PROFILE: &str = "windows-amd64-av-scalar-mov-v1";
const PREMISES: [&str; 3] = [
    "captured instruction bytes and exception context are assumed contemporaneous",
    "the selected exception context is interpreted as before the ordinary memory access",
    "pinned BAP lifting and the admitted address projection are trusted; no root cause or historical path is established",
];
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AssessmentLimits {
    pub max_evidence: usize,
    pub max_claims: usize,
}
impl Default for AssessmentLimits {
    fn default() -> Self {
        Self {
            max_evidence: 32,
            max_claims: 32,
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ZeroAddressConclusion {
    ConsistentWithEvidence,
    RefutedUnderPremises,
    Unknown,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ZeroAddressEvidenceData {
    Instruction {
        instruction: SiteEvidence,
        reached: bool,
    },
    Fault {
        datum: FaultDatum,
    },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroAddressEvidence {
    pub id: String,
    pub data: ZeroAddressEvidenceData,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ZeroAddressAssertion {
    CapturedInstruction {
        #[serde(with = "super::model::va")]
        site: u64,
    },
    CapturedField {
        name: String,
        #[serde(with = "super::model::va")]
        value: u64,
    },
    ComputedAddress {
        #[serde(with = "super::model::va")]
        value: u64,
    },
    Assessment {
        conclusion: ZeroAddressConclusion,
    },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroAddressClaim {
    pub id: String,
    pub classification: Classification,
    pub assertion: ZeroAddressAssertion,
    pub evidence_refs: Vec<String>,
    pub premises: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AssessedValue {
    #[serde(with = "super::model::va")]
    pub value: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroAddressAssessment {
    pub schema: String,
    pub profile: String,
    pub identity: Identity,
    pub question: FaultAddressQuestion,
    pub context_digest: String,
    pub scope_id: String,
    pub context: FaultMetadata,
    pub limits: AssessmentLimits,
    pub inputs_complete: bool,
    pub evidence: Vec<ZeroAddressEvidence>,
    pub conclusion: ZeroAddressConclusion,
    pub evaluated_address: Option<AssessedValue>,
    pub reported_data_address: Option<AssessedValue>,
    pub used_registers: Vec<String>,
    pub claims: Vec<ZeroAddressClaim>,
    pub gaps: Vec<String>,
    pub evidence_requirements: Vec<String>,
    pub premises: Vec<String>,
    pub truncated: bool,
}
#[derive(Default)]
struct Decision {
    evaluated: Option<u64>,
    reported: Option<u64>,
    used: Vec<String>,
    gaps: BTreeSet<String>,
}
fn instruction(evidence: &[ZeroAddressEvidence]) -> Option<(&SiteEvidence, bool)> {
    evidence.iter().find_map(|e| {
        if let ZeroAddressEvidenceData::Instruction {
            instruction,
            reached,
        } = &e.data
        {
            Some((instruction, *reached))
        } else {
            None
        }
    })
}
fn fault_data(evidence: &[ZeroAddressEvidence]) -> Vec<FaultDatum> {
    evidence
        .iter()
        .filter_map(|e| {
            if let ZeroAddressEvidenceData::Fault { datum } = &e.data {
                Some(datum.clone())
            } else {
                None
            }
        })
        .collect()
}
fn guarded_prefix(bytes: &str) -> bool {
    let bytes: Vec<_> = (0..bytes.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&bytes[i..i + 2], 16).expect("validated instruction bytes"))
        .collect();
    for b in bytes {
        if [
            0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65, 0x66, 0x67,
        ]
        .contains(&b)
        {
            return true;
        }
        if !(0x40..=0x4f).contains(&b) {
            break;
        }
    }
    false
}
fn decide(
    context: &FaultMetadata,
    question: &FaultAddressQuestion,
    evidence: &[ZeroAddressEvidence],
) -> Decision {
    let mut d = Decision::default();
    d.gaps.extend(context.gaps.iter().cloned());
    let data = fault_data(evidence);
    let fields = values(&data);
    if context.platform != "windows-amd64" {
        d.gaps.insert("unsupported-platform".into());
    }
    if !context.exception_present {
        d.gaps.insert("missing-exception-stream".into());
    }
    if !context.context_supported {
        d.gaps
            .insert("missing-or-unsupported-exception-context".into());
    }
    if fields.get("code") != Some(&0xc0000005) {
        d.gaps.insert("unsupported-exception-kind".into());
    }
    if fields.get("flags").is_none_or(|f| f & !1 != 0) {
        d.gaps.insert("unsupported-exception-flags".into());
    }
    if fields.get("chain") != Some(&0) {
        d.gaps.insert("chained-or-missing-exception-record".into());
    }
    if fields.get("number_parameters").is_none_or(|n| *n < 2) {
        d.gaps.insert("missing-access-violation-parameters".into());
    }
    if fields.get("reg:rip") != Some(&question.site) {
        d.gaps.insert("missing-or-mismatched-exception-rip".into());
    }
    if fields.get("exception_location") != Some(&question.site) {
        d.gaps.insert("exception-location-mismatch".into());
    }
    let operation = fields.get("parameter:0").copied();
    if !matches!(operation, Some(0 | 1)) {
        d.gaps.insert("unsupported-access-kind".into());
    }
    if context.platform == "windows-amd64"
        && fields.get("code") == Some(&0xc0000005)
        && fields.get("number_parameters").is_some_and(|n| *n >= 2)
        && matches!(operation, Some(0 | 1))
    {
        d.reported = fields.get("parameter:1").copied();
    }
    let Some((site, reached)) = instruction(evidence) else {
        d.gaps.insert("missing-instruction-evidence".into());
        return d;
    };
    if !reached {
        d.gaps.insert("site-not-reached".into());
    }
    if !site.captured || site.bytes_hex.is_empty() {
        d.gaps.insert("missing-captured-instruction".into());
    }
    if site.semantic_status.as_deref() != Some("projected")
        || site.quality != "external_lift"
        || site.projection.as_deref() != Some("bap-bit-provenance-v2")
        || site.helper_sha256.is_none()
        || site.runtime_sha256.is_none()
        || site.ast_sha256.is_none()
    {
        d.gaps.insert("unadmitted-instruction-semantics".into());
    }
    if guarded_prefix(&site.bytes_hex) {
        d.gaps.insert("unsupported-instruction-prefix".into());
    }
    let expected = match site.opcode.as_deref() {
        Some("MOV32rm") => Some((AccessRole::Load, 32)),
        Some("MOV64rm") => Some((AccessRole::Load, 64)),
        Some("MOV32mr" | "MOV32mi") => Some((AccessRole::Store, 32)),
        Some("MOV64mr" | "MOV64mi32") => Some((AccessRole::Store, 64)),
        _ => None,
    };
    if expected.is_none() {
        d.gaps.insert("unsupported-instruction-form".into());
    }
    if site.accesses.len() != 1 {
        d.gaps.insert("missing-or-multiple-memory-accesses".into());
    }
    let Some(access) = site.accesses.get(question.memory_access) else {
        return d;
    };
    if !access.gaps.is_empty() || access.address_width != 64 {
        d.gaps.insert("unsupported-address-evidence".into());
    }
    if expected
        .as_ref()
        .is_some_and(|(role, width)| role != &access.role || *width != access.access_width)
    {
        d.gaps.insert("form-access-disagreement".into());
    }
    if operation
        != Some(if access.role == AccessRole::Load {
            0
        } else {
            1
        })
    {
        d.gaps.insert("access-kind-mismatch".into());
    }
    let Some(expression) = &access.expression else {
        d.gaps.insert("unsupported-address-expression".into());
        return d;
    };
    let mut address = expression.constant;
    for term in &expression.terms {
        let reg = GPRS[term.bank as usize];
        d.used.push(reg.into());
        if let Some(value) = fields.get(format!("reg:{reg}").as_str()) {
            address = address.wrapping_add(value.wrapping_mul(term.coefficient));
        } else {
            d.gaps.insert(format!("missing-valid-register:{reg}"));
        }
    }
    if !d.gaps.is_empty() {
        return d;
    }
    d.evaluated = Some(address);
    let end = address.checked_add(u64::from(access.access_width / 8));
    if end.is_none_or(|end| end > 0x0000800000000000) {
        d.gaps.insert("unsupported-access-range".into());
    }
    if d.reported
        .zip(end)
        .is_none_or(|(at, end)| at < address || at >= end)
    {
        d.gaps.insert("reported-data-address-mismatch".into());
    }
    d
}
fn requirement(gap: &str) -> String {
    match gap {
        g if g.starts_with("budget-")=>"Increase assessment evidence/claim limits and rerun the same bound question.".into(),
        g if g.starts_with("missing-valid-register:")=>format!("Provide a valid exception-context observation for {}; raw zero bytes or another thread context are insufficient.",g.trim_start_matches("missing-valid-register:")),
        "reported-data-address-mismatch"|"access-kind-mismatch"|"exception-location-mismatch"|"missing-or-mismatched-exception-rip"=>"Resolve the conflicting exception-site/access observations from the same capture; do not choose one source silently.".into(),
        _=>format!("Supply or qualify the missing premise for {gap} under the declared Windows scalar-MOV profile; missing evidence is not refutation."),
    }
}
fn claim(
    scope: &str,
    assertion: ZeroAddressAssertion,
    class: Classification,
    refs: Vec<String>,
) -> ZeroAddressClaim {
    let premises = if class == Classification::DerivedUnderPremises {
        PREMISES.iter().map(|s| s.to_string()).collect()
    } else {
        Vec::new()
    };
    let key = id("i5a-claim", scope, &(&assertion, &class, &refs, &premises));
    ZeroAddressClaim {
        id: key,
        classification: class,
        assertion,
        evidence_refs: refs,
        premises,
    }
}
impl ZeroAddressAssessment {
    fn construct(
        identity: Identity,
        question: FaultAddressQuestion,
        fault: CapturedFaultContext,
        context_digest: String,
        inputs_complete: bool,
        evidence_data: Vec<ZeroAddressEvidenceData>,
        limits: AssessmentLimits,
    ) -> Self {
        let scope_id = sha(&serde_json::to_vec(&(
            &identity,
            &question,
            ZERO_ADDRESS_PROFILE,
            &context_digest,
        ))
        .expect("owned identity"));
        let evidence: Vec<_> = evidence_data
            .into_iter()
            .map(|data| ZeroAddressEvidence {
                id: id("i5a-evidence", &scope_id, &data),
                data,
            })
            .collect();
        let mut decision = if inputs_complete {
            decide(&fault.metadata, &question, &evidence)
        } else {
            Decision {
                gaps: ["budget-evidence".into()].into(),
                ..Decision::default()
            }
        };
        let mut claims = Vec::new();
        for e in &evidence {
            let assertion = match &e.data {
                ZeroAddressEvidenceData::Instruction { instruction, .. }
                    if instruction.captured && !instruction.bytes_hex.is_empty() =>
                {
                    Some(ZeroAddressAssertion::CapturedInstruction {
                        site: instruction.va,
                    })
                }
                ZeroAddressEvidenceData::Fault {
                    datum: FaultDatum::Field { observation },
                } => Some(ZeroAddressAssertion::CapturedField {
                    name: observation.name.clone(),
                    value: observation.value,
                }),
                _ => None,
            };
            if let Some(a) = assertion {
                claims.push(claim(
                    &scope_id,
                    a,
                    Classification::Observed,
                    vec![e.id.clone()],
                ));
            }
        }
        let needed = claims.len() + usize::from(decision.evaluated.is_some()) + 1;
        let mut truncated = !inputs_complete;
        if needed > limits.max_claims {
            truncated = true;
            decision.gaps.insert("budget-claims".into());
            decision.evaluated = None;
            decision.reported = None;
            decision.used.clear();
            claims.truncate(limits.max_claims);
        }
        let conclusion = if !decision.gaps.is_empty() {
            ZeroAddressConclusion::Unknown
        } else if decision.evaluated == Some(0) {
            ZeroAddressConclusion::ConsistentWithEvidence
        } else {
            ZeroAddressConclusion::RefutedUnderPremises
        };
        let refs: Vec<_> = evidence.iter().map(|e| e.id.clone()).collect();
        if let Some(value) = decision.evaluated {
            claims.push(claim(
                &scope_id,
                ZeroAddressAssertion::ComputedAddress { value },
                Classification::DerivedUnderPremises,
                refs.clone(),
            ));
        }
        if claims.len() < limits.max_claims {
            claims.push(claim(
                &scope_id,
                ZeroAddressAssertion::Assessment { conclusion },
                if conclusion == ZeroAddressConclusion::Unknown {
                    Classification::Unknown
                } else {
                    Classification::DerivedUnderPremises
                },
                refs,
            ));
        }
        let gaps: Vec<_> = decision.gaps.into_iter().collect();
        Self {
            schema: ZERO_ADDRESS_SCHEMA.into(),
            profile: ZERO_ADDRESS_PROFILE.into(),
            identity,
            question,
            context_digest,
            scope_id,
            context: fault.metadata,
            limits,
            inputs_complete,
            evidence,
            conclusion,
            evaluated_address: decision.evaluated.map(|value| AssessedValue { value }),
            reported_data_address: decision.reported.map(|value| AssessedValue { value }),
            used_registers: decision.used,
            claims,
            evidence_requirements: gaps.iter().map(|g| requirement(g)).collect(),
            gaps,
            premises: PREMISES.iter().map(|s| s.to_string()).collect(),
            truncated,
        }
    }
    pub fn validate(&self) -> Result<(), Error> {
        if self.schema != ZERO_ADDRESS_SCHEMA
            || self.profile != ZERO_ADDRESS_PROFILE
            || ![
                &self.context_digest,
                &self.identity.artifact_sha256,
                &self.identity.query_id,
                &self.identity.request_sha256,
            ]
            .into_iter()
            .all(|s| digest(s))
            || self.identity.snapshot_id != self.context.snapshot_id
            || self.identity.artifact_sha256 != self.context.artifact_sha256
            || self.identity.semantic_profile.is_empty()
            || self.evidence.len() > self.limits.max_evidence
            || self.claims.len() > self.limits.max_claims
        {
            return Err(invalid("invalid zero-address assessment identity/limits"));
        }
        let sites: Vec<_> = self
            .evidence
            .iter()
            .filter_map(|e| {
                if let ZeroAddressEvidenceData::Instruction { instruction, .. } = &e.data {
                    Some(instruction)
                } else {
                    None
                }
            })
            .collect();
        if sites.len() > 1
            || self.inputs_complete && sites.len() != 1
            || sites.iter().any(|s| {
                s.va != self.question.site
                    || !site_valid(s)
                    || !s.accesses.is_empty() && self.question.memory_access >= s.accesses.len()
            })
        {
            return Err(invalid("invalid selected instruction evidence"));
        }
        let data = fault_data(&self.evidence);
        validate_context(&self.context, &data, self.inputs_complete)?;
        let fault = CapturedFaultContext {
            metadata: self.context.clone(),
            data,
        };
        if self.inputs_complete && fault.digest() != self.context_digest {
            return Err(invalid("fault context digest mismatch"));
        }
        let expected = Self::construct(
            self.identity.clone(),
            self.question.clone(),
            fault,
            self.context_digest.clone(),
            self.inputs_complete,
            self.evidence.iter().map(|e| e.data.clone()).collect(),
            self.limits,
        );
        if self != &expected {
            return Err(invalid(
                "zero-address conclusion, evidence or claims disagree with recomputed assessment",
            ));
        }
        Ok(())
    }
}
/// Assess only the selected exception instruction; all analyzer facts remain immutable.
pub fn assess_zero_address(
    bound: &BoundFaultContext,
    question: FaultAddressQuestion,
    limits: AssessmentLimits,
) -> Result<ZeroAddressAssessment, Error> {
    let site = bound
        .analysis
        .sites
        .get(&question.site)
        .ok_or_else(|| invalid("question site is outside this query"))?;
    if !site.accesses.is_empty() && question.memory_access >= site.accesses.len() {
        return Err(invalid("memory-access index does not exist"));
    }
    let mut data = vec![ZeroAddressEvidenceData::Instruction {
        instruction: site.clone(),
        reached: bound.analysis.state.decoded.contains(&question.site),
    }];
    data.extend(
        bound
            .fault
            .data
            .iter()
            .cloned()
            .map(|datum| ZeroAddressEvidenceData::Fault { datum }),
    );
    let complete = data.len() <= limits.max_evidence;
    data.truncate(limits.max_evidence);
    let result = ZeroAddressAssessment::construct(
        bound.identity().clone(),
        question,
        bound.fault.clone(),
        bound.fault.digest(),
        complete,
        data,
        limits,
    );
    result.validate()?;
    Ok(result)
}
