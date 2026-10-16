use ariadne::investigation::FrameStructureLimits;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicUsize, Ordering};

static NEXT_FILE: AtomicUsize = AtomicUsize::new(0);

struct TempFile(PathBuf);
impl TempFile {
    fn new(bytes: &[u8]) -> Self {
        let path = std::env::temp_dir().join(format!(
            "ariadne-frame-structure-policy-{}-{}.json",
            std::process::id(),
            NEXT_FILE.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::write(&path, bytes).unwrap();
        Self(path)
    }

    fn policy(policy: &FrameStructureLimits) -> Self {
        Self::new(&serde_json::to_vec(policy).unwrap())
    }
}
impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn invoke(options: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "/nonexistent/ariadne-frame-structure.dmp",
            "--decoder-reference",
            "/nonexistent/ariadne-frame-structure-decoder",
            "--format",
            "json",
        ])
        .args(options)
        .output()
        .unwrap()
}

fn rejects(options: &[&str], expected: &str) {
    let output = invoke(options);
    assert!(!output.status.success());
    let error = String::from_utf8_lossy(&output.stderr);
    assert!(error.contains(expected), "{error}");
    assert!(!error.contains("LLVM MC decoder I/O"), "{error}");
}

#[test]
fn structure_question_rejects_legacy_modes_before_dump_access() {
    for options in [
        vec!["--entry", "0x400100"],
        vec!["--seed", "0x400100"],
        vec!["--seed-exception-rip"],
        vec!["--stateflow-input", "missing.json"],
        vec!["--explanation-only"],
        vec!["--assessment-only"],
        vec!["--memory-access", "0"],
        vec!["--path-count-bound", "2"],
        vec!["--frame-path-limits", "missing.json"],
    ] {
        let mut args = vec!["--frame-structure", "1:0"];
        args.extend(options);
        rejects(&args, "--frame-structure cannot combine");
    }
    for options in [
        vec!["--explain-fault-address", "0x400100"],
        vec!["--assess-zero-address", "0x400100"],
        vec!["--assess-zero-base-offset", "0x400100"],
        vec!["--assess-memory-provenance", "0x400100"],
        vec!["--list-frame-paths", "1:0", "--path-count-bound", "2"],
    ] {
        let mut args = vec!["--frame-structure", "1:0"];
        args.extend(options);
        rejects(&args, "choose one explanation or assessment question");
    }
}

#[test]
fn structure_question_rejects_even_explicit_rust_full_analysis_selection() {
    for options in [
        vec!["--analysis-backend", "rust"],
        vec!["--analysis-backend", "bap"],
        vec!["--bap-core-dir", "/nonexistent/core"],
        vec!["--bap-core-response-timeout-ms", "1000"],
        vec!["--bap-core-max-request-bytes", "1048576"],
    ] {
        let mut args = vec!["--frame-structure", "0:0"];
        args.extend(options);
        rejects(
            &args,
            "explicit analysis-backend or native-core options are incompatible",
        );
    }
}

#[test]
fn structure_question_validates_order_syntax_and_duplicate_options() {
    rejects(&["--frame-structure", "0:1"], "requires N >= M");
    rejects(&["--frame-structure", "1"], "requires N:M");
    rejects(&["--frame-structure", "-1:0"], "invalid unsigned");
    rejects(
        &["--frame-structure", "1:0", "--frame-structure", "1:0"],
        "unknown or duplicate option",
    );
    rejects(
        &[
            "--entry",
            "400100",
            "--frame-structure-limits",
            "missing.json",
        ],
        "--frame-structure-limits requires --frame-structure",
    );
}

