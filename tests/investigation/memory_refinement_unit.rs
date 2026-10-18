use super::*;
use crate::bap::ast::Stmt;
use crate::effects::{Catalogue, RegisterView};
use crate::{AnalysisRequest, Analyzer, InputKind, Instruction, InstructionKind};
use serde_json::json;

fn variable(name: &str, width: usize, kind: &str) -> serde_json::Value {
    json!({"name":name,"index":0,"virtual":false,"width":width,"type":kind})
}
fn expression_var(name: &str) -> serde_json::Value {
    json!({"kind":"var","var":variable(name,64,"imm")})
}
fn integer(value: u64) -> serde_json::Value {
    json!({"kind":"int","value":format!("0x{value:x}:64u")})
}
fn address(offset: u64, constant: bool) -> serde_json::Value {
    if constant {
        integer(offset)
    } else {
        json!({"kind":"binop","op":18,"lhs":expression_var("RBX"),"rhs":integer(offset)})
    }
}
fn fixture(constant: bool, cycle: bool, receipts: bool) -> (BoundMemoryRefinement, u64) {
    let store = 0x1000;
    let load = store + if constant { 8 } else { 4 };
    let ret = load + if constant { 8 } else { 4 };
    let store_bil:Vec<Stmt>=serde_json::from_value(json!([{"kind":"move","var":variable("mem",0,"mem"),"value":{"kind":"store","width":64,"mem":{"kind":"var","var":variable("mem",0,"mem")},"addr":address(if constant {0x1000} else {0x18},constant),"value":expression_var("RAX")}}])).unwrap();
    let load_bil:Vec<Stmt>=serde_json::from_value(json!([{"kind":"move","var":variable("RAX",64,"imm"),"value":{"kind":"load","width":64,"mem":{"kind":"var","var":variable("mem",0,"mem")},"addr":address(if constant {0x2000} else {0x28},constant)}}])).unwrap();
    let store_bytes = if constant {
        "4889042500100000"
    } else {
        "48894318"
    };
    let load_bytes = if constant {
        "488b042500200000"
    } else {
        "488b4328"
    };
    let mut evidence = Vec::new();
    let mut transfers = BTreeMap::new();
    for (site, bytes, opcode, bil) in [
        (store, store_bytes, "MOV64mr", store_bil),
        (load, load_bytes, "MOV64rm", load_bil),
    ] {
        let receipt = crate::bap::refinement::extract(&bil, site, bytes.into()).unwrap();
        evidence.push(SiteEvidence {
            va: site,
            bytes_hex: bytes.into(),
            captured: true,
            opcode: Some(opcode.into()),
            quality: "external_lift".into(),
            semantic_status: Some("projected".into()),
            helper_sha256: Some("1".repeat(64)),
            runtime_sha256: Some("2".repeat(64)),
            ast_sha256: Some(receipt.ast_sha256.clone()),
            projection: Some("bap-bit-provenance-v3".into()),
            accesses: crate::bap::address::extract(&bil, site)
                .iter()
                .map(AddressUse::from)
                .collect(),
            spans: vec![super::super::Span {
                va: site,
                length: bytes.len() / 2,
                contributors: vec![super::super::Contributor {
                    stream: 5,
                    entry: 0,
                    file_offset: 32 + site - store,
                }],
            }],
            gaps: Vec::new(),
        });
        if receipts {
            transfers.insert(site, receipt);
        }
    }
    evidence.push(SiteEvidence {
        va: ret,
        bytes_hex: "c3".into(),
        captured: true,
        opcode: Some("RET64".into()),
        quality: "opaque".into(),
        semantic_status: Some("opaque-call-return".into()),
        helper_sha256: Some("1".repeat(64)),
        runtime_sha256: Some("2".repeat(64)),
        ast_sha256: None,
        projection: Some("bap-bit-provenance-v3".into()),
        accesses: Vec::new(),
        spans: vec![super::super::Span {
            va: ret,
            length: 1,
            contributors: vec![super::super::Contributor {
                stream: 5,
                entry: 0,
                file_offset: 32 + ret - store,
            }],
        }],
        gaps: Vec::new(),
    });
    let rax = RegisterView::new(0, 0, 64).unwrap().reads();
    let rbx = RegisterView::new(3, 0, 64).unwrap().reads();
    let request = AnalysisRequest {
        snapshot_id: "memory-fixture".into(),
        addresses: [store, load, ret].into(),
        locations: Catalogue.locations(),
        entry_points: [store].into(),
        slice_seeds: [load].into(),
        input_kind: InputKind::Dump,
        captured: [store, load, ret].into(),
        decodable: [store, load, ret].into(),
        instructions: [
            (
                store,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [load].into(),
                    uses: rax.clone(),
                    may_defs: ["memory:any".into()].into(),
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                load,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [if cycle { store } else { ret }].into(),
                    uses: rbx.union(&["memory:any".into()].into()).cloned().collect(),
                    may_defs: rax.clone(),
                    must_defs: rax,
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                ret,
                Instruction {
                    kind: InstructionKind::Return,
                    complete: true,
                    ..Instruction::default()
                },
            ),
        ]
        .into(),
        ..AnalysisRequest::default()
    };
    let mut analyzer = Analyzer::new(request.clone()).unwrap();
    while analyzer.step() {}
    let context = super::super::EvidenceContext {
        snapshot_id: request.snapshot_id.clone(),
        artifact_sha256: "1".repeat(64),
        query_id: "2".repeat(64),
        semantic_profile: "independent-fixture-premises".into(),
        sites: evidence,
        recovery_gaps: Vec::new(),
    };
    let bound = BoundInvestigation::new(&analyzer, &request, context).unwrap();
    (
        BoundMemoryRefinement::new(bound, transfers, None).unwrap(),
        load,
    )
}
fn question(load: u64) -> FaultAddressQuestion {
    FaultAddressQuestion {
        site: load,
        memory_access: 0,
    }
}

