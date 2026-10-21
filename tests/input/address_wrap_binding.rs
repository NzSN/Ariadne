//! Binding controls over the frozen raw corpus and supplied finite summaries.
//! The W1 binding controls retain their original behavior. Ordinary W3 tests use
//! supplied preparation facts; the separately ignored native gate explicitly
//! requires production preparation and completed analysis for all 114 captures.
use super::*;
use crate::effects::{
    AddressExpression, AddressTerm, MemoryAccessEvidence, MemoryAccessRole, Operand,
    SemanticEvidence,
};
use crate::input::investigation::bind_address_wrap;
use crate::investigation::{
    AddressWrapArithmetic, AddressWrapAssertion, AddressWrapAssessment, AddressWrapEvidenceData,
    AddressWrapKind, AddressWrapLimits, BoundAddressWrapContext, Classification,
    FaultAddressQuestion, FaultDatum, ZeroAddressConclusion, assess_address_wrap,
};
use crate::llvm_mc::address_reference::DecodedAddressReference;
use crate::llvm_mc::{PreparedBatch, PreparedSite};
use crate::{Analyzer, CompletedAnalysis};
use serde_json::Value;
use std::path::PathBuf;

const SITE: u64 = 0x401000;
const NEXT: u64 = SITE + 7;
const BANKS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];

pub(crate) fn cases() -> Vec<Value> {
    serde_json::from_slice::<Value>(include_bytes!("fixtures/i5c/manifest.json")).unwrap()["cases"]
        .as_array()
        .unwrap()
        .clone()
}

pub(crate) fn case(name: &str) -> Value {
    cases().into_iter().find(|row| row["name"] == name).unwrap()
}

pub(crate) fn bytes(text: &str) -> Vec<u8> {
    (0..text.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&text[index..index + 2], 16).unwrap())
        .collect()
}

fn register(name: &str, width: u64) -> String {
    let bank = BANKS.iter().position(|candidate| *candidate == name);
    match (bank, width) {
        (Some(index), 32) if index < 8 => {
            ["EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI"][index].into()
        }
        (Some(index), 32) => format!("R{index}D"),
        (Some(index), 16) if index < 8 => {
            ["AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"][index].into()
        }
        (Some(index), 16) => format!("R{index}W"),
        _ => name.to_uppercase(),
    }
}

fn selected_bytes(row: &Value) -> &str {
    row["selected_instruction"]["bytes_hex"]
        .as_str()
        .unwrap_or_else(|| row["code"].as_str().unwrap())
}

fn selected_opcode(row: &Value) -> &str {
    row["selected_instruction"]["opcode"]
        .as_str()
        .unwrap_or_else(|| row["opcode"].as_str().unwrap())
}

fn raw_record(row: &Value) -> String {
    let opcode = selected_opcode(row);
    let length = selected_bytes(row).len() / 2;
    if ["XRELEASE_PREFIX", "LOCK_PREFIX"].contains(&opcode) {
        return format!("v2 {opcode} 0 0 4 0 0 {SITE} ok 1 ordinary -");
    }
    let worksheet = &row["decoded_receipt"];
    let width = worksheet["access_width"].as_u64().unwrap();
    let address_width = worksheet["address_width"].as_u64().unwrap();
    let name = |field: &str| {
        worksheet[field]
            .as_str()
            .map(|value| register(value, address_width))
            .unwrap_or_else(|| "NONE".into())
    };
    let tuple = format!(
        "r:{} i:{} r:{} i:{} r:{}",
        name("base"),
        worksheet["scale"].as_u64().unwrap(),
        name("index"),
        worksheet["signed_displacement"].as_i64().unwrap(),
        worksheet["segment"]
            .as_str()
            .unwrap_or("NONE")
            .to_uppercase(),
    );
    let load = worksheet["operation"] == 0;
    let operands = if load {
        format!("r:{} {tuple}", register("rax", width))
    } else if opcode == "MOVUPSmr" {
        format!("{tuple} r:XMM0")
    } else if let Some(payload) = worksheet["payload_register"].as_str() {
        format!("{tuple} r:{}", register(payload, width))
    } else {
        format!(
            "{tuple} i:{}",
            worksheet["immediate_payload"].as_u64().unwrap() as i64
        )
    };
    format!(
        "v2 {opcode} 6 {operands} {} {} 0 0 -1 -1 -1 -1 -1 -1 {SITE} ok {length} ordinary -",
        usize::from(load),
        if load { 1 } else { 2 },
    )
}

pub(crate) fn independent_receipt(row: &Value, target: &str) -> Option<DecodedAddressReference> {
    if !row["receipt"].as_bool().unwrap() {
        return None;
    }
    let worksheet = &row["decoded_receipt"];
    let address_width = worksheet["address_width"].as_u64().unwrap();
    let name = |field: &str| {
        worksheet[field]
            .as_str()
            .map(|value| register(value, address_width))
    };
    Some(DecodedAddressReference {
        address: SITE,
        bytes_hex: selected_bytes(row).into(),
        length: (selected_bytes(row).len() / 2) as u8,
        opcode: selected_opcode(row).into(),
        memory_operand: worksheet["memory_operand"].as_u64().unwrap() as usize,
        base: name("base"),
        index: name("index"),
        scale: worksheet["scale"].as_u64().unwrap() as u8,
        displacement: worksheet["signed_displacement"].as_i64().unwrap(),
        segment: worksheet["segment"].as_str().map(str::to_uppercase),
        address_width: address_width as u8,
        access_width: worksheet["access_width"].as_u64().unwrap() as u8,
        rip_relative: worksheet["rip_relative"].as_bool().unwrap(),
        raw_record: raw_record(row),
        decoder_sha256: Some("4".repeat(64)),
        decoder_version: "LLVM MC 20.1.2".into(),
        protocol: 2,
        target: target.into(),
        gaps: if worksheet["prefixes"].as_array().unwrap().is_empty() {
            Vec::new()
        } else {
            vec!["decoded-encoding-disagreement-or-prefix".into()]
        },
    })
}

pub(crate) fn expression(row: &Value) -> AddressExpression {
    let worksheet = &row["decoded_receipt"];
    let mut coefficients = BTreeMap::new();
    for (field, coefficient) in [("base", 1), ("index", worksheet["scale"].as_u64().unwrap())] {
        if let Some(bank) = worksheet[field]
            .as_str()
            .and_then(|name| BANKS.iter().position(|candidate| *candidate == name))
        {
            *coefficients.entry(bank as u8).or_insert(0) += coefficient;
        }
    }
    let displacement = worksheet["signed_displacement"].as_i64().unwrap() as u64;
    AddressExpression {
        width: 64,
        terms: coefficients
            .into_iter()
            .map(|(bank, coefficient)| AddressTerm { bank, coefficient })
            .collect(),
        constant: if worksheet["rip_relative"].as_bool().unwrap() {
            (SITE + worksheet["length"].as_u64().unwrap()).wrapping_add(displacement)
        } else {
            displacement
        },
    }
}

