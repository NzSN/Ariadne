//! A saved-source entry point requiring BAP data codecs, with no input/helper feature.
use ariadne::investigation::*;
use ariadne::reports::{frame_question, frame_structure};
use std::path::PathBuf;
#[test]
#[ignore = "requires explicitly frozen source, policy, trusted binding, request and output"]
fn saved_source_question_product_and_replay() {
    let path = |name| PathBuf::from(std::env::var_os(name).expect(name));
    let source_bytes = std::fs::read(path("ARIADNE_QUESTION_SOURCE")).unwrap();
    let policy: FrameQuestionLimits =
        serde_json::from_slice(&std::fs::read(path("ARIADNE_QUESTION_POLICY")).unwrap()).unwrap();
    let binding = std::env::var("ARIADNE_QUESTION_SOURCE_BINDING").unwrap();
    let request: FrameQuestionRequest =
        serde_json::from_slice(&std::fs::read(path("ARIADNE_QUESTION_REQUEST")).unwrap()).unwrap();
    request.validate(&policy).unwrap();
    let source =
        frame_structure::decode_expected(&source_bytes, &policy.structural, &binding).unwrap();
    assert_eq!(
        source.question(),
        &FrameStructureQuestion {
            from_frame: request.from_frame,
            to_frame: request.to_frame
        }
    );
    let bound = investigate_frame_question(
        source,
        request.question,
        FrameQuestionEvidence::default(),
        policy.clone(),
    )
    .unwrap();
    assert_eq!(
        frame_structure::render_json(bound.source().structure())
            .unwrap()
            .as_bytes(),
        source_bytes
    );
    assert!(
        bound
            .source()
            .structure()
            .recoveries()
            .iter()
            .all(|(_, r)| r.recovery().metrics().incoming_evaluations == 0)
    );
    let out = path("ARIADNE_QUESTION_OUT");
    std::fs::create_dir_all(&out).unwrap();
    let json = frame_question::render_json(&bound).unwrap();
    std::fs::write(out.join("frame-question.json"), &json).unwrap();
    std::fs::write(
        out.join("frame-question.txt"),
        frame_question::render_text(&bound).unwrap(),
    )
    .unwrap();
    std::fs::write(
        out.join("frame-question.dot"),
        frame_question::render_dot(&bound).unwrap(),
    )
    .unwrap();
    drop(bound);
    let checked = frame_question::decode(json.as_bytes(), &policy).unwrap();
    assert_eq!(frame_question::render_json(&checked).unwrap(), json);
    println!(
        "verdict={:?} values={} origins={:?} unresolved={} resolution={:?}",
        checked.assessment().verdict,
        checked.assessment().values.len(),
        checked.assessment().candidate_count,
        checked.assessment().obligations.len(),
        checked.assessment().layers.resolution
    );
}
#[test]
#[ignore = "requires an explicitly selected saved question publication and host policy"]
fn saved_question_publication_replay() {
    let bytes = std::fs::read(std::env::var_os("ARIADNE_QUESTION_PUBLICATION").unwrap()).unwrap();
    let policy: FrameQuestionLimits = serde_json::from_slice(
        &std::fs::read(std::env::var_os("ARIADNE_QUESTION_POLICY").unwrap()).unwrap(),
    )
    .unwrap();
    let checked = frame_question::decode(&bytes, &policy).unwrap();
    assert_eq!(
        frame_question::render_json(&checked).unwrap().as_bytes(),
        bytes
    );
}