#[test]
fn modular_ranges_match_784_independent_integer_cases() {
    let oracle: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/memory_refinement_oracle.json")).unwrap();
    for c in oracle["range_cases"].as_array().unwrap() {
        let a = u64::from_str_radix(c["a"].as_str().unwrap().trim_start_matches("0x"), 16).unwrap();
        let b = u64::from_str_radix(c["b"].as_str().unwrap().trim_start_matches("0x"), 16).unwrap();
        assert_eq!(
            modular_memory_overlap(
                a,
                c["a_bytes"].as_u64().unwrap() as usize,
                b,
                c["b_bytes"].as_u64().unwrap() as usize
            )
            .unwrap(),
            c["overlapping"].as_bool().unwrap()
        );
    }
}
#[test]
fn inverse_rules_match_1280_exhaustive_predecessor_sets() {
    let oracle: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/memory_refinement_oracle.json")).unwrap();
    for c in oracle["inverse_cases"].as_array().unwrap() {
        let value = c["operand"].as_u64().unwrap();
        let op = match c["kind"].as_str().unwrap() {
            "copy" => super::super::ScalarTransfer::Copy,
            "add" => super::super::ScalarTransfer::Add { value },
            "sub" => super::super::ScalarTransfer::Sub { value },
            "and" => super::super::ScalarTransfer::And { mask: value },
            _ => super::super::ScalarTransfer::Constant { value },
        };
        let after = BackwardValue::Exact {
            width: 4,
            value: c["after"].as_u64().unwrap(),
        };
        let result = super::super::backward_preimage(&after, &op).unwrap();
        for v in 0..16 {
            let expected = c["before"]
                .as_array()
                .unwrap()
                .iter()
                .any(|n| n.as_u64() == Some(v));
            assert_eq!(
                result
                    .before
                    .as_ref()
                    .is_some_and(|b| b.permits(v).unwrap()),
                expected,
                "case={c}, value={v}"
            );
        }
        assert_eq!(result.conflict, c["precision"] == "conflict");
    }
}
#[test]
fn constant_and_preserved_base_exclusions_keep_entry_memory() {
    for constant in [false, true] {
        let (bound, load) = fixture(constant, false, true);
        let r = assess_memory_origins(&bound, question(load), MemoryRefinementLimits::default())
            .unwrap();
        assert_eq!(r.original_candidate_count, 2);
        assert_eq!(r.candidates.len(), 2);
        assert_eq!(r.candidates[0].origin, OriginKind::Entry);
        assert_eq!(r.candidates[0].disposition, "unresolved");
        assert_eq!(r.candidates[1].disposition, "excluded_within_scope");
        r.validate_for(&bound).unwrap();
    }
}
#[test]
fn loops_and_absent_receipts_do_not_gain_precise_aliases() {
    for (cycle, receipts) in [(true, true), (false, false)] {
        let (bound, load) = fixture(false, cycle, receipts);
        let r = assess_memory_origins(&bound, question(load), MemoryRefinementLimits::default())
            .unwrap();
        assert!(
            r.candidates
                .iter()
                .all(|c| c.disposition != "excluded_within_scope")
        );
    }
}
#[test]
fn budgets_preserve_candidate_universe_and_validate_questions_first() {
    let (bound, load) = fixture(false, false, true);
    for limits in [
        MemoryRefinementLimits {
            max_candidates: 0,
            ..Default::default()
        },
        MemoryRefinementLimits {
            max_pair_checks: 0,
            ..Default::default()
        },
    ] {
        let r = assess_memory_origins(&bound, question(load), limits.clone()).unwrap();
        assert_eq!(r.original_candidate_count, 2);
        assert!(r.truncated);
        assert!(
            r.candidates
                .iter()
                .all(|c| c.disposition != "excluded_within_scope")
        );
        assert!(
            assess_memory_origins(
                &bound,
                FaultAddressQuestion {
                    site: load,
                    memory_access: 1
                },
                limits
            )
            .is_err()
        );
    }
}
#[test]
fn report_codec_recomputes_and_rejects_forged_exclusions() {
    let (bound, load) = fixture(false, false, true);
    let r =
        assess_memory_origins(&bound, question(load), MemoryRefinementLimits::default()).unwrap();
    let mut encoded = crate::reports::encode_memory_provenance(&r).unwrap();
    let bytes = serde_json::to_vec(&encoded).unwrap();
    assert_eq!(crate::reports::decode_memory_provenance(&bytes).unwrap(), r);
    encoded["candidates"][0]["disposition"] = json!("excluded_within_scope");
    assert!(
        crate::reports::decode_memory_provenance(&serde_json::to_vec(&encoded).unwrap()).is_err()
    );
    for format in [
        crate::reports::Format::Text,
        crate::reports::Format::Dot,
        crate::reports::Format::Json,
    ] {
        assert!(
            !crate::reports::render_memory_provenance(&r, format)
                .unwrap()
                .is_empty()
        );
    }
}
#[test]
fn receipt_namespace_maps_all_sixteen_gpr_banks_independently() {
    let names = [
        "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12",
        "R13", "R14", "R15",
    ];
    for (index, name) in names.iter().enumerate() {
        let bil: Vec<Stmt> = serde_json::from_value(
            json!([{"kind":"move","var":variable(name,64,"imm"),"value":integer(index as u64)}]),
        )
        .unwrap();
        let receipt = crate::bap::refinement::extract(&bil, 0x1000, "90".into()).unwrap();
        assert_eq!(
            receipt.outputs.get(&(index as u8)),
            Some(&TransferExpression::Constant {
                value: index as u64
            })
        );
    }
}
#[test]
fn information_erasure_and_partial_constraints_stop_independently() {
    use super::super::{ScalarTransfer, backward_preimage};
    let partial = backward_preimage(
        &BackwardValue::Exact {
            width: 64,
            value: 0x34,
        },
        &ScalarTransfer::And { mask: 0xff },
    )
    .unwrap();
    let value = partial.before.unwrap();
    assert!(value.permits(0x1234).unwrap());
    assert!(!value.permits(0x1235).unwrap());
    assert!(partial.boundary.is_none());
    let shifted = backward_preimage(&value, &ScalarTransfer::Add { value: 8 }).unwrap();
    assert!(shifted.before.unwrap().permits(0x122c).unwrap());
    let erased = backward_preimage(
        &BackwardValue::Exact {
            width: 64,
            value: 0,
        },
        &ScalarTransfer::Constant { value: 0 },
    )
    .unwrap();
    assert_eq!(erased.boundary.as_deref(), Some("information-erasure"));
    assert!(erased.before.unwrap().permits(u64::MAX).unwrap());
    let conflict = backward_preimage(
        &BackwardValue::Exact {
            width: 64,
            value: 1,
        },
        &ScalarTransfer::Constant { value: 0 },
    )
    .unwrap();
    assert!(conflict.conflict);
    assert!(conflict.before.is_none());
}

