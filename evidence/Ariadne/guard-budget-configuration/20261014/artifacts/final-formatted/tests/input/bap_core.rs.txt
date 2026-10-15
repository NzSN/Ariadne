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
fn vector_capture_has_native_reference_parity_and_keeps_prior_vector_origins() {
    for (fixture, entry) in [
        ("vector-linux.dmp", 0x401000),
        ("vector-windows.dmp", 0x7ff700001000),
    ] {
        let snapshot = FileSnapshot::open_minidump(
            root().join("tests/input/fixtures").join(fixture),
            OpenLimits::default(),
        )
        .unwrap();
        let p = snapshot
            .prepare_with_bap(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [entry + 7].into(),
                },
                &decoder(),
                &ariadne::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        for va in [entry, entry + 3, entry + 7] {
            let site = &p.prepared.instructions[&va];
            assert_eq!(
                site.semantic.as_ref().unwrap().projection,
                "bap-bit-provenance-v6"
            );
            assert_eq!(site.semantic.as_ref().unwrap().status, "projected");
        }
        assert!(
            !p.prepared.request.instructions[&entry]
                .must_defs
                .contains("state:other")
        );
        let reference =
            CompletedAnalysis::from_analyzer(Analyzer::new(p.prepared.request.clone()).unwrap());
        let native = NativeAnalyzer::from_capture(&config(), "vector-capture", &p)
            .unwrap()
            .complete()
            .unwrap();
        assert_eq!(reference.state(), native.state());
        let origins = &native.state().reaching[&(entry + 7)];
        assert!(
            origins
                .iter()
                .any(|d| d.loc == "state:other" && d.site == entry)
        );
        assert!(
            origins
                .iter()
                .any(|d| d.loc == "state:other" && d.origin == ariadne::DefinitionOrigin::Entry)
        );
        ariadne::input::investigation::bind_investigation(&p, &native).unwrap();
    }
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

#[test]
#[ignore = "requires pinned BAP, LLVM MC and rebuilt guarded native helper in remote WSL"]
fn guarded_frame_capture_has_native_parity_and_rejects_direct_proof_tampering() {
    use ariadne::bap::{core_protocol::GUARDED_PROFILE, guard_admission};
    use ariadne::input::FramePreparation;
    use ariadne::investigation::FrameRecoveryLimits;
    use serde_json::{Value, json};

    let snapshot = FileSnapshot::open_minidump(
        root().join("tests/input/fixtures/guard-frame.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let bap = ariadne::bap::Config::from_env();
    let options = PreparationOptions::default();
    let reference_decoder = decoder();
    let setup = FramePreparation {
        decoder: &reference_decoder,
        config: &bap,
        options: &options,
        limits: PrepareLimits::default(),
    };
    let prepared = snapshot
        .prepare_frame_with_bap_assuming_windows_call_entry(
            &chain,
            0,
            0x400200,
            &setup,
            guard_admission::Limits::default(),
        )
        .unwrap();
    let proof = prepared.guard_admission().unwrap();
    assert_eq!(proof.guards.len(), 1);
    assert_eq!(proof.guards[0].verdict, guard_admission::Verdict::Aligned);
    assert_eq!(proof.input.premises[0].policy, guard_admission::ABI_POLICY);
    let rust =
        CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone()).unwrap());
    let native = NativeAnalyzer::from_capture(&config(), "guard-frame-parity", &prepared)
        .unwrap()
        .complete()
        .unwrap();
    assert_eq!(rust.state(), native.state());
    let bound = ariadne::input::investigation::bind_investigation(&prepared, &native).unwrap();
    let explanation = ariadne::investigation::explain_fault_address(
        &bound,
        ariadne::investigation::FaultAddressQuestion {
            site: 0x400204,
            memory_access: 0,
        },
        ariadne::investigation::ExplainLimits::default(),
    )
    .unwrap();
    assert_eq!(explanation.schema, "ariadne.fault-address-explanation/v2");
    assert!(
        explanation
            .assumptions
            .iter()
            .any(|p| p.contains(guard_admission::ABI_POLICY))
    );
    let mut stripped = explanation.clone();
    stripped.guard_admission = None;
    stripped.schema = "ariadne.fault-address-explanation/v1".into();
    assert!(
        stripped.validate().is_err(),
        "guarded explanation lost its proof"
    );
    let rendered = ariadne::input::report::render_bound(
        &prepared,
        &rust,
        ariadne::input::report::ReportFormat::Json,
        false,
    )
    .unwrap();
    let report: Value = serde_json::from_str(&rendered).unwrap();
    assert_eq!(report["schema"], "ariadne-minidump-report-v3");
    assert_eq!(
        report["guard_admission"]["input"]["premises"][0]["policy"],
        guard_admission::ABI_POLICY
    );
    let mut different_request = prepared.prepared.request.clone();
    different_request.slice_seeds.insert(0x400204);
    let different = CompletedAnalysis::from_analyzer(Analyzer::new(different_request).unwrap());
    assert!(
        ariadne::input::report::render_bound(
            &prepared,
            &different,
            ariadne::input::report::ReportFormat::Json,
            false,
        )
        .is_err(),
        "same-snapshot different request carried a guard proof"
    );
    assert!(
        ariadne::input::report::render(
            &prepared,
            &rust.into_result(),
            ariadne::input::report::ReportFormat::Json,
            false,
        )
        .is_err(),
        "raw AnalysisResult carried a guard proof"
    );

    // Construct the wire input independently of NativeAnalyzer's host-side
    // prevalidation. Every mutation below must be refused by the native profile.
    let sites: Vec<_> = prepared
        .prepared
        .instructions
        .iter()
        .map(|(&a, e)| {
            let s = e.semantic.as_ref();
            let read = prepared.reads.get(&a);
            json!({
                "address":format!("0x{a:016x}"),
                "bytes":e.bytes.iter().map(|b|format!("{b:02x}")).collect::<String>(),
                "captured":e.source==ariadne::ByteSource::Captured,
                "quality":match e.quality {
                    ariadne::effects::EffectQuality::ExternalLifted=>"external_lift",
                    ariadne::effects::EffectQuality::Opaque=>"opaque",
                    ariadne::effects::EffectQuality::Reviewed=>"reviewed",
                    ariadne::effects::EffectQuality::Unavailable=>"unavailable",
                },
                "status":s.map(|v|v.status.as_str()),
                "helper_sha256":s.map(|v|v.helper_sha256.as_str()),
                "runtime_sha256":s.map(|v|v.runtime_sha256.as_str()),
                "ast_sha256":s.and_then(|v|v.ast_sha256.as_deref()),
                "projection":s.map(|v|v.projection.as_str()),
                "spans":read.map(|r|r.spans.iter().map(|p|json!({
                    "address":format!("0x{:016x}",p.address),"length":p.length,
                    "contributors":p.contributors.iter().map(|c|json!({
                        "stream":c.stream,"entry":c.entry,
                        "file_offset":c.file_offset.to_string()
                    })).collect::<Vec<_>>()
                })).collect::<Vec<_>>()).unwrap_or_default()
            })
        })
        .collect();
    let good = json!({
        "normalized":ariadne::bap::core_adapter::encode_request(&prepared.prepared.request).unwrap(),
        "capture":{
            "snapshot":prepared.snapshot.snapshot_id,
            "artifact_sha256":prepared.snapshot.artifact_sha256,
            "query_id":prepared.materialization.query_identity,
            "semantic_profile":format!("direct:{}:{}", guard_admission::PROFILE,
                ariadne::reports::sha256(&serde_json::to_vec(proof).unwrap())),
            "sites":sites,
        },
        "guard_admission":proof,
    });
    let accepted = ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-good",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &good,
    )
    .unwrap();
    assert!(accepted.1.error.is_none());
    for mutation in [
        "candidate-ast",
        "transfer",
        "fact",
        "premise",
        "normal-ast",
        "receipt",
        "request",
        "capture-effect",
        "opaque-source",
    ] {
        let mut bad = good.clone();
        match mutation {
            "candidate-ast" => bad["guard_admission"]["input"]["sites"][1]["ast"] = json!("[]"),
            "transfer" => bad["guard_admission"]["transfers"][0]["relation"][0] = json!(65535),
            "fact" => bad["guard_admission"]["facts"][1]["residues"] = json!(65535),
            "premise" => bad["guard_admission"]["input"]["premises"][0]["rsp_residues"] = json!(1),
            "normal-ast" => bad["guard_admission"]["guards"][0]["normal_ast"] = json!("[]"),
            "receipt" => {
                bad["guard_admission"]["guards"][0]["receipt_sha256"] = json!("0".repeat(64))
            }
            "request" => bad["normalized"]["instructions"][0]["uses"] = json!([]),
            "capture-effect" => bad["capture"]["sites"][1]["quality"] = json!("opaque"),
            "opaque-source" => {
                bad["capture"]["sites"][0]["status"] = json!("opaque-unsupported");
                bad["capture"]["sites"][0]["quality"] = json!("opaque");
            }
            _ => unreachable!(),
        }
        bad["capture"]["semantic_profile"] = json!(format!(
            "direct:{}:{}",
            guard_admission::PROFILE,
            ariadne::reports::sha256(&serde_json::to_vec(&bad["guard_admission"]).unwrap())
        ));
        let rejected = match ariadne::bap::core_session::CoreSession::start_profile(
            &config(),
            &format!("guard-direct-{mutation}"),
            &prepared.snapshot.snapshot_id,
            GUARDED_PROFILE,
            &bad,
        ) {
            Err(_) => true,
            Ok((_session, response)) => response.error.is_some(),
        };
        assert!(rejected, "native admitted guard {mutation} tampering");
    }

    // Rehash every dependent receipt after changing only the final graph.
    // A checker that accepts any one fall edge would admit this loop even
    // though its candidate proof covered the next instruction instead.
    let mut wrong_edge = good.clone();
    let guard_address = "0x0000000000400204";
    let guard_index = wrong_edge["normalized"]["instructions"]
        .as_array()
        .unwrap()
        .iter()
        .position(|row| row["address"] == guard_address)
        .unwrap();
    wrong_edge["normalized"]["instructions"][guard_index]["fall"] = json!(["0x0000000000400200"]);
    let mut forged: guard_admission::Report =
        serde_json::from_value(wrong_edge["guard_admission"].clone()).unwrap();
    forged.final_request_sha256 = Some(ariadne::reports::sha256(
        &serde_json::to_vec(&wrong_edge["normalized"]).unwrap(),
    ));
    let mut receipt_row = forged.guards[0].clone();
    receipt_row.receipt_sha256.clear();
    let forged_receipt = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-guard-receipt/v1",
            &forged.checker_sha256,
            &forged.intent_id,
            &forged.candidate_graph_sha256,
            forged.input.candidate_epoch,
            &forged.input.model_version,
            &forged.input.model_sha256,
            &forged.input.premises,
            &forged.input.limits,
            &forged.transfers,
            &forged.facts,
            &forged.stop,
            &forged.final_request_sha256,
            receipt_row,
        ))
        .unwrap(),
    );
    forged.guards[0].receipt_sha256 = forged_receipt;
    let forged_analysis_id = guard_admission::analysis_id(&forged).unwrap();
    wrong_edge["guard_admission"] = serde_json::to_value(&forged).unwrap();
    wrong_edge["capture"]["query_id"] = json!(forged_analysis_id);
    wrong_edge["capture"]["semantic_profile"] = json!(format!(
        "direct:{}:{}",
        guard_admission::PROFILE,
        ariadne::reports::sha256(&serde_json::to_vec(&forged).unwrap())
    ));
    let rejected = match ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-rehashed-wrong-edge",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &wrong_edge,
    ) {
        Err(_) => true,
        Ok((_session, response)) => response.error.is_some(),
    };
    assert!(rejected, "native admitted rehashed wrong guard fall edge");

    // A direct client can rehash a false source claim. The first instruction
    // is represented as RSP:=0 followed by unsupported RAX data, while its
    // captured bytes remain SUB RSP,8. Treating the latter statement as
    // irrelevant would retain a precise RSP constant that typed BAP admission
    // explicitly refuses. Native must require TOP for this untyped BIL.
    let mut untyped = good.clone();
    let mut forged: guard_admission::Report =
        serde_json::from_value(untyped["guard_admission"].clone()).unwrap();
    forged.input.sites[0].ast = json!([
        {"kind":"move","var":{"name":"RSP","index":0,"virtual":false,
            "width":64,"type":"imm"},
            "value":{"kind":"int","value":"0x0:64u"}},
        {"kind":"move","var":{"name":"RAX","index":0,"virtual":false,
            "width":64,"type":"imm"},"value":{"kind":"unsupported"}}
    ])
    .to_string();
    forged.candidate_graph_sha256 = guard_admission::graph_digest(&forged.input).unwrap();
    forged.transfers[0].ast_sha256 = ariadne::reports::sha256(forged.input.sites[0].ast.as_bytes());
    forged.transfers[0].relation = vec![1; 16];
    forged.transfers[0].relation_sha256 = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            forged.transfers[0].rule.as_str(),
            &forged.transfers[0].relation,
        ))
        .unwrap(),
    );
    let mut receipt_row = forged.guards[0].clone();
    receipt_row.receipt_sha256.clear();
    let untyped_receipt = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-guard-receipt/v1",
            &forged.checker_sha256,
            &forged.intent_id,
            &forged.candidate_graph_sha256,
            forged.input.candidate_epoch,
            &forged.input.model_version,
            &forged.input.model_sha256,
            &forged.input.premises,
            &forged.input.limits,
            &forged.transfers,
            &forged.facts,
            &forged.stop,
            &forged.final_request_sha256,
            receipt_row,
        ))
        .unwrap(),
    );
    forged.guards[0].receipt_sha256 = untyped_receipt;
    let forged_analysis_id = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-guard-analysis/v1",
            &forged.intent_id,
            forged.final_request_sha256.as_ref().unwrap(),
            vec![forged.guards[0].receipt_sha256.as_str()],
        ))
        .unwrap(),
    );
    untyped["capture"]["sites"][0]["ast_sha256"] = json!(forged.transfers[0].ast_sha256);
    untyped["guard_admission"] = serde_json::to_value(&forged).unwrap();
    untyped["capture"]["query_id"] = json!(forged_analysis_id);
    untyped["capture"]["semantic_profile"] = json!(format!(
        "direct:{}:{}",
        guard_admission::PROFILE,
        ariadne::reports::sha256(&serde_json::to_vec(&forged).unwrap())
    ));
    let rejected = match ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-rehashed-untyped-transfer",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &untyped,
    ) {
        Err(_) => true,
        Ok((_session, response)) => response.error.is_some(),
    };
    assert!(
        rejected,
        "native admitted rehashed unsupported RAX expression"
    );
    // Unsupported ordinary data retains structural continuation with TOP RSP.
    // The downstream MOVAPS guard must remain stopped and explicit.
    let mut opaque_input = proof.input.clone();
    opaque_input.sites[0].ast = json!([{
        "kind":"move",
        "var":{"name":"RAX","index":0,"virtual":false,"width":64,"type":"imm"},
        "value":{"kind":"unsupported"}
    }])
    .to_string();
    opaque_input.sites[0].opaque = true;
    let mut opaque_report = guard_admission::certify_guards(&opaque_input).unwrap();
    assert_eq!(
        opaque_report.guards[0].verdict,
        guard_admission::Verdict::Unknown
    );
    assert_eq!(opaque_report.transfers[0].relation, vec![u16::MAX; 16]);
    let mut opaque_request = prepared.prepared.request.clone();
    let all_locations = opaque_request.locations.clone();
    let entry = opaque_request.instructions.get_mut(&0x400200).unwrap();
    entry.uses = all_locations.clone();
    entry.may_defs = all_locations.clone();
    entry.must_defs.clear();
    let stopped = opaque_request.instructions.get_mut(&0x400204).unwrap();
    stopped.kind = ariadne::InstructionKind::Stop;
    stopped.fall.clear();
    stopped.targets.clear();
    stopped.complete = false;
    stopped.uses = all_locations.clone();
    stopped.may_defs = all_locations;
    stopped.must_defs.clear();
    opaque_request.decodable.remove(&0x400204);
    opaque_request.validate().unwrap();
    let normalized = ariadne::bap::core_adapter::encode_request(&opaque_request).unwrap();
    guard_admission::bind_final_request(
        &opaque_input,
        &mut opaque_report,
        &ariadne::reports::sha256(&serde_json::to_vec(&normalized).unwrap()),
    )
    .unwrap();
    let mut opaque_wire = good.clone();
    opaque_wire["normalized"] = normalized;
    opaque_wire["guard_admission"] = serde_json::to_value(&opaque_report).unwrap();
    opaque_wire["capture"]["sites"][0]["ast_sha256"] = json!(ariadne::reports::sha256(
        opaque_input.sites[0].ast.as_bytes()
    ));
    opaque_wire["capture"]["sites"][0]["status"] = json!("opaque-ordinary");
    opaque_wire["capture"]["sites"][0]["quality"] = json!("opaque");
    opaque_wire["capture"]["sites"][1]["status"] = json!("guard-not-admitted");
    opaque_wire["capture"]["sites"][1]["quality"] = json!("opaque");
    opaque_wire["capture"]["query_id"] =
        json!(guard_admission::analysis_id(&opaque_report).unwrap());
    opaque_wire["capture"]["semantic_profile"] = json!(format!(
        "direct:{}:{}",
        guard_admission::PROFILE,
        ariadne::reports::sha256(&serde_json::to_vec(&opaque_report).unwrap())
    ));
    let (mut opaque_native, initial) = ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-opaque-ordinary",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &opaque_wire,
    )
    .unwrap();
    assert!(
        initial.error.is_none(),
        "legitimate opaque ordinary rejected"
    );
    let native_done = opaque_native.finish_paged().unwrap();
    assert!(native_done.error.is_none());
    let native_state =
        ariadne::bap::core_adapter::decode_state(&opaque_request, &native_done.observation)
            .unwrap();
    let reference =
        CompletedAnalysis::from_analyzer(Analyzer::new(opaque_request.clone()).unwrap());
    assert_eq!(reference.state(), &native_state);

    // A fully rehashed stopped guard cannot be reported as decoded/complete.
    let mut false_stop = opaque_wire.clone();
    let decodable = false_stop["normalized"]["decodable"]
        .as_array_mut()
        .unwrap();
    decodable.push(json!(guard_address));
    decodable.sort_by(|a, b| a.as_str().cmp(&b.as_str()));
    false_stop["normalized"]["instructions"][guard_index]["targets_complete"] = json!(true);
    let mut false_report = guard_admission::certify_guards(&opaque_input).unwrap();
    guard_admission::bind_final_request(
        &opaque_input,
        &mut false_report,
        &ariadne::reports::sha256(&serde_json::to_vec(&false_stop["normalized"]).unwrap()),
    )
    .unwrap();
    false_stop["guard_admission"] = serde_json::to_value(&false_report).unwrap();
    false_stop["capture"]["query_id"] = json!(guard_admission::analysis_id(&false_report).unwrap());
    false_stop["capture"]["semantic_profile"] = json!(format!(
        "direct:{}:{}",
        guard_admission::PROFILE,
        ariadne::reports::sha256(&serde_json::to_vec(&false_report).unwrap())
    ));
    let rejected = match ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-rehashed-false-stop",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &false_stop,
    ) {
        Err(_) => true,
        Ok((_session, response)) => response.error.is_some(),
    };
    assert!(
        rejected,
        "native admitted rehashed decoded/complete guard stop"
    );
}

