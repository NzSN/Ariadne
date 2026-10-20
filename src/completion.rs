//! Completion-only, lossless fixed-point storage and scheduling. Ordinary
//! `Analyzer::step` retains the historical least-address action schedule.
use crate::engine::AnalyzerMetrics;
use crate::model::*;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::sync::Arc;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug)]
pub struct CompletionLimits {
    pub max_actions: u64,
    /// Total words for one membership plane; the solver owns two planes.
    pub max_bitmap_words: usize,
    pub max_definitions: usize,
    pub max_definition_bytes: usize,
    pub max_elapsed: Duration,
}
impl Default for CompletionLimits {
    fn default() -> Self {
        Self {
            max_actions: 1_000_000,
            max_bitmap_words: 32 * 1024 * 1024,
            max_definitions: 1_000_000,
            max_definition_bytes: 64 * 1024 * 1024,
            max_elapsed: Duration::from_secs(600),
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CompletionError {
    pub reason: &'static str,
    pub actions: u64,
}
impl fmt::Display for CompletionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "completion stopped: {} after {} actions",
            self.reason, self.actions
        )
    }
}
impl std::error::Error for CompletionError {}

pub(crate) fn check(
    limits: CompletionLimits,
    started: Instant,
    actions: u64,
) -> Result<(), CompletionError> {
    let reason = if actions >= limits.max_actions {
        Some("action budget")
    } else if started.elapsed() >= limits.max_elapsed {
        Some("deadline")
    } else {
        None
    };
    match reason {
        Some(reason) => Err(CompletionError { reason, actions }),
        None => Ok(()),
    }
}

