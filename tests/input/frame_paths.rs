use ariadne::input::{FileSnapshot, OpenLimits};
use ariadne::investigation::FrameRecoveryLimits;
use std::path::PathBuf;
fn fixture(name: &str) -> FileSnapshot {
    FileSnapshot::open_minidump(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(format!("tests/input/fixtures/frame_paths/{name}.dmp")),
        OpenLimits::default(),
    )
    .unwrap()
}
#[test]
fn captured_allocations_saves_and_frame_pointer_restore_only_valid_registers() {
    for name in [
        "diamond",
        "control-only",
        "large-alloc-16",
        "large-alloc-32",
        "push-rbx",
        "save-rbp",
        "frame-pointer",
    ] {
        let chain = fixture(name)
            .recover_thread_frames(17, FrameRecoveryLimits::default())
            .unwrap();
        assert_eq!(chain.frames.len(), 3, "{name}: {}", chain.stop_reason);
        assert_eq!(chain.stop_reason, "zero-return-boundary", "{name}");
        assert!(!chain.frames[1].registers.contains_key("rax"));
        assert!(!chain.frames[1].registers.contains_key("rcx"));
        assert_eq!(
            chain.frames[0].register_evidence["rip"].classification,
            ariadne::investigation::Classification::Observed
        );
        assert_eq!(
            chain.frames[1].register_evidence["rip"].classification,
            ariadne::investigation::Classification::DerivedUnderPremises
        );
        assert_eq!(chain.frames[1].pc, 0x400315);
        if name == "push-rbx" {
            assert_eq!(chain.frames[1].registers["rbx"], 0x12345678);
        }
        if name == "save-rbp" {
            assert_eq!(chain.frames[1].registers["rbp"], 0x12345678);
        }
        chain.validate().unwrap();
        fixture(name).validate_thread_frames(&chain).unwrap();
    }
}
#[test]
fn recursive_frames_keep_distinct_stack_contexts() {
    let chain = fixture("recursive")
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    assert_eq!(chain.frames.len(), 3);
    assert_eq!(chain.frames[1].pc, chain.frames[2].pc);
    assert_ne!(chain.frames[1].sp, chain.frames[2].sp);
    chain.validate().unwrap();
}

