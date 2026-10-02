use ariadne::mbt::stage_e::{
    Evidence, LLVMIRPort, MachineStatePort, fixtures_ir, fixtures_machine, ir_binding,
    machine_binding,
};
use mirrorrust::{ApalacheConfig, FallibleStateComputer, State, Value};
use std::cell::RefCell;
use std::rc::Rc;

fn initial(case: &str) -> State {
    [("case_id".into(), Value::Str(case.into()))].into()
}

fn config() -> ApalacheConfig {
    ApalacheConfig {
        spec_path: "replay.tla".into(),
        init_predicate: Some("Init".into()),
        next_predicate: Some("Next".into()),
        const_init: None,
        invariant: "Safety".into(),
        length_bound: 30,
        param_vars: Some("parameters".into()),
    }
}

#[test]
fn machine_binding_resets_and_ignores_expected_or_previous_state() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let port = MachineStatePort::new(fixtures_machine::request(), evidence.clone());
    let mut binding = machine_binding::bind_machine_state_replay(port, &config()).unwrap();
    let poisoned_previous = [("phase".into(), Value::Str("invented".into()))].into();
    for _ in 0..2 {
        let initial = binding
            .compute("init", &initial("MachineStateReplay"), &poisoned_previous)
            .unwrap();
        assert_eq!(initial["phase"], Value::Str("stateflow".into()));
        for _ in 0..3 {
            binding
                .compute("propagate", &State::new(), &poisoned_previous)
                .unwrap();
        }
        let done = binding
            .compute("finishStateflow", &State::new(), &poisoned_previous)
            .unwrap();
        assert_eq!(done["phase"], Value::Str("done".into()));
    }
    binding.assert_all_actions_covered().unwrap();
    assert_eq!(evidence.borrow().initializations, 2);
    assert_eq!(evidence.borrow().observations, 10);
    assert_eq!(evidence.borrow().port_drops, 0);
    drop(binding);
    assert_eq!(evidence.borrow().port_drops, 1);
}

#[test]
fn ir_binding_resets_and_rejects_advancing_after_completion() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let port = LLVMIRPort::new(fixtures_ir::request(), evidence.clone());
    let mut binding = ir_binding::bind_l_l_v_m_i_r_replay(port, &config()).unwrap();
    for _ in 0..2 {
        binding
            .compute("init", &initial("LLVMIRReplay"), &State::new())
            .unwrap();
        for _ in 0..3 {
            binding
                .compute("expandSlice", &State::new(), &State::new())
                .unwrap();
        }
        let done = binding
            .compute("finishSlice", &State::new(), &State::new())
            .unwrap();
        assert_eq!(done["phase"], Value::Str("done".into()));
    }
    binding.assert_all_actions_covered().unwrap();
    let error = binding
        .compute("expandSlice", &State::new(), &State::new())
        .unwrap_err();
    assert_eq!(error.code, "adapter_failure");
    assert_eq!(error.message, "step requested after completion");
    assert_eq!(
        binding
            .compute("init", &initial("LLVMIRReplay"), &State::new())
            .unwrap_err()
            .code,
        "binding_poisoned"
    );
    assert_eq!(evidence.borrow().initializations, 2);
    assert_eq!(evidence.borrow().observations, 10);
    drop(binding);
    assert_eq!(evidence.borrow().port_drops, 1);
}

#[test]
fn unknown_action_poisoning_prevents_machine_initialization() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let port = MachineStatePort::new(fixtures_machine::request(), evidence.clone());
    let mut binding = machine_binding::bind_machine_state_replay(port, &config()).unwrap();
    assert_eq!(
        binding
            .compute("invented", &State::new(), &State::new())
            .unwrap_err()
            .code,
        "unknown_action"
    );
    assert_eq!(
        binding
            .compute("init", &State::new(), &State::new())
            .unwrap_err()
            .code,
        "binding_poisoned"
    );
    assert_eq!(evidence.borrow().initializations, 0);
    assert_eq!(evidence.borrow().observations, 0);
    drop(binding);
    assert_eq!(evidence.borrow().port_drops, 1);
}

#[test]
fn machine_wire_rows_preserve_empty_entries_and_full_u64_addresses() {
    let mut request = fixtures_machine::request();
    request.nodes.remove(&5);
    request.nodes.insert(u64::MAX);
    let effects = request.effects.remove(&5).unwrap();
    request.effects.insert(u64::MAX, effects);
    request.complete_sites.remove(&5);
    request.complete_sites.insert(u64::MAX);
    request.structural_edges = request
        .structural_edges
        .into_iter()
        .map(|mut edge| {
            if edge.dst == 5 {
                edge.dst = u64::MAX;
            }
            edge
        })
        .collect();
    request.terminal_transitions = request
        .terminal_transitions
        .into_iter()
        .map(|mut row| {
            if row.site == 5 {
                row.site = u64::MAX;
            }
            row
        })
        .collect();
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let mut binding = machine_binding::bind_machine_state_replay(
        MachineStatePort::new(request, evidence),
        &config(),
    )
    .unwrap();
    let observed = binding
        .compute("init", &initial("MachineStateReplay"), &State::new())
        .unwrap();
    let Value::Set(rows) = &observed["statesAt"] else {
        panic!("expected state rows");
    };
    assert_eq!(rows.len(), 5);
    let Value::Record(row) = rows.iter().find(|row| matches!(row, Value::Record(fields) if fields["va"] == Value::Int(u64::MAX.into()))).unwrap() else { unreachable!() };
    assert_eq!(row["states"], Value::Set(vec![]));
    assert!(
        mirrorrust::encode_state(&observed)
            .to_string()
            .contains("18446744073709551615")
    );
}

#[test]
fn malformed_case_input_is_rejected_before_reset_and_poisoned() {
    let evidence = Rc::new(RefCell::new(Evidence::default()));
    let mut binding = machine_binding::bind_machine_state_replay(
        MachineStatePort::new(fixtures_machine::request(), evidence.clone()),
        &config(),
    )
    .unwrap();
    let malformed = [("case_id".into(), Value::Int(7.into()))].into();
    assert_eq!(
        binding
            .compute("init", &malformed, &State::new())
            .unwrap_err()
            .code,
        "input_shape_mismatch"
    );
    assert_eq!(evidence.borrow().initializations, 0);
    assert_eq!(evidence.borrow().observations, 0);
    assert_eq!(
        binding
            .compute("init", &initial("MachineStateReplay"), &State::new())
            .unwrap_err()
            .code,
        "binding_poisoned"
    );
}
