//! Finite actual-BIL and capture controls for the explicitly selected REP profile.
//! Counts and directions in synthetic dumps are setup instructions, not captured
//! execution history. These tests do not qualify hardware partial faults.
use super::common;
use crate::bap::ast::Stmt;
use crate::bap::core_adapter::NativeAnalyzer;
use crate::bap::core_session::{CoreConfig, CoreSession};
use crate::bap::{Config, Session, guard_admission, target_resolution};
use crate::effects::PreparationOptions;
use crate::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{AnalysisView, CompletedAnalysis, DefinitionOrigin, InstructionKind, LocationSet};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::PathBuf;

const PROFILE: &str = "bap-bit-provenance-v12";
const FORMS: [(&str, u8); 3] = [("MOVSB", 0xa4), ("STOSB", 0xaa), ("CMPSB", 0xa6)];

fn config() -> Config {
    let directory = std::env::var_os("ARIADNE_BAP_REPEATED_STRING_SOURCE_EXTENSION")
        .or_else(|| std::env::var_os("ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION"))
        .expect("pinned advanced flag dependency directory is required");
    Config::from_env().with_repeated_strings(directory.into())
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc"))
}
fn core() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
            }),
    )
}
fn entry(linux: bool) -> u64 {
    if linux { 0x401000 } else { 0x7ff700001000 }
}
fn snapshot(code: &[u8], linux: bool) -> FileSnapshot {
    let mut dump = common::Dump::new(linux);
    dump.memory64(&[
        (entry(linux), code),
        (0x7000, &[0x80; 16]),
        (0x8000, &[0x80; 16]),
    ]);
    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap()
}
fn query(linux: bool, seed: u64) -> AnalysisQuery {
    AnalysisQuery {
        entry_points: [entry(linux)].into(),
        // The absent seed must remain a selector, never an additional root.
        slice_seeds: [seed, 0xdead0000].into(),
    }
}
fn cells(banks: &[&str]) -> LocationSet {
    banks
        .iter()
        .flat_map(|bank| (0..8).map(move |byte| format!("gpr:{bank}:{byte}")))
        .collect()
}
fn expected(opcode: &str) -> (LocationSet, LocationSet) {
    let banks: &[&str] = if opcode == "STOSB" {
        &["rcx", "rdi"]
    } else {
        &["rcx", "rsi", "rdi"]
    };
    let mut uses = cells(banks);
    let mut writes = uses.clone();
    uses.insert("flag:df".into());
    if opcode == "STOSB" {
        uses.insert("gpr:rax:0".into());
    } else {
        uses.insert("memory:any".into());
    }
    if opcode == "CMPSB" {
        for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
            uses.insert(format!("flag:{flag}"));
            writes.insert(format!("flag:{flag}"));
        }
    } else {
        writes.insert("memory:any".into());
    }
    (uses, writes)
}
fn contains_loop(statements: &[Stmt]) -> bool {
    statements.iter().any(|statement| match statement {
        Stmt::While { .. } => true,
        Stmt::If { yes, no, .. } => contains_loop(yes) || contains_loop(no),
        _ => false,
    })
}

#[test]
fn repeated_string_proofs_refuse_before_helper_dispatch_even_without_roots() {
    let snapshot = snapshot(&[0xf3, 0xa4, 0xc3], true);
    let absent = PathBuf::from("/nonexistent/ariadne-repeated-string-test");
    let config = Config::new(absent.join("helper"), absent.join("runtime"))
        .with_repeated_strings(absent.join("source"));
    for roots in [false, true] {
        let query = AnalysisQuery {
            entry_points: if roots {
                [entry(true)].into()
            } else {
                [].into()
            },
            slice_seeds: [entry(true)].into(),
        };
        let options = PreparationOptions::default();
        let limits = PrepareLimits::default();
        let results = [
            snapshot.prepare_with_bap_refinement(
                &query,
                &absent,
                &config,
                &options,
                limits.clone(),
            ),
            snapshot.prepare_with_bap_target_resolution(
                &query,
                &absent,
                &config,
                &options,
                limits.clone(),
                target_resolution::Limits::default(),
            ),
            snapshot.prepare_with_bap_guard_admission(
                &query,
                &absent,
                &config,
                &options,
                limits,
                guard_admission::Limits::default(),
            ),
        ];
        for result in results {
            let error = result.unwrap_err().to_string();
            assert!(error.contains("does not admit guards, target resolution or refinement"));
        }
    }
}

