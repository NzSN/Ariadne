use std::path::{Path, PathBuf};
use std::process::Command;
fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}
#[test]
#[ignore = "requires pinned LLVM IR helper"]
fn ir_cli_reports_verified_text_and_bitcode_and_rejects_unverified_output() {
    let helper: PathBuf = std::env::var_os("ARIADNE_LLVM_IR")
        .expect("native helper required")
        .into();
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let tmp = std::env::temp_dir().join(format!("ariadne-ir-cli-{}-{nonce}", std::process::id()));
    std::fs::create_dir(&tmp).unwrap();
    let run = |path: &Path, output: &Path| {
        Command::new(env!("CARGO_BIN_EXE_ariadne-ir"))
            .arg(path)
            .arg("--helper")
            .arg(&helper)
            .args(["--function", "diamond", "--seed", "i11", "--output-dir"])
            .arg(output)
            .output()
            .unwrap()
    };
    let mut ids = Vec::new();
    for name in ["diamond.ll", "diamond.bc"] {
        let output = tmp.join(name);
        let result = run(&fixture(name), &output);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let dot_binary =
            std::env::var_os("ARIADNE_DOT").expect("completion gate supplies Graphviz");
        let parsed = Command::new(&dot_binary)
            .arg("-Tdot")
            .arg(output.join("report.dot"))
            .output()
            .unwrap();
        assert!(
            parsed.status.success(),
            "{}",
            String::from_utf8_lossy(&parsed.stderr)
        );
        let json: serde_json::Value =
            serde_json::from_slice(&std::fs::read(output.join("report.json")).unwrap()).unwrap();
        assert_eq!(json["schema"], "ariadne.llvm-ir-report/v1");
        assert_eq!(json["identity"]["function_id"], "diamond");
        assert!(json["identity"]["artifact_id"].as_str().unwrap().contains(
            &ariadne_reports::sha256(&std::fs::read(fixture(name)).unwrap())
        ));
        assert_eq!(json["slice"].as_array().unwrap().len(), 9);
        assert_eq!(json["control_graph"].as_array().unwrap().len(), 4);
        assert_eq!(json["obligations"].as_array().unwrap().len(), 3);
        let text = std::fs::read_to_string(output.join("report.txt")).unwrap();
        let dot = std::fs::read_to_string(output.join("report.dot")).unwrap();
        assert!(text.contains("unknown-memory-alias") && dot.contains("unknown-memory-alias"));
        assert!(!run(&fixture(name), &output).status.success());
        ids.push(json["identity"]["artifact_id"].clone());
    }
    assert_ne!(ids[0], ids[1]);
    let invalid = tmp.join("invalid.ll");
    std::fs::write(&invalid, b"define i32 @diamond() { ret void }\n").unwrap();
    let output = tmp.join("bad");
    assert!(!run(&invalid, &output).status.success());
    assert!(!output.exists());
    std::fs::remove_dir_all(tmp).unwrap();
}
