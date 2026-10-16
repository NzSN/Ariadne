use super::*;
use serde_json::json;

#[test]
fn evidence_deduplicates_subtrees_and_checks_every_reference() {
    let limits = FrameStructureLimits::default();
    let value = json!({"first":["same",1],"second":["same",1]});
    let mut dictionary = Dictionary::new();
    let id = dictionary.intern(value.clone(), &limits).unwrap();
    let entries = dictionary.entries();
    assert_eq!(entries.len(), 4); // two scalars, one shared array, one object
    let mut decoded = Dictionary::from_entries(entries, &limits).unwrap();
    assert_eq!(decoded.resolve(&id, &limits).unwrap(), value);
    decoded.finish().unwrap();
    assert!(decoded.resolve(&"0".repeat(64), &limits).is_err());
}

#[test]
fn dictionary_publication_limit_is_checked_before_retention() {
    let limits = FrameStructureLimits {
        max_output_bytes: 0,
        ..FrameStructureLimits::default()
    };
    let mut dictionary = Dictionary::new();
    assert!(dictionary.intern(json!("captured bytes"), &limits).is_err());
    assert!(dictionary.nodes.is_empty());
}

#[test]
fn flat_deep_dictionary_cannot_bypass_json_nesting_safety() {
    let limits = FrameStructureLimits {
        max_dictionary_depth: 10_000,
        ..FrameStructureLimits::default()
    };
    let scalar = Node::Scalar { value: Value::Null };
    let mut id = identity(&scalar).unwrap();
    let mut entries = vec![Entry {
        id: id.clone(),
        node: scalar,
    }];
    for _ in 0..5_000 {
        let node = Node::Array { items: vec![id] };
        id = identity(&node).unwrap();
        entries.push(Entry {
            id: id.clone(),
            node,
        });
    }
    let mut dictionary = Dictionary::from_entries(entries, &limits).unwrap();
    assert!(dictionary.resolve(&id, &limits).is_err());
}

#[test]
fn shared_evidence_is_charged_for_each_expanded_use() {
    let producer = FrameStructureLimits::default();
    let mut dictionary = Dictionary::new();
    let id = dictionary
        .intern(
            json!(["x".repeat(128), "x".repeat(128), "x".repeat(128)]),
            &producer,
        )
        .unwrap();
    let mut host = producer;
    host.max_owned_bytes = 300;
    let mut decoded = Dictionary::from_entries(dictionary.entries(), &host).unwrap();
    assert!(decoded.resolve(&id, &host).is_err());
}
