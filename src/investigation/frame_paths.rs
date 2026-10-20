//! Bounded structural alternatives between validated captured activations.
use super::{BoundInvestigation, CapturedFrameChain, Error, Identity, SiteEvidence, invalid, sha};
use crate::{EdgeKind, InstructionKind};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;
pub const FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v1";
pub const LEGACY_GUARDED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v2";
pub const GUARDED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v5";
pub const LEGACY_COMPOSED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v3";
pub const LEGACY_V2_COMPOSED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v4";
pub const COMPOSED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v6";
pub const LIMITED_FRAME_PATH_SCHEMA: &str = "ariadne.frame-paths/v7";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathQuestion {
    pub from_frame: usize,
    pub to_frame: usize,
    pub np: usize,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathLimits {
    pub max_graph_nodes: usize,
    pub max_graph_edges: usize,
    pub max_search_states: usize,
    pub max_scanned_edges: usize,
    pub max_path_steps: usize,
    pub max_node_visits: usize,
    pub max_frontier_bytes: usize,
    pub max_output_bytes: usize,
    pub deadline_ms: u64,
}
impl Default for FramePathLimits {
    fn default() -> Self {
        Self {
            max_graph_nodes: 8192,
            max_graph_edges: 32768,
            max_search_states: 4096,
            max_scanned_edges: 16384,
            max_path_steps: 256,
            max_node_visits: 2,
            max_frontier_bytes: 4 * 1024 * 1024,
            max_output_bytes: 4 * 1024 * 1024,
            deadline_ms: 1000,
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FramePathEdgeKind {
    Next,
    Taken,
    Fallthrough,
    Jump,
    Indirect,
    Summary,
    Call,
}
impl From<EdgeKind> for FramePathEdgeKind {
    fn from(k: EdgeKind) -> Self {
        match k {
            EdgeKind::Next => Self::Next,
            EdgeKind::Taken => Self::Taken,
            EdgeKind::Fallthrough => Self::Fallthrough,
            EdgeKind::Jump => Self::Jump,
            EdgeKind::Indirect => Self::Indirect,
            EdgeKind::Summary => Self::Summary,
            EdgeKind::Call => Self::Call,
        }
    }
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathNode {
    pub frame: usize,
    #[serde(with = "super::model::va")]
    pub site: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathEdge {
    pub src: FramePathNode,
    pub dst: FramePathNode,
    pub kind: FramePathEdgeKind,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct GraphNode {
    evidence: SiteEvidence,
    call: bool,
    #[serde(with = "super::frame_unwind::address_list")]
    fall: Vec<u64>,
    #[serde(with = "super::frame_unwind::address_list")]
    targets: Vec<u64>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct FrameGraph {
    frame: usize,
    identity: Identity,
    #[serde(with = "super::model::va")]
    entry: u64,
    nodes: Vec<GraphNode>,
    edges: Vec<FramePathEdge>,
    gaps: Vec<String>,
    #[cfg(feature = "bap")]
    #[serde(default, skip_serializing_if = "Option::is_none")]
    guard_admission: Option<GuardFrameEvidence>,
}
#[cfg(feature = "bap")]
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct GuardFrameEvidence {
    report: crate::bap::guard_admission::Report,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    composition: Option<crate::bap::composition::Report>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    target_resolution: Option<crate::bap::target_resolution::Report>,
    normalized: serde_json::Value,
    sites: Vec<SiteEvidence>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    chain: CapturedFrameChain,
    graphs: Vec<FrameGraph>,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "graph_limits"
    )]
    graph_limits: Option<FramePathGraphLimits>,
}
/// Aggregate graph admission bounds, independent of path-search restrictions.
/// Saved-report consumers supply these separately from the retained source policy.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathGraphLimits {
    pub max_graph_nodes: usize,
    pub max_graph_edges: usize,
}
impl Default for FramePathGraphLimits {
    fn default() -> Self {
        Self::from(&FramePathLimits::default())
    }
}
impl From<&FramePathLimits> for FramePathGraphLimits {
    fn from(limits: &FramePathLimits) -> Self {
        Self {
            max_graph_nodes: limits.max_graph_nodes,
            max_graph_edges: limits.max_graph_edges,
        }
    }
}
fn graph_limits<'de, D: serde::Deserializer<'de>>(
    d: D,
) -> Result<Option<FramePathGraphLimits>, D::Error> {
    FramePathGraphLimits::deserialize(d).map(Some)
}
pub struct BoundFramePaths {
    input: Input,
}

fn call_target(node: &GraphNode, return_pc: u64) -> Option<u64> {
    captured_call_target(
        &node.evidence,
        node.call,
        &node.fall,
        &node.targets,
        return_pc,
    )
}
pub(crate) fn captured_call_target(
    s: &SiteEvidence,
    call: bool,
    fall: &[u64],
    targets: &[u64],
    return_pc: u64,
) -> Option<u64> {
    if !call
        || !s.captured
        || !super::validate::site_valid(s)
        || s.bytes_hex.len() != 10
        || !s.bytes_hex.starts_with("e8")
    {
        return None;
    }
    let b = super::frame_unwind::unhex(&s.bytes_hex).ok()?;
    let next = s.va.checked_add(5)?;
    let target = next.wrapping_add_signed(i64::from(i32::from_le_bytes(b[1..5].try_into().ok()?)));
    (next == return_pc && fall == [next] && targets == [target]).then_some(target)
}
/// Entry of a leaf activation is supplied only by its verified active direct call.
pub fn active_frame_entry(
    chain: &CapturedFrameChain,
    child: usize,
    parent: &BoundInvestigation,
) -> Result<u64, Error> {
    chain.validate()?;
    let younger = chain
        .frames
        .get(child)
        .ok_or_else(|| invalid("child frame outside chain"))?;
    let older = chain
        .frames
        .get(child + 1)
        .ok_or_else(|| invalid("caller frame unavailable"))?;
    if parent.identity.snapshot_id != chain.snapshot_id
        || parent.identity.artifact_sha256 != chain.artifact_sha256
    {
        return Err(invalid("caller query belongs to another snapshot"));
    }
    let candidates: Vec<_> = parent
        .state
        .decoded
        .iter()
        .filter_map(|site| {
            let i = &parent.request.instructions[site];
            let n = GraphNode {
                evidence: parent.sites.get(site)?.clone(),
                call: i.kind == InstructionKind::Call,
                fall: i.fall.iter().copied().collect(),
                targets: i.targets.iter().copied().collect(),
            };
            call_target(&n, older.pc)
                .filter(|target| younger.function_begin.is_none_or(|begin| begin == *target))
        })
        .collect();
    if candidates.len() != 1 {
        return Err(invalid("missing-or-ambiguous-active-direct-call"));
    }
    Ok(candidates[0])
}
pub fn bind_frame_paths(
    chain: CapturedFrameChain,
    analyses: Vec<(usize, BoundInvestigation)>,
) -> Result<BoundFramePaths, Error> {
    bind_frame_paths_inner(chain, analyses, None)
}
/// Bind under explicit graph admission bounds, retained separately from search
/// restrictions in a v7 source. The default binder and legacy wire stay unchanged.
pub fn bind_frame_paths_with_limits(
    chain: CapturedFrameChain,
    analyses: Vec<(usize, BoundInvestigation)>,
    limits: &FramePathLimits,
) -> Result<BoundFramePaths, Error> {
    bind_frame_paths_inner(chain, analyses, Some(FramePathGraphLimits::from(limits)))
}
fn bind_frame_paths_inner(
    chain: CapturedFrameChain,
    analyses: Vec<(usize, BoundInvestigation)>,
    graph_policy: Option<FramePathGraphLimits>,
) -> Result<BoundFramePaths, Error> {
    chain.validate()?;
    let limits = graph_policy.unwrap_or_default();
    let mut graphs = Vec::new();
    let mut count = 0usize;
    let mut edge_count = 0usize;
    if analyses.len() > 64 {
        return Err(invalid("frame graph count budget"));
    }
    for (frame, bound) in analyses {
        let f = chain
            .frames
            .get(frame)
            .ok_or_else(|| invalid("graph frame outside recovered chain"))?;
        if bound.identity.snapshot_id != chain.snapshot_id
            || bound.identity.artifact_sha256 != chain.artifact_sha256
            || bound.request.entry_points.len() != 1
        {
            return Err(invalid("frame graph identity or root mismatch"));
        }
        let entry = *bound.request.entry_points.first().expect("one root");
        if f.function_begin.is_some_and(|begin| begin != entry) {
            return Err(invalid("graph entry disagrees with frame function"));
        }
        count = count
            .checked_add(bound.state.decoded.len())
            .filter(|v| *v <= limits.max_graph_nodes)
            .ok_or_else(|| invalid("frame graph admission node budget"))?;
        edge_count = edge_count
            .checked_add(bound.state.edges.len())
            .filter(|v| *v <= limits.max_graph_edges)
            .ok_or_else(|| invalid("frame graph admission edge budget"))?;
        #[cfg(feature = "bap")]
        let guard_admission = bound
            .guard_admission
            .as_ref()
            .map(|report| {
                let normalized = crate::bap::core_adapter::encode_request(&bound.request)?;
                let (query, _, _) = super::proof_binding(
                    bound.composition.as_ref(),
                    if bound.composition.is_some() {
                        bound.target_resolution.as_ref()
                    } else {
                        None
                    },
                    report,
                    &bound.request,
                )?;
                if query != bound.identity.query_id {
                    return Err(invalid(
                        "guarded frame query differs from original bound request",
                    ));
                }
                Ok(GuardFrameEvidence {
                    report: report.clone(),
                    composition: bound.composition.clone(),
                    target_resolution: if bound.composition.is_some() {
                        bound.target_resolution.clone()
                    } else {
                        None
                    },
                    normalized,
                    sites: bound.context.sites.clone(),
                })
            })
            .transpose()?;
        let in_function = |site: u64| {
            f.function_begin.is_none_or(|b| site >= b) && f.function_end.is_none_or(|e| site < e)
        };
        let nodes = bound
            .state
            .decoded
            .iter()
            .filter(|site| in_function(**site))
            .map(|site| {
                let i = &bound.request.instructions[site];
                Ok(GraphNode {
                    evidence: bound
                        .sites
                        .get(site)
                        .ok_or_else(|| invalid("frame node evidence missing"))?
                        .clone(),
                    call: i.kind == InstructionKind::Call,
                    fall: i.fall.iter().copied().collect(),
                    targets: i.targets.iter().copied().collect(),
                })
            })
            .collect::<Result<Vec<_>, Error>>()?;
        let edges = bound
            .state
            .edges
            .iter()
            .filter(|e| {
                e.kind.is_local()
                    && bound.state.decoded.contains(&e.src)
                    && bound.state.decoded.contains(&e.dst)
                    && in_function(e.src)
                    && in_function(e.dst)
            })
            .map(|e| FramePathEdge {
                src: FramePathNode { frame, site: e.src },
                dst: FramePathNode { frame, site: e.dst },
                kind: e.kind.into(),
            })
            .collect();
        let mut gaps: Vec<_> = bound
            .context
            .recovery_gaps
            .iter()
            .map(|g| format!("0x{:016x}:{}", g.site, g.code))
            .collect();
        gaps.extend(bound.state.obligations.iter().map(|g| format!("{:?}", g)));
        if bound
            .state
            .edges
            .iter()
            .any(|e| e.kind.is_local() && in_function(e.src) && !in_function(e.dst))
        {
            gaps.push("local-edge-outside-frame-function".into());
        }
        #[cfg(feature = "bap")]
        if guard_admission.as_ref().is_some_and(|e| {
            e.composition.is_some() || !crate::bap::guard_admission::is_legacy(&e.report)
        }) {
            // Reuse the already completed analysis. Published coverage gaps
            // are core recovery facts, rather than caller-editable context.
            gaps = recovered_frame_graph(frame, f, &bound.request, &bound.state).gaps;
        }
        graphs.push(FrameGraph {
            frame,
            identity: bound.identity,
            entry,
            nodes,
            edges,
            gaps,
            #[cfg(feature = "bap")]
            guard_admission,
        });
    }
    graphs.sort_by_key(|g| g.frame);
    let input = Input {
        chain,
        graphs,
        graph_limits: graph_policy,
    };
    validate_input(&input)?;
    Ok(BoundFramePaths { input })
}
fn validate_input(input: &Input) -> Result<(), Error> {
    // Legacy v1 treats profiles as supplied premises in builds without BAP.
    // Explicit-policy v7 must not lose proof checks under the same schema.
    #[cfg(not(feature = "bap"))]
    if input.graph_limits.is_some()
        && input.graphs.iter().any(|graph| {
            [
                "bap-guard-admission-v1",
                "bap-guard-admission-v2",
                "captured-guarded-targets/v1",
                "captured-guarded-targets/v2",
                "captured-guarded-targets/v3",
            ]
            .iter()
            .any(|profile| graph.identity.semantic_profile.contains(profile))
        })
    {
        return Err(invalid(
            "explicit frame graph proof profile requires bap feature",
        ));
    }
    input.chain.validate()?;
    let limits = input.graph_limits.unwrap_or_default();
    let mut frames = BTreeSet::new();
    let mut total = 0usize;
    let mut edges = 0usize;
    for g in &input.graphs {
        let f = input
            .chain
            .frames
            .get(g.frame)
            .ok_or_else(|| invalid("invalid graph frame"))?;
        total = total
            .checked_add(g.nodes.len())
            .ok_or_else(|| invalid("frame node count overflow"))?;
        edges = edges
            .checked_add(g.edges.len())
            .ok_or_else(|| invalid("frame edge count overflow"))?;
        if !frames.insert(g.frame)
            || total > limits.max_graph_nodes
            || edges > limits.max_graph_edges
            || g.identity.snapshot_id != input.chain.snapshot_id
            || g.identity.artifact_sha256 != input.chain.artifact_sha256
            || !super::validate::digest(&g.identity.query_id)
            || !super::validate::digest(&g.identity.request_sha256)
            || f.function_begin.is_some_and(|v| v != g.entry)
        {
            return Err(invalid("frame graph identity/size invalid"));
        }
        #[cfg(feature = "bap")]
        validate_guarded_graph(&input.chain, g)?;
        let nodes: BTreeSet<_> = g.nodes.iter().map(|n| n.evidence.va).collect();
        if nodes.len() != g.nodes.len()
            || g.nodes.iter().any(|n| {
                !n.evidence.captured
                    || !super::validate::site_valid(&n.evidence)
                    || f.function_begin.is_some_and(|b| n.evidence.va < b)
                    || f.function_end.is_some_and(|e| {
                        u128::from(n.evidence.va) + (n.evidence.bytes_hex.len() / 2) as u128
                            > u128::from(e)
                    })
            })
            || g.edges.iter().any(|e| {
                e.src.frame != g.frame
                    || e.dst.frame != g.frame
                    || e.kind == FramePathEdgeKind::Call
                    || !nodes.contains(&e.src.site)
                    || !nodes.contains(&e.dst.site)
            })
            || g.edges.iter().collect::<BTreeSet<_>>().len() != g.edges.len()
        {
            return Err(invalid("invalid frame graph evidence/edges"));
        }
    }
    Ok(())
}

#[cfg(feature = "bap")]
fn validate_guarded_graph(chain: &CapturedFrameChain, graph: &FrameGraph) -> Result<(), Error> {
    validate_guarded_graph_inner(chain, graph, false)
}
#[cfg(feature = "bap")]
fn validate_guarded_graph_inner(
    chain: &CapturedFrameChain,
    graph: &FrameGraph,
    structural: bool,
) -> Result<(), Error> {
    use crate::bap::guard_admission as guard;
    let Some(evidence) = &graph.guard_admission else {
        if [guard::LEGACY_PROFILE, guard::PROFILE]
            .iter()
            .any(|profile| graph.identity.semantic_profile.contains(profile))
            || crate::bap::composition::contains_profile(&graph.identity.semantic_profile)
        {
            return Err(invalid("guarded frame graph has no proof sources"));
        }
        return Ok(());
    };
    let report = &evidence.report;
    let input = &report.input;
    let normalized_request = decode_guard_request(&evidence.normalized)?;
    super::validate_normal_flow_sources(report, &normalized_request, &evidence.sites)?;
    if evidence.composition.is_none() && !guard::is_legacy(report) {
        super::validate_guard_capture(&graph.identity.semantic_profile, report, &evidence.sites)?;
    }

    let frame = &chain.frames[graph.frame];
    let (query, semantic_suffix, candidate) = super::proof_binding(
        evidence.composition.as_ref(),
        evidence.target_resolution.as_ref(),
        report,
        &normalized_request,
    )?;
    if let Some(composition) = &evidence.composition {
        super::validate_composition_capture(
            &graph.identity.semantic_profile,
            composition,
            evidence
                .target_resolution
                .as_ref()
                .expect("validated paired target proof"),
            report,
            &evidence.sites,
        )?;
        if graph.identity.request_sha256 != super::request_fingerprint(&normalized_request) {
            return Err(invalid(
                "composed frame original request fingerprint changed",
            ));
        }
    }
    if query != graph.identity.query_id
        || (evidence.composition.is_none()
            && crate::bap::composition::contains_profile(&graph.identity.semantic_profile))
        || input.snapshot != chain.snapshot_id
        || input.artifact_sha256 != chain.artifact_sha256
        || input.activation.thread_id != chain.thread_id
        || input.activation.frame_activation
            != format!("{}:{}:0x{:016x}", chain.chain_id, graph.frame, frame.sp)
        || if structural {
            frame
                .function_begin
                .is_some_and(|entry| entry != graph.entry)
        } else {
            frame.function_begin != Some(graph.entry)
        }
        || input.roots.len() != 1
        || input.roots[0].site != format!("0x{:016x}", graph.entry)
        || !input.roots[0].function_entry
        || !graph.identity.semantic_profile.ends_with(&semantic_suffix)
        || evidence.normalized["snapshot"].as_str() != Some(input.snapshot.as_str())
        || normalized_request.entry_points != [graph.entry].into()
        || normalized_request.input_kind != crate::InputKind::Dump
        || !normalized_request.file_backed.is_empty()
        || !normalized_request.trusted_fallback.is_empty()
    {
        return Err(invalid(
            "guarded frame activation, entry or request binding changed",
        ));
    }
    if (!structural || !input.premises.is_empty())
        && (input.premises.len() != 1
            || input.premises[0].origin != guard::PremiseOrigin::AbiNormalCall
            || input.premises[0].policy != guard::ABI_POLICY)
    {
        return Err(invalid("guarded frame normal-call premise absent"));
    }
    let rows = evidence.normalized["instructions"]
        .as_array()
        .ok_or_else(|| invalid("guarded frame normalized rows absent"))?;
    let row_count = rows.len();
    let rows: BTreeMap<_, _> = rows
        .iter()
        .map(|row| {
            Ok((
                row["address"]
                    .as_str()
                    .ok_or_else(|| invalid("guarded frame row address"))?,
                row,
            ))
        })
        .collect::<Result<_, Error>>()?;
    if rows.len() != row_count {
        return Err(invalid("duplicate guarded frame normalized row"));
    }
    let sites: BTreeMap<_, _> = evidence.sites.iter().map(|s| (s.va, s)).collect();
    if sites.len() != evidence.sites.len() {
        return Err(invalid("duplicate guarded frame capture source"));
    }
    if sites.keys().copied().collect::<crate::AddressSet>() != normalized_request.addresses {
        return Err(invalid("guarded frame capture source domain changed"));
    }
    for source in &input.sites {
        let va = crate::bap::core_adapter::address(&source.site)?;
        let site = sites
            .get(&va)
            .ok_or_else(|| invalid("guarded frame raw capture source absent"))?;
        if !super::validate::site_valid(site)
            || site.bytes_hex != source.bytes_hex
            || (!source.bytes_hex.is_empty()
                && (!site.captured
                    || site.ast_sha256.as_deref()
                        != Some(crate::reports::sha256(source.ast.as_bytes()).as_str())
                    || site.helper_sha256.as_ref() != Some(&input.producer.helper_sha256)
                    || site.runtime_sha256.as_ref() != Some(&input.producer.runtime_sha256)
                    || site.projection.as_ref() != Some(&input.producer.projection)))
        {
            return Err(invalid("guarded frame BIL, bytes or producer changed"));
        }
        let row = rows
            .get(source.site.as_str())
            .ok_or_else(|| invalid("guarded frame summary absent"))?;
        if guard::recognize_pending_for_input(input, source)?.is_some() {
            if let Some(ast) = report.normal_selection(va) {
                let bytes = super::frame_unwind::unhex(&source.bytes_hex)?;
                let selected = crate::bap::Backend::guard_normal_projection(
                    ast,
                    site.opcode.as_deref().unwrap_or(""),
                    &bytes,
                    va,
                )?;
                let actual = normalized_summary(row)?;
                if selected.instruction != actual
                    || !normalized_request.decodable.contains(&va)
                    || site.quality != "external_lift"
                    || site.semantic_status.as_deref() != Some("projected")
                    || site.accesses
                        != selected
                            .memory_accesses
                            .iter()
                            .map(super::model::AddressUse::from)
                            .collect::<Vec<_>>()
                {
                    return Err(invalid("guarded frame normal effect selection changed"));
                }
            } else {
                let actual = normalized_summary(row)?;
                let locations: crate::LocationSet =
                    serde_json::from_value(evidence.normalized["locations"].clone())?;
                if actual.kind != InstructionKind::Stop
                    || normalized_request.decodable.contains(&va)
                    || !actual.fall.is_empty()
                    || !actual.targets.is_empty()
                    || actual.complete
                    || !actual.must_defs.is_empty()
                    || actual.uses != locations
                    || actual.may_defs != locations
                    || site.quality != "opaque"
                    || site.semantic_status.as_deref() != Some("guard-not-admitted")
                    || !site.accesses.is_empty()
                {
                    return Err(invalid("unadmitted frame guard committed normal effects"));
                }
            }
        } else if guard::CandidateControl::from_instruction(&normalized_summary(row)?)
            != candidate
                .as_ref()
                .and_then(|r| r.instructions.get(&va))
                .map(guard::CandidateControl::from_instruction)
                .unwrap_or_else(|| source.control.clone())
        {
            return Err(invalid("guarded frame candidate control changed"));
        }
    }
    for node in &graph.nodes {
        if sites.get(&node.evidence.va).copied() != Some(&node.evidence)
            || !normalized_request.decodable.contains(&node.evidence.va)
        {
            return Err(invalid(
                "guarded frame published node differs from full capture source",
            ));
        }
        let address = format!("0x{:016x}", node.evidence.va);
        let actual = normalized_summary(
            rows.get(address.as_str())
                .ok_or_else(|| invalid("guarded graph row absent"))?,
        )?;
        if node.call != (actual.kind == InstructionKind::Call)
            || node.fall != actual.fall.iter().copied().collect::<Vec<_>>()
            || node.targets != actual.targets.iter().copied().collect::<Vec<_>>()
        {
            return Err(invalid(
                "guarded frame published control differs from full request",
            ));
        }
    }
    if !structural && (evidence.composition.is_some() || !guard::is_legacy(report)) {
        // Replay only structural recovery. Stopping with an empty pending set
        // avoids FinishRecovery and every dataflow/slice action.
        let mut recovery = crate::Analyzer::new(normalized_request.clone())?;
        while !recovery.state().pending.is_empty() {
            recovery.step();
        }
        let expected =
            recovered_frame_graph(graph.frame, frame, &normalized_request, recovery.state());
        if graph
            .nodes
            .iter()
            .map(|n| n.evidence.va)
            .collect::<Vec<_>>()
            != expected.node_addresses
            || graph.edges != expected.edges
            || graph.gaps != expected.gaps
        {
            return Err(invalid(
                "composed frame topology or coverage gaps differ from sealed recovery",
            ));
        }
    }
    Ok(())
}

/// Reuse complete source/effect/proof checks without draining recovery or requiring completed analysis.
#[cfg(feature = "bap")]
#[allow(clippy::too_many_arguments)]
pub(crate) fn validate_frame_recovery_sources(
    chain: &CapturedFrameChain,
    frame: usize,
    entry: u64,
    identity: &Identity,
    normalized: serde_json::Value,
    sites: Vec<SiteEvidence>,
    report: crate::bap::guard_admission::Report,
    composition: Option<crate::bap::composition::Report>,
    target_resolution: Option<crate::bap::target_resolution::Report>,
    decoder_records: &BTreeMap<String, String>,
) -> Result<(), Error> {
    validate_structural_decode_sources(&report, &sites, decoder_records)?;
    let graph = FrameGraph {
        frame,
        identity: identity.clone(),
        entry,
        nodes: Vec::new(),
        edges: Vec::new(),
        gaps: Vec::new(),
        guard_admission: Some(GuardFrameEvidence {
            report,
            composition,
            target_resolution,
            normalized,
            sites,
        }),
    };
    validate_guarded_graph_inner(chain, &graph, true)
}

/// The original decoded continuation is independent of the final guard Stop.
/// Require every attempted captured source's decode receipt before considering
/// opaque effects, so omitting a receipt cannot evade the control checks.
#[cfg(feature = "bap")]
pub(crate) fn validate_structural_decode_sources(
    report: &crate::bap::guard_admission::Report,
    sites: &[SiteEvidence],
    decoder_records: &BTreeMap<String, String>,
) -> Result<(), Error> {
    use crate::bap::guard_admission::ControlKind;
    let evidence: BTreeMap<_, _> = sites.iter().map(|site| (site.va, site)).collect();
    let expected: BTreeSet<_> = report
        .input
        .sites
        .iter()
        .filter(|source| !source.bytes_hex.is_empty())
        .map(|source| source.site.clone())
        .collect();
    if decoder_records.keys().cloned().collect::<BTreeSet<_>>() != expected {
        return Err(invalid("captured structural decode receipt domain changed"));
    }
    for source in report
        .input
        .sites
        .iter()
        .filter(|source| !source.bytes_hex.is_empty())
    {
        let address = crate::bap::core_adapter::address(&source.site)?;
        let site = evidence
            .get(&address)
            .ok_or_else(|| invalid("decoded source evidence absent"))?;
        let raw = crate::llvm_mc::protocol::parse(&decoder_records[&source.site])?;
        let opcode = (raw.opcode != "-").then_some(raw.opcode.as_str());
        if !site.captured
            || site.bytes_hex != source.bytes_hex
            || site.opcode.as_deref() != opcode
            || raw.decoded.address != address
            || (raw.decoded.status != "invalid"
                && raw.decoded.length != (source.bytes_hex.len() / 2) as u64)
        {
            return Err(invalid(
                "captured structural decoder opcode/address/extent changed",
            ));
        }
        if source.control.kind == ControlKind::Stop {
            let terminal = site.semantic_status.as_deref() == Some("normal-flow-terminal");
            if terminal {
                let receipt = crate::bap::guard_admission::terminal_receipt(&report.input, address)
                    .ok_or_else(|| invalid("captured structural terminal receipt absent"))?;
                crate::bap::guard_admission::terminal_valid(source, receipt)?;
                if receipt.reference.decoder_record != decoder_records[&source.site] {
                    return Err(invalid(
                        "captured structural terminal decode receipt changed",
                    ));
                }
            }
            if !source.opaque
                || !source.control.fall.is_empty()
                || !source.control.targets.is_empty()
                || (!terminal && source.control.complete)
                || (raw.decoded.status == "ok"
                    && !matches!(
                        site.semantic_status.as_deref(),
                        Some(
                            "normal-flow-terminal"
                                | "decode-disagreement"
                                | "control-disagreement"
                                | "opaque-unsupported"
                                | "operand-binding-disagreement"
                        )
                    ))
            {
                return Err(invalid(
                    "captured structural Stop lacks its explicit decode/semantic barrier",
                ));
            }
            continue;
        }
        let kind = raw
            .decoded
            .kind
            .ok_or_else(|| invalid("captured structural candidate lacks decoded control"))?;
        if source.control.kind
            != crate::bap::guard_admission::CandidateControl::from_instruction(
                &crate::Instruction {
                    kind,
                    ..Default::default()
                },
            )
            .kind
        {
            return Err(invalid("captured structural candidate kind changed"));
        }
        let expected_fall = if matches!(
            kind,
            InstructionKind::Ordinary | InstructionKind::Conditional | InstructionKind::Call
        ) {
            vec![format!(
                "0x{:016x}",
                address
                    .checked_add(raw.decoded.length)
                    .ok_or_else(|| invalid("decoded continuation overflow"))?
            )]
        } else {
            Vec::new()
        };
        if source.control.fall != expected_fall {
            return Err(invalid("captured structural original continuation changed"));
        }
        match kind {
            InstructionKind::Jump | InstructionKind::Conditional => {
                let target = raw
                    .decoded
                    .target
                    .ok_or_else(|| invalid("direct decoded branch target absent"))?;
                if source.control.targets != [format!("0x{target:016x}")] {
                    return Err(invalid("captured structural direct target changed"));
                }
            }
            InstructionKind::Call => {
                let targets = raw
                    .decoded
                    .target
                    .into_iter()
                    .map(|target| format!("0x{target:016x}"))
                    .collect::<Vec<_>>();
                if source.control.targets != targets {
                    return Err(invalid("captured structural call target changed"));
                }
            }
            InstructionKind::Ordinary | InstructionKind::Return => {
                if raw.decoded.target.is_some() || !source.control.targets.is_empty() {
                    return Err(invalid("nonbranch captured source gained a target"));
                }
            }
            InstructionKind::Indirect => {
                if raw.decoded.target.is_some() {
                    return Err(invalid("indirect decoded source gained a direct target"));
                }
            }
            InstructionKind::Stop => {
                return Err(invalid("nonterminal candidate has decoded Stop control"));
            }
        }
        if kind != InstructionKind::Indirect
            && source.control.complete
                != (kind != InstructionKind::Call || raw.decoded.target.is_some())
        {
            return Err(invalid(
                "captured structural original control completeness changed",
            ));
        }
    }
    Ok(())
}

#[cfg(feature = "bap")]
struct RecoveredFrameGraph {
    node_addresses: Vec<u64>,
    edges: Vec<FramePathEdge>,
    gaps: Vec<String>,
}

#[cfg(feature = "bap")]
fn recovered_frame_graph(
    frame_index: usize,
    frame: &super::frame_unwind::RecoveredFrame,
    request: &crate::AnalysisRequest,
    state: &crate::AnalysisState,
) -> RecoveredFrameGraph {
    let in_function = |site: u64| {
        frame.function_begin.is_none_or(|b| site >= b)
            && frame.function_end.is_none_or(|e| site < e)
    };
    let node_addresses = state
        .decoded
        .iter()
        .copied()
        .filter(|site| in_function(*site))
        .collect();
    let edges = state
        .edges
        .iter()
        .filter(|e| {
            e.kind.is_local()
                && state.decoded.contains(&e.src)
                && state.decoded.contains(&e.dst)
                && in_function(e.src)
                && in_function(e.dst)
        })
        .map(|e| FramePathEdge {
            src: FramePathNode {
                frame: frame_index,
                site: e.src,
            },
            dst: FramePathNode {
                frame: frame_index,
                site: e.dst,
            },
            kind: e.kind.into(),
        })
        .collect();
    let mut gaps: Vec<_> = state
        .obligations
        .iter()
        .map(|o| format!("0x{:016x}:recovery:{:?}", o.site, o.reason))
        .chain(
            request
                .slice_seeds
                .difference(&state.decoded)
                .map(|site| format!("0x{site:016x}:missing-seed")),
        )
        .collect();
    gaps.extend(state.obligations.iter().map(|o| format!("{o:?}")));
    if state
        .edges
        .iter()
        .any(|e| e.kind.is_local() && in_function(e.src) && !in_function(e.dst))
    {
        gaps.push("local-edge-outside-frame-function".into());
    }
    RecoveredFrameGraph {
        node_addresses,
        edges,
        gaps,
    }
}

#[cfg(feature = "bap")]
fn normalized_summary(row: &serde_json::Value) -> Result<crate::Instruction, Error> {
    let addresses = |name: &str| -> Result<crate::AddressSet, Error> {
        row[name]
            .as_array()
            .ok_or_else(|| invalid("guarded summary address set"))?
            .iter()
            .map(|v| {
                crate::bap::core_adapter::address(
                    v.as_str()
                        .ok_or_else(|| invalid("guarded summary address"))?,
                )
            })
            .collect()
    };
    Ok(crate::Instruction {
        kind: match row["kind"].as_str() {
            Some("ordinary") => InstructionKind::Ordinary,
            Some("conditional") => InstructionKind::Conditional,
            Some("jump") => InstructionKind::Jump,
            Some("indirect") => InstructionKind::Indirect,
            Some("call") => InstructionKind::Call,
            Some("return") => InstructionKind::Return,
            Some("stop") => InstructionKind::Stop,
            _ => return Err(invalid("guarded summary kind")),
        },
        fall: addresses("fall")?,
        targets: addresses("targets")?,
        complete: row["targets_complete"]
            .as_bool()
            .ok_or_else(|| invalid("guarded summary completeness"))?,
        uses: serde_json::from_value(row["uses"].clone())?,
        may_defs: serde_json::from_value(row["may_defs"].clone())?,
        must_defs: serde_json::from_value(row["must_defs"].clone())?,
    })
}

#[cfg(feature = "bap")]
pub(crate) fn decode_guard_request(
    value: &serde_json::Value,
) -> Result<crate::AnalysisRequest, Error> {
    let addresses = |name: &str| -> Result<crate::AddressSet, Error> {
        value[name]
            .as_array()
            .ok_or_else(|| invalid("guarded request address set"))?
            .iter()
            .map(|v| {
                crate::bap::core_adapter::address(
                    v.as_str()
                        .ok_or_else(|| invalid("guarded request address"))?,
                )
            })
            .collect()
    };
    let rows = value["instructions"]
        .as_array()
        .ok_or_else(|| invalid("guarded request rows"))?;
    let instructions: BTreeMap<_, _> = rows
        .iter()
        .map(|row| {
            Ok((
                crate::bap::core_adapter::address(
                    row["address"]
                        .as_str()
                        .ok_or_else(|| invalid("guarded request row address"))?,
                )?,
                normalized_summary(row)?,
            ))
        })
        .collect::<Result<_, Error>>()?;
    let request = crate::AnalysisRequest {
        snapshot_id: value["snapshot"]
            .as_str()
            .ok_or_else(|| invalid("guarded request snapshot"))?
            .into(),
        addresses: addresses("addresses")?,
        locations: serde_json::from_value(value["locations"].clone())?,
        entry_points: addresses("entry_points")?,
        slice_seeds: addresses("slice_seeds")?,
        input_kind: match value["input_kind"].as_str() {
            Some("dump") => crate::InputKind::Dump,
            Some("binary") => crate::InputKind::Binary,
            _ => return Err(invalid("guarded request input kind")),
        },
        captured: addresses("captured")?,
        file_backed: addresses("file_backed")?,
        trusted_fallback: addresses("trusted_fallback")?,
        decodable: addresses("decodable")?,
        instructions,
    };
    request.validate()?;
    if crate::bap::core_adapter::encode_request(&request)? != *value {
        return Err(invalid(
            "noncanonical or duplicate guarded normalized request",
        ));
    }
    Ok(request)
}

fn frame_path_schema(input: &Input) -> &'static str {
    if input.graph_limits.is_some() {
        return LIMITED_FRAME_PATH_SCHEMA;
    }
    #[cfg(feature = "bap")]
    {
        let proofs: Vec<_> = input
            .graphs
            .iter()
            .filter_map(|g| g.guard_admission.as_ref())
            .collect();
        let composition = proofs
            .iter()
            .filter_map(|p| p.composition.as_ref())
            .map(crate::bap::composition::generation)
            .max();
        let current_guard = proofs
            .iter()
            .any(|p| !crate::bap::guard_admission::is_legacy(&p.report));
        if let Some(generation) = composition {
            return match (generation, current_guard) {
                (1, false) => LEGACY_COMPOSED_FRAME_PATH_SCHEMA,
                (2, false) => LEGACY_V2_COMPOSED_FRAME_PATH_SCHEMA,
                _ => COMPOSED_FRAME_PATH_SCHEMA,
            };
        }
        if current_guard {
            return GUARDED_FRAME_PATH_SCHEMA;
        }
        if !proofs.is_empty() {
            return LEGACY_GUARDED_FRAME_PATH_SCHEMA;
        }
    }
    let _ = input;
    FRAME_PATH_SCHEMA
}

#[cfg(feature = "bap")]
fn append_guard_premises(input: &Input, premises: &mut Vec<String>) {
    for graph in &input.graphs {
        if let Some(evidence) = &graph.guard_admission {
            if let Some(scope) = crate::bap::guard_admission::normal_flow_scope(&evidence.report) {
                premises.push(format!("frame-{}: normal-flow-scope {scope}; exception-exit; exception-resumption-outside-local-scope; exceptional effects unsupported",graph.frame));
            }
            if let Some(composition) = &evidence.composition {
                let target = evidence
                    .target_resolution
                    .as_ref()
                    .expect("validated paired target proof");
                premises.push(format!("frame-{}: composition {} proof {}; target profile {}; premise {}: captured control data is interpreted as frozen; no historical memory stability or executed path is inferred", graph.frame, composition.profile, composition.binding_sha256, target.profile, target.memory_premise));
                for row in &target.resolutions {
                    premises.push(format!(
                        "frame-{}: indirect {}: {} targets; complete={}; unresolved={:?}",
                        graph.frame,
                        row.site,
                        row.targets.len(),
                        row.complete,
                        row.unresolved
                    ));
                }
                premises.push(format!(
                    "frame-{}: target resolution stopped: {:?}",
                    graph.frame, target.stop
                ));
            }
            for premise in &evidence.report.input.premises {
                premises.push(format!(
                    "frame-{}: assumed {}: entry RSP mod 16 = 8 at {}; activation {}; evidence {}",
                    graph.frame,
                    premise.policy,
                    premise.point,
                    premise.activation.frame_activation,
                    premise.evidence_sha256
                ));
            }
            for decision in &evidence.report.guards {
                premises.push(format!(
                    "frame-{}: guard {} {:?}; {}; proof {}",
                    graph.frame,
                    decision.site,
                    decision.verdict,
                    decision.residual,
                    decision.receipt_sha256
                ));
            }
            if let Some(stop) = &evidence.report.stop {
                premises.push(format!(
                    "frame-{}: guard admission stopped: {stop}",
                    graph.frame
                ));
            }
        }
    }
}
#[cfg(not(feature = "bap"))]
fn append_guard_premises(_input: &Input, _premises: &mut Vec<String>) {}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ListedFramePath {
    pub path_id: String,
    pub nodes: Vec<FramePathNode>,
    pub edges: Vec<FramePathEdge>,
    pub contains_opaque_summary: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathCounters {
    pub expanded_states: usize,
    pub scanned_edges: usize,
    pub peak_frontier_bytes: usize,
    pub retained_path_bytes: usize,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FramePathListing {
    pub schema: String,
    pub scope_id: String,
    pub question: FramePathQuestion,
    pub limits: FramePathLimits,
    pub available: bool,
    pub coverage: String,
    pub truncated: bool,
    pub enumeration_exhausted: bool,
    pub stop_reason: String,
    pub gaps: Vec<String>,
    pub returned_count: usize,
    pub paths: Vec<ListedFramePath>,
    pub counters: FramePathCounters,
    pub frontier_count: usize,
    pub elapsed_ms: u64,
    pub premises: Vec<String>,
    input: Input,
}
fn compose(
    input: &Input,
    q: &FramePathQuestion,
) -> Result<
    (
        FramePathNode,
        FramePathNode,
        Vec<FramePathEdge>,
        Vec<String>,
    ),
    Error,
> {
    let graphs: BTreeMap<_, _> = input.graphs.iter().map(|g| (g.frame, g)).collect();
    let mut anchors = BTreeMap::new();
    let mut edges = Vec::new();
    let mut gaps = Vec::new();
    for frame in q.to_frame..=q.from_frame {
        let g = *graphs
            .get(&frame)
            .ok_or_else(|| invalid("missing-frame-query"))?;
        gaps.extend(g.gaps.iter().map(|v| format!("frame-{frame}:{v}")));
        for n in &g.nodes {
            if !n.evidence.gaps.is_empty() {
                gaps.extend(
                    n.evidence
                        .gaps
                        .iter()
                        .map(|v| format!("frame-{frame}:0x{:016x}:{v}", n.evidence.va)),
                );
            }
        }
        let anchor = if frame == 0 {
            input.chain.frames[0].pc
        } else {
            let child = graphs.get(&(frame - 1));
            let expected = input.chain.frames[frame - 1]
                .function_begin
                .or(child.map(|g| g.entry));
            let calls: Vec<_> = g
                .nodes
                .iter()
                .filter(|n| {
                    call_target(n, input.chain.frames[frame].pc)
                        .is_some_and(|target| expected == Some(target))
                })
                .collect();
            if calls.len() != 1 {
                return Err(invalid("missing-or-ambiguous-active-call-anchor"));
            }
            let call = calls[0];
            if frame > q.to_frame {
                let child = child.ok_or_else(|| invalid("missing-child-query"))?;
                if !child.nodes.iter().any(|n| n.evidence.va == child.entry) {
                    return Err(invalid("child-entry-not-reached"));
                }
                edges.push(FramePathEdge {
                    src: FramePathNode {
                        frame,
                        site: call.evidence.va,
                    },
                    dst: FramePathNode {
                        frame: frame - 1,
                        site: child.entry,
                    },
                    kind: FramePathEdgeKind::Call,
                });
            }
            call.evidence.va
        };
        if !g.nodes.iter().any(|n| n.evidence.va == anchor) {
            return Err(invalid("frame-endpoint-not-reached"));
        }
        anchors.insert(frame, anchor);
        edges.extend(
            g.edges
                .iter()
                .filter(|e| e.src.site != anchor || frame == q.to_frame)
                .cloned(),
        );
    }
    edges.sort();
    edges.dedup();
    gaps.sort();
    gaps.dedup();
    Ok((
        FramePathNode {
            frame: q.from_frame,
            site: anchors[&q.from_frame],
        },
        FramePathNode {
            frame: q.to_frame,
            site: anchors[&q.to_frame],
        },
        edges,
        gaps,
    ))
}
fn list(
    input: Input,
    q: FramePathQuestion,
    limits: FramePathLimits,
    replay_deadline: Option<usize>,
) -> Result<FramePathListing, Error> {
    if q.np == 0 || q.np > 4097 || q.from_frame < q.to_frame {
        return Err(invalid("invalid NP or frame indices"));
    }
    validate_input(&input)?;
    let started = Instant::now();
    let scope_id = sha(&serde_json::to_vec(&(&input, &q, &limits))?);
    let mut premises = vec!["Structural alternatives under captured frame, decoded-control and unwind/Windows ABI premises; no executed history or selected writer".into(), "Opaque summary steps retain unknown callee interiors; an incomplete path list never excludes a memory writer".into()];
    append_guard_premises(&input, &mut premises);
    let mut result = FramePathListing {
        schema: frame_path_schema(&input).into(),
        scope_id,
        question: q.clone(),
        limits: limits.clone(),
        available: true,
        coverage: "partial".into(),
        truncated: false,
        enumeration_exhausted: false,
        stop_reason: String::new(),
        gaps: Vec::new(),
        returned_count: 0,
        paths: Vec::new(),
        counters: FramePathCounters {
            expanded_states: 0,
            scanned_edges: 0,
            peak_frontier_bytes: 0,
            retained_path_bytes: 0,
        },
        frontier_count: 0,
        elapsed_ms: 0,
        premises,
        input,
    };
    let payload = serde_json::to_vec(&result)?.len();
    if payload > limits.max_output_bytes {
        return Err(invalid("frame-output-input-byte-budget"));
    }
    if q.from_frame >= result.input.chain.frames.len() {
        if result.input.chain.stop_reason == "zero-return-boundary" {
            return Err(invalid("frame index outside complete recovered chain"));
        }
        result.available = false;
        result.coverage = "unavailable".into();
        result.truncated = result.input.chain.truncated;
        result.stop_reason = "requested-frame-not-recovered".into();
        result.gaps.push(result.input.chain.stop_reason.clone());
        return Ok(result);
    }
    let composed = compose(&result.input, &q);
    let (start, end, edges, gaps) = match composed {
        Ok(v) => v,
        Err(e) => {
            result.available = false;
            result.coverage = "unavailable".into();
            result.stop_reason = e.to_string();
            result.gaps.push(result.stop_reason.clone());
            return Ok(result);
        }
    };
    result.gaps = gaps;
    if result
        .input
        .graphs
        .iter()
        .map(|g| g.nodes.len())
        .sum::<usize>()
        > limits.max_graph_nodes
        || edges.len() > limits.max_graph_edges
    {
        result.truncated = true;
        result.stop_reason = "frame-graph-budget".into();
        return Ok(result);
    }
    if limits.max_path_steps == 0 || limits.max_node_visits == 0 {
        result.truncated = true;
        result.stop_reason = "path-or-visit-budget".into();
        return Ok(result);
    }
    let mut outgoing: BTreeMap<FramePathNode, Vec<FramePathEdge>> = BTreeMap::new();
    for e in edges {
        outgoing.entry(e.src).or_default().push(e);
    }
    let first = (vec![start], Vec::<FramePathEdge>::new());
    let size = |p: &(Vec<FramePathNode>, Vec<FramePathEdge>)| {
        p.0.len() * std::mem::size_of::<FramePathNode>()
            + p.1.len() * std::mem::size_of::<FramePathEdge>()
    };
    let mut frontier = vec![first];
    let mut bytes = size(&frontier[0]);
    let mut blocked = false;
    if bytes > limits.max_frontier_bytes {
        result.truncated = true;
        result.stop_reason = "frontier-byte-budget".into();
        result.frontier_count = 1;
        return Ok(result);
    }
    result.counters.peak_frontier_bytes = bytes;
    while !frontier.is_empty() {
        let reason = if result.paths.len() >= q.np - 1 {
            Some("path-count-budget")
        } else if result.counters.expanded_states >= limits.max_search_states {
            Some("search-state-budget")
        } else if replay_deadline.is_some_and(|at| at == result.counters.expanded_states)
            || (replay_deadline.is_none()
                && started.elapsed().as_millis() >= u128::from(limits.deadline_ms))
        {
            Some("deadline-budget")
        } else {
            None
        };
        if let Some(reason) = reason {
            result.stop_reason = reason.into();
            result.truncated = true;
            break;
        }
        let current = frontier.pop().expect("nonempty");
        bytes -= size(&current);
        result.counters.expanded_states += 1;
        let here = *current.0.last().expect("path has start");
        if here == end {
            let contains_opaque_summary = current
                .1
                .iter()
                .any(|e| e.kind == FramePathEdgeKind::Summary);
            let path = ListedFramePath {
                path_id: sha(&serde_json::to_vec(&(&result.scope_id, &current))?),
                nodes: current.0,
                edges: current.1,
                contains_opaque_summary,
            };
            let path_bytes = serde_json::to_vec(&path)?.len();
            if payload
                .checked_add(result.counters.retained_path_bytes)
                .and_then(|v| v.checked_add(path_bytes))
                .and_then(|v| v.checked_add(1024))
                .is_none_or(|v| v > limits.max_output_bytes)
            {
                result.truncated = true;
                result.stop_reason = "output-byte-budget".into();
                blocked = true;
                break;
            }
            result.counters.retained_path_bytes += path_bytes;
            result.paths.push(path);
            continue;
        }
        if current.0.len() >= limits.max_path_steps {
            blocked = true;
            result.gaps.push("path-step-budget".into());
            continue;
        }
        if let Some(next) = outgoing.get(&here) {
            for edge in next.iter().rev() {
                if result.counters.scanned_edges >= limits.max_scanned_edges {
                    blocked = true;
                    result.gaps.push("scanned-edge-budget".into());
                    break;
                }
                result.counters.scanned_edges += 1;
                if current.0.iter().filter(|n| **n == edge.dst).count() >= limits.max_node_visits {
                    blocked = true;
                    result.gaps.push("loop-visit-budget".into());
                    continue;
                }
                let extra =
                    std::mem::size_of::<FramePathNode>() + std::mem::size_of::<FramePathEdge>();
                let addition = size(&current) + extra;
                if bytes
                    .checked_add(addition)
                    .is_none_or(|v| v > limits.max_frontier_bytes)
                {
                    blocked = true;
                    result.gaps.push("frontier-byte-budget".into());
                    break;
                }
                let mut nodes = current.0.clone();
                nodes.push(edge.dst);
                let mut path_edges = current.1.clone();
                path_edges.push(edge.clone());
                frontier.push((nodes, path_edges));
                bytes += addition;
                result.counters.peak_frontier_bytes =
                    result.counters.peak_frontier_bytes.max(bytes);
            }
        }
    }
    result.returned_count = result.paths.len();
    result.frontier_count = frontier.len();
    result.enumeration_exhausted = frontier.is_empty() && !blocked && result.stop_reason.is_empty();
    result.truncated |= blocked;
    if result.stop_reason.is_empty() {
        result.stop_reason = if blocked {
            "search-restriction"
        } else {
            "frontier-exhausted"
        }
        .into();
    }
    if result.enumeration_exhausted && result.gaps.is_empty() {
        result.coverage = "complete_within_declared_scope".into();
    }
    result.gaps.sort();
    result.gaps.dedup();
    result.elapsed_ms = started.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
    Ok(result)
}
pub fn list_frame_paths(
    bound: &BoundFramePaths,
    question: FramePathQuestion,
    limits: FramePathLimits,
) -> Result<FramePathListing, Error> {
    list(bound.input.clone(), question, limits, None)
}
impl FramePathListing {
    #[cfg(test)]
    pub(super) fn relist_for_test(&self) -> Result<Self, Error> {
        list(
            self.input.clone(),
            self.question.clone(),
            self.limits.clone(),
            Some(usize::MAX),
        )
    }
    pub fn frame_chain(&self) -> &CapturedFrameChain {
        &self.input.chain
    }
    /// Check caller-selected saved-report graph bounds before chain/proof replay.
    /// The retained producer policy cannot enlarge these independent host bounds.
    pub fn validate_with_graph_limits(&self, limits: &FramePathGraphLimits) -> Result<(), Error> {
        let mut nodes = 0usize;
        let mut edges = 0usize;
        for graph in &self.input.graphs {
            nodes = nodes
                .checked_add(graph.nodes.len())
                .filter(|count| *count <= limits.max_graph_nodes)
                .ok_or_else(|| invalid("frame host graph admission node budget"))?;
            edges = edges
                .checked_add(graph.edges.len())
                .filter(|count| *count <= limits.max_graph_edges)
                .ok_or_else(|| invalid("frame host graph admission edge budget"))?;
        }
        self.validate()
    }
    /// Replay under the retained source policy. Saved-report decoders additionally
    /// enforce independently supplied host bounds via `validate_with_graph_limits`.
    pub fn validate(&self) -> Result<(), Error> {
        let deadline = if self.stop_reason == "deadline-budget" {
            if self.elapsed_ms < self.limits.deadline_ms {
                return Err(invalid("invalid deadline receipt"));
            }
            Some(self.counters.expanded_states)
        } else {
            Some(usize::MAX)
        };
        let mut expected = list(
            self.input.clone(),
            self.question.clone(),
            self.limits.clone(),
            deadline,
        )?;
        expected.elapsed_ms = self.elapsed_ms;
        if expected != *self {
            return Err(invalid("frame path recomputation mismatch"));
        }
        if serde_json::to_vec(self)?.len() > self.limits.max_output_bytes {
            return Err(invalid("frame output exceeds byte budget"));
        }
        Ok(())
    }
    pub fn validate_for(&self, bound: &BoundFramePaths) -> Result<(), Error> {
        if self.input != bound.input {
            return Err(invalid("frame path binding changed"));
        }
        self.validate()
    }
}

#[cfg(all(test, feature = "input"))]
#[path = "../../tests/investigation/frame_paths_unit.rs"]
mod tests;

#[cfg(all(test, feature = "reports", not(feature = "bap")))]
#[path = "../../tests/investigation/frame_paths_reports_only.rs"]
mod reports_only_tests;

#[cfg(all(test, feature = "property-tests"))]
#[path = "../../tests/investigation/frame_paths_properties.rs"]
mod properties;
