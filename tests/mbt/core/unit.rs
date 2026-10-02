use super::*;

fn config() -> ApalacheConfig {
    ApalacheConfig {
        spec_path: "AriadneReplay.tla".into(),
        init_predicate: Some("Init".into()),
        next_predicate: Some("Next".into()),
        const_init: None,
        invariant: "Safety".into(),
        length_bound: 30,
        param_vars: Some("parameters".into()),
    }
}

fn pipeline_input() -> State {
    [("fixture_id".into(), Value::Str("Pipeline".into()))].into()
}

#[test]
fn generated_decoder_rejects_input_before_reset_and_poisons_binding() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let mut binding =
        generated::bind_ariadne_replay(adapter::Adapter::new(evidence.clone()), &config()).unwrap();
    let malformed = [("fixture_id".into(), Value::Int(1.into()))].into();
    assert_eq!(
        binding
            .compute("init", &malformed, &State::new())
            .unwrap_err()
            .code,
        "input_shape_mismatch"
    );
    assert!(evidence.borrow().fixtures.is_empty());
    assert_eq!(evidence.borrow().observations, 0);
    assert_eq!(
        binding
            .compute("init", &pipeline_input(), &State::new())
            .unwrap_err()
            .code,
        "binding_poisoned"
    );
    assert!(evidence.borrow().fixtures.is_empty());
    drop(binding);
    assert_eq!(evidence.borrow().port_drops, 1);
}

#[test]
fn generated_binding_covers_pipeline_and_owns_port_cleanup() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let mut binding =
        generated::bind_ariadne_replay(adapter::Adapter::new(evidence.clone()), &config()).unwrap();
    let mut observed = binding
        .compute("init", &pipeline_input(), &State::new())
        .unwrap();
    for action in [
        "visit",
        "visit",
        "finishRecovery",
        "propagate",
        "propagate",
        "finishDataflow",
        "expandSlice",
        "finishSlice",
    ] {
        observed = binding.compute(action, &State::new(), &observed).unwrap();
    }
    assert_eq!(observed["phase"], Value::Str("done".into()));
    binding.assert_all_actions_covered().unwrap();
    assert_eq!(
        binding.coverage(),
        BTreeMap::from([
            ("Initialize", 1),
            ("Visit", 2),
            ("FinishRecovery", 1),
            ("Propagate", 2),
            ("FinishDataflow", 1),
            ("ExpandSlice", 1),
            ("FinishSlice", 1),
        ])
    );
    assert_eq!(evidence.borrow().observations, 9);
    let mut local = binding.into_local_binding().unwrap();
    (local.dispose)().unwrap();
    assert_eq!(
        evidence.borrow().port_drops,
        0,
        "generated disposal callback is a no-op"
    );
    drop(local);
    assert_eq!(
        evidence.borrow().port_drops,
        1,
        "dropping the binding must release the actual SUT"
    );
}
