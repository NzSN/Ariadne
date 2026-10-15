use crate::investigation::*;
use crate::{AnalysisRequest, AnalysisState, AnalysisView, Phase};
use std::collections::{BTreeMap, BTreeSet};
pub struct BoundInvestigation {
    #[cfg(feature = "bap")]
    pub(crate) composition: Option<crate::bap::composition::Report>,
    #[cfg(feature = "bap")]
    pub(crate) target_resolution: Option<crate::bap::target_resolution::Report>,
    #[cfg(feature = "bap")]
    pub(crate) guard_admission: Option<crate::bap::guard_admission::Report>,
    pub(crate) request: AnalysisRequest,
    pub(crate) state: std::sync::Arc<AnalysisState>,
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
#[cfg(feature = "bap")]
pub(crate) fn guard_assumptions(report: &crate::bap::guard_admission::Report) -> Vec<String> {
    let mut assumptions = Vec::new();
    for premise in &report.input.premises {
        assumptions.push(format!(
            "guard-premise {:?}: {} at root {} and point {}, frame {}; RSP residues 0x{:04x}; assumed or observed only at that point, never backward from the crash",
            premise.origin, premise.policy, premise.root, premise.point,
            premise.activation.frame_activation, premise.rsp_residues,
        ));
    }
    for decision in &report.guards {
        assumptions.push(format!(
            "guard-decision {}: {:?}, residue mask 0x{:04x}, residual {}; proof {}; structural paths are not executed history",
            decision.site, decision.verdict, decision.address_residues,
            decision.residual, decision.receipt_sha256,
        ));
    }
    assumptions
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
            #[cfg(feature = "bap")]
            guard_admission: None,
            #[cfg(feature = "bap")]
            composition: None,
            #[cfg(feature = "bap")]
            target_resolution: None,
            request: expected.clone(),
            state: analyzer.shared_state(),
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
        #[cfg(feature = "bap")]
        let schema_ok = match &self.guard_admission {
            Some(report) => {
                validate_guarded_explanation(self, report)?;
                if let Some(composition) = &self.composition {
                    self.schema
                        == if crate::bap::composition::is_legacy(composition) {
                            "ariadne.fault-address-explanation/v3"
                        } else {
                            "ariadne.fault-address-explanation/v4"
                        }
                } else {
                    self.schema == "ariadne.fault-address-explanation/v2"
                        && self.target_resolution.is_none()
                        && self.guard_sources.is_none()
                        && !crate::bap::composition::contains_profile(
                            &self.identity.semantic_profile,
                        )
                }
            }
            None => {
                self.schema == "ariadne.fault-address-explanation/v1"
                    && self.guard_request.is_none()
                    && self.composition.is_none()
                    && self.target_resolution.is_none()
                    && self.guard_sources.is_none()
                    && !crate::bap::composition::contains_profile(&self.identity.semantic_profile)
                    && !self
                        .identity
                        .semantic_profile
                        .contains(":bap-guard-admission-v1:")
            }
        };
        #[cfg(not(feature = "bap"))]
        let schema_ok = self.schema == "ariadne.fault-address-explanation/v1";
        if !schema_ok
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

#[cfg(feature = "bap")]
fn validate_guarded_explanation(
    explanation: &Explanation,
    report: &crate::bap::guard_admission::Report,
) -> Result<(), Error> {
    use crate::bap::guard_admission as guard;
    let normalized = explanation
        .guard_request
        .as_ref()
        .ok_or_else(|| invalid("guarded explanation normalized request absent"))?;
    let request = super::frame_paths::decode_guard_request(normalized)?;
    let (query, semantic_suffix, candidate) = super::proof_binding(
        explanation.composition.as_ref(),
        explanation.target_resolution.as_ref(),
        report,
        &request,
    )?;
    let roots: Vec<_> = request
        .entry_points
        .iter()
        .map(|a| format!("0x{a:016x}"))
        .collect();
    let seeds: Vec<_> = request
        .slice_seeds
        .iter()
        .map(|a| format!("0x{a:016x}"))
        .collect();
    if query != explanation.identity.query_id
        || report.input.snapshot != explanation.identity.snapshot_id
        || report.input.artifact_sha256 != explanation.identity.artifact_sha256
        || request.snapshot_id != explanation.identity.snapshot_id
        || request_fingerprint(&request) != explanation.identity.request_sha256
        || request.input_kind != crate::InputKind::Dump
        || !request.file_backed.is_empty()
        || !request.trusted_fallback.is_empty()
        || report
            .input
            .roots
            .iter()
            .map(|r| r.site.clone())
            .collect::<Vec<_>>()
            != roots
        || report.input.seeds != seeds
        || !explanation
            .identity
            .semantic_profile
            .ends_with(&semantic_suffix)
        || !guard_assumptions(report)
            .iter()
            .all(|p| explanation.assumptions.contains(p))
    {
        return Err(invalid(
            "guarded explanation request or premise binding changed",
        ));
    }
    let sources: BTreeMap<_, _> = report
        .input
        .sites
        .iter()
        .map(|s| Ok((crate::bap::core_adapter::address(&s.site)?, s)))
        .collect::<Result<_, Error>>()?;
    for &va in &request.decodable {
        if !sources.contains_key(&va) {
            return Err(invalid("guarded explanation decoded source absent"));
        }
    }
    for (&va, source) in &sources {
        let actual = request
            .instructions
            .get(&va)
            .ok_or_else(|| invalid("guarded explanation candidate summary absent"))?;
        if guard::recognize_pending(source)?.is_some() {
            if let Some(ast) = report.normal_selection(va) {
                let projection = crate::bap::Backend::guard_normal_projection(
                    ast,
                    "MOVAPSmr",
                    &super::frame_unwind::unhex(&source.bytes_hex)?,
                    va,
                )?;
                if projection.instruction != *actual || !request.decodable.contains(&va) {
                    return Err(invalid(
                        "guarded explanation selected normal summary changed",
                    ));
                }
            } else if actual.kind != crate::InstructionKind::Stop
                || !actual.fall.is_empty()
                || !actual.targets.is_empty()
                || actual.complete
                || !actual.must_defs.is_empty()
                || actual.uses != request.locations
                || actual.may_defs != request.locations
                || request.decodable.contains(&va)
            {
                return Err(invalid("guarded explanation unadmitted normal effects"));
            }
        } else if guard::CandidateControl::from_instruction(actual)
            != candidate
                .as_ref()
                .and_then(|r| r.instructions.get(&va))
                .map(guard::CandidateControl::from_instruction)
                .unwrap_or_else(|| source.control.clone())
        {
            return Err(invalid("guarded explanation candidate control changed"));
        }
    }
    let mut retained = BTreeMap::new();
    if let Some(composition) = &explanation.composition {
        let full = explanation
            .guard_sources
            .as_ref()
            .ok_or_else(|| invalid("composed explanation full capture sources absent"))?;
        super::validate_composition_capture(
            &explanation.identity.semantic_profile,
            composition,
            explanation
                .target_resolution
                .as_ref()
                .ok_or_else(|| invalid("composed explanation target proof absent"))?,
            report,
            full,
        )?;
        for site in full {
            if !site_valid(site) || retained.insert(site.va, site).is_some() {
                return Err(invalid(
                    "composed explanation duplicate or invalid capture source",
                ));
            }
        }
        if retained.keys().copied().collect::<BTreeSet<_>>() != request.addresses {
            return Err(invalid(
                "composed explanation capture source domain changed",
            ));
        }
        for record in &explanation.evidence {
            if retained.get(&record.instruction.va).copied() != Some(&record.instruction) {
                return Err(invalid(
                    "composed explanation evidence differs from full capture source",
                ));
            }
        }
        let premise = "FrozenCapturedControlData: covered control-data loads use the named captured bytes; target coverage is relative to that snapshot model, not historical memory stability";
        if !explanation.assumptions.iter().any(|p| p == premise) {
            return Err(invalid(
                "composed explanation captured control data premise absent",
            ));
        }
    }
    for site in retained
        .values()
        .copied()
        .chain(explanation.evidence.iter().map(|r| &r.instruction))
    {
        if !request.addresses.contains(&site.va) {
            return Err(invalid("guarded explanation evidence outside request"));
        }
        let Some(source) = sources.get(&site.va) else {
            if site.captured || !site.bytes_hex.is_empty() {
                return Err(invalid("guarded explanation captured source absent"));
            }
            continue;
        };
        if site.bytes_hex != source.bytes_hex
            || (!source.bytes_hex.is_empty()
                && (!site.captured
                    || site.ast_sha256.as_deref() != Some(sha(source.ast.as_bytes()).as_str())
                    || site.helper_sha256.as_ref() != Some(&report.input.producer.helper_sha256)
                    || site.runtime_sha256.as_ref() != Some(&report.input.producer.runtime_sha256)
                    || site.projection.as_ref() != Some(&report.input.producer.projection)))
        {
            return Err(invalid(
                "guarded explanation captured bytes or original AST changed",
            ));
        }
        if guard::recognize_pending(source)?.is_some() {
            if let Some(ast) = report.normal_selection(site.va) {
                let projection = crate::bap::Backend::guard_normal_projection(
                    ast,
                    site.opcode.as_deref().unwrap_or(""),
                    &super::frame_unwind::unhex(&source.bytes_hex)?,
                    site.va,
                )?;
                if site.quality != "external_lift"
                    || site.semantic_status.as_deref() != Some("projected")
                    || site.accesses
                        != projection
                            .memory_accesses
                            .iter()
                            .map(AddressUse::from)
                            .collect::<Vec<_>>()
                {
                    return Err(invalid(
                        "guarded explanation selected normal access changed",
                    ));
                }
            } else if site.quality != "opaque"
                || site.semantic_status.as_deref() != Some("guard-not-admitted")
                || !site.accesses.is_empty()
            {
                return Err(invalid(
                    "guarded explanation stopped guard has normal access",
                ));
            }
        }
    }
    Ok(())
}
