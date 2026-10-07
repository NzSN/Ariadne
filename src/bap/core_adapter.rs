//! Typed transport projection for the native analyzer. This module never runs
//! the Rust reference solver or constructs a native observation from it.
use super::core_protocol::Observation;
use super::core_session::{CoreConfig, CoreSession};
use super::{Error, invalid};
use crate::*;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

pub fn hex(a: Address) -> String {
    format!("0x{a:016x}")
}
fn addresses(values: &AddressSet) -> Vec<String> {
    values.iter().copied().map(hex).collect()
}
pub fn encode_request(r: &AnalysisRequest) -> Result<Value, Error> {
    r.validate()?;
    Ok(
        json!({"snapshot":r.snapshot_id,"addresses":addresses(&r.addresses),"locations":r.locations,
        "entry_points":addresses(&r.entry_points),"slice_seeds":addresses(&r.slice_seeds),
        "input_kind":match r.input_kind {InputKind::Dump=>"dump",InputKind::Binary=>"binary"},
        "captured":addresses(&r.captured),"file_backed":addresses(&r.file_backed),
        "trusted_fallback":addresses(&r.trusted_fallback),"decodable":addresses(&r.decodable),
        "instructions":r.instructions.iter().map(|(&a,i)| json!({"address":hex(a),
            "kind":match i.kind {InstructionKind::Ordinary=>"ordinary",InstructionKind::Conditional=>"conditional",
                InstructionKind::Jump=>"jump",InstructionKind::Indirect=>"indirect",InstructionKind::Call=>"call",
                InstructionKind::Return=>"return",InstructionKind::Stop=>"stop"},
            "fall":addresses(&i.fall),"targets":addresses(&i.targets),"targets_complete":i.complete,
            "uses":i.uses,"may_defs":i.may_defs,"must_defs":i.must_defs})).collect::<Vec<_>>()}),
    )
}
pub fn address(s: &str) -> Result<Address, Error> {
    if s.len() != 18
        || !s.starts_with("0x")
        || !s[2..]
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid("noncanonical native address"));
    }
    Ok(u64::from_str_radix(&s[2..], 16)?)
}
fn set(values: &[String], domain: &AddressSet) -> Result<AddressSet, Error> {
    let mut result = AddressSet::new();
    for value in values {
        let a = address(value)?;
        if !domain.contains(&a) || !result.insert(a) {
            return Err(invalid("native set duplicate/outside domain"));
        }
    }
    Ok(result)
}
pub fn decode_state(r: &AnalysisRequest, o: &Observation) -> Result<AnalysisState, Error> {
    decode_state_cached(r, o, None)
}
fn decode_state_cached(
    r: &AnalysisRequest,
    o: &Observation,
    previous: Option<(
        &BTreeMap<Address, super::core_protocol::Reaching>,
        &AnalysisState,
    )>,
) -> Result<AnalysisState, Error> {
    let phase = match o.phase.as_str() {
        "recover" => Phase::Recover,
        "dataflow" => Phase::Dataflow,
        "slice" => Phase::Slice,
        "done" => Phase::Done,
        _ => return Err(invalid("native phase")),
    };
    let pending = set(&o.pending, &r.addresses)?;
    let visited = set(&o.visited, &r.addresses)?;
    let decoded = set(&o.decoded, &visited)?;
    let slice = set(&o.slice, &decoded)?;
    if !pending.is_disjoint(&visited) {
        return Err(invalid("native pending/visited overlap"));
    }
    let mut provenance = BTreeMap::new();
    for row in &o.provenance {
        let a = address(&row.address)?;
        let source = match row.source.as_str() {
            "captured" => ByteSource::Captured,
            "file" => ByteSource::File,
            "unavailable" => ByteSource::Unavailable,
            _ => return Err(invalid("native byte source")),
        };
        if !r.addresses.contains(&a)
            || provenance.insert(a, source).is_some()
            || (decoded.contains(&a) == (source == ByteSource::Unavailable))
        {
            return Err(invalid("native provenance domain/classification"));
        }
    }
    let mut edges = EdgeSet::new();
    for row in &o.edges {
        let src = address(&row.src)?;
        let dst = address(&row.dst)?;
        let kind = match row.kind.as_str() {
            "next" => EdgeKind::Next,
            "taken" => EdgeKind::Taken,
            "fallthrough" => EdgeKind::Fallthrough,
            "jump" => EdgeKind::Jump,
            "indirect" => EdgeKind::Indirect,
            "summary" => EdgeKind::Summary,
            "call" => EdgeKind::Call,
            _ => return Err(invalid("native edge kind")),
        };
        if !decoded.contains(&src)
            || !r.addresses.contains(&dst)
            || !edges.insert(Edge { src, dst, kind })
        {
            return Err(invalid("native edge domain/duplicate"));
        }
    }
    let mut obligations = ObligationSet::new();
    for row in &o.obligations {
        let site = address(&row.site)?;
        let reason = match row.reason.as_str() {
            "unavailable" => ObligationReason::Unavailable,
            "decode-failed" => ObligationReason::DecodeFailed,
            "indirect-targets" => ObligationReason::IndirectTargets,
            "call-targets" => ObligationReason::CallTargets,
            _ => return Err(invalid("native obligation reason")),
        };
        if !visited.contains(&site) || !obligations.insert(Obligation { site, reason }) {
            return Err(invalid("native obligation domain/duplicate"));
        }
    }
    let previous = previous.filter(|(_, state)| state.decoded.is_subset(&decoded));
    let mut reaching = BTreeMap::new();
    for row in &o.reaching {
        let a = address(&row.address)?;
        let cached = previous.and_then(|(rows, state)| {
            rows.get(&a)
                .is_some_and(|old| old.definitions == row.definitions)
                .then(|| state.reaching.get(&a))
                .flatten()
        });
        let mut defs = cached.cloned().unwrap_or_default();
        for d in row.definitions.iter().filter(|_| cached.is_none()) {
            let site = address(&d.site)?;
            let origin = match d.origin.as_str() {
                "entry" => DefinitionOrigin::Entry,
                "instruction" => DefinitionOrigin::Instruction,
                _ => return Err(invalid("native definition origin")),
            };
            if !r.locations.contains(&d.loc)
                || match origin {
                    DefinitionOrigin::Entry => !r.entry_points.contains(&site),
                    DefinitionOrigin::Instruction => !decoded.contains(&site),
                }
                || !defs.insert(Definition {
                    loc: d.loc.clone(),
                    site,
                    origin,
                })
            {
                return Err(invalid("native definition identity/duplicate"));
            }
        }
        if !r.addresses.contains(&a)
            || (!decoded.contains(&a) && !defs.is_empty())
            || reaching.insert(a, defs).is_some()
        {
            return Err(invalid("native reaching domain/duplicate"));
        }
    }
    if provenance.keys().copied().collect::<BTreeSet<_>>() != r.addresses
        || reaching.keys().copied().collect::<BTreeSet<_>>() != r.addresses
    {
        return Err(invalid("native maps are not total"));
    }
    Ok(AnalysisState {
        phase,
        pending,
        visited,
        decoded,
        provenance,
        edges,
        obligations,
        reaching,
        slice,
    })
}