#[test]
#[ignore = "requires pinned BAP helper/runtime and explicit advanced flag dependency"]
fn actual_repeated_string_bil_has_exact_effects_and_old_profile_prefix_refusals() {
    for target in ["windows-amd64", "linux-amd64"] {
        let mut session = Session::start(&config(), "actual-repeated-string-bil", target).unwrap();
        let candidates: BTreeMap<_, _> = FORMS
            .iter()
            .enumerate()
            .map(|(index, (_, byte))| (0x401000 + index as u64 * 16, vec![0xf3, *byte]))
            .collect();
        let lifts = session.lift(&candidates).unwrap();
        session.finish().unwrap();
        for ((opcode, byte), (&site, lift)) in FORMS.into_iter().zip(&lifts) {
            assert_eq!(lift.status, "decoded");
            assert_eq!(lift.length, 2);
            assert_eq!(lift.bytes, format!("f3{byte:02x}"));
            assert_eq!(lift.opcode.as_deref(), Some(opcode));
            assert!(contains_loop(&lift.bil));
            let project = |bytes: &[u8], selected: &str| {
                crate::bap::projection::project_with_destination_profile(
                    &lift.bil, opcode, bytes, site, None, selected,
                )
            };
            let projected = project(&[0xf3, byte], PROFILE).unwrap();
            let (uses, writes) = expected(opcode);
            assert_eq!(projected.uses, uses, "{target} {opcode}");
            assert_eq!(projected.may_defs, writes, "{target} {opcode}");
            assert!(projected.must_defs.is_empty());
            assert!(projected.targets.is_empty());
            for old in ["bap-bit-provenance-v10", "bap-bit-provenance-v11"] {
                assert!(project(&[0xf3, byte], old).is_err());
            }
            for prefix in [0xf0, 0xf2, 0x64, 0x65, 0x66, 0x67, 0x48] {
                assert!(project(&[prefix, 0xf3, byte], PROFILE).is_err());
            }
            assert!(project(&[0xf2, byte], PROFILE).is_err());
            assert!(project(&[byte], PROFILE).is_err());
        }
    }
}

fn sequence(byte: u8, count: u32, direction: bool, linux: bool) -> (Vec<u8>, u64, u64) {
    let mut code = vec![0xb9]; // MOV ECX,imm32
    code.extend(count.to_le_bytes());
    for (opcode, pointer) in [(0xbe, 0x7008u64), (0xbf, 0x8008u64)] {
        code.extend([0x48, opcode]);
        code.extend(pointer.to_le_bytes());
    }
    code.extend([0xb0, 0x5a]); // MOV AL,0x5a
    code.push(if direction { 0xfd } else { 0xfc }); // STD / CLD
    let repeated = entry(linux) + code.len() as u64;
    code.extend([0xf3, byte]);
    let consumer = entry(linux) + code.len() as u64;
    code.extend([0x48, 0x89, 0xca]); // MOV RDX,RCX
    code.extend([0x8a, 0x1f]); // MOV BL,[RDI]
    code.push(0xc3);
    (code, repeated, consumer)
}

