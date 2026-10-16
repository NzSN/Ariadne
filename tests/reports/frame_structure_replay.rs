//! Opt-in full payload replay through the public API, without input/native code.
use ariadne::investigation::FrameStructureLimits;
use ariadne::reports::frame_structure;
use std::io::Read;
use std::path::Path;

#[test]
#[ignore = "requires an explicitly selected self-contained report, policy and trusted publication binding"]
fn saved_structure_replays_without_native_helpers() {
    let report = std::env::var_os("ARIADNE_FRAME_STRUCTURE_REPORT").expect("report path");
    let policy = std::env::var_os("ARIADNE_FRAME_STRUCTURE_POLICY").expect("host policy path");
    let expected =
        std::env::var("ARIADNE_FRAME_STRUCTURE_BINDING").expect("trusted publication binding");
    let limits: FrameStructureLimits =
        serde_json::from_slice(&std::fs::read(policy).unwrap()).unwrap();
    let mut bytes = Vec::new();
    std::fs::File::open(&report)
        .unwrap()
        .take((limits.max_input_bytes as u64).checked_add(1).unwrap())
        .read_to_end(&mut bytes)
        .unwrap();
    assert!(bytes.len() <= limits.max_input_bytes);
    let mut too_small = limits.clone();
    too_small.max_input_bytes = bytes.len() - 1;
    assert!(frame_structure::decode_expected(&bytes, &too_small, &expected).is_err());
    let bound = frame_structure::decode_expected(&bytes, &limits, &expected).unwrap();
    for (_, frame) in bound.recoveries() {
        assert_eq!(frame.recovery().state().phase(), ariadne::Phase::Recover);
        let metrics = frame.recovery().metrics();
        assert_eq!(metrics.actions, frame.recovery().receipt().visits);
        assert_eq!(metrics.incoming_evaluations, 0);
        assert_eq!(metrics.edge_scans, 0);
        assert_eq!(metrics.transfer_evaluations, 0);
        assert_eq!(metrics.max_reaching_definitions_at_site, 0);
    }
    assert_eq!(
        frame_structure::render_json(&bound).unwrap().as_bytes(),
        bytes
    );
    let directory = Path::new(&report).parent().unwrap();
    assert_eq!(
        frame_structure::render_text(&bound).unwrap(),
        std::fs::read_to_string(directory.join("frame-structure.txt")).unwrap()
    );
    assert_eq!(
        frame_structure::render_dot(&bound).unwrap(),
        std::fs::read_to_string(directory.join("frame-structure.dot")).unwrap()
    );
    println!(
        "standalone structural replay: frames={}, maps={}, visits={}, native_helpers=unused",
        bound.chain().frames.len(),
        bound.frames().len(),
        bound
            .recoveries()
            .iter()
            .map(|(_, f)| f.recovery().receipt().visits)
            .sum::<u64>()
    );
}