fn prepare(
    row: &Value,
    mut before_seal: impl FnMut(&mut InstructionEvidence),
) -> FilePreparedAnalysis {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures/i5c/dumps")
        .join(format!("{}.dmp", row["name"].as_str().unwrap()));
    let snapshot = FileSnapshot::open_minidump(path, OpenLimits::default()).unwrap();
    let code = bytes(selected_bytes(row));
    let address = expression(row);
    let unsupported_address =
        ["segment-fs", "address-size"].contains(&row["name"].as_str().unwrap());
    let isolated_prefix = ["repeat", "lock"].contains(&row["name"].as_str().unwrap());
    let stopped = unsupported_address || isolated_prefix;
    snapshot
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
                    let kind = if !selected {
                        InstructionKind::Return
                    } else if stopped {
                        InstructionKind::Stop
                    } else {
                        InstructionKind::Ordinary
                    };
                    let inputs = if selected && !stopped {
                        address.locations()
                    } else {
                        LocationSet::new()
                    };
                    let receipt = selected
                        .then(|| independent_receipt(row, target.triple()))
                        .flatten();
                    let mut evidence = InstructionEvidence {
                        bytes: prefix.as_ref().unwrap()[..length].to_vec(),
                        source: ByteSource::Captured,
                        opcode: Some(
                            if selected {
                                selected_opcode(row)
                            } else {
                                "RET64"
                            }
                            .into(),
                        ),
                        length: length as u8,
                        operands: Vec::new(),
                        rule: Some("independent-binding-fixture".into()),
                        control: Some(kind),
                        quality: if selected && stopped {
                            EffectQuality::Opaque
                        } else {
                            EffectQuality::ExternalLifted
                        },
                        undefined_flags: LocationSet::new(),
                        decoder_record: selected.then(|| raw_record(row)),
                        decoded_address: receipt,
                        decoder_control: Some(if selected {
                            InstructionKind::Ordinary
                        } else {
                            InstructionKind::Return
                        }),
                        semantic: Some(SemanticEvidence {
                            backend: "bap-x86-legacy".into(),
                            helper_sha256: "1".repeat(64),
                            runtime_sha256: "2".repeat(64),
                            ast_sha256: Some("3".repeat(64)),
                            projection: "bap-bit-provenance-v6".into(),
                            status: if selected && isolated_prefix {
                                "decode-disagreement"
                            } else if selected && unsupported_address {
                                "opaque-unsupported"
                            } else {
                                "projected"
                            }
                            .into(),
                            fallback: None,
                            gaps: Vec::new(),
                            memory_accesses: if selected && !stopped {
                                vec![MemoryAccessEvidence {
                                    index: 0,
                                    role: if row["decoded_receipt"]["operation"] == 0 {
                                        MemoryAccessRole::Load
                                    } else {
                                        MemoryAccessRole::Store
                                    },
                                    access_width: row["decoded_receipt"]["access_width"]
                                        .as_u64()
                                        .unwrap()
                                        as u16,
                                    address_width: 64,
                                    expression: Some(address.clone()),
                                    address_inputs: inputs.clone(),
                                    attribution: "independent-binding-fixture".into(),
                                    gaps: Vec::new(),
                                }]
                            } else {
                                Vec::new()
                            },
                        }),
                    };
                    if selected {
                        assert_eq!(evidence.bytes, code, "{}", row["name"]);
                        before_seal(&mut evidence);
                    }
                    sites.insert(
                        va,
                        PreparedSite {
                            instruction: Instruction {
                                kind,
                                fall: if selected && !stopped {
                                    [va + length as u64].into()
                                } else {
                                    AddressSet::new()
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
                        decoder: "independent-binding-fixture".into(),
                        protocol: 2,
                        ruleset: "bap-bit-provenance-v6".into(),
                        catalogue: "independent-binding-fixture".into(),
                    },
                })
            },
        )
        .unwrap()
}

fn complete(prepared: &FilePreparedAnalysis) -> CompletedAnalysis {
    CompletedAnalysis::from_analyzer(Analyzer::new(prepared.prepared.request.clone()).unwrap())
}

fn question() -> FaultAddressQuestion {
    FaultAddressQuestion {
        site: SITE,
        memory_access: 0,
    }
}

fn selected(prepared: &mut FilePreparedAnalysis) -> &mut InstructionEvidence {
    prepared.prepared.instructions.get_mut(&SITE).unwrap()
}

fn semantic(prepared: &mut FilePreparedAnalysis) -> &mut SemanticEvidence {
    selected(prepared).semantic.as_mut().unwrap()
}

fn rejected(prepared: &FilePreparedAnalysis, completed: &CompletedAnalysis, label: &str) {
    assert!(
        bind_address_wrap(prepared, completed, question()).is_err(),
        "{label}"
    );
}

