//! Exact mandatory-prefix admission and fresh producer/decode effects.
use super::*;
use crate::bap::{Config, Session, admission};
use crate::effects::PreparationOptions;
use crate::llvm_mc::{DecoderTarget, decode_captured_batch};
use serde_json::Value as Json;
use std::path::PathBuf;

const PROFILE: &str = "bap-bit-provenance-v10";
fn cases() -> Vec<Json> {
    serde_json::from_str::<Json>(include_str!("fixtures/bit-count/contract.json")).unwrap()["cases"]
        .as_array()
        .unwrap()
        .clone()
}
fn bytes(hex: &str) -> Vec<u8> {
    (0..hex.len())
        .step_by(2)
        .map(|at| u8::from_str_radix(&hex[at..at + 2], 16).unwrap())
        .collect()
}
fn opcode(case: &Json) -> String {
    format!(
        "{}{}{}",
        case["operation"].as_str().unwrap().to_ascii_uppercase(),
        case["width"].as_u64().unwrap(),
        if case["source"] == "register" {
            "rr"
        } else {
            "rm"
        }
    )
}
fn data() -> Vec<Stmt> {
    vec![Stmt::Move {
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
    }]
}

#[test]
fn mandatory_count_prefix_permission_is_exact_and_profile_scoped() {
    for case in cases() {
        let encoded = bytes(case["bytes"].as_str().unwrap());
        let expected = opcode(&case);
        for profile in [PROFILE, "bap-bit-provenance-v11"] {
            assert_eq!(
                admission::mandatory_count_opcode(&encoded, profile),
                Some(expected.as_str())
            );
            admission::admit_with_profile(&data(), &expected, &encoded, profile).unwrap();
            assert!(admission::admit_with_profile(&data(), "BSR64rr", &encoded, profile).is_err());
            assert!(admission::admit_with_profile(&[], &expected, &encoded, profile).is_err());
            for length in 0..encoded.len() {
                assert!(admission::mandatory_count_opcode(&encoded[..length], profile).is_none());
            }
            for prefix in [0xf0, 0xf2, 0xf3, 0x64, 0x65, 0x67, 0x48] {
                let altered: Vec<_> = [prefix]
                    .into_iter()
                    .chain(encoded.iter().copied())
                    .collect();
                assert!(
                    admission::admit_with_profile(&data(), &expected, &altered, profile).is_err()
                );
            }
            let mut altered = encoded.clone();
            altered.push(0x90);
            assert!(admission::admit_with_profile(&data(), &expected, &altered, profile).is_err());
            let mut altered = encoded.clone();
            *altered.last_mut().unwrap() = 0x04;
            assert!(admission::admit_with_profile(&data(), &expected, &altered, profile).is_err());
            let mut altered = encoded.clone();
            let repeat = altered.iter().position(|b| *b == 0xf3).unwrap();
            altered[repeat] = 0xf2;
            assert!(admission::admit_with_profile(&data(), &expected, &altered, profile).is_err());
        }
        for profile in ["bap-bit-provenance-v6", "bap-bit-provenance-v9", "unknown"] {
            assert!(admission::mandatory_count_opcode(&encoded, profile).is_none());
            assert!(admission::admit_with_profile(&data(), &expected, &encoded, profile).is_err());
        }
    }
    assert!(admission::admit_with_profile(&data(), "PAUSE", &[0xf3, 0x90], PROFILE).is_err());
}

#[test]
#[ignore = "requires the pinned BAP runtime/helper and LLVM MC decode reference"]
fn actual_bit_count_forms_preserve_defined_and_unknown_flag_effects() {
    let cases = cases();
    let candidates: BTreeMap<_, _> = cases
        .iter()
        .enumerate()
        .map(|(i, case)| {
            (
                0x501000 + i as u64 * 32,
                bytes(case["bytes"].as_str().unwrap()),
            )
        })
        .collect();
    let mut session = Session::start(
        &Config::from_env(),
        "mandatory-count-effects",
        "windows-amd64",
    )
    .unwrap();
    let lifted = session.lift(&candidates).unwrap();
    session.finish().unwrap();
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc")
        });
    let reference = decode_captured_batch(
        "mandatory-count-effects",
        &candidates
            .iter()
            .map(|(va, b)| (*va, Some(b.clone())))
            .collect(),
        &decoder,
        &PreparationOptions::default(),
        DecoderTarget::WindowsAmd64,
    )
    .unwrap();
    for (i, case) in cases.iter().enumerate() {
        let va = 0x501000 + i as u64 * 32;
        let encoded = &candidates[&va];
        let lift = &lifted[&va];
        let site = &reference.sites[&va];
        let opcode = opcode(case);
        assert_eq!(lift.length as usize, encoded.len());
        assert_eq!(site.evidence.length, lift.length);
        assert_eq!(site.evidence.bytes, *encoded);
        assert_eq!(site.evidence.opcode.as_ref(), Some(&opcode));
        assert_eq!(site.instruction.kind, crate::InstructionKind::Ordinary);
        let control = lift.properties.as_ref().unwrap();
        assert!(
            !control.jump
                && !control.conditional
                && !control.indirect
                && !control.call
                && !control.return_
                && !control.control
        );
        let p = project_with_destination_profile(&lift.bil, &opcode, encoded, va, None, PROFILE)
            .unwrap();
        let width = case["width"].as_u64().unwrap() as usize;
        let destination: LocationSet = (0..if width == 16 { 2 } else { 8 })
            .map(|b| format!("gpr:rax:{b}"))
            .collect();
        let flags: LocationSet = ["cf", "pf", "af", "zf", "sf", "of"]
            .into_iter()
            .map(|f| format!("flag:{f}"))
            .collect();
        assert_eq!(
            p.may_defs,
            destination.union(&flags).cloned().collect(),
            "{}",
            case["name"]
        );
        let defined: LocationSet = if case["operation"] == "popcnt" {
            flags
        } else {
            ["flag:cf".into(), "flag:zf".into()].into()
        };
        assert_eq!(
            p.must_defs,
            destination.union(&defined).cloned().collect(),
            "{}",
            case["name"]
        );
        assert!(!p.may_defs.contains("flag:df"));
        let mut required: LocationSet = (0..if case["source"] == "memory" {
            8
        } else {
            width / 8
        })
            .map(|b| format!("gpr:rbx:{b}"))
            .collect();
        if case["source"] == "memory" {
            required.insert("memory:any".into());
        }
        assert!(p.uses.is_superset(&required));
        if case["operation"] == "popcnt" {
            assert_eq!(p.uses, required);
        } else {
            assert!(p.gaps.iter().any(|gap| gap.starts_with("unknown-output:")));
        }
        for profile in ["bap-bit-provenance-v6", "bap-bit-provenance-v9"] {
            assert!(
                project_with_destination_profile(&lift.bil, &opcode, encoded, va, None, profile)
                    .is_err()
            );
        }
    }
}