fn validate_attribution(
    r: &AnalysisRequest,
    state: &AnalysisState,
    rows: &[super::core_protocol::Attribution],
    evidence: &BTreeMap<String, Value>,
) -> Result<(), Error> {
    let mut ids = BTreeSet::new();
    let mut machines = BTreeSet::new();
    let mut programs = Vec::new();
    for row in rows {
        if row.term.is_empty() || !ids.insert(row.term.clone()) || row.snapshot != r.snapshot_id {
            return Err(invalid("native term identity"));
        }
        match row.origin.as_str() {
            "machine" => {
                let va = row
                    .va
                    .as_deref()
                    .ok_or_else(|| invalid("machine term lacks VA"))?;
                if !state.decoded.contains(&address(va)?)
                    || !["blk", "sub"].contains(&row.class.as_str())
                    || !row.parents.is_empty()
                    || !machines.insert((address(va)?, row.class.clone()))
                    || row.evidence.as_ref() != evidence.get(va)
                {
                    return Err(invalid("native machine term attribution"));
                }
            }
            "synthetic" if row.class == "program" && row.va.is_none() && row.evidence.is_none() => {
                programs.push(row)
            }
            _ => return Err(invalid("native term class/origin")),
        }
    }
    if machines.len() != 2 * state.decoded.len()
        || programs.len() != usize::from(!state.decoded.is_empty())
    {
        return Err(invalid("native term coverage"));
    }
    if let Some(program) = programs.first() {
        let parents: BTreeSet<_> = program.parents.iter().cloned().collect();
        let expected: BTreeSet<_> = rows
            .iter()
            .filter(|r| r.origin == "machine")
            .map(|r| r.term.clone())
            .collect();
        if parents.len() != program.parents.len() || parents != expected {
            return Err(invalid("native synthetic parent attribution"));
        }
    }
    Ok(())
}

