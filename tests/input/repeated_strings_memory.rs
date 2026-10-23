//! Multi-root actual captures keep the recipe corpus independent while sharing
//! one immutable snapshot/session. Setup counts are not execution observations.
use super::common;
use crate::bap::core_adapter::NativeAnalyzer;
use crate::bap::core_session::CoreConfig;
use crate::bap::{Config, SourceExtensionMode, guard_admission, target_resolution};
use crate::effects::PreparationOptions;
use crate::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{AnalysisView, CompletedAnalysis, DefinitionOrigin, LocationSet};
use serde_json::Value;
use std::path::PathBuf;

const PROFILE13: &str = "bap-bit-provenance-v13";
const PROFILE14: &str = "bap-bit-provenance-v14";
const PROFILE15: &str = "bap-bit-provenance-v15";

fn config(profile: &str) -> Config {
    let flags = std::env::var_os("ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION")
        .expect("pinned advanced flag dependency is required")
        .into();
    match profile {
        PROFILE13 => Config::from_env().with_memory_repeated_strings(flags),
        PROFILE14 => Config::from_env().with_memory_repeated_strings_and_lods(
            flags,
            std::env::var_os("ARIADNE_BAP_LODS_SOURCE_EXTENSION")
                .expect("v14 requires its separately pinned LODS producer")
                .into(),
        ),
        PROFILE15 => Config::from_env().with_amd_memory_repeated_strings_address_size(
            flags,
            std::env::var_os("ARIADNE_BAP_REP_ADDRESS_SOURCE_EXTENSION")
                .expect("v15 requires its separately pinned AMD address-size REP producer")
                .into(),
        ),
        _ => panic!("unreviewed memory-string test profile"),
    }
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc"))
}
fn core() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .expect("current native core is required")
            .into(),
    )
}
fn cells(bank: &str, bytes: usize) -> LocationSet {
    (0..bytes)
        .map(|byte| format!("gpr:{bank}:{byte}"))
        .collect()
}
fn expected(case: &Value) -> (LocationSet, LocationSet) {
    let family = case["family"].as_str().unwrap();
    let bytes = case["elementBits"].as_u64().unwrap() as usize / 8;
    let mut writes = cells("rcx", 8);
    if matches!(family, "movs" | "cmps" | "lods") {
        writes.extend(cells("rsi", 8));
    }
    if family != "lods" {
        writes.extend(cells("rdi", 8));
    }
    let mut uses = writes.clone();
    uses.insert("flag:df".into());
    if matches!(family, "stos" | "scas") {
        uses.extend(cells("rax", bytes));
    }
    if family != "stos" {
        uses.insert("memory:any".into());
    }
    if matches!(family, "movs" | "stos") {
        writes.insert("memory:any".into());
    }
    if matches!(family, "cmps" | "scas") {
        for flag in ["cf", "pf", "af", "zf", "sf", "of"] {
            uses.insert(format!("flag:{flag}"));
            writes.insert(format!("flag:{flag}"));
        }
    }
    if family == "lods" {
        let lanes = if bytes == 4 { 8 } else { bytes };
        writes.extend(cells("rax", lanes));
        uses.extend(cells("rax", lanes));
    }
    (uses, writes)
}
fn recipes(profile: &str) -> Vec<Value> {
    let document: Value = serde_json::from_str(include_str!(
        "../bap/fixtures/repeated-string/memory-recipes-v2.json"
    ))
    .unwrap();
    assert_eq!(document["cases"].as_array().unwrap().len(), 28);
    let mut cases: Vec<Value> = document["cases"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|case| match profile {
            PROFILE13 => case["profile"] == PROFILE13,
            // The base recipe catalogue deliberately preserves the missing
            // historical producer disposition for LODS. Its v14 producer is
            // selected through a separate, explicit dependency above.
            PROFILE14 | PROFILE15 => true,
            _ => panic!("unreviewed memory-string recipe profile"),
        })
        .cloned()
        .collect();
    if profile == PROFILE15 {
        // The source catalogue remains the immutable default-address recipe
        // input. v15 explicitly selects both widths and its separate producer.
        let address32: Vec<_> = cases
            .iter()
            .map(|case| {
                let mut selected = case.clone();
                selected["name"] = format!("{}-address32", case["name"].as_str().unwrap()).into();
                selected["bytes"] = format!("67{}", case["bytes"].as_str().unwrap()).into();
                for width in ["addressBits", "countBits", "indexBits"] {
                    selected[width] = 32.into();
                }
                selected
            })
            .collect();
        cases.extend(address32);
    }
    cases
}
fn bytes(case: &Value) -> Vec<u8> {
    let encoded = case["bytes"].as_str().unwrap();
    (0..encoded.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&encoded[i..i + 2], 16).unwrap())
        .collect()
}
fn sequence(case: &Value, count: u32, reverse: bool) -> (Vec<u8>, usize, usize) {
    let address32 = case["addressBits"] == 32;
    let family = case["family"].as_str().unwrap();
    let mut code = Vec::new();
    if address32 {
        code.extend([0x48, 0xb9]); // MOV RCX,imm64: upper count bits remain nonzero.
        code.extend((0x8765_4321_0000_0000 | u64::from(count)).to_le_bytes());
    } else {
        code.push(0xb9); // MOV ECX,count, including its reviewed zero extension.
        code.extend(count.to_le_bytes());
    }
    let source = 0x7010u64
        | if address32 && matches!(family, "movs" | "cmps" | "lods") {
            0x1357_9bdf_0000_0000
        } else {
            0
        };
    let destination = 0x8010u64
        | if address32 && matches!(family, "movs" | "stos" | "cmps" | "scas") {
            0x2468_ace0_0000_0000
        } else {
            0
        };
    for (register, value) in [
        (0xbe, source),
        (0xbf, destination),
        (0xb8, 0xa512_3487_9bcd_0123),
    ] {
        code.extend([0x48, register]);
        code.extend(value.to_le_bytes());
    }
    code.push(if reverse { 0xfd } else { 0xfc });
    let repeated = code.len();
    code.extend(bytes(case));
    let consumer = code.len();
    code.extend([0x48, 0x89, 0xca, 0x8a, 0x1f, 0xc3]);
    (code, repeated, consumer)
}