#[test]
fn self_consistent_context_offset_forgery_is_rejected_by_live_capture_binding() {
    use sha2::{Digest, Sha256};
    let snapshot = fixture("diamond");
    let original = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let mut value = serde_json::to_value(&original).unwrap();
    value["seed"]["context_offset"] =
        serde_json::json!(value["seed"]["context_offset"].as_u64().unwrap() + 8);
    for evidence in value["frames"][0]["register_evidence"]
        .as_object_mut()
        .unwrap()
        .values_mut()
    {
        evidence["context_file_offset"] =
            serde_json::json!(evidence["context_file_offset"].as_u64().unwrap() + 8);
    }
    let mut forged: ariadne::investigation::CapturedFrameChain =
        serde_json::from_value(value).unwrap();
    forged.chain_id = String::new();
    forged.chain_id = format!("{:x}", Sha256::digest(serde_json::to_vec(&forged).unwrap()));
    forged.validate().unwrap();
    assert!(snapshot.validate_thread_frames(&forged).is_err());
}
#[test]
fn missing_and_unsupported_unwind_evidence_stops_without_scanning() {
    for name in [
        "missing-control",
        "prologue",
        "epilogue",
        "chained",
        "unsorted-table",
        "missing-table-bytes",
    ] {
        let chain = fixture(name)
            .recover_thread_frames(17, FrameRecoveryLimits::default())
            .unwrap();
        assert!(chain.frames.len() <= 1, "{name}");
        assert_ne!(chain.stop_reason, "zero-return-boundary", "{name}");
        chain.validate().unwrap();
    }
}
#[test]
fn frame_recovery_budgets_and_receipt_tampering_are_checked() {
    let s = fixture("diamond");
    let chain = s
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let mut null_bytes = std::fs::read(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/input/fixtures/frame_paths/diamond.dmp"),
    )
    .unwrap();
    let context_pc = chain.frames[0].register_evidence["rip"]
        .context_file_offset
        .unwrap() as usize;
    null_bytes[context_pc..context_pc + 8].copy_from_slice(&0u64.to_le_bytes());
    let exception_pc = s
        .metadata()
        .streams
        .iter()
        .find(|s| s.kind == 6)
        .unwrap()
        .file_offset as usize
        + 24;
    null_bytes[exception_pc..exception_pc + 8].copy_from_slice(&0u64.to_le_bytes());
    let null = FileSnapshot::from_minidump_bytes(null_bytes, OpenLimits::default())
        .unwrap()
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    assert_eq!(null.frames[0].pc, 0);
    assert_ne!(null.stop_reason, "zero-return-boundary");
    null.validate().unwrap();
    let limited = s
        .recover_thread_frames(
            17,
            FrameRecoveryLimits {
                max_runtime_entries: 0,
                ..FrameRecoveryLimits::default()
            },
        )
        .unwrap();
    assert!(limited.truncated);
    assert_eq!(limited.stop_reason, "runtime-table-budget");
    limited.validate().unwrap();
    let mut bytes = std::fs::read(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/input/fixtures/frame_paths/diamond.dmp"),
    )
    .unwrap();
    let offset =
        s.read_prefix(0x400098 + 140, 4).unwrap().spans[0].contributors[0].file_offset as usize;
    bytes[offset..offset + 4].copy_from_slice(&35u32.to_le_bytes());
    let malformed = FileSnapshot::from_minidump_bytes(bytes, OpenLimits::default())
        .unwrap()
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    assert!(!malformed.truncated);
    assert_eq!(malformed.stop_reason, "invalid-runtime-table-shape");
    malformed.validate().unwrap();
    let chain = s
        .recover_thread_frames(
            17,
            FrameRecoveryLimits {
                max_frames: 1,
                ..FrameRecoveryLimits::default()
            },
        )
        .unwrap();
    assert_eq!(chain.frames.len(), 1);
    assert!(chain.truncated);
    chain.validate().unwrap();
    let chain = s
        .recover_thread_frames(
            17,
            FrameRecoveryLimits {
                max_read_bytes: 0,
                ..FrameRecoveryLimits::default()
            },
        )
        .unwrap();
    assert!(chain.truncated);
    chain.validate().unwrap();
    assert!(
        s.recover_thread_frames(999, FrameRecoveryLimits::default())
            .is_err()
    );
    let mut chain = s
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    chain.frames[1].pc += 1;
    assert!(chain.validate().is_err());
    let mut chain = s
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    chain.reads[0].spans[0].contributors[0].file_offset = u64::MAX;
    assert!(chain.validate().is_err());
}
#[test]
fn cli_rejects_invalid_frame_questions_before_helper_start() {
    let exe = env!("CARGO_BIN_EXE_ariadne-minidump");
    let dump = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures/frame_paths/diamond.dmp");
    for extra in [
        vec!["--list-frame-paths", "0:1", "--path-count-bound", "3"],
        vec!["--list-frame-paths", "2:0", "--path-count-bound", "0"],
        vec!["--list-frame-paths", "2:0"],
        vec![
            "--list-frame-paths",
            "2:0",
            "--path-count-bound",
            "3",
            "--entry",
            "0x400400",
        ],
    ] {
        let output = std::process::Command::new(exe)
            .arg(&dump)
            .args([
                "--decoder-reference",
                "/nonexistent/helper",
                "--format",
                "json",
            ])
            .args(extra)
            .output()
            .unwrap();
        assert!(!output.status.success());
        assert!(!String::from_utf8_lossy(&output.stderr).contains("LLVM MC decoder I/O"));
    }
}

