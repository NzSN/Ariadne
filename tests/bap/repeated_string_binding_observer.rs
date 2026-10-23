//! Fresh C3/C4 finite-domain admission evidence. Python validates the source,
//! producer envelopes and numeric semantics; this observer exercises Rust's
//! actual typed-AST and profile projection gates for every bound observation.
use super::*;
use std::collections::{BTreeMap, BTreeSet};

fn bytes(value: &str) -> Vec<u8> {
    assert!(value.len().is_multiple_of(2));
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

fn admits(version: u32, code: &[u8]) -> bool {
    match version {
        12 => matches!(code, [0xf3, 0xa4 | 0xaa | 0xa6]),
        13 => code[0] != 0x67 && !matches!(code.last(), Some(0xac | 0xad)),
        14 => code[0] != 0x67,
        15 => true,
        _ => false,
    }
}

#[test]
#[ignore = "requires all 111 fresh selected-producer observations in ARIADNE_REP_BINDING_LIFTS"]
fn fresh_selected_producers_bind_all_memory_rep_profiles() {
    let path = std::env::var_os("ARIADNE_REP_BINDING_LIFTS")
        .expect("ARIADNE_REP_BINDING_LIFTS must identify the fresh producer observations");
    let observations: Vec<serde_json::Value> = serde_json::from_value(
        crate::reports::strict_json_with_limit(&std::fs::read(path).unwrap(), 16 * 1024 * 1024)
            .unwrap(),
    )
    .unwrap();
    assert_eq!(observations.len(), 111);
    let mut seen = BTreeSet::new();
    let mut byte_points = BTreeSet::new();
    let mut counts = BTreeMap::new();
    for observation in observations {
        let profile = observation["profile"].as_str().unwrap();
        let version: u32 = profile
            .strip_prefix("bap-bit-provenance-v")
            .unwrap()
            .parse()
            .unwrap();
        assert!((12..=15).contains(&version));
        let response = &observation["response"];
        let encoded = response["bytes"].as_str().unwrap();
        let code = bytes(encoded);
        assert!(seen.insert((version, encoded.to_owned())));
        byte_points.insert(encoded.to_owned());
        assert!(admits(version, &code));
        assert_eq!(
            observation["addressBits"],
            if code[0] == 0x67 { 32 } else { 64 }
        );
        let lods = matches!(code.last(), Some(0xac | 0xad));
        let producer = if version == 15 && (code[0] == 0x67 || lods) {
            "repAddress"
        } else if lods {
            "lods"
        } else {
            "base"
        };
        assert_eq!(observation["producer"], producer);
        let opcode = observation["opcode"].as_str().unwrap();
        let lift: crate::bap::ast::Lift = serde_json::from_value(serde_json::json!({
            "schema": "ariadne.bap-site/v1", "batch": 0,
            "snapshot": response["snapshot"], "va": response["va"], "status": "decoded",
            "length": response["length"], "bytes": encoded, "opcode": opcode,
            "properties": response.get("properties"), "bil": response["bil"],
        }))
        .unwrap();
        assert_eq!(usize::from(lift.length), code.len());
        assert!(!lift.bil.is_empty());
        lift.validate_ast().unwrap();
        assert_eq!(
            observation["astSha256"],
            crate::reports::sha256(&serde_json::to_vec(&response["bil"]).unwrap())
        );
        // Every row also exercises the adjacent frozen consumer profiles. A
        // valid typed AST never authorizes a wider byte/profile scope by itself.
        for consumer in 12..=15 {
            let consumer_profile = format!("bap-bit-provenance-v{consumer}");
            let projected = project_with_destination_profile(
                &lift.bil,
                opcode,
                &code,
                0x401000,
                None,
                &consumer_profile,
            );
            assert_eq!(
                projected.is_ok(),
                admits(consumer, &code),
                "{consumer_profile} {encoded}: {projected:?}"
            );
            if let Ok(projected) = projected {
                assert!(projected.must_defs.is_empty());
                assert!(projected.may_defs.contains("gpr:rcx:0"));
                assert!(projected.uses.contains("flag:df"));
                assert_eq!(
                    projected.may_defs.contains("memory:any"),
                    matches!(code.last(), Some(0xa4 | 0xa5 | 0xaa | 0xab))
                );
            }
        }
        *counts.entry(version).or_insert(0usize) += 1;
    }
    assert_eq!(byte_points.len(), 56);
    assert_eq!(
        counts,
        BTreeMap::from([(12, 3), (13, 24), (14, 28), (15, 56)])
    );
}