#[test]
fn memory_rep_proof_modes_refuse_before_native_or_decoder_work() {
    let mut dump = common::Dump::new(true);
    dump.memory64(&[(0x401000, &[0xf3, 0xaa, 0xc3])]);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let missing = PathBuf::from("/nonexistent/ariadne-memory-rep-test");
    let base = Config::new(missing.join("helper"), missing.join("runtime"));
    for config in [
        base.clone()
            .with_memory_repeated_strings(missing.join("source")),
        base.clone().with_memory_repeated_strings_and_lods(
            missing.join("source"),
            missing.join("lods-source"),
        ),
        base.with_amd_memory_repeated_strings_address_size(
            missing.join("source"),
            missing.join("rep-address-source"),
        ),
    ] {
        for roots in [vec![], vec![0x401000]] {
            let query = AnalysisQuery {
                entry_points: roots.into_iter().collect(),
                slice_seeds: [0x401000].into(),
            };
            for result in [
                snapshot.prepare_with_bap_refinement(
                    &query,
                    &missing,
                    &config,
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                ),
                snapshot.prepare_with_bap_target_resolution(
                    &query,
                    &missing,
                    &config,
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                    target_resolution::Limits::default(),
                ),
                snapshot.prepare_with_bap_guard_admission(
                    &query,
                    &missing,
                    &config,
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                    guard_admission::Limits::default(),
                ),
            ] {
                assert!(
                    result
                        .unwrap_err()
                        .to_string()
                        .contains("does not admit guards, target resolution or refinement")
                );
            }
        }
    }
}

#[test]
fn memory_rep_config_requires_the_lods_dependency_only_for_v14() {
    let missing = PathBuf::from("/nonexistent/ariadne-memory-rep-config");
    let base = Config::new(missing.join("helper"), missing.join("runtime"));
    let flags = missing.join("flags");
    let lods = missing.join("lods");
    let v13 = base.clone().with_memory_repeated_strings(flags.clone());
    let v14 = base.with_memory_repeated_strings_and_lods(flags.clone(), lods.clone());
    assert!(v13.validate_source_mode().is_ok());
    assert!(v14.validate_source_mode().is_ok());
    assert_eq!(
        v13.source_extension_mode,
        SourceExtensionMode::MemoryRepeatedStrings
    );
    assert_eq!(
        v14.source_extension_mode,
        SourceExtensionMode::MemoryRepeatedStringsWithLods
    );
    assert!(v13.lods_source_extension.is_none());
    assert_eq!(v14.lods_source_extension.as_ref(), Some(&lods));
    let mut missing_lods = v14.clone();
    missing_lods.lods_source_extension = None;
    assert!(missing_lods.validate_source_mode().is_err());
    let mut missing_flags = v14.clone();
    missing_flags.source_extension = None;
    assert!(missing_flags.validate_source_mode().is_err());
    let mut mismatched = v13;
    mismatched.lods_source_extension = Some(lods);
    assert!(mismatched.validate_source_mode().is_err());
    let reset = v14.with_memory_repeated_strings(flags);
    assert!(reset.lods_source_extension.is_none());
    assert_eq!(
        reset.source_extension_mode,
        SourceExtensionMode::MemoryRepeatedStrings
    );
    assert!(reset.validate_source_mode().is_ok());
}