struct GuardLimitFile(PathBuf);
impl GuardLimitFile {
    fn new(name: &str, bytes: &[u8]) -> Self {
        let path = std::env::temp_dir().join(format!(
            "ariadne-guard-limits-{}-{name}.json",
            std::process::id()
        ));
        std::fs::write(&path, bytes).unwrap();
        Self(path)
    }
}
impl Drop for GuardLimitFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}
fn guard_cli_rejects(options: &[&str], message: &str) {
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "missing.dmp",
            "--decoder-reference",
            "/nonexistent/helper",
            "--list-frame-paths",
            "0:0",
            "--path-count-bound",
            "2",
            "--format",
            "json",
        ])
        .args(options)
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stderr).contains(message),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn cli_guard_limits_require_guarded_frame_mode_and_unique_option() {
    guard_cli_rejects(
        &["--guard-admission-limits", "missing.json"],
        "--guard-admission-limits requires --assume-windows-call-entry",
    );
    guard_cli_rejects(
        &[
            "--assume-windows-call-entry",
            "--guard-admission-limits",
            "missing.json",
            "--guard-admission-limits",
            "missing.json",
        ],
        "unknown or duplicate option: --guard-admission-limits",
    );
    guard_cli_rejects(
        &["--assume-windows-call-entry", "--guard-admission-limits"],
        "usage:",
    );
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "missing.dmp",
            "--decoder-reference",
            "/nonexistent/helper",
            "--entry",
            "0x400200",
            "--format",
            "json",
            "--assume-windows-call-entry",
            "--guard-admission-limits",
            "missing.json",
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stderr)
            .contains("frame options require --list-frame-paths"),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn cli_frame_targets_require_guard_assumption_and_keep_limit_options_independent() {
    guard_cli_rejects(
        &["--resolve-indirect-targets"],
        "frame target resolution requires --assume-windows-call-entry",
    );
    guard_cli_rejects(
        &[
            "--assume-windows-call-entry",
            "--target-resolution-limits",
            "missing.json",
        ],
        "--target-resolution-limits requires --resolve-indirect-targets",
    );
    let missing = std::env::temp_dir().join(format!(
        "ariadne-composition-missing-{}.dmp",
        std::process::id()
    ));
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(&missing)
        .args([
            "--decoder-reference",
            "/nonexistent/helper",
            "--list-frame-paths",
            "0:0",
            "--path-count-bound",
            "2",
            "--format",
            "json",
            "--assume-windows-call-entry",
            "--resolve-indirect-targets",
        ])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("input I/O:"),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper in remote WSL"]
fn composed_frame_cli_roundtrip_retains_paired_proofs_and_rejects_stripping() {
    use ariadne::{
        bap::{composition, guard_admission, target_resolution},
        reports,
    };
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(root.join("tests/input/fixtures/guard-frame.dmp"))
        .arg("--decoder-reference")
        .arg(root.join("target/ariadne-llvm-mc"))
        .args([
            "--list-frame-paths",
            "0:0",
            "--path-count-bound",
            "2",
            "--assume-windows-call-entry",
            "--resolve-indirect-targets",
            "--format",
            "json",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let listing = reports::decode_frame_paths(&output.stdout).unwrap();
    let value = reports::encode_frame_paths(&listing).unwrap();
    assert_eq!(value["schema"], "ariadne.frame-paths/v4");
    let proof = &value["input"]["graphs"][0]["guard_admission"];
    assert_eq!(proof["composition"]["profile"], composition::PROFILE);
    assert_eq!(
        proof["target_resolution"]["profile"],
        target_resolution::LOCAL_PROFILE
    );
    assert_eq!(proof["report"]["profile"], guard_admission::PROFILE);
    assert!(proof["normalized"].is_object());
    assert!(proof["sites"].as_array().is_some_and(|s| !s.is_empty()));
    for field in [
        "composition",
        "target_resolution",
        "report",
        "normalized",
        "sites",
    ] {
        let mut forged = value.clone();
        forged["input"]["graphs"][0]["guard_admission"]
            .as_object_mut()
            .unwrap()
            .remove(field);
        assert!(
            reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err(),
            "stripped {field}"
        );
    }
    for (field, replacement) in [
        ("query_id", serde_json::json!("0".repeat(64))),
        ("semantic_profile", serde_json::json!("ordinary")),
    ] {
        let mut forged = value.clone();
        forged["input"]["graphs"][0]["identity"][field] = replacement;
        assert!(
            reports::decode_frame_paths(&serde_json::to_vec(&forged).unwrap()).is_err(),
            "changed {field}"
        );
    }
    let mut stale = value.clone();
    stale["input"]["graphs"][0]["guard_admission"]["composition"]["candidate_epoch"] =
        serde_json::json!(u64::MAX);
    assert!(reports::decode_frame_paths(&serde_json::to_vec(&stale).unwrap()).is_err());
    let mut wrong_schema = value.clone();
    wrong_schema["schema"] = serde_json::json!("ariadne.frame-paths/v2");
    assert!(reports::decode_frame_paths(&serde_json::to_vec(&wrong_schema).unwrap()).is_err());
    for format in [reports::Format::Text, reports::Format::Dot] {
        let rendered = reports::render_frame_paths(&listing, format).unwrap();
        assert!(rendered.contains(target_resolution::MEMORY_PREMISE));
        assert!(rendered.contains(guard_admission::ABI_POLICY));
        assert!(rendered.contains(composition::PROFILE));
    }
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper in remote WSL"]
fn paired_minidump_report_retains_exact_full_source_commitment_in_all_formats() {
    use ariadne::{
        AnalysisView, Analyzer, CompletedAnalysis,
        bap::{guard_admission as guard, target_resolution as target},
        effects::PreparationOptions,
        input::{
            FramePreparation, PrepareLimits,
            report::{self, ReportFormat},
        },
    };
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let snapshot = FileSnapshot::open_minidump(
        root.join("tests/input/fixtures/guard-frame.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let decoder = root.join("target/ariadne-llvm-mc");
    let config = ariadne::bap::Config::from_env();
    let options = PreparationOptions::default();
    let setup = FramePreparation {
        decoder: &decoder,
        config: &config,
        options: &options,
        limits: PrepareLimits::default(),
    };
    let prepared = snapshot
        .prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(
            &chain,
            0,
            0x400200,
            &setup,
            guard::Limits::default(),
            target::Limits::default(),
        )
        .unwrap();
    let completed =
        CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone()).unwrap());
    assert_eq!(completed.request(), &prepared.prepared.request);
    let saved = report::render_bound(&prepared, &completed, ReportFormat::Json, false).unwrap();
    let value: serde_json::Value = serde_json::from_str(&saved).unwrap();
    assert_eq!(value["schema"], "ariadne-minidump-report-v5");
    report::validate_saved_composition(saved.as_bytes(), 64 * 1024 * 1024).unwrap();
    let mut downgraded = value.clone();
    downgraded["schema"] = serde_json::json!("ariadne-minidump-report-v4");
    assert!(
        report::validate_saved_composition(
            &serde_json::to_vec(&downgraded).unwrap(),
            64 * 1024 * 1024
        )
        .is_err()
    );
    let sources: Vec<ariadne::investigation::SiteEvidence> =
        serde_json::from_value(value["capture_sources"].clone()).unwrap();
    let composition = prepared.composition().unwrap();
    let expected = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-composed-capture/v2",
            &sources,
            &composition.binding_sha256,
        ))
        .unwrap(),
    );
    let profile = value["identity"]["semantic_profile"].as_str().unwrap();
    let mut forged = value.clone();
    let mut forged_sources = sources.clone();
    let source = forged_sources
        .iter_mut()
        .find(|s| !s.bytes_hex.is_empty())
        .unwrap();
    source.ast_sha256 = Some("1".repeat(64));
    let forged_binding = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-composed-capture/v2",
            &forged_sources,
            &composition.binding_sha256,
        ))
        .unwrap(),
    );
    forged["capture_sources"] = serde_json::to_value(forged_sources).unwrap();
    forged["identity"]["semantic_profile"] =
        serde_json::json!(profile.replace(&expected, &forged_binding));
    assert!(
        report::validate_saved_composition(&serde_json::to_vec(&forged).unwrap(), 64 * 1024 * 1024)
            .is_err()
    );
    let committed_prefix = profile.split_once(":bap-guard-admission-v1:").unwrap().0;
    assert_eq!(committed_prefix.rsplit(':').next(), Some(expected.as_str()));
    assert_eq!(
        value["composition"],
        serde_json::to_value(composition).unwrap()
    );
    assert_eq!(
        value["guard_admission"],
        serde_json::to_value(prepared.guard_admission().unwrap()).unwrap()
    );
    assert_eq!(
        value["target_resolution"],
        serde_json::to_value(prepared.target_resolution().unwrap()).unwrap()
    );
    let mut altered_sources = sources;
    altered_sources[0].spans[0].contributors[0].file_offset += 1;
    let altered = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-composed-capture/v2",
            &altered_sources,
            &composition.binding_sha256,
        ))
        .unwrap(),
    );
    assert_ne!(altered, expected);
    let serialized_profile = serde_json::to_string(profile).unwrap();
    for format in [ReportFormat::Text, ReportFormat::Dot] {
        let rendered = report::render_bound(&prepared, &completed, format, false).unwrap();
        assert!(rendered.contains(&serialized_profile));
        assert!(rendered.contains(guard::ABI_POLICY));
        assert!(rendered.contains(target::MEMORY_PREMISE));
    }
}