#[test]
fn numerical_worklist_keeps_independent_values_across_a_load_barrier() {
    let (bound, load) = fixture(false, false, true);
    let input = bound.input(question(load)).unwrap();
    let ret = input.nodes.iter().find(|n| !n.ordinary).unwrap().site;
    let (facts, _, truncated) = walk_numerical(
        &input,
        &MemoryRefinementLimits::default(),
        ret,
        [(0, 0x34), (3, 0x9000)].into(),
    )
    .unwrap();
    assert!(!truncated);
    assert!(facts.iter().any(|f| f.register == "rax"
        && f.reason.as_deref() == Some("memory-history-unavailable")
        && f.value
            == BackwardValue::Exact {
                width: 64,
                value: 0x34
            }));
    assert!(facts.iter().any(|f| f.site == 0x1000
        && f.register == "rbx"
        && f.value
            == BackwardValue::Exact {
                width: 64,
                value: 0x9000
            }));
    assert!(
        facts
            .iter()
            .all(|f| f.classification == super::super::Classification::DerivedUnderPremises)
    );
}
#[test]
fn numerical_loops_and_budgets_retain_the_last_established_fact() {
    let (bound, load) = fixture(false, true, true);
    let input = bound.input(question(load)).unwrap();
    let (facts, _, truncated) = walk_numerical(
        &input,
        &MemoryRefinementLimits::default(),
        load,
        [(3, 0x9000)].into(),
    )
    .unwrap();
    assert!(!truncated);
    assert!(
        facts
            .iter()
            .any(|f| f.reason.as_deref() == Some("cyclic-value-scope"))
    );
    let limits = MemoryRefinementLimits {
        max_numerical_tasks: 1,
        ..Default::default()
    };
    let (facts, gaps, truncated) =
        walk_numerical(&input, &limits, load, [(3, 0x9000)].into()).unwrap();
    assert!(truncated);
    assert!(gaps.iter().any(|g| g == "numerical-task-budget"));
    assert_eq!(
        facts[0].value,
        BackwardValue::Exact {
            width: 64,
            value: 0x9000
        }
    );
}
#[test]
fn altered_transfer_ast_and_footprint_claims_fail_rebinding() {
    let (bound, load) = fixture(false, false, true);
    let mut receipt = bound.receipts.values().next().unwrap().clone();
    let site = bound.analysis.sites[&receipt.site].clone();
    receipt.ast_sha256 = "0".repeat(64);
    assert!(receipt.validate(&site).is_err());
    let mut receipt = bound.receipts.values().next().unwrap().clone();
    receipt.memory_footprint_complete = false;
    assert!(receipt.validate(&site).is_err());
    assert!(
        assess_memory_origins(
            &bound,
            FaultAddressQuestion {
                site: load + 100,
                memory_access: 0
            },
            MemoryRefinementLimits {
                max_candidates: 0,
                ..Default::default()
            }
        )
        .is_err()
    );
}