#[test]
fn alignment_hypotheses_are_explicit_scoped_and_unique_before_dump_access() {
    rejects(
        &["--entry", "400100", "--assume-frame-aligned", "0:400204"],
        "requires --frame-structure",
    );
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--assume-frame-aligned",
            "1:400204",
        ],
        "outside selected frame range",
    );
    rejects(
        &["--frame-structure", "0:0", "--assume-frame-aligned", "0"],
        "requires FRAME:VA",
    );
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--assume-frame-aligned",
            "0:xyz",
        ],
        "invalid hexadecimal VA",
    );
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--assume-frame-aligned",
            "0:400204",
            "--assume-frame-aligned",
            "0:0x400204",
        ],
        "duplicate --assume-frame-aligned",
    );
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--assume-frame-aligned",
            "0:400204",
        ],
        "input I/O:",
    );
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper in remote WSL"]
fn conditional_alignment_cli_preserves_baseline_sources_and_replays_assumed_normal() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let run = |conditional: bool| {
        let mut command = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"));
        command
            .arg(root.join("tests/input/fixtures/guard-frame.dmp"))
            .arg("--decoder-reference")
            .arg(root.join("target/ariadne-llvm-mc"))
            .args(["--frame-structure", "0:0", "--format", "json"]);
        if conditional {
            command.args(["--assume-frame-aligned", "0:0x400204"]);
        }
        let output = command.output().unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        output.stdout
    };
    let baseline_bytes = run(false);
    let conditional_bytes = run(true);
    let baseline = ariadne::reports::frame_structure::decode(
        &baseline_bytes,
        &FrameStructureLimits::default(),
    )
    .unwrap();
    let conditional = ariadne::reports::frame_structure::decode(
        &conditional_bytes,
        &FrameStructureLimits::default(),
    )
    .unwrap();
    assert!(!baseline.is_conditional());
    assert!(conditional.is_conditional());
    assert_eq!(
        ariadne::reports::frame_structure::render_json(&baseline)
            .unwrap()
            .as_bytes(),
        baseline_bytes
    );
    assert_eq!(
        ariadne::reports::frame_structure::render_json(&conditional)
            .unwrap()
            .as_bytes(),
        conditional_bytes
    );
    let base = &baseline.recoveries()[0].1;
    let derived = &conditional.recoveries()[0].1;
    assert_eq!(base.context(), derived.context());
    assert_eq!(
        base.request(),
        &ariadne::bap::alignment_hypothesis::base_request(derived.alignment_hypotheses().unwrap())
            .unwrap()
    );
    assert_eq!(base.request().entry_points, derived.request().entry_points);
    assert!(!base.request().decodable.contains(&0x400204));
    assert!(derived.request().decodable.contains(&0x400204));
    assert!(
        derived
            .recovery()
            .state()
            .edges
            .iter()
            .any(|edge| edge.src == 0x400204 && edge.dst == 0x40020c)
    );
    let decision = derived
        .alignment_hypotheses()
        .unwrap()
        .decisions
        .iter()
        .find(|decision| decision.site == "0x0000000000400204")
        .unwrap();
    assert_eq!(
        decision.baseline_verdict,
        ariadne::bap::guard_admission::Verdict::Unknown
    );
    assert_eq!(
        decision.basis,
        ariadne::bap::alignment_hypothesis::Basis::Assumed
    );
    assert_eq!(
        conditional.frames()[0].conditional_on,
        conditional.hypothesis_ids()
    );
    assert!(
        !conditional.frames()[0]
            .gaps
            .iter()
            .any(|gap| gap.site == 0x400204
                && gap.kind == ariadne::investigation::FrameStructureGapKind::UnresolvedGuard)
    );
    for text in [
        ariadne::reports::frame_structure::render_text(&conditional).unwrap(),
        ariadne::reports::frame_structure::render_dot(&conditional).unwrap(),
    ] {
        assert!(text.contains("CONDITIONAL"));
        assert!(text.contains("baseline=Unknown"));
        assert!(text.contains("conditional normal under alignment hypothesis"));
    }
}

#[test]
fn structure_question_accepts_no_path_count_and_preserves_independent_assumptions() {
    for options in [
        vec!["--frame-structure", "0:0"],
        vec!["--frame-structure", "64:0"],
        vec!["--frame-structure", "0:0", "--resolve-indirect-targets"],
        vec!["--frame-structure", "0:0", "--assume-windows-call-entry"],
        vec![
            "--frame-structure",
            "0:0",
            "--max-artifact-bytes",
            "2147483649",
        ],
    ] {
        rejects(&options, "input I/O:");
    }
}

