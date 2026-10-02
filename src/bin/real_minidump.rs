#![allow(unsafe_code)] // Existing benchmark-only allocation counters.
//! Stage timings and core work counters for one frozen real minidump query.
use ariadne::Analyzer;
use ariadne::effects::PreparationOptions;
use ariadne::input::report::{ReportFormat, render};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::alloc::{GlobalAlloc, Layout, System};
use std::collections::BTreeSet;
use std::error::Error;
use std::path::Path;
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

fn parse_va(text: &str) -> Result<u64, Box<dyn Error>> {
    let digits = text
        .strip_prefix("0x")
        .or_else(|| text.strip_prefix("0X"))
        .unwrap_or(text);
    Ok(u64::from_str_radix(digits, 16)?)
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 5 {
        return Err("usage: real_minidump DUMP DECODER ENTRY_HEX SEED_HEX RUNS".into());
    }
    let dump = Path::new(&args[0]);
    let decoder = Path::new(&args[1]);
    let entry = parse_va(&args[2])?;
    let seed = parse_va(&args[3])?;
    let runs: usize = args[4].parse()?;
    if runs == 0 {
        return Err("RUNS must be positive".into());
    }
    println!(
        "workload,artifact_sha256,entry_va,seed_va,run,open_ns,prepare_ns,analysis_ns,render_ns,total_ns,allocations,allocated_bytes,actions,incoming_evaluations,edge_scans,transfer_evaluations,max_reaching_at_site,total_reaching,decoded,edges,slice,obligations,output_bytes"
    );
    for run in 0..runs {
        let allocation_start = ALLOCATIONS.load(Ordering::Relaxed);
        let bytes_start = ALLOCATED_BYTES.load(Ordering::Relaxed);
        let start = Instant::now();
        let snapshot = FileSnapshot::open_minidump(dump, OpenLimits::default())?;
        let open_ns = start.elapsed().as_nanos();
        let artifact_sha256 = snapshot.metadata().artifact_sha256.clone();
        let exception_seed = snapshot
            .metadata()
            .exception
            .as_ref()
            .and_then(|exception| exception.registers.get("rip"))
            == Some(&seed);

        let prepared = snapshot.prepare(
            &AnalysisQuery {
                entry_points: [entry].into(),
                slice_seeds: [seed].into(),
            },
            decoder,
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )?;
        let prepare_ns = start.elapsed().as_nanos() - open_ns;

        let mut analyzer = Analyzer::new(prepared.prepared.request.clone())?;
        while analyzer.step() {}
        let metrics = analyzer.metrics();
        let result = analyzer.finish();
        let analysis_ns = start.elapsed().as_nanos() - open_ns - prepare_ns;

        let outputs = [ReportFormat::Text, ReportFormat::Dot, ReportFormat::Json]
            .into_iter()
            .map(|format| render(&prepared, &result, format, exception_seed))
            .collect::<Result<Vec<_>, _>>()?;
        let output_bytes: usize = outputs.iter().map(String::len).sum();
        let total_ns = start.elapsed().as_nanos();
        let render_ns = total_ns - open_ns - prepare_ns - analysis_ns;
        let allocations = ALLOCATIONS.load(Ordering::Relaxed) - allocation_start;
        let allocated_bytes = ALLOCATED_BYTES.load(Ordering::Relaxed) - bytes_start;
        let state = &result.state;
        let total_reaching: usize = state.reaching.values().map(BTreeSet::len).sum();
        println!(
            "real_minidump,{artifact_sha256},0x{entry:016x},0x{seed:016x},{run},{open_ns},{prepare_ns},{analysis_ns},{render_ns},{total_ns},{allocations},{allocated_bytes},{},{},{},{},{},{total_reaching},{},{},{},{},{output_bytes}",
            metrics.actions,
            metrics.incoming_evaluations,
            metrics.edge_scans,
            metrics.transfer_evaluations,
            metrics.max_reaching_definitions_at_site,
            state.decoded.len(),
            state.edges.len(),
            state.slice.len(),
            state.obligations.len(),
        );
        std::hint::black_box(outputs);
    }
    Ok(())
}