#[test]
fn cli_request_budget_rejects_invalid_and_duplicate_options_before_dump_access() {
    for value in ["0", "-1", "18446744073709551616", "1.5", "+1"] {
        guard_cli_rejects(
            &["--bap-core-max-request-bytes", value],
            "--bap-core-max-request-bytes expects a positive unsigned byte count",
        );
    }
    guard_cli_rejects(&["--bap-core-max-request-bytes"], "usage:");
    guard_cli_rejects(
        &[
            "--bap-core-max-request-bytes",
            "33554432",
            "--bap-core-max-request-bytes",
            "33554432",
        ],
        "unknown or duplicate option: --bap-core-max-request-bytes",
    );
}

#[test]
fn cli_request_budget_accepts_positive_values_above_and_below_default() {
    let missing_dump = std::env::temp_dir().join(format!(
        "ariadne-missing-request-budget-{}.dmp",
        std::process::id()
    ));
    assert!(!missing_dump.exists());
    let run = |options: &[&str]| {
        std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
            .arg(&missing_dump)
            .args([
                "--decoder-reference",
                "/nonexistent/helper",
                "--entry",
                "0x400200",
                "--format",
                "json",
            ])
            .args(options)
            .output()
            .unwrap()
    };
    let baseline = run(&[]);
    assert!(!baseline.status.success());
    assert!(
        String::from_utf8_lossy(&baseline.stderr).contains("input I/O:"),
        "{}",
        String::from_utf8_lossy(&baseline.stderr)
    );
    for value in ["1", "8388609", "33554432"] {
        let output = run(&["--bap-core-max-request-bytes", value]);
        assert!(!output.status.success());
        assert_eq!(output.stderr, baseline.stderr, "{value}");
    }
}

