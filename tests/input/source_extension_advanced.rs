//! Actual source-built BAP sequences, independent numerical/alias expectations,
//! native/reference equality and saved-proof hostility controls.
use super::{GuardPreparation, common, guard_query_scope};
use crate::bap::core_adapter::NativeAnalyzer;
use crate::bap::core_session::CoreConfig;
use crate::bap::{Config, guard_admission as guard, target_resolution as target};
use crate::effects::PreparationOptions;
use crate::input::{AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{AnalysisView, CompletedAnalysis, InstructionKind};
use serde_json::json;
use std::collections::BTreeSet;
use std::path::PathBuf;

const ENTRY: u64 = 0x401000;
const TABLE: u64 = 0x403000;
const LEFT: u64 = 0x402000;
const RIGHT: u64 = 0x402010;
const CALLEE: u64 = 0x404000;
const MOVAPS: [u8; 8] = [0x0f, 0x29, 0xb4, 0x24, 0x40, 0x02, 0, 0];

fn config() -> Config {
    let directory = std::env::var_os("ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION")
        .or_else(|| std::env::var_os("ARIADNE_BAP_SOURCE_EXTENSION"))
        .expect("advanced source-built producer directory is required");
    Config::from_env().with_advanced_source_extension(directory.into())
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
fn snapshot(code: &[u8], linux: bool) -> FileSnapshot {
    let mut dump = common::Dump::new(linux);
    let pointers = [
        ((LEFT as i64 - TABLE as i64) as i32).to_le_bytes(),
        ((RIGHT as i64 - TABLE as i64) as i32).to_le_bytes(),
    ]
    .concat();
    dump.memory64(&[
        (ENTRY, code),
        (TABLE, &pointers),
        (LEFT, &[0xc3]),
        (RIGHT, &[0xc3]),
        (CALLEE, &[0xc3]),
    ]);
    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap()
}
fn query(seed: u64) -> AnalysisQuery {
    AnalysisQuery {
        entry_points: [ENTRY].into(),
        slice_seeds: [seed, 0xdead0000].into(),
    }
}
fn setup(snapshot: &FileSnapshot, query: &AnalysisQuery) -> GuardPreparation {
    let activation = guard::Activation {
        thread_id: 0,
        frame_activation: "actual-source-flags/v1".into(),
    };
    let roots = query
        .entry_points
        .iter()
        .map(|site| guard::Root {
            site: format!("0x{site:016x}"),
            function_entry: false,
            anchor_sha256: crate::reports::sha256(format!("test-root:{site:x}").as_bytes()),
        })
        .collect::<Vec<_>>();
    let scope = guard_query_scope(
        &snapshot.metadata().snapshot_id,
        query,
        &PrepareLimits::default(),
        &activation,
        &roots,
    )
    .unwrap();
    GuardPreparation {
        // Combined discovery advances the epoch for each newly prepared batch,
        // not just resolver passes. This table needs more than the default 8.
        limits: guard::Limits {
            max_closure_rounds: 64,
            ..guard::Limits::default()
        },
        activation,
        roots,
        premises: vec![],
        query_scope_sha256: scope,
        producer: None,
    }
}
fn mov_rsp(code: &mut Vec<u8>, value: u64) {
    code.extend([0x48, 0xbc]);
    code.extend(value.to_le_bytes());
}
fn call(code: &mut Vec<u8>) -> u64 {
    let site = ENTRY + code.len() as u64;
    code.push(0xe8);
    code.extend(
        i32::try_from(CALLEE as i128 - (site + 5) as i128)
            .unwrap()
            .to_le_bytes(),
    );
    site
}
fn parity(
    prepared: &FilePreparedAnalysis,
    query: &AnalysisQuery,
    label: &str,
) -> (CompletedAnalysis, CompletedAnalysis) {
    assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
    assert_eq!(prepared.prepared.request.slice_seeds, query.slice_seeds);
    for instruction in prepared.prepared.request.instructions.values() {
        if matches!(
            instruction.kind,
            InstructionKind::Call | InstructionKind::Return
        ) {
            assert_eq!(instruction.uses, prepared.prepared.request.locations);
            assert_eq!(instruction.may_defs, prepared.prepared.request.locations);
            assert!(instruction.must_defs.is_empty());
            assert!(instruction.uses.contains("state:other"));
        }
    }
    let rust = CompletedAnalysis::from_analyzer(
        crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
    );
    let native = NativeAnalyzer::from_capture(&core(), label, prepared)
        .unwrap()
        .complete()
        .unwrap();
    assert_eq!(rust.state(), native.state(), "{label}");
    (rust, native)
}
fn guard_roundtrip(prepared: &FilePreparedAnalysis) {
    prepared.validate_guard_admission().unwrap();
    let original = prepared.guard_admission().unwrap();
    assert_eq!(original.schema, "ariadne.guard-admission/v3");
    assert_eq!(original.profile, "bap-guard-admission-v3");
    let saved: guard::Report =
        serde_json::from_slice(&serde_json::to_vec(original).unwrap()).unwrap();
    guard::replay_report(&saved.input, &saved).unwrap();
    let mut changed = saved.clone();
    changed.input.producer.projection = "bap-bit-provenance-v9".into();
    assert!(guard::replay_report(&changed.input, &changed).is_err());
    let mut changed = saved.clone();
    changed.candidate_graph_sha256 = "0".repeat(64);
    assert!(guard::replay_report(&changed.input, &changed).is_err());
    for index in 0..saved.guards.len() {
        let mut changed = saved.clone();
        changed.guards[index].verdict = if changed.guards[index].verdict == guard::Verdict::Aligned
        {
            guard::Verdict::Misaligned
        } else {
            guard::Verdict::Aligned
        };
        assert!(guard::replay_report(&changed.input, &changed).is_err());
    }
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_guards_preserve_flag_independence_and_refuse_missing_rsp_facts() {
    for flag in [0xf8, 0xf9, 0xf5, 0xfd] {
        for (start, expected) in [
            (Some(0x1000), guard::Verdict::Aligned),
            (Some(0x1008), guard::Verdict::Misaligned),
            (None, guard::Verdict::Unknown),
        ] {
            let mut code = Vec::new();
            if let Some(value) = start {
                mov_rsp(&mut code, value);
            }
            code.push(flag);
            let store = ENTRY + code.len() as u64;
            code.extend(MOVAPS);
            code.push(0xc3);
            let snapshot = snapshot(&code, false);
            let query = query(store);
            let prepared = snapshot
                .prepare_with_bap_guard_admission(
                    &query,
                    &decoder(),
                    &config(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                    guard::Limits::default(),
                )
                .unwrap();
            assert_eq!(prepared.prepared.identity.ruleset, "bap-bit-provenance-v11");
            assert_eq!(
                prepared.guard_admission().unwrap().guards[0].verdict,
                expected
            );
            assert_eq!(
                prepared.prepared.request.instructions[&store].kind,
                if expected == guard::Verdict::Aligned {
                    InstructionKind::Ordinary
                } else {
                    InstructionKind::Stop
                }
            );
            parity(&prepared, &query, "advanced-source-guard");
            guard_roundtrip(&prepared);
        }
    }
    for bypass in [false, true] {
        let mut code = Vec::new();
        mov_rsp(&mut code, 0x1000);
        let flag_site = ENTRY + code.len() as u64;
        code.push(0xf8);
        if !bypass {
            call(&mut code);
        }
        let store = ENTRY + code.len() as u64;
        code.extend(MOVAPS);
        code.push(0xc3);
        let snapshot = snapshot(&code, false);
        let mut query = query(store);
        if bypass {
            query.entry_points.insert(flag_site);
        }
        let prepared = snapshot
            .prepare_with_bap_guard_admission(
                &query,
                &decoder(),
                &config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                guard::Limits::default(),
            )
            .unwrap();
        assert_eq!(
            prepared.guard_admission().unwrap().guards[0].verdict,
            guard::Verdict::Unknown
        );
        assert_eq!(
            prepared.prepared.request.instructions[&store].kind,
            InstructionKind::Stop
        );
        parity(&prepared, &query, "advanced-source-guard-alternative");
        guard_roundtrip(&prepared);
    }
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_new_state_and_coarsened_data_forms_preserve_rsp_guards() {
    // These are normal-completion projection tests. They do not establish that
    // arbitrary MXCSR inputs cannot fault or reconstruct vector-register values.
    for (name, bytes) in [
        ("ldmxcsr", &[0x0f, 0xae, 0x10][..]),
        ("stmxcsr", &[0x0f, 0xae, 0x18][..]),
        ("fldcw", &[0xd9, 0x28][..]),
        ("fnstcw", &[0xd9, 0x38][..]),
        ("nop-memory-encoding", &[0x0f, 0x1f, 0x00][..]),
        ("pshufb", &[0x66, 0x0f, 0x38, 0x00, 0xc1][..]),
    ] {
        let mut code = Vec::new();
        mov_rsp(&mut code, 0x1000);
        code.extend(bytes);
        let store = ENTRY + code.len() as u64;
        code.extend(MOVAPS);
        code.push(0xc3);
        let snapshot = snapshot(&code, false);
        let query = query(store);
        let prepared = snapshot
            .prepare_with_bap_guard_admission(
                &query,
                &decoder(),
                &config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                guard::Limits::default(),
            )
            .unwrap();
        assert_eq!(prepared.prepared.identity.ruleset, "bap-bit-provenance-v11");
        assert_eq!(
            prepared.guard_admission().unwrap().guards[0].verdict,
            guard::Verdict::Aligned,
            "{name}"
        );
        assert_eq!(
            prepared.prepared.request.instructions[&store].kind,
            InstructionKind::Ordinary,
            "{name}"
        );
        parity(&prepared, &query, name);
        guard_roundtrip(&prepared);
    }
}

fn table_sequence(flags: &[u8], combined: bool, opaque_call: bool) -> (Vec<u8>, u64, u64) {
    let mut code = Vec::new();
    if combined {
        mov_rsp(&mut code, 0x1000);
    }
    code.extend([0x89, 0xc8]); // MOV EAX,ECX: symbolic zero-extended index.
    code.extend(flags);
    if opaque_call {
        call(&mut code);
    }
    if combined {
        code.extend(MOVAPS);
    }
    let branch = ENTRY + code.len() as u64;
    // JB selects independently checked index ranges: EAX=0 versus EAX=1.
    // Neither table contents nor captured registers supply a branch result.
    code.extend([
        0x72, 7, 0x83, 0xf8, 0, 0x75, 26, 0xeb, 5, 0x83, 0xf8, 1, 0x75, 19,
    ]);
    code.extend([0x48, 0xba]); // MOV RDX,table base.
    code.extend(TABLE.to_le_bytes());
    code.extend([0x48, 0x63, 0x04, 0x82]); // MOVSXD RAX,dword [RDX+RAX*4].
    code.extend([0x48, 0x01, 0xd0]); // ADD RAX,RDX.
    let dispatch = ENTRY + code.len() as u64;
    code.extend([0xff, 0xe0, 0xc3]); // JMP RAX; abort RET.
    (code, branch, dispatch)
}

#[test]
#[ignore = "requires pinned BAP/LLVM; no source extension or native core"]
fn packaged_table_preparation_keeps_the_movaps_guard() {
    // CLD is supplied by the packaged lifter and leaves CF unknown. This
    // isolates the shared rooted/composed fixture from source-built flags.
    let (code, _, dispatch) = table_sequence(&[0xfc], true, false);
    let snapshot = snapshot(&code, false);
    let query = query(dispatch);
    let mut config = Config::from_env();
    config.source_extension = None;
    config.source_extension_mode = crate::bap::SourceExtensionMode::Basic;
    let mut bounded = setup(&snapshot, &query);
    bounded.limits = guard::Limits::default();
    let stopped = snapshot
        .prepare_bap_guarded_targets(
            &query,
            &decoder(),
            &config,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            bounded,
            target::Limits::default(),
        )
        .unwrap();
    assert_eq!(
        stopped.guard_admission().unwrap().stop.as_deref(),
        Some("guard-closure-round-limit")
    );
    assert!(stopped.guard_admission().unwrap().guards.is_empty());
    assert_eq!(
        stopped.prepared.request.instructions[&(ENTRY + 13)].kind,
        InstructionKind::Stop
    );
    let prepared = snapshot
        .prepare_bap_guarded_targets(
            &query,
            &decoder(),
            &config,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            setup(&snapshot, &query),
            target::Limits::default(),
        )
        .unwrap();
    let report = prepared.guard_admission().unwrap();
    assert_eq!(report.guards.len(), 1, "guard stop: {:?}", report.stop);
    assert_eq!(
        prepared.guard_admission().unwrap().guards[0].verdict,
        guard::Verdict::Aligned
    );
    prepared.validate_guard_admission().unwrap();
    prepared.validate_target_resolution().unwrap();
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_mandatory_counts_replay_guarded_table_composition() {
    let contract: serde_json::Value =
        serde_json::from_str(include_str!("../bap/fixtures/bit-count/contract.json")).unwrap();
    for case in contract["cases"].as_array().unwrap() {
        let text = case["bytes"].as_str().unwrap();
        let bytes: Vec<_> = (0..text.len())
            .step_by(2)
            .map(|at| u8::from_str_radix(&text[at..at + 2], 16).unwrap())
            .collect();
        let (mut code, _, dispatch) = table_sequence(&[0xf8], true, false);
        // Count after setting RSP, before MOV EAX,ECX and CLC. The later
        // table index and branch flag have independent expected definitions.
        code.splice(10..10, bytes.iter().copied());
        let snapshot = snapshot(&code, false);
        let query = query(dispatch + bytes.len() as u64);
        let prepared = snapshot
            .prepare_bap_guarded_targets(
                &query,
                &decoder(),
                &config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                setup(&snapshot, &query),
                target::Limits::default(),
            )
            .unwrap_or_else(|error| panic!("{}: {error}", case["name"]));
        let instruction = &prepared.prepared.request.instructions[&(ENTRY + 10)];
        assert_eq!(
            instruction.kind,
            InstructionKind::Ordinary,
            "{}",
            case["name"]
        );
        let guards = prepared.guard_admission().unwrap();
        assert_eq!(
            guards.guards.len(),
            1,
            "{}: {:?}",
            case["name"],
            guards.stop
        );
        assert_eq!(
            guards.guards[0].verdict,
            guard::Verdict::Aligned,
            "{}",
            case["name"]
        );
        let resolution = prepared
            .target_resolution()
            .unwrap()
            .resolutions
            .iter()
            .find(|row| row.site == format!("0x{:016x}", dispatch + bytes.len() as u64))
            .unwrap();
        assert!(
            resolution.complete,
            "{}: {:?}",
            case["name"], resolution.unresolved
        );
        assert_eq!(resolution.targets, vec![format!("0x{LEFT:016x}")]);
        guard_roundtrip(&prepared);
        prepared.validate_target_resolution().unwrap();
        prepared.validate_composition().unwrap();
        let (rust, _) = parity(&prepared, &query, case["name"].as_str().unwrap());
        let saved = crate::input::report::render_bound(
            &prepared,
            &rust,
            crate::input::report::ReportFormat::Json,
            false,
        )
        .unwrap();
        crate::input::report::validate_saved_composition(saved.as_bytes(), 16 * 1024 * 1024)
            .unwrap();
    }
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_flag_branches_resolve_tables_with_versioned_saved_composition() {
    for (flags, expected) in [
        (&[0xf8][..], vec![LEFT]),
        (&[0xf9][..], vec![RIGHT]),
        (&[0xf9, 0xf5][..], vec![LEFT]),
        (&[0xf8, 0xf5][..], vec![RIGHT]),
        (&[0xf5][..], vec![LEFT, RIGHT]),
        (&[0xfd][..], vec![LEFT, RIGHT]),
    ] {
        for combined in [false, true] {
            let (code, branch, dispatch) = table_sequence(flags, combined, false);
            let snapshot = snapshot(&code, false);
            let query = query(dispatch);
            let prepared = if combined {
                snapshot
                    .prepare_bap_guarded_targets(
                        &query,
                        &decoder(),
                        &config(),
                        &PreparationOptions::default(),
                        PrepareLimits::default(),
                        setup(&snapshot, &query),
                        target::Limits::default(),
                    )
                    .unwrap()
            } else {
                snapshot
                    .prepare_with_bap_target_resolution(
                        &query,
                        &decoder(),
                        &config(),
                        &PreparationOptions::default(),
                        PrepareLimits::default(),
                        target::Limits::default(),
                    )
                    .unwrap()
            };
            prepared.validate_target_resolution().unwrap();
            assert_eq!(
                prepared.target_resolution().unwrap().schema,
                "ariadne.indirect-target-resolution/v4"
            );
            assert_eq!(
                prepared.target_resolution().unwrap().profile,
                if combined {
                    "captured-local-indirect-targets/v3"
                } else {
                    "captured-indirect-targets/v2"
                }
            );
            let resolution = prepared
                .target_resolution()
                .unwrap()
                .resolutions
                .iter()
                .find(|r| r.site == format!("0x{dispatch:016x}"))
                .unwrap();
            if !resolution.complete
                && let Some(directory) = std::env::var_os("ARIADNE_ADVANCED_TEST_DEBUG")
            {
                let directory = PathBuf::from(directory);
                let target = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("target")
                    .canonicalize()
                    .unwrap();
                assert!(
                    directory
                        .parent()
                        .unwrap()
                        .canonicalize()
                        .unwrap()
                        .starts_with(&target)
                );
                std::fs::create_dir(&directory).unwrap();
                std::fs::write(directory.join("target.json"), serde_json::to_vec_pretty(&json!({
                    "flags": flags, "combined": combined,
                    "normalized": crate::bap::core_adapter::encode_request(&prepared.prepared.request).unwrap(),
                    "target_resolution": prepared.target_resolution(),
                })).unwrap()).unwrap();
            }
            assert!(
                resolution.complete,
                "{:x?}: {:?}",
                flags, resolution.unresolved
            );
            let targets: BTreeSet<_> = resolution
                .targets
                .iter()
                .map(|s| u64::from_str_radix(&s[2..], 16).unwrap())
                .collect();
            assert_eq!(
                targets,
                expected.iter().copied().collect(),
                "combined={combined}; frontier roots={:?}",
                resolution
                    .paths
                    .iter()
                    .filter(|path| path.frontier)
                    .map(|path| &path.root)
                    .collect::<Vec<_>>()
            );
            let branch_instruction = &prepared.prepared.request.instructions[&branch];
            assert_eq!(branch_instruction.kind, InstructionKind::Conditional);
            assert_eq!(branch_instruction.fall.len(), 1);
            assert_eq!(branch_instruction.targets.len(), 1);
            let (rust, _) = parity(&prepared, &query, "advanced-source-targets");
            let mut changed = prepared.clone();
            changed
                .prepared
                .instructions
                .get_mut(&branch)
                .unwrap()
                .bytes[0] ^= 1;
            assert!(changed.validate_target_resolution().is_err());
            if combined {
                assert_eq!(
                    prepared.guard_admission().unwrap().guards.len(),
                    1,
                    "combined fixture must exercise its MOVAPS guard"
                );
                guard_roundtrip(&prepared);
                prepared.validate_composition().unwrap();
                assert_eq!(
                    prepared.composition().unwrap().profile,
                    "captured-guarded-targets/v4"
                );
                assert_eq!(
                    prepared.composition().unwrap().schema,
                    "ariadne.guarded-target-resolution/v4"
                );
                let saved = crate::input::report::render_bound(
                    &prepared,
                    &rust,
                    crate::input::report::ReportFormat::Json,
                    false,
                )
                .unwrap();
                crate::input::report::validate_saved_composition(
                    saved.as_bytes(),
                    16 * 1024 * 1024,
                )
                .unwrap();
                let mut changed: serde_json::Value = serde_json::from_str(&saved).unwrap();
                changed["composition"]["profile"] = json!("captured-guarded-targets/v3");
                assert!(
                    crate::input::report::validate_saved_composition(
                        &serde_json::to_vec(&changed).unwrap(),
                        16 * 1024 * 1024
                    )
                    .is_err()
                );
            }
        }
    }
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_branch_bypasses_and_calls_do_not_inherit_flag_certainty() {
    for opaque_call in [false, true] {
        let (code, branch, dispatch) = table_sequence(&[0xf8], false, opaque_call);
        let snapshot = snapshot(&code, false);
        let mut query = query(dispatch);
        if !opaque_call {
            query.entry_points.insert(branch);
        }
        let prepared = snapshot
            .prepare_with_bap_target_resolution(
                &query,
                &decoder(),
                &config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                target::Limits::default(),
            )
            .unwrap();
        let resolution = prepared
            .target_resolution()
            .unwrap()
            .resolutions
            .iter()
            .find(|r| r.site == format!("0x{dispatch:016x}"))
            .unwrap();
        if resolution.complete {
            assert_eq!(
                resolution.targets.iter().cloned().collect::<BTreeSet<_>>(),
                [format!("0x{LEFT:016x}"), format!("0x{RIGHT:016x}")].into()
            );
        } else {
            assert!(!resolution.unresolved.is_empty());
        }
        assert_eq!(
            prepared.prepared.request.instructions[&branch].kind,
            InstructionKind::Conditional
        );
        parity(&prepared, &query, "advanced-source-target-unknown");
    }
}

#[test]
#[ignore = "requires advanced source BAP producer, LLVM and current native core"]
fn native_memory_refinement_keeps_writers_across_unknowns_and_replays_sources() {
    for flag in [0xf8, 0xf9, 0xf5, 0xfd] {
        for mode in 0..6 {
            let mut code = vec![0x48, 0x89, 0x43, if mode == 1 { 0x28 } else { 0x18 }];
            code.push(flag);
            if mode == 2 {
                call(&mut code);
            }
            if mode == 3 {
                code.extend([0x48, 0x89, 0xcb]);
            } // MOV RBX,RCX loses base identity.
            if mode == 4 {
                // Unknown ZF selects either a preserved or an unrelated base.
                code.extend([0x74, 3, 0x48, 0x89, 0xcb]);
            }
            if mode == 5 {
                code.extend([0x0f, 0xa2]); // CPUID remains an opaque ordinary effect.
            }
            let load = ENTRY + code.len() as u64;
            code.extend([0x48, 0x8b, 0x43, 0x28, 0xc3]);
            let snapshot = snapshot(&code, false);
            let mut query = query(load);
            query.slice_seeds = [load].into();
            let prepared = snapshot
                .prepare_with_bap_refinement(
                    &query,
                    &decoder(),
                    &config(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                )
                .unwrap();
            assert_eq!(prepared.prepared.identity.ruleset, "bap-bit-provenance-v10");
            assert!(!prepared.refinement.is_empty());
            assert!(
                prepared
                    .refinement
                    .values()
                    .all(|receipt| receipt.profile == "bap-memory-refinement-v2")
            );
            let (rust, native) = parity(&prepared, &query, "advanced-source-memory");
            let question = crate::investigation::FaultAddressQuestion {
                site: load,
                memory_access: 0,
            };
            let assess = |view: &dyn AnalysisView| {
                let bound =
                    crate::input::investigation::bind_memory_refinement(&prepared, view).unwrap();
                crate::investigation::assess_memory_origins(
                    &bound,
                    question.clone(),
                    Default::default(),
                )
                .unwrap()
            };
            let report = assess(&rust);
            assert_eq!(report, assess(&native));
            let writer = report
                .candidates
                .iter()
                .find(|c| {
                    c.origin == crate::investigation::OriginKind::Instruction && c.site == ENTRY
                })
                .unwrap();
            assert_eq!(writer.disposition == "excluded_within_scope", mode == 0);
            assert!(
                report
                    .candidates
                    .iter()
                    .any(|c| c.origin == crate::investigation::OriginKind::Entry
                        && c.disposition != "excluded_within_scope")
            );
            let encoded = crate::reports::encode_memory_provenance(&report).unwrap();
            assert_eq!(
                crate::reports::decode_memory_provenance(&serde_json::to_vec(&encoded).unwrap())
                    .unwrap(),
                report
            );
            let mut changed = encoded.clone();
            changed["candidates"][0]["disposition"] = json!("excluded_within_scope");
            assert!(
                crate::reports::decode_memory_provenance(&serde_json::to_vec(&changed).unwrap())
                    .is_err()
            );
            let mut changed = encoded;
            changed["input"]["sites"][0]["projection"] = json!("bap-bit-provenance-v9");
            assert!(
                crate::reports::decode_memory_provenance(&serde_json::to_vec(&changed).unwrap())
                    .is_err()
            );
        }
    }
}

#[test]
#[ignore = "requires advanced source BAP producer and rebuilt native proof validators"]
fn native_composed_validator_rejects_tampering_without_rust_prevalidation() {
    let (code, _, dispatch) = table_sequence(&[0xf8], true, false);
    let snapshot = snapshot(&code, false);
    let query = query(dispatch);
    let prepared = snapshot
        .prepare_bap_guarded_targets(
            &query,
            &decoder(),
            &config(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
            setup(&snapshot, &query),
            target::Limits::default(),
        )
        .unwrap();
    let profile = prepared.composition().unwrap().profile.clone();
    assert_eq!(profile, "captured-guarded-targets/v4");
    let good = NativeAnalyzer::capture_wire_for_test(&prepared).unwrap();
    let run = |wire: &serde_json::Value| {
        crate::bap::core_session::CoreSession::start_profile(
            &core(),
            "advanced-native-refusal",
            &prepared.prepared.request.snapshot_id,
            &profile,
            wire,
        )
    };
    let (session, response) = run(&good).unwrap();
    assert!(response.error.is_none());
    drop(session);
    for mutation in [
        "capture-profile",
        "guard-profile",
        "memory-premise",
        "old-composition",
        "candidate-binding",
        "flag-byte",
    ] {
        let mut bad = good.clone();
        match mutation {
            "capture-profile" => {
                bad["capture"]["sites"][0]["projection"] = json!("bap-bit-provenance-v9")
            }
            "guard-profile" => {
                bad["guard_admission"]["input"]["producer"]["projection"] =
                    json!("bap-bit-provenance-v9")
            }
            "memory-premise" => bad["target_resolution"]["memory_premise"] = json!("ObservedOnly"),
            "old-composition" => {
                bad["composition"]["profile"] = json!("captured-guarded-targets/v3")
            }
            "candidate-binding" => bad["composition"]["candidate_sha256"] = json!("0".repeat(64)),
            "flag-byte" => {
                let flag_site = format!("0x{:016x}", ENTRY + 12);
                let site = bad["capture"]["sites"]
                    .as_array_mut()
                    .unwrap()
                    .iter_mut()
                    .find(|site| site["address"].as_str() == Some(flag_site.as_str()))
                    .unwrap();
                assert_eq!(site["bytes"], "f8");
                site["bytes"] = json!("f9");
            }
            _ => unreachable!(),
        }
        match run(&bad) {
            Ok((session, response)) => {
                assert!(response.error.is_some(), "native accepted {mutation}");
                drop(session);
            }
            Err(error) => assert!(
                error.to_string().contains("partial frame/EOF"),
                "unexpected {mutation} failure: {error}"
            ),
        }
    }
}
