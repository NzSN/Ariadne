use std::process::Command;
fn rejects(options: &[&str], message: &str) {
    let out = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "missing.dmp",
            "--decoder-reference",
            "missing-decoder",
            "--entry",
            "0x401000",
            "--format",
            "json",
        ])
        .args(options)
        .output()
        .unwrap();
    assert!(!out.status.success());
    assert!(
        String::from_utf8_lossy(&out.stderr).contains(message),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
}
#[test]
fn resolver_cli_requires_explicit_mode_and_bounded_nonzero_artifact_allowance() {
    rejects(
        &["--target-resolution-limits", "limits.json"],
        "requires --resolve-indirect-targets",
    );
    rejects(
        &["--resolve-indirect-targets", "--resolve-indirect-targets"],
        "duplicate --resolve-indirect-targets",
    );
    rejects(&["--max-artifact-bytes", "0"], "positive and at most 2 GiB");
    rejects(
        &["--max-artifact-bytes", "2147483649"],
        "positive and at most 2 GiB",
    );
}
#[test]
fn initial_profile_rejects_unsupported_composed_modes() {
    rejects(
        &[
            "--resolve-indirect-targets",
            "--stateflow-input",
            "semantics.json",
        ],
        "cannot combine",
    );
    rejects(
        &[
            "--resolve-indirect-targets",
            "--assess-memory-provenance",
            "0x401000",
            "--memory-access",
            "0",
            "--assessment-only",
        ],
        "cannot combine",
    );
}

#[test]
fn native_response_timeout_is_explicit_and_bounded() {
    rejects(&["--bap-core-response-timeout-ms", "0"], "1..60000 ms");
    rejects(&["--bap-core-response-timeout-ms", "60001"], "1..60000 ms");
    rejects(
        &[
            "--bap-core-response-timeout-ms",
            "30000",
            "--bap-core-response-timeout-ms",
            "30000",
        ],
        "unknown or duplicate option",
    );
}
