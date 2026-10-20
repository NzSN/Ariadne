use super::*;
use serde_json::json;
fn fixture() -> Value {
    json!({"phase":"done","pending":[],"visited":["0x0000000000000001"],"decoded":["0x0000000000000001"],"provenance":[],"edges":[],"obligations":[],"slice":[],
        "definition_dictionary":[{"loc":"rax","site":"0x0000000000000001","origin":"entry"}],
        "definition_sets":[[],[0]],"reaching":[{"address":"0x0000000000000001","definitions_ref":1}]})
}
#[test]
fn dictionary_expansion_is_lossless_and_rejects_bad_indices_duplicates_and_order() {
    let value = fixture();
    let observation = serde_json::from_value::<DictionaryObservation>(value.clone())
        .unwrap()
        .expand()
        .unwrap();
    assert_eq!(observation.reaching[0].definitions[0].loc, "rax");
    for mutation in 0..5 {
        let mut v = value.clone();
        match mutation {
            0 => v["definition_sets"][1] = json!([9]),
            1 => v["definition_sets"][1] = json!([0, 0]),
            2 => v["definition_sets"] = json!([[], [], [0]]),
            3 => v["reaching"][0]["definitions_ref"] = json!(9),
            _ => {
                v["definition_dictionary"] = json!([
                    v["definition_dictionary"][0].clone(),
                    v["definition_dictionary"][0].clone()
                ])
            }
        }
        assert!(
            serde_json::from_value::<DictionaryObservation>(v)
                .unwrap()
                .expand()
                .is_err(),
            "mutation {mutation}"
        );
    }
}
#[test]
fn compact_input_cannot_amplify_beyond_the_expanded_link_budget() {
    let mut v = fixture();
    v["definition_dictionary"] = json!(
        (0..4096)
            .map(|i| json!({"loc":format!("cell{i}"),"site":"0x0000000000000001","origin":"entry"}))
            .collect::<Vec<_>>()
    );
    v["definition_sets"] = json!([(0..4096).collect::<Vec<_>>()]);
    v["reaching"] = json!(
        (0..4097)
            .map(|i| json!({"address":format!("0x{i:016x}"),"definitions_ref":0}))
            .collect::<Vec<_>>()
    );
    let error = serde_json::from_value::<DictionaryObservation>(v)
        .unwrap()
        .expand()
        .unwrap_err();
    assert!(
        error
            .to_string()
            .contains("expanded completed definition budget")
    );
}

fn bitmap_fixture() -> (crate::AnalysisRequest, Value) {
    use crate::*;
    let r = AnalysisRequest {
        snapshot_id: "bitmap-fixture".into(),
        addresses: [1, 2].into(),
        locations: ["memory".into()].into(),
        entry_points: [1].into(),
        captured: [1, 2].into(),
        decodable: [1, 2].into(),
        input_kind: InputKind::Dump,
        instructions: [
            (
                1,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [2].into(),
                    may_defs: ["memory".into()].into(),
                    complete: true,
                    ..Instruction::default()
                },
            ),
            (
                2,
                Instruction {
                    kind: InstructionKind::Stop,
                    complete: true,
                    ..Instruction::default()
                },
            ),
        ]
        .into(),
        ..AnalysisRequest::default()
    };
    let v = json!({"phase":"done","pending":[],"visited":["0x0000000000000001","0x0000000000000002"],
        "decoded":["0x0000000000000001","0x0000000000000002"],
        "provenance":[{"address":"0x0000000000000001","source":"captured"},{"address":"0x0000000000000002","source":"captured"}],
        "edges":[{"src":"0x0000000000000001","dst":"0x0000000000000002","kind":"next"}],"obligations":[],"slice":[],
        "definition_dictionary":[{"loc":"memory","site":"0x0000000000000001","origin":"entry"},
            {"loc":"memory","site":"0x0000000000000001","origin":"instruction"}],
        "definition_bitmaps":["1","3"],"reaching":[{"address":"0x0000000000000001","definitions_ref":0},
            {"address":"0x0000000000000002","definitions_ref":1}]});
    (r, v)
}
fn bind_bitmap(r: &crate::AnalysisRequest, v: Value) -> Result<crate::AnalysisState, Error> {
    let wire: BitmapObservation = serde_json::from_value(v)?;
    let (metadata, membership) = wire.split();
    let mut state = super::super::core_adapter::decode_state(r, &metadata)?;
    membership.bind(r, &mut state)?;
    Ok(state)
}
#[test]
fn bitmap_completion_is_lossless_and_rejects_tampered_membership_and_universe() {
    let (r, v) = bitmap_fixture();
    assert_eq!(
        bind_bitmap(&r, v.clone()).unwrap(),
        crate::Analyzer::new(r.clone()).unwrap().finish().state
    );
    for mutation in 0..10 {
        let mut v = v.clone();
        match mutation {
            0 => v["definition_bitmaps"][0] = json!("5"), // padding bit
            1 => v["definition_bitmaps"][0] = json!("A"),
            2 => v["definition_bitmaps"][0] = json!("01"),
            3 => v["definition_bitmaps"][1] = json!("1"),
            4 => v["reaching"][0]["definitions_ref"] = json!(2),
            5 => v["definition_dictionary"][1]["site"] = json!("0x0000000000000002"),
            6 => v["definition_dictionary"][1]["loc"] = json!("other"),
            7 => v["definition_dictionary"]
                .as_array_mut()
                .unwrap()
                .swap(0, 1),
            8 => v["reaching"]
                .as_array_mut()
                .unwrap()
                .pop()
                .map(|_| ())
                .unwrap(),
            _ => v["reaching"][0]["address"] = json!("0x0000000000000003"),
        }
        assert!(bind_bitmap(&r, v).is_err(), "mutation {mutation}");
    }
}
