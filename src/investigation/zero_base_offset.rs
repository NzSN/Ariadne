//! Encoded zero-base/nonzero-displacement assessment at one captured fault site.
use super::fault_context::{CapturedFaultContext, GPRS, validate_context, values};
use super::validate::{digest, site_valid};
use super::zero_address::{ZeroAddressEvidence, ZeroAddressEvidenceData, decide};
use super::{
    AssessedValue, BoundFaultContext, Classification, Error, FaultAddressQuestion, FaultDatum,
    FaultMetadata, Identity, SiteEvidence, ZeroAddressConclusion, id, invalid, sha,
};
use crate::llvm_mc::address_reference::{DecodedAddressReference, gpr_bank};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const ZERO_BASE_OFFSET_SCHEMA: &str = "ariadne.zero-base-offset-assessment/v1";
pub const ZERO_BASE_OFFSET_PROFILE: &str = "windows-amd64-av-scalar-mov-base-displacement-v1";
const PREMISES: [&str; 4] = [
    "captured instruction bytes and exception context are assumed contemporaneous",
    "the selected exception context is interpreted as before the ordinary memory access",
    "pinned BAP lifting and the admitted address projection are trusted",
    "the reviewed decoded base role agrees with the captured encoding and BIL; no historical null provenance, execution path or root cause is established",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroBaseOffsetLimits {
    pub max_evidence: usize,
    pub max_claims: usize,
}
impl Default for ZeroBaseOffsetLimits {
    fn default() -> Self {
        Self {
            max_evidence: 64,
            max_claims: 64,
        }
    }
}
/// The reader adapter alone constructs this question-specific owned binding.
pub struct BoundZeroBaseOffsetContext {
    fault: BoundFaultContext,
    question: FaultAddressQuestion,
    receipt: Option<DecodedAddressReference>,
}
impl BoundZeroBaseOffsetContext {
    #[cfg(feature = "input")]
    pub(crate) fn new(
        fault: BoundFaultContext,
        question: FaultAddressQuestion,
        receipt: Option<DecodedAddressReference>,
    ) -> Result<Self, Error> {
        let site = fault
            .analysis
            .sites
            .get(&question.site)
            .ok_or_else(|| invalid("question site is outside this query"))?;
        if !site.accesses.is_empty() && question.memory_access >= site.accesses.len()
            || site.accesses.is_empty() && question.memory_access != 0
        {
            return Err(invalid("memory-access index does not exist"));
        }
        if let Some(r) = &receipt {
            r.validate()?;
            if r.address != question.site
                || r.bytes_hex != site.bytes_hex
                || Some(r.opcode.as_str()) != site.opcode.as_deref()
            {
                return Err(invalid("decoded receipt belongs to another instruction"));
            }
        }
        Ok(Self {
            fault,
            question,
            receipt,
        })
    }
    pub fn identity(&self) -> &Identity {
        self.fault.identity()
    }
    pub fn question(&self) -> &FaultAddressQuestion {
        &self.question
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ZeroBaseOffsetEvidenceData {
    Instruction {
        instruction: SiteEvidence,
        reached: bool,
    },
    Fault {
        datum: FaultDatum,
    },
    DecodedAddress {
        receipt: DecodedAddressReference,
    },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroBaseOffsetEvidence {
    pub id: String,
    pub data: ZeroBaseOffsetEvidenceData,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ZeroBaseOffsetAssertion {
    CapturedInstruction {
        #[serde(with = "super::model::va")]
        site: u64,
    },
    CapturedField {
        name: String,
        #[serde(with = "super::model::va")]
        value: u64,
    },
    DecodedBase {
        register: String,
        displacement: i64,
    },
    CapturedBase {
        register: String,
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
pub struct ZeroBaseOffsetClaim {
    pub id: String,
    pub classification: Classification,
    pub assertion: ZeroBaseOffsetAssertion,
    pub evidence_refs: Vec<String>,
    pub premises: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZeroBaseOffsetAssessment {
    pub schema: String,
    pub profile: String,
    pub identity: Identity,
    pub question: FaultAddressQuestion,
    pub context_digest: String,
    pub receipt_digest: String,
    pub scope_id: String,
    pub context: FaultMetadata,
    pub limits: ZeroBaseOffsetLimits,
    pub inputs_complete: bool,
    pub evidence: Vec<ZeroBaseOffsetEvidence>,
    pub conclusion: ZeroAddressConclusion,
    pub base_register: Option<String>,
    pub base_value: Option<AssessedValue>,
    pub signed_displacement: Option<i64>,
    pub displacement_bits: Option<AssessedValue>,
    pub evaluated_address: Option<AssessedValue>,
    pub reported_data_address: Option<AssessedValue>,
    pub claims: Vec<ZeroBaseOffsetClaim>,
    pub gaps: Vec<String>,
    pub evidence_requirements: Vec<String>,
    pub premises: Vec<String>,
    pub truncated: bool,
}
fn fault_data(evidence: &[ZeroBaseOffsetEvidence]) -> Vec<FaultDatum> {
    evidence
        .iter()
        .filter_map(|e| {
            if let ZeroBaseOffsetEvidenceData::Fault { datum } = &e.data {
                Some(datum.clone())
            } else {
                None
            }
        })
        .collect()
}
fn receipt(evidence: &[ZeroBaseOffsetEvidence]) -> Option<&DecodedAddressReference> {
    evidence.iter().find_map(|e| {
        if let ZeroBaseOffsetEvidenceData::DecodedAddress { receipt } = &e.data {
            Some(receipt)
        } else {
            None
        }
    })
}
fn receipt_digest(value: Option<&DecodedAddressReference>) -> String {
    sha(&serde_json::to_vec(&value).expect("owned receipt"))
}
#[derive(Default)]
struct Decision {
    address: Option<u64>,
    reported: Option<u64>,
    base: Option<String>,
    value: Option<u64>,
    displacement: Option<i64>,
    gaps: BTreeSet<String>,
}
fn decision(
    context: &FaultMetadata,
    question: &FaultAddressQuestion,
    evidence: &[ZeroBaseOffsetEvidence],
) -> Decision {
    let numeric: Vec<_> = evidence
        .iter()
        .filter_map(|e| {
            let data = match &e.data {
                ZeroBaseOffsetEvidenceData::Instruction {
                    instruction,
                    reached,
                } => ZeroAddressEvidenceData::Instruction {
                    instruction: instruction.clone(),
                    reached: *reached,
                },
                ZeroBaseOffsetEvidenceData::Fault { datum } => ZeroAddressEvidenceData::Fault {
                    datum: datum.clone(),
                },
                ZeroBaseOffsetEvidenceData::DecodedAddress { .. } => return None,
            };
            Some(ZeroAddressEvidence {
                id: e.id.clone(),
                data,
            })
        })
        .collect();
    let admitted = decide(context, question, &numeric);
    let mut result = Decision {
        address: admitted.evaluated,
        reported: admitted.reported,
        gaps: admitted.gaps,
        ..Decision::default()
    };
    let Some(r) = receipt(evidence) else {
        result
            .gaps
            .insert("missing-decoded-address-reference".into());
        result.address = None;
        return result;
    };
    let Some(bank) = r.base.as_deref().and_then(gpr_bank) else {
        result.gaps.insert("unsupported-encoded-base".into());
        result.address = None;
        return result;
    };
    if r.index.is_some()
        || r.segment.is_some()
        || r.rip_relative
        || r.address_width != 64
        || !r.gaps.is_empty()
        || r.decoder_sha256.is_none()
        || r.target != "x86_64-pc-windows-msvc"
    {
        result
            .gaps
            .insert("unsupported-decoded-address-profile".into());
        result.address = None;
        return result;
    }
    let access = numeric.iter().find_map(|e| {
        if let ZeroAddressEvidenceData::Instruction { instruction, .. } = &e.data {
            instruction.accesses.get(question.memory_access)
        } else {
            None
        }
    });
    if access.is_none_or(|a| {
        a.access_width != u16::from(r.access_width)
            || a.address_width != u16::from(r.address_width)
            || a.expression.as_ref().is_none_or(|x| {
                x.width != 64
                    || x.terms.len() != 1
                    || x.terms[0].bank != bank
                    || x.terms[0].coefficient != 1
                    || x.constant != r.displacement as u64
            })
    }) {
        result
            .gaps
            .insert("decoded-bil-address-disagreement".into());
        result.address = None;
        return result;
    }
    let data = fault_data(evidence);
    let fields = values(&data);
    let name = GPRS[bank as usize];
    if result.gaps.is_empty() {
        result.base = Some(name.into());
        result.value = fields.get(format!("reg:{name}").as_str()).copied();
        result.displacement = Some(r.displacement);
    }
    result
}
fn claim(
    scope: &str,
    assertion: ZeroBaseOffsetAssertion,
    classification: Classification,
    evidence_refs: Vec<String>,
) -> ZeroBaseOffsetClaim {
    let premises = if classification == Classification::DerivedUnderPremises {
        PREMISES.iter().map(|p| p.to_string()).collect()
    } else {
        Vec::new()
    };
    let id = id(
        "i5b-claim",
        scope,
        &(&assertion, &classification, &evidence_refs, &premises),
    );
    ZeroBaseOffsetClaim {
        id,
        classification,
        assertion,
        evidence_refs,
        premises,
    }
}
impl ZeroBaseOffsetAssessment {
    fn construct(
        identity: Identity,
        question: FaultAddressQuestion,
        fault: CapturedFaultContext,
        digests: (String, String),
        complete: bool,
        data: Vec<ZeroBaseOffsetEvidenceData>,
        limits: ZeroBaseOffsetLimits,
    ) -> Self {
        let (context_digest, receipt_digest) = digests;
        let scope_id = sha(&serde_json::to_vec(&(
            &identity,
            &question,
            ZERO_BASE_OFFSET_SCHEMA,
            ZERO_BASE_OFFSET_PROFILE,
            &context_digest,
            &receipt_digest,
        ))
        .expect("owned scope"));
        let evidence: Vec<_> = data
            .into_iter()
            .map(|data| ZeroBaseOffsetEvidence {
                id: id("i5b-evidence", &scope_id, &data),
                data,
            })
            .collect();
        let mut d = if complete {
            decision(&fault.metadata, &question, &evidence)
        } else {
            Decision {
                gaps: ["budget-evidence".into()].into(),
                ..Decision::default()
            }
        };
        let mut claims = Vec::new();
        for e in &evidence {
            let assertion = match &e.data {
                ZeroBaseOffsetEvidenceData::Instruction { instruction, .. }
                    if instruction.captured && !instruction.bytes_hex.is_empty() =>
                {
                    Some(ZeroBaseOffsetAssertion::CapturedInstruction {
                        site: instruction.va,
                    })
                }
                ZeroBaseOffsetEvidenceData::Fault {
                    datum: FaultDatum::Field { observation },
                } => Some(ZeroBaseOffsetAssertion::CapturedField {
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
        let needed =
            claims.len() + usize::from(d.base.is_some()) * 2 + usize::from(d.address.is_some()) + 1;
        let mut truncated = !complete;
        if needed > limits.max_claims {
            truncated = true;
            d.gaps.insert("budget-claims".into());
            d.base = None;
            d.value = None;
            d.displacement = None;
            d.address = None;
            d.reported = None;
            claims.truncate(limits.max_claims);
        }
        let conclusion = if !d.gaps.is_empty() {
            ZeroAddressConclusion::Unknown
        } else if d.value == Some(0) && d.displacement.is_some_and(|n| n != 0) {
            ZeroAddressConclusion::ConsistentWithEvidence
        } else {
            ZeroAddressConclusion::RefutedUnderPremises
        };
        let refs: Vec<_> = evidence.iter().map(|e| e.id.clone()).collect();
        if let (Some(base), Some(value), Some(displacement)) = (&d.base, d.value, d.displacement) {
            claims.push(claim(
                &scope_id,
                ZeroBaseOffsetAssertion::DecodedBase {
                    register: base.clone(),
                    displacement,
                },
                Classification::DerivedUnderPremises,
                refs.clone(),
            ));
            claims.push(claim(
                &scope_id,
                ZeroBaseOffsetAssertion::CapturedBase {
                    register: base.clone(),
                    value,
                },
                Classification::DerivedUnderPremises,
                refs.clone(),
            ));
        }
        if let Some(value) = d.address {
            claims.push(claim(
                &scope_id,
                ZeroBaseOffsetAssertion::ComputedAddress { value },
                Classification::DerivedUnderPremises,
                refs.clone(),
            ));
        }
        if claims.len() < limits.max_claims {
            claims.push(claim(
                &scope_id,
                ZeroBaseOffsetAssertion::Assessment { conclusion },
                if conclusion == ZeroAddressConclusion::Unknown {
                    Classification::Unknown
                } else {
                    Classification::DerivedUnderPremises
                },
                refs,
            ));
        }
        let gaps: Vec<_> = d.gaps.into_iter().collect();
        Self { schema: ZERO_BASE_OFFSET_SCHEMA.into(), profile: ZERO_BASE_OFFSET_PROFILE.into(), identity,
            question, context_digest, receipt_digest, scope_id, context: fault.metadata, limits,
            inputs_complete: complete, evidence, conclusion, base_register: d.base,
            base_value: d.value.map(|value| AssessedValue { value }), signed_displacement: d.displacement,
            displacement_bits: d.displacement.map(|value| AssessedValue { value: value as u64 }),
            evaluated_address: d.address.map(|value| AssessedValue { value }),
            reported_data_address: d.reported.map(|value| AssessedValue { value }), claims,
            evidence_requirements: gaps.iter().map(|g| format!("Resolve {g} in the same capture/query under the declared encoded-base profile; missing evidence is not refutation.")).collect(),
            gaps, premises: PREMISES.iter().map(|p| p.to_string()).collect(), truncated }
    }
    pub fn validate(&self) -> Result<(), Error> {
        if self.schema != ZERO_BASE_OFFSET_SCHEMA
            || self.profile != ZERO_BASE_OFFSET_PROFILE
            || ![
                &self.context_digest,
                &self.receipt_digest,
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
            return Err(invalid("invalid I5b identity/limits"));
        }
        let sites: Vec<_> = self
            .evidence
            .iter()
            .filter_map(|e| {
                if let ZeroBaseOffsetEvidenceData::Instruction { instruction, .. } = &e.data {
                    Some(instruction)
                } else {
                    None
                }
            })
            .collect();
        let receipts: Vec<_> = self
            .evidence
            .iter()
            .filter_map(|e| {
                if let ZeroBaseOffsetEvidenceData::DecodedAddress { receipt } = &e.data {
                    Some(receipt)
                } else {
                    None
                }
            })
            .collect();
        if sites.len() > 1
            || receipts.len() > 1
            || self.inputs_complete && sites.len() != 1
            || sites.iter().any(|s| {
                s.va != self.question.site
                    || !site_valid(s)
                    || !s.accesses.is_empty() && self.question.memory_access >= s.accesses.len()
                    || s.accesses.is_empty() && self.question.memory_access != 0
            })
        {
            return Err(invalid("invalid I5b selected evidence"));
        }
        for r in &receipts {
            r.validate()?;
            if sites.first().is_none_or(|s| {
                s.va != r.address
                    || s.bytes_hex != r.bytes_hex
                    || s.opcode.as_deref() != Some(r.opcode.as_str())
            }) {
                return Err(invalid("I5b decoded receipt/site disagreement"));
            }
        }
        let data = fault_data(&self.evidence);
        validate_context(&self.context, &data, self.inputs_complete)?;
        let fault = CapturedFaultContext {
            metadata: self.context.clone(),
            data,
        };
        if self.inputs_complete
            && (fault.digest() != self.context_digest
                || receipt_digest(receipt(&self.evidence)) != self.receipt_digest)
        {
            return Err(invalid("I5b complete evidence digest mismatch"));
        }
        let expected = Self::construct(
            self.identity.clone(),
            self.question.clone(),
            fault,
            (self.context_digest.clone(), self.receipt_digest.clone()),
            self.inputs_complete,
            self.evidence.iter().map(|e| e.data.clone()).collect(),
            self.limits,
        );
        if self != &expected {
            return Err(invalid("I5b conclusion/claims differ from recomputation"));
        }
        Ok(())
    }
}
pub fn assess_zero_base_offset(
    bound: &BoundZeroBaseOffsetContext,
    limits: ZeroBaseOffsetLimits,
) -> Result<ZeroBaseOffsetAssessment, Error> {
    let site = &bound.fault.analysis.sites[&bound.question.site];
    let mut data = vec![ZeroBaseOffsetEvidenceData::Instruction {
        instruction: site.clone(),
        reached: bound
            .fault
            .analysis
            .state
            .decoded
            .contains(&bound.question.site),
    }];
    data.extend(
        bound
            .fault
            .fault
            .data
            .iter()
            .cloned()
            .map(|datum| ZeroBaseOffsetEvidenceData::Fault { datum }),
    );
    if let Some(r) = &bound.receipt {
        data.push(ZeroBaseOffsetEvidenceData::DecodedAddress { receipt: r.clone() });
    }
    let complete = data.len() <= limits.max_evidence;
    data.truncate(limits.max_evidence);
    let result = ZeroBaseOffsetAssessment::construct(
        bound.identity().clone(),
        bound.question.clone(),
        bound.fault.fault.clone(),
        (
            bound.fault.fault.digest(),
            receipt_digest(bound.receipt.as_ref()),
        ),
        complete,
        data,
        limits,
    );
    result.validate()?;
    Ok(result)
}
