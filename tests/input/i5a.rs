use ariadne::effects::{self, *};
use ariadne::input::{
    AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits,
    investigation::{bind_fault_context, bind_investigation},
};
use ariadne::investigation::*;
use ariadne::llvm_mc::{PreparedBatch, PreparedSite};
use ariadne::{AnalysisView, Analyzer, ByteSource, Instruction, InstructionKind};
use serde_json::Value;
use std::{collections::BTreeMap, path::PathBuf, sync::Arc};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/ariadne-llvm-mc"))
}
fn cases() -> Vec<Value> {
    serde_json::from_slice::<Value>(include_bytes!("fixtures/i5a/manifest.json")).unwrap()["cases"]
        .as_array()
        .unwrap()
        .clone()
}
fn bytes(hex: &str) -> Vec<u8> {
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
        .collect()
}
fn prepare(row: &Value, native: bool) -> (FilePreparedAnalysis, Analyzer) {
    let snapshot = FileSnapshot::open_minidump(
        root().join(format!(
            "tests/input/fixtures/i5a/{}.dmp",
            row["name"].as_str().unwrap()
        )),
        OpenLimits::default(),
    )
    .unwrap();
    let site = row["site"].as_u64().unwrap();
    let query = AnalysisQuery {
        entry_points: [site].into(),
        slice_seeds: [site].into(),
    };
    let options = PreparationOptions::default();
    let prepared = if native {
        snapshot
            .prepare(&query, &decoder(), &options, PrepareLimits::default())
            .unwrap()
    } else {
        // Independent normalized summary fixture, not a substitute for native admission.
        let code = bytes(row["code"].as_str().unwrap());
        let banks = [
            "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11",
            "r12", "r13", "r14", "r15",
        ];
        let mut terms: Vec<_> = row["terms"]
            .as_object()
            .unwrap()
            .iter()
            .map(|(name, n)| effects::AddressTerm {
                bank: banks.iter().position(|r| *r == name).unwrap() as u8,
                coefficient: n.as_u64().unwrap(),
            })
            .collect();
        terms.sort_by_key(|t| t.bank);
        let expression = effects::AddressExpression {
            width: 64,
            terms,
            constant: row["constant"].as_u64().unwrap(),
        };
        let opcode = match code.as_slice() {
            [0x48, 0xc7, ..] => "MOV64mi32",
            [0x48, 0x8b, ..] => "MOV64rm",
            [0x48, 0x89, ..] => "MOV64mr",
            [0x8b, ..] => "MOV32rm",
            [0x89, ..] => "MOV32mr",
            [0x50] => "PUSH64r",
            _ => "MOV32mi",
        };
        snapshot
            .prepare_with_preparer(
                &query,
                &options,
                PrepareLimits::default(),
                |_, candidates, _, _| {
                    let mut sites = BTreeMap::new();
                    for (&va, prefix) in candidates {
                        let is_site = va == site;
                        let length = if is_site { code.len() } else { 1 };
                        let kind = if is_site {
                            InstructionKind::Ordinary
                        } else {
                            InstructionKind::Return
                        };
                        let inputs = if is_site {
                            expression.locations()
                        } else {
                            Default::default()
                        };
                        sites.insert(
                            va,
                            PreparedSite {
                                instruction: Instruction {
                                    kind,
                                    fall: if is_site {
                                        [va + length as u64].into()
                                    } else {
                                        Default::default()
                                    },
                                    complete: true,
                                    uses: inputs.clone(),
                                    ..Instruction::default()
                                },
                                evidence: InstructionEvidence {
                                    bytes: prefix.as_ref().unwrap()[..length].to_vec(),
                                    source: ByteSource::Captured,
                                    opcode: Some(if is_site { opcode } else { "RET64" }.into()),
                                    length: length as u8,
                                    operands: Vec::new(),
                                    rule: Some("independent-summary".into()),
                                    control: Some(kind),
                                    quality: EffectQuality::ExternalLifted,
                                    undefined_flags: Default::default(),
                                    decoder_record: None,
                                    decoded_address: None,
                                    decoder_control: Some(kind),
                                    semantic: Some(SemanticEvidence {
                                        backend: "bap-x86-legacy".into(),
                                        helper_sha256: "1".repeat(64),
                                        runtime_sha256: "2".repeat(64),
                                        ast_sha256: Some("3".repeat(64)),
                                        projection: "bap-bit-provenance-v2".into(),
                                        status: "projected".into(),
                                        fallback: None,
                                        gaps: Vec::new(),
                                        memory_accesses: if is_site {
                                            vec![MemoryAccessEvidence {
                                                index: 0,
                                                role: if row["operation"] == 0 {
                                                    MemoryAccessRole::Load
                                                } else {
                                                    MemoryAccessRole::Store
                                                },
                                                access_width: row["access_width"].as_u64().unwrap()
                                                    as u16,
                                                address_width: 64,
                                                expression: Some(expression.clone()),
                                                address_inputs: inputs,
                                                attribution: "independent-fixture".into(),
                                                gaps: Vec::new(),
                                            }]
                                        } else {
                                            Vec::new()
                                        },
                                    }),
                                },
                                gaps: Vec::new(),
                                decodable: true,
                                complete_capture: true,
                            },
                        );
                    }
                    Ok(PreparedBatch {
                        sites,
                        identity: PreparationIdentity {
                            target: "independent-model".into(),
                            decoder: "fixture".into(),
                            protocol: 2,
                            ruleset: "bap-bit-provenance-v2".into(),
                            catalogue: "fixture".into(),
                        },
                    })
                },
            )
            .unwrap()
    };
    let mut analyzer = Analyzer::new(prepared.prepared.request.clone()).unwrap();
    while analyzer.step() {}
    (prepared, analyzer)
}
fn assess(
    p: &FilePreparedAnalysis,
    a: &dyn AnalysisView,
    limits: AssessmentLimits,
) -> ZeroAddressAssessment {
    let bound = bind_fault_context(p, a).unwrap();
    assess_zero_address(
        &bound,
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 0,
        },
        limits,
    )
    .unwrap()
}
fn expected(row: &Value, e: &ZeroAddressAssessment) {
    e.validate().unwrap();
    assert_eq!(e.premises.len(), 3);
    assert!(
        e.premises
            .iter()
            .any(|p| p.contains("no root cause or historical path"))
    );
    for c in &e.claims {
        let class = match &c.assertion {
            ZeroAddressAssertion::CapturedInstruction { .. }
            | ZeroAddressAssertion::CapturedField { .. } => Classification::Observed,
            ZeroAddressAssertion::ComputedAddress { .. } => Classification::DerivedUnderPremises,
            ZeroAddressAssertion::Assessment {
                conclusion: ZeroAddressConclusion::Unknown,
            } => Classification::Unknown,
            ZeroAddressAssertion::Assessment { .. } => Classification::DerivedUnderPremises,
        };
        assert_eq!(c.classification, class);
        if class == Classification::DerivedUnderPremises {
            assert_eq!(c.premises, e.premises);
        }
    }
    assert_eq!(
        serde_json::to_value(e.conclusion).unwrap(),
        row["outcome"],
        "{} gaps={:?}",
        row["name"],
        e.gaps
    );
    if row["outcome"] == "unknown"
        && ![
            "excluded-range",
            "span-wrap",
            "cross-low-range",
            "wrong-data-address",
            "past-access-span",
        ]
        .contains(&row["name"].as_str().unwrap())
    {
        assert!(
            e.evaluated_address.is_none(),
            "unadmitted arithmetic for {}",
            row["name"]
        );
    }
    if row["outcome"] != "unknown" {
        assert_eq!(
            e.evaluated_address.as_ref().unwrap().value,
            row["address"].as_u64().unwrap(),
            "{}",
            row["name"]
        );
        assert!(!e.truncated);
        assert!(e.gaps.is_empty());
    }
}
#[test]
fn independent_context_and_arithmetic_corpus() {
    for row in cases() {
        let (p, a) = prepare(&row, false);
        let e = assess(&p, &a, AssessmentLimits::default());
        expected(&row, &e);
    }
}
#[test]
#[ignore = "requires pinned BAP lifting, LLVM and native analysis helpers"]
fn native_i5a_corpus_matches_independent_context_and_address_expectations() {
    use ariadne::bap::{core_adapter::NativeAnalyzer, core_session::CoreConfig};
    let directory = std::env::var_os("ARIADNE_BAP_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/bap-core-native"));
    let manifest: Value =
        serde_json::from_slice(&std::fs::read(directory.join("manifest.json")).unwrap()).unwrap();
    let config = CoreConfig::from_directory(directory);
    for row in cases() {
        let (p, a) = prepare(&row, true);
        let e = assess(&p, &a, AssessmentLimits::default());
        expected(&row, &e);
        let native = NativeAnalyzer::from_capture(&config, "i5a-corpus", &p).unwrap();
        assert_eq!(native.identity()["backend"], "bap");
        assert_eq!(native.identity()["profile"], "captured-fixed-input/v1");
        assert_eq!(native.identity()["build"], manifest);
        let native = native.complete().unwrap();
        let actual = assess(&p, &native, AssessmentLimits::default());
        expected(&row, &actual);
        assert_eq!(
            serde_json::to_value(actual).unwrap(),
            serde_json::to_value(e).unwrap()
        );
        if row["name"] == "zero-store" {
            check_budgets_and_invalid_questions(&bind_fault_context(&p, &native).unwrap());
            let mut changed = p;
            Arc::make_mut(&mut changed.snapshot)
                .exception
                .as_mut()
                .unwrap()
                .registers
                .insert("rax".into(), 17);
            assert!(bind_fault_context(&changed, &native).is_err());
        }
    }
}
#[test]
fn fault_binding_is_owned_and_rejects_metadata_or_query_substitution() {
    let row = cases().remove(0);
    let (mut p, a) = prepare(&row, false);
    let bound = bind_fault_context(&p, &a).unwrap();
    Arc::make_mut(&mut p.snapshot)
        .exception
        .as_mut()
        .unwrap()
        .registers
        .insert("rax".into(), 17);
    assert!(bind_fault_context(&p, &a).is_err());
    let e = assess_zero_address(
        &bound,
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 0,
        },
        AssessmentLimits::default(),
    )
    .unwrap();
    assert_eq!(e.conclusion, ZeroAddressConclusion::ConsistentWithEvidence);
    let (p, _) = prepare(&row, false);
    let mut request = p.prepared.request.clone();
    request.slice_seeds.clear();
    let mut other = Analyzer::new(request).unwrap();
    while other.step() {}
    assert!(bind_fault_context(&p, &other).is_err());
}
#[test]
fn budgets_preserve_valid_unknown_results_and_invalid_questions_stay_errors() {
    let row = cases().remove(0);
    let (p, a) = prepare(&row, false);
    let bound = bind_fault_context(&p, &a).unwrap();
    check_budgets_and_invalid_questions(&bound);
}
fn check_budgets_and_invalid_questions(bound: &BoundFaultContext) {
    for max_evidence in [0, 1, 2, 3, 16, 31, 32, 33] {
        for max_claims in [0, 1, 2, 16, 31, 32, 33] {
            let e = assess_zero_address(
                bound,
                FaultAddressQuestion {
                    site: 0x401000,
                    memory_access: 0,
                },
                AssessmentLimits {
                    max_evidence,
                    max_claims,
                },
            )
            .unwrap();
            assert!(e.evidence.len() <= max_evidence);
            assert!(e.claims.len() <= max_claims);
            e.validate().unwrap();
            if max_evidence < 32 || max_claims < 32 {
                assert_eq!(e.conclusion, ZeroAddressConclusion::Unknown);
                assert!(e.truncated);
            } else {
                assert_eq!(e.conclusion, ZeroAddressConclusion::ConsistentWithEvidence);
            }
        }
    }
    for question in [
        FaultAddressQuestion {
            site: 0x9999,
            memory_access: 0,
        },
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 1,
        },
    ] {
        assert!(
            assess_zero_address(
                bound,
                question,
                AssessmentLimits {
                    max_evidence: 0,
                    max_claims: 0
                }
            )
            .is_err()
        );
    }
}
#[test]
fn serialized_observation_and_conclusion_tampering_is_rejected() {
    let (p, a) = prepare(&cases().remove(0), false);
    let good = assess(&p, &a, AssessmentLimits::default());
    let bytes = serde_json::to_vec(&good).unwrap();
    let round: ZeroAddressAssessment = serde_json::from_slice(&bytes).unwrap();
    round.validate().unwrap();
    let mut bad = good.clone();
    bad.conclusion = ZeroAddressConclusion::RefutedUnderPremises;
    assert!(bad.validate().is_err());
    let mut bad = good.clone();
    bad.evaluated_address.as_mut().unwrap().value = 1;
    assert!(bad.validate().is_err());
    let mut bad = good.clone();
    bad.premises.clear();
    assert!(bad.validate().is_err());
    let mut bad = good.clone();
    bad.claims[0].evidence_refs.push("missing".into());
    assert!(bad.validate().is_err());
    let mut bad = good.clone();
    bad.question.site += 1;
    assert!(bad.validate().is_err());
    let mut bad = good.clone();
    for e in &mut bad.evidence {
        if let ZeroAddressEvidenceData::Fault {
            datum: FaultDatum::Field { observation },
        } = &mut e.data
        {
            if observation.name == "reg:rax" {
                observation.value = 7;
            }
        }
    }
    assert!(bad.validate().is_err());
}
#[test]
fn numeric_question_does_not_rewrite_prior_analysis_or_producer_uncertainty() {
    let (p, a) = prepare(&cases().remove(0), false);
    let state = a.state().clone();
    let request = a.request().clone();
    let old = explain_fault_address(
        &bind_investigation(&p, &a).unwrap(),
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    assert_eq!(old.status, AnswerStatus::Partial);
    let numeric = assess(&p, &a, AssessmentLimits::default());
    assert_eq!(
        numeric.conclusion,
        ZeroAddressConclusion::ConsistentWithEvidence
    );
    assert_eq!(*a.state(), state);
    assert_eq!(*a.request(), request);
    let after = explain_fault_address(
        &bind_investigation(&p, &a).unwrap(),
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    assert_eq!(
        serde_json::to_value(old).unwrap(),
        serde_json::to_value(after).unwrap()
    );
}

#[test]
fn strict_assessment_formats_preserve_scope_and_reject_extra_or_duplicate_fields() {
    use ariadne::reports::{Format, decode_zero_address, render_zero_address};
    for name in ["zero-store", "nonzero-store", "missing-integer"] {
        let row = cases().into_iter().find(|r| r["name"] == name).unwrap();
        let (p, a) = prepare(&row, false);
        for limits in [
            AssessmentLimits::default(),
            AssessmentLimits {
                max_evidence: 0,
                max_claims: 0,
            },
        ] {
            let e = assess(&p, &a, limits);
            let json = render_zero_address(&e, Format::Json).unwrap();
            assert_eq!(decode_zero_address(json.as_bytes()).unwrap(), e);
            let text = render_zero_address(&e, Format::Text).unwrap();
            assert!(text.contains(&e.identity.query_id));
            let dot = render_zero_address(&e, Format::Dot).unwrap();
            let embedded = dot
                .lines()
                .next()
                .unwrap()
                .strip_prefix("// zero_address_assessment: ")
                .unwrap();
            assert_eq!(decode_zero_address(embedded.as_bytes()).unwrap(), e);
            let mut extra: Value = serde_json::from_str(&json).unwrap();
            extra["confidence"] = serde_json::json!(1.0);
            assert!(decode_zero_address(&serde_json::to_vec(&extra).unwrap()).is_err());
            let duplicate = json.replacen('{', "{\"schema\":\"duplicate\",", 1);
            assert!(decode_zero_address(duplicate.as_bytes()).is_err());
        }
    }
}

#[test]
#[ignore = "requires pinned BAP/MC and Graphviz; executes normal CLI publication"]
fn assessment_cli_modes_publish_atomically_and_never_add_entry_roots() {
    use std::process::Command;
    let work = std::env::temp_dir().join(format!(
        "ariadne-i5a-cli-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&work).unwrap();
    let cli = env!("CARGO_BIN_EXE_ariadne-minidump");
    let dump = root().join("tests/input/fixtures/i5a/zero-store.dmp");
    let decoder = decoder();
    let common = [
        dump.as_os_str(),
        std::ffi::OsStr::new("--decoder-reference"),
        decoder.as_os_str(),
        std::ffi::OsStr::new("--entry"),
        std::ffi::OsStr::new("401000"),
    ];
    for name in ["zero-store", "missing-integer"] {
        let capture = root().join(format!("tests/input/fixtures/i5a/{name}.dmp"));
        let out = work.join(name);
        let r = Command::new(cli)
            .args([
                capture.as_os_str(),
                std::ffi::OsStr::new("--decoder-reference"),
                decoder.as_os_str(),
                std::ffi::OsStr::new("--entry"),
                std::ffi::OsStr::new("401000"),
            ])
            .args([
                "--assess-zero-address",
                "401000",
                "--memory-access",
                "0",
                "--output-dir",
            ])
            .arg(&out)
            .output()
            .unwrap();
        assert!(r.status.success(), "{}", String::from_utf8_lossy(&r.stderr));
        let assessment = ariadne::reports::decode_zero_address(
            &std::fs::read(out.join("zero-address-assessment.json")).unwrap(),
        )
        .unwrap();
        assert_eq!(
            assessment.conclusion,
            if name == "zero-store" {
                ZeroAddressConclusion::ConsistentWithEvidence
            } else {
                ZeroAddressConclusion::Unknown
            }
        );
        let core: Value =
            serde_json::from_slice(&std::fs::read(out.join("report.json")).unwrap()).unwrap();
        assert_eq!(
            core["query"]["entries"],
            serde_json::json!(["0x0000000000401000"])
        );
        assert_eq!(std::fs::read_dir(&out).unwrap().count(), 6);
        let graphroot = root().join("tmp/graphviz-headers/root");
        let dot = std::env::var_os("ARIADNE_DOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| graphroot.join("usr/bin/dot"));
        let parsed = Command::new(dot)
            .env(
                "LD_LIBRARY_PATH",
                graphroot.join("usr/lib/x86_64-linux-gnu"),
            )
            .env(
                "GVBINDIR",
                graphroot.join("usr/lib/x86_64-linux-gnu/graphviz"),
            )
            .args(["-Tsvg"])
            .arg(out.join("zero-address-assessment.dot"))
            .arg("-o")
            .arg(work.join(format!("{name}.svg")))
            .output()
            .unwrap();
        assert!(
            parsed.status.success(),
            "{}",
            String::from_utf8_lossy(&parsed.stderr)
        );
        let repeated = Command::new(cli)
            .args(common)
            .args([
                "--assess-zero-address",
                "401000",
                "--memory-access",
                "0",
                "--output-dir",
            ])
            .arg(&out)
            .output()
            .unwrap();
        assert!(!repeated.status.success());
    }
    let one = Command::new(cli)
        .args(common)
        .args([
            "--assess-zero-address",
            "401000",
            "--memory-access",
            "0",
            "--assessment-only",
            "--format",
            "json",
        ])
        .output()
        .unwrap();
    assert!(one.status.success());
    ariadne::reports::decode_zero_address(&one.stdout).unwrap();
    let unreached = Command::new(cli)
        .arg(&dump)
        .arg("--decoder-reference")
        .arg(&decoder)
        .args([
            "--entry",
            "401006",
            "--assess-zero-address",
            "401000",
            "--memory-access",
            "0",
            "--assessment-only",
            "--format",
            "json",
        ])
        .output()
        .unwrap();
    assert!(
        unreached.status.success(),
        "{}",
        String::from_utf8_lossy(&unreached.stderr)
    );
    let value = ariadne::reports::decode_zero_address(&unreached.stdout).unwrap();
    assert_eq!(value.conclusion, ZeroAddressConclusion::Unknown);
    assert!(value.gaps.iter().any(|g| g == "site-not-reached"));
    for extra in [
        vec!["--assessment-only", "--format", "json"],
        vec![
            "--assess-zero-address",
            "401000",
            "--memory-access",
            "0",
            "--format",
            "json",
        ],
        vec![
            "--assess-zero-address",
            "401000",
            "--explain-fault-address",
            "401000",
            "--memory-access",
            "0",
            "--assessment-only",
            "--format",
            "json",
        ],
        vec![
            "--assess-zero-address",
            "401000",
            "--memory-access",
            "0",
            "--assessment-only",
            "--stateflow-input",
            "missing.json",
            "--format",
            "json",
        ],
    ] {
        let r = Command::new(cli).args(common).args(extra).output().unwrap();
        assert!(!r.status.success());
        assert!(r.stdout.is_empty());
    }
    std::fs::remove_dir_all(work).unwrap();
}

#[test]
fn malformed_fault_extents_and_parameter_counts_are_rejected_before_binding() {
    let row = cases().remove(0);
    let original = std::fs::read(root().join("tests/input/fixtures/i5a/zero-store.dmp")).unwrap();
    let offset = row["offsets"]["exception_offset"].as_u64().unwrap() as usize;
    for (at, value) in [(32, 16u32), (164, u32::MAX)] {
        let mut bytes = original.clone();
        bytes[offset + at..offset + at + 4].copy_from_slice(&value.to_le_bytes());
        assert!(FileSnapshot::from_minidump_bytes(bytes, OpenLimits::default()).is_err());
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM; prior fixtures lack the new evidence"]
fn legacy_stage_b_fixtures_remain_unknown_for_i5a() {
    for (name, entry) in [
        ("stage_b_windows.dmp", 0x7ff700001000),
        ("stage_b_linux.dmp", 0x401000),
    ] {
        let snapshot = FileSnapshot::open_minidump(
            root().join("tests/input/fixtures").join(name),
            OpenLimits::default(),
        )
        .unwrap();
        let p = snapshot
            .prepare(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [entry + 6].into(),
                },
                &decoder(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        let mut a = Analyzer::new(p.prepared.request.clone()).unwrap();
        while a.step() {}
        let result = assess_zero_address(
            &bind_fault_context(&p, &a).unwrap(),
            FaultAddressQuestion {
                site: entry + 6,
                memory_access: 0,
            },
            AssessmentLimits::default(),
        )
        .unwrap();
        assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
        assert!(result.evaluated_address.is_none());
        assert!(
            result
                .gaps
                .iter()
                .any(|g| g == "missing-access-violation-parameters")
        );
    }
}

#[test]
fn unadmitted_access_shapes_cannot_produce_numeric_claims() {
    for variation in 0..6 {
        let (mut p, a) = prepare(&cases().remove(0), false);
        let site = p.prepared.instructions.get_mut(&0x401000).unwrap();
        let semantic = site.semantic.as_mut().unwrap();
        match variation {
            0 => {
                let mut second = semantic.memory_accesses[0].clone();
                second.index = 1;
                semantic.memory_accesses.push(second);
            }
            1 => semantic.memory_accesses[0]
                .gaps
                .push("conditional-memory-access".into()),
            2 => semantic.memory_accesses[0].role = MemoryAccessRole::Load,
            3 => semantic.memory_accesses[0].access_width = 64,
            4 => {
                semantic.memory_accesses[0].expression = None;
                semantic.memory_accesses[0]
                    .gaps
                    .push("unsupported-address-cast".into());
            }
            _ => semantic.projection = "unreviewed-projection".into(),
        }
        let result = assess(&p, &a, AssessmentLimits::default());
        assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
        assert!(result.evaluated_address.is_none());
    }
}
