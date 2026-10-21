//! W3's 26 explicitly supplied typed-evidence cases. This module is compiled
//! privately inside the assessor under cfg(test, feature = "input"). It creates
//! a new named unit snapshot and checked bound context before assessment; it
//! never asks the public capture binder to accept post-publication changes.
//! No row here contributes native or 114-raw-capture preparation credit.
use super::*;
use crate::effects::{MemoryAccessEvidence, MemoryAccessRole};
use crate::input::address_wrap_binding_tests::{
    SUPPLIED_UNIT_CASES, assert_frozen_assessment, bound_raw_fixture, bytes, case,
    checked_frozen_inventory, expression, hex_value, independent_receipt, oracle_limits,
};
use crate::investigation::{AddressUse, BoundInvestigation, FaultObservation};
use crate::{Analyzer, CompletedAnalysis, InstructionKind};
use serde_json::Value;
use std::path::PathBuf;

const SITE: u64 = 0x401000;
const NEXT: u64 = SITE + 7;

fn write_observation(source: &mut [u8], observation: &mut FaultObservation, value: u64) {
    let offset = observation.source.file_offset as usize;
    let end = offset + observation.source.length;
    let representation = value.to_le_bytes();
    source[offset..end].copy_from_slice(&representation[..observation.source.length]);
    observation.value = value;
    observation.bytes_hex = source[offset..end]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    observation.source.sha256 = sha(&source[offset..end]);
}

/// Produce a coherent new in-memory byte source for record/context/site facts.
/// The original raw artifact is used only for bounded layout and source-span
/// templates. Its identity is never attached to changed bytes.
fn supplied_fault_source(
    row: &Value,
    fault: &mut CapturedFaultContext,
    site: &mut SiteEvidence,
) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures/i5c/dumps/mov32mi-upper.dmp");
    let mut source = std::fs::read(path).unwrap();
    assert_eq!(sha(&source), fault.metadata.artifact_sha256);
    let code = bytes(row["code"].as_str().unwrap());
    // Every supplied case is the seven-byte upper form or the exact seven-byte
    // RIP-relative form. The retained source span covers the complete selection.
    assert_eq!(code.len(), 7);
    let span = site
        .spans
        .iter()
        .find(|span| span.va <= SITE && span.va + span.length as u64 >= SITE + code.len() as u64)
        .unwrap();
    assert_eq!(span.contributors.len(), 1);
    let offset = (span.contributors[0].file_offset + SITE - span.va) as usize;
    source[offset..offset + code.len()].copy_from_slice(&code);
    site.bytes_hex = row["code"].as_str().unwrap().into();
    site.opcode = Some(row["opcode"].as_str().unwrap().into());

    let parameters = row["parameter_count"].as_u64().unwrap();
    assert!([2, 15].contains(&parameters));
    if parameters == 15 {
        let template = fault
            .data
            .iter()
            .find_map(|datum| match datum {
                FaultDatum::Field { observation } if observation.name == "parameter:0" => {
                    Some(observation.clone())
                }
                _ => None,
            })
            .unwrap();
        let insertion = fault.data.iter().position(|datum| matches!(datum, FaultDatum::Field { observation } if observation.name == "context_flags")).unwrap();
        let additional = (2..15)
            .map(|index| {
                let mut observation = template.clone();
                observation.name = format!("parameter:{index}");
                observation.source.file_offset += index * 8;
                write_observation(&mut source, &mut observation, 0);
                FaultDatum::Field { observation }
            })
            .collect::<Vec<_>>();
        fault.data.splice(insertion..insertion, additional);
    }
    for datum in &mut fault.data {
        if let FaultDatum::Field { observation } = datum {
            let value = match observation.name.as_str() {
                "number_parameters" => parameters,
                "parameter:0" => row["operation"].as_u64().unwrap(),
                "parameter:1" => hex_value(&row["reported"]),
                "context_flags" => row["context_flags"].as_u64().unwrap(),
                name if name.starts_with("reg:") && row["registers"].get(&name[4..]).is_some() => {
                    hex_value(&row["registers"][&name[4..]])
                }
                _ => observation.value,
            };
            write_observation(&mut source, observation, value);
        }
    }
    for datum in &mut fault.data {
        let span = match datum {
            FaultDatum::Record { span } | FaultDatum::Context { span } => span,
            FaultDatum::Field { .. } => continue,
        };
        let start = span.file_offset as usize;
        span.sha256 = sha(&source[start..start + span.length]);
    }
    let artifact_sha256 = sha(&source);
    fault.metadata.artifact_sha256 = artifact_sha256.clone();
    fault.metadata.artifact_bytes = source.len() as u64;
    fault.metadata.snapshot_id = format!(
        "i5c-supplied-unit:{}:{artifact_sha256}",
        row["name"].as_str().unwrap()
    );
    fault.validate(true).unwrap();
    artifact_sha256
}