#[test]
fn cli_guard_limits_reject_invalid_json_before_dump_or_helper_access() {
    let valid = serde_json::to_value(ariadne::bap::guard_admission::Limits::default()).unwrap();
    let mut missing = valid.clone();
    missing
        .as_object_mut()
        .unwrap()
        .remove("max_evidence_bytes");
    let mut unknown = valid.clone();
    unknown["max_unrecognized"] = serde_json::json!(1);
    let valid_text = serde_json::to_string(&valid).unwrap();
    let duplicate = format!("{{\"max_sites\":1,{}", &valid_text[1..]);
    let mut cases = vec![
        (
            serde_json::to_vec(&missing).unwrap(),
            "missing field `max_evidence_bytes`",
        ),
        (
            serde_json::to_vec(&unknown).unwrap(),
            "unknown field `max_unrecognized`",
        ),
        (duplicate.into_bytes(), "duplicate field: max_sites"),
        (b"{".to_vec(), "EOF"),
        (b"[]".to_vec(), "expects a JSON object"),
        (
            b"[4096,16384,131072,262144,8,4194304,1000]".to_vec(),
            "expects a JSON object",
        ),
        (vec![b' '; 8193], "guard admission limits input byte budget"),
    ];
    for invalid in ["-1", "1.5", "18446744073709551616"] {
        cases.push((
            valid_text
                .replace("\"max_sites\":4096", &format!("\"max_sites\":{invalid}"))
                .into_bytes(),
            "invalid",
        ));
    }
    for (index, (bytes, expected)) in cases.iter().enumerate() {
        let file = GuardLimitFile::new(&format!("invalid-{index}"), bytes);
        guard_cli_rejects(
            &[
                "--assume-windows-call-entry",
                "--guard-admission-limits",
                file.0.to_str().unwrap(),
            ],
            expected,
        );
    }
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime, LLVM decode helper and accepted native core"]
fn frame_path_cli_accepts_above_default_guard_limits_and_binds_full_report() {
    use ariadne::bap::guard_admission;
    let limits = guard_admission::Limits {
        max_sites: 8192,
        max_edges: 32768,
        max_residue_updates: 262144,
        max_transfer_evaluations: 524288,
        max_closure_rounds: 16,
        max_evidence_bytes: 32 * 1024 * 1024,
        max_elapsed_ms: 10000,
    };
    let mut bytes = serde_json::to_vec(&limits).unwrap();
    bytes.resize(8192, b' ');
    let file = GuardLimitFile::new("native", &bytes);
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for (fixture, pair, count, frames, has_guard) in [
        ("guard-frame.dmp", "0:0", 1, 1, true),
        ("frame_paths/diamond.dmp", "2:0", 2, 3, false),
    ] {
        let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
            .arg(root.join("tests/input/fixtures").join(fixture))
            .arg("--decoder-reference")
            .arg(root.join("target/ariadne-llvm-mc"))
            .args([
                "--list-frame-paths",
                pair,
                "--path-count-bound",
                "3",
                "--assume-windows-call-entry",
                "--guard-admission-limits",
            ])
            .arg(&file.0)
            .args([
                "--bap-core-max-request-bytes",
                "33554432",
                "--analysis-backend",
                "bap",
                "--format",
                "json",
            ])
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{fixture}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let listing = ariadne::reports::decode_frame_paths(&output.stdout).unwrap();
        assert!(listing.available, "{fixture}: {}", listing.stop_reason);
        assert_eq!(listing.returned_count, count);
        let encoded = ariadne::reports::encode_frame_paths(&listing).unwrap();
        assert_eq!(encoded["schema"], "ariadne.frame-paths/v2");
        let graphs = encoded["input"]["graphs"].as_array().unwrap();
        assert_eq!(graphs.len(), frames);
        let configured = serde_json::to_value(&limits).unwrap();
        for graph in graphs {
            let proof = &graph["guard_admission"]["report"];
            assert_eq!(proof["input"]["limits"], configured);
            assert_eq!(
                proof["input"]["premises"][0]["policy"],
                guard_admission::ABI_POLICY
            );
        }
        if has_guard {
            assert_eq!(
                graphs[0]["guard_admission"]["report"]["guards"][0]["verdict"],
                "aligned"
            );
        }
        for format in [
            ariadne::reports::Format::Text,
            ariadne::reports::Format::Dot,
        ] {
            let rendered = ariadne::reports::render_frame_paths(&listing, format).unwrap();
            assert!(rendered.contains(guard_admission::ABI_POLICY));
        }
    }
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime, LLVM decode helper and accepted native core"]
fn frame_path_cli_native_reference_parity_on_finite_diamond_and_recursion() {
    let exe = env!("CARGO_BIN_EXE_ariadne-minidump");
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for name in ["diamond", "recursive"] {
        let mut results = Vec::new();
        for backend in ["rust", "bap"] {
            let output = std::process::Command::new(exe)
                .arg(root.join(format!("tests/input/fixtures/frame_paths/{name}.dmp")))
                .args(["--decoder-reference"])
                .arg(root.join("target/ariadne-llvm-mc"))
                .args([
                    "--list-frame-paths",
                    "0x2:0x0",
                    "--path-count-bound",
                    "10",
                    "--analysis-backend",
                    backend,
                    "--format",
                    "json",
                ])
                .output()
                .unwrap();
            assert!(
                output.status.success(),
                "{name}/{backend}: {}",
                String::from_utf8_lossy(&output.stderr)
            );
            let decoded = ariadne::reports::decode_frame_paths(&output.stdout).unwrap();
            assert!(decoded.available, "{name}: {}", decoded.stop_reason);
            assert_eq!(decoded.returned_count, 2, "{name}: {:?}", decoded.gaps);
            let mut value = serde_json::from_slice::<serde_json::Value>(&output.stdout).unwrap();
            value.as_object_mut().unwrap().remove("elapsed_ms");
            results.push(value);
        }
        assert_eq!(results[0], results[1], "{name}");
    }
}

/// Decompress the source-bound 2026-10-14 artifacts on the remote runner and
/// provide the exact paths. These large artifacts are never generated by the test.
#[test]
#[ignore = "requires decompressed retained 2026-10-14 combined reports; run in remote WSL"]
fn retained_combined_v1_minidump_and_frame_reports_replay_after_upgrade() {
    let minidump = std::fs::read(
        std::env::var_os("ARIADNE_LEGACY_COMPOSED_MINIDUMP")
            .expect("retained minidump report path"),
    )
    .unwrap();
    let value =
        ariadne::input::report::validate_saved_composition(&minidump, 256 * 1024 * 1024).unwrap();
    assert_eq!(value["schema"], "ariadne-minidump-report-v4");
    assert_eq!(
        value["composition"]["model_sha256"],
        ariadne::bap::composition::LEGACY_MODEL_SHA256
    );
    assert_eq!(
        value["composition"]["checker_sha256"],
        ariadne::bap::composition::LEGACY_CHECKER_SHA256
    );
    let mut forged = value.clone();
    forged["composition"]["profile"] = serde_json::json!(ariadne::bap::composition::PROFILE);
    assert!(
        ariadne::input::report::validate_saved_composition(
            &serde_json::to_vec(&forged).unwrap(),
            256 * 1024 * 1024
        )
        .is_err()
    );
    let frame = std::fs::read(
        std::env::var_os("ARIADNE_LEGACY_COMPOSED_FRAME").expect("retained frame report path"),
    )
    .unwrap();
    let listing =
        ariadne::reports::decode_frame_paths_with_limit(&frame, 256 * 1024 * 1024).unwrap();
    assert_eq!(
        listing.schema,
        ariadne::investigation::LEGACY_COMPOSED_FRAME_PATH_SCHEMA
    );
    assert!(!listing.available);
    assert_eq!(listing.returned_count, 0);
}

#[test]
fn combined_profile_query_digest_preserves_ordered_loop_evidence() {
    use ariadne::bap::core_protocol::{
        COMPOSED_PROFILE, LEGACY_COMPOSED_PROFILE, profile_query_digest,
    };
    let input = serde_json::json!({"ordered_edge_word":[true, false, true]});
    let changed = serde_json::json!({"ordered_edge_word":[false, true, true]});
    for profile in [LEGACY_COMPOSED_PROFILE, COMPOSED_PROFILE] {
        assert_ne!(
            profile_query_digest("snapshot", "recovery", profile, &input).unwrap(),
            profile_query_digest("snapshot", "recovery", profile, &changed).unwrap()
        );
    }
    assert_ne!(
        profile_query_digest("snapshot", "recovery", LEGACY_COMPOSED_PROFILE, &input).unwrap(),
        profile_query_digest("snapshot", "recovery", COMPOSED_PROFILE, &input).unwrap()
    );
}
