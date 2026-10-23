//! Actual producer/decoder observations for the finite register-byte MOV domain.
//! The byte-field oracle is independent of the Python domain enumerator. These
//! tests bind the existing projection contract; they add no opcode semantics.
use super::*;
use std::collections::BTreeSet;

fn decode_bytes(value: &str) -> Vec<u8> {
    assert!(value.len().is_multiple_of(2));
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

fn byte_register(field: u8, extension: bool, rex: bool) -> (u8, u8) {
    if extension {
        (field + 8, 0)
    } else if !rex && field >= 4 {
        (field - 4, 8)
    } else {
        (field, 0)
    }
}

#[test]
#[ignore = "requires fresh BAP/LLVM observations in ARIADNE_MOV8_BINDING_OBSERVATIONS"]
fn fresh_mov8_domain_observations_match_byte_origins() {
    let path = std::env::var_os("ARIADNE_MOV8_BINDING_OBSERVATIONS")
        .expect("fresh MOV8 binding observations required");
    let document =
        crate::reports::strict_json_with_limit(&std::fs::read(path).unwrap(), 32 * 1024 * 1024)
            .unwrap();
    let rows = document["rows"].as_array().unwrap();
    assert_eq!(rows.len(), 1280);
    let mut expected = BTreeSet::new();
    for target in ["windows-amd64", "linux-amd64"] {
        for prefix in [None, Some(0x40), Some(0x41), Some(0x44), Some(0x45)] {
            for opcode in [0x88, 0x8a] {
                for modrm in 0xc0..=0xff {
                    let mut code = prefix.into_iter().collect::<Vec<_>>();
                    code.extend([opcode, modrm]);
                    let encoded = code.iter().map(|b| format!("{b:02x}")).collect::<String>();
                    assert!(expected.insert((target.to_owned(), encoded)));
                }
            }
        }
    }
    let mut seen = BTreeSet::new();
    for row in rows {
        let target = row["target"].as_str().unwrap();
        let response = &row["response"];
        let encoded = response["bytes"].as_str().unwrap();
        assert!(seen.insert((target.to_owned(), encoded.to_owned())));
        let code = decode_bytes(encoded);
        assert!((2..=3).contains(&code.len()));
        let rex = if code.len() == 3 { code[0] } else { 0 };
        assert!(matches!(rex, 0 | 0x40 | 0x41 | 0x44 | 0x45));
        let opcode = code[code.len() - 2];
        let modrm = code[code.len() - 1];
        assert!(matches!(opcode, 0x88 | 0x8a));
        assert_eq!(modrm >> 6, 3);
        let reg = byte_register((modrm >> 3) & 7, rex & 4 != 0, rex != 0);
        let rm = byte_register(modrm & 7, rex & 1 != 0, rex != 0);
        let (dest, source) = if opcode == 0x88 { (rm, reg) } else { (reg, rm) };
        let destination = crate::effects::RegisterView::new(dest.0, dest.1, 8).unwrap();
        let origin = crate::effects::RegisterView::new(source.0, source.1, 8).unwrap();
        let reference =
            crate::llvm_mc::protocol::parse(row["reference"].as_str().unwrap()).unwrap();
        let va = u64::from_str_radix(
            response["va"].as_str().unwrap().trim_start_matches("0x"),
            16,
        )
        .unwrap();
        assert_eq!(reference.decoded.address, va);
        assert_eq!(reference.decoded.length as usize, code.len());
        assert_eq!(reference.decoded.status, "ok");
        assert_eq!(
            reference.decoded.kind,
            Some(crate::InstructionKind::Ordinary)
        );
        assert_eq!(reference.operands.len(), 2);
        for (operand, view) in reference.operands.iter().zip([&destination, &origin]) {
            let crate::llvm_mc::protocol::RawOperand::Register(name) = operand else {
                panic!("non-register MOV operand")
            };
            assert_eq!(
                crate::effects::RegisterView::parse(name).as_ref(),
                Some(view)
            );
        }
        assert_eq!(reference.opcode, response["opcode"].as_str().unwrap());
        let lift: crate::bap::ast::Lift = serde_json::from_value(response.clone()).unwrap();
        assert_eq!(usize::from(lift.length), code.len());
        assert!(!lift.bil.is_empty());
        lift.validate_ast().unwrap();
        assert_eq!(
            row["astSha256"],
            crate::reports::sha256(&serde_json::to_vec(&response["bil"]).unwrap())
        );
        let projection = project_with_destination_profile(
            &lift.bil,
            &reference.opcode,
            &code,
            va,
            Some(&destination),
            "bap-bit-provenance-v6",
        )
        .unwrap();
        assert_eq!(projection.uses, origin.reads(), "{encoded}");
        assert_eq!(projection.may_defs, destination.replacements(), "{encoded}");
        // Reverse-encoding self moves retain the existing v6 conservative
        // no-kill behavior. Every reported definite write must still be sound.
        let must = if opcode == 0x8a && dest == source {
            crate::LocationSet::new()
        } else {
            destination.replacements()
        };
        assert_eq!(projection.must_defs, must, "{encoded}");
        assert!(projection.targets.is_empty(), "{encoded}");
        assert!(projection.gaps.is_empty(), "{encoded}");
    }
    assert_eq!(seen, expected);
}
