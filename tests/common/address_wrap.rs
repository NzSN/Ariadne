//! Shared public-bound MOV32mi fixtures and independent frozen oracle assertions.
use ariadne::effects::{
    AddressExpression, AddressTerm, EffectQuality, InstructionEvidence, MemoryAccessEvidence,
    MemoryAccessRole, PreparationIdentity, PreparationOptions, SemanticEvidence,
};
use ariadne::input::{
    AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits, bind_address_wrap,
};
use ariadne::investigation::{
    AddressWrapAssertion, AddressWrapAssessment, AddressWrapKind, AddressWrapLimits,
    Classification, Error, FaultAddressQuestion, assess_address_wrap,
};
use ariadne::llvm_mc::address_reference::DecodedAddressReference;
use ariadne::llvm_mc::{PreparedBatch, PreparedSite};
use ariadne::{Analyzer, ByteSource, CompletedAnalysis, Instruction, InstructionKind};
use serde_json::Value;
use std::{collections::BTreeMap, path::PathBuf};

pub(crate) const SITE: u64 = 0x401000;

pub(crate) fn oracle(name: &str) -> Value {
    serde_json::from_slice::<Value>(include_bytes!("../input/fixtures/i5c/manifest.json")).unwrap()
        ["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["name"] == name)
        .unwrap()
        .clone()
}

fn bytes(text: &str) -> Vec<u8> {
    (0..text.len())
        .step_by(2)
        .map(|at| u8::from_str_radix(&text[at..at + 2], 16).unwrap())
        .collect()
}

fn va(value: &Value) -> u64 {
    u64::from_str_radix(value.as_str().unwrap().trim_start_matches("0x"), 16).unwrap()
}

pub(crate) fn question() -> FaultAddressQuestion {
    FaultAddressQuestion {
        site: SITE,
        memory_access: 0,
    }
}

pub(crate) fn assert_capture_identity(snapshot: &FileSnapshot, raw_name: &str) {
    let corpus: Value =
        serde_json::from_slice(include_bytes!("../input/fixtures/i5c/raw-corpus.json")).unwrap();
    let pinned = corpus["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["name"] == raw_name)
        .unwrap();
    assert_eq!(
        snapshot.metadata().artifact_sha256,
        pinned["sha256"].as_str().unwrap()
    );
    assert_eq!(
        snapshot.metadata().artifact_bytes as u64,
        pinned["bytes"].as_u64().unwrap()
    );
}

fn receipt(row: &Value, target: &str) -> Option<DecodedAddressReference> {
    if !row["receipt"].as_bool().unwrap() {
        return None;
    }
    let decoded = &row["decoded_receipt"];
    assert_eq!(decoded["opcode"], "MOV32mi");
    assert_eq!(decoded["base"], "rax");
    assert!(decoded["index"].is_null());
    let length = decoded["length"].as_u64().unwrap() as u8;
    let displacement = decoded["signed_displacement"].as_i64().unwrap();
    let payload = decoded["immediate_payload"].as_u64().unwrap();
    let raw = format!(
        "v2 MOV32mi 6 r:RAX i:1 r:NONE i:{displacement} r:NONE i:{payload} 0 2 0 0 -1 -1 -1 -1 -1 -1 {SITE} ok {length} ordinary -"
    );
    Some(DecodedAddressReference {
        address: SITE,
        bytes_hex: row["code"].as_str().unwrap().into(),
        length,
        opcode: "MOV32mi".into(),
        memory_operand: 0,
        base: Some("RAX".into()),
        index: None,
        scale: 1,
        displacement,
        segment: None,
        address_width: 64,
        access_width: 32,
        rip_relative: false,
        raw_record: raw,
        decoder_sha256: (row["name"] != "missing-decoder-identity").then(|| "4".repeat(64)),
        decoder_version: "LLVM MC 20.1.2".into(),
        protocol: 2,
        target: target.into(),
        gaps: Vec::new(),
    })
}

pub(crate) fn prepare(
    name: &str,
    mut before_seal: impl FnMut(&mut InstructionEvidence),
) -> (FilePreparedAnalysis, CompletedAnalysis) {
    let row = oracle(name);
    let raw_name = if row["harness"] == "synthetic-capture" {
        name
    } else {
        // These bound-unit rows vary limits or supplied preparation facts over
        // the same frozen upper-wrap capture; no new dump is constructed.
        let original = oracle("mov32mi-upper");
        for field in [
            "code",
            "registers",
            "context_flags",
            "parameter_count",
            "reported",
        ] {
            assert_eq!(row[field], original[field], "{name}: {field}");
        }
        "mov32mi-upper"
    };
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let path = root
        .join("tests/input/fixtures/i5c/dumps")
        .join(format!("{raw_name}.dmp"));
    let snapshot = FileSnapshot::open_minidump(path, OpenLimits::default()).unwrap();
    assert_capture_identity(&snapshot, raw_name);
    let code = bytes(row["code"].as_str().unwrap());
    let mut address = AddressExpression {
        width: 64,
        terms: vec![AddressTerm {
            bank: 0,
            coefficient: 1,
        }],
        constant: row["decoded_receipt"]["signed_displacement"]
            .as_i64()
            .unwrap() as u64,
    };
    if name == "decoder-bap-constant-disagreement" {
        address.constant = address.constant.wrapping_add(1);
    }
    let prepared = snapshot
        .prepare_with_preparer(
            &AnalysisQuery {
                entry_points: [SITE].into(),
                slice_seeds: [SITE].into(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            |_, candidates, _, target| {
                let mut sites = BTreeMap::new();
                for (&va, prefix) in candidates {
                    let selected = va == SITE;
                    let length = if selected { code.len() } else { 1 };
                    let kind = if selected {
                        InstructionKind::Ordinary
                    } else {
                        InstructionKind::Return
                    };
                    let inputs = if selected {
                        address.locations()
                    } else {
                        Default::default()
                    };
                    let decoded = selected.then(|| receipt(&row, target.triple())).flatten();
                    let mut evidence = InstructionEvidence {
                        bytes: prefix.as_ref().unwrap()[..length].to_vec(),
                        source: ByteSource::Captured,
                        opcode: Some(if selected { "MOV32mi" } else { "RET64" }.into()),
                        length: length as u8,
                        operands: Vec::new(),
                        rule: Some("independent-i5c-pilot".into()),
                        control: Some(kind),
                        quality: EffectQuality::ExternalLifted,
                        undefined_flags: Default::default(),
                        decoder_record: decoded.as_ref().map(|value| value.raw_record.clone()),
                        decoded_address: decoded,
                        decoder_control: Some(kind),
                        semantic: Some(SemanticEvidence {
                            backend: "bap-x86-legacy".into(),
                            helper_sha256: "1".repeat(64),
                            runtime_sha256: "2".repeat(64),
                            projection: "bap-bit-provenance-v6".into(),
                            status: "projected".into(),
                            ast_sha256: Some("3".repeat(64)),
                            fallback: None,
                            gaps: Vec::new(),
                            memory_accesses: if selected {
                                vec![MemoryAccessEvidence {
                                    index: 0,
                                    role: MemoryAccessRole::Store,
                                    access_width: 32,
                                    address_width: 64,
                                    expression: Some(address.clone()),
                                    address_inputs: inputs.clone(),
                                    attribution: "independent-i5c-pilot".into(),
                                    gaps: Vec::new(),
                                }]
                            } else {
                                Vec::new()
                            },
                        }),
                    };
                    if selected {
                        assert_eq!(evidence.bytes, code, "{name}");
                        before_seal(&mut evidence);
                    }
                    sites.insert(
                        va,
                        PreparedSite {
                            instruction: Instruction {
                                kind,
                                fall: if selected {
                                    [va + length as u64].into()
                                } else {
                                    Default::default()
                                },
                                complete: true,
                                uses: inputs,
                                ..Instruction::default()
                            },
                            evidence,
                            gaps: Vec::new(),
                            decodable: true,
                            complete_capture: true,
                        },
                    );
                }
                Ok(PreparedBatch {
                    sites,
                    identity: PreparationIdentity {
                        target: target.triple().into(),
                        decoder: "independent-i5c-pilot".into(),
                        protocol: 2,
                        ruleset: "bap-bit-provenance-v6".into(),
                        catalogue: "independent-i5c-pilot".into(),
                    },
                })
            },
        )
        .unwrap();
    let completed =
        CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone()).unwrap());
    (prepared, completed)
}

pub(crate) fn pipeline(
    prepared: &FilePreparedAnalysis,
    completed: &CompletedAnalysis,
    question: FaultAddressQuestion,
    limits: AddressWrapLimits,
) -> Result<AddressWrapAssessment, Error> {
    let bound = bind_address_wrap(prepared, completed, question)?;
    assess_address_wrap(&bound, limits)
}

pub(crate) fn limits(row: &Value) -> AddressWrapLimits {
    AddressWrapLimits {
        max_evidence: row["max_evidence"].as_u64().unwrap() as usize,
        max_claims: row["max_claims"].as_u64().unwrap() as usize,
    }
}

fn arithmetic_claim(assertion: &AddressWrapAssertion) -> bool {
    matches!(
        assertion,
        AddressWrapAssertion::DecodedBase { .. }
            | AddressWrapAssertion::CapturedBase { .. }
            | AddressWrapAssertion::WideSum { .. }
            | AddressWrapAssertion::WrapKind { .. }
            | AddressWrapAssertion::ComputedAddress { .. }
    )
}

pub(crate) fn assert_oracle(result: &AddressWrapAssessment, row: &Value) {
    let expected = &row["expected"];
    assert_eq!(result.schema, "ariadne.address-wrap-assessment/v1");
    assert_eq!(
        serde_json::to_value(result.conclusion).unwrap(),
        expected["conclusion"]
    );
    assert_eq!(
        result.input_evidence_count,
        expected["input_evidence_count"].as_u64().unwrap() as usize
    );
    assert_eq!(
        result.evidence.len(),
        expected["retained_evidence_count"].as_u64().unwrap() as usize
    );
    assert_eq!(
        result.claims.len(),
        expected["retained_claims"].as_u64().unwrap() as usize
    );
    assert_eq!(
        result.inputs_complete,
        expected["inputs_complete"].as_bool().unwrap()
    );
    assert_eq!(result.truncated, expected["truncated"].as_bool().unwrap());
    for gap in expected["required_gaps"].as_array().unwrap() {
        assert!(
            result
                .gaps
                .iter()
                .any(|actual| actual == gap.as_str().unwrap()),
            "{}: {gap}",
            row["name"]
        );
    }
    let arithmetic_claims: Vec<_> = result
        .claims
        .iter()
        .filter(|claim| arithmetic_claim(&claim.assertion))
        .collect();
    if expected["arithmetic"].is_null() {
        assert!(result.arithmetic.is_none(), "{}", row["name"]);
        assert!(
            arithmetic_claims.is_empty(),
            "partial arithmetic claim bundle"
        );
    } else {
        let actual = result.arithmetic.as_ref().unwrap();
        let expected = &expected["arithmetic"];
        assert_eq!(
            actual.base_register,
            expected["base_register"].as_str().unwrap()
        );
        assert_eq!(actual.base_value.value, va(&expected["base_value"]));
        assert_eq!(
            actual.signed_displacement,
            expected["signed_displacement"].as_i64().unwrap()
        );
        assert_eq!(
            actual.displacement_bits.value,
            va(&expected["displacement_bits"])
        );
        assert_eq!(
            actual.sum_before_reduction,
            expected["sum_before_reduction"].as_str().unwrap()
        );
        assert_eq!(
            actual.effective_address.value,
            va(&expected["effective_address"])
        );
        let wrap = match expected["wrap_kind"].as_str().unwrap() {
            "upper" => AddressWrapKind::Upper,
            "lower" => AddressWrapKind::Lower,
            "none" => AddressWrapKind::None,
            other => panic!("unexpected frozen wrap kind {other}"),
        };
        assert_eq!(actual.wrap_kind, wrap);
        assert_eq!(arithmetic_claims.len(), 5);
        assert!(matches!(
            &arithmetic_claims[0].assertion,
            AddressWrapAssertion::DecodedBase { register, displacement }
                if register == expected["base_register"].as_str().unwrap()
                    && *displacement == expected["signed_displacement"].as_i64().unwrap()
        ));
        assert!(matches!(
            &arithmetic_claims[1].assertion,
            AddressWrapAssertion::CapturedBase { register, value }
                if register == expected["base_register"].as_str().unwrap()
                    && *value == va(&expected["base_value"])
        ));
        assert!(matches!(
            &arithmetic_claims[2].assertion,
            AddressWrapAssertion::WideSum { sum_before_reduction }
                if sum_before_reduction == expected["sum_before_reduction"].as_str().unwrap()
        ));
        assert!(matches!(
            &arithmetic_claims[3].assertion,
            AddressWrapAssertion::WrapKind { wrap_kind } if *wrap_kind == wrap
        ));
        assert!(matches!(
            &arithmetic_claims[4].assertion,
            AddressWrapAssertion::ComputedAddress { value }
                if *value == va(&expected["effective_address"])
        ));
        assert!(
            arithmetic_claims
                .iter()
                .all(|claim| claim.classification == Classification::DerivedUnderPremises)
        );
    }
    assert!(result.claims.iter().all(|claim| {
        claim
            .evidence_refs
            .iter()
            .all(|id| result.evidence.iter().any(|evidence| &evidence.id == id))
    }));
    result.validate().unwrap();
}
