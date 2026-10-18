use super::*;
#[test]
fn independent_service_sequence_and_arrival_fairness() {
    let oracle: serde_json::Value = serde_json::from_str(include_str!(
        "../investigation/fixtures/frame_question_oracle.json"
    ))
    .unwrap();
    let mut queue = FairQueue::default();
    for (band, values) in oracle["scheduler"]["bands"]
        .as_array()
        .unwrap()
        .iter()
        .enumerate()
    {
        for value in values.as_array().unwrap() {
            queue.push(band, value.as_u64().unwrap());
        }
    }
    for expected in oracle["scheduler"]["first_twelve"].as_array().unwrap() {
        let (band, value) = queue.pop().unwrap();
        assert_eq!(value, expected.as_u64().unwrap());
        queue.push(band, value);
    }
    queue.push(2, 99);
    assert!((0..8).any(|_| {
        let (b, v) = queue.pop().unwrap();
        queue.push(b, v);
        v == 99
    }));
    assert_eq!(queue.len(), 5);
}