#[test]
#[ignore = "requires pinned BAP, LLVM MC and rebuilt guarded native helper in remote WSL"]
fn captured_xorps_shift_width_has_guarded_native_parity_and_rejects_rehashed_nonshift() {
    use ariadne::bap::{core_protocol::GUARDED_PROFILE, guard_admission};
    use ariadne::input::FramePreparation;
    use ariadne::investigation::FrameRecoveryLimits;
    use serde_json::{Value, json};

    let snapshot = FileSnapshot::open_minidump(
        root().join("tests/input/fixtures/shift-frame.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let bap = ariadne::bap::Config::from_env();
    let options = PreparationOptions::default();
    let reference_decoder = decoder();
    let prepared = snapshot
        .prepare_frame_with_bap_assuming_windows_call_entry(
            &chain,
            0,
            0x400200,
            &FramePreparation {
                decoder: &reference_decoder,
                config: &bap,
                options: &options,
                limits: PrepareLimits::default(),
            },
            guard_admission::Limits::default(),
        )
        .unwrap();
    let proof = prepared.guard_admission().unwrap();
    assert_eq!(proof.guards[0].verdict, guard_admission::Verdict::Aligned);
    let shift = &prepared.prepared.instructions[&0x40020c];
    let semantic = shift.semantic.as_ref().unwrap();
    assert_eq!(shift.bytes.as_slice(), &[0x0f, 0x57, 0xc0]);
    assert_eq!(semantic.projection, "bap-bit-provenance-v7");
    assert_eq!(semantic.status, "projected", "{:?}", semantic.gaps);
    assert!(prepared.prepared.request.decodable.contains(&0x40020c));
    assert!(
        prepared.prepared.request.instructions[&0x40020c]
            .may_defs
            .contains("state:other")
    );
    let rust =
        CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone()).unwrap());
    let native = NativeAnalyzer::from_capture(&config(), "guarded-shift-parity", &prepared)
        .unwrap()
        .complete()
        .unwrap();
    assert_eq!(rust.state(), native.state());

    // Direct native admission must not accept the same two widths when the
    // lifted operator is changed from shift (11) to ordinary ADD (18), even
    // after every dependent candidate/receipt/analysis digest is refreshed.
    let sites: Vec<_> = prepared
        .prepared
        .instructions
        .iter()
        .map(|(&a, e)| {
            let s = e.semantic.as_ref();
            let read = prepared.reads.get(&a);
            json!({
                "address":format!("0x{a:016x}"),
                "bytes":e.bytes.iter().map(|b|format!("{b:02x}")).collect::<String>(),
                "captured":e.source==ariadne::ByteSource::Captured,
                "quality":match e.quality {
                    ariadne::effects::EffectQuality::ExternalLifted=>"external_lift",
                    ariadne::effects::EffectQuality::Opaque=>"opaque",
                    ariadne::effects::EffectQuality::Reviewed=>"reviewed",
                    ariadne::effects::EffectQuality::Unavailable=>"unavailable",
                },
                "status":s.map(|v|v.status.as_str()),
                "helper_sha256":s.map(|v|v.helper_sha256.as_str()),
                "runtime_sha256":s.map(|v|v.runtime_sha256.as_str()),
                "ast_sha256":s.and_then(|v|v.ast_sha256.as_deref()),
                "projection":s.map(|v|v.projection.as_str()),
                "spans":read.map(|r|r.spans.iter().map(|p|json!({
                    "address":format!("0x{:016x}",p.address),"length":p.length,
                    "contributors":p.contributors.iter().map(|c|json!({
                        "stream":c.stream,"entry":c.entry,
                        "file_offset":c.file_offset.to_string()
                    })).collect::<Vec<_>>()
                })).collect::<Vec<_>>()).unwrap_or_default()
            })
        })
        .collect();
    let mut wire = json!({
        "normalized":ariadne::bap::core_adapter::encode_request(&prepared.prepared.request).unwrap(),
        "capture":{
            "snapshot":prepared.snapshot.snapshot_id,
            "artifact_sha256":prepared.snapshot.artifact_sha256,
            "query_id":prepared.materialization.query_identity,
            "semantic_profile":"guarded-shift-direct-validation",
            "sites":sites,
        },
        "guard_admission":proof,
    });
    let mut forged = proof.clone();
    let shift_index = forged
        .input
        .sites
        .iter()
        .position(|s| s.site == "0x000000000040020c")
        .unwrap();
    let mut ast: Value = serde_json::from_str(&forged.input.sites[shift_index].ast).unwrap();
    assert_eq!(
        ast[3]["value"]["rhs"]["op"], 11,
        "pinned captured XORPS lift changed"
    );
    ast[3]["value"]["rhs"]["op"] = json!(18);
    forged.input.sites[shift_index].ast = serde_json::to_string(&ast).unwrap();
    forged.candidate_graph_sha256 = guard_admission::graph_digest(&forged.input).unwrap();
    forged.transfers[shift_index].ast_sha256 =
        ariadne::reports::sha256(forged.input.sites[shift_index].ast.as_bytes());
    // The old relation is already RSP identity: this remains a plausible
    // forged transfer unless the native typed checker inspects the full AST.
    let mut receipt_row = forged.guards[0].clone();
    receipt_row.receipt_sha256.clear();
    let receipt_sha = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-guard-receipt/v1",
            &forged.checker_sha256,
            &forged.intent_id,
            &forged.candidate_graph_sha256,
            forged.input.candidate_epoch,
            &forged.input.model_version,
            &forged.input.model_sha256,
            &forged.input.premises,
            &forged.input.limits,
            &forged.transfers,
            &forged.facts,
            &forged.stop,
            &forged.final_request_sha256,
            receipt_row,
        ))
        .unwrap(),
    );
    forged.guards[0].receipt_sha256 = receipt_sha;
    let forged_analysis_id = ariadne::reports::sha256(
        &serde_json::to_vec(&(
            "ariadne-guard-analysis/v1",
            &forged.intent_id,
            forged.final_request_sha256.as_ref().unwrap(),
            vec![forged.guards[0].receipt_sha256.as_str()],
        ))
        .unwrap(),
    );
    let captured_shift_index = wire["capture"]["sites"]
        .as_array()
        .unwrap()
        .iter()
        .position(|s| s["address"] == "0x000000000040020c")
        .unwrap();
    wire["capture"]["sites"][captured_shift_index]["ast_sha256"] =
        json!(forged.transfers[shift_index].ast_sha256);
    wire["capture"]["query_id"] = json!(forged_analysis_id);
    wire["guard_admission"] = serde_json::to_value(&forged).unwrap();
    wire["capture"]["semantic_profile"] = json!(format!(
        "direct:{}:{}",
        guard_admission::PROFILE,
        ariadne::reports::sha256(&serde_json::to_vec(&forged).unwrap()),
    ));
    let rejected = match ariadne::bap::core_session::CoreSession::start_profile(
        &config(),
        "guard-direct-rehashed-nonshift-width",
        &prepared.snapshot.snapshot_id,
        GUARDED_PROFILE,
        &wire,
    ) {
        Err(_) => true,
        Ok((_session, response)) => response.error.is_some(),
    };
    assert!(
        rejected,
        "native admitted rehashed unequal-width ADD as a BIL shift"
    );
}

