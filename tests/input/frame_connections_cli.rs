use std::process::Command;
fn rejects(options: &[&str], message: &str) {
    let output = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "/nonexistent/connections.dmp",
            "--decoder-reference",
            "/nonexistent/decoder",
            "--format",
            "json",
        ])
        .args(options)
        .output()
        .unwrap();
    assert!(!output.status.success());
    let error = String::from_utf8_lossy(&output.stderr);
    assert!(error.contains(message), "{error}");
}
#[test]
fn validates_connection_mode_before_capture_io() {
    rejects(&["--frame-connections", "0:1"], "requires N >= M");
    rejects(
        &[
            "--frame-connections",
            "0:0",
            "--example-path-count-bound",
            "0",
        ],
        "invalid connection example count bound",
    );
    rejects(
        &[
            "--frame-connections",
            "0:0",
            "--example-path-count-bound",
            "4098",
        ],
        "invalid connection example count bound",
    );
    rejects(
        &[
            "--frame-structure",
            "0:0",
            "--example-path-count-bound",
            "2",
        ],
        "connection options require",
    );
    rejects(
        &["--frame-connections", "0:0", "--frame-structure", "0:0"],
        "choose one structural or connection",
    );
    rejects(
        &["--frame-connections", "0:0", "--entry", "400100"],
        "cannot combine",
    );
    rejects(
        &["--frame-connections", "0:0", "--path-count-bound", "2"],
        "cannot combine",
    );
    rejects(
        &["--frame-connections", "0:0", "--analysis-backend", "bap"],
        "explicit analysis-backend",
    );
    rejects(&["--frame-connections", "0:0"], "input I/O:");
    rejects(
        &[
            "--frame-connections",
            "0:0",
            "--example-path-count-bound",
            "1",
        ],
        "input I/O:",
    );
}

#[test]
#[ignore = "requires pinned BAP lifter/runtime and LLVM decode helper"]
fn live_connections_preserve_conditional_source_and_independent_stops() {
    use ariadne::investigation::{ConnectionLayerStatus, FrameConnectionLimits};
    use ariadne::reports::{frame_connections, frame_structure};
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let run = |conditional: bool, policy: Option<&std::path::Path>| {
        let mut command = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"));
        command
            .arg(root.join("tests/input/fixtures/guard-frame.dmp"))
            .arg("--decoder-reference")
            .arg(root.join("target/ariadne-llvm-mc"))
            .args(["--frame-connections", "0:0", "--format", "json"]);
        if conditional {
            command.args(["--assume-frame-aligned", "0:400204"]);
        }
        if let Some(path) = policy {
            command.arg("--frame-connections-limits").arg(path);
        }
        let out = command.output().unwrap();
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        out.stdout
    };
    let limits = FrameConnectionLimits::default();
    let baseline = frame_connections::decode(&run(false, None), &limits).unwrap();
    let conditional = frame_connections::decode(&run(true, None), &limits).unwrap();
    assert!(!baseline.source().is_conditional());
    assert!(conditional.source().is_conditional());
    assert_eq!(
        conditional.analysis().conditional_on,
        conditional.source().hypothesis_ids()
    );
    assert!(!conditional.analysis().conditional_on.is_empty());
    if let Some(output) = std::env::var_os("ARIADNE_CONNECTION_CONDITIONAL_SOURCE_OUT") {
        std::fs::write(
            output,
            frame_structure::render_json(conditional.source()).unwrap(),
        )
        .unwrap();
    }
    let mut policy = limits.clone();
    policy.reach_work = 0;
    policy.scc_work = 0;
    let file = root.join("target/frame-connections-live-stop-policy.json");
    std::fs::write(&file, serde_json::to_vec(&policy).unwrap()).unwrap();
    let partial = frame_connections::decode(&run(true, Some(&file)), &limits).unwrap();
    assert_eq!(
        partial.analysis().corridor_status,
        ConnectionLayerStatus::WorkStopped
    );
    assert_eq!(
        partial.analysis().scc_status,
        ConnectionLayerStatus::WorkStopped
    );
    assert_eq!(partial.analysis().examples.len(), 1);
    assert_eq!(partial.analysis().examples[0].edges.len(), 0);
}