#[test]
fn structure_policy_is_strict_and_read_before_the_dump() {
    let mut unknown = serde_json::to_value(FrameStructureLimits::default()).unwrap();
    unknown["extra_policy"] = serde_json::json!(1);
    for bytes in [
        b"{\"max_frames\":1,\"max_frames\":2}".to_vec(),
        serde_json::to_vec(&unknown).unwrap(),
        vec![b' '; 65_537],
    ] {
        let file = TempFile::new(&bytes);
        let output = invoke(&[
            "--frame-structure",
            "0:0",
            "--frame-structure-limits",
            file.0.to_str().unwrap(),
        ]);
        assert!(!output.status.success());
        let error = String::from_utf8_lossy(&output.stderr);
        assert!(!error.contains("input I/O:"), "{error}");
        assert!(!error.contains("LLVM MC decoder I/O"), "{error}");
    }
}

#[test]
fn structural_host_policy_controls_frames_and_explicit_shared_overrides() {
    let policy = FrameStructureLimits {
        max_frames: 2,
        max_prepare_starts: 1,
        max_file_bytes: 1,
        ..FrameStructureLimits::default()
    };
    let file = TempFile::policy(&policy);
    let common = [
        "--frame-structure",
        "1:0",
        "--frame-structure-limits",
        file.0.to_str().unwrap(),
    ];
    // Implicit legacy defaults must not overwrite the selected host policy.
    rejects(&common, "input I/O:");
    for (option, value, message) in [
        (
            "--max-starts",
            "2",
            "--max-starts exceeds structural host policy",
        ),
        (
            "--max-artifact-bytes",
            "2",
            "--max-artifact-bytes exceeds structural host policy",
        ),
    ] {
        let mut args = common.to_vec();
        args.extend([option, value]);
        rejects(&args, message);
    }
    rejects(
        &[
            "--frame-structure",
            "2:0",
            "--frame-structure-limits",
            file.0.to_str().unwrap(),
        ],
        "exceeds host frame policy",
    );
}

#[test]
fn structural_guard_and_target_files_cannot_raise_the_host_policy() {
    let policy = FrameStructureLimits::default();
    let policy_file = TempFile::policy(&policy);
    let mut guard = policy.guard.clone();
    guard.max_sites += 1;
    let guard_file = TempFile::new(&serde_json::to_vec(&guard).unwrap());
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--frame-structure-limits",
            policy_file.0.to_str().unwrap(),
            "--guard-admission-limits",
            guard_file.0.to_str().unwrap(),
        ],
        "--guard-admission-limits max_sites exceeds structural host policy",
    );
    let mut target = policy.target.clone();
    target.max_steps += 1;
    let target_file = TempFile::new(&serde_json::to_vec(&target).unwrap());
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--frame-structure-limits",
            policy_file.0.to_str().unwrap(),
            "--resolve-indirect-targets",
            "--target-resolution-limits",
            target_file.0.to_str().unwrap(),
        ],
        "--target-resolution-limits max_steps exceeds structural host policy",
    );
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper in remote WSL"]
fn structural_capture_cli_roundtrip_keeps_recovery_separate_from_dataflow() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let output = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(root.join("tests/input/fixtures/guard-frame.dmp"))
        .arg("--decoder-reference")
        .arg(root.join("target/ariadne-llvm-mc"))
        .args(["--frame-structure", "0:0", "--format", "json"])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let decoded =
        ariadne::reports::frame_structure::decode(&output.stdout, &FrameStructureLimits::default())
            .unwrap();
    assert_eq!(decoded.question().from_frame, 0);
    assert_eq!(decoded.question().to_frame, 0);
    assert!(!decoded.frames().is_empty());
    for (_, frame) in decoded.recoveries() {
        assert_eq!(frame.recovery().state().phase(), ariadne::Phase::Recover);
        assert_eq!(
            frame.recovery().metrics().actions,
            frame.recovery().receipt().visits
        );
        assert_eq!(frame.recovery().metrics().transfer_evaluations, 0);
        assert_eq!(frame.recovery().metrics().incoming_evaluations, 0);
    }
    assert!(!String::from_utf8_lossy(&output.stdout).contains("path_count"));
}
