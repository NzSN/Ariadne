//! Independent finite memory-MOV admission and byte-origin projection observer.
use super::*;
use std::collections::BTreeSet;

fn bytes(value: &str) -> Vec<u8> {
    assert!(value.len().is_multiple_of(2));
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|part| u8::from_str_radix(std::str::from_utf8(part).unwrap(), 16).unwrap())
        .collect()
}

fn expected_members() -> BTreeSet<(String, String)> {
    let mut expected = BTreeSet::new();
    for target in ["windows-amd64", "linux-amd64"] {
        for address32 in [false, true] {
            for rex in [
                None,
                Some(0x40),
                Some(0x41),
                Some(0x42),
                Some(0x43),
                Some(0x44),
                Some(0x45),
                Some(0x46),
                Some(0x47),
            ] {
                for opcode in [0x88, 0x8a] {
                    for register in [0, 4] {
                        for mode in 0..3 {
                            for rm in [0, 4, 5] {
                                let sibs = if rm == 4 {
                                    vec![
                                        Some(0),
                                        Some(5),
                                        Some(0x20),
                                        Some(0x25),
                                        Some(0xc0),
                                        Some(0xc5),
                                        Some(0xe0),
                                        Some(0xe5),
                                    ]
                                } else {
                                    vec![None]
                                };
                                for sib in sibs {
                                    let width = if mode == 1 {
                                        1
                                    } else if mode == 2
                                        || mode == 0
                                            && (rm == 5 || sib.is_some_and(|value| value & 7 == 5))
                                    {
                                        4
                                    } else {
                                        0
                                    };
                                    let displacements: &[i32] = match width {
                                        1 => &[-128, 0, 127],
                                        4 => &[i32::MIN, 0, i32::MAX],
                                        _ => &[0],
                                    };
                                    for displacement in displacements {
                                        let mut code =
                                            if address32 { vec![0x67] } else { Vec::new() };
                                        code.extend(rex);
                                        code.extend([opcode, (mode << 6) | (register << 3) | rm]);
                                        code.extend(sib);
                                        code.extend(&displacement.to_le_bytes()[..width]);
                                        assert!(expected.insert((
                                            target.to_owned(),
                                            code.iter().map(|byte| format!("{byte:02x}")).collect()
                                        )));
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    assert_eq!(expected.len(), 11520);
    expected
}

#[test]
#[ignore = "requires fresh BAP/LLVM memory observations in ARIADNE_MOV8_MEMORY_OBSERVATIONS"]
fn fresh_memory_mov8_observations_preserve_origins_and_prefix_refusals() {
    let path =
        std::env::var_os("ARIADNE_MOV8_MEMORY_OBSERVATIONS").expect("fresh observations required");
    let document =
        crate::reports::strict_json_with_limit(&std::fs::read(path).unwrap(), 96 * 1024 * 1024)
            .unwrap();
    let rows = document["rows"].as_array().unwrap();
    assert_eq!(rows.len(), 11520);
    let mut seen = BTreeSet::new();
    let mut supported = 0;
    let mut refused = 0;
    for row in rows {
        let response = &row["response"];
        let encoded = response["bytes"].as_str().unwrap();
        assert_eq!(row["point"]["bytes"], encoded);
        assert!(seen.insert((
            row["target"].as_str().unwrap().to_owned(),
            encoded.to_owned()
        )));
        let code = bytes(encoded);
        let address32 = code[0] == 0x67;
        let mut cursor = usize::from(address32);
        let rex = if (0x40..=0x47).contains(&code[cursor]) {
            cursor += 1;
            code[cursor - 1]
        } else {
            0
        };
        let opcode = code[cursor];
        let modrm = code[cursor + 1];
        cursor += 2;
        let mode = modrm >> 6;
        let reg = (modrm >> 3) & 7;
        let rm = modrm & 7;
        assert!(mode < 3 && matches!(opcode, 0x88 | 0x8a));
        let sib = (rm == 4).then(|| code[cursor]);
        let bank = if rex == 0 && reg == 4 {
            0
        } else {
            reg + if rex & 4 != 0 { 8 } else { 0 }
        };
        let offset = if rex == 0 && reg == 4 { 8 } else { 0 };
        let data = crate::effects::RegisterView::new(bank, offset, 8).unwrap();
        let reference =
            crate::llvm_mc::protocol::parse(row["reference"].as_str().unwrap()).unwrap();
        let va = u64::from_str_radix(
            response["va"].as_str().unwrap().trim_start_matches("0x"),
            16,
        )
        .unwrap();
        assert_eq!(reference.decoded.address, va);
        assert_eq!(reference.decoded.length as usize, code.len());
        assert_eq!(
            reference.decoded.kind,
            Some(crate::InstructionKind::Ordinary)
        );
        assert_eq!(reference.decoded.status, "ok");
        assert_eq!(reference.operands.len(), 6);
        assert_eq!(reference.opcode, response["opcode"].as_str().unwrap());
        let crate::llvm_mc::protocol::RawOperand::Register(name) =
            &reference.operands[if opcode == 0x8a { 0 } else { 5 }]
        else {
            panic!("MOV8 data operand is not a register")
        };
        assert_eq!(
            crate::effects::RegisterView::parse(name),
            Some(data.clone())
        );
        let lift: crate::bap::ast::Lift = serde_json::from_value(response.clone()).unwrap();
        lift.validate_ast().unwrap();
        assert_eq!(
            row["astSha256"],
            crate::reports::sha256(&serde_json::to_vec(&response["bil"]).unwrap())
        );
        let guarded =
            crate::bap::admission::guarded_prefix_with_profile(&code, "bap-bit-provenance-v6");
        let result = project_with_destination_profile(
            &lift.bil,
            &reference.opcode,
            &code,
            va,
            (opcode == 0x8a).then_some(&data),
            "bap-bit-provenance-v6",
        );
        if address32 {
            assert_eq!(row["disposition"], "U");
            assert!(guarded && result.is_err(), "{encoded}");
            refused += 1;
            continue;
        }
        assert_eq!(row["disposition"], "S");
        assert!(!guarded);
        let projection = result.unwrap();
        let mut expected_uses = crate::LocationSet::new();
        let ip_relative = mode == 0 && rm == 5;
        let no_base = mode == 0 && sib.is_some_and(|value| value & 7 == 5);
        if !ip_relative && !no_base {
            let base = sib.map_or(rm, |value| value & 7) + if rex & 1 != 0 { 8 } else { 0 };
            expected_uses.extend(
                crate::effects::RegisterView::new(base, 0, 64)
                    .unwrap()
                    .reads(),
            );
        }
        if let Some(sib) = sib {
            let index = (sib >> 3) & 7;
            if index != 4 || rex & 2 != 0 {
                expected_uses.extend(
                    crate::effects::RegisterView::new(
                        index + if rex & 2 != 0 { 8 } else { 0 },
                        0,
                        64,
                    )
                    .unwrap()
                    .reads(),
                );
            }
        }
        // Queried PC-relative addresses are BAP constants bound to VA/extent;
        // RIP is outside the provenance catalogue, not an independent input.
        if opcode == 0x8a {
            expected_uses.insert("memory:any".into());
            assert_eq!(projection.may_defs, data.replacements(), "{encoded}");
            assert_eq!(projection.must_defs, data.replacements(), "{encoded}");
        } else {
            expected_uses.extend(data.reads());
            assert_eq!(
                projection.may_defs,
                ["memory:any".to_owned()].into(),
                "{encoded}"
            );
            assert!(projection.must_defs.is_empty(), "{encoded}");
        }
        assert_eq!(projection.uses, expected_uses, "{encoded}");
        assert!(
            projection.gaps.is_empty() && projection.targets.is_empty(),
            "{encoded}"
        );
        supported += 1;
    }
    assert_eq!((supported, refused), (5760, 5760));
    assert_eq!(seen, expected_members());
}
