//! Supplied typed-BIL controls for original-control replay in composition.
use super::*;
use crate::bap::ast::{Expr, Stmt, Var};

#[test]
fn mandatory_count_original_control_is_replayed_under_its_declared_profile() {
    let wire: Value =
        serde_json::from_str(include_str!("fixtures/loop-closure/native-wire.json")).unwrap();
    let mut input: guard::GuardInput =
        serde_json::from_value(wire["guard_admission"]["input"].clone()).unwrap();
    let cases: Value =
        serde_json::from_str(include_str!("fixtures/bit-count/contract.json")).unwrap();
    // Numeric count correctness is exercised by the separate fresh-BIL oracle.
    // This unit isolates byte/prefix/profile admission of a typed data transfer.
    let bil = vec![Stmt::Move {
        var: Var {
            name: "RAX".into(),
            index: 0,
            virtual_: false,
            width: 64,
            type_: "imm".into(),
        },
        value: Expr::Int {
            value: "0:64u".into(),
        },
    }];
    for case in cases["cases"].as_array().unwrap() {
        let encoded = case["bytes"].as_str().unwrap();
        let mut source = guard::CandidateSite {
            site: "0x0000000000001000".into(),
            bytes_hex: encoded.into(),
            ast: serde_json::to_string(&bil).unwrap(),
            opaque: false,
            control: guard::CandidateControl {
                kind: guard::ControlKind::Ordinary,
                fall: vec![format!("0x{:016x}", 0x1000 + encoded.len() / 2)],
                targets: vec![],
                complete: true,
            },
        };
        input.policy = guard::ADVANCED_PROFILE.into();
        input.producer.projection = guard::ADVANCED_PRODUCER_PROFILE.into();
        let replay = validate_original_control(&source, &source.control, &input);
        assert!(replay.is_ok());
        for prefix in ["f2", "f3", "64", "67"] {
            source.bytes_hex = format!("{prefix}{encoded}");
            source.control.fall = vec![format!("0x{:016x}", 0x1001 + encoded.len() / 2)];
            assert!(validate_original_control(&source, &source.control, &input).is_err());
        }
        source.bytes_hex = encoded.into();
        source.control.fall = vec![format!("0x{:016x}", 0x1000 + encoded.len() / 2)];
        for profile in [guard::PRODUCER_PROFILE, guard::LEGACY_PRODUCER_PROFILE] {
            input.producer.projection = profile.into();
            input.policy = if profile == guard::PRODUCER_PROFILE {
                guard::PROFILE
            } else {
                guard::LEGACY_PROFILE
            }
            .into();
            assert!(validate_original_control(&source, &source.control, &input).is_err());
        }
    }
}
