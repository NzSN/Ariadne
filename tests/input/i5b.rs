use ariadne::effects::{self, *};
use ariadne::input::{
    AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits,
    investigation::bind_zero_base_offset,
};
use ariadne::investigation::*;
use ariadne::llvm_mc::{PreparedBatch, PreparedSite};
use ariadne::{AnalysisView, Analyzer, ByteSource, Instruction, InstructionKind};
use serde_json::Value;
use std::{collections::BTreeMap, path::PathBuf};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
fn independent_receipt(
    row: &Value,
) -> ariadne::llvm_mc::address_reference::DecodedAddressReference {
    use ariadne::llvm_mc::address_reference::DecodedAddressReference;
    let name = row["name"].as_str().unwrap();
    let opcode = row["opcode"].as_str().unwrap();
    let mut base = Some(row["base"].as_str().unwrap().to_uppercase());
    let mut index = None;
    let mut scale = 1;
    let mut segment = None;
    match name {
        "index-only" => {
            base = None;
            index = Some("RAX".into());
        }
        "absolute" => base = None,
        "rip-relative" => base = Some("RIP".into()),
        "indexed" => {
            index = Some("RCX".into());
            scale = 2;
        }
        "merged-base-index" => index = Some("RAX".into()),
        "segment" => segment = Some("FS".into()),
        "address-size" => base = Some("EAX".into()),
        _ => {}
    }
    let tuple = format!(
        "r:{} i:{} r:{} i:{} r:{}",
        base.as_deref().unwrap_or("NONE"),
        scale,
        index.as_deref().unwrap_or("NONE"),
        row["displacement"].as_i64().unwrap(),
        segment.as_deref().unwrap_or("NONE")
    );
    let load = opcode.ends_with("rm");
    let width = row["access_width"].as_u64().unwrap() as u8;
    let operands = if load {
        format!("r:{} {tuple}", if width == 64 { "RAX" } else { "EAX" })
    } else if opcode.ends_with("mr") {
        format!("{tuple} r:{}", if width == 64 { "RAX" } else { "EAX" })
    } else {
        format!("{tuple} i:5")
    };
    let length = row["code"].as_str().unwrap().len() / 2;
    let raw = format!(
        "v2 {opcode} 6 {operands} {} {} 0 0 -1 -1 -1 -1 -1 -1 4198400 ok {length} ordinary -",
        usize::from(load),
        if load { 1 } else { 2 }
    );
    DecodedAddressReference {
        address: 0x401000,
        bytes_hex: row["code"].as_str().unwrap().into(),
        length: length as u8,
        opcode: opcode.into(),
        memory_operand: usize::from(load),
        rip_relative: base.as_deref() == Some("RIP"),
        base,
        index,
        scale,
        displacement: row["displacement"].as_i64().unwrap(),
        segment,
        address_width: if name == "address-size" { 32 } else { 64 },
        access_width: width,
        raw_record: raw,
        decoder_sha256: Some("4".repeat(64)),
        decoder_version: "LLVM MC 20.1.2".into(),
        protocol: 2,
        target: "x86_64-pc-windows-msvc".into(),
        gaps: if ["segment", "address-size", "repeat", "lock"].contains(&name) {
            vec!["decoded-encoding-disagreement-or-prefix".into()]
        } else {
            Vec::new()
        },
    }
}

fn assess(
    p: &FilePreparedAnalysis,
    a: &dyn AnalysisView,
    limits: ZeroBaseOffsetLimits,
) -> ZeroBaseOffsetAssessment {
    let bound = bind_zero_base_offset(
        p,
        a,
        FaultAddressQuestion {
            site: 0x401000,
            memory_access: 0,
        },
    )
    .unwrap();
    assess_zero_base_offset(&bound, limits).unwrap()
}

