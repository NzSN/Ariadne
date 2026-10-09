use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::{AnalysisView, Analyzer, CompletedAnalysis, effects::PreparationOptions};
use std::path::PathBuf;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/ariadne-llvm-mc"))
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
                &decoder(),
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

#[test]
#[ignore = "requires pinned helpers and v3 native capture admission"]
fn opaque_ordinary_keeps_old_and_unknown_origins_and_all_format_gaps() {
    for (file, entry) in [
        ("opaque-linux.dmp", 0x401000),
        ("opaque-windows.dmp", 0x7ff700001000),
    ] {
        let seed = entry + 5;
        let opaque = entry + 3;
        let snapshot = FileSnapshot::open_minidump(
            root().join("tests/input/fixtures/admission").join(file),
            OpenLimits::default(),
        )
        .unwrap();
        let prepared = snapshot
            .prepare_with_bap(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [seed].into(),
                },
                &decoder(),
                &ariadne::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        let summary = &prepared.prepared.request.instructions[&opaque];
        assert_eq!(summary.kind, ariadne::InstructionKind::Ordinary);
        assert_eq!(summary.fall, [seed].into());
        assert!(summary.must_defs.is_empty());
        assert_eq!(summary.uses, prepared.prepared.request.locations);
        assert_eq!(summary.may_defs, prepared.prepared.request.locations);
        let evidence = &prepared.prepared.instructions[&opaque];
        assert_eq!(
            evidence.semantic.as_ref().unwrap().status,
            "opaque-ordinary"
        );
        assert!(
            evidence
                .semantic
                .as_ref()
                .unwrap()
                .gaps
                .iter()
                .any(|g| g == "unsupported-data-effects")
        );
        assert!(
            !prepared.prepared.gaps.iter().any(|g| g.address == opaque
                && g.reason == ariadne::effects::GapReason::UnsupportedControl)
        );
        let reference = CompletedAnalysis::from_analyzer(
            Analyzer::new(prepared.prepared.request.clone()).unwrap(),
        );
        let native = NativeAnalyzer::from_capture(&config(), "opaque-capture", &prepared)
            .unwrap()
            .complete()
            .unwrap();
        assert_eq!(reference.state(), native.state());
        assert_eq!(native.state().decoded.len(), 4);
        assert_eq!(native.state().slice, [entry, opaque, seed].into());
        for index in 0..8 {
            let definitions: std::collections::BTreeSet<_> = native.state().reaching[&seed]
                .iter()
                .filter(|d| d.loc == format!("gpr:rcx:{index}"))
                .map(|d| (d.site, d.origin))
                .collect();
            assert_eq!(
                definitions,
                [
                    (entry, ariadne::DefinitionOrigin::Instruction),
                    (opaque, ariadne::DefinitionOrigin::Instruction)
                ]
                .into()
            );
        }
        let bound = ariadne::input::investigation::bind_investigation(&prepared, &native).unwrap();
        let explanation = ariadne::investigation::explain_fault_address(
            &bound,
            ariadne::investigation::FaultAddressQuestion {
                site: seed,
                memory_access: 0,
            },
            ariadne::investigation::ExplainLimits::default(),
        )
        .unwrap();
        assert_eq!(
            explanation.status,
            ariadne::investigation::AnswerStatus::Partial
        );
        let mut bad = prepared.clone();
        bad.prepared
            .instructions
            .get_mut(&opaque)
            .unwrap()
            .semantic
            .as_mut()
            .unwrap()
            .gaps
            .retain(|g| g != "unsupported-data-effects");
        assert!(ariadne::input::investigation::bind_investigation(&bad, &native).is_err());
        assert!(NativeAnalyzer::from_capture(&config(), "hidden-gap", &bad).is_err());
        let mut bad_kill = prepared.clone();
        bad_kill
            .prepared
            .request
            .instructions
            .get_mut(&opaque)
            .unwrap()
            .must_defs
            .insert("gpr:rcx:0".into());
        assert!(NativeAnalyzer::from_capture(&config(), "wrong-kill", &bad_kill).is_err());
        let mut bad_profile = prepared.clone();
        bad_profile
            .prepared
            .instructions
            .get_mut(&opaque)
            .unwrap()
            .semantic
            .as_mut()
            .unwrap()
            .projection = "bap-bit-provenance-v2".into();
        assert!(NativeAnalyzer::from_capture(&config(), "wrong-profile", &bad_profile).is_err());
        let reference = reference.into_result();
        let native = native.into_result();
        for format in [
            ariadne::input::report::ReportFormat::Json,
            ariadne::input::report::ReportFormat::Text,
            ariadne::input::report::ReportFormat::Dot,
        ] {
            let rendered =
                ariadne::input::report::render(&prepared, &native, format, false).unwrap();
            assert!(
                rendered.contains("opaque-ordinary")
                    && rendered.contains("unsupported-data-effects")
            );
            assert_eq!(
                rendered,
                ariadne::input::report::render(&prepared, &reference, format, false).unwrap()
            );
            assert!(ariadne::input::report::render(&bad, &native, format, false).is_err());
        }
    }
}