/// Owns a single native analysis lifetime. The local state is only a validated
/// mirror of a complete response, never a separately advanced Rust analyzer.
pub struct NativeAnalyzer {
    request: AnalysisRequest,
    state: AnalysisState,
    session: CoreSession,
    actions: u64,
    evidence: BTreeMap<String, Value>,
    reaching_rows: BTreeMap<Address, super::core_protocol::Reaching>,
    closed: bool,
}
impl NativeAnalyzer {
    pub fn new(config: &CoreConfig, token: &str, request: AnalysisRequest) -> Result<Self, Error> {
        let input = encode_request(&request)?;
        Self::start(config, token, request, super::core_protocol::PROFILE, input)
    }
    fn start(
        config: &CoreConfig,
        token: &str,
        request: AnalysisRequest,
        profile: &str,
        input: Value,
    ) -> Result<Self, Error> {
        let evidence = input
            .get("capture")
            .and_then(|c| c.get("sites"))
            .and_then(Value::as_array)
            .map(|rows| {
                rows.iter()
                    .map(|r| {
                        Ok((
                            r["address"]
                                .as_str()
                                .ok_or_else(|| invalid("capture address"))?
                                .to_owned(),
                            r.clone(),
                        ))
                    })
                    .collect::<Result<BTreeMap<_, _>, Error>>()
            })
            .transpose()?
            .unwrap_or_default();
        let (session, response) =
            CoreSession::start_profile(config, token, &request.snapshot_id, profile, &input)?;
        if response.error.is_some() {
            return Err(invalid("native initialize rejected"));
        }
        let state = decode_state(&request, &response.observation)?;
        validate_attribution(&request, &state, &response.attribution, &evidence)?;
        Ok(Self {
            request,
            state,
            session,
            actions: 0,
            evidence,
            reaching_rows: response
                .observation
                .reaching
                .into_iter()
                .map(|row| Ok((address(&row.address)?, row)))
                .collect::<Result<_, Error>>()?,
            closed: false,
        })
    }
    #[cfg(feature = "input")]
    pub fn from_capture(
        config: &CoreConfig,
        token: &str,
        prepared: &crate::input::FilePreparedAnalysis,
    ) -> Result<Self, Error> {
        let request = prepared.prepared.request.clone();
        if prepared.prepared.instructions.values().any(|e| {
            e.semantic
                .as_ref()
                .is_some_and(|s| s.backend != "bap-x86-legacy")
        }) {
            return Err(invalid("capture semantics must come from pinned BAP"));
        }
        if request.input_kind != InputKind::Dump
            || !request.file_backed.is_empty()
            || !request.trusted_fallback.is_empty()
        {
            return Err(invalid("native capture input requires capture-only dump"));
        }
        let context = crate::input::investigation::capture_context(prepared)?;
        let sites = context.sites.iter().map(|s| json!({
            "address":hex(s.va), "bytes":s.bytes_hex, "captured":s.captured,
            "quality":s.quality, "status":s.semantic_status, "helper_sha256":s.helper_sha256,
            "runtime_sha256":s.runtime_sha256,"ast_sha256":s.ast_sha256,"projection":s.projection,
            "spans":s.spans.iter().map(|p| json!({"address":hex(p.va),"length":p.length,
                "contributors":p.contributors.iter().map(|c| json!({"stream":c.stream,"entry":c.entry,"file_offset":c.file_offset.to_string()})).collect::<Vec<_>>()
            })).collect::<Vec<_>>()
        })).collect::<Vec<_>>();
        let input = json!({"normalized":encode_request(&request)?, "capture":{
            "snapshot":context.snapshot_id,"artifact_sha256":context.artifact_sha256,
            "query_id":context.query_id,"semantic_profile":context.semantic_profile,"sites":sites}});
        Self::start(
            config,
            token,
            request,
            super::core_protocol::CAPTURED_PROFILE,
            input,
        )
    }
    pub fn identity(&self) -> &Value {
        self.session.identity()
    }
    /// Native process identity for external diagnostic/resource measurements.
    pub fn process_id(&self) -> u32 {
        self.session.process_id()
    }
    pub fn request(&self) -> &AnalysisRequest {
        &self.request
    }
    pub fn state(&self) -> &AnalysisState {
        &self.state
    }
    pub fn step(&mut self) -> Result<bool, Error> {
        self.step_payload(json!({}))
    }
    pub fn advance_named(&mut self, action: &str) -> Result<(), Error> {
        if !self.step_payload(json!({"action":action}))? {
            return Err(invalid("native action after done"));
        }
        Ok(())
    }
    fn step_payload(&mut self, payload: Value) -> Result<bool, Error> {
        if self.state.phase == Phase::Done {
            return Ok(false);
        }
        if self.actions >= 1_000_000 {
            return Err(invalid("native action budget exhausted"));
        }
        let response = self.session.request("step", payload)?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        let state = decode_state_cached(
            &self.request,
            &response.observation,
            Some((&self.reaching_rows, &self.state)),
        )?;
        self.reaching_rows = response
            .observation
            .reaching
            .into_iter()
            .map(|row| Ok((address(&row.address)?, row)))
            .collect::<Result<_, Error>>()?;
        self.state = state;
        validate_attribution(
            &self.request,
            &self.state,
            &response.attribution,
            &self.evidence,
        )?;
        self.actions = response.action_index;
        Ok(true)
    }
    pub fn observe(&mut self) -> Result<&AnalysisState, Error> {
        let response = self.session.request("observe", json!({}))?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        self.state = decode_state(&self.request, &response.observation)?;
        validate_attribution(
            &self.request,
            &self.state,
            &response.attribution,
            &self.evidence,
        )?;
        Ok(&self.state)
    }
    pub fn close(&mut self) -> Result<(), Error> {
        if !self.closed {
            self.session.request("reset", json!({}))?;
            self.closed = true;
        }
        Ok(())
    }
    pub fn complete(self) -> Result<CompletedAnalysis, Error> {
        let request = self.request.clone();
        let result = self.finish()?;
        Ok(CompletedAnalysis::from_native(request, result))
    }
    pub fn finish(mut self) -> Result<AnalysisResult, Error> {
        while self.step()? {}
        let response = self.session.request("finish", json!({}))?;
        if let Some(error) = response.error {
            return Err(invalid(error.message));
        }
        let state = decode_state(&self.request, &response.observation)?;
        validate_attribution(&self.request, &state, &response.attribution, &self.evidence)?;
        if state != self.state {
            return Err(invalid("native finish mutated state"));
        }
        let result = response
            .result
            .ok_or_else(|| invalid("missing native completed result"))?;
        let missing = set(
            &result
                .missing_slice_seeds
                .ok_or_else(|| invalid("missing native seed result"))?,
            &self.request.slice_seeds,
        )?;
        if missing
            != self
                .request
                .slice_seeds
                .difference(&state.decoded)
                .copied()
                .collect()
        {
            return Err(invalid("native missing seed binding"));
        }
        self.session.request("reset", json!({}))?;
        Ok(AnalysisResult {
            snapshot_id: self.request.snapshot_id,
            state,
            missing_slice_seeds: missing,
        })
    }
}