#[test]
fn pilot_decisions_use_base_and_displacement_not_effective_zero() {
    for row in cases().into_iter().filter(|r| {
        [
            "mov32mi-positive",
            "mov32mi-nonzero",
            "mov32mi-no-displacement",
            "effective-zero-nonzero-base",
            "missing-integer",
            "last-access-byte",
            "index-only",
        ]
        .contains(&r["name"].as_str().unwrap())
    }) {
        let (p, a) = prepare(&row, false);
        let result = assess(&p, &a, ZeroBaseOffsetLimits::default());
        assert_eq!(
            serde_json::to_value(result.conclusion).unwrap(),
            row["outcome"],
            "{}",
            row["name"]
        );
        result.validate().unwrap();
        if result.conclusion != ZeroAddressConclusion::Unknown {
            assert_eq!(
                result.evaluated_address.unwrap().value,
                row["address"].as_u64().unwrap()
            );
        }
    }
}

#[test]
fn independent_corpus_covers_six_forms_and_admission_negatives() {
    for row in cases() {
        let (p, a) = prepare(&row, false);
        let result = assess(&p, &a, ZeroBaseOffsetLimits::default());
        assert_eq!(
            serde_json::to_value(result.conclusion).unwrap(),
            row["outcome"],
            "{}",
            row["name"]
        );
        for format in [
            ariadne::reports::Format::Text,
            ariadne::reports::Format::Json,
            ariadne::reports::Format::Dot,
        ] {
            ariadne::reports::render_zero_base_offset(&result, format).unwrap();
        }
        let encoded = ariadne::reports::encode_zero_base_offset(&result).unwrap();
        assert_eq!(
            ariadne::reports::decode_zero_base_offset(&serde_json::to_vec(&encoded).unwrap())
                .unwrap(),
            result
        );
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM and OCaml helper"]
fn native_corpus_and_reference_match_independent_oracle() {
    for row in cases() {
        let (p, a) = prepare(&row, true);
        let reference = assess(&p, &a, ZeroBaseOffsetLimits::default());
        assert_eq!(
            serde_json::to_value(reference.conclusion).unwrap(),
            row["outcome"],
            "{}",
            row["name"]
        );
        let native = ariadne::bap::core_adapter::NativeAnalyzer::from_capture(
            &ariadne::bap::core_session::CoreConfig::from_directory(
                root().join("target/bap-core-native"),
            ),
            "i5b-oracle",
            &p,
        )
        .unwrap()
        .complete()
        .unwrap();
        assert_eq!(
            assess(&p, &native, ZeroBaseOffsetLimits::default()),
            reference,
            "{}",
            row["name"]
        );
    }
}

#[test]
fn budgets_binding_and_strict_decoding_preserve_unknown_or_errors() {
    let row = &cases()[0];
    let (p, a) = prepare(row, false);
    for evidence in [0, 1, 2, 31, 32, 33, 64] {
        for claims in [0, 1, 2, 31, 32, 33, 34, 64] {
            let result = assess(
                &p,
                &a,
                ZeroBaseOffsetLimits {
                    max_evidence: evidence,
                    max_claims: claims,
                },
            );
            result.validate().unwrap();
            if result.truncated {
                assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
            }
        }
    }
    let result = assess(&p, &a, ZeroBaseOffsetLimits::default());
    let original = ariadne::reports::encode_zero_base_offset(&result).unwrap();
    for field in ["scope_id", "receipt_digest", "context_digest", "profile"] {
        let mut tampered = original.clone();
        tampered[field] = "changed".into();
        assert!(
            ariadne::reports::decode_zero_base_offset(&serde_json::to_vec(&tampered).unwrap())
                .is_err()
        );
    }
    let mut tampered = original.clone();
    tampered["conclusion"] = "refuted_under_premises".into();
    assert!(
        ariadne::reports::decode_zero_base_offset(&serde_json::to_vec(&tampered).unwrap()).is_err()
    );
    let text = serde_json::to_string(&original).unwrap();
    assert!(
        ariadne::reports::decode_zero_base_offset(
            text.replacen("{", "{\"profile\":\"duplicate\",", 1)
                .as_bytes()
        )
        .is_err()
    );
    for site in [0x401001, 0x999999] {
        assert!(
            bind_zero_base_offset(
                &p,
                &a,
                FaultAddressQuestion {
                    site,
                    memory_access: 0
                }
            )
            .is_err()
        );
    }
    assert!(
        bind_zero_base_offset(
            &p,
            &a,
            FaultAddressQuestion {
                site: 0x401000,
                memory_access: 1
            }
        )
        .is_err()
    );
    let mut different_request = p.prepared.request.clone();
    different_request.slice_seeds.clear();
    let wrong_query =
        ariadne::CompletedAnalysis::from_analyzer(Analyzer::new(different_request).unwrap());
    assert!(
        bind_zero_base_offset(
            &p,
            &wrong_query,
            FaultAddressQuestion {
                site: 0x401000,
                memory_access: 0
            }
        )
        .is_err()
    );
    let mut changed = p.clone();
    changed.prepared.request.snapshot_id.push_str("changed");
    assert!(
        bind_zero_base_offset(
            &changed,
            &a,
            FaultAddressQuestion {
                site: 0x401000,
                memory_access: 0
            }
        )
        .is_err()
    );
    let mut changed = p.clone();
    changed
        .prepared
        .instructions
        .get_mut(&0x401000)
        .unwrap()
        .decoded_address
        .as_mut()
        .unwrap()
        .base = Some("RBX".into());
    assert!(
        bind_zero_base_offset(
            &changed,
            &a,
            FaultAddressQuestion {
                site: 0x401000,
                memory_access: 0
            }
        )
        .is_err()
    );
}

#[test]
fn decoded_bil_disagreement_and_missing_receipt_are_unknown() {
    for variation in 0..4 {
        let (mut p, a) = prepare(&cases()[0], false);
        let s = p.prepared.instructions.get_mut(&0x401000).unwrap();
        match variation {
            0 => s.decoded_address = None,
            1 => {
                s.semantic.as_mut().unwrap().memory_accesses[0]
                    .expression
                    .as_mut()
                    .unwrap()
                    .constant = 9
            }
            2 => s.semantic.as_mut().unwrap().memory_accesses[0]
                .expression
                .as_mut()
                .unwrap()
                .terms
                .clear(),
            _ => s.decoded_address.as_mut().unwrap().decoder_sha256 = None,
        }
        if variation == 2 {
            s.semantic.as_mut().unwrap().memory_accesses[0]
                .address_inputs
                .clear();
        }
        let result = assess(&p, &a, ZeroBaseOffsetLimits::default());
        assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
        assert!(result.evaluated_address.is_none());
    }
}

#[test]
#[ignore = "requires native BAP/LLVM, CLI and OCaml helper"]
fn cli_modes_publish_atomically_and_never_promote_question_roots() {
    use std::process::Command;
    let cli = env!("CARGO_BIN_EXE_ariadne-minidump");
    let work = std::env::temp_dir().join(format!("ariadne-i5b-cli-{}", std::process::id()));
    std::fs::create_dir_all(&work).unwrap();
    let dump = root().join("tests/input/fixtures/i5b/mov32mi-positive.dmp");
    let decoder_path = decoder();
    let common = [
        dump.to_str().unwrap(),
        "--decoder-reference",
        decoder_path.to_str().unwrap(),
        "--entry",
        "401000",
    ];
    let output = work.join("bundle");
    let result = Command::new(cli)
        .args(common)
        .args([
            "--assess-zero-base-offset",
            "401000",
            "--memory-access",
            "0",
            "--output-dir",
        ])
        .arg(&output)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    assert_eq!(std::fs::read_dir(&output).unwrap().count(), 6);
    let record = ariadne::reports::decode_zero_base_offset(
        &std::fs::read(output.join("zero-base-offset-assessment.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(
        record.conclusion,
        ZeroAddressConclusion::ConsistentWithEvidence
    );
    let before = std::fs::read(output.join("report.json")).unwrap();
    let repeated = Command::new(cli)
        .args(common)
        .args([
            "--assess-zero-base-offset",
            "401000",
            "--memory-access",
            "0",
            "--output-dir",
        ])
        .arg(&output)
        .output()
        .unwrap();
    assert!(!repeated.status.success());
    assert_eq!(std::fs::read(output.join("report.json")).unwrap(), before);
    for extra in [
        vec![
            "--assess-zero-base-offset",
            "401000",
            "--assess-zero-address",
            "401000",
            "--memory-access",
            "0",
            "--assessment-only",
            "--format",
            "json",
        ],
        vec![
            "--assess-zero-base-offset",
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
            "--assess-zero-base-offset",
            "401000",
            "--memory-access",
            "0",
            "--stateflow-input",
            "missing.json",
            "--assessment-only",
            "--format",
            "json",
        ],
        vec![
            "--assess-zero-base-offset",
            "401000",
            "--memory-access",
            "99",
            "--assessment-only",
            "--format",
            "json",
        ],
    ] {
        let result = Command::new(cli).args(common).args(extra).output().unwrap();
        assert!(!result.status.success());
        assert!(result.stdout.is_empty());
    }
    let result = Command::new(cli)
        .args([
            dump.to_str().unwrap(),
            "--decoder-reference",
            decoder_path.to_str().unwrap(),
            "--entry",
            "401007",
            "--assess-zero-base-offset",
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
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let answer = ariadne::reports::decode_zero_base_offset(&result.stdout).unwrap();
    assert_eq!(answer.conclusion, ZeroAddressConclusion::Unknown);
    assert!(answer.gaps.iter().any(|g| g == "site-not-reached"));
    std::fs::remove_dir_all(work).unwrap();
}

#[test]
#[ignore = "requires native BAP/LLVM"]
fn opaque_upstream_call_keeps_producers_partial_but_numeric_site_admitted() {
    let snapshot = FileSnapshot::open_minidump(
        root().join("tests/input/fixtures/i5b/upstream-call.dmp"),
        OpenLimits::default(),
    )
    .unwrap();
    let p = snapshot
        .prepare(
            &AnalysisQuery {
                entry_points: [0x401000].into(),
                slice_seeds: [0x401005].into(),
            },
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    let completed = ariadne::CompletedAnalysis::from_analyzer(
        Analyzer::new(p.prepared.request.clone()).unwrap(),
    );
    let question = FaultAddressQuestion {
        site: 0x401005,
        memory_access: 0,
    };
    let bound = bind_zero_base_offset(&p, &completed, question.clone()).unwrap();
    assert_eq!(
        assess_zero_base_offset(&bound, ZeroBaseOffsetLimits::default())
            .unwrap()
            .conclusion,
        ZeroAddressConclusion::ConsistentWithEvidence
    );
    let producer = ariadne::input::investigation::bind_investigation(&p, &completed).unwrap();
    let explanation = explain_fault_address(&producer, question, ExplainLimits::default()).unwrap();
    assert_eq!(explanation.status, AnswerStatus::Partial);
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/ariadne-llvm-mc"))
}
fn cases() -> Vec<Value> {
    serde_json::from_slice::<Value>(include_bytes!("fixtures/i5b/manifest.json")).unwrap()["cases"]
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
            "tests/input/fixtures/i5b/{}.dmp",
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
    let mut prepared = if native {
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
        let opcode = row["opcode"].as_str().unwrap();
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
    if !native {
        let site = prepared.prepared.instructions.get_mut(&0x401000).unwrap();
        let receipt = independent_receipt(row);
        site.decoder_record = Some(receipt.raw_record.clone());
        site.decoded_address = Some(receipt);
    }
    let mut analyzer = Analyzer::new(prepared.prepared.request.clone()).unwrap();
    while analyzer.step() {}
    (prepared, analyzer)
}