#[test]
#[ignore = "requires pinned BAP, LLVM MC and rebuilt guarded native helper in remote WSL"]
fn guarded_native_accepts_full_unsigned_budgets_and_retains_zero_budget_stop() {
    use ariadne::bap::guard_admission;
    use ariadne::input::FramePreparation;
    use ariadne::investigation::FrameRecoveryLimits;
    let snapshot = FileSnapshot::open_minidump(
        root().join("tests/input/fixtures/guard-frame.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    let bap = ariadne::bap::Config::from_env();
    let options = PreparationOptions::default();
    let reference_decoder = decoder();
    let setup = FramePreparation {
        decoder: &reference_decoder,
        config: &bap,
        options: &options,
        limits: PrepareLimits::default(),
    };
    for zero in [false, true] {
        let limits = guard_admission::Limits {
            max_sites: usize::MAX,
            max_edges: usize::MAX,
            max_residue_updates: usize::MAX,
            max_transfer_evaluations: usize::MAX,
            max_closure_rounds: usize::MAX,
            max_evidence_bytes: usize::MAX,
            max_elapsed_ms: if zero { 0 } else { u64::MAX },
        };
        let prepared = snapshot
            .prepare_frame_with_bap_assuming_windows_call_entry(
                &chain,
                0,
                0x400200,
                &setup,
                limits.clone(),
            )
            .unwrap();
        let proof = prepared.guard_admission().unwrap();
        assert_eq!(proof.input.limits, limits);
        if zero {
            assert_eq!(proof.stop.as_deref(), Some("guard-zero-work-budget"));
            assert!(proof.guards.is_empty());
            assert_eq!(
                prepared.prepared.request.instructions[&0x400204].kind,
                ariadne::InstructionKind::Stop
            );
        } else {
            assert_eq!(proof.guards[0].verdict, guard_admission::Verdict::Aligned);
        }
        let reference = CompletedAnalysis::from_analyzer(
            Analyzer::new(prepared.prepared.request.clone()).unwrap(),
        );
        let native =
            NativeAnalyzer::from_capture(&config(), "guard-full-unsigned-budgets", &prepared)
                .unwrap()
                .complete()
                .unwrap();
        assert_eq!(reference.state(), native.state());
        ariadne::input::investigation::bind_investigation(&prepared, &native).unwrap();
    }
}
