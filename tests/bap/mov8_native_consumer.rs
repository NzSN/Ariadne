//! Native consumption of the selected 640 register-byte MOV encodings.
//!
//! Expected aliases and byte origins come from raw encoding fields, without
//! calling the projection or its register parser. Captures use both actual
//! minidump target profiles. Each independent root executes MOV8, a full-width
//! register consumer, then RET. These are analysis inputs, not execution traces.
//!
//! The plain native capture contract trusts reader-produced normalized effects.
//! Its structural refusal controls do not establish independent native decoding
//! or rejection of a self-consistent forged semantic summary.
use crate::bap::core_adapter::NativeAnalyzer;
use crate::bap::core_protocol::{CAPTURED_PROFILE, profile_query_digest};
use crate::bap::core_session::{CoreConfig, CoreSession};
use crate::bap::{Config, Session};
use crate::effects::{EffectQuality, PreparationOptions};
use crate::input::{AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{
    Address, AddressSet, AnalysisView, Analyzer, ByteSource, CompletedAnalysis, Definition,
    DefinitionOrigin, Edge, EdgeKind, InstructionKind, LocationSet, Phase,
};
use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

// The input module's copy is private; keep this test-only fixture import local.
#[allow(clippy::duplicate_mod)]
#[path = "../input/common/mod.rs"]
mod common;

#[path = "mov8_address_size_guard.rs"]
mod address_size_guard;

#[path = "mov8_memory_native_consumer.rs"]
mod memory;

const BANKS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];
const PREFIXES: [Option<u8>; 5] = [None, Some(0x40), Some(0x41), Some(0x44), Some(0x45)];
const LEGACY_BYTES: [(usize, usize); 8] = [
    (0, 0),
    (1, 0),
    (2, 0),
    (3, 0),
    (0, 1),
    (1, 1),
    (2, 1),
    (3, 1),
];

#[derive(Clone, Debug)]
struct Case {
    index: usize,
    bytes: Vec<u8>,
    destination: (usize, usize),
    source: (usize, usize),
    may_only: bool,
}

fn encoded(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn cell(register: (usize, usize)) -> String {
    format!("gpr:{}:{}", BANKS[register.0], register.1)
}

fn bank_cells(bank: usize) -> LocationSet {
    (0..8).map(|lane| cell((bank, lane))).collect()
}

fn locations() -> LocationSet {
    let mut result: LocationSet = (0..16).flat_map(bank_cells).collect();
    result.extend(["cf", "pf", "af", "zf", "sf", "of", "df"].map(|name| format!("flag:{name}")));
    result.extend(["memory:any".into(), "state:other".into()]);
    result
}

fn cases() -> Vec<Case> {
    let mut result = Vec::new();
    for prefix in PREFIXES {
        for opcode in [0x88, 0x8a] {
            for reg in 0..8 {
                for rm in 0..8 {
                    let alias = |field: usize, extension: u8| match prefix {
                        None => LEGACY_BYTES[field],
                        Some(rex) => (field + if rex & extension == 0 { 0 } else { 8 }, 0),
                    };
                    let reg_alias = alias(reg, 4);
                    let rm_alias = alias(rm, 1);
                    let (destination, source) = if opcode == 0x88 {
                        (rm_alias, reg_alias)
                    } else {
                        (reg_alias, rm_alias)
                    };
                    let mut bytes: Vec<u8> = prefix.into_iter().collect();
                    bytes.extend([opcode, 0xc0 | ((reg as u8) << 3) | rm as u8]);
                    result.push(Case {
                        index: result.len(),
                        bytes,
                        destination,
                        source,
                        // The v6 reverse self-MOV contract deliberately keeps
                        // the earlier origin as a conservative alternative.
                        may_only: opcode == 0x8a && destination == source,
                    });
                }
            }
        }
    }
    result
}

fn assert_domain(cases: &[Case]) {
    assert_eq!(cases.len(), 640);
    assert_eq!(
        cases
            .iter()
            .map(|case| &case.bytes)
            .collect::<BTreeSet<_>>()
            .len(),
        640
    );
    assert_eq!(cases.iter().filter(|case| case.may_only).count(), 24);
    assert_eq!(
        cases
            .iter()
            .filter(|case| case.destination.1 == 1 || case.source.1 == 1)
            .count(),
        96,
    );
    assert_eq!(
        cases
            .iter()
            .filter(|case| case.destination.0 >= 8 || case.source.0 >= 8)
            .count(),
        384,
    );
    for prefix in PREFIXES {
        for opcode in [0x88, 0x8a] {
            assert_eq!(
                cases
                    .iter()
                    .filter(|case| {
                        case.bytes[..case.bytes.len() - 2] == prefix.into_iter().collect::<Vec<_>>()
                            && case.bytes[case.bytes.len() - 2] == opcode
                    })
                    .count(),
                64,
            );
        }
    }
}

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn producer() -> Config {
    let selected = Config::from_env();
    // This domain binds ordinary v6 byte-register semantics. Other opt-in
    // source profiles have their own native-consumer campaigns.
    Config::new(selected.helper, selected.runtime)
}

fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/ariadne-llvm-mc"))
}

