//! Explicit source-bound saved replay; usable with bap only and no helpers.
use ariadne::investigation::{FrameConnectionLimits, summarize_frame_connections};
use ariadne::reports::{frame_connections, frame_structure};
use std::path::PathBuf;
#[test]
#[ignore = "requires an explicitly selected saved source/policy/binding and output directory"]
fn saved_source_connection_product_and_replay() {
    let path = PathBuf::from(std::env::var_os("ARIADNE_CONNECTION_SOURCE").expect("source report"));
    let policy =
        PathBuf::from(std::env::var_os("ARIADNE_CONNECTION_POLICY").expect("source policy"));
    let binding = std::env::var("ARIADNE_CONNECTION_BINDING").expect("trusted source binding");
    let output = PathBuf::from(std::env::var_os("ARIADNE_CONNECTION_OUT").expect("output"));
    std::fs::create_dir_all(&output).unwrap();
    let bytes = std::fs::read(path).unwrap();
    let limits = FrameConnectionLimits {
        structural: serde_json::from_slice(&std::fs::read(policy).unwrap()).unwrap(),
        ..Default::default()
    };
    println!("decoding structural source ({} bytes)", bytes.len());
    let source = frame_structure::decode_expected(&bytes, &limits.structural, &binding).unwrap();
    println!("structural source decoded");
    assert_eq!(
        frame_structure::render_json(&source).unwrap().as_bytes(),
        bytes
    );
    println!("source rendering preserved; computing connections");
    let bound = summarize_frame_connections(source, 2, limits.clone()).unwrap();
    assert_eq!(
        frame_structure::render_json(bound.source())
            .unwrap()
            .as_bytes(),
        bytes
    );
    assert!(
        bound
            .source()
            .recoveries()
            .iter()
            .all(
                |(_, r)| r.recovery().state().phase() == ariadne::Phase::Recover
                    && r.recovery().metrics().incoming_evaluations == 0
            )
    );
    println!("connections computed; publishing");
    let json = frame_connections::render_json(&bound).unwrap();
    let value: serde_json::Value = serde_json::from_str(&json).unwrap();
    assert_eq!(value["source_json"].as_str().unwrap().as_bytes(), bytes);
    let trusted = value["publication_binding"].as_str().unwrap().to_owned();
    std::fs::write(output.join("frame-connections.json"), &json).unwrap();
    std::fs::write(
        output.join("frame-connections.txt"),
        frame_connections::render_text(&bound).unwrap(),
    )
    .unwrap();
    std::fs::write(
        output.join("frame-connections.dot"),
        frame_connections::render_dot(&bound).unwrap(),
    )
    .unwrap();
    std::fs::write(
        output.join("limits.json"),
        serde_json::to_vec_pretty(&limits).unwrap(),
    )
    .unwrap();
    drop(bound);
    drop(value);
    println!("publication saved; replaying connections");
    let replay = frame_connections::decode_expected(json.as_bytes(), &limits, &trusted).unwrap();
    assert_eq!(frame_connections::render_json(&replay).unwrap(), json);
    println!(
        "source-preserved; nodes={} edges={} corridor={} SCC={} cyclic={} examples={} status={:?}",
        replay.analysis().nodes.len(),
        replay.analysis().edges.len(),
        replay.analysis().corridor.len(),
        replay.analysis().components.len(),
        replay
            .analysis()
            .components
            .iter()
            .filter(|c| c.cyclic)
            .count(),
        replay.analysis().examples.len(),
        replay.analysis().connection
    );
}