#[test]
fn memory_rep_address_config_requires_explicit_amd_mode_and_resets_other_bundles() {
    let missing = PathBuf::from("/nonexistent/ariadne-memory-rep-address-config");
    let base = Config::new(missing.join("helper"), missing.join("runtime"));
    let flags = missing.join("flags");
    let lods = missing.join("lods");
    let address = missing.join("rep-address");
    let v14 = base.with_memory_repeated_strings_and_lods(flags.clone(), lods.clone());
    let v15 = v14
        .clone()
        .with_amd_memory_repeated_strings_address_size(flags.clone(), address.clone());
    assert!(v15.validate_source_mode().is_ok());
    assert_eq!(
        v15.source_extension_mode,
        SourceExtensionMode::AmdMemoryRepeatedStringsAddressSize
    );
    assert!(v15.lods_source_extension.is_none());
    assert_eq!(v15.rep_address_source_extension.as_ref(), Some(&address));
    let mut missing_address = v15.clone();
    missing_address.rep_address_source_extension = None;
    assert!(missing_address.validate_source_mode().is_err());
    let mut missing_flags = v15.clone();
    missing_flags.source_extension = None;
    assert!(missing_flags.validate_source_mode().is_err());
    let mut mixed = v15.clone();
    mixed.lods_source_extension = Some(lods.clone());
    assert!(mixed.validate_source_mode().is_err());
    for mut old in [v14, v15.clone().with_memory_repeated_strings(flags.clone())] {
        old.rep_address_source_extension = Some(address.clone());
        assert!(old.validate_source_mode().is_err());
    }
    for reset in [
        v15.clone().with_source_extension(flags.clone()),
        v15.clone().with_advanced_source_extension(flags.clone()),
        v15.clone().with_repeated_strings(flags.clone()),
        v15.clone().with_memory_repeated_strings(flags.clone()),
        v15.with_memory_repeated_strings_and_lods(flags, lods),
    ] {
        assert!(reset.rep_address_source_extension.is_none());
        assert!(reset.validate_source_mode().is_ok());
    }
}