#[test]
fn partial_overlap_is_retained_and_recovery_gaps_block_equal_base_exclusion() {
    let (mut bound, load) = fixture(false, false, true);
    let mut ast: serde_json::Value = serde_json::from_str(&bound.receipts[&load].ast).unwrap();
    ast[0]["value"]["addr"]["rhs"]["value"] = json!("0x1c:64u");
    let bil: Vec<Stmt> = serde_json::from_value(ast).unwrap();
    let receipt = crate::bap::refinement::extract(&bil, load, "488b431c".into()).unwrap();
    let site = bound.analysis.sites.get_mut(&load).unwrap();
    site.bytes_hex = "488b431c".into();
    site.ast_sha256 = Some(receipt.ast_sha256.clone());
    site.accesses = crate::bap::address::extract(&bil, load)
        .iter()
        .map(AddressUse::from)
        .collect();
    bound.receipts.insert(load, receipt);
    let r =
        assess_memory_origins(&bound, question(load), MemoryRefinementLimits::default()).unwrap();
    assert_eq!(r.candidates[1].disposition, "retained");
    assert_eq!(r.candidates[1].pairs[0].relation, "overlapping");
    let (mut bound, load) = fixture(false, false, true);
    std::sync::Arc::make_mut(&mut bound.analysis.state)
        .obligations
        .insert(crate::Obligation {
            site: 0x1000,
            reason: crate::ObligationReason::CallTargets,
        });
    let r =
        assess_memory_origins(&bound, question(load), MemoryRefinementLimits::default()).unwrap();
    assert!(
        r.candidates
            .iter()
            .all(|c| c.disposition != "excluded_within_scope")
    );
}