fn core() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .expect("set ARIADNE_BAP_CORE_DIR to the current audited native core")
            .into(),
    )
}

fn target(linux: bool) -> &'static str {
    if linux {
        "linux-amd64"
    } else {
        "windows-amd64"
    }
}

#[derive(Clone, Debug)]
struct Block {
    entry: Address,
    consumer: Address,
    terminal: Address,
    sink: usize,
    bytes: Vec<u8>,
}

fn prepare(cases: &[Case], linux: bool) -> (FilePreparedAnalysis, Vec<Block>, Address) {
    let base = if linux { 0x401000 } else { 0x7ff700001000 };
    let unrooted_seed = base + 0x800000;
    let blocks: Vec<_> = cases
        .iter()
        .map(|case| {
            let entry = base + case.index as u64 * 0x1000;
            let consumer = entry + case.bytes.len() as u64;
            let source_bank = case.destination.0;
            let sink = if source_bank == 15 { 14 } else { 15 };
            // MOV r/m64, r64: the whole destination bank is read by an unrelated
            // bank, so every preserved byte and the copied byte are observable.
            let rex = 0x48 | if source_bank >= 8 { 4 } else { 0 } | if sink >= 8 { 1 } else { 0 };
            let mut bytes = case.bytes.clone();
            bytes.extend([
                rex,
                0x89,
                0xc0 | ((source_bank as u8 & 7) << 3) | (sink as u8 & 7),
                0xc3,
            ]);
            Block {
                entry,
                consumer,
                terminal: consumer + 3,
                sink,
                bytes,
            }
        })
        .collect();
    let mut ranges: Vec<_> = blocks
        .iter()
        .map(|block| (block.entry, block.bytes.as_slice()))
        .collect();
    // These bytes really are captured. Their presence and selection as a seed
    // must not turn them into a discovery root or connect independent cases.
    ranges.push((unrooted_seed, &[0x90, 0xc3]));
    let mut dump = common::Dump::new(linux);
    dump.memory64(&ranges);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let query = AnalysisQuery {
        entry_points: blocks.iter().map(|block| block.entry).collect(),
        slice_seeds: blocks
            .iter()
            .map(|block| block.consumer)
            .chain([unrooted_seed])
            .collect(),
    };
    let prepared = snapshot
        .prepare_with_bap(
            &query,
            &decoder(),
            &producer(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    assert_eq!(
        prepared.prepared.identity.target,
        if linux {
            "x86_64-unknown-linux-gnu"
        } else {
            "x86_64-pc-windows-msvc"
        },
    );
    assert_eq!(prepared.prepared.identity.ruleset, "bap-bit-provenance-v6");
    assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
    assert_eq!(prepared.prepared.request.slice_seeds, query.slice_seeds);
    assert_eq!(prepared.materialization.entry_points, query.entry_points);
    assert_eq!(prepared.materialization.slice_seeds, query.slice_seeds);
    assert!(!prepared.materialization.attempted.contains(&unrooted_seed));
    assert_eq!(prepared.prepared.request.locations, locations());
    (prepared, blocks, unrooted_seed)
}

fn entry_origins(entry: Address) -> BTreeSet<Definition> {
    locations()
        .into_iter()
        .map(|loc| Definition {
            loc,
            site: entry,
            origin: DefinitionOrigin::Entry,
        })
        .collect()
}

fn expected_consumer_origins(case: &Case, block: &Block) -> BTreeSet<Definition> {
    let mut expected = entry_origins(block.entry);
    let destination = cell(case.destination);
    if !case.may_only {
        expected.retain(|definition| definition.loc != destination);
    }
    expected.insert(Definition {
        loc: destination,
        site: block.entry,
        origin: DefinitionOrigin::Instruction,
    });
    expected
}

#[test]
fn mov8_native_domain_keeps_all_alias_partitions() {
    let cases = cases();
    assert_domain(&cases);
    for (bytes, destination, source) in [
        ("88e7", (3, 1), (0, 1)),
        ("4088e7", (7, 0), (4, 0)),
        ("4188e7", (15, 0), (4, 0)),
        ("4488e7", (7, 0), (12, 0)),
        ("4588e7", (15, 0), (12, 0)),
        ("458ae7", (12, 0), (15, 0)),
    ] {
        let case = cases
            .iter()
            .find(|case| encoded(&case.bytes) == bytes)
            .unwrap();
        assert_eq!(
            (case.destination, case.source),
            (destination, source),
            "{bytes}"
        );
    }
}

#[test]
#[ignore = "requires current BAP/LLVM helpers and audited native capture core; run in release mode"]
fn native_mov8_domain_preserves_all_register_byte_origins() {
    let cases = cases();
    assert_domain(&cases);
    let mut seen = BTreeSet::new();
    let mut batches = 0;
    let mut may_only = 0;
    for linux in [false, true] {
        for batch in cases.chunks(64) {
            let (prepared, blocks, unrooted_seed) = prepare(batch, linux);
            let request = &prepared.prepared.request;
            let reference =
                CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
            let native = NativeAnalyzer::from_capture(&core(), "mov8-native-domain", &prepared)
                .unwrap()
                .complete()
                .unwrap();
            assert_eq!(
                crate::bap::core_adapter::encode_request(native.request()).unwrap(),
                crate::bap::core_adapter::encode_request(request).unwrap()
            );
            assert_eq!(native.state(), reference.state());
            assert_eq!(native.state().phase, Phase::Done);
            assert!(native.state().obligations.is_empty());
            let decoded: AddressSet = blocks
                .iter()
                .flat_map(|block| [block.entry, block.consumer, block.terminal])
                .collect();
            assert_eq!(native.state().decoded, decoded);
            assert_eq!(native.state().visited, decoded);
            let edges: BTreeSet<_> = blocks
                .iter()
                .flat_map(|block| {
                    [
                        Edge {
                            src: block.entry,
                            dst: block.consumer,
                            kind: EdgeKind::Next,
                        },
                        Edge {
                            src: block.consumer,
                            dst: block.terminal,
                            kind: EdgeKind::Next,
                        },
                    ]
                })
                .collect();
            assert_eq!(native.state().edges, edges);
            assert_eq!(
                native.state().slice,
                blocks
                    .iter()
                    .flat_map(|block| [block.entry, block.consumer])
                    .collect()
            );
            for (case, block) in batch.iter().zip(&blocks) {
                let bytes = encoded(&case.bytes);
                assert!(seen.insert((target(linux), bytes.clone())));
                let instruction = &request.instructions[&block.entry];
                let evidence = &prepared.prepared.instructions[&block.entry];
                assert_eq!(evidence.bytes, case.bytes);
                assert_eq!(evidence.length as usize, case.bytes.len());
                assert_eq!(evidence.source, ByteSource::Captured);
                assert_eq!(evidence.quality, EffectQuality::ExternalLifted);
                let semantic = evidence.semantic.as_ref().unwrap();
                assert_eq!(semantic.status, "projected");
                assert_eq!(semantic.projection, "bap-bit-provenance-v6");
                assert!(semantic.fallback.is_none());
                assert!(semantic.gaps.is_empty());
                assert_eq!(instruction.kind, InstructionKind::Ordinary);
                assert_eq!(instruction.uses, [cell(case.source)].into());
                assert_eq!(instruction.may_defs, [cell(case.destination)].into());
                let must: LocationSet = if case.may_only {
                    LocationSet::new()
                } else {
                    [cell(case.destination)].into()
                };
                assert_eq!(instruction.must_defs, must, "{bytes}");
                assert_eq!(instruction.fall, [block.consumer].into());
                assert!(instruction.targets.is_empty());
                assert!(instruction.complete);
                let consumer = &request.instructions[&block.consumer];
                assert_eq!(consumer.uses, bank_cells(case.destination.0));
                assert_eq!(consumer.may_defs, bank_cells(block.sink));
                assert_eq!(consumer.must_defs, bank_cells(block.sink));
                assert_eq!(
                    native.state().reaching[&block.entry]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    entry_origins(block.entry)
                );
                let expected = expected_consumer_origins(case, block);
                assert_eq!(
                    native.state().reaching[&block.consumer]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    expected,
                    "{bytes}"
                );
                let mut after_consumer = expected;
                let sink = bank_cells(block.sink);
                after_consumer.retain(|definition| !sink.contains(&definition.loc));
                after_consumer.extend(sink.into_iter().map(|loc| Definition {
                    loc,
                    site: block.consumer,
                    origin: DefinitionOrigin::Instruction,
                }));
                assert_eq!(
                    native.state().reaching[&block.terminal]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    after_consumer,
                    "{bytes}"
                );
                assert_eq!(
                    native.state().provenance[&block.entry],
                    ByteSource::Captured
                );
                for contributor in prepared.reads[&block.entry]
                    .spans
                    .iter()
                    .flat_map(|span| &span.contributors)
                {
                    assert!(contributor.file_offset < prepared.snapshot.artifact_bytes as u64);
                    assert_ne!(contributor.file_offset, block.entry);
                }
                may_only += usize::from(case.may_only);
            }
            crate::input::investigation::bind_investigation(&prepared, &native).unwrap();
            let result = native.into_result();
            assert_eq!(result.snapshot_id, request.snapshot_id);
            assert_eq!(result.missing_slice_seeds, [unrooted_seed].into());
            assert!(result.scope_closed());
            batches += 1;
        }
    }
    assert_eq!(seen.len(), 1280);
    assert_eq!(batches, 20);
    assert_eq!(may_only, 48);
    eprintln!(
        "MOV8_NATIVE_CONSUMER points=640 targets=2 instances=1280 independent_root_batches=20 definite_write_instances=1232 may_only_instances=48"
    );
}

fn direct_native_refusal(input: &Value, snapshot: &str, expected: &str) {
    let config = core();
    let manifest: Value =
        serde_json::from_slice(&std::fs::read(&config.manifest).unwrap()).unwrap();
    assert_eq!(
        manifest["helper_sha256"],
        crate::reports::sha256(&std::fs::read(&config.helper).unwrap())
    );
    let session = "mov8-native-refusal";
    let query = profile_query_digest(snapshot, "recovery", CAPTURED_PROFILE, input).unwrap();
    let request = json!({"schema":"ariadne.bap-core/v1", "session":session,
        "snapshot":snapshot,"query":query,"family":"recovery","sequence":0,
        "operation":"initialize","payload":{"profile":CAPTURED_PROFILE,"input":input}});
    let mut command = Command::new(&config.helper);
    for key in [
        "OPAMROOT",
        "OPAMSWITCH",
        "OPAM_SWITCH_PREFIX",
        "OCAMLPATH",
        "OCAMLLIB",
        "CAML_LD_LIBRARY_PATH",
        "OCAML_TOPLEVEL_PATH",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
    ] {
        command.env_remove(key);
    }
    let mut child = command
        .args([session, snapshot, &query, "recovery"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut stdin = child.stdin.take().unwrap();
    let writer = std::thread::spawn(move || writeln!(stdin, "{request}"));
    let mut stdout = child.stdout.take().unwrap();
    let stdout_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.read_to_end(&mut bytes).unwrap();
        bytes
    });
    let mut stderr = child.stderr.take().unwrap();
    let stderr_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stderr.read_to_end(&mut bytes).unwrap();
        bytes
    });
    let started = Instant::now();
    while child.try_wait().unwrap().is_none() {
        if started.elapsed() >= config.timeout {
            child.kill().unwrap();
            child.wait().unwrap();
            let _ = writer.join();
            let _ = stdout_reader.join();
            let _ = stderr_reader.join();
            panic!("native refusal timed out instead of rejecting {expected}");
        }
        std::thread::sleep(Duration::from_millis(2));
    }
    let status = child.wait().unwrap();
    writer.join().unwrap().unwrap();
    assert_eq!(status.code(), Some(2));
    let stdout = String::from_utf8(stdout_reader.join().unwrap()).unwrap();
    let frames: Vec<Value> = stdout
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(frames, vec![manifest["handshake"].clone()]);
    let stderr = String::from_utf8(stderr_reader.join().unwrap()).unwrap();
    assert!(
        stderr.contains(expected),
        "wrong native rejection for {expected}: {stderr}"
    );
}