#[test]
fn original_publication_and_clone_bind_all_114_raw_inputs() {
    let raw: Value =
        serde_json::from_slice(include_bytes!("fixtures/i5c/raw-corpus.json")).unwrap();
    let rows: Vec<_> = cases()
        .into_iter()
        .filter(|row| row["harness"] == "synthetic-capture")
        .collect();
    assert_eq!(rows.len(), 114);
    for row in rows {
        let prepared = prepare(&row, |_| {});
        let frozen = raw["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|expected| expected["name"] == row["name"])
            .unwrap();
        assert_eq!(
            prepared.snapshot.artifact_sha256,
            frozen["sha256"].as_str().unwrap()
        );
        assert_eq!(
            prepared.snapshot.artifact_bytes as u64,
            frozen["bytes"].as_u64().unwrap()
        );
        let completed = complete(&prepared);
        let bound = bind_address_wrap(&prepared, &completed, question()).unwrap();
        let cloned = prepared.clone();
        assert!(Arc::ptr_eq(
            &prepared.scalar_binding,
            &cloned.scalar_binding
        ));
        let rebound = bind_address_wrap(&cloned, &completed, question()).unwrap();
        assert_eq!(bound.identity(), rebound.identity(), "{}", row["name"]);
        assert_eq!(bound.question(), &question());
    }
}

#[test]
fn original_missing_receipt_and_supplied_bil_disagreement_are_bindable() {
    let row = case("mov32mi-upper");
    let absent = prepare(&row, |site| {
        site.decoder_record = None;
        site.decoded_address = None;
    });
    assert!(bind_address_wrap(&absent, &complete(&absent), question()).is_ok());
    let disagreement = prepare(&row, |site| {
        site.semantic.as_mut().unwrap().memory_accesses[0]
            .expression
            .as_mut()
            .unwrap()
            .constant += 1;
    });
    assert!(bind_address_wrap(&disagreement, &complete(&disagreement), question()).is_ok());
}

#[test]
fn receipt_presence_raw_rows_and_decoder_identity_cannot_change_after_publication() {
    let row = case("mov32mi-upper");
    let original = prepare(&row, |_| {});
    let completed = complete(&original);
    let absent = prepare(&row, |site| {
        site.decoder_record = None;
        site.decoded_address = None;
    });
    let absent_completed = complete(&absent);
    let mut inserted = absent.clone();
    selected(&mut inserted).decoded_address = original.prepared.instructions[&SITE]
        .decoded_address
        .clone();
    selected(&mut inserted).decoder_record =
        original.prepared.instructions[&SITE].decoder_record.clone();
    rejected(&inserted, &absent_completed, "None to coherent Some");
    let mut raw_inserted = absent.clone();
    selected(&mut raw_inserted).decoder_record =
        original.prepared.instructions[&SITE].decoder_record.clone();
    rejected(&raw_inserted, &absent_completed, "raw None to Some");

    for mutation in 0..6 {
        let mut changed = original.clone();
        let site = selected(&mut changed);
        match mutation {
            0 => site.decoded_address = None,
            1 => site.decoder_record = None,
            2 => site.decoded_address.as_mut().unwrap().decoder_sha256 = None,
            3 => site.decoded_address.as_mut().unwrap().decoder_sha256 = Some("5".repeat(64)),
            4 => {
                let receipt = site.decoded_address.as_mut().unwrap();
                receipt.raw_record = receipt.raw_record.replace("i:5 ", "i:6 ");
                receipt.validate().unwrap();
                site.decoder_record = Some(receipt.raw_record.clone());
            }
            _ => {
                site.decoded_address = None;
                site.decoder_record = None;
            }
        }
        rejected(
            &changed,
            &completed,
            "post-publication receipt or raw substitution",
        );
    }
    assert!(bind_address_wrap(&original, &completed, question()).is_ok());
}

#[test]
fn an_original_internally_mismatched_receipt_still_fails_binding() {
    let prepared = prepare(&case("mov32mi-upper"), |site| {
        site.decoder_record = None;
    });
    rejected(
        &prepared,
        &complete(&prepared),
        "original row/receipt mismatch",
    );
}

#[test]
fn all_published_instruction_and_semantic_facts_are_sealed() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let completed = complete(&prepared);
    type Mutation = (&'static str, fn(&mut FilePreparedAnalysis));
    let mutations: &[Mutation] = &[
        ("bytes", |p| selected(p).bytes[0] ^= 1),
        ("source", |p| selected(p).source = ByteSource::File),
        ("opcode", |p| selected(p).opcode = Some("MOV64mi32".into())),
        ("length", |p| selected(p).length += 1),
        ("operands", |p| {
            selected(p).operands.push(Operand::Condition(0))
        }),
        ("rule", |p| selected(p).rule = None),
        ("control", |p| {
            selected(p).control = Some(InstructionKind::Stop)
        }),
        ("quality", |p| selected(p).quality = EffectQuality::Opaque),
        ("undefined", |p| {
            selected(p).undefined_flags.insert("flag:cf".into());
        }),
        ("decoder control", |p| selected(p).decoder_control = None),
        ("semantic absence", |p| selected(p).semantic = None),
        ("backend", |p| semantic(p).backend = "other-backend".into()),
        ("helper", |p| semantic(p).helper_sha256 = "6".repeat(64)),
        ("runtime", |p| semantic(p).runtime_sha256 = "7".repeat(64)),
        ("projection", |p| {
            semantic(p).projection = "bap-bit-provenance-v5".into()
        }),
        ("status", |p| {
            semantic(p).status = "opaque-unsupported".into()
        }),
        ("AST", |p| semantic(p).ast_sha256 = Some("8".repeat(64))),
        ("fallback", |p| {
            semantic(p).fallback = Some("forbidden".into())
        }),
        ("semantic gaps", |p| semantic(p).gaps.push("new-gap".into())),
        ("access", |p| semantic(p).memory_accesses.clear()),
        ("access expression", |p| {
            semantic(p).memory_accesses[0]
                .expression
                .as_mut()
                .unwrap()
                .constant += 1;
        }),
        ("unselected tool", |p| {
            p.prepared
                .instructions
                .get_mut(&NEXT)
                .unwrap()
                .semantic
                .as_mut()
                .unwrap()
                .helper_sha256 = "9".repeat(64);
        }),
        ("instruction removal", |p| {
            p.prepared.instructions.remove(&NEXT);
        }),
        ("instruction insertion", |p| {
            let extra = p.prepared.instructions[&NEXT].clone();
            p.prepared.instructions.insert(NEXT + 1, extra);
        }),
        ("preparation gaps", |p| {
            p.prepared.gaps.push(PreparationGap {
                address: NEXT,
                reason: crate::effects::GapReason::OpaqueEffects,
            })
        }),
    ];
    for (name, mutate) in mutations {
        let mut changed = prepared.clone();
        mutate(&mut changed);
        rejected(&changed, &completed, name);
    }
}

#[test]
fn complete_read_provenance_and_stops_are_sealed() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let completed = complete(&prepared);
    for mutation in 0..10 {
        let mut changed = prepared.clone();
        match mutation {
            0 => changed.reads.get_mut(&SITE).unwrap().bytes[0] ^= 1,
            1 => changed.reads.get_mut(&SITE).unwrap().spans[0].address += 1,
            2 => changed.reads.get_mut(&SITE).unwrap().spans[0].length += 1,
            3 => changed.reads.get_mut(&SITE).unwrap().spans[0].contributors[0].stream += 1,
            4 => changed.reads.get_mut(&SITE).unwrap().spans[0].contributors[0].entry += 1,
            5 => changed.reads.get_mut(&SITE).unwrap().spans[0].contributors[0].file_offset += 1,
            6 => changed.reads.get_mut(&SITE).unwrap().stop = ReadStop::AddressOverflow,
            7 => {
                let source = changed.reads[&SITE].spans[0].contributors[0].clone();
                changed
                    .reads
                    .get_mut(&SITE)
                    .unwrap()
                    .conflict_sources
                    .push(source);
            }
            8 => {
                changed.reads.remove(&NEXT);
            }
            _ => {
                let extra = changed.reads[&NEXT].clone();
                changed.reads.insert(NEXT + 1, extra);
            }
        }
        rejected(&changed, &completed, "captured read substitution");
    }
}

