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
