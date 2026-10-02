use ariadne::investigation::*;
use ariadne::{
    AnalysisRequest, Analyzer, InputKind, Instruction, InstructionKind,
    effects::{Catalogue, RegisterView},
};
fn cells(bank: u8) -> ariadne::LocationSet {
    RegisterView::new(bank, 0, 64).unwrap().reads()
}
fn fixture() -> (Analyzer, AnalysisRequest, EvidenceContext) {
    let locations = Catalogue.locations();
    let request = AnalysisRequest {
        snapshot_id: "fixture-snapshot".into(),
        addresses: [0x1000, 0x1003, 0x1006].into(),
        locations,
        entry_points: [0x1000].into(),
        slice_seeds: [0x1003].into(),
        input_kind: InputKind::Dump,
        captured: [0x1000, 0x1003, 0x1006].into(),
        decodable: [0x1000, 0x1003, 0x1006].into(),
        instructions: [
            (
                0x1000,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [0x1003].into(),
                    uses: cells(3),
                    may_defs: cells(0),
                    must_defs: cells(0),
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                0x1003,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [0x1006].into(),
                    uses: cells(0),
                    may_defs: ["memory:any".into()].into(),
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                0x1006,
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
    let sites = [(0x1000, "4889d8"), (0x1003, "c70005000000"), (0x1006, "c3")]
        .into_iter()
        .map(|(va, hex)| SiteEvidence {
            va,
            bytes_hex: hex.into(),
            captured: true,
            opcode: Some(if va == 0x1003 { "MOV32mi" } else { "MOV64rr" }.into()),
            quality: "external_lift".into(),
            semantic_status: Some("projected".into()),
            helper_sha256: Some("1".repeat(64)),
            runtime_sha256: Some("2".repeat(64)),
            ast_sha256: Some("3".repeat(64)),
            projection: Some("tested-fixture-v1".into()),
            accesses: if va == 0x1003 {
                vec![AddressUse {
                    index: 0,
                    role: AccessRole::Store,
                    access_width: 32,
                    address_width: 64,
                    expression: Some(AddressExpression {
                        width: 64,
                        terms: vec![AddressTerm {
                            bank: 0,
                            coefficient: 1,
                        }],
                        constant: 0,
                    }),
                    address_inputs: cells(0).into_iter().collect(),
                    attribution: "bil.0.value".into(),
                    gaps: Vec::new(),
                }]
            } else {
                Vec::new()
            },
            spans: vec![Span {
                va,
                length: hex.len() / 2,
                contributors: vec![Contributor {
                    stream: 5,
                    entry: 0,
                    file_offset: 32 + va - 0x1000,
                }],
            }],
            gaps: Vec::new(),
        })
        .collect();
    let context = EvidenceContext {
        snapshot_id: request.snapshot_id.clone(),
        artifact_sha256: "4".repeat(64),
        query_id: "5".repeat(64),
        semantic_profile: "fixture-semantics".into(),
        sites,
        recovery_gaps: Vec::new(),
    };
    (analyzer, request, context)
}
#[test]
fn producer_claims_retain_byte_origins_entry_alternatives_and_capture_references() {
    let (a, r, c) = fixture();
    let bound = BoundInvestigation::new(&a, &r, c).unwrap();
    let e = explain_fault_address(
        &bound,
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    e.validate().unwrap();
    assert_eq!(e.status, AnswerStatus::Partial);
    assert_eq!(e.origins.len(), 8);
    for group in &e.origins {
        assert!(group.location.starts_with("gpr:rax:"));
        assert_eq!(group.producers.len(), 1);
        assert_eq!(group.producers[0].site, 0x1000);
        assert_eq!(group.producers[0].origin, OriginKind::Instruction);
        assert!(group.producers[0].evidence_id.is_some());
    }
    assert!(e.gaps.iter().any(|g| g.code == "entry-origin"));
    assert!(
        e.evidence_requirements
            .iter()
            .all(|r| r.observation.len() > 30)
    );
    assert!(
        e.claims
            .iter()
            .filter(|c| matches!(
                c.assertion,
                Assertion::PossibleOrigin { .. } | Assertion::Dependency { .. }
            ))
            .all(|c| c.classification == Classification::DerivedUnderPremises)
    );
    assert!(
        e.evidence.iter().any(|v| v.instruction.va == 0x1000
            && v.instruction.spans[0].contributors[0].file_offset == 32)
    );
}
#[test]
fn same_snapshot_wrong_query_and_different_snapshot_are_rejected() {
    let (a, mut r, c) = fixture();
    r.slice_seeds = [0x1000].into();
    assert!(BoundInvestigation::new(&a, &r, c.clone()).is_err());
    let (_, r, _) = fixture();
    let mut c = c;
    c.snapshot_id = "other-snapshot".into();
    assert!(BoundInvestigation::new(&a, &r, c).is_err());
}
#[test]
fn finite_limits_never_label_truncated_output_explained() {
    let (a, r, c) = fixture();
    let b = BoundInvestigation::new(&a, &r, c).unwrap();
    let e = explain_fault_address(
        &b,
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        },
        ExplainLimits {
            max_evidence: 1,
            ..ExplainLimits::default()
        },
    )
    .unwrap();
    assert!(e.truncated);
    assert_eq!(e.status, AnswerStatus::Partial);
    assert!(e.gaps.iter().any(|g| g.code.starts_with("budget-")));
}

fn assert_bounded(e: &Explanation, limits: ExplainLimits) {
    e.validate().unwrap();
    assert!(e.evidence.len() <= limits.max_evidence);
    assert!(e.claims.len() <= limits.max_claims);
    let links = e
        .facts
        .iter()
        .filter(|f| {
            matches!(
                f.assertion,
                Assertion::PossibleOrigin { .. } | Assertion::Dependency { .. }
            )
        })
        .count();
    assert!(links <= limits.max_origin_links);
    let dependency_sites: std::collections::BTreeSet<_> = e
        .facts
        .iter()
        .filter_map(|f| {
            if let Assertion::Dependency { at, .. } = f.assertion {
                Some(at)
            } else {
                None
            }
        })
        .collect();
    assert!(dependency_sites.len() <= limits.max_dependency_nodes);
    for f in &e.facts {
        if let Assertion::PossibleOrigin { producer, .. } | Assertion::Dependency { producer, .. } =
            &f.assertion
        {
            if producer.origin == OriginKind::Instruction {
                assert!(producer.evidence_id.is_some());
            }
        }
    }
    if e.truncated {
        assert_ne!(e.status, AnswerStatus::Explained);
        assert!(e.gaps.iter().any(|g| g.code.starts_with("budget-")));
    }
    let json = serde_json::to_vec(e).unwrap();
    let decoded: Explanation = serde_json::from_slice(&json).unwrap();
    decoded.validate().unwrap();
    assert_eq!(
        serde_json::to_value(e).unwrap(),
        serde_json::to_value(decoded).unwrap()
    );
    #[cfg(feature = "reports")]
    {
        use ariadne::reports::{Format, decode_explanation, render_explanation};
        decode_explanation(&json).unwrap();
        for format in [Format::Text, Format::Json, Format::Dot] {
            render_explanation(e, format).unwrap();
        }
    }
}

#[test]
fn claim_and_evidence_exhaustion_return_valid_partial_answers() {
    let (a, r, c) = fixture();
    let bound = BoundInvestigation::new(&a, &r, c).unwrap();
    for limits in [
        ExplainLimits {
            max_claims: 1,
            ..ExplainLimits::default()
        },
        ExplainLimits {
            // Selected-site and address claims fit; the producer's evidence
            // spends the final slot before its origin fact can be admitted.
            max_claims: 3,
            ..ExplainLimits::default()
        },
        ExplainLimits {
            max_evidence: 0,
            ..ExplainLimits::default()
        },
    ] {
        let e = explain_fault_address(
            &bound,
            FaultAddressQuestion {
                site: 0x1003,
                memory_access: 0,
            },
            limits,
        )
        .unwrap();
        assert!(e.truncated);
        if limits.max_evidence == 0 {
            assert_eq!(e.status, AnswerStatus::Unavailable);
            assert!(e.address.is_none());
            assert!(e.origins.is_empty());
        } else {
            assert_eq!(e.status, AnswerStatus::Partial);
        }
        assert_bounded(&e, limits);
    }
}

#[test]
fn limit_boundaries_and_cycles_preserve_references_and_default_answers() {
    for cycle in [false, true] {
        let (mut analyzer, mut request, context) = fixture();
        if cycle {
            request.instructions.get_mut(&0x1000).unwrap().uses = cells(0);
            request.instructions.insert(
                0x1006,
                Instruction {
                    kind: InstructionKind::Jump,
                    targets: [0x1000].into(),
                    complete: true,
                    ..Instruction::default()
                },
            );
            analyzer = Analyzer::new(request.clone()).unwrap();
            while analyzer.step() {}
        }
        let bound = BoundInvestigation::new(&analyzer, &request, context).unwrap();
        let question = FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        };
        let baseline =
            explain_fault_address(&bound, question.clone(), ExplainLimits::default()).unwrap();
        assert!(!baseline.truncated);
        let exact = ExplainLimits {
            max_evidence: baseline.evidence.len(),
            max_claims: baseline.claims.len(),
            max_origin_links: baseline
                .facts
                .iter()
                .filter(|f| {
                    matches!(
                        f.assertion,
                        Assertion::PossibleOrigin { .. } | Assertion::Dependency { .. }
                    )
                })
                .count(),
            max_dependency_nodes: 1,
        };
        let at_boundary = explain_fault_address(&bound, question.clone(), exact).unwrap();
        assert!(!at_boundary.truncated);
        assert_eq!(
            serde_json::to_value(&baseline).unwrap(),
            serde_json::to_value(&at_boundary).unwrap()
        );
        for max_evidence in [0, 1, exact.max_evidence, exact.max_evidence + 1] {
            for max_claims in [0, 1, 2, exact.max_claims, exact.max_claims + 1] {
                for max_origin_links in [0, 1, exact.max_origin_links, exact.max_origin_links + 1] {
                    for max_dependency_nodes in [0, 1, 2] {
                        let limits = ExplainLimits {
                            max_evidence,
                            max_claims,
                            max_origin_links,
                            max_dependency_nodes,
                        };
                        let e = explain_fault_address(&bound, question.clone(), limits).unwrap();
                        assert_bounded(&e, limits);
                    }
                }
            }
        }
    }
}

#[test]
fn zero_budgets_do_not_hide_invalid_questions() {
    let (a, r, c) = fixture();
    let bound = BoundInvestigation::new(&a, &r, c).unwrap();
    let limits = ExplainLimits {
        max_evidence: 0,
        max_claims: 0,
        max_origin_links: 0,
        max_dependency_nodes: 0,
    };
    for question in [
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 1,
        },
        FaultAddressQuestion {
            site: 0x9999,
            memory_access: 0,
        },
    ] {
        assert!(explain_fault_address(&bound, question, limits).is_err());
    }
}
#[test]
fn unsupported_address_missing_fact_and_unreached_site_remain_unavailable() {
    let (a, r, mut c) = fixture();
    c.sites[1].accesses[0].expression = None;
    c.sites[1].accesses[0]
        .gaps
        .push("unsupported-address-variable".into());
    let b = BoundInvestigation::new(&a, &r, c).unwrap();
    let e = explain_fault_address(
        &b,
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    assert_eq!(e.status, AnswerStatus::Unavailable);
    assert!(e.origins.is_empty());
    assert!(e.gaps.iter().any(|g| g.code == "unsupported-address"));
}
#[test]
fn serialized_dangling_refs_history_classes_and_root_cause_variants_are_rejected() {
    let (a, r, c) = fixture();
    let b = BoundInvestigation::new(&a, &r, c).unwrap();
    let e = explain_fault_address(
        &b,
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    let mut bad = e.clone();
    bad.claims[0].fact_refs.push("missing".into());
    assert!(bad.validate().is_err());
    let mut json = serde_json::to_value(&e).unwrap();
    let index = e
        .claims
        .iter()
        .position(|c| matches!(c.assertion, Assertion::PossibleOrigin { .. }))
        .unwrap();
    json["claims"][index]["classification"] = serde_json::json!("observed");
    let bad: Explanation = serde_json::from_value(json.clone()).unwrap();
    assert!(bad.validate().is_err());
    json["claims"][index]["assertion"]["kind"] = serde_json::json!("confirmed_root_cause");
    assert!(serde_json::from_value::<Explanation>(json).is_err());
}
#[test]
fn evidence_scope_and_address_input_tampering_are_rejected() {
    let (a, r, c) = fixture();
    let b = BoundInvestigation::new(&a, &r, c.clone()).unwrap();
    let mut e = explain_fault_address(
        &b,
        FaultAddressQuestion {
            site: 0x1003,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap();
    e.evidence[0].scope_id = "another-context".into();
    assert!(e.validate().is_err());
    let mut c = c;
    c.sites[1].accesses[0]
        .address_inputs
        .push("gpr:rdx:0".into());
    assert!(BoundInvestigation::new(&a, &r, c).is_err());
}