#[cfg(test)]
mod cache_tests {
    use super::*;
    #[test]
    fn reaching_cache_revalidates_changed_rows_and_shrinking_decoded_domain() {
        let request = AnalysisRequest {
            addresses: [0x10, 0x20].into(),
            locations: ["rax".into()].into(),
            entry_points: [0x10].into(),
            ..AnalysisRequest::default()
        };
        let observation: Observation = serde_json::from_value(json!({
            "phase":"dataflow","pending":[],"visited":[hex(0x10),hex(0x20)],"decoded":[hex(0x10),hex(0x20)],
            "provenance":[{"address":hex(0x10),"source":"captured"},{"address":hex(0x20),"source":"captured"}],
            "edges":[],"obligations":[],"slice":[],
            "reaching":[{"address":hex(0x10),"definitions":[]},{"address":hex(0x20),"definitions":[{"loc":"rax","site":hex(0x10),"origin":"instruction"}]}]
        })).unwrap();
        let state = decode_state(&request, &observation).unwrap();
        let rows = observation
            .reaching
            .iter()
            .cloned()
            .map(|r| (address(&r.address).unwrap(), r))
            .collect();
        let previous = Some((&rows, &state));
        assert_eq!(
            decode_state_cached(&request, &observation, previous).unwrap(),
            state
        );
        let mut changed = observation.clone();
        changed.reaching[1].definitions[0].loc = "unknown".into();
        assert!(decode_state_cached(&request, &changed, previous).is_err());
        let mut changed = observation.clone();
        let duplicate = changed.reaching[1].definitions[0].clone();
        changed.reaching[1].definitions.push(duplicate);
        assert!(decode_state_cached(&request, &changed, previous).is_err());
        let mut changed = observation.clone();
        changed.decoded.remove(0);
        changed.provenance[0].source = "unavailable".into();
        assert!(decode_state_cached(&request, &changed, previous).is_err());
        let mut changed = observation.clone();
        changed.reaching[1].definitions[0].site = hex(0x30);
        assert!(decode_state_cached(&request, &changed, previous).is_err());
    }
}
