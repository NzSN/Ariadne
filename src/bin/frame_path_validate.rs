//! F4 original-capture qualification using public bounded-path and replay APIs.
use ariadne::bap::{
    core_adapter::{NativeAnalyzer, encode_request},
    core_session::CoreConfig,
};
use ariadne::input::{FileSnapshot, FramePreparation, OpenLimits, PrepareLimits};
use ariadne::investigation::{
    CapturedFrameChain, FramePathGraphLimits, FramePathLimits, FramePathListing, FramePathQuestion,
    FrameRecoveryLimits, bind_frame_paths_with_limits, list_frame_paths,
};
use ariadne::*;
use serde_json::{Value, json};
use std::error::Error;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const ORIGINAL_SHA256: &str = "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab";
const NORMALIZED_SHA256: [&str; 2] = [
    "9de5f240615225de915605c7af0b76c31dbc67ba9d82061522b77c2328c22a4f",
    "6b5afebea31cff34103ddb38e4bf795ce63660eb9eb375804aff8a340a4bed22",
];
const MAX_REPORT_BYTES: usize = 512 * 1024 * 1024;

fn read_bounded(path: &Path, max_bytes: usize) -> Result<Vec<u8>, Box<dyn Error>> {
    let file = std::fs::File::open(path)?;
    if file.metadata()?.len() > max_bytes as u64 {
        return Err("input exceeds byte budget".into());
    }
    let mut bytes = Vec::new();
    file.take(max_bytes as u64 + 1).read_to_end(&mut bytes)?;
    if bytes.len() > max_bytes {
        return Err("input exceeds byte budget".into());
    }
    Ok(bytes)
}

fn assert_original_scope(
    chain: &CapturedFrameChain,
    question: &FramePathQuestion,
) -> Result<(), Box<dyn Error>> {
    if chain.artifact_sha256 != ORIGINAL_SHA256
        || chain.thread_id != 23668
        || question.from_frame != 1
        || question.to_frame != 0
        || question.np != 10
    {
        return Err("original artifact/thread/frame question differs".into());
    }
    for (index, pc, entry) in [
        (0, 0x0000_7ff7_7443_dd6e, 0x0000_7ff7_7443_d960),
        (1, 0x0000_7ff7_7440_410d, 0x0000_7ff7_7440_33a0),
    ] {
        let frame = chain.frames.get(index).ok_or("original frame missing")?;
        if frame.index != index || frame.pc != pc || frame.function_begin != Some(entry) {
            return Err("original frame PC/entry differs".into());
        }
    }
    Ok(())
}

fn assert_original_listing(listing: &FramePathListing) -> Result<(), Box<dyn Error>> {
    assert_original_scope(listing.frame_chain(), &listing.question)?;
    if !listing.available || !(1..10).contains(&listing.returned_count) {
        return Err("original full-dump positive path gate not met".into());
    }
    Ok(())
}