fn memory_rep_recipe_matrix(config: &Config, profile: &str, cases: &[Value], native_backend: bool) {
    assert_eq!(
        cases.len(),
        match profile {
            PROFILE13 => 24,
            PROFILE14 => 28,
            PROFILE15 => 56,
            _ => panic!("unreviewed memory-string test profile"),
        }
    );
    let mut checked = 0;
    for linux in [false, true] {
        for count in [0, 3] {
            for reverse in [false, true] {
                let base = if linux { 0x401000 } else { 0x7ff700001000 };
                let blocks: Vec<_> = cases
                    .iter()
                    .enumerate()
                    .map(|(i, case)| {
                        let entry = base + i as u64 * 0x1000;
                        let (code, repeated, consumer) = sequence(case, count, reverse);
                        (
                            entry,
                            code,
                            entry + repeated as u64,
                            entry + consumer as u64,
                        )
                    })
                    .collect();
                let mut ranges: Vec<_> = blocks
                    .iter()
                    .map(|(entry, code, _, _)| (*entry, code.as_slice()))
                    .collect();
                let data = [0x80; 128];
                ranges.extend([(0x7000, data.as_slice()), (0x8000, data.as_slice())]);
                let mut dump = common::Dump::new(linux);
                dump.memory64(&ranges);
                let snapshot =
                    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default())
                        .unwrap();
                let query = AnalysisQuery {
                    entry_points: blocks.iter().map(|row| row.0).collect(),
                    slice_seeds: blocks.iter().map(|row| row.3).chain([0xdead0000]).collect(),
                };
                let prepared = snapshot
                    .prepare_with_bap(
                        &query,
                        &decoder(),
                        config,
                        &PreparationOptions::default(),
                        PrepareLimits::default(),
                    )
                    .unwrap();
                assert_eq!(prepared.prepared.identity.ruleset, profile);
                assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
                assert_eq!(prepared.prepared.request.slice_seeds, query.slice_seeds);
                assert!(!prepared.materialization.attempted.contains(&0xdead0000));
                let rust = CompletedAnalysis::from_analyzer(
                    crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
                );
                let completed = if native_backend {
                    let native =
                        NativeAnalyzer::from_capture(&core(), "memory-rep-matrix", &prepared)
                            .unwrap()
                            .complete()
                            .unwrap();
                    assert_eq!(native.state(), rust.state());
                    native
                } else {
                    rust
                };
                for (case, (entry, _, repeated, consumer)) in cases.iter().zip(&blocks) {
                    let semantic = prepared.prepared.instructions[repeated]
                        .semantic
                        .as_ref()
                        .unwrap();
                    assert_eq!(semantic.projection, profile);
                    assert_eq!(semantic.status, "projected", "{}", case["name"]);
                    assert_eq!(
                        semantic
                            .gaps
                            .iter()
                            .filter(|gap| *gap == "amd-address32-zero-count-semantics-premise")
                            .count(),
                        usize::from(profile == PROFILE15 && case["addressBits"] == 32),
                        "{} AMD address-size premise",
                        case["name"]
                    );
                    assert!(!semantic.memory_accesses.is_empty());
                    assert!(semantic.memory_accesses.iter().all(|access| {
                        access.expression.is_none()
                            && access
                                .gaps
                                .iter()
                                .any(|gap| gap == "iteration-dependent-memory-access")
                    }));
                    let instruction = &prepared.prepared.request.instructions[repeated];
                    let (uses, writes) = expected(case);
                    assert_eq!(instruction.uses, uses, "{} uses", case["name"]);
                    assert_eq!(instruction.may_defs, writes, "{} writes", case["name"]);
                    assert!(instruction.must_defs.is_empty());
                    let reaching = &completed.state().reaching[consumer];
                    for byte in 0..8 {
                        let cell = format!("gpr:rcx:{byte}");
                        for producer in [entry, repeated] {
                            assert!(reaching.iter().any(|d| d.loc == cell
                                && d.site == *producer
                                && d.origin == DefinitionOrigin::Instruction));
                        }
                    }
                    assert!(
                        reaching
                            .iter()
                            .any(|d| d.loc == "memory:any" && d.origin == DefinitionOrigin::Entry)
                    );
                    checked += 1;
                }
                crate::input::investigation::bind_investigation(&prepared, &completed).unwrap();
            }
        }
    }
    assert_eq!(checked, cases.len() * 8);
}

#[test]
#[ignore = "requires pinned BAP/LLVM, selected v13 memory recipes and current native core"]
fn native_memory_rep_recipe_matrix_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE13), PROFILE13, &recipes(PROFILE13), true);
}

#[test]
#[ignore = "requires pinned BAP/LLVM, separate v14 LODS producer and current native core"]
fn native_lods_memory_rep_recipe_matrix_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE14), PROFILE14, &recipes(PROFILE14), true);
}

#[test]
#[ignore = "requires pinned BAP/LLVM, explicit AMD v15 REP producer and current native core"]
fn native_amd_address_memory_rep_recipe_matrix_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE15), PROFILE15, &recipes(PROFILE15), true);
}

#[test]
#[ignore = "requires pinned BAP/LLVM and selected v13 memory recipes"]
fn memory_rep_recipe_materialization_v13_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE13), PROFILE13, &recipes(PROFILE13), false);
}

#[test]
#[ignore = "requires pinned BAP/LLVM and separate v14 LODS producer"]
fn memory_rep_recipe_materialization_v14_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE14), PROFILE14, &recipes(PROFILE14), false);
}

#[test]
#[ignore = "requires pinned BAP/LLVM and explicit AMD v15 REP producer"]
fn memory_rep_recipe_materialization_v15_preserves_roots_effects_and_origins() {
    memory_rep_recipe_matrix(&config(PROFILE15), PROFILE15, &recipes(PROFILE15), false);
}
