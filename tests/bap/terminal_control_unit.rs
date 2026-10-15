use super::super::guard_admission::CandidateControl;
use super::*;
fn fixtures() -> (serde_json::Value, serde_json::Value) {
    (
        serde_json::from_str(include_str!(
            "fixtures/caller-coverage/dump-four-shapes.json"
        ))
        .unwrap(),
        serde_json::from_str(include_str!(
            "fixtures/caller-coverage/raw-bap-observations.json"
        ))
        .unwrap(),
    )
}
fn case(name: &str) -> (CandidateSite, TerminalReceipt, Lift) {
    let (captured, raw) = fixtures();
    let captured = captured["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["id"] == name)
        .unwrap();
    let raw = raw["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["id"] == name)
        .unwrap();
    let lift: Lift = serde_json::from_value(raw["raw_bap"].clone()).unwrap();
    let ast = serde_json::to_string(&lift.bil).unwrap();
    let full = bytes(
        captured["llvm_and_preparation"]["bytes_hex"]
            .as_str()
            .unwrap(),
    )
    .unwrap();
    let mut record = captured["llvm_and_preparation"]["decoder_record"]
        .as_str()
        .unwrap()
        .to_owned();
    if name == "int3" {
        record = record.replace(" unsupported 1 - -", " ok 1 stop -");
    }
    let site = address(captured["site"].as_str().unwrap()).unwrap();
    let receipt = recognize(site, &full, &ast, &lift, &record)
        .unwrap()
        .unwrap();
    let source = CandidateSite {
        site: receipt.site.clone(),
        bytes_hex: receipt.bytes_hex.clone(),
        ast,
        control: CandidateControl {
            kind: ControlKind::Stop,
            fall: vec![],
            targets: vec![],
            complete: true,
        },
        opaque: true,
    };
    (source, receipt, lift)
}
#[test]
fn exact_captured_terminal_shapes_replay_and_preserve_the_ud1_extent_disagreement() {
    for name in ["int3", "ud2", "ud1"] {
        let (source, receipt, _) = case(name);
        validate_source(&source, &receipt).unwrap();
        validate_capture(&receipt, &bytes(&receipt.bytes_hex).unwrap()).unwrap();
        assert_eq!(receipt.annotation, EXIT);
        assert_eq!(receipt.resumption, RESUMPTION);
        if name == "ud1" {
            assert_eq!(receipt.bytes_hex, "670fb94012");
            assert_eq!(receipt.bap.bytes_hex, "670fb9");
            assert_eq!(receipt.bap.length, 3);
            assert_eq!(receipt.reference.length, 5);
        }
    }
}
#[test]
fn terminal_replay_rejects_unreviewed_bytes_bil_annotations_and_normal_successors() {
    let (original, receipt, _) = case("int3");
    for variant in [
        "nop",
        "prefixed",
        "extra-effect",
        "conditional",
        "exception",
        "bap-extent",
        "bap-opcode",
        "bap-properties",
        "scope",
        "resume",
        "fall",
        "incomplete",
        "rule",
    ] {
        let mut source = original.clone();
        let mut proof = receipt.clone();
        match variant {
            "nop" => {
                source.bytes_hex = "90".into();
                proof.bytes_hex = source.bytes_hex.clone();
            }
            "prefixed" => {
                source.bytes_hex = "66cc".into();
                proof.bytes_hex = source.bytes_hex.clone();
            }
            "extra-effect" => {
                source.ast=r#"[{"kind":"exception","number":3},{"kind":"move","var":{"name":"RAX","index":0,"virtual":false,"width":64,"type":"imm"},"value":{"kind":"int","value":"0:64u"}}]"#.into();
                proof.ast_sha256 = crate::reports::sha256(source.ast.as_bytes());
            }
            "conditional" => {
                source.ast=r#"[{"kind":"if","condition":{"kind":"int","value":"1:1u"},"yes":[{"kind":"exception","number":3}],"no":[]}]"#.into();
                proof.ast_sha256 = crate::reports::sha256(source.ast.as_bytes());
            }
            "exception" => {
                source.ast = r#"[{"kind":"exception","number":1}]"#.into();
                proof.ast_sha256 = crate::reports::sha256(source.ast.as_bytes());
            }
            "bap-extent" => proof.bap.length = 2,
            "bap-opcode" => proof.bap.opcode = "NOOP".into(),
            "bap-properties" => proof.bap.properties.control = true,
            "scope" => proof.annotation.clear(),
            "resume" => proof.resumption.clear(),
            "fall" => source.control.fall.push("0x00007ff77440b30e".into()),
            "incomplete" => source.control.complete = false,
            "rule" => proof.rule = "ordinary-empty-bil/v1".into(),
            _ => unreachable!(),
        }
        assert!(validate_source(&source, &proof).is_err(), "{variant}");
    }
    assert!(validate_capture(&receipt, &[]).is_err());
    assert!(validate_capture(&receipt, &[0x90]).is_err());
}
#[test]
fn ud1_parser_checks_every_modrm_sib_displacement_boundary_without_other_prefixes() {
    for hex in [
        "0fb9c0",
        "0fb900",
        "0fb90420",
        "0fb9042500000000",
        "0fb90500000000",
        "0fb94012",
        "0fb9842000000000",
        "670fb9c0",
        "670fb94012",
    ] {
        let b = bytes(hex).unwrap();
        assert_eq!(ud1_extent(&b), Some(b.len()), "{hex}");
        for end in 0..b.len() {
            assert_eq!(ud1_extent(&b[..end]), None, "truncated {hex} at {end}");
        }
        let mut extra = b.clone();
        extra.push(0);
        assert_eq!(ud1_extent(&extra), None);
    }
    for hex in [
        "660fb9c0",
        "480fb9c0",
        "f30fb9c0",
        "67670fb9c0",
        "0f0b",
        "90",
    ] {
        assert_eq!(ud1_extent(&bytes(hex).unwrap()), None, "{hex}");
    }
}
#[test]
fn normal_flow_wire_rejects_unknown_tags_and_keeps_the_scope_visible() {
    let evidence = NormalFlowEvidence::empty();
    let value = serde_json::to_value(&evidence).unwrap();
    assert_eq!(value["kind"], "local_normal_completion");
    assert_eq!(value["scope"], SCOPE);
    let mut wrong = value;
    wrong["kind"] = "whole_machine_completion".into();
    assert!(serde_json::from_value::<NormalFlowEvidence>(wrong).is_err());
}

fn scoped_input(
    source: CandidateSite,
    receipt: TerminalReceipt,
) -> super::super::guard_admission::GuardInput {
    use super::super::guard_admission as guard;
    let mut normal = NormalFlowEvidence::empty();
    normal.terminals.push(receipt);
    guard::GuardInput {
        snapshot: "terminal-fixture".into(),
        artifact_sha256: "1".repeat(64),
        query_scope_sha256: "2".repeat(64),
        preparation_sha256: "3".repeat(64),
        platform: "windows-amd64".into(),
        roots: vec![guard::Root {
            site: source.site.clone(),
            function_entry: true,
            anchor_sha256: "4".repeat(64),
        }],
        seeds: vec![],
        activation: guard::Activation {
            thread_id: 1,
            frame_activation: "terminal-root".into(),
        },
        premises: vec![],
        producer: guard::Producer {
            helper_sha256: "5".repeat(64),
            runtime_sha256: "6".repeat(64),
            decoder_sha256: "7".repeat(64),
            projection: guard::PRODUCER_PROFILE.into(),
        },
        policy: guard::PROFILE.into(),
        model_version: guard::MODEL_VERSION.into(),
        model_sha256: guard::model_identity(),
        limits: guard::Limits::default(),
        candidate_epoch: 1,
        closure_complete: true,
        barriers: vec![],
        sites: vec![source],
        normal_flow: Some(normal),
    }
}
#[test]
fn explicit_terminal_scope_closes_only_normal_coverage_and_binds_source_epoch_and_effects() {
    use super::super::guard_admission as guard;
    for name in ["int3", "ud2", "ud1"] {
        let (source, receipt, _) = case(name);
        let input = scoped_input(source, receipt);
        let report = guard::certify_guards(&input).unwrap();
        assert!(report.stop.is_none());
        guard::replay_report(&input, &report).unwrap();
        assert_eq!(guard::normal_flow_scope(&report), Some(SCOPE));
        let mut missing = input.clone();
        missing.normal_flow.as_mut().unwrap().terminals.clear();
        assert_eq!(
            guard::certify_guards(&missing).unwrap().stop.as_deref(),
            Some("candidate-coverage-incomplete")
        );
        let mut wrong = input.clone();
        wrong.normal_flow.as_mut().unwrap().scope = "whole-machine-completion".into();
        assert!(guard::certify_guards(&wrong).is_err());
        let mut stale = input.clone();
        stale.candidate_epoch += 1;
        assert!(guard::replay_report(&stale, &report).is_err());
        let va = address(&input.sites[0].site).unwrap();
        let locations =
            std::collections::BTreeSet::from(["memory:any".into(), "state:other".into()]);
        let instruction = crate::Instruction {
            kind: crate::InstructionKind::Stop,
            fall: Default::default(),
            targets: Default::default(),
            complete: true,
            uses: locations.clone(),
            may_defs: locations.clone(),
            must_defs: Default::default(),
        };
        let mut request = crate::AnalysisRequest {
            snapshot_id: input.snapshot.clone(),
            input_kind: crate::InputKind::Dump,
            addresses: [va].into(),
            entry_points: [va].into(),
            locations,
            instructions: [(va, instruction)].into(),
            captured: [va].into(),
            decodable: [va].into(),
            ..crate::AnalysisRequest::default()
        };
        guard::validate_normal_flow_request(&input, &request).unwrap();
        crate::bap::guard_admission_tests::export_caller_receipt_unit(
            &format!("terminal-{name}"),
            &input,
            &report,
            &request,
        );
        let mut omitted = input.clone();
        omitted.normal_flow.as_mut().unwrap().terminals.clear();
        assert!(
            guard::validate_normal_flow_request(&omitted, &request).is_err(),
            "a decodable Stop cannot lose its terminal proof"
        );
        request
            .instructions
            .get_mut(&va)
            .unwrap()
            .must_defs
            .insert("memory:any".into());
        assert!(guard::validate_normal_flow_request(&input, &request).is_err());
    }
}