fn run() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if !matches!(args.first().map(String::as_str), Some("dump") if args.len() == 3)
        && !matches!(args.first().map(String::as_str), Some("replay") if args.len() == 4)
    {
        return Err("usage: frame-path-validate dump INPUT OUTPUT | replay INPUT OUTPUT EXPECTED_REPORT_SHA256".into());
    }
    let out = PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out)?;
    if args[0] == "replay" {
        if args[3].len() != 64 || !args[3].bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("expected report SHA-256 must contain 64 hexadecimal digits".into());
        }
        let bytes = read_bounded(Path::new(&args[1]), MAX_REPORT_BYTES)?;
        let report_sha256 = ariadne::reports::sha256(&bytes);
        if !report_sha256.eq_ignore_ascii_case(&args[3]) {
            return Err("sealed original report SHA differs".into());
        }
        let listing = ariadne::reports::decode_frame_paths_with_policy(
            &bytes,
            MAX_REPORT_BYTES,
            &FramePathGraphLimits {
                max_graph_nodes: 16384,
                max_graph_edges: 65536,
            },
        )?;
        assert_original_listing(&listing)?;
        for (name, format) in [
            ("json", ariadne::reports::Format::Json),
            ("txt", ariadne::reports::Format::Text),
            ("dot", ariadne::reports::Format::Dot),
        ] {
            std::fs::write(
                out.join(format!("replay.{name}")),
                ariadne::reports::render_frame_paths(&listing, format)?,
            )?;
        }
        std::fs::write(
            out.join("summary.json"),
            serde_json::to_vec_pretty(
                &json!({"passed":true,"returned_count":listing.returned_count,"coverage":listing.coverage,"gaps":listing.gaps.len(),"schema":listing.schema,"source_sha256":report_sha256}),
            )?,
        )?;
        return Ok(());
    }
    if args[0] != "dump" {
        return Err("unknown mode".into());
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut core = CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .ok_or("native helper directory")?,
    );
    core.timeout = Duration::from_secs(600);
    core.max_request_bytes = 128 * 1024 * 1024;
    let snapshot = FileSnapshot::open_minidump(
        &args[1],
        OpenLimits {
            max_file_bytes: 2 * 1024 * 1024 * 1024,
            max_read_bytes: 32 * 1024 * 1024,
            ..Default::default()
        },
    )?;
    if snapshot.metadata().artifact_sha256 != ORIGINAL_SHA256 {
        return Err("original dump SHA differs".into());
    }
    let thread = snapshot
        .metadata()
        .exception
        .as_ref()
        .ok_or("missing exception")?
        .thread_id;
    let chain = snapshot.recover_thread_frames(
        thread,
        FrameRecoveryLimits {
            max_frames: 6,
            max_runtime_entries: 440520,
            max_read_bytes: 6334816,
            ..Default::default()
        },
    )?;
    snapshot.validate_thread_frames(&chain)?;
    let question = FramePathQuestion {
        from_frame: 1,
        to_frame: 0,
        np: 10,
    };
    assert_original_scope(&chain, &question)?;
    let config = ariadne::bap::Config::from_env();
    let options = ariadne::effects::PreparationOptions::default();
    let decoder = root.join("target/ariadne-llvm-mc");
    let setup = FramePreparation {
        decoder: &decoder,
        config: &config,
        options: &options,
        limits: PrepareLimits {
            max_starts: 16384,
            max_candidates: 32768,
            max_prefix_bytes: 16384 * 15,
            max_decoder_batches: 16384,
            batch_size: 128,
        },
    };
    let guard = ariadne::bap::guard_admission::Limits {
        max_sites: 32768,
        max_edges: 131072,
        max_residue_updates: 4194304,
        max_transfer_evaluations: 67108864,
        max_closure_rounds: 32768,
        max_evidence_bytes: 64 * 1024 * 1024,
        max_elapsed_ms: 120000,
    };
    let target = ariadne::bap::target_resolution::Limits {
        max_entries: 16384,
        max_targets: 65536,
        max_read_bytes: 16 * 1024 * 1024,
        max_evidence_bytes: 128 * 1024 * 1024,
        max_values: 4096,
        max_steps: 2097152,
        max_path_steps: 512,
        max_rounds: 64,
        max_elapsed_ms: 120000,
    };
    let limits = FramePathLimits {
        max_graph_nodes: 16384,
        max_graph_edges: 65536,
        max_search_states: 1000000,
        max_scanned_edges: 4194304,
        max_path_steps: 32,
        max_node_visits: 2,
        max_frontier_bytes: 128 * 1024 * 1024,
        max_output_bytes: 512 * 1024 * 1024,
        deadline_ms: 30000,
    };
    let mut native_queries = Vec::new();
    let mut rust_queries = Vec::new();
    let mut summaries = Vec::new();
    std::fs::write(out.join("chain.json"), serde_json::to_vec_pretty(&chain)?)?;
    for frame in [1, 0] {
        eprintln!("PREPARE frame {frame}");
        let entry = chain.frames[frame]
            .function_begin
            .ok_or("missing original frame entry")?;
        let prepared = snapshot
            .prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(
                &chain,
                frame,
                entry,
                &setup,
                guard.clone(),
                target.clone(),
            )?;
        let request = prepared.prepared.request.clone();
        let expected = read_bounded(
            &root.join(format!("target/original-frame{frame}-normalized.json")),
            16 * 1024 * 1024,
        )?;
        if ariadne::reports::sha256(&expected) != NORMALIZED_SHA256[frame] {
            return Err("sealed S6 normalized reference SHA differs".into());
        }
        if serde_json::from_slice::<Value>(&expected)? != encode_request(&request)? {
            return Err("original normalized request changed".into());
        }
        let native = NativeAnalyzer::from_capture(&core, &format!("frame-f4-{frame}"), &prepared)?
            .complete()?;
        let (reference, metrics) =
            Analyzer::new(request.clone())?.finish_bounded(CompletionLimits::default())?;
        if native.request() != &request || native.state() != &reference.state {
            return Err("full native/Rust completed state mismatch".into());
        }
        let rust = CompletedAnalysis::from_analyzer(Analyzer::new(request)?);
        if rust.state() != &reference.state {
            return Err("completed reference carrier mismatch".into());
        }
        summaries.push(json!({"frame":frame,"full_state_equal":true,"original_request_equal":true,
            "decoded":reference.state.decoded.len(),"edges":reference.state.edges.len(),
            "definition_links":reference.state.reaching.values().map(DefinitionSet::len).sum::<usize>(),"actions":metrics.actions}));
        drop(reference);
        eprintln!("BIND frame {frame}");
        native_queries.push((
            frame,
            ariadne::input::investigation::bind_investigation(&prepared, &native)?,
        ));
        rust_queries.push((
            frame,
            ariadne::input::investigation::bind_investigation(&prepared, &rust)?,
        ));
        std::fs::write(
            out.join("completion.json"),
            serde_json::to_vec_pretty(&summaries)?,
        )?;
    }
    let native = bind_frame_paths_with_limits(chain.clone(), native_queries, &limits)?;
    let rust = bind_frame_paths_with_limits(chain, rust_queries, &limits)?;
    let mut results = Vec::new();
    let mut native_value = None;
    for (name, bound) in [("native", &native), ("rust", &rust)] {
        eprintln!("ENUMERATE {name}");
        let began = Instant::now();
        let listing = list_frame_paths(bound, question.clone(), limits.clone())?;
        listing.validate_for(bound)?;
        assert_original_listing(&listing)?;
        let mut value = serde_json::to_value(&listing)?;
        value["elapsed_ms"] = json!(0);
        if let Some(expected) = native_value.as_ref() {
            if expected != &value {
                return Err("native/Rust path products differ".into());
            }
        } else {
            native_value = Some(value);
        }
        for (extension, format) in [
            ("json", ariadne::reports::Format::Json),
            ("txt", ariadne::reports::Format::Text),
            ("dot", ariadne::reports::Format::Dot),
        ] {
            std::fs::write(
                out.join(format!("{name}.{extension}")),
                ariadne::reports::render_frame_paths(&listing, format)?,
            )?;
        }
        results.push(json!({"backend":name,"available":listing.available,"returned_count":listing.returned_count,"coverage":listing.coverage,
            "truncated":listing.truncated,"enumeration_exhausted":listing.enumeration_exhausted,"stop_reason":listing.stop_reason,
            "gaps":listing.gaps.len(),"counters":listing.counters,"seconds":began.elapsed().as_secs_f64()}));
        std::fs::write(
            out.join("summary.json"),
            serde_json::to_vec_pretty(&results)?,
        )?;
    }
    println!("{}", json!({"passed":true,"results":results}));
    Ok(())
}
fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
