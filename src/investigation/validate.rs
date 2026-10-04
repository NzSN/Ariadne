use crate::investigation::*;
use crate::{AnalysisRequest, AnalysisState, AnalysisView, Phase};
use std::collections::{BTreeMap, BTreeSet};
pub struct BoundInvestigation {
    pub(crate) request: AnalysisRequest,
    pub(crate) state: AnalysisState,
    pub(crate) context: EvidenceContext,
    pub(crate) identity: Identity,
    pub(crate) scope: String,
    pub(crate) sites: BTreeMap<u64, SiteEvidence>,
}
pub fn request_fingerprint(r: &AnalysisRequest) -> String {
    let instructions:Vec<_>=r.instructions.iter().map(|(a,i)|serde_json::json!({"va":format!("0x{a:016x}"),"kind":format!("{:?}",i.kind),"fall":i.fall,"targets":i.targets,"complete":i.complete,"uses":i.uses,"may":i.may_defs,"must":i.must_defs})).collect();
    sha(&serde_json::to_vec(&serde_json::json!({"snapshot":r.snapshot_id,"addresses":r.addresses,"locations":r.locations,"entries":r.entry_points,"seeds":r.slice_seeds,"input":format!("{:?}",r.input_kind),"captured":r.captured,"file":r.file_backed,"fallback":r.trusted_fallback,"decodable":r.decodable,"instructions":instructions})).unwrap())
}
pub(crate) fn digest(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}
pub(crate) fn site_valid(site: &SiteEvidence) -> bool {
    if site.bytes_hex.len() > 30
        || site.bytes_hex.len() % 2 != 0
        || !site
            .bytes_hex
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
    {
        return false;
    }
    if [
        site.helper_sha256.as_deref(),
        site.runtime_sha256.as_deref(),
        site.ast_sha256.as_deref(),
    ]
    .into_iter()
    .flatten()
    .any(|s| !digest(s))
    {
        return false;
    }
    if !site.accesses.is_empty()
        && (site.semantic_status.as_deref() != Some("projected")
            || site.quality != "external_lift"
            || site.ast_sha256.is_none())
    {
        return false;
    }
    for (index, a) in site.accesses.iter().enumerate() {
        if a.index != index
            || ![8, 16, 32, 64, 128, 256].contains(&a.access_width)
            || a.attribution.is_empty()
        {
            return false;
        }
        if let Some(e) = &a.expression {
            if e.width != 64
                || a.address_width != 64
                || e.terms.len() > 16
                || e.terms.iter().any(|t| t.bank >= 16 || t.coefficient == 0)
                || !e.terms.windows(2).all(|w| w[0].bank < w[1].bank)
            {
                return false;
            }
            let expected: BTreeSet<String> = e
                .terms
                .iter()
                .flat_map(|t| {
                    crate::effects::RegisterView::new(t.bank, 0, 64)
                        .unwrap()
                        .reads()
                })
                .collect();
            if expected != a.address_inputs.iter().cloned().collect() {
                return false;
            }
        }
    }
    if site.captured && !site.bytes_hex.is_empty() {
        let end = site.va as u128 + (site.bytes_hex.len() / 2) as u128;
        let mut at = site.va as u128;
        for span in &site.spans {
            if at >= end {
                break;
            }
            if span.length == 0 || span.contributors.is_empty() {
                return false;
            }
            let low = span.va as u128;
            let high = low + span.length as u128;
            if low > at {
                return false;
            }
            if high > at {
                at = high.min(end);
            }
        }
        if at < end {
            return false;
        }
    }
    true
}
impl BoundInvestigation {
    pub fn new(
        analyzer: &dyn AnalysisView,
        expected: &AnalysisRequest,
        context: EvidenceContext,
    ) -> Result<Self, Error> {
        if analyzer.state().phase != Phase::Done {
            return Err(invalid("analysis is not completed"));
        }
        if analyzer.request() != expected || context.snapshot_id != expected.snapshot_id {
            return Err(invalid("prepared/analyzer query or snapshot mismatch"));
        }
        if !digest(&context.artifact_sha256)
            || !digest(&context.query_id)
            || context.semantic_profile.is_empty()
        {
            return Err(invalid("invalid investigation identity"));
        }
        let mut sites = BTreeMap::new();
        for s in &context.sites {
            if !expected.addresses.contains(&s.va)
                || !site_valid(s)
                || sites.insert(s.va, s.clone()).is_some()
            {
                return Err(invalid("invalid or duplicate investigation site evidence"));
            }
        }
        if sites.len() != expected.addresses.len() {
            return Err(invalid("investigation evidence domain mismatch"));
        }
        for &a in &expected.decodable {
            if !sites[&a].captured || sites[&a].bytes_hex.is_empty() {
                return Err(invalid("decoded instruction lacks captured evidence"));
            }
        }
        let identity = Identity {
            snapshot_id: context.snapshot_id.clone(),
            artifact_sha256: context.artifact_sha256.clone(),
            query_id: context.query_id.clone(),
            request_sha256: request_fingerprint(expected),
            semantic_profile: context.semantic_profile.clone(),
        };
        let scope = sha(&serde_json::to_vec(&identity)?);
        Ok(Self {
            request: expected.clone(),
            state: analyzer.state().clone(),
            sites,
            context,
            identity,
            scope,
        })
    }
    pub fn identity(&self) -> &Identity {
        &self.identity
    }
}
impl Explanation {
    pub fn validate(&self) -> Result<(), Error> {
        if self.schema != "ariadne.fault-address-explanation/v1"
            || self.scope_id != sha(&serde_json::to_vec(&self.identity)?)
            || ![
                &self.identity.artifact_sha256,
                &self.identity.query_id,
                &self.identity.request_sha256,
            ]
            .into_iter()
            .all(|s| digest(s))
        {
            return Err(invalid("explanation identity/schema mismatch"));
        }
        let mut evidence = BTreeSet::new();
        for e in &self.evidence {
            if e.scope_id != self.scope_id
                || !site_valid(&e.instruction)
                || e.id != id("evidence", &self.scope_id, &e.instruction)
                || !evidence.insert(e.id.clone())
            {
                return Err(invalid("invalid evidence identity"));
            }
        }
        let mut facts = BTreeMap::new();
        for f in &self.facts {
            if f.scope_id != self.scope_id
                || f.id != id("fact", &self.scope_id, &(&f.assertion, &f.evidence_refs))
                || f.evidence_refs.iter().any(|r| !evidence.contains(r))
                || facts.insert(f.id.clone(), f).is_some()
            {
                return Err(invalid("invalid or dangling fact"));
            }
        }
        let mut claims = BTreeSet::new();
        for c in &self.claims {
            if c.scope_id != self.scope_id
                || c.id
                    != id(
                        "claim",
                        &self.scope_id,
                        &(
                            &c.classification,
                            &c.assertion,
                            &c.fact_refs,
                            &c.evidence_refs,
                            &c.premises,
                        ),
                    )
                || !claims.insert(c.id.clone())
                || c.fact_refs.is_empty()
                || c.fact_refs.iter().any(|r| !facts.contains_key(r))
                || c.evidence_refs.iter().any(|r| !evidence.contains(r))
            {
                return Err(invalid("invalid or dangling claim"));
            }
            let expected = match c.assertion {
                Assertion::CapturedInstruction { .. } => Classification::Observed,
                Assertion::Uncertainty { .. } => Classification::Unknown,
                _ => Classification::DerivedUnderPremises,
            };
            if c.classification != expected
                || c.fact_refs
                    .iter()
                    .any(|r| facts[r].assertion != c.assertion)
            {
                return Err(invalid("unsupported claim classification or assertion"));
            }
            if c.classification == Classification::DerivedUnderPremises
                && !c
                    .premises
                    .iter()
                    .any(|p| p == "possible dependencies; historical execution is not established")
            {
                return Err(invalid("missing claim scope premise"));
            }
        }
        for g in &self.gaps {
            if g.evidence_refs.iter().any(|r| !evidence.contains(r)) {
                return Err(invalid("dangling gap evidence"));
            }
        }
        if (self.truncated || !self.gaps.is_empty()) && self.status == AnswerStatus::Explained {
            return Err(invalid(
                "apparently complete truncated/uncertain explanation",
            ));
        }
        if self.status == AnswerStatus::Explained
            && self
                .address
                .as_ref()
                .and_then(|a| a.expression.as_ref())
                .is_none()
        {
            return Err(invalid("explained answer has no supported address"));
        }
        if let Some(address) = &self.address {
            let site = self
                .evidence
                .iter()
                .find(|e| e.instruction.va == self.question.site)
                .ok_or_else(|| invalid("selected site lacks evidence"))?;
            if site.instruction.accesses.get(self.question.memory_access) != Some(address) {
                return Err(invalid("selected address does not match bound evidence"));
            }
        }
        let mut locations = BTreeSet::new();
        for group in &self.origins {
            if !locations.insert(&group.location)
                || self
                    .address
                    .as_ref()
                    .is_none_or(|a| !a.address_inputs.contains(&group.location))
            {
                return Err(invalid("unbound or duplicate origin location"));
            }
            for p in &group.producers {
                if !self.facts.iter().any(|f|matches!(&f.assertion,Assertion::PossibleOrigin{at,location,producer} if *at==self.question.site && location==&group.location && producer==p)) {return Err(invalid("producer lacks its origin fact"));}
            }
        }
        for group in &self.origins {
            for p in &group.producers {
                if p.evidence_id
                    .as_ref()
                    .is_some_and(|e| !evidence.contains(e))
                {
                    return Err(invalid("dangling producer evidence"));
                }
            }
        }
        Ok(())
    }
}
