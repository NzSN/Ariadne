use crate::*;
use ariadne::DefinitionOrigin;
use std::collections::{BTreeMap, BTreeSet};
const PREMISE: &str = "possible dependencies; historical execution is not established";
struct Builder<'a> {
    bound: &'a BoundInvestigation,
    out: Explanation,
    limits: ExplainLimits,
    evidence: BTreeMap<u64, String>,
    links: usize,
}
impl Builder<'_> {
    fn gap(&mut self, code: &str, site: u64, refs: Vec<String>) {
        if self
            .out
            .gaps
            .iter()
            .any(|g| g.code == code && g.site == site)
        {
            return;
        }
        self.out.gaps.push(Gap {
            code: code.into(),
            site,
            evidence_refs: refs,
        });
        let observation = match code {
            "entry-origin" => {
                "Provide an independently anchored earlier entry or observed input provenance for this location."
            }
            "opaque-call" => {
                "Provide captured callee evidence or an accepted callee effect/trace relation for this call."
            }
            "unknown-memory-alias" => {
                "Provide matched alias/object observations for the memory-derived value; the coarse memory cell identifies no object."
            }
            "not-reached" => {
                "Provide a justified captured entry and supported local path reaching this instruction."
            }
            "missing-capture" | "conflicting-capture" => {
                "Provide a coherent captured instruction span at the stated VA from the same investigation context."
            }
            c if c.starts_with("budget-") => {
                "Increase the stated explanation budget and rerun the same bound query; omitted facts remain unresolved."
            }
            "unsupported-address" => {
                "Provide a source-reviewed address-expression projection for this exact captured instruction and addressing mode."
            }
            _ => {
                "Provide accepted semantic or control-target evidence for this stated gap and instruction; do not infer a historical path."
            }
        };
        self.out.evidence_requirements.push(EvidenceRequirement {
            code: code.into(),
            locations: Vec::new(),
            site,
            observation: observation.into(),
        });
    }
    fn location_gap(&mut self, code: &str, site: u64, location: &str, refs: Vec<String>) {
        self.gap(code, site, refs);
        if let Some(r) = self
            .out
            .evidence_requirements
            .iter_mut()
            .find(|r| r.code == code && r.site == site)
        {
            if !r.locations.iter().any(|l| l == location) {
                r.locations.push(location.into());
                r.locations.sort();
            }
        }
    }
    fn evidence(&mut self, site: u64) -> Option<String> {
        if let Some(e) = self.evidence.get(&site) {
            return Some(e.clone());
        }
        if self.out.evidence.len() >= self.limits.max_evidence {
            self.out.truncated = true;
            self.gap("budget-evidence", site, Vec::new());
            return None;
        }
        let instruction = self.bound.sites.get(&site)?.clone();
        let key = id("evidence", &self.out.scope_id, &instruction);
        self.out.evidence.push(EvidenceRecord {
            id: key.clone(),
            scope_id: self.out.scope_id.clone(),
            instruction: instruction.clone(),
        });
        self.evidence.insert(site, key.clone());
        if instruction.captured && !instruction.bytes_hex.is_empty() {
            self.claim(
                Assertion::CapturedInstruction { site },
                Classification::Observed,
                vec![key.clone()],
            );
        }
        Some(key)
    }
    fn claim(
        &mut self,
        assertion: Assertion,
        classification: Classification,
        evidence_refs: Vec<String>,
    ) {
        if self.out.claims.len() >= self.limits.max_claims {
            self.out.truncated = true;
            self.gap("budget-claims", self.out.question.site, Vec::new());
            return;
        }
        let fact_id = id("fact", &self.out.scope_id, &(&assertion, &evidence_refs));
        if !self.out.facts.iter().any(|f| f.id == fact_id) {
            self.out.facts.push(FactRecord {
                id: fact_id.clone(),
                scope_id: self.out.scope_id.clone(),
                assertion: assertion.clone(),
                evidence_refs: evidence_refs.clone(),
            });
        }
        let fact_refs = vec![fact_id];
        let premises = if classification == Classification::DerivedUnderPremises {
            vec![
                PREMISE.into(),
                "captured-only local graph and admitted semantic summaries".into(),
            ]
        } else {
            Vec::new()
        };
        let claim_id = id(
            "claim",
            &self.out.scope_id,
            &(
                &classification,
                &assertion,
                &fact_refs,
                &evidence_refs,
                &premises,
            ),
        );
        if !self.out.claims.iter().any(|c| c.id == claim_id) {
            self.out.claims.push(Claim {
                id: claim_id,
                scope_id: self.out.scope_id.clone(),
                classification,
                assertion,
                fact_refs,
                evidence_refs,
                premises,
            });
        }
    }
    fn producers(
        &mut self,
        at: u64,
        loc: &str,
        dependency: bool,
        pending: &mut BTreeSet<u64>,
    ) -> Vec<Producer> {
        let definitions: Vec<_> = self.bound.state.reaching[&at]
            .iter()
            .filter(|d| d.loc == loc)
            .cloned()
            .collect();
        let mut result = Vec::new();
        for d in definitions {
            if self.links >= self.limits.max_origin_links {
                self.out.truncated = true;
                self.gap("budget-origin-links", at, Vec::new());
                break;
            }
            self.links += 1;
            let producer = match d.origin {
                DefinitionOrigin::Entry => {
                    self.location_gap("entry-origin", d.site, loc, Vec::new());
                    Producer {
                        site: d.site,
                        origin: OriginKind::Entry,
                        evidence_id: None,
                    }
                }
                DefinitionOrigin::Instruction => {
                    let evidence = self.evidence(d.site);
                    pending.insert(d.site);
                    let gaps = self.bound.sites[&d.site].gaps.clone();
                    for gap in gaps {
                        self.location_gap(
                            &gap,
                            d.site,
                            loc,
                            evidence.clone().into_iter().collect(),
                        );
                    }
                    if self.bound.sites[&d.site].semantic_status.as_deref()
                        == Some("opaque-call-return")
                    {
                        self.gap(
                            "opaque-call",
                            d.site,
                            evidence.clone().into_iter().collect(),
                        );
                    }
                    if self.bound.request.instructions[&d.site]
                        .uses
                        .contains("memory:any")
                    {
                        self.gap(
                            "unknown-memory-alias",
                            d.site,
                            evidence.clone().into_iter().collect(),
                        );
                    }
                    Producer {
                        site: d.site,
                        origin: OriginKind::Instruction,
                        evidence_id: evidence,
                    }
                }
            };
            let assertion = if dependency {
                Assertion::Dependency {
                    at,
                    location: loc.into(),
                    producer: producer.clone(),
                }
            } else {
                Assertion::PossibleOrigin {
                    at,
                    location: loc.into(),
                    producer: producer.clone(),
                }
            };
            self.claim(
                assertion,
                Classification::DerivedUnderPremises,
                producer.evidence_id.clone().into_iter().collect(),
            );
            result.push(producer);
        }
        if result.is_empty() {
            self.gap("no-established-origin", at, Vec::new());
        }
        result
    }
}
pub fn explain_fault_address(
    bound: &BoundInvestigation,
    question: FaultAddressQuestion,
    limits: ExplainLimits,
) -> Result<Explanation, Error> {
    if !bound.request.addresses.contains(&question.site) {
        return Err(invalid("question site is outside this query"));
    }
    let mut b = Builder {
        bound,
        limits,
        evidence: Default::default(),
        links: 0,
        out: Explanation {
            schema: "ariadne.fault-address-explanation/v1".into(),
            identity: bound.identity.clone(),
            scope_id: bound.scope.clone(),
            question: question.clone(),
            status: AnswerStatus::Unavailable,
            address: None,
            origins: Vec::new(),
            evidence: Vec::new(),
            facts: Vec::new(),
            claims: Vec::new(),
            gaps: Vec::new(),
            evidence_requirements: Vec::new(),
            assumptions: vec![
                "possible byte origins are alternatives, not jointly observed values".into(),
                "the dependency relation is not a historical execution trace".into(),
                "no object lifetime, store retirement or root cause is inferred".into(),
            ],
            truncated: false,
        },
    };
    let refs: Vec<_> = b.evidence(question.site).into_iter().collect();
    if !bound.state.decoded.contains(&question.site) {
        b.gap("not-reached", question.site, refs);
    } else if bound.sites[&question.site].accesses.is_empty() {
        b.gap("unsupported-address", question.site, refs);
    } else {
        let address = bound.sites[&question.site]
            .accesses
            .get(question.memory_access)
            .cloned()
            .ok_or_else(|| invalid("memory-access index does not exist"))?;
        b.out.address = Some(address.clone());
        b.claim(
            Assertion::AddressInputs {
                site: question.site,
                memory_access: question.memory_access,
            },
            Classification::DerivedUnderPremises,
            refs.clone(),
        );
        for gap in &address.gaps {
            b.gap(gap, question.site, refs.clone());
        }
        if address.expression.is_none() {
            b.gap("unsupported-address", question.site, refs);
        } else {
            b.out.status = AnswerStatus::Explained;
            let mut pending = BTreeSet::new();
            for loc in &address.address_inputs {
                let producers = b.producers(question.site, loc, false, &mut pending);
                b.out.origins.push(OriginGroup {
                    location: loc.clone(),
                    producers,
                });
            }
            let mut visited = BTreeSet::new();
            while let Some(site) = pending.pop_first() {
                if visited.contains(&site) {
                    continue;
                }
                if visited.len() >= limits.max_dependency_nodes {
                    b.out.truncated = true;
                    b.gap("budget-dependency-nodes", site, Vec::new());
                    break;
                }
                visited.insert(site);
                let uses: Vec<_> = bound.request.instructions[&site]
                    .uses
                    .iter()
                    .cloned()
                    .collect();
                for loc in uses {
                    b.producers(site, &loc, true, &mut pending);
                }
            }
        }
    }
    for gap in &bound.context.recovery_gaps {
        b.gap(&gap.code, gap.site, Vec::new());
    }
    for g in b.out.gaps.clone() {
        b.claim(
            Assertion::Uncertainty {
                code: g.code,
                site: g.site,
            },
            Classification::Unknown,
            g.evidence_refs,
        );
    }
    if b.out.status == AnswerStatus::Explained && (!b.out.gaps.is_empty() || b.out.truncated) {
        b.out.status = AnswerStatus::Partial;
    }
    b.out.validate()?;
    Ok(b.out)
}