#[test]
fn all_store_accesses_must_be_disjoint_before_static_exclusion() {
    let (bound, load) = fixture(true, false, true);
    let mut input = bound.input(question(load)).unwrap();
    let store = 0x1000;
    let bil:Vec<Stmt>=serde_json::from_value(json!([1000u64,0x2000].into_iter().map(|offset|json!({"kind":"move","var":variable("mem",0,"mem"),"value":{"kind":"store","width":64,"mem":{"kind":"var","var":variable("mem",0,"mem")},"addr":integer(offset),"value":expression_var("RAX")}})).collect::<Vec<_>>())).unwrap();
    let site = input.sites.iter_mut().find(|s| s.va == store).unwrap();
    let receipt = crate::bap::refinement::extract(&bil, store, site.bytes_hex.clone()).unwrap();
    site.ast_sha256 = Some(receipt.ast_sha256.clone());
    site.accesses = crate::bap::address::extract(&bil, store)
        .iter()
        .map(AddressUse::from)
        .collect();
    *input.receipts.iter_mut().find(|r| r.site == store).unwrap() = receipt;
    let full = run(input.clone(), MemoryRefinementLimits::default()).unwrap();
    let c = full
        .candidates
        .iter()
        .find(|c| c.origin == OriginKind::Instruction)
        .unwrap();
    assert_eq!(c.pairs.len(), 2);
    assert_eq!(c.pairs[0].relation, "disjoint");
    assert_eq!(c.pairs[1].relation, "overlapping");
    assert_ne!(c.disposition, "excluded_within_scope");
    let partial = run(
        input,
        MemoryRefinementLimits {
            max_pair_checks: 1,
            ..Default::default()
        },
    )
    .unwrap();
    assert!(
        partial
            .candidates
            .iter()
            .all(|c| c.disposition != "excluded_within_scope")
    );
}
