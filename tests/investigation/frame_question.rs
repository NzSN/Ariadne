use super::*;
use crate::investigation::{
    FrameStructureLimits, FrameStructureQuestion, QuestionVerdict, bind_frame_structure,
};
fn source() -> BoundFrameStructure {
    let (chain, frame) = super::super::frame_structure::tests::fixture();
    bind_frame_structure(
        chain,
        FrameStructureQuestion {
            from_frame: 0,
            to_frame: 0,
        },
        vec![(0, frame)],
        vec![],
        FrameStructureLimits::default(),
    )
    .unwrap()
}
fn question() -> FrameQuestion {
    FrameQuestion {
        question: FrameQuestionKind::Alternative {
            frame: 0,
            site: 0x400200,
            destination: 0x400204,
            edge_kind: crate::investigation::FramePathEdgeKind::Next,
            endpoint: ValueConstraint {
                point: QuestionPoint {
                    frame: 0,
                    site: 0x400200,
                    moment: QuestionMoment::Before,
                },
                bank: 0,
                width: 64,
                mask: u64::MAX,
                value: 0,
            },
        },
        conditions: Vec::new(),
    }
}
#[test]
fn partial_source_stays_unknown_and_roundtrips_without_helpers() {
    let source = source();
    let original = crate::reports::frame_structure::render_json(&source).unwrap();
    let result = investigate_frame_question(
        source,
        question(),
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    assert_eq!(
        result.assessment().layers.execution_evidence,
        "not_supplied"
    );
    assert!(!result.assessment().obligations.is_empty());
    let expected = result
        .source()
        .structure()
        .frames()
        .iter()
        .filter(|m| !m.auxiliary)
        .map(|m| m.gaps.len())
        .sum::<usize>();
    assert_eq!(
        result
            .assessment()
            .obligations
            .iter()
            .filter(|o| o.kind.starts_with("source:"))
            .count(),
        expected
    );
    assert_eq!(
        crate::reports::frame_structure::render_json(result.source().structure()).unwrap(),
        original
    );
    let json = crate::reports::frame_question::render_json(&result).unwrap();
    let checked =
        crate::reports::frame_question::decode(json.as_bytes(), &FrameQuestionLimits::default())
            .unwrap();
    assert_eq!(
        crate::reports::frame_question::render_json(&checked).unwrap(),
        json
    );
    let state_host = FrameQuestionLimits {
        max_states: 0,
        ..Default::default()
    };
    assert!(crate::reports::frame_question::decode(json.as_bytes(), &state_host).is_err());
    let host = FrameQuestionLimits {
        max_input_bytes: json.len() - 1,
        ..Default::default()
    };
    assert!(crate::reports::frame_question::decode(json.as_bytes(), &host).is_err());
    assert!(
        crate::reports::frame_question::decode(
            json.replace("\"schema\":", "\"schema\":0,\"schema\":")
                .as_bytes(),
            &FrameQuestionLimits::default()
        )
        .is_err()
    );
}
#[test]
fn invalid_selectors_and_nonprogressive_revisions_reject_before_work() {
    let mut q = question();
    q.conditions.push(ValueConstraint {
        point: QuestionPoint {
            frame: 1,
            site: 0x400200,
            moment: QuestionMoment::Before,
        },
        bank: 0,
        width: 64,
        mask: 1,
        value: 0,
    });
    assert!(
        investigate_frame_question(
            source(),
            q,
            FrameQuestionEvidence::default(),
            FrameQuestionLimits::default()
        )
        .is_err()
    );
    assert!(
        investigate_frame_question(
            source(),
            question(),
            FrameQuestionEvidence::default().with_revision(source()),
            FrameQuestionLimits::default()
        )
        .is_err()
    );
    for (access, load) in [(99, None), (0, Some(0x400200))] {
        let q = FrameQuestion {
            question: FrameQuestionKind::FaultDependency {
                frame: 0,
                site: 0x400206,
                access,
                load,
                focus_writer: None,
            },
            conditions: vec![],
        };
        assert!(
            investigate_frame_question(
                saved_source(),
                q,
                FrameQuestionEvidence::default(),
                FrameQuestionLimits {
                    origin_work: 0,
                    ..Default::default()
                }
            )
            .is_err()
        );
    }
    let limits = FrameQuestionLimits {
        quantum: 0,
        ..Default::default()
    };
    assert!(
        investigate_frame_question(
            source(),
            question(),
            FrameQuestionEvidence::default(),
            limits
        )
        .is_err()
    );
}
#[test]
fn independent_exhaustive_inverse_oracle() {
    let oracle: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/frame_question_oracle.json")).unwrap();
    for row in oracle["inverses"].as_array().unwrap() {
        let value = row["constant"].as_u64().unwrap();
        let op = match row["op"].as_str().unwrap() {
            "copy" => super::super::ScalarTransfer::Copy,
            "add" => super::super::ScalarTransfer::Add { value },
            "sub" => super::super::ScalarTransfer::Sub { value },
            "and" => super::super::ScalarTransfer::And { mask: value },
            _ => super::super::ScalarTransfer::Constant { value },
        };
        let step = super::super::backward_preimage(
            &super::super::BackwardValue::Exact {
                width: 4,
                value: row["endpoint"].as_u64().unwrap(),
            },
            &op,
        )
        .unwrap();
        let actual: Vec<_> = (0..16)
            .filter(|n| step.before.as_ref().is_some_and(|v| v.permits(*n).unwrap()))
            .collect();
        let expected: Vec<_> = row["inputs"]
            .as_array()
            .unwrap()
            .iter()
            .map(|n| n.as_u64().unwrap())
            .collect();
        assert_eq!(actual, expected, "{row}");
    }
}

fn saved_source() -> BoundFrameStructure {
    crate::reports::frame_structure::decode_expected(
        include_bytes!("fixtures/evidence/frame-question-source.json"),
        &FrameStructureLimits::default(),
        "92ec88bd4e0f55b977bbe0ee08a80f4eb077c00d0b3884c4660e1d1f8da05739",
    )
    .unwrap()
}
fn alternative(value: u64) -> FrameQuestion {
    FrameQuestion {
        question: FrameQuestionKind::Alternative {
            frame: 1,
            site: 0x400306,
            destination: 0x40030c,
            edge_kind: crate::investigation::FramePathEdgeKind::Taken,
            endpoint: ValueConstraint {
                point: QuestionPoint {
                    frame: 1,
                    site: 0x400310,
                    moment: QuestionMoment::Before,
                },
                bank: 1,
                width: 64,
                mask: u64::MAX,
                value,
            },
        },
        conditions: vec![],
    }
}
fn partial_saved_source() -> BoundFrameStructure {
    let source = saved_source();
    let mut rows = Vec::new();
    for (i, r) in source.recoveries() {
        let mut limits = *r.recovery().limits();
        if *i == 1 {
            limits.max_visits = 1;
        }
        let recovery = crate::recovery::recover(r.request().clone(), limits).unwrap();
        rows.push((
            *i,
            super::super::frame_structure::bind_recovery(
                source.chain(),
                *i,
                recovery,
                r.context().clone(),
                r.proofs().clone(),
                source.limits(),
            )
            .unwrap(),
        ));
    }
    bind_frame_structure(
        source.chain().clone(),
        source.question().clone(),
        rows,
        source.diagnostics().to_vec(),
        source.limits().clone(),
    )
    .unwrap()
}
#[test]
fn source_bound_witness_refutation_abstract_unknown_and_zero_work() {
    let run = |value, limits| {
        investigate_frame_question(
            saved_source(),
            alternative(value),
            FrameQuestionEvidence::default(),
            limits,
        )
        .unwrap()
    };
    let p = run(0, FrameQuestionLimits::default());
    assert_eq!(p.assessment().verdict, QuestionVerdict::PossibleUnderModel);
    assert!(p.assessment().witness.is_some());
    let r = run(1, FrameQuestionLimits::default());
    assert_eq!(r.assessment().verdict, QuestionVerdict::RefutedUnderModel);
    assert!(r.assessment().witness.is_none());
    let limits = FrameQuestionLimits {
        max_values: 0,
        ..Default::default()
    };
    let a = run(0, limits);
    assert_eq!(a.assessment().verdict, QuestionVerdict::Unknown);
    assert!(a.assessment().witness.is_none());
    let limits = FrameQuestionLimits {
        constraint_work: 0,
        ..Default::default()
    };
    let z = run(1, limits);
    assert_eq!(z.assessment().verdict, QuestionVerdict::Unknown);
    assert_eq!(z.assessment().layers.feasibility.work, 0);
    let mut json: serde_json::Value =
        serde_json::from_str(&crate::reports::frame_question::render_json(&a).unwrap()).unwrap();
    json["assessment"]["verdict"] = serde_json::json!("possible_under_model");
    crate::reports::frame_question::rehash_for_test(&mut json).unwrap();
    assert!(
        crate::reports::frame_question::decode(
            &serde_json::to_vec(&json).unwrap(),
            &FrameQuestionLimits::default()
        )
        .is_err()
    );
}
#[test]
fn revisions_preserve_roots_invalidate_old_conclusions_and_reject_regression() {
    let initial = partial_saved_source();
    let result = investigate_frame_question(
        initial,
        alternative(1),
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    let result = investigate_frame_question(
        partial_saved_source(),
        alternative(1),
        FrameQuestionEvidence::default().with_revision(saved_source()),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(
        result.assessment().verdict,
        QuestionVerdict::RefutedUnderModel
    );
    assert_eq!(result.assessment().revisions.len(), 2);
    assert!(result.assessment().revisions[1].invalidated_prior_conclusions);
    let json = crate::reports::frame_question::render_json(&result).unwrap();
    crate::reports::frame_question::decode(json.as_bytes(), &FrameQuestionLimits::default())
        .unwrap();
    assert!(
        investigate_frame_question(
            saved_source(),
            alternative(1),
            FrameQuestionEvidence::default().with_revision(partial_saved_source()),
            FrameQuestionLimits::default()
        )
        .is_err()
    );
}
#[test]
fn completed_callee_identity_and_candidate_universe_survive_focus_and_stops() {
    let source = saved_source();
    let r = &source.recoveries().iter().find(|(i, _)| *i == 0).unwrap().1;
    let mut wrong = r.request().clone();
    wrong.snapshot_id.push_str(":different");
    let mut a = crate::Analyzer::new(wrong).unwrap();
    while a.state().phase != crate::Phase::Done {
        a.step();
    }
    let wrong = CompletedAnalysis::from_analyzer(a);
    assert!(
        FrameQuestionEvidence::default()
            .with_completed_frame(&source, 0, wrong)
            .is_err()
    );
    let query = FrameQuestion {
        question: FrameQuestionKind::FaultDependency {
            frame: 0,
            site: 0x400206,
            access: 0,
            load: Some(0x400206),
            focus_writer: Some(0x400200),
        },
        conditions: vec![],
    };
    let mut a = crate::Analyzer::new(r.request().clone()).unwrap();
    while a.state().phase != crate::Phase::Done {
        a.step();
    }
    let evidence = FrameQuestionEvidence::default()
        .with_completed_frame(&source, 0, CompletedAnalysis::from_analyzer(a))
        .unwrap();
    let caller = &source.recoveries().iter().find(|(i, _)| *i == 1).unwrap().1;
    let mut extra = crate::Analyzer::new(caller.request().clone()).unwrap();
    while extra.state().phase != crate::Phase::Done {
        extra.step();
    }
    let evidence = evidence
        .with_completed_frame(&source, 1, CompletedAnalysis::from_analyzer(extra))
        .unwrap();
    let result = investigate_frame_question(
        source,
        query.clone(),
        evidence,
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(
        result
            .evidence()
            .completed_frames
            .iter()
            .map(|i| i.frame)
            .collect::<Vec<_>>(),
        vec![0]
    );
    assert!(
        result
            .source()
            .structure()
            .recoveries()
            .iter()
            .all(|(_, r)| r.recovery().metrics().incoming_evaluations == 0)
    );
    assert_eq!(result.assessment().candidate_count, Some(1));
    assert!(result.assessment().candidate_universe_sha256.is_some());
    assert!(
        result
            .assessment()
            .origins
            .iter()
            .any(|c| c.kind == "entry")
    );
    assert!(
        result
            .assessment()
            .origins
            .iter()
            .any(|c| c.kind == "external_interference")
    );
    let json = crate::reports::frame_question::render_json(&result).unwrap();
    crate::reports::frame_question::decode(json.as_bytes(), &FrameQuestionLimits::default())
        .unwrap();
    let limits = FrameQuestionLimits {
        origin_work: 0,
        ..Default::default()
    };
    let stopped = investigate_frame_question(
        saved_source(),
        query,
        FrameQuestionEvidence::default(),
        limits,
    )
    .unwrap();
    assert_eq!(stopped.assessment().candidate_count, None);
    assert!(
        stopped
            .assessment()
            .origins
            .iter()
            .all(|c| c.disposition != "excluded_within_scope")
    );
}

#[test]
fn partial_connection_carrier_preserves_conditional_source_and_independent_layers() {
    let source = crate::reports::frame_structure::decode(
        include_bytes!("fixtures/evidence/frame-question-conditional-source.json"),
        &FrameStructureLimits::default(),
    )
    .unwrap();
    assert!(source.is_conditional());
    let hypotheses = source.hypothesis_ids();
    let entry = source
        .frames()
        .iter()
        .find(|m| m.frame == 0 && !m.auxiliary)
        .unwrap()
        .entry;
    let connections = super::super::summarize_frame_connections(
        source,
        1,
        super::super::FrameConnectionLimits {
            scc_work: 0,
            ..Default::default()
        },
    )
    .unwrap();
    assert_eq!(
        connections.analysis().scc_status,
        super::super::ConnectionLayerStatus::WorkStopped
    );
    let question = FrameQuestion {
        question: FrameQuestionKind::Alternative {
            frame: 0,
            site: entry,
            destination: entry,
            edge_kind: super::super::FramePathEdgeKind::Next,
            endpoint: ValueConstraint {
                point: QuestionPoint {
                    frame: 0,
                    site: entry,
                    moment: QuestionMoment::Before,
                },
                bank: 0,
                width: 64,
                mask: u64::MAX,
                value: 0,
            },
        },
        conditions: vec![],
    };
    let result = investigate_frame_question(
        connections,
        question,
        FrameQuestionEvidence::default(),
        FrameQuestionLimits {
            constraint_work: 0,
            ..Default::default()
        },
    )
    .unwrap();
    assert_eq!(result.assessment().conditional_on, hypotheses);
    assert!(result.source().connections().is_some());
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    let json = crate::reports::frame_question::render_json(&result).unwrap();
    let checked =
        crate::reports::frame_question::decode(json.as_bytes(), &FrameQuestionLimits::default())
            .unwrap();
    assert_eq!(checked.assessment(), result.assessment());
}

#[test]
fn clock_metadata_and_expression_budgets_are_replayed() {
    let result = investigate_frame_question(
        saved_source(),
        alternative(0),
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    let mut value: serde_json::Value =
        serde_json::from_str(&crate::reports::frame_question::render_json(&result).unwrap())
            .unwrap();
    value["assessment"]["layers"]["feasibility"]["elapsed_ms"] =
        serde_json::json!(result.assessment().elapsed_total_ms + 1);
    crate::reports::frame_question::rehash_for_test(&mut value).unwrap();
    assert!(
        crate::reports::frame_question::decode(
            &serde_json::to_vec(&value).unwrap(),
            &FrameQuestionLimits::default()
        )
        .is_err()
    );
    for limits in [
        FrameQuestionLimits {
            max_expression_nodes: 0,
            ..Default::default()
        },
        FrameQuestionLimits {
            max_tasks: 0,
            ..Default::default()
        },
    ] {
        let stopped = investigate_frame_question(
            saved_source(),
            alternative(0),
            FrameQuestionEvidence::default(),
            limits,
        )
        .unwrap();
        assert_eq!(stopped.assessment().verdict, QuestionVerdict::Unknown);
        assert_eq!(
            stopped.assessment().layers.feasibility.status,
            QuestionLayerStatus::WorkStopped
        );
        let json = crate::reports::frame_question::render_json(&stopped).unwrap();
        crate::reports::frame_question::decode(json.as_bytes(), &FrameQuestionLimits::default())
            .unwrap();
    }
}

#[test]
fn future_after_conditions_are_not_premature_model_witnesses() {
    let mut q = alternative(0);
    let FrameQuestionKind::Alternative { endpoint, .. } = &mut q.question else {
        unreachable!()
    };
    endpoint.point.site = 0x40030c;
    let mut after = endpoint.clone();
    after.point.moment = QuestionMoment::After;
    after.value = 1;
    q.conditions.push(after);
    let result = investigate_frame_question(
        saved_source(),
        q,
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    assert!(result.assessment().witness.is_none());
}
#[test]
fn captured_point_is_a_before_state_boundary() {
    let mut q = FrameQuestion {
        question: FrameQuestionKind::Alternative {
            frame: 0,
            site: 0x400200,
            destination: 0x400204,
            edge_kind: super::super::FramePathEdgeKind::Next,
            endpoint: ValueConstraint {
                point: QuestionPoint {
                    frame: 0,
                    site: 0x40020d,
                    moment: QuestionMoment::Before,
                },
                bank: 1,
                width: 64,
                mask: u64::MAX,
                value: 0,
            },
        },
        conditions: vec![],
    };
    let result = investigate_frame_question(
        saved_source(),
        q.clone(),
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    assert!(
        !result
            .assessment()
            .serviced_tasks
            .iter()
            .any(|s| s.ends_with(":0x400209"))
    );
    assert!(
        result
            .assessment()
            .obligations
            .iter()
            .any(|o| o.kind == "captured-point-normal-transfer-unavailable")
    );
    let FrameQuestionKind::Alternative { endpoint, .. } = &mut q.question else {
        unreachable!()
    };
    endpoint.point.site = 0x400206;
    endpoint.point.moment = QuestionMoment::After;
    let result = investigate_frame_question(
        saved_source(),
        q,
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(
        result.assessment().layers.feasibility.status,
        QuestionLayerStatus::Unavailable
    );
    assert_eq!(
        result.assessment().layers.feasibility.reason.as_deref(),
        Some("captured-point-normal-transfer-unavailable")
    );
}
#[test]
fn partial_word_outputs_cannot_become_exact_whole_registers() {
    use crate::bap::target_resolution::question_semantics::{Bits, Environment};
    let bil:Vec<crate::bap::ast::Stmt>=serde_json::from_value(serde_json::json!([{"kind":"move","var":{"name":"RAX","index":0,"virtual":false,"width":8,"type":"imm"},"value":{"kind":"int","value":"0:8u"}}])).unwrap();
    let transfer = crate::bap::target_resolution::extract(&bil, 0, &[0xb0, 0]).unwrap();
    let bytes = crate::effects::RegisterView::new(0, 0, 8).unwrap().reads();
    let instruction = crate::Instruction {
        kind: crate::InstructionKind::Ordinary,
        may_defs: bytes.clone(),
        must_defs: bytes,
        ..Default::default()
    };
    let env = Environment::from([("RAX".into(), Bits::exact(64, 0x123400))]);
    let limits = FrameQuestionLimits::default();
    let mut meter = super::meter::Meter::new(
        limits.constraint_work,
        &limits,
        std::time::Instant::now(),
        None,
    );
    let (after, _, _, exact) =
        super::alternative::advance(&env, &instruction, Some(&transfer), &mut meter, &limits)
            .unwrap();
    assert_eq!(after["RAX"].width, 64);
    assert_eq!(after["RAX"].number(), None);
    assert!(!exact);
    let merged = Bits::exact(8, 0).join(Bits::exact(64, 0x123400));
    assert_eq!(merged.width, 64);
    assert_eq!(merged.number(), None);
}

#[test]
fn captured_loop_observation_is_not_forced_onto_its_first_visit() {
    let source = crate::reports::frame_structure::decode_expected(
        include_bytes!("fixtures/evidence/frame-question-loop-source.json"),
        &FrameStructureLimits::default(),
        "2c15d35ef28b9c0192e373650e3e008cab4eb157ad32acaef21dd2c211a39fed",
    )
    .unwrap();
    assert_eq!(source.chain().frames[0].registers["rcx"], 2);
    let q = FrameQuestion {
        question: FrameQuestionKind::Alternative {
            frame: 0,
            site: 0x400212,
            destination: 0x40020b,
            edge_kind: super::super::FramePathEdgeKind::Taken,
            endpoint: ValueConstraint {
                point: QuestionPoint {
                    frame: 0,
                    site: 0x40020b,
                    moment: QuestionMoment::Before,
                },
                bank: 1,
                width: 64,
                mask: u64::MAX,
                value: 2,
            },
        },
        conditions: vec![],
    };
    let result = investigate_frame_question(
        source,
        q,
        FrameQuestionEvidence::default(),
        FrameQuestionLimits::default(),
    )
    .unwrap();
    assert_eq!(result.assessment().verdict, QuestionVerdict::Unknown);
    assert!(
        result
            .assessment()
            .obligations
            .iter()
            .any(|o| o.kind == "cyclic-value-coverage-unavailable")
    );
}
