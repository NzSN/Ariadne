use crate::*;

#[test]
fn retained_completed_snapshot_survives_mutation_of_consumed_owned_result() {
    let request = AnalysisRequest {
        snapshot_id: "retained-completed-state".into(),
        addresses: [1].into(),
        entry_points: [1].into(),
        slice_seeds: [1].into(),
        file_backed: [1].into(),
        decodable: [1].into(),
        locations: ["x".into()].into(),
        instructions: [(
            1,
            Instruction {
                kind: InstructionKind::Return,
                fall: AddressSet::new(),
                targets: AddressSet::new(),
                complete: true,
                uses: ["x".into()].into(),
                may_defs: LocationSet::new(),
                must_defs: LocationSet::new(),
            },
        )]
        .into(),
        ..AnalysisRequest::default()
    };
    let completed = CompletedAnalysis::from_analyzer(Analyzer::new(request).unwrap());
    let retained = completed.shared_state();
    let expected = (*retained).clone();
    let mut owned = completed.into_result();
    owned.state.reaching.clear();
    owned.state.decoded.clear();
    assert_eq!(*retained, expected);
    assert!(!retained.reaching[&1].is_empty());
}
