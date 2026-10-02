use ariadne::machine_state as ms;
use ariadne::reports::*;
use serde_json::json;

fn request() -> ms::Request {
    ms::Request {
        snapshot_id: "report-snapshot".into(),
        nodes: [1, u64::MAX].into(),
        structural_edges: Default::default(),
        value_domain: [("x".into(), [ms::AbstractValue("unknown".into())].into())].into(),
        catalogue: [(
            ms::StateId("s\"\n".into()),
            ms::AbstractState {
                status: ms::Status::Running,
                valuation: [("x".into(), [ms::AbstractValue("unknown".into())].into())].into(),
            },
        )]
        .into(),
        entry_states: [(1, [ms::StateId("s\"\n".into())].into())].into(),
        effects: [
            (1, ms::Effects::default()),
            (u64::MAX, ms::Effects::default()),
        ]
        .into(),
        steps: Default::default(),
        terminal_transitions: Default::default(),
        complete_sites: [1].into(),
        adapter_obligations: [ms::AdapterObligation {
            site: u64::MAX,
            reason: ms::AdapterObligationReason::UnknownMemory,
        }]
        .into(),
    }
}
#[test]
fn request_round_trip_preserves_high_addresses_and_explicit_uncertainty() {
    let req = request();
    let value = encode_machine_request(&req).unwrap();
    let bytes = serde_json::to_vec(&value).unwrap();
    let decoded = decode_machine_request(&bytes).unwrap();
    assert_eq!(encode_machine_request(&decoded).unwrap(), value);
    let semantics = encode_semantics(&req).unwrap();
    assert!(decode_semantics(&serde_json::to_vec(&semantics).unwrap()).is_ok());
    let report =
        machine_report(&ms::analyze(decoded).unwrap(), None, Some(&sha256(&bytes))).unwrap();
    assert_eq!(report["not_reached"], json!(["0xffffffffffffffff"]));
    assert_eq!(report["obligations"].as_array().unwrap().len(), 2);
    let text = render_report(&report, Format::Text).unwrap();
    let dot = render_report(&report, Format::Dot).unwrap();
    let parsed: serde_json::Value =
        serde_json::from_str(&render_report(&report, Format::Json).unwrap()).unwrap();
    assert_eq!(parsed, report);
    assert!(text.contains("0xffffffffffffffff") && text.contains("unknown-memory"));
    assert!(
        dot.contains("0xffffffffffffffff")
            && dot.contains("unknown-memory")
            && dot.contains("\\\"")
    );
}
#[test]
fn strict_inputs_reject_duplicate_unknown_numeric_and_noncanonical_fields() {
    assert!(strict_json(br#"{"x":{"y":1,"y":2}}"#).is_err());
    let original = encode_machine_request(&request()).unwrap();
    for (field, bad) in [
        ("nodes", json!([1])),
        ("nodes", json!(["0xFFFFFFFFFFFFFFFF"])),
        ("nodes", json!(["0x1"])),
        ("schema", json!("v2")),
        ("extra", json!(true)),
    ] {
        let mut value = original.clone();
        value[field] = bad;
        assert!(
            decode_machine_request(&serde_json::to_vec(&value).unwrap()).is_err(),
            "{field}"
        );
    }
    let mut duplicate = original.clone();
    duplicate["effects"]
        .as_array_mut()
        .unwrap()
        .push(original["effects"][0].clone());
    assert!(decode_machine_request(&serde_json::to_vec(&duplicate).unwrap()).is_err());
    assert!(decode_semantics(&serde_json::to_vec(&original).unwrap()).is_err());
}
#[test]
fn recovery_report_rejects_wrong_identity_and_retains_call_context() {
    let result = ms::analyze(request()).unwrap();
    let mut context = ms::RecoveryContext {
        snapshot_id: "wrong".into(),
        full_edges: Default::default(),
        byte_provenance: [(1, ariadne::ByteSource::Captured)].into(),
        recovery_obligations: Default::default(),
        missing_slice_seeds: [99].into(),
    };
    assert!(machine_report(&result, Some(&context), None).is_err());
    context.snapshot_id = "report-snapshot".into();
    context.full_edges.insert(ariadne::Edge {
        src: 1,
        dst: 99,
        kind: ariadne::EdgeKind::Call,
    });
    let report = machine_report(&result, Some(&context), None).unwrap();
    assert_eq!(report["recovery"]["full_edges"][0]["kind"], "call");
    assert_eq!(
        report["recovery"]["missing_slice_seeds"],
        json!(["0x0000000000000063"])
    );
}
#[test]
fn publication_rejects_reuse_and_invalid_filename_without_partial_output() {
    let root = std::env::temp_dir().join(format!("ariadne-report-contract-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir(&root).unwrap();
    let output = root.join("reports");
    assert!(publish_all(&output, &[("../bad", String::new())]).is_err());
    assert!(!output.exists());
    publish_all(&output, &[("report.txt", "original".into())]).unwrap();
    assert!(publish_all(&output, &[("report.txt", "replacement".into())]).is_err());
    assert_eq!(
        std::fs::read_to_string(output.join("report.txt")).unwrap(),
        "original"
    );
    std::fs::remove_dir_all(root).unwrap();
}
