//! Read-only graph questions over a validated Stage 5.1 source.
use super::frame_paths::captured_call_target;
use super::{
    BoundFrameStructure, Error, FramePathEdge, FramePathEdgeKind, FramePathNode, FrameStructureGap,
    FrameStructureLimits, invalid,
};
use crate::InstructionKind;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::io::Write;
use std::time::Instant;

pub const FRAME_CONNECTION_SCHEMA: &str = "ariadne.frame-connections/v1";
const ALGORITHM: &str = "represented-graph-kosaraju-bfs-detours/v1";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameConnectionLimits {
    pub structural: FrameStructureLimits,
    pub max_input_bytes: usize,
    pub max_output_bytes: usize,
    pub max_source_bytes: usize,
    pub max_graph_nodes: usize,
    pub max_graph_edges: usize,
    pub max_work_bytes: usize,
    pub graph_work: u64,
    pub reach_work: u64,
    pub scc_work: u64,
    pub example_work: u64,
    pub deadline_ms: u64,
    pub max_example_attempts: usize,
    pub max_path_nodes: usize,
    pub max_count_bound: usize,
}
impl Default for FrameConnectionLimits {
    fn default() -> Self {
        Self {
            structural: FrameStructureLimits::default(),
            max_input_bytes: 1024 * 1024 * 1024,
            max_output_bytes: 1024 * 1024 * 1024,
            max_source_bytes: 512 * 1024 * 1024,
            max_graph_nodes: 65_536,
            max_graph_edges: 262_144,
            max_work_bytes: 128 * 1024 * 1024,
            graph_work: 4_194_304,
            reach_work: 4_194_304,
            scc_work: 8_388_608,
            example_work: 4_194_304,
            deadline_ms: 5000,
            max_example_attempts: 64,
            max_path_nodes: 4096,
            max_count_bound: 4097,
        }
    }
}
impl FrameConnectionLimits {
    pub fn validate(&self) -> Result<(), Error> {
        self.structural.validate()?;
        if self.max_count_bound == 0 {
            return Err(invalid("connection count host cap must be positive"));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionLayerStatus {
    CompleteForRepresentedGraph,
    WorkStopped,
    Unavailable,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExampleSearchStatus {
    Finished,
    WorkStopped,
    Unavailable,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RepresentedConnection {
    Found,
    AbsentInRepresentedGraph,
    UnknownWorkStopped,
    UnavailableAnchors,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectionStop {
    WorkLimit,
    Deadline,
    ByteLimit,
    NodeLimit,
    EdgeLimit,
    AttemptLimit,
    PathLengthLimit,
    CountBound,
}
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConnectionReceipt {
    pub work: u64,
    pub elapsed_ms: u64,
    pub stop: Option<ConnectionStop>,
}
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConnectionReceipts {
    pub graph: ConnectionReceipt,
    pub forward: ConnectionReceipt,
    pub backward: ConnectionReceipt,
    pub scc: ConnectionReceipt,
    pub examples: ConnectionReceipt,
}
struct Meter<'a> {
    used: u64,
    cap: u64,
    deadline_ms: u64,
    started: Instant,
    replay: Option<&'a ConnectionReceipt>,
}
impl<'a> Meter<'a> {
    fn new(
        cap: u64,
        limits: &FrameConnectionLimits,
        replay: Option<&'a ConnectionReceipt>,
    ) -> Self {
        Self {
            used: 0,
            cap,
            deadline_ms: limits.deadline_ms,
            started: Instant::now(),
            replay,
        }
    }
    fn tick(&mut self) -> Result<(), ConnectionStop> {
        if self.used >= self.cap {
            return Err(ConnectionStop::WorkLimit);
        }
        let deadline = self.replay.map_or_else(
            || self.started.elapsed().as_millis() >= u128::from(self.deadline_ms),
            |r| r.stop == Some(ConnectionStop::Deadline) && self.used == r.work,
        );
        if deadline {
            return Err(ConnectionStop::Deadline);
        }
        self.used += 1;
        Ok(())
    }
    fn receipt(&self, stop: Option<ConnectionStop>) -> ConnectionReceipt {
        ConnectionReceipt {
            work: self.used,
            stop,
            elapsed_ms: self.replay.map_or_else(
                || u64::try_from(self.started.elapsed().as_millis()).unwrap_or(u64::MAX),
                |r| r.elapsed_ms,
            ),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrontierRelation {
    OnCorridor,
    ForwardReachable,
    OtherRegion,
    Unclassified,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConnectionFrontier {
    pub frame: usize,
    pub gap: FrameStructureGap,
    pub relation: FrontierRelation,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ContextEdge {
    pub edge: FramePathEdge,
    pub reason: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StructuralComponent {
    pub id: String,
    pub members: Vec<FramePathNode>,
    pub cyclic: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CondensationEdge {
    pub source: String,
    pub destination: String,
    pub kind: FramePathEdgeKind,
    pub original_edges: Vec<FramePathEdge>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConnectionExample {
    pub id: String,
    pub nodes: Vec<FramePathNode>,
    pub edges: Vec<FramePathEdge>,
    pub shortest_in_represented_graph: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameConnectionAnalysis {
    pub algorithm: String,
    pub source_fingerprint: String,
    pub scope_id: String,
    pub conditional_on: Vec<String>,
    pub from_frame: usize,
    pub to_frame: usize,
    pub example_count_bound: usize,
    pub limits: FrameConnectionLimits,
    pub graph_status: ConnectionLayerStatus,
    pub nodes: Vec<FramePathNode>,
    pub edges: Vec<FramePathEdge>,
    pub context_edges: Vec<ContextEdge>,
    pub frontiers: Vec<ConnectionFrontier>,
    pub start: Option<FramePathNode>,
    pub endpoint: Option<FramePathNode>,
    pub anchor_gaps: Vec<String>,
    pub connection: RepresentedConnection,
    pub corridor_status: ConnectionLayerStatus,
    pub forward: Vec<FramePathNode>,
    pub backward: Vec<FramePathNode>,
    pub corridor: Vec<FramePathNode>,
    pub scc_status: ConnectionLayerStatus,
    pub components: Vec<StructuralComponent>,
    pub condensation: Vec<CondensationEdge>,
    pub examples_status: ExampleSearchStatus,
    pub examples: Vec<ConnectionExample>,
    pub receipts: ConnectionReceipts,
    pub premises: Vec<String>,
}
/// No public deserialization or arbitrary-graph constructor exists.
pub struct BoundFrameConnections {
    source: BoundFrameStructure,
    analysis: FrameConnectionAnalysis,
}
impl BoundFrameConnections {
    pub fn source(&self) -> &BoundFrameStructure {
        &self.source
    }
    pub fn analysis(&self) -> &FrameConnectionAnalysis {
        &self.analysis
    }
}

pub(crate) fn digest<T: Serialize>(value: &T, cap: usize) -> Result<String, Error> {
    struct Sink {
        hash: Sha256,
        used: usize,
        cap: usize,
    }
    impl Write for Sink {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            if bytes.len() > self.cap.saturating_sub(self.used) {
                return Err(std::io::Error::other("connection source/identity byte cap"));
            }
            self.used += bytes.len();
            self.hash.update(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut sink = Sink {
        hash: Sha256::new(),
        used: 0,
        cap,
    };
    serde_json::to_writer(&mut sink, value)?;
    Ok(format!("{:x}", sink.hash.finalize()))
}
pub(crate) fn source_fingerprint(
    source: &BoundFrameStructure,
    cap: usize,
) -> Result<String, Error> {
    // Borrow payloads: hashing cannot allocate a second copy of captured BIL.
    let recoveries: Vec<_> = source
        .recoveries()
        .iter()
        .map(|(i, r)| {
            let receipt = r.recovery().receipt();
            let limits = r.recovery().limits();
            (
                *i,
                r.identity(),
                r.context(),
                r.proofs(),
                limits.max_visits,
                limits.deadline_ms,
                receipt.visits,
                receipt.elapsed_ms,
                format!("{:?}", receipt.stop),
            )
        })
        .collect();
    digest(
        &(
            "ariadne.frame-connection-source/v1",
            source.chain(),
            source.question(),
            source.limits(),
            source.frames(),
            source.links(),
            source.diagnostics(),
            recoveries,
        ),
        cap,
    )
}
fn anchor(source: &BoundFrameStructure, frame: usize) -> Result<FramePathNode, String> {
    let chain = source.chain();
    let captured = chain.frames.get(frame).ok_or("frame-not-recovered")?;
    if frame == 0 {
        return Ok(FramePathNode {
            frame,
            site: captured.pc,
        });
    }
    let child = chain
        .frames
        .get(frame - 1)
        .ok_or("child-frame-not-recovered")?;
    let parent = source
        .recoveries()
        .iter()
        .find(|(i, _)| *i == frame)
        .map(|(_, r)| r)
        .ok_or("missing-frame-recovery")?;
    let expected = child.function_begin.or_else(|| {
        source
            .frames()
            .iter()
            .find(|m| m.frame == frame - 1)
            .map(|m| m.entry)
    });
    let candidates: Vec<_> = parent
        .context()
        .sites
        .iter()
        .filter_map(|site| {
            if !parent.recovery().state().decoded.contains(&site.va)
                || captured.function_begin.is_some_and(|b| site.va < b)
                || captured
                    .function_end
                    .is_some_and(|e| u128::from(site.va) + 5 > u128::from(e))
            {
                return None;
            }
            let instruction = parent.request().instructions.get(&site.va)?;
            captured_call_target(
                site,
                instruction.kind == InstructionKind::Call,
                &instruction.fall.iter().copied().collect::<Vec<_>>(),
                &instruction.targets.iter().copied().collect::<Vec<_>>(),
                captured.pc,
            )
            .filter(|target| expected == Some(*target))
            .map(|_| FramePathNode {
                frame,
                site: site.va,
            })
        })
        .collect();
    if candidates.len() != 1 {
        return Err("missing-or-ambiguous-active-call-anchor".into());
    }
    Ok(candidates[0])
}

#[derive(Default)]
struct Graph {
    nodes: Vec<FramePathNode>,
    edges: Vec<FramePathEdge>,
    context: Vec<ContextEdge>,
    frontiers: Vec<ConnectionFrontier>,
}
fn graph(
    source: &BoundFrameStructure,
    limits: &FrameConnectionLimits,
    meter: &mut Meter<'_>,
    anchors: &BTreeMap<usize, FramePathNode>,
) -> Result<Graph, ConnectionStop> {
    let q = source.question();
    let maps: Vec<_> = source
        .frames()
        .iter()
        .filter(|m| !m.auxiliary && m.frame >= q.to_frame && m.frame <= q.from_frame)
        .collect();
    let nc = maps
        .iter()
        .try_fold(0usize, |n, m| n.checked_add(m.nodes.len()))
        .ok_or(ConnectionStop::NodeLimit)?;
    let ec = maps
        .iter()
        .try_fold(source.links().len(), |n, m| n.checked_add(m.edges.len()))
        .ok_or(ConnectionStop::EdgeLimit)?;
    let gc = maps
        .iter()
        .try_fold(0usize, |n, m| n.checked_add(m.gaps.len()))
        .ok_or(ConnectionStop::ByteLimit)?;
    if nc > limits.max_graph_nodes {
        return Err(ConnectionStop::NodeLimit);
    }
    if ec > limits.max_graph_edges {
        return Err(ConnectionStop::EdgeLimit);
    }
    // Accounted graph/adjacency/SCC storage; allocator overhead is not an RSS claim.
    if nc
        .checked_add(ec)
        .and_then(|n| n.checked_add(gc))
        .and_then(|n| n.checked_mul(256))
        .is_none_or(|n| n > limits.max_work_bytes)
    {
        return Err(ConnectionStop::ByteLimit);
    }
    let mut nodes = BTreeSet::new();
    for m in &maps {
        let activation = &source.chain().frames[m.frame];
        for site in &m.nodes {
            meter.tick()?;
            if activation.function_begin.is_none_or(|b| site.va >= b)
                && activation.function_end.is_none_or(|e| {
                    u128::from(site.va) + (site.bytes_hex.len() / 2) as u128 <= u128::from(e)
                })
            {
                nodes.insert(FramePathNode {
                    frame: m.frame,
                    site: site.va,
                });
            }
        }
    }
    let mut edges = BTreeSet::new();
    let mut context = Vec::new();
    let mut frontiers = Vec::new();
    for m in maps {
        for gap in &m.gaps {
            meter.tick()?;
            frontiers.push(ConnectionFrontier {
                frame: m.frame,
                gap: gap.clone(),
                relation: FrontierRelation::Unclassified,
            });
        }
        for e in &m.edges {
            meter.tick()?;
            let edge = FramePathEdge {
                src: e.src,
                dst: e.dst,
                kind: e.kind,
            };
            let active = m.frame > q.to_frame && anchors.get(&m.frame) == Some(&edge.src);
            let reason = if e.kind == FramePathEdgeKind::Call {
                Some("call-context")
            } else if active {
                Some("active-call-continuation-context")
            } else if !nodes.contains(&e.src) || !nodes.contains(&e.dst) {
                Some("endpoint-outside-admitted-instruction-graph")
            } else {
                None
            };
            if let Some(reason) = reason {
                context.push(ContextEdge {
                    edge,
                    reason: reason.into(),
                });
            } else {
                edges.insert(edge);
            }
        }
    }
    for link in source.links() {
        meter.tick()?;
        if link.admitted && link.caller <= q.from_frame && link.child >= q.to_frame {
            let src = FramePathNode {
                frame: link.caller,
                site: link.call_site.expect("validated admitted link"),
            };
            let dst = FramePathNode {
                frame: link.child,
                site: link.child_entry.expect("validated admitted link"),
            };
            if nodes.contains(&src) && nodes.contains(&dst) {
                edges.insert(FramePathEdge {
                    src,
                    dst,
                    kind: FramePathEdgeKind::Call,
                });
            }
        }
    }
    Ok(Graph {
        nodes: nodes.into_iter().collect(),
        edges: edges.into_iter().collect(),
        context,
        frontiers,
    })
}
struct Index {
    ids: BTreeMap<FramePathNode, usize>,
    outgoing: Vec<Vec<usize>>,
    incoming: Vec<Vec<usize>>,
}
impl Index {
    #[cfg(test)]
    fn new(g: &Graph) -> Self {
        Self::bounded(
            g,
            &mut Meter::new(
                u64::MAX,
                &FrameConnectionLimits {
                    deadline_ms: u64::MAX,
                    ..Default::default()
                },
                None,
            ),
        )
        .unwrap()
    }
    fn bounded(g: &Graph, meter: &mut Meter<'_>) -> Result<Self, ConnectionStop> {
        let mut ids = BTreeMap::new();
        for (i, n) in g.nodes.iter().enumerate() {
            meter.tick()?;
            ids.insert(*n, i);
        }
        let mut outgoing = vec![Vec::new(); g.nodes.len()];
        let mut incoming = outgoing.clone();
        for (i, e) in g.edges.iter().enumerate() {
            meter.tick()?;
            outgoing[ids[&e.src]].push(i);
            incoming[ids[&e.dst]].push(i);
        }
        Ok(Self {
            ids,
            outgoing,
            incoming,
        })
    }
}
fn reachable(
    g: &Graph,
    index: &Index,
    start: usize,
    reverse: bool,
    meter: &mut Meter<'_>,
) -> (BTreeSet<usize>, Option<ConnectionStop>) {
    let mut seen = BTreeSet::from([start]);
    let mut queue = VecDeque::from([start]);
    while let Some(here) = queue.pop_front() {
        if let Err(stop) = meter.tick() {
            return (seen, Some(stop));
        }
        for &edge in if reverse {
            &index.incoming[here]
        } else {
            &index.outgoing[here]
        } {
            if let Err(stop) = meter.tick() {
                return (seen, Some(stop));
            }
            let next = if reverse {
                index.ids[&g.edges[edge].src]
            } else {
                index.ids[&g.edges[edge].dst]
            };
            if seen.insert(next) {
                queue.push_back(next);
            }
        }
    }
    (seen, None)
}
fn components(
    g: &Graph,
    index: &Index,
    scope: &str,
    limits: &FrameConnectionLimits,
    meter: &mut Meter<'_>,
) -> Result<(Vec<StructuralComponent>, Vec<CondensationEdge>), ConnectionStop> {
    let mut seen = vec![false; g.nodes.len()];
    let mut finish = Vec::new();
    for root in 0..g.nodes.len() {
        meter.tick()?;
        if seen[root] {
            continue;
        }
        seen[root] = true;
        let mut stack = vec![(root, 0usize)];
        while let Some((here, next)) = stack.last_mut() {
            meter.tick()?;
            if *next == index.outgoing[*here].len() {
                finish.push(*here);
                stack.pop();
                continue;
            }
            let edge = index.outgoing[*here][*next];
            *next += 1;
            let dst = index.ids[&g.edges[edge].dst];
            if !seen[dst] {
                seen[dst] = true;
                stack.push((dst, 0));
            }
        }
    }
    let mut assigned = vec![false; g.nodes.len()];
    let mut groups = Vec::new();
    for root in finish.into_iter().rev() {
        meter.tick()?;
        if assigned[root] {
            continue;
        }
        assigned[root] = true;
        let mut stack = vec![root];
        let mut members = Vec::new();
        while let Some(here) = stack.pop() {
            meter.tick()?;
            members.push(g.nodes[here]);
            for &edge in &index.incoming[here] {
                meter.tick()?;
                let src = index.ids[&g.edges[edge].src];
                if !assigned[src] {
                    assigned[src] = true;
                    stack.push(src);
                }
            }
        }
        members.sort();
        groups.push(members);
    }
    groups.sort();
    let mut self_loops = BTreeSet::new();
    for e in &g.edges {
        meter.tick()?;
        if e.src == e.dst {
            self_loops.insert(e.src);
        }
    }
    let mut owner = BTreeMap::new();
    let mut result = Vec::new();
    for members in groups {
        meter.tick()?;
        let id = digest(&("scc/v1", scope, &members), limits.max_work_bytes)
            .map_err(|_| ConnectionStop::ByteLimit)?;
        for n in &members {
            meter.tick()?;
            owner.insert(*n, id.clone());
        }
        let cyclic = members.len() > 1 || members.first().is_some_and(|n| self_loops.contains(n));
        result.push(StructuralComponent {
            id,
            members,
            cyclic,
        });
    }
    let mut quotient: BTreeMap<(String, String, FramePathEdgeKind), Vec<FramePathEdge>> =
        BTreeMap::new();
    for edge in &g.edges {
        meter.tick()?;
        let src = &owner[&edge.src];
        let dst = &owner[&edge.dst];
        if src != dst {
            quotient
                .entry((src.clone(), dst.clone(), edge.kind))
                .or_default()
                .push(edge.clone());
        }
    }
    Ok((
        result,
        quotient
            .into_iter()
            .map(
                |((source, destination, kind), original_edges)| CondensationEdge {
                    source,
                    destination,
                    kind,
                    original_edges,
                },
            )
            .collect(),
    ))
}

fn bfs(
    g: &Graph,
    index: &Index,
    start: usize,
    end: usize,
    forbidden: Option<usize>,
    limits: &FrameConnectionLimits,
    meter: &mut Meter<'_>,
) -> Result<Option<Vec<usize>>, ConnectionStop> {
    let mut parents: Vec<Option<usize>> = vec![None; g.nodes.len()];
    let mut depth = vec![0usize; g.nodes.len()];
    if limits.max_path_nodes == 0 {
        return Err(ConnectionStop::PathLengthLimit);
    }
    depth[start] = 1;
    let mut queue = VecDeque::from([start]);
    let mut restricted = false;
    while let Some(here) = queue.pop_front() {
        meter.tick()?;
        if here == end {
            let mut path = Vec::new();
            let mut cursor = end;
            while cursor != start {
                let e = parents[cursor].expect("reached node parent");
                path.push(e);
                cursor = index.ids[&g.edges[e].src];
            }
            path.reverse();
            return Ok(Some(path));
        }
        for &edge in &index.outgoing[here] {
            meter.tick()?;
            if forbidden == Some(edge) {
                continue;
            }
            let dst = index.ids[&g.edges[edge].dst];
            if depth[dst] != 0 {
                continue;
            }
            if depth[here] >= limits.max_path_nodes {
                restricted = true;
                continue;
            }
            depth[dst] = depth[here] + 1;
            parents[dst] = Some(edge);
            queue.push_back(dst);
        }
    }
    if restricted {
        Err(ConnectionStop::PathLengthLimit)
    } else {
        Ok(None)
    }
}
#[allow(clippy::too_many_arguments)] // Separate immutable graph, query and work-policy inputs.
fn examples(
    g: &Graph,
    index: &Index,
    start: usize,
    end: usize,
    np: usize,
    scope: &str,
    limits: &FrameConnectionLimits,
    meter: &mut Meter<'_>,
) -> (Vec<ConnectionExample>, Option<ConnectionStop>) {
    if np == 1 {
        return (Vec::new(), None);
    }
    if limits.max_example_attempts == 0 {
        return (Vec::new(), Some(ConnectionStop::AttemptLimit));
    }
    let first = match bfs(g, index, start, end, None, limits, meter) {
        Ok(Some(p)) => p,
        Ok(None) => return (Vec::new(), None),
        Err(s) => return (Vec::new(), Some(s)),
    };
    let mut accepted = vec![first.clone()];
    let mut tried = BTreeSet::new();
    let mut attempts = 1;
    let mut stop = None;
    let mut bytes = first.len().saturating_add(1).saturating_mul(128);
    if bytes > limits.max_work_bytes {
        return (Vec::new(), Some(ConnectionStop::ByteLimit));
    }
    'search: while accepted.len() < np - 1 {
        let mut candidates = BTreeSet::new();
        for path in &accepted {
            for &excluded in path {
                if !tried.insert(excluded) {
                    continue;
                }
                if attempts >= limits.max_example_attempts {
                    stop = Some(ConnectionStop::AttemptLimit);
                    break 'search;
                }
                attempts += 1;
                match bfs(g, index, start, end, Some(excluded), limits, meter) {
                    Ok(Some(p)) if !accepted.contains(&p) => {
                        let added = p.len().saturating_add(1).saturating_mul(128);
                        if bytes
                            .checked_add(added)
                            .is_none_or(|n| n > limits.max_work_bytes)
                        {
                            stop = Some(ConnectionStop::ByteLimit);
                            break 'search;
                        }
                        bytes += added;
                        candidates.insert((p.len(), p));
                    }
                    Ok(_) => {}
                    Err(s) => {
                        stop = Some(s);
                        break 'search;
                    }
                }
            }
        }
        let Some((_, path)) = candidates.into_iter().next() else {
            break;
        };
        accepted.push(path);
    }
    if accepted.len() == np - 1 {
        stop = Some(ConnectionStop::CountBound);
    }
    let mut result = Vec::new();
    for (i, path) in accepted.into_iter().enumerate() {
        let edges: Vec<_> = path.into_iter().map(|e| g.edges[e].clone()).collect();
        let mut nodes = vec![g.nodes[start]];
        nodes.extend(edges.iter().map(|e| e.dst));
        let Ok(id) = digest(
            &("example/v1", scope, &nodes, &edges),
            limits.max_work_bytes,
        ) else {
            return (result, Some(ConnectionStop::ByteLimit));
        };
        result.push(ConnectionExample {
            id,
            nodes,
            edges,
            shortest_in_represented_graph: i == 0,
        });
    }
    (result, stop)
}

pub fn summarize_frame_connections(
    source: BoundFrameStructure,
    np: usize,
    limits: FrameConnectionLimits,
) -> Result<BoundFrameConnections, Error> {
    compute(source, np, limits, None)
}
pub(crate) fn replay_connections(
    source: BoundFrameStructure,
    expected: &FrameConnectionAnalysis,
) -> Result<BoundFrameConnections, Error> {
    let result = compute(
        source,
        expected.example_count_bound,
        expected.limits.clone(),
        Some(&expected.receipts),
    )?;
    if &result.analysis != expected {
        return Err(invalid(
            "connection assessment differs from deterministic replay",
        ));
    }
    Ok(result)
}
fn compute(
    source: BoundFrameStructure,
    np: usize,
    limits: FrameConnectionLimits,
    replay: Option<&ConnectionReceipts>,
) -> Result<BoundFrameConnections, Error> {
    limits.validate()?;
    if np == 0 || np > limits.max_count_bound {
        return Err(invalid("invalid connection example count bound"));
    }
    if let Some(r) = replay {
        for (receipt, cap) in [
            (&r.graph, limits.graph_work),
            (&r.forward, limits.reach_work),
            (&r.backward, limits.reach_work),
            (&r.scc, limits.scc_work),
            (&r.examples, limits.example_work),
        ] {
            if receipt.work > cap
                || receipt.stop == Some(ConnectionStop::Deadline)
                    && receipt.elapsed_ms < limits.deadline_ms
            {
                return Err(invalid("invalid connection work/clock receipt"));
            }
        }
    }
    let fingerprint = source_fingerprint(&source, limits.max_source_bytes)?;
    let scope = digest(
        &(ALGORITHM, &fingerprint, np, &limits),
        limits.max_source_bytes,
    )?;
    let q = source.question();
    let mut anchors = BTreeMap::new();
    let mut gaps = Vec::new();
    for frame in q.to_frame..=q.from_frame {
        match anchor(&source, frame) {
            Ok(n) => {
                anchors.insert(frame, n);
            }
            Err(reason) => gaps.push(format!("frame-{frame}:{reason}")),
        }
        if !source
            .frames()
            .iter()
            .any(|m| m.frame == frame && !m.auxiliary)
        {
            gaps.push(format!("frame-{frame}:missing-frame-map"));
        }
    }
    for caller in q.to_frame + 1..=q.from_frame {
        if !source
            .links()
            .iter()
            .any(|l| l.caller == caller && l.child == caller - 1 && l.admitted)
        {
            gaps.push(format!("frame-{caller}:missing-admitted-active-link"));
        }
    }
    let mut a=FrameConnectionAnalysis {
        algorithm:ALGORITHM.into(),source_fingerprint:fingerprint,scope_id:scope,conditional_on:source.hypothesis_ids(),
        from_frame:q.from_frame,to_frame:q.to_frame,example_count_bound:np,limits:limits.clone(),
        graph_status:ConnectionLayerStatus::WorkStopped,nodes:Vec::new(),edges:Vec::new(),context_edges:Vec::new(),frontiers:Vec::new(),
        start:anchors.get(&q.from_frame).cloned(),endpoint:anchors.get(&q.to_frame).cloned(),anchor_gaps:gaps,
        connection:RepresentedConnection::UnknownWorkStopped,corridor_status:ConnectionLayerStatus::Unavailable,
        forward:Vec::new(),backward:Vec::new(),corridor:Vec::new(),scc_status:ConnectionLayerStatus::Unavailable,
        components:Vec::new(),condensation:Vec::new(),examples_status:ExampleSearchStatus::Unavailable,examples:Vec::new(),receipts:ConnectionReceipts::default(),
        premises:vec!["All connections, SCCs and shortest guarantees are relative to the represented activation-qualified graph.".into(),
          "Unknown continuations, including forward-reachable frontiers outside the corridor, may reconnect.".into(),
          "Examples are loop-free structural witnesses; no exhaustive paths, executed history, feasibility, iteration count or writer exclusion is established.".into(),
          "Original capture, trusted lifting, unwind, local-normal-completion and conditional hypothesis premises remain in the source.".into()],
    };
    let mut meter = Meter::new(limits.graph_work, &limits, replay.map(|r| &r.graph));
    let mut g = match graph(&source, &limits, &mut meter, &anchors) {
        Ok(g) => {
            a.receipts.graph = meter.receipt(None);
            g
        }
        Err(stop) => {
            a.receipts.graph = meter.receipt(Some(stop));
            return Ok(BoundFrameConnections {
                source,
                analysis: a,
            });
        }
    };
    let index = match Index::bounded(&g, &mut meter) {
        Ok(index) => index,
        Err(stop) => {
            a.receipts.graph = meter.receipt(Some(stop));
            return Ok(BoundFrameConnections {
                source,
                analysis: a,
            });
        }
    };
    a.receipts.graph = meter.receipt(None);
    a.graph_status = ConnectionLayerStatus::CompleteForRepresentedGraph;
    for (name, n) in [("start", &a.start), ("endpoint", &a.endpoint)] {
        if n.as_ref().is_some_and(|n| !index.ids.contains_key(n)) {
            a.anchor_gaps.push(format!("{name}:anchor-not-admitted"));
        }
    }
    let mut scc = Meter::new(limits.scc_work, &limits, replay.map(|r| &r.scc));
    match components(&g, &index, &a.scope_id, &limits, &mut scc) {
        Ok((cs, es)) => {
            a.components = cs;
            a.condensation = es;
            a.scc_status = ConnectionLayerStatus::CompleteForRepresentedGraph;
            a.receipts.scc = scc.receipt(None);
        }
        Err(stop) => {
            a.scc_status = ConnectionLayerStatus::WorkStopped;
            a.receipts.scc = scc.receipt(Some(stop));
        }
    }
    if a.anchor_gaps.is_empty() {
        let start = index.ids[a.start.as_ref().expect("validated anchor")];
        let end = index.ids[a.endpoint.as_ref().expect("validated endpoint")];
        let mut fw = Meter::new(limits.reach_work, &limits, replay.map(|r| &r.forward));
        let (f, fs) = reachable(&g, &index, start, false, &mut fw);
        a.receipts.forward = fw.receipt(fs);
        let mut bw = Meter::new(limits.reach_work, &limits, replay.map(|r| &r.backward));
        let (b, bs) = reachable(&g, &index, end, true, &mut bw);
        a.receipts.backward = bw.receipt(bs);
        let mut ex = Meter::new(limits.example_work, &limits, replay.map(|r| &r.examples));
        let (ps, es) = examples(&g, &index, start, end, np, &a.scope_id, &limits, &mut ex);
        a.examples = ps;
        a.receipts.examples = ex.receipt(es);
        a.examples_status = if es.is_some_and(|s| s != ConnectionStop::CountBound) {
            ExampleSearchStatus::WorkStopped
        } else {
            ExampleSearchStatus::Finished
        };
        a.connection = if f.contains(&end) || b.contains(&start) || !a.examples.is_empty() {
            RepresentedConnection::Found
        } else if fs.is_none() || bs.is_none() {
            RepresentedConnection::AbsentInRepresentedGraph
        } else {
            RepresentedConnection::UnknownWorkStopped
        };
        if fs.is_none() {
            a.forward = f.iter().map(|i| g.nodes[*i]).collect();
        }
        if bs.is_none() {
            a.backward = b.iter().map(|i| g.nodes[*i]).collect();
        }
        a.corridor_status = if fs.is_none() && bs.is_none() {
            a.corridor = f.intersection(&b).map(|i| g.nodes[*i]).collect();
            ConnectionLayerStatus::CompleteForRepresentedGraph
        } else {
            ConnectionLayerStatus::WorkStopped
        };
        classify_frontiers(&mut g, &index, &a.corridor, &a.forward, fs.is_none());
    } else {
        a.connection = RepresentedConnection::UnavailableAnchors;
    }
    a.nodes = g.nodes;
    a.edges = g.edges;
    a.context_edges = g.context;
    a.frontiers = g.frontiers;
    Ok(BoundFrameConnections {
        source,
        analysis: a,
    })
}

#[cfg(test)]
#[path = "../../tests/investigation/frame_connections.rs"]
mod tests;

fn classify_frontiers(
    g: &mut Graph,
    index: &Index,
    corridor: &[FramePathNode],
    forward: &[FramePathNode],
    forward_complete: bool,
) {
    for frontier in &mut g.frontiers {
        let n = FramePathNode {
            frame: frontier.frame,
            site: frontier.gap.site,
        };
        frontier.relation = if corridor.binary_search(&n).is_ok() {
            FrontierRelation::OnCorridor
        } else if forward.binary_search(&n).is_ok() {
            FrontierRelation::ForwardReachable
        } else if forward_complete && index.ids.contains_key(&n) {
            FrontierRelation::OtherRegion
        } else {
            FrontierRelation::Unclassified
        };
    }
}
