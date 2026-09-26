//! Inspection example; no symbol/module files are opened implicitly.
use ariadne::effects::PreparationOptions;
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let path = args
        .next()
        .ok_or("usage: inspect DUMP [DECODER ROOT_VA_HEX]")?;
    let snapshot = FileSnapshot::open_minidump(path, OpenLimits::default())?;
    println!(
        "snapshot={} platform={:?} modules={} threads={} metadata_gaps={}",
        snapshot.metadata().snapshot_id,
        snapshot.metadata().platform,
        snapshot.metadata().modules.len(),
        snapshot.metadata().threads.len(),
        snapshot.metadata().gaps.len()
    );
    if let Some(e) = &snapshot.metadata().exception {
        println!(
            "exception_thread={} code={:#x} reported_address={:#x} rip={:?}",
            e.thread_id,
            e.code,
            e.reported_address,
            e.registers.get("rip")
        );
    }
    if let Some(decoder) = args.next() {
        let root = args.next().ok_or("explicit hexadecimal root required")?;
        let va = u64::from_str_radix(root.trim_start_matches("0x"), 16)?;
        let p = snapshot.prepare(
            &AnalysisQuery {
                entry_points: [va].into(),
                slice_seeds: [va].into(),
            },
            std::path::Path::new(&decoder),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )?;
        println!(
            "attempted={} read_bytes={} decoder_batches={} preparation_gaps={}",
            p.materialization.attempted.len(),
            p.materialization.prefix_bytes,
            p.materialization.decoder_batches,
            p.prepared.gaps.len()
        );
        let r = ariadne::analyze(p.prepared.request)?;
        println!(
            "decoded={} edges={} obligations={} missing_seeds={}",
            r.state.decoded.len(),
            r.state.edges.len(),
            r.state.obligations.len(),
            r.missing_slice_seeds.len()
        );
    }
    Ok(())
}