#[test]
fn preparation_identity_limits_and_report_are_sealed() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let completed = complete(&prepared);
    type Mutation = (&'static str, fn(&mut FilePreparedAnalysis));
    let mutations: &[Mutation] = &[
        ("target", |p| {
            p.prepared.identity.target = "other-target".into()
        }),
        ("decoder", |p| {
            p.prepared.identity.decoder = "other-decoder".into()
        }),
        ("protocol", |p| p.prepared.identity.protocol += 1),
        ("ruleset", |p| {
            p.prepared.identity.ruleset = "other-rules".into()
        }),
        ("catalogue", |p| {
            p.prepared.identity.catalogue = "other-catalogue".into()
        }),
        ("entry report", |p| {
            p.materialization.entry_points.insert(NEXT);
        }),
        ("seed report", |p| p.materialization.slice_seeds.clear()),
        ("starts limit", |p| p.materialization.limits.max_starts += 1),
        ("candidates limit", |p| {
            p.materialization.limits.max_candidates += 1
        }),
        ("prefix limit", |p| {
            p.materialization.limits.max_prefix_bytes += 1
        }),
        ("batch limit", |p| {
            p.materialization.limits.max_decoder_batches += 1
        }),
        ("batch size", |p| p.materialization.limits.batch_size += 1),
        ("attempted", |p| p.materialization.attempted.clear()),
        ("referenced", |p| p.materialization.referenced.clear()),
        ("unattempted", |p| {
            p.materialization.unattempted_references.insert(NEXT);
        }),
        ("prefix bytes", |p| p.materialization.prefix_bytes += 1),
        ("batches", |p| p.materialization.decoder_batches += 1),
        ("overlaps", |p| {
            p.materialization.overlapping_starts.insert((SITE, NEXT));
        }),
        ("query identity", |p| {
            p.materialization.query_identity = "a".repeat(64)
        }),
        ("file limit", |p| p.open_limits.max_file_bytes += 1),
        ("stream limit", |p| p.open_limits.max_streams += 1),
        ("record limit", |p| p.open_limits.max_records += 1),
        ("metadata limit", |p| p.open_limits.max_metadata_bytes += 1),
        ("capture limit", |p| p.open_limits.max_capture_ranges += 1),
        ("overlap limit", |p| p.open_limits.max_overlap += 1),
        ("read limit", |p| p.open_limits.max_read_bytes += 1),
    ];
    for (name, mutate) in mutations {
        let mut changed = prepared.clone();
        mutate(&mut changed);
        rejected(&changed, &completed, name);
    }
}

#[test]
fn a_new_matching_analyzer_cannot_authorize_a_replaced_request() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let mut changed = prepared.clone();
    let location = changed
        .prepared
        .request
        .locations
        .iter()
        .next()
        .unwrap()
        .clone();
    changed
        .prepared
        .request
        .instructions
        .get_mut(&NEXT)
        .unwrap()
        .uses
        .insert(location);
    let new_completed = complete(&changed);
    rejected(
        &changed,
        &new_completed,
        "coherent request/new analyzer substitution",
    );

    let mut changed = prepared.clone();
    changed.prepared.request.slice_seeds = [NEXT].into();
    changed.materialization.slice_seeds = [NEXT].into();
    changed.materialization.query_identity = query_identity(
        &changed.prepared.request.snapshot_id,
        &AnalysisQuery {
            entry_points: changed.materialization.entry_points.clone(),
            slice_seeds: changed.materialization.slice_seeds.clone(),
        },
        &changed.materialization.limits,
        None,
    )
    .unwrap();
    rejected(&changed, &complete(&changed), "coherent replacement query");
}

#[test]
fn private_coherent_fault_substitutions_and_global_metadata_are_rejected() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let completed = complete(&prepared);
    let mut changed = prepared.clone();
    Arc::make_mut(&mut changed.snapshot).gaps.push(MetadataGap {
        stream: 0,
        entry: None,
        reason: "substituted metadata".into(),
    });
    Arc::make_mut(&mut changed.fault).metadata = changed.snapshot.clone();
    rejected(
        &changed,
        &completed,
        "coherent snapshot and private metadata substitution",
    );

    let mut changed = prepared.clone();
    let fault = Arc::make_mut(&mut changed.fault);
    let observation = fault
        .evidence
        .data
        .iter_mut()
        .find_map(|datum| match datum {
            FaultDatum::Field { observation } if observation.name == "reg:rax" => Some(observation),
            _ => None,
        })
        .unwrap();
    observation.value = 8;
    let replacement = observation.value.to_le_bytes();
    observation.bytes_hex = replacement
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    observation.source.sha256 = crate::reports::sha256(&replacement);
    fault.evidence.validate(true).unwrap();
    rejected(
        &changed,
        &completed,
        "coherent private fault field replacement",
    );

    let mut changed = prepared.clone();
    Arc::make_mut(&mut changed.fault)
        .evidence
        .metadata
        .gaps
        .push("new-gap".into());
    changed.fault.evidence.validate(true).unwrap();
    rejected(&changed, &completed, "private fault metadata replacement");
}

#[test]
fn question_and_completed_analysis_checks_remain_required() {
    let prepared = prepare(&case("mov32mi-upper"), |_| {});
    let incomplete = Analyzer::new(prepared.prepared.request.clone()).unwrap();
    assert!(bind_address_wrap(&prepared, &incomplete, question()).is_err());
    let completed = complete(&prepared);
    for question in [
        FaultAddressQuestion {
            site: SITE + 1,
            memory_access: 0,
        },
        FaultAddressQuestion {
            site: SITE,
            memory_access: 1,
        },
    ] {
        assert!(bind_address_wrap(&prepared, &completed, question).is_err());
    }
}

/// The W0 partition is fixed: 114 physical raw captures and these 26 supplied
/// typed-evidence cases. None of these names denotes an extra native capture.
pub(crate) const SUPPLIED_UNIT_CASES: [&str; 26] = [
    "rip-relative",
    "multiple-access",
    "missing-decoded-receipt",
    "decoder-bap-base-disagreement",
    "decoder-bap-constant-disagreement",
    "decoder-bap-width-disagreement",
    "missing-decoder-identity",
    "different-decoder-target",
    "site-not-reached",
    "unadmitted-semantics",
    "budget-e0-c64",
    "budget-e1-c64",
    "budget-e31-c64",
    "budget-e32-c64",
    "budget-e33-c64",
    "budget-e34-c64",
    "budget-e64-c0",
    "budget-e64-c30",
    "budget-e64-c35",
    "budget-e64-c36",
    "budget-e64-c37",
    "budget-e0-c0",
    "budget-max-bundle-e45-c64",
    "budget-max-bundle-e46-c49",
    "budget-max-bundle-e64-c48",
    "budget-max-bundle-e64-c49",
];