#[test]
#[ignore = "requires pinned BAP/LLVM, advanced flag dependency and current native capture core"]
fn native_repeated_string_captures_preserve_possible_origins_for_24_sequences() {
    let mut checked = 0;
    for linux in [false, true] {
        for (opcode, byte) in FORMS {
            for count in [0, 4] {
                for direction in [false, true] {
                    let (code, repeated, consumer) = sequence(byte, count, direction, linux);
                    let snapshot = snapshot(&code, linux);
                    let query = query(linux, consumer);
                    let prepared = snapshot
                        .prepare_with_bap(
                            &query,
                            &decoder(),
                            &config(),
                            &PreparationOptions::default(),
                            PrepareLimits::default(),
                        )
                        .unwrap();
                    assert_eq!(prepared.prepared.identity.ruleset, PROFILE);
                    assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
                    assert_eq!(prepared.prepared.request.slice_seeds, query.slice_seeds);
                    assert!(!prepared.materialization.attempted.contains(&0xdead0000));
                    let semantic = prepared.prepared.instructions[&repeated]
                        .semantic
                        .as_ref()
                        .unwrap();
                    assert_eq!(semantic.projection, PROFILE);
                    assert_eq!(semantic.status, "projected");
                    assert!(semantic.ast_sha256.is_some());
                    let instruction = &prepared.prepared.request.instructions[&repeated];
                    assert_eq!(instruction.kind, InstructionKind::Ordinary);
                    assert_eq!(instruction.fall, [consumer].into());
                    let (uses, writes) = expected(opcode);
                    assert_eq!(instruction.uses, uses);
                    assert_eq!(instruction.may_defs, writes);
                    assert!(instruction.must_defs.is_empty());
                    assert!(prepared.guard_admission().is_none());
                    assert!(prepared.target_resolution().is_none());
                    assert!(prepared.refinement.is_empty());
                    let rust = CompletedAnalysis::from_analyzer(
                        crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
                    );
                    let native =
                        NativeAnalyzer::from_capture(&core(), "repeated-string-capture", &prepared)
                            .unwrap()
                            .complete()
                            .unwrap();
                    assert_eq!(rust.state(), native.state());
                    for byte in 0..8 {
                        let cell = format!("gpr:rcx:{byte}");
                        let reaching = &native.state().reaching[&consumer];
                        assert!(reaching.iter().any(|d| d.loc == cell
                            && d.site == entry(linux)
                            && d.origin == DefinitionOrigin::Instruction));
                        assert!(reaching.iter().any(|d| d.loc == cell
                            && d.site == repeated
                            && d.origin == DefinitionOrigin::Instruction));
                    }
                    let reaching = &native.state().reaching[&consumer];
                    assert!(
                        reaching
                            .iter()
                            .any(|d| d.loc == "memory:any" && d.origin == DefinitionOrigin::Entry)
                    );
                    assert_eq!(
                        reaching.iter().any(|d| d.loc == "memory:any"
                            && d.site == repeated
                            && d.origin == DefinitionOrigin::Instruction),
                        opcode != "CMPSB",
                    );
                    crate::input::investigation::bind_investigation(&prepared, &native).unwrap();
                    checked += 1;
                }
            }
        }
    }
    assert_eq!(checked, 24);
}

#[test]
#[ignore = "requires pinned BAP/LLVM, advanced flag dependency and current native capture core"]
fn saved_repeated_string_capture_roundtrips_and_rejects_capture_tampering() {
    for linux in [false, true] {
        let (code, repeated, consumer) = sequence(0xa4, 4, false, linux);
        let prepared = snapshot(&code, linux)
            .prepare_with_bap(
                &query(linux, consumer),
                &decoder(),
                &config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        for mutation in ["bytes", "query", "spans", "helper"] {
            let mut bad = prepared.clone();
            match mutation {
                "bytes" => bad.prepared.instructions.get_mut(&repeated).unwrap().bytes[1] = 0xaa,
                "query" => bad.materialization.query_identity = "0".repeat(64),
                "spans" => bad.reads.get_mut(&repeated).unwrap().spans.clear(),
                "helper" => {
                    bad.prepared
                        .instructions
                        .get_mut(&repeated)
                        .unwrap()
                        .semantic
                        .as_mut()
                        .unwrap()
                        .helper_sha256 = "invalid".into()
                }
                _ => unreachable!(),
            }
            assert!(NativeAnalyzer::from_capture(&core(), "bad-repeated-capture", &bad).is_err());
        }
        let wire = NativeAnalyzer::capture_wire_for_test(&prepared).unwrap();
        let saved: Value = serde_json::from_slice(&serde_json::to_vec(&wire).unwrap()).unwrap();
        assert_eq!(wire, saved);
        let run = |input: &Value| {
            CoreSession::start_profile(
                &core(),
                "saved-repeated-capture",
                &prepared.prepared.request.snapshot_id,
                crate::bap::core_protocol::CAPTURED_PROFILE,
                input,
            )
        };
        let (session, response) = run(&saved).unwrap();
        assert!(response.error.is_none());
        drop(session);
        let site = saved["capture"]["sites"]
            .as_array()
            .unwrap()
            .iter()
            .position(|row| row["address"] == format!("0x{repeated:016x}"))
            .unwrap();
        for mutation in ["ast", "spans", "availability"] {
            let mut bad = saved.clone();
            match mutation {
                "ast" => bad["capture"]["sites"][site]["ast_sha256"] = Value::Null,
                "spans" => bad["capture"]["sites"][site]["spans"] = json!([]),
                "availability" => bad["capture"]["sites"][site]["captured"] = json!(false),
                _ => unreachable!(),
            }
            let rejected = match run(&bad) {
                Err(_) => true,
                Ok((session, response)) => {
                    drop(session);
                    response.error.is_some()
                }
            };
            assert!(
                rejected,
                "native admitted repeated-string {mutation} mutation"
            );
        }
    }
}
