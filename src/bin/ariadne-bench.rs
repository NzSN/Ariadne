#![allow(unsafe_code)] // Existing benchmark-only allocation counters.
//! Repeatable operation-count and allocation baseline for the recovery core.
use ariadne::effects::PreparationOptions;
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::{AddressSet, AnalysisRequest, Analyzer, Instruction, InstructionKind};
use std::alloc::{GlobalAlloc, Layout, System};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

struct CountingAllocator;
static ALLOCATIONS: AtomicU64 = AtomicU64::new(0);
static ALLOCATED_BYTES: AtomicU64 = AtomicU64::new(0);
#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size() as u64, Ordering::Relaxed);
        unsafe { System.alloc_zeroed(layout) }
    }
    unsafe fn realloc(&self, pointer: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(new_size as u64, Ordering::Relaxed);
        unsafe { System.realloc(pointer, layout, new_size) }
    }
    unsafe fn dealloc(&self, pointer: *mut u8, layout: Layout) {
        unsafe { System.dealloc(pointer, layout) }
    }
}

fn request(kind: &str, n: usize) -> AnalysisRequest {
    let va = |i: usize| 0x1000_u64 + (i as u64) * 16;
    let extra_call = va(n + 1);
    let mut addresses: AddressSet = (0..n).map(va).collect();
    let mut file_backed = addresses.clone();
    let mut decodable = addresses.clone();
    let mut locations: BTreeSet<_> = (0..if kind == "dense" { 128 } else { 16 })
        .map(|i| format!("loc:{i}"))
        .collect();
    locations.insert("memory:any".into());
    let mut instructions = BTreeMap::new();
    for i in 0..n {
        let site = va(i);
        let mut instruction = Instruction {
            kind: if i + 1 == n {
                InstructionKind::Return
            } else {
                InstructionKind::Ordinary
            },
            ..Instruction::default()
        };
        if i + 1 < n {
            instruction.fall.insert(va(i + 1));
        }
        let loc = if kind == "dense" {
            "memory:any".into()
        } else {
            format!("loc:{}", i % 16)
        };
        instruction.uses.insert(loc.clone());
        instruction.may_defs.insert(loc.clone());
        if kind != "dense" {
            instruction.must_defs.insert(loc);
        }
        if kind == "loops" && i > 0 && i % 16 == 0 {
            instruction.kind = InstructionKind::Conditional;
            instruction.targets.insert(va(i - 16));
        }
        if kind == "joins" && i + 2 < n && i % 4 == 0 {
            instruction.kind = InstructionKind::Conditional;
            instruction.targets.insert(va(i + 2));
        }
        if kind == "calls" && i + 1 < n && i % 8 == 0 {
            instruction.kind = InstructionKind::Call;
            instruction.targets.insert(extra_call);
            instruction.complete = false;
        }
        instructions.insert(site, instruction);
    }
    if kind == "calls" {
        addresses.insert(extra_call);
        instructions.insert(extra_call, Instruction::default());
    }
    AnalysisRequest {
        snapshot_id: format!("bench-{kind}-{n}"),
        addresses,
        locations,
        entry_points: [va(0)].into(),
        slice_seeds: [va(n - 1)].into(),
        file_backed: std::mem::take(&mut file_backed),
        decodable: std::mem::take(&mut decodable),
        instructions,
        ..AnalysisRequest::default()
    }
}
fn parse_positive(text: Option<&String>, default: usize) -> usize {
    text.map(|s| s.parse::<usize>().expect("positive integer"))
        .unwrap_or(default)
        .max(1)
}
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let n = parse_positive(args.first(), 128);
    let repeats = parse_positive(args.get(1), 3);
    println!(
        "workload,n,run,elapsed_ns,allocations,allocated_bytes,actions,incoming_evaluations,edge_scans,transfer_evaluations,max_reaching_at_site,total_reaching,decoded,edges,slice,obligations"
    );
    for kind in ["linear", "loops", "joins", "calls", "dense"] {
        for run in 0..repeats {
            let input = request(kind, n);
            let alloc_before = ALLOCATIONS.load(Ordering::Relaxed);
            let bytes_before = ALLOCATED_BYTES.load(Ordering::Relaxed);
            let start = Instant::now();
            let mut analyzer = Analyzer::new(input).expect("benchmark request contract");
            while analyzer.step() {}
            let elapsed = start.elapsed().as_nanos();
            let metrics = analyzer.metrics();
            let allocations = ALLOCATIONS.load(Ordering::Relaxed) - alloc_before;
            let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed) - bytes_before;
            let state = analyzer.state();
            let total_reaching: usize = state.reaching.values().map(BTreeSet::len).sum();
            let decoded = state.decoded.len();
            let edges = state.edges.len();
            let slice = state.slice.len();
            let obligations = state.obligations.len();
            std::hint::black_box(analyzer);
            println!(
                "{kind},{n},{run},{elapsed},{allocations},{bytes},{},{},{},{},{},{total_reaching},{decoded},{edges},{slice},{obligations}",
                metrics.actions,
                metrics.incoming_evaluations,
                metrics.edge_scans,
                metrics.transfer_evaluations,
                metrics.max_reaching_definitions_at_site
            );
        }
    }
    if args.get(2).map(String::as_str) == Some("minidump") {
        let decoder = std::env::var_os("ARIADNE_LLVM_MC")
            .expect("set ARIADNE_LLVM_MC for minidump benchmark");
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("tests/input/fixtures/stage_b_windows.dmp");
        for run in 0..repeats {
            let alloc_before = ALLOCATIONS.load(Ordering::Relaxed);
            let bytes_before = ALLOCATED_BYTES.load(Ordering::Relaxed);
            let start = Instant::now();
            let snapshot = FileSnapshot::open_minidump(&path, OpenLimits::default()).unwrap();
            let prepared = snapshot
                .prepare(
                    &AnalysisQuery {
                        entry_points: [0x7ff700001000].into(),
                        slice_seeds: [0x7ff700001006].into(),
                    },
                    std::path::Path::new(&decoder),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                )
                .unwrap();
            let mut analyzer = Analyzer::new(prepared.prepared.request).unwrap();
            while analyzer.step() {}
            let elapsed = start.elapsed().as_nanos();
            let metrics = analyzer.metrics();
            let allocations = ALLOCATIONS.load(Ordering::Relaxed) - alloc_before;
            let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed) - bytes_before;
            let state = analyzer.state();
            let total_reaching: usize = state.reaching.values().map(BTreeSet::len).sum();
            println!(
                "minidump,4,{run},{elapsed},{allocations},{bytes},{},{},{},{},{},{total_reaching},{},{},{},{}",
                metrics.actions,
                metrics.incoming_evaluations,
                metrics.edge_scans,
                metrics.transfer_evaluations,
                metrics.max_reaching_definitions_at_site,
                state.decoded.len(),
                state.edges.len(),
                state.slice.len(),
                state.obligations.len()
            );
            std::hint::black_box(analyzer);
        }
    }
}
