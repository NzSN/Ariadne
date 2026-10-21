//! Exact unsigned-base plus signed-displacement arithmetic at one captured access.
use super::fault_context::{CapturedFaultContext, GPRS, validate_context, values};
use super::scalar_base_displacement::scalar_base_displacement;
use super::validate::{digest, site_valid};
use super::zero_address::{ZeroAddressEvidence, ZeroAddressEvidenceData, decide};
use super::{
    AssessedValue, BoundFaultContext, Classification, Error, FaultAddressQuestion, FaultDatum,
    FaultMetadata, Identity, SiteEvidence, ZeroAddressConclusion, id, invalid, sha,
};
use crate::llvm_mc::address_reference::DecodedAddressReference;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const ADDRESS_WRAP_SCHEMA: &str = "ariadne.address-wrap-assessment/v1";
pub const ADDRESS_WRAP_PROFILE: &str = "windows-amd64-av-scalar-mov-base-displacement-wrap-v1";
const MODULUS: i128 = 1i128 << 64;
const MAX_INPUT_EVIDENCE: usize = 46;
#[cfg(all(test, feature = "input"))]
#[path = "../../tests/investigation/address_wrap_unit.rs"]
mod unit_tests;
const PREMISES: [&str; 4] = [
    "captured instruction bytes and exception context are assumed contemporaneous",
    "the selected exception context is interpreted as before the ordinary memory access",
    "pinned BAP lifting and the admitted address projection are trusted",
    "unsigned captured base plus signed encoded displacement describes this access only; no earlier executed arithmetic, execution path, lifetime or root cause is established",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressWrapLimits {
    pub max_evidence: usize,
    pub max_claims: usize,
}
impl Default for AddressWrapLimits {
    fn default() -> Self {
        Self {
            max_evidence: 64,
            max_claims: 64,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AddressWrapKind {
    None,
    Upper,
    Lower,
}

/// An atomic conditional arithmetic bundle, not a claim of executed history.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressWrapArithmetic {
    pub base_register: String,
    pub base_value: AssessedValue,
    pub signed_displacement: i64,
    pub displacement_bits: AssessedValue,
    pub sum_before_reduction: String,
    pub wrap_kind: AddressWrapKind,
    pub effective_address: AssessedValue,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum AddressWrapEvidenceData {
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
pub struct AddressWrapEvidence {
    pub id: String,
    pub data: AddressWrapEvidenceData,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum AddressWrapAssertion {
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
    WideSum {
        sum_before_reduction: String,
    },
    WrapKind {
        wrap_kind: AddressWrapKind,
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
pub struct AddressWrapClaim {
    pub id: String,
    pub classification: Classification,
    pub assertion: AddressWrapAssertion,
    pub evidence_refs: Vec<String>,
    pub premises: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AddressWrapAssessment {
    pub schema: String,
    pub profile: String,
    pub identity: Identity,
    pub question: FaultAddressQuestion,
    pub context_digest: String,
    pub receipt_digest: String,
    pub scope_id: String,
    pub content_id: String,
    pub context: FaultMetadata,
    pub limits: AddressWrapLimits,
    pub input_evidence_count: usize,
    pub inputs_complete: bool,
    pub evidence: Vec<AddressWrapEvidence>,
    pub conclusion: ZeroAddressConclusion,
    pub arithmetic: Option<AddressWrapArithmetic>,
    pub reported_data_address: Option<AssessedValue>,
    pub claims: Vec<AddressWrapClaim>,
    pub gaps: Vec<String>,
    pub evidence_requirements: Vec<String>,
    pub premises: Vec<String>,
    pub truncated: bool,
}

/// Only the capture adapter constructs this owned, question-specific binding.
pub struct BoundAddressWrapContext {
    fault: BoundFaultContext,
    question: FaultAddressQuestion,
    receipt: Option<DecodedAddressReference>,
}

impl BoundAddressWrapContext {
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

fn fault_data(evidence: &[AddressWrapEvidence]) -> Vec<FaultDatum> {
    evidence
        .iter()
        .filter_map(|e| match &e.data {
            AddressWrapEvidenceData::Fault { datum } => Some(datum.clone()),
            _ => None,
        })
        .collect()
}

fn receipt(evidence: &[AddressWrapEvidence]) -> Option<&DecodedAddressReference> {
    evidence.iter().find_map(|e| match &e.data {
        AddressWrapEvidenceData::DecodedAddress { receipt } => Some(receipt),
        _ => None,
    })
}

fn receipt_digest(value: Option<&DecodedAddressReference>) -> String {
    sha(&serde_json::to_vec(&value).expect("owned receipt"))
}

#[derive(Default)]
struct Decision {
    arithmetic: Option<AddressWrapArithmetic>,
    reported: Option<u64>,
    gaps: BTreeSet<String>,
}

fn decision(
    context: &FaultMetadata,
    question: &FaultAddressQuestion,
    evidence: &[AddressWrapEvidence],
) -> Decision {
    let numeric: Vec<_> = evidence
        .iter()
        .filter_map(|e| {
            let data = match &e.data {
                AddressWrapEvidenceData::Instruction {
                    instruction,
                    reached,
                } => ZeroAddressEvidenceData::Instruction {
                    instruction: instruction.clone(),
                    reached: *reached,
                },
                AddressWrapEvidenceData::Fault { datum } => ZeroAddressEvidenceData::Fault {
                    datum: datum.clone(),
                },
                AddressWrapEvidenceData::DecodedAddress { .. } => return None,
            };
            Some(ZeroAddressEvidence {
                id: e.id.clone(),
                data,
            })
        })
        .collect();
    let admitted = decide(context, question, &numeric);
    let mut d = Decision {
        reported: admitted.reported,
        gaps: admitted.gaps,
        ..Decision::default()
    };
    let access = numeric.iter().find_map(|e| match &e.data {
        ZeroAddressEvidenceData::Instruction { instruction, .. } => {
            instruction.accesses.get(question.memory_access)
        }
        _ => None,
    });
    let facts = match scalar_base_displacement(receipt(evidence), access) {
        Ok(facts) => facts,
        Err(gap) => {
            d.gaps.insert(gap.into());
            return d;
        }
    };
    // Only the range and reported-byte checks follow this admission marker.
    // Earlier gaps must not turn convenient register bytes into arithmetic facts.
    let Some(admitted_ea) = admitted.evaluated else {
        return d;
    };
    let data = fault_data(evidence);
    let fields = values(&data);
    let register = GPRS[facts.bank as usize];
    let Some(&base) = fields.get(format!("reg:{register}").as_str()) else {
        d.gaps.insert(format!("missing-valid-register:{register}"));
        return d;
    };
    let sum = i128::from(base) + i128::from(facts.displacement);
    let (wrap_kind, quotient) = if sum < 0 {
        (AddressWrapKind::Lower, -1)
    } else if sum >= MODULUS {
        (AddressWrapKind::Upper, 1)
    } else {
        (AddressWrapKind::None, 0)
    };
    let ea = u64::try_from(sum - quotient * MODULUS)
        .expect("one unsigned base and signed encoded displacement reduce to u64");
    if ea != admitted_ea {
        d.gaps.insert("decoded-bil-arithmetic-disagreement".into());
        return d;
    }
    d.arithmetic = Some(AddressWrapArithmetic {
        base_register: register.into(),
        base_value: AssessedValue { value: base },
        signed_displacement: facts.displacement,
        displacement_bits: AssessedValue {
            value: facts.displacement as u64,
        },
        sum_before_reduction: sum.to_string(),
        wrap_kind,
        effective_address: AssessedValue { value: ea },
    });
    d
}

fn claim(
    scope: &str,
    assertion: AddressWrapAssertion,
    classification: Classification,
    evidence_refs: Vec<String>,
) -> AddressWrapClaim {
    let premises = if classification == Classification::DerivedUnderPremises {
        PREMISES.iter().map(|p| p.to_string()).collect()
    } else {
        Vec::new()
    };
    AddressWrapClaim {
        id: id(
            "i5c-claim",
            scope,
            &(&assertion, &classification, &evidence_refs, &premises),
        ),
        classification,
        assertion,
        evidence_refs,
        premises,
    }
}

impl AddressWrapAssessment {
    fn construct(
        identity: Identity,
        question: FaultAddressQuestion,
        fault: CapturedFaultContext,
        digests: (String, String),
        input_evidence_count: usize,
        data: Vec<AddressWrapEvidenceData>,
        limits: AddressWrapLimits,
    ) -> Self {
        let (context_digest, receipt_digest) = digests;
        let scope_id = sha(&serde_json::to_vec(&(
            &identity,
            &question,
            ADDRESS_WRAP_SCHEMA,
            ADDRESS_WRAP_PROFILE,
            &context_digest,
            &receipt_digest,
        ))
        .expect("owned scope"));
        let evidence: Vec<_> = data
            .into_iter()
            .map(|data| AddressWrapEvidence {
                id: id("i5c-evidence", &scope_id, &data),
                data,
            })
            .collect();
        let inputs_complete = evidence.len() == input_evidence_count;
        let mut d = if inputs_complete {
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
                AddressWrapEvidenceData::Instruction { instruction, .. }
                    if instruction.captured && !instruction.bytes_hex.is_empty() =>
                {
                    Some(AddressWrapAssertion::CapturedInstruction {
                        site: instruction.va,
                    })
                }
                AddressWrapEvidenceData::Fault {
                    datum: FaultDatum::Field { observation },
                } => Some(AddressWrapAssertion::CapturedField {
                    name: observation.name.clone(),
                    value: observation.value,
                }),
                _ => None,
            };
            if let Some(assertion) = assertion {
                claims.push(claim(
                    &scope_id,
                    assertion,
                    Classification::Observed,
                    vec![e.id.clone()],
                ));
            }
        }
        let needed = claims.len() + usize::from(d.arithmetic.is_some()) * 5 + 1;
        let mut truncated = !inputs_complete;
        if needed > limits.max_claims {
            truncated = true;
            d.gaps.insert("budget-claims".into());
            d.arithmetic = None;
            d.reported = None;
            claims.truncate(limits.max_claims);
        }
        let conclusion = if !d.gaps.is_empty() || d.arithmetic.is_none() {
            ZeroAddressConclusion::Unknown
        } else if d
            .arithmetic
            .as_ref()
            .is_some_and(|a| a.wrap_kind != AddressWrapKind::None)
        {
            ZeroAddressConclusion::ConsistentWithEvidence
        } else {
            ZeroAddressConclusion::RefutedUnderPremises
        };
        let refs: Vec<_> = evidence.iter().map(|e| e.id.clone()).collect();
        if let Some(a) = &d.arithmetic {
            for assertion in [
                AddressWrapAssertion::DecodedBase {
                    register: a.base_register.clone(),
                    displacement: a.signed_displacement,
                },
                AddressWrapAssertion::CapturedBase {
                    register: a.base_register.clone(),
                    value: a.base_value.value,
                },
                AddressWrapAssertion::WideSum {
                    sum_before_reduction: a.sum_before_reduction.clone(),
                },
                AddressWrapAssertion::WrapKind {
                    wrap_kind: a.wrap_kind,
                },
                AddressWrapAssertion::ComputedAddress {
                    value: a.effective_address.value,
                },
            ] {
                claims.push(claim(
                    &scope_id,
                    assertion,
                    Classification::DerivedUnderPremises,
                    refs.clone(),
                ));
            }
        }
        if claims.len() < limits.max_claims {
            claims.push(claim(
                &scope_id,
                AddressWrapAssertion::Assessment { conclusion },
                if conclusion == ZeroAddressConclusion::Unknown {
                    Classification::Unknown
                } else {
                    Classification::DerivedUnderPremises
                },
                refs,
            ));
        }
        let gaps: Vec<_> = d.gaps.into_iter().collect();
        let mut result = Self {
            schema: ADDRESS_WRAP_SCHEMA.into(),
            profile: ADDRESS_WRAP_PROFILE.into(),
            identity,
            question,
            context_digest,
            receipt_digest,
            scope_id,
            content_id: String::new(),
            context: fault.metadata,
            limits,
            input_evidence_count,
            inputs_complete,
            evidence,
            conclusion,
            arithmetic: d.arithmetic,
            reported_data_address: d.reported.map(|value| AssessedValue { value }),
            claims,
            evidence_requirements: gaps.iter().map(|g| format!("Resolve {g} in the same capture/query under the declared address-wrap profile; missing evidence is not refutation.")).collect(),
            gaps,
            premises: PREMISES.iter().map(|p| p.to_string()).collect(),
            truncated,
        };
        result.content_id = sha(&serde_json::to_vec(&result).expect("owned assessment"));
        result
    }

    pub fn validate(&self) -> Result<(), Error> {
        if self.schema != ADDRESS_WRAP_SCHEMA
            || self.profile != ADDRESS_WRAP_PROFILE
            || ![
                &self.context_digest,
                &self.receipt_digest,
                &self.scope_id,
                &self.content_id,
                &self.identity.artifact_sha256,
                &self.identity.query_id,
                &self.identity.request_sha256,
            ]
            .into_iter()
            .all(|s| digest(s))
            || self.identity.snapshot_id != self.context.snapshot_id
            || self.identity.artifact_sha256 != self.context.artifact_sha256
            || self.identity.semantic_profile.is_empty()
            || !(1..=MAX_INPUT_EVIDENCE).contains(&self.input_evidence_count)
            || self.evidence.len() != self.input_evidence_count.min(self.limits.max_evidence)
            || self.inputs_complete != (self.evidence.len() == self.input_evidence_count)
            || self.claims.len() > self.limits.max_claims
        {
            return Err(invalid("invalid I5c identity/limits/input count"));
        }
        let sites: Vec<_> = self
            .evidence
            .iter()
            .filter_map(|e| match &e.data {
                AddressWrapEvidenceData::Instruction { instruction, .. } => Some(instruction),
                _ => None,
            })
            .collect();
        let receipts: Vec<_> = self
            .evidence
            .iter()
            .filter_map(|e| match &e.data {
                AddressWrapEvidenceData::DecodedAddress { receipt } => Some(receipt),
                _ => None,
            })
            .collect();
        if sites.len() != usize::from(!self.evidence.is_empty())
            || receipts.len() > 1
            || sites.iter().any(|s| {
                s.va != self.question.site
                    || !site_valid(s)
                    || !s.accesses.is_empty() && self.question.memory_access >= s.accesses.len()
                    || s.accesses.is_empty() && self.question.memory_access != 0
            })
        {
            return Err(invalid("invalid I5c selected evidence"));
        }
        for r in &receipts {
            r.validate()?;
            if sites.first().is_none_or(|s| {
                s.va != r.address
                    || s.bytes_hex != r.bytes_hex
                    || s.opcode.as_deref() != Some(r.opcode.as_str())
            }) {
                return Err(invalid("I5c decoded receipt/site disagreement"));
            }
        }
        let data = fault_data(&self.evidence);
        validate_context(&self.context, &data, self.inputs_complete)?;
        validate_evidence_prefix(self, &data)?;
        let fault = CapturedFaultContext {
            metadata: self.context.clone(),
            data,
        };
        if self.inputs_complete
            && (fault.digest() != self.context_digest
                || receipt_digest(receipt(&self.evidence)) != self.receipt_digest)
        {
            return Err(invalid("I5c complete evidence digest mismatch"));
        }
        if let Some(a) = &self.arithmetic {
            validate_sum(&a.sum_before_reduction)?;
        }
        for c in &self.claims {
            if let AddressWrapAssertion::WideSum {
                sum_before_reduction,
            } = &c.assertion
            {
                validate_sum(sum_before_reduction)?;
            }
        }
        let expected = Self::construct(
            self.identity.clone(),
            self.question.clone(),
            fault,
            (self.context_digest.clone(), self.receipt_digest.clone()),
            self.input_evidence_count,
            self.evidence.iter().map(|e| e.data.clone()).collect(),
            self.limits,
        );
        if self != &expected {
            return Err(invalid(
                "I5c arithmetic/conclusion/claims differ from recomputation",
            ));
        }
        Ok(())
    }
}

fn validate_sum(text: &str) -> Result<(), Error> {
    if text.is_empty() || text.len() > 21 {
        return Err(invalid("invalid I5c wide integer spelling"));
    }
    let n = text
        .parse::<i128>()
        .map_err(|_| invalid("invalid I5c wide integer"))?;
    if text != n.to_string()
        || !(i128::from(i32::MIN)..=i128::from(u64::MAX) + i128::from(i32::MAX)).contains(&n)
    {
        return Err(invalid("noncanonical/out-of-profile I5c wide integer"));
    }
    Ok(())
}

/// Validate the retained prefix in the reader's physical publication order.
/// Opaque digests for omitted tails never supply arithmetic premises.
fn validate_evidence_prefix(
    value: &AddressWrapAssessment,
    data: &[FaultDatum],
) -> Result<(), Error> {
    let fields = values(data);
    if fields.get("number_parameters").is_some_and(|n| *n > 15) {
        return Err(invalid("invalid I5c exception parameter count"));
    }
    let mut order = vec!["instruction".to_string()];
    let mut count_known = true;
    if value.context.exception_present {
        order.push("record".into());
        let context_present = data.iter().any(|d| matches!(d, FaultDatum::Context { .. }));
        if context_present {
            order.push("context".into());
        }
        order.extend(
            [
                "thread_id",
                "code",
                "flags",
                "chain",
                "exception_location",
                "number_parameters",
                "context_size",
                "context_offset",
            ]
            .into_iter()
            .map(str::to_string),
        );
        let parameters = fields.get("number_parameters").copied();
        let size = fields.get("context_size").copied();
        count_known = parameters.is_some() && size.is_some();
        if let Some(n) = parameters {
            order.extend((0..n).map(|i| format!("parameter:{i}")));
        }
        if let Some(size) = size {
            if context_present != (size > 0) {
                return Err(invalid("I5c context extent/order disagreement"));
            }
            if size >= 52 {
                order.push("context_flags".into());
                let flags = fields.get("context_flags").copied();
                count_known &= flags.is_some();
                if value.context.context_supported {
                    if let Some(flags) = flags {
                        for name in GPRS.into_iter().chain(["rip", "rflags"]) {
                            let group = if ["rsp", "rip", "rflags"].contains(&name) {
                                1
                            } else {
                                2
                            };
                            if flags & group != 0 {
                                order.push(format!("reg:{name}"));
                            }
                        }
                    }
                }
            }
        }
    }
    if value.receipt_digest != receipt_digest(None) {
        order.push("receipt".into());
    }
    let labels: Vec<_> = value
        .evidence
        .iter()
        .map(|e| match &e.data {
            AddressWrapEvidenceData::Instruction { .. } => "instruction".to_string(),
            AddressWrapEvidenceData::DecodedAddress { .. } => "receipt".to_string(),
            AddressWrapEvidenceData::Fault { datum } => match datum {
                FaultDatum::Record { .. } => "record".into(),
                FaultDatum::Context { .. } => "context".into(),
                FaultDatum::Field { observation } => observation.name.clone(),
            },
        })
        .collect();
    if !order.starts_with(&labels) || count_known && value.input_evidence_count != order.len() {
        return Err(invalid("I5c evidence is not the reader-ordered prefix"));
    }
    Ok(())
}

pub fn assess_address_wrap(
    bound: &BoundAddressWrapContext,
    limits: AddressWrapLimits,
) -> Result<AddressWrapAssessment, Error> {
    // Binding validity precedes every output budget, including zero.
    validate_context(&bound.fault.fault.metadata, &bound.fault.fault.data, true)?;
    if let Some(r) = &bound.receipt {
        r.validate()?;
    }
    let site = &bound.fault.analysis.sites[&bound.question.site];
    let mut data = vec![AddressWrapEvidenceData::Instruction {
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
            .map(|datum| AddressWrapEvidenceData::Fault { datum }),
    );
    if let Some(r) = &bound.receipt {
        data.push(AddressWrapEvidenceData::DecodedAddress { receipt: r.clone() });
    }
    let count = data.len();
    data.truncate(limits.max_evidence);
    let result = AddressWrapAssessment::construct(
        bound.identity().clone(),
        bound.question.clone(),
        bound.fault.fault.clone(),
        (
            bound.fault.fault.digest(),
            receipt_digest(bound.receipt.as_ref()),
        ),
        count,
        data,
        limits,
    );
    result.validate()?;
    Ok(result)
}