pub(crate) fn oracle_limits(row: &Value) -> AddressWrapLimits {
    AddressWrapLimits {
        max_evidence: row["max_evidence"].as_u64().unwrap() as usize,
        max_claims: row["max_claims"].as_u64().unwrap() as usize,
    }
}

pub(crate) fn hex_value(value: &Value) -> u64 {
    u64::from_str_radix(value.as_str().unwrap().strip_prefix("0x").unwrap(), 16).unwrap()
}

pub(crate) fn checked_frozen_inventory() -> BTreeSet<String> {
    let manifest_bytes = include_bytes!("fixtures/i5c/manifest.json");
    let raw_bytes = include_bytes!("fixtures/i5c/raw-corpus.json");
    assert_eq!(
        crate::reports::sha256(manifest_bytes),
        "8d13a87e8f443328a4994cfdc0596d0098cb1f8c4508e4ffd67f91f0ffc0e0ae"
    );
    assert_eq!(
        crate::reports::sha256(raw_bytes),
        "af59912c7475d9b4c1e341604fb92e1fc30f7a19f0f267c39424b231c2cd2325"
    );
    let manifest: Value = serde_json::from_slice(manifest_bytes).unwrap();
    assert_eq!(manifest["decision_case_count"], 140);
    assert_eq!(manifest["form_grid_count"], 66);
    assert_eq!(manifest["boundary_count"], 20);
    assert_eq!(manifest["negative_capture_count"], 30);
    assert_eq!(manifest["adapter_case_count"], 8);
    assert_eq!(manifest["budget_case_count"], 16);
    assert_eq!(
        manifest["gap_policy"],
        "required_gaps are a minimum mandatory subset, not an exact inherited gap list"
    );
    let rows = cases();
    let names: BTreeSet<_> = rows
        .iter()
        .map(|row| row["name"].as_str().unwrap().to_string())
        .collect();
    assert_eq!(rows.len(), 140);
    assert_eq!(names.len(), 140, "duplicate frozen decision name");
    let raw: Value = serde_json::from_slice(raw_bytes).unwrap();
    let raw_names: BTreeSet<_> = raw["cases"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| row["name"].as_str().unwrap().to_string())
        .collect();
    assert_eq!(raw["cases"].as_array().unwrap().len(), 114);
    assert_eq!(raw_names.len(), 114);
    let dump_root =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/input/fixtures/i5c/dumps");
    let actual_files: BTreeSet<_> = std::fs::read_dir(&dump_root)
        .unwrap()
        .map(|entry| {
            let entry = entry.unwrap();
            assert!(
                entry.file_type().unwrap().is_file(),
                "raw corpus contains a non-file entry"
            );
            entry.file_name().into_string().unwrap()
        })
        .collect();
    let expected_files: BTreeSet<_> = raw_names
        .iter()
        .map(|name| format!("{name}.dmp"))
        .chain(["manifest.json".into()])
        .collect();
    assert_eq!(actual_files, expected_files, "raw corpus file closure");
    let materialized: Value =
        serde_json::from_slice(&std::fs::read(dump_root.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(
        materialized["cases"], raw["cases"],
        "raw corpus materialization manifest"
    );
    let supplied_names: BTreeSet<_> = SUPPLIED_UNIT_CASES
        .into_iter()
        .map(str::to_string)
        .collect();
    assert_eq!(supplied_names.len(), 26);
    assert!(raw_names.is_disjoint(&supplied_names));
    assert_eq!(
        raw_names
            .union(&supplied_names)
            .cloned()
            .collect::<BTreeSet<_>>(),
        names
    );
    for row in &rows {
        let name = row["name"].as_str().unwrap();
        assert_eq!(
            row["harness"],
            if raw_names.contains(name) {
                "synthetic-capture"
            } else {
                "bound-unit"
            }
        );
    }
    for form in [
        "mov32mi",
        "mov64mi32",
        "mov32rm",
        "mov64rm",
        "mov32mr",
        "mov64mr",
    ] {
        for boundary in [
            "upper",
            "upper-boundary",
            "ordinary-positive",
            "no-displacement",
            "negative-zero",
            "negative-nonzero",
            "underflow",
            "disp8-min",
            "disp8-max",
            "disp32-min",
            "disp32-max",
        ] {
            assert!(raw_names.contains(&format!("{form}-{boundary}")));
        }
    }
    names
}

/// Private test support: obtain only an exact named raw fixture through the
/// public reader/binder. The supplied-unit module constructs its own new typed
/// context from a fixture shape; it does not submit changed captures to binding.
pub(crate) fn bound_raw_fixture(name: &str) -> BoundAddressWrapContext {
    let row = case(name);
    assert_eq!(row["harness"], "synthetic-capture");
    let prepared = prepare(&row, |_| {});
    let raw: Value =
        serde_json::from_slice(include_bytes!("fixtures/i5c/raw-corpus.json")).unwrap();
    let entry = raw["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|entry| entry["name"] == name)
        .unwrap();
    assert_eq!(
        prepared.snapshot.artifact_sha256,
        entry["sha256"].as_str().unwrap()
    );
    assert_eq!(
        prepared.snapshot.artifact_bytes as u64,
        entry["bytes"].as_u64().unwrap()
    );
    let completed = complete(&prepared);
    bind_address_wrap(&prepared, &completed, question()).unwrap()
}

fn evidence_label(data: &AddressWrapEvidenceData) -> String {
    match data {
        AddressWrapEvidenceData::Instruction { .. } => "instruction".into(),
        AddressWrapEvidenceData::DecodedAddress { .. } => "receipt".into(),
        AddressWrapEvidenceData::Fault { datum } => match datum {
            FaultDatum::Record { .. } => "record".into(),
            FaultDatum::Context { .. } => "context".into(),
            FaultDatum::Field { observation } => observation.name.clone(),
        },
    }
}

pub(crate) fn assert_frozen_assessment(result: &AddressWrapAssessment, row: &Value) {
    let name = row["name"].as_str().unwrap();
    let expected = &row["expected"];
    let limits = oracle_limits(row);
    assert_eq!(
        result.schema, "ariadne.address-wrap-assessment/v1",
        "{name}"
    );
    assert_eq!(result.limits, limits, "{name}");
    assert_eq!(
        serde_json::to_value(result.conclusion).unwrap(),
        expected["conclusion"],
        "{name}"
    );
    assert_eq!(
        result.input_evidence_count,
        expected["input_evidence_count"].as_u64().unwrap() as usize,
        "{name}"
    );
    assert_eq!(
        result.evidence.len(),
        expected["retained_evidence_count"].as_u64().unwrap() as usize,
        "{name}"
    );
    assert_eq!(
        result.claims.len(),
        expected["retained_claims"].as_u64().unwrap() as usize,
        "{name}"
    );
    assert_eq!(
        result.inputs_complete,
        expected["inputs_complete"].as_bool().unwrap(),
        "{name}"
    );
    assert_eq!(
        result.truncated,
        expected["truncated"].as_bool().unwrap(),
        "{name}"
    );
    assert!(
        result.gaps.windows(2).all(|pair| pair[0] < pair[1]),
        "{name}: canonical gaps"
    );
    for gap in expected["required_gaps"].as_array().unwrap() {
        assert!(
            result
                .gaps
                .iter()
                .any(|actual| actual == gap.as_str().unwrap()),
            "{name}: missing required {gap}"
        );
    }
    let mut order = vec!["instruction".to_string()];
    if row["exception_present"].as_bool().unwrap() {
        order.push("record".into());
        if row["context_present"].as_bool().unwrap() {
            order.push("context".into());
        }
        order.extend(
            [
                "thread_id",
                "code",
                "flags",
                "chain",
                "exception_location",
                "number_parameters",
                "context_size",
                "context_offset",
            ]
            .map(str::to_string),
        );
        order.extend(
            (0..row["parameter_count"].as_u64().unwrap()).map(|index| format!("parameter:{index}")),
        );
        if row["context_present"].as_bool().unwrap() {
            order.push("context_flags".into());
            if row["context_supported"].as_bool().unwrap() {
                let flags = row["context_flags"].as_u64().unwrap();
                for register in BANKS.into_iter().chain(["rip", "rflags"]) {
                    let group = if ["rsp", "rip", "rflags"].contains(&register) {
                        1
                    } else {
                        2
                    };
                    if flags & group != 0 {
                        order.push(format!("reg:{register}"));
                    }
                }
            }
        }
    }
    if row["receipt"].as_bool().unwrap() {
        order.push("receipt".into());
    }
    assert_eq!(
        order.len(),
        result.input_evidence_count,
        "{name}: full publication order"
    );
    order.truncate(limits.max_evidence);
    assert_eq!(
        result
            .evidence
            .iter()
            .map(|e| evidence_label(&e.data))
            .collect::<Vec<_>>(),
        order,
        "{name}: retained publication prefix"
    );

    let mut derived = Vec::new();
    if expected["arithmetic"].is_null() {
        assert!(
            result.arithmetic.is_none(),
            "{name}: arithmetic crossed readiness/budget boundary"
        );
    } else {
        let arithmetic = &expected["arithmetic"];
        let wrap_kind = match arithmetic["wrap_kind"].as_str().unwrap() {
            "none" => AddressWrapKind::None,
            "upper" => AddressWrapKind::Upper,
            "lower" => AddressWrapKind::Lower,
            other => panic!("unknown frozen wrap kind {other}"),
        };
        let expected_arithmetic = AddressWrapArithmetic {
            base_register: arithmetic["base_register"].as_str().unwrap().into(),
            base_value: crate::investigation::AssessedValue {
                value: hex_value(&arithmetic["base_value"]),
            },
            signed_displacement: arithmetic["signed_displacement"].as_i64().unwrap(),
            displacement_bits: crate::investigation::AssessedValue {
                value: hex_value(&arithmetic["displacement_bits"]),
            },
            sum_before_reduction: arithmetic["sum_before_reduction"].as_str().unwrap().into(),
            wrap_kind,
            effective_address: crate::investigation::AssessedValue {
                value: hex_value(&arithmetic["effective_address"]),
            },
        };
        assert_eq!(
            result.arithmetic.as_ref(),
            Some(&expected_arithmetic),
            "{name}"
        );
        derived.extend([
            AddressWrapAssertion::DecodedBase {
                register: expected_arithmetic.base_register.clone(),
                displacement: expected_arithmetic.signed_displacement,
            },
            AddressWrapAssertion::CapturedBase {
                register: expected_arithmetic.base_register,
                value: expected_arithmetic.base_value.value,
            },
            AddressWrapAssertion::WideSum {
                sum_before_reduction: expected_arithmetic.sum_before_reduction,
            },
            AddressWrapAssertion::WrapKind { wrap_kind },
            AddressWrapAssertion::ComputedAddress {
                value: expected_arithmetic.effective_address.value,
            },
        ]);
    }
    let observed: Vec<_> = result
        .evidence
        .iter()
        .filter_map(|e| {
            let assertion = match &e.data {
                AddressWrapEvidenceData::Instruction { instruction, .. }
                    if instruction.captured && !instruction.bytes_hex.is_empty() =>
                {
                    AddressWrapAssertion::CapturedInstruction {
                        site: instruction.va,
                    }
                }
                AddressWrapEvidenceData::Fault {
                    datum: FaultDatum::Field { observation },
                } => AddressWrapAssertion::CapturedField {
                    name: observation.name.clone(),
                    value: observation.value,
                },
                _ => return None,
            };
            Some((assertion, vec![e.id.clone()]))
        })
        .collect();
    assert_eq!(
        observed.len(),
        expected["observed_claims"].as_u64().unwrap() as usize,
        "{name}"
    );
    let observed_count = observed.len().min(limits.max_claims);
    for (claim, (assertion, references)) in result.claims.iter().zip(observed).take(observed_count)
    {
        assert_eq!(claim.assertion, assertion, "{name}");
        assert_eq!(claim.classification, Classification::Observed, "{name}");
        assert_eq!(claim.evidence_refs, references, "{name}");
        assert!(claim.premises.is_empty(), "{name}");
    }
    let all_refs: Vec<_> = result.evidence.iter().map(|e| e.id.clone()).collect();
    let tail = &result.claims[observed_count..];
    assert!(
        tail.len() >= derived.len(),
        "{name}: partial arithmetic bundle"
    );
    for (claim, assertion) in tail.iter().zip(&derived) {
        assert_eq!(&claim.assertion, assertion, "{name}");
        assert_eq!(
            claim.classification,
            Classification::DerivedUnderPremises,
            "{name}"
        );
        assert_eq!(claim.premises, result.premises, "{name}");
        assert_eq!(claim.evidence_refs, all_refs, "{name}");
    }
    let assessment = &tail[derived.len()..];
    assert!(assessment.len() <= 1, "{name}: unaccounted claim");
    assert_eq!(
        assessment.len(),
        usize::from(observed_count + derived.len() < limits.max_claims),
        "{name}: final assessment slot"
    );
    if let Some(claim) = assessment.first() {
        assert_eq!(
            claim.assertion,
            AddressWrapAssertion::Assessment {
                conclusion: result.conclusion
            },
            "{name}"
        );
        let classification = if result.conclusion == ZeroAddressConclusion::Unknown {
            Classification::Unknown
        } else {
            Classification::DerivedUnderPremises
        };
        assert_eq!(claim.classification, classification, "{name}");
        assert_eq!(claim.evidence_refs, all_refs, "{name}");
        if classification == Classification::Unknown {
            assert!(claim.premises.is_empty(), "{name}");
        } else {
            assert_eq!(claim.premises, result.premises, "{name}");
        }
    }
    assert_eq!(
        result
            .evidence
            .iter()
            .map(|e| &e.id)
            .collect::<BTreeSet<_>>()
            .len(),
        result.evidence.len(),
        "{name}: duplicate evidence IDs"
    );
    assert_eq!(
        result
            .claims
            .iter()
            .map(|c| &c.id)
            .collect::<BTreeSet<_>>()
            .len(),
        result.claims.len(),
        "{name}: duplicate claim IDs"
    );
    result.validate().unwrap();
}

#[test]
fn w3_all_114_raw_capture_decisions_match_the_frozen_oracle() {
    let all_names = checked_frozen_inventory();
    let mut exercised = BTreeSet::new();
    for row in cases()
        .into_iter()
        .filter(|row| row["harness"] == "synthetic-capture")
    {
        let name = row["name"].as_str().unwrap();
        let bound = bound_raw_fixture(name);
        let result = assess_address_wrap(&bound, oracle_limits(&row)).unwrap();
        assert_frozen_assessment(&result, &row);
        assert_eq!(
            assess_address_wrap(&bound, oracle_limits(&row)).unwrap(),
            result,
            "{name}: deterministic repeated assessment"
        );
        assert!(exercised.insert(name.to_string()));
        println!(
            "I5C_W3_DECISION {}",
            serde_json::json!({"name": name, "tier": "raw-capture-supplied-preparation", "passed": true, "native_preparation": false})
        );
    }
    let supplied: BTreeSet<_> = SUPPLIED_UNIT_CASES
        .into_iter()
        .map(str::to_string)
        .collect();
    assert_eq!(exercised.len(), 114);
    assert!(exercised.is_disjoint(&supplied));
    assert_eq!(
        exercised.union(&supplied).cloned().collect::<BTreeSet<_>>(),
        all_names
    );
}

fn changed_fault_field<'a>(
    prepared: &'a mut FilePreparedAnalysis,
    name: &str,
) -> &'a mut crate::investigation::FaultObservation {
    Arc::make_mut(&mut prepared.fault)
        .evidence
        .data
        .iter_mut()
        .find_map(|datum| match datum {
            FaultDatum::Field { observation } if observation.name == name => Some(observation),
            _ => None,
        })
        .unwrap()
}

fn set_fault_value(observation: &mut crate::investigation::FaultObservation, value: u64) {
    observation.value = value;
    let representation = value.to_le_bytes();
    let bytes = &representation[..observation.source.length];
    observation.bytes_hex = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
    observation.source.sha256 = crate::reports::sha256(bytes);
}

#[test]
fn w3_frozen_19_binding_controls_with_four_raw_row_variants_reject_before_budgets() {
    let matrix_bytes = include_bytes!("fixtures/i5c/qualification-matrix.json");
    assert_eq!(
        crate::reports::sha256(matrix_bytes),
        "2751fdf2fc407e6b104f29c57f6619cbdbc9d9bb226bdd9c029d16dec4fc2fca"
    );
    let matrix: Value = serde_json::from_slice(matrix_bytes).unwrap();
    let controls = matrix["binding_rejections"].as_array().unwrap();
    assert_eq!(controls.len(), 19);
    let original = prepare(&case("mov32mi-upper"), |_| {});
    let completed = complete(&original);
    let absent = prepare(&case("mov32mi-upper"), |site| {
        site.decoder_record = None;
        site.decoded_address = None;
    });
    let absent_completed = complete(&absent);
    let mut exercised = BTreeSet::new();
    let mut baseline_names = BTreeSet::new();
    for control in controls {
        let name = control["name"].as_str().unwrap();
        assert!(baseline_names.insert(name));
        assert_eq!(control["expected"], "Err before budgets");
        assert_eq!(control["budgets"], serde_json::json!([[64, 64], [0, 0]]));
        let variants: &[&str] = if name == "receipt-raw-row" {
            &[
                "raw-row-substitution",
                "none-to-some",
                "some-to-none",
                "coherent-raw-row-and-receipt-substitution",
            ]
        } else {
            &["baseline"]
        };
        for &variant in variants {
            for limits in [
                AddressWrapLimits::default(),
                AddressWrapLimits {
                    max_evidence: 0,
                    max_claims: 0,
                },
            ] {
                let (seed, completed) = if variant == "none-to-some" {
                    (&absent, &absent_completed)
                } else {
                    (&original, &completed)
                };
                let mut changed = seed.clone();
                let mut selected_question = question();
                match name {
                    "snapshot-id" => {
                        Arc::make_mut(&mut changed.snapshot).snapshot_id =
                            "substituted-snapshot".into()
                    }
                    "artifact-sha256" => {
                        Arc::make_mut(&mut changed.snapshot).artifact_sha256 = "a".repeat(64)
                    }
                    "query-id" => changed.materialization.query_identity = "a".repeat(64),
                    "request-sha256" => {
                        let location = changed
                            .prepared
                            .request
                            .locations
                            .iter()
                            .next()
                            .unwrap()
                            .clone();
                        changed
                            .prepared
                            .request
                            .instructions
                            .get_mut(&NEXT)
                            .unwrap()
                            .uses
                            .insert(location);
                    }
                    "semantic-profile" => {
                        changed.prepared.identity.ruleset = "substituted-ruleset".into()
                    }
                    "mutable-reader-metadata" => {
                        Arc::make_mut(&mut changed.snapshot).gaps.push(MetadataGap {
                            stream: 0,
                            entry: None,
                            reason: "substituted reader metadata".into(),
                        })
                    }
                    "outside-query-site" => selected_question.site += 1,
                    "invalid-access-index" => selected_question.memory_access = 1,
                    "receipt-address" => {
                        selected(&mut changed)
                            .decoded_address
                            .as_mut()
                            .unwrap()
                            .address += 1
                    }
                    "receipt-bytes" => selected(&mut changed)
                        .decoded_address
                        .as_mut()
                        .unwrap()
                        .bytes_hex
                        .replace_range(..2, "90"),
                    "receipt-opcode" => {
                        selected(&mut changed)
                            .decoded_address
                            .as_mut()
                            .unwrap()
                            .opcode = "MOV64mi32".into()
                    }
                    "receipt-length" => {
                        selected(&mut changed)
                            .decoded_address
                            .as_mut()
                            .unwrap()
                            .length += 1
                    }
                    "receipt-decoder-hash" => {
                        selected(&mut changed)
                            .decoded_address
                            .as_mut()
                            .unwrap()
                            .decoder_sha256 = Some("5".repeat(64))
                    }
                    "receipt-raw-row" => match variant {
                        "raw-row-substitution" => {
                            let record = selected(&mut changed).decoder_record.as_mut().unwrap();
                            let replacement = record.replace("i:5 ", "i:6 ");
                            assert_ne!(&replacement, record);
                            *record = replacement;
                        }
                        "none-to-some" => {
                            let replacement = original.prepared.instructions[&SITE]
                                .decoded_address
                                .clone()
                                .unwrap();
                            replacement.validate().unwrap();
                            let site = selected(&mut changed);
                            site.decoder_record = Some(replacement.raw_record.clone());
                            site.decoded_address = Some(replacement);
                        }
                        "some-to-none" => {
                            let site = selected(&mut changed);
                            site.decoded_address = None;
                            site.decoder_record = None;
                        }
                        "coherent-raw-row-and-receipt-substitution" => {
                            let site = selected(&mut changed);
                            let replacement = site.decoded_address.as_mut().unwrap();
                            let old = replacement.raw_record.clone();
                            replacement.raw_record = old.replace("i:5 ", "i:6 ");
                            assert_ne!(replacement.raw_record, old);
                            replacement.validate().unwrap();
                            assert_eq!(replacement.address, SITE);
                            assert_eq!(
                                replacement.bytes_hex,
                                case("mov32mi-upper")["code"].as_str().unwrap()
                            );
                            assert_eq!(replacement.length, 7);
                            assert_eq!(replacement.opcode, "MOV32mi");
                            site.decoder_record = Some(replacement.raw_record.clone());
                        }
                        _ => panic!("unaccounted raw-row control {variant}"),
                    },
                    "fault-field-bytes" => changed_fault_field(&mut changed, "reg:rax")
                        .bytes_hex
                        .replace_range(..2, "00"),
                    "fault-span-hash" => {
                        changed_fault_field(&mut changed, "reg:rax").source.sha256 = "a".repeat(64)
                    }
                    "duplicate-fault-field" => {
                        let duplicate = Arc::make_mut(&mut changed.fault).evidence.data.iter().find(|datum| matches!(datum, FaultDatum::Field { observation } if observation.name == "reg:rax")).unwrap().clone();
                        Arc::make_mut(&mut changed.fault)
                            .evidence
                            .data
                            .push(duplicate);
                    }
                    "invalid-context-validity-claim" => {
                        let observation = changed_fault_field(&mut changed, "context_flags");
                        let flags = observation.value & !2;
                        set_fault_value(observation, flags);
                    }
                    "invalid-parameter-count" => {
                        set_fault_value(changed_fault_field(&mut changed, "number_parameters"), 16)
                    }
                    _ => panic!("unimplemented frozen binding control {name}"),
                }
                let mut assessor_invoked = false;
                let result =
                    bind_address_wrap(&changed, completed, selected_question).and_then(|bound| {
                        assessor_invoked = true;
                        assess_address_wrap(&bound, limits)
                    });
                assert!(
                    result.is_err(),
                    "{name}/{variant}: Unknown is not a binding rejection"
                );
                assert!(
                    !assessor_invoked,
                    "{name}/{variant}: binding failure reached output budgets"
                );
                assert!(exercised.insert((name, variant, limits.max_evidence, limits.max_claims)));
                println!(
                    "I5C_W3_BINDING {}",
                    serde_json::json!({"baseline_name": name, "variant": variant, "max_evidence": limits.max_evidence, "max_claims": limits.max_claims, "assessor_invoked": false, "passed": true})
                );
            }
        }
    }
    assert_eq!(baseline_names.len(), 19);
    // Frozen 19 × 2 = 38, replacing one 2-run row with four 2-run variants.
    assert_eq!(exercised.len(), 38 - 2 + 8);
}

#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime; explicitly qualify all 114 captures remotely"]
fn w3_native_preparation_and_completed_analysis_match_all_114_raw_decisions() {
    use crate::bap::core_adapter::NativeAnalyzer;
    use crate::bap::core_session::CoreConfig;

    let all_names = checked_frozen_inventory();
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/ariadne-llvm-mc"));
    let core = std::env::var_os("ARIADNE_BAP_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/qualification-native"));
    let raw: Value =
        serde_json::from_slice(include_bytes!("fixtures/i5c/raw-corpus.json")).unwrap();
    let mut exercised = BTreeSet::new();
    for row in cases()
        .into_iter()
        .filter(|row| row["harness"] == "synthetic-capture")
    {
        let name = row["name"].as_str().unwrap();
        println!("I5C_W3_NATIVE_START {name}");
        let snapshot = FileSnapshot::open_minidump(
            root.join("tests/input/fixtures/i5c/dumps")
                .join(format!("{name}.dmp")),
            OpenLimits::default(),
        )
        .unwrap();
        let frozen = raw["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|entry| entry["name"] == name)
            .unwrap();
        assert_eq!(
            snapshot.metadata().artifact_sha256,
            frozen["sha256"].as_str().unwrap(),
            "{name}"
        );
        assert_eq!(
            snapshot.metadata().artifact_bytes as u64,
            frozen["bytes"].as_u64().unwrap(),
            "{name}"
        );
        let prepared = snapshot
            .prepare(
                &AnalysisQuery {
                    entry_points: [SITE].into(),
                    slice_seeds: [SITE].into(),
                },
                &decoder,
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap_or_else(|error| panic!("{name}: native preparation failed: {error}"));
        let completed = NativeAnalyzer::from_capture(
            &CoreConfig::from_directory(core.clone()),
            "minidump-analysis",
            &prepared,
        )
        .unwrap_or_else(|error| panic!("{name}: native analyzer initialization failed: {error}"))
        .complete()
        .unwrap_or_else(|error| panic!("{name}: native completion failed: {error}"));
        let bound = bind_address_wrap(&prepared, &completed, question())
            .unwrap_or_else(|error| panic!("{name}: native capture binding failed: {error}"));
        let result = assess_address_wrap(&bound, oracle_limits(&row))
            .unwrap_or_else(|error| panic!("{name}: native-bound assessment failed: {error}"));
        assert_frozen_assessment(&result, &row);
        assert!(exercised.insert(name.to_string()));
        println!(
            "I5C_W3_NATIVE_DECISION {}",
            serde_json::json!({"name": name, "tier": "native-raw-capture", "passed": true, "native_preparation": true, "native_completed_analysis": true})
        );
    }
    let supplied: BTreeSet<_> = SUPPLIED_UNIT_CASES
        .into_iter()
        .map(str::to_string)
        .collect();
    assert_eq!(exercised.len(), 114);
    assert!(exercised.is_disjoint(&supplied));
    assert_eq!(
        exercised.union(&supplied).cloned().collect::<BTreeSet<_>>(),
        all_names
    );
}
