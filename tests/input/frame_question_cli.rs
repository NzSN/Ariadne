use ariadne::investigation::*;
use ariadne::reports::frame_question;
use std::{path::PathBuf, process::Command};
fn request(value: u64) -> FrameQuestionRequest {
    FrameQuestionRequest {
        schema: FRAME_QUESTION_REQUEST_SCHEMA.into(),
        from_frame: 1,
        to_frame: 0,
        question: FrameQuestion {
            question: FrameQuestionKind::Alternative {
                frame: 1,
                site: 0x400306,
                destination: 0x40030c,
                edge_kind: FramePathEdgeKind::Taken,
                endpoint: ValueConstraint {
                    point: QuestionPoint {
                        frame: 1,
                        site: 0x400310,
                        moment: QuestionMoment::Before,
                    },
                    bank: 1,
                    width: 64,
                    mask: u64::MAX,
                    value,
                },
            },
            conditions: vec![],
        },
    }
}
fn write(name: &str, value: &impl serde::Serialize) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/frame-question-cli");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join(format!("{}-{name}.json", std::process::id()));
    std::fs::write(&path, serde_json::to_vec(value).unwrap()).unwrap();
    path
}
fn run(
    file: &std::path::Path,
    policy: Option<&std::path::Path>,
    dump: &str,
) -> std::process::Output {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut c = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"));
    c.arg(dump)
        .arg("--decoder-reference")
        .arg(root.join("target/ariadne-llvm-mc"))
        .arg("--frame-question")
        .arg(file)
        .args(["--format", "json"]);
    if let Some(p) = policy {
        c.arg("--frame-question-limits").arg(p);
    }
    c.output().unwrap()
}
#[test]
fn question_options_reject_before_capture_io() {
    let mut q = request(0);
    q.from_frame = 0;
    q.to_frame = 1;
    let file = write("bad-range", &q);
    let out = run(&file, None, "/nonexistent/question.dmp");
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("schema/range"));
    let file = write("valid", &request(0));
    let out = run(&file, None, "/nonexistent/question.dmp");
    assert!(String::from_utf8_lossy(&out.stderr).contains("input I/O"));
    let p = FrameQuestionLimits {
        quantum: 0,
        ..Default::default()
    };
    let policy = write("bad-quantum", &p);
    let out = run(&file, Some(&policy), "/nonexistent/question.dmp");
    assert!(String::from_utf8_lossy(&out.stderr).contains("quantum"));
}
#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM MC helper"]
fn native_question_witness_refutation_conflict_and_stop() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let dump = root.join("tests/input/fixtures/frame_paths/diamond.dmp");
    let check = |name: &str, q: &FrameQuestionRequest, policy: &FrameQuestionLimits| {
        let f = write(name, q);
        let p = write(&format!("{name}-policy"), policy);
        let out = run(&f, Some(&p), dump.to_str().unwrap());
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        let bound = frame_question::decode(&out.stdout, &FrameQuestionLimits::default()).unwrap();
        if let Some(dir) = std::env::var_os("ARIADNE_QUESTION_FIXTURE_OUT") {
            let dir = PathBuf::from(dir);
            std::fs::create_dir_all(&dir).unwrap();
            std::fs::write(dir.join(format!("{name}.json")), &out.stdout).unwrap();
        }
        bound
    };
    let policy = FrameQuestionLimits::default();
    let possible = check("possible", &request(0), &policy);
    assert_eq!(
        possible.assessment().verdict,
        QuestionVerdict::PossibleUnderModel
    );
    assert!(possible.assessment().witness.is_some());
    let refuted = check("refuted", &request(1), &policy);
    assert_eq!(
        refuted.assessment().verdict,
        QuestionVerdict::RefutedUnderModel
    );
    assert!(refuted.assessment().witness.is_none());
    let mut stopped = policy.clone();
    stopped.constraint_work = 0;
    let stopped = check("stopped", &request(1), &stopped);
    assert_eq!(stopped.assessment().verdict, QuestionVerdict::Unknown);
    assert_eq!(
        stopped.assessment().layers.feasibility.status,
        QuestionLayerStatus::WorkStopped
    );
    let mut conflict = request(0);
    let FrameQuestionKind::Alternative { endpoint, .. } = &conflict.question.question else {
        unreachable!()
    };
    let mut c = endpoint.clone();
    c.point.site = 0x400300;
    conflict.question.conditions.push(c.clone());
    c.value = 1;
    conflict.question.conditions.push(c);
    let conflict = check("conflict", &conflict, &policy);
    assert_eq!(
        conflict.assessment().verdict,
        QuestionVerdict::PremiseConflict
    );
}