pub(crate) fn dataflow(
    request: &AnalysisRequest,
    state: &mut AnalysisState,
    metrics: &mut AnalyzerMetrics,
    limits: CompletionLimits,
    started: Instant,
) -> Result<(), CompletionError> {
    let error = |reason| CompletionError {
        reason,
        actions: metrics.actions,
    };
    let addresses: Vec<_> = state.decoded.iter().copied().collect();
    let indices: BTreeMap<_, _> = addresses.iter().enumerate().map(|(n, a)| (*a, n)).collect();
    let mut universe = BTreeSet::new();
    let mut definition_bytes = 0usize;
    for &a in &addresses {
        check(limits, started, metrics.actions)?;
        for loc in &request.instructions[&a].may_defs {
            definition_bytes = definition_bytes
                .checked_add(loc.len())
                .ok_or_else(|| error("definition bytes overflow"))?;
            if definition_bytes > limits.max_definition_bytes {
                return Err(error("definition bytes budget"));
            }
            universe.insert(Definition {
                loc: loc.clone(),
                site: a,
                origin: DefinitionOrigin::Instruction,
            });
        }
        if request.entry_points.contains(&a) {
            for loc in &request.locations {
                definition_bytes = definition_bytes
                    .checked_add(loc.len())
                    .ok_or_else(|| error("definition bytes overflow"))?;
                if definition_bytes > limits.max_definition_bytes {
                    return Err(error("definition bytes budget"));
                }
                universe.insert(Definition {
                    loc: loc.clone(),
                    site: a,
                    origin: DefinitionOrigin::Entry,
                });
            }
        }
        if universe.len() > limits.max_definitions {
            return Err(error("definition universe budget"));
        }
    }
    let universe: Arc<[Definition]> = universe.into_iter().collect();
    let words = universe.len().div_ceil(64);
    if words
        .checked_mul(addresses.len())
        .is_none_or(|n| n > limits.max_bitmap_words)
    {
        return Err(error("bitmap budget"));
    }
    let mut successors = vec![Vec::new(); addresses.len()];
    for edge in &state.edges {
        if edge.kind.is_local() {
            if let (Some(&a), Some(&b)) = (indices.get(&edge.src), indices.get(&edge.dst)) {
                successors[a].push(b);
            }
        }
    }
    for row in &mut successors {
        row.sort_unstable();
        row.dedup();
    }
    // Iterative DFS: graph depth never consumes the call stack.
    let mut seen = vec![false; addresses.len()];
    let mut post = Vec::with_capacity(addresses.len());
    for root in 0..addresses.len() {
        if seen[root] {
            continue;
        }
        let mut stack = vec![(root, false)];
        while let Some((a, exit)) = stack.pop() {
            if exit {
                post.push(a);
                continue;
            }
            if seen[a] {
                continue;
            }
            seen[a] = true;
            stack.push((a, true));
            for &b in successors[a].iter().rev() {
                if !seen[b] {
                    stack.push((b, false));
                }
            }
        }
    }
    let mut rank = vec![0; addresses.len()];
    for (n, a) in post.into_iter().rev().enumerate() {
        rank[a] = n;
    }
    let mut location_ranges: BTreeMap<&str, (usize, usize)> = BTreeMap::new();
    for (n, d) in universe.iter().enumerate() {
        location_ranges
            .entry(&d.loc)
            .and_modify(|r| r.1 = n + 1)
            .or_insert((n, n + 1));
    }
    let mut values = vec![vec![0u64; words]; addresses.len()];
    let mut outgoing = vec![vec![0u64; words]; addresses.len()];
    let mut kills = vec![Vec::new(); addresses.len()];
    for (a, &va) in addresses.iter().enumerate() {
        check(limits, started, metrics.actions)?;
        for d in &state.reaching[&va] {
            let n = universe
                .binary_search(d)
                .map_err(|_| error("prefix definition outside universe"))?;
            values[a][n / 64] |= 1 << (n % 64);
        }
        outgoing[a].copy_from_slice(&values[a]);
        for loc in &request.instructions[&va].must_defs {
            if let Some(&(begin, end)) = location_ranges.get(loc.as_str()) {
                for (word, value) in outgoing[a]
                    .iter_mut()
                    .enumerate()
                    .take(end.div_ceil(64))
                    .skip(begin / 64)
                {
                    let low = begin.saturating_sub(word * 64).min(64);
                    let high = (end - word * 64).min(64);
                    let mask = (u64::MAX.checked_shl(low as u32).unwrap_or(0))
                        & (u64::MAX.checked_shr((64 - high) as u32).unwrap_or(0));
                    kills[a].push((word, mask));
                    *value &= !mask;
                }
            }
        }
        for loc in &request.instructions[&va].may_defs {
            let d = Definition {
                loc: loc.clone(),
                site: va,
                origin: DefinitionOrigin::Instruction,
            };
            let n = universe.binary_search(&d).expect("generated universe");
            outgoing[a][n / 64] |= 1 << (n % 64);
        }
    }
    // Entry facts and every predecessor's generated/previous outgoing facts
    // are available before the first new Propagate, exactly as in Incoming.
    for (a, &va) in addresses.iter().enumerate() {
        if request.entry_points.contains(&va) {
            for loc in &request.locations {
                let d = Definition {
                    loc: loc.clone(),
                    site: va,
                    origin: DefinitionOrigin::Entry,
                };
                let n = universe.binary_search(&d).expect("entry universe");
                values[a][n / 64] |= 1 << (n % 64);
            }
        }
        for &b in &successors[a] {
            for (dest, source) in values[b].iter_mut().zip(&outgoing[a]) {
                *dest |= source;
            }
        }
    }
    let mut ready = BTreeSet::new();
    for (a, &va) in addresses.iter().enumerate() {
        let count: usize = values[a].iter().map(|w| w.count_ones() as usize).sum();
        if count > state.reaching[&va].len() {
            ready.insert((rank[a], a));
        }
    }
    let mut delta = vec![0u64; words];
    while let Some((_, a)) = ready.pop_first() {
        check(limits, started, metrics.actions)?;
        metrics.actions += 1;
        delta.copy_from_slice(&values[a]);
        for &(word, mask) in &kills[a] {
            delta[word] &= !mask;
        }
        // GEN is already in outgoing; it cannot be killed by a must-def.
        for (d, out) in delta.iter_mut().zip(outgoing[a].iter_mut()) {
            *d &= !*out;
            *out |= *d;
        }
        for &b in &successors[a] {
            let mut changed = false;
            for (dest, d) in values[b].iter_mut().zip(&delta) {
                changed |= d & !*dest != 0;
                *dest |= d;
            }
            if changed {
                ready.insert((rank[b], b));
            }
            metrics.edge_scans += 1;
            metrics.incoming_evaluations += 1;
            metrics.transfer_evaluations += 1;
        }
    }
    check(limits, started, metrics.actions)?;
    for (a, row) in addresses.into_iter().zip(values) {
        let set = DefinitionSet::from_dense(universe.clone(), row);
        metrics.max_reaching_definitions_at_site =
            metrics.max_reaching_definitions_at_site.max(set.len());
        state.reaching.insert(a, set);
    }
    Ok(())
}