fn supplied_bound_unit(row: &Value) -> BoundAddressWrapContext {
    let name = row["name"].as_str().unwrap();
    assert_eq!(row["harness"], "bound-unit");
    assert!(SUPPLIED_UNIT_CASES.contains(&name));
    let BoundAddressWrapContext { fault: seed, .. } = bound_raw_fixture("mov32mi-upper");
    let mut request = seed.analysis.request;
    let mut context = seed.analysis.context;
    let mut fault = seed.fault;
    let site = context
        .sites
        .iter_mut()
        .find(|site| site.va == SITE)
        .unwrap();
    let artifact_sha256 = supplied_fault_source(row, &mut fault, site);
    let mut address = expression(row);
    if name == "decoder-bap-base-disagreement" {
        address.terms[0].bank = 1;
    }
    if name == "decoder-bap-constant-disagreement" {
        address.constant = address.constant.wrapping_add(1);
    }
    let access = MemoryAccessEvidence {
        index: 0,
        role: if row["decoded_receipt"]["operation"] == 0 {
            MemoryAccessRole::Load
        } else {
            MemoryAccessRole::Store
        },
        access_width: if name == "decoder-bap-width-disagreement" {
            64
        } else {
            row["decoded_receipt"]["access_width"].as_u64().unwrap() as u16
        },
        address_width: 64,
        address_inputs: address.locations(),
        expression: Some(address),
        attribution: "independently-supplied-i5c-unit".into(),
        gaps: Vec::new(),
    };
    site.accesses = vec![AddressUse::from(&access)];
    if name == "multiple-access" {
        let mut additional = site.accesses[0].clone();
        additional.index = 1;
        site.accesses.push(additional);
    }
    let instruction = request.instructions.get_mut(&SITE).unwrap();
    instruction.uses = access.address_inputs;
    request.locations.extend(instruction.uses.iter().cloned());
    if name == "unadmitted-semantics" {
        site.quality = "opaque".into();
        site.semantic_status = Some("opaque-unsupported".into());
        site.accesses.clear();
        instruction.kind = InstructionKind::Stop;
        instruction.fall.clear();
        instruction.uses.clear();
    }
    if name == "site-not-reached" {
        request.entry_points = [NEXT].into();
        assert_eq!(request.slice_seeds, [SITE].into());
    }
    let target = if name == "different-decoder-target" {
        "x86_64-unknown-linux-gnu"
    } else {
        "x86_64-pc-windows-msvc"
    };
    let mut receipt = independent_receipt(row, target);
    if name == "missing-decoder-identity" {
        receipt.as_mut().unwrap().decoder_sha256 = None;
    }
    if let Some(receipt) = &receipt {
        receipt.validate().unwrap();
    }
    assert!(
        site_valid(site),
        "{name}: supplied site facts must be structurally valid"
    );
    request.snapshot_id = fault.metadata.snapshot_id.clone();
    context.snapshot_id = request.snapshot_id.clone();
    context.artifact_sha256 = artifact_sha256;
    context.query_id =
        sha(&serde_json::to_vec(&(name, &request.entry_points, &request.slice_seeds)).unwrap());
    context.semantic_profile = "i5c-supplied-unit-facts; no-native-preparation-credit".into();
    let completed = CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
    let analysis = BoundInvestigation::new(&completed, &request, context).unwrap();
    let fault = BoundFaultContext::new(analysis, fault).unwrap();
    let bound = BoundAddressWrapContext::new(
        fault,
        FaultAddressQuestion {
            site: SITE,
            memory_access: 0,
        },
        receipt,
    )
    .unwrap();
    assert!(
        bound
            .identity()
            .snapshot_id
            .starts_with("i5c-supplied-unit:")
    );
    bound
}

fn exercise_supplied_rows(names: &[&str]) -> BTreeSet<String> {
    let mut exercised = BTreeSet::new();
    for &name in names {
        let row = case(name);
        let bound = supplied_bound_unit(&row);
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
            serde_json::json!({"name": name, "tier": "supplied-bound-unit", "passed": true, "native_preparation": false, "raw_capture_credit": false})
        );
    }
    exercised
}

#[test]
fn w3_all_10_supplied_admission_cases_match_the_frozen_oracle() {
    checked_frozen_inventory();
    let exercised = exercise_supplied_rows(&SUPPLIED_UNIT_CASES[..10]);
    assert_eq!(exercised.len(), 10);
    assert_eq!(
        exercised,
        SUPPLIED_UNIT_CASES[..10]
            .iter()
            .map(|name| name.to_string())
            .collect()
    );
}

#[test]
fn w3_all_16_supplied_budget_cases_match_the_frozen_oracle() {
    checked_frozen_inventory();
    let exercised = exercise_supplied_rows(&SUPPLIED_UNIT_CASES[10..]);
    assert_eq!(exercised.len(), 16);
    assert_eq!(
        exercised,
        SUPPLIED_UNIT_CASES[10..]
            .iter()
            .map(|name| name.to_string())
            .collect()
    );
    assert_eq!(
        SUPPLIED_UNIT_CASES
            .iter()
            .copied()
            .collect::<BTreeSet<_>>()
            .len(),
        26
    );
}

/// Select one existing independent expectation without altering the W3 matrix.
/// The campaign pins this observer before compiling controls and mutations.
#[test]
#[ignore = "requires an explicit frozen I5c mutation observer case"]
fn w5_selected_frozen_mutation_case() {
    let name = std::env::var("ARIADNE_I5C_MUTATION_CASE").unwrap();
    println!("I5C_W5_OBSERVER {}", serde_json::json!({"case": name}));
    if name == "binding:receipt-bytes" {
        let mut bound = bound_raw_fixture("mov32mi-upper");
        bound
            .receipt
            .as_mut()
            .unwrap()
            .bytes_hex
            .replace_range(0..2, "90");
        assert!(
            assess_address_wrap(
                &bound,
                AddressWrapLimits {
                    max_evidence: 0,
                    max_claims: 0,
                }
            )
            .is_err(),
            "invalid receipt must be rejected before zero budgets"
        );
        return;
    }
    let row = case(&name);
    let bound = match row["harness"].as_str().unwrap() {
        "synthetic-capture" => bound_raw_fixture(&name),
        "bound-unit" => supplied_bound_unit(&row),
        other => panic!("unsupported frozen harness: {other}"),
    };
    let result = assess_address_wrap(&bound, oracle_limits(&row)).unwrap();
    assert_frozen_assessment(&result, &row);
}