#[test]
#[ignore = "requires pinned helpers and v3 native capture admission"]
fn observed_chain_recovers_from_one_root_and_empty_lifts_still_stop() {
    for target in ["windows", "linux"] {
        let entry = if target == "windows" {
            0x7ff700001000
        } else {
            0x401000
        };
        for (label, count, seed_offset) in [("observed", 5, 11), ("empty", 1, 4)] {
            let snapshot = FileSnapshot::open_minidump(
                root()
                    .join("tests/input/fixtures/admission")
                    .join(format!("{label}-{target}.dmp")),
                OpenLimits::default(),
            )
            .unwrap();
            let prepared = snapshot
                .prepare(
                    &AnalysisQuery {
                        entry_points: [entry].into(),
                        slice_seeds: [entry + seed_offset].into(),
                    },
                    &decoder(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                )
                .unwrap();
            let native = NativeAnalyzer::from_capture(&config(), "observed-chain", &prepared)
                .unwrap()
                .complete()
                .unwrap();
            assert_eq!(native.state().decoded.len(), count);
            assert_eq!(
                native.state().decoded.contains(&(entry + seed_offset)),
                label == "observed"
            );
            if label == "empty" {
                assert!(!prepared.prepared.request.decodable.contains(&(entry + 3)));
            }
        }
    }
}

#[test]
#[ignore = "requires current native capture helper; bypasses Rust prevalidation"]
fn native_rejects_opaque_contract_tampering_directly() {
    use serde_json::json;
    let entry = 0x401000;
    let opaque = entry + 3;
    let snapshot = FileSnapshot::open_minidump(
        root().join("tests/input/fixtures/admission/opaque-linux.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let p = snapshot
        .prepare(
            &AnalysisQuery {
                entry_points: [entry].into(),
                slice_seeds: [entry + 5].into(),
            },
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    let request = &p.prepared.request;
    let sites:Vec<_>=p.prepared.instructions.iter().map(|(&a,e)| {
        let s=e.semantic.as_ref().unwrap();let read=&p.reads[&a];
        json!({"address":format!("0x{a:016x}"),"bytes":e.bytes.iter().map(|b|format!("{b:02x}")).collect::<String>(),"captured":true,
            "quality":if e.quality==ariadne::effects::EffectQuality::ExternalLifted{"external_lift"}else{"opaque"},
            "status":s.status,"helper_sha256":s.helper_sha256,"runtime_sha256":s.runtime_sha256,"ast_sha256":s.ast_sha256,"projection":s.projection,
            "spans":read.spans.iter().map(|s|json!({"address":format!("0x{:016x}",s.address),"length":s.length,
                "contributors":s.contributors.iter().map(|c|json!({"stream":c.stream,"entry":c.entry,"file_offset":c.file_offset.to_string()})).collect::<Vec<_>>() })).collect::<Vec<_>>()})
    }).collect();
    let good = json!({"normalized":ariadne::bap::core_adapter::encode_request(request).unwrap(),"capture":{
        "snapshot":request.snapshot_id,"artifact_sha256":p.snapshot.artifact_sha256,"query_id":p.materialization.query_identity,
        "semantic_profile":"v3-independent-native-negative-control","sites":sites}});
    let run = |input: &serde_json::Value| {
        ariadne::bap::core_session::CoreSession::start_profile(
            &config(),
            "direct-capture-admission",
            &request.snapshot_id,
            ariadne::bap::core_protocol::CAPTURED_PROFILE,
            input,
        )
    };
    let (_session, response) = run(&good).unwrap();
    assert!(response.error.is_none());
    let index = good["normalized"]["instructions"]
        .as_array()
        .unwrap()
        .iter()
        .position(|r| r["address"] == format!("0x{opaque:016x}"))
        .unwrap();
    let site = good["capture"]["sites"]
        .as_array()
        .unwrap()
        .iter()
        .position(|r| r["address"] == format!("0x{opaque:016x}"))
        .unwrap();
    for mutation in ["kill", "uses", "may", "profile", "quality", "ast"] {
        let mut bad = good.clone();
        match mutation {
            "kill" => bad["normalized"]["instructions"][index]["must_defs"] = json!(["gpr:rcx:0"]),
            "uses" => bad["normalized"]["instructions"][index]["uses"] = json!([]),
            "may" => bad["normalized"]["instructions"][index]["may_defs"] = json!([]),
            "profile" => {
                bad["capture"]["sites"][site]["projection"] = json!("bap-bit-provenance-v2")
            }
            "quality" => bad["capture"]["sites"][site]["quality"] = json!("external_lift"),
            "ast" => bad["capture"]["sites"][site]["ast_sha256"] = serde_json::Value::Null,
            _ => unreachable!(),
        }
        let rejected = match run(&bad) {
            Err(_) => true,
            Ok((_session, response)) => response.error.is_some(),
        };
        assert!(rejected, "native admitted opaque {mutation} mutation");
    }
}