#[test]
#[ignore = "requires current BAP/LLVM helpers and audited native capture core"]
fn native_mov8_boundary_controls_keep_host_and_native_claims_separate() {
    let selected: Vec<_> = cases()
        .into_iter()
        .filter(|case| case.bytes.last() == Some(&0xe7))
        .collect();
    assert_eq!(selected.len(), 10);
    let mut host_byte_refusals = 0;
    let mut native_refusals = 0;
    for linux in [false, true] {
        let (prepared, blocks, _) = prepare(&selected, linux);
        let snapshot = &prepared.prepared.request.snapshot_id;
        let wire = NativeAnalyzer::capture_wire_for_test(&prepared).unwrap();
        let (mut session, response) = CoreSession::start_profile(
            &core(),
            "mov8-boundary-positive",
            snapshot,
            CAPTURED_PROFILE,
            &wire,
        )
        .unwrap();
        assert!(response.error.is_none());
        assert!(session.request("reset", json!({})).unwrap().error.is_none());
        assert!(
            CoreSession::start_profile(
                &core(),
                "mov8-wrong-profile",
                snapshot,
                "captured-fixed-input/v999",
                &wire
            )
            .err()
            .unwrap()
            .to_string()
            .contains("unsupported core input profile")
        );
        assert!(
            Session::start(
                &producer(),
                snapshot,
                if linux { "linux-x86" } else { "windows-arm64" }
            )
            .err()
            .unwrap()
            .to_string()
            .contains("invalid BAP query identity/target")
        );
        for block in &blocks {
            let mut wrong_bytes = prepared.clone();
            *wrong_bytes
                .prepared
                .instructions
                .get_mut(&block.entry)
                .unwrap()
                .bytes
                .last_mut()
                .unwrap() ^= 1;
            assert!(
                NativeAnalyzer::from_capture(&core(), "mov8-wrong-bytes", &wrong_bytes)
                    .err()
                    .unwrap()
                    .to_string()
                    .contains("instruction bytes do not match captured read")
            );
            host_byte_refusals += 1;
            let site = wire["capture"]["sites"]
                .as_array()
                .unwrap()
                .iter()
                .position(|row| row["address"] == format!("0x{:016x}", block.entry))
                .unwrap();
            for (mutation, expected) in [
                ("nonhex-bytes", "capture bytes"),
                ("odd-bytes", "capture bytes"),
                ("absent-projection", "decoded semantic identity absent"),
                ("absent-ast", "projected AST identity"),
                ("availability", "capture availability"),
                ("spans", "capture span coverage"),
            ] {
                let mut changed = wire.clone();
                let row = &mut changed["capture"]["sites"][site];
                match mutation {
                    "nonhex-bytes" => row["bytes"] = json!("zz"),
                    "odd-bytes" => row["bytes"] = json!("8"),
                    "absent-projection" => row["projection"] = Value::Null,
                    "absent-ast" => row["ast_sha256"] = Value::Null,
                    "availability" => row["captured"] = json!(false),
                    "spans" => row["spans"] = json!([]),
                    _ => unreachable!(),
                }
                direct_native_refusal(&changed, snapshot, expected);
                native_refusals += 1;
            }
        }
    }
    assert_eq!(host_byte_refusals, 20);
    assert_eq!(native_refusals, 120);
    eprintln!(
        "MOV8_NATIVE_BOUNDARY host_byte_refusals=20 host_profile_refusals=2 host_target_refusals=2 native_structural_refusals=120"
    );
}
