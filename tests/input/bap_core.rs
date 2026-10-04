use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::{AnalysisView, Analyzer, CompletedAnalysis, effects::PreparationOptions};
use std::path::PathBuf;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
fn config() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| root().join("target/bap-core-stage2")),
    )
}
#[test]
#[ignore = "requires pinned lifting, MC and native analysis helpers"]
fn captured_native_results_and_explanations_match_reference_and_reject_tampering() {
    for (name, entry) in [
        ("stage_b_linux.dmp", 0x401000),
        ("stage_b_windows.dmp", 0x7ff700001000),
    ] {
        let snapshot = FileSnapshot::open_minidump(
            root().join("tests/input/fixtures").join(name),
            OpenLimits::default(),
        )
        .unwrap();
        let p = snapshot
            .prepare_with_bap(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [entry + 6, entry + 0x100].into(),
                },
                &root().join("target/ariadne-llvm-mc"),
                &ariadne::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        let reference =
            CompletedAnalysis::from_analyzer(Analyzer::new(p.prepared.request.clone()).unwrap());
        let native = NativeAnalyzer::from_capture(&config(), "capture-test", &p)
            .unwrap()
            .complete()
            .unwrap();
        assert_eq!(reference.request(), native.request());
        assert_eq!(reference.state(), native.state());
        let explain = |a: &dyn AnalysisView| {
            let bound = ariadne::input::investigation::bind_investigation(&p, a).unwrap();
            ariadne::investigation::explain_fault_address(
                &bound,
                ariadne::investigation::FaultAddressQuestion {
                    site: entry + 6,
                    memory_access: 0,
                },
                ariadne::investigation::ExplainLimits::default(),
            )
            .unwrap()
        };
        assert_eq!(
            serde_json::to_value(explain(&reference)).unwrap(),
            serde_json::to_value(explain(&native)).unwrap()
        );
        let expected = reference.into_result();
        let actual = native.into_result();
        for format in [
            ariadne::input::report::ReportFormat::Json,
            ariadne::input::report::ReportFormat::Text,
            ariadne::input::report::ReportFormat::Dot,
        ] {
            assert_eq!(
                ariadne::input::report::render(&p, &expected, format, false).unwrap(),
                ariadne::input::report::render(&p, &actual, format, false).unwrap()
            );
        }
        let mut bad = p.clone();
        bad.prepared.instructions.get_mut(&entry).unwrap().bytes[0] ^= 1;
        assert!(NativeAnalyzer::from_capture(&config(), "wrong-bytes", &bad).is_err());
        let mut bad = p.clone();
        bad.materialization.query_identity = "0".repeat(64);
        assert!(NativeAnalyzer::from_capture(&config(), "wrong-query", &bad).is_err());
        let mut bad = p.clone();
        bad.reads.get_mut(&entry).unwrap().spans.clear();
        assert!(NativeAnalyzer::from_capture(&config(), "missing-contributor", &bad).is_err());
        let mut bad = p.clone();
        bad.prepared.request.file_backed.insert(entry);
        assert!(NativeAnalyzer::from_capture(&config(), "forbidden-file", &bad).is_err());
        let mut bad = p.clone();
        bad.prepared
            .instructions
            .get_mut(&entry)
            .unwrap()
            .semantic
            .as_mut()
            .unwrap()
            .helper_sha256 = "invalid".into();
        assert!(NativeAnalyzer::from_capture(&config(), "bad-helper", &bad).is_err());
    }
}

#[test]
#[ignore = "requires pinned native helpers"]
fn native_cli_assessment_and_explanation_preserve_reference_output() {
    for (fixture, option, only) in [
        (
            "i5a/zero-store.dmp",
            "--assess-zero-address",
            "--assessment-only",
        ),
        (
            "bap_precision_linux.dmp",
            "--explain-fault-address",
            "--explanation-only",
        ),
    ] {
        for format in ["json", "text", "dot"] {
            let mut outputs = Vec::new();
            for backend in ["rust", "bap"] {
                let output = std::process::Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
                    .arg(root().join("tests/input/fixtures").join(fixture))
                    .arg("--decoder-reference")
                    .arg(root().join("target/ariadne-llvm-mc"))
                    .args([
                        "--entry",
                        "401000",
                        option,
                        if only == "--assessment-only" {
                            "401000"
                        } else {
                            "401006"
                        },
                        "--memory-access",
                        "0",
                        only,
                        "--format",
                        format,
                        "--analysis-backend",
                        backend,
                    ])
                    .arg("--bap-core-dir")
                    .arg(config().helper.parent().unwrap())
                    .output()
                    .unwrap();
                assert!(
                    output.status.success(),
                    "{}",
                    String::from_utf8_lossy(&output.stderr)
                );
                if format == "json" {
                    let _: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
                }
                outputs.push(output.stdout);
            }
            assert_eq!(outputs[0], outputs[1], "{fixture}/{format}");
        }
    }
}
