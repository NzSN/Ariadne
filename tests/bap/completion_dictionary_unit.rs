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
