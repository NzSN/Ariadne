use std::path::{Path, PathBuf};
use std::process::Command;
fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures")
        .join(name)
}
#[test]
#[ignore = "requires pinned BAP and LLVM native helpers"]
fn default_bap_and_explicit_runtime_preserve_captured_producer_slice_without_fallback() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for (name, entry, producer, seed) in [
        (
            "stage_b_linux.dmp",
            "0x401000",
            "0x0000000000401000",
            "0x0000000000401006",
        ),
        (
            "stage_b_windows.dmp",
            "0x7ff700001000",
            "0x00007ff700001000",
            "0x00007ff700001006",
        ),
    ] {
        let run = |backend: bool| {
            let mut command = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"));
            command
                .arg(fixture(name))
                .arg("--decoder")
                .arg(root.join("target/ariadne-llvm-mc"))
                .args(["--entry", entry, "--seed-exception-rip", "--format", "json"]);
            if backend {
                command
                    .arg("--bap-helper")
                    .arg(root.join("target/ariadne-bap-lift"))
                    .arg("--bap-runtime")
                    .arg(root.join("tmp/bap-setup/stable"));
            }
            command.output().unwrap()
        };
        let baseline = run(false);
        let result = run(true);
        assert!(baseline.status.success());
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let reference: serde_json::Value = serde_json::from_slice(&baseline.stdout).unwrap();
        let report: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
        assert_eq!(reference["analysis"], report["analysis"]);
        assert_eq!(
            report["analysis"]["slice"],
            serde_json::json!([producer, seed])
        );
        assert!(
            reference["preparation"]["sites"]
                .as_array()
                .unwrap()
                .iter()
                .all(|s| s["semantic"]["backend"] == "bap-x86-legacy"
                    && s["semantic"]["fallback"].is_null())
        );
        let sites = report["preparation"]["sites"].as_array().unwrap();
        assert_eq!(sites[0]["quality"], "external_lift");
        assert_eq!(sites[0]["semantic"]["status"], "projected");
        assert_eq!(sites[3]["quality"], "opaque");
        assert_eq!(sites[3]["semantic"]["status"], "opaque-call-return");
        assert_eq!(
            reference["identity"]["artifact_sha256"],
            report["identity"]["artifact_sha256"]
        );
    }
}
#[test]
fn bap_options_and_infrastructure_failures_do_not_publish_complete_reports() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let output = std::env::temp_dir().join(format!("ariadne-bap-failure-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&output);
    let result = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(fixture("stage_b_linux.dmp"))
        .arg("--decoder")
        .arg(root.join("target/ariadne-llvm-mc"))
        .args([
            "--entry",
            "0x401000",
            "--bap-helper",
            "/missing/helper",
            "--bap-runtime",
        ])
        .arg(root.join("tmp/bap-setup/stable"))
        .arg("--output-dir")
        .arg(&output)
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(!output.exists());
    let result = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(fixture("stage_b_linux.dmp"))
        .args([
            "--entry",
            "0x401000",
            "--decoder",
            "/missing",
            "--semantics-backend",
            "unknown",
            "--format",
            "json",
        ])
        .output()
        .unwrap();
    assert!(!result.status.success());
}

mod common;
#[test]
#[ignore = "requires pinned BAP and LLVM native helpers"]
fn bap_materialization_preserves_conflicts_missing_seeds_and_call_only_discovery() {
    use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
    use ariadne::{analyze, effects::PreparationOptions};
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for linux in [false, true] {
        let mut dump = common::Dump::new(linux);
        dump.memory64(&[
            (0x1000, &[0xe8, 0xfb, 0x0f, 0, 0, 0xc3]),
            (0x2000, &[0xc3]),
            (0x3000, &[0x48, 0x89, 0xd8]),
            (0x3001, &[0xff]),
            (0x4000, &[0x0f]),
            (0x6000, &[0xff, 0xd0, 0xc3]),
        ]);
        let snapshot =
            FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
        let query = AnalysisQuery {
            entry_points: [0x1000, 0x3000, 0x4000, 0x6000].into(),
            slice_seeds: [0x2000].into(),
        };
        let mut backend = ariadne::bap::Backend::new(
            ariadne::bap::Config::new(
                root.join("target/ariadne-bap-lift"),
                root.join("tmp/bap-setup/stable"),
            ),
            &root.join("target/ariadne-llvm-mc"),
        )
        .unwrap();
        let prepared = snapshot
            .prepare_with_preparer(
                &query,
                &PreparationOptions::default(),
                PrepareLimits::default(),
                |s, c, o, t| {
                    backend
                        .prepare(s, c, o, t)
                        .map_err(|e| ariadne::input::PreparationError::Backend(e.to_string()))
                },
            )
            .unwrap();
        backend.finish().unwrap();
        assert!(!prepared.reads.contains_key(&0x2000));
        assert!(
            prepared
                .materialization
                .unattempted_references
                .contains(&0x2000)
        );
        assert_eq!(prepared.reads[&0x3000].bytes, [0x48]);
        assert!(prepared.prepared.instructions[&0x3000].semantic.is_some());
        assert!(!prepared.prepared.request.decodable.contains(&0x3000));
        assert!(!prepared.prepared.request.decodable.contains(&0x4000));
        let result = analyze(prepared.prepared.request).unwrap();
        assert!(result.missing_slice_seeds.contains(&0x2000));
        assert!(
            result
                .state
                .obligations
                .iter()
                .any(|o| o.site == 0x6000 && o.reason == ariadne::ObligationReason::CallTargets)
        );
    }
}
#[test]
#[ignore = "requires pinned BAP and LLVM native helpers"]
fn controlled_not_fixture_demonstrates_coverage_and_keeps_all_report_formats_bound() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let out = std::env::temp_dir().join(format!("ariadne-bap-precision-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&out);
    let result = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(fixture("bap_precision_linux.dmp"))
        .arg("--decoder")
        .arg(root.join("target/ariadne-llvm-mc"))
        .args([
            "--entry",
            "0x401000",
            "--seed-exception-rip",
            "--bap-helper",
        ])
        .arg(root.join("target/ariadne-bap-lift"))
        .arg("--bap-runtime")
        .arg(root.join("tmp/bap-setup/stable"))
        .arg("--output-dir")
        .arg(&out)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let data = std::fs::read_to_string(out.join("report.json")).unwrap();
    let value: serde_json::Value = serde_json::from_str(&data).unwrap();
    assert_eq!(value["analysis"]["decoded"].as_array().unwrap().len(), 4);
    assert_eq!(
        value["analysis"]["slice"],
        serde_json::json!([
            "0x0000000000401000",
            "0x0000000000401003",
            "0x0000000000401006"
        ])
    );
    assert_eq!(
        value["preparation"]["sites"][1]["semantic"]["status"],
        "projected"
    );
    for name in ["report.txt", "report.dot"] {
        let report = std::fs::read_to_string(out.join(name)).unwrap();
        assert!(report.contains("bap-x86-legacy"));
        assert!(report.contains("opaque-call-return"));
        assert!(report.contains(value["identity"]["artifact_sha256"].as_str().unwrap()));
    }
    std::fs::remove_dir_all(out).unwrap();
}

#[test]
fn removed_llvm_and_bap_selectors_cannot_select_a_semantic_backend() {
    for backend in ["llvm", "bap"] {
        let result = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
            .arg(fixture("stage_b_linux.dmp"))
            .args([
                "--decoder-reference",
                "/unused",
                "--entry",
                "0x401000",
                "--format",
                "json",
                "--semantics-backend",
                backend,
            ])
            .output()
            .unwrap();
        assert!(!result.status.success());
        assert!(result.stdout.is_empty());
        assert!(String::from_utf8_lossy(&result.stderr).contains("was removed"));
    }
}
