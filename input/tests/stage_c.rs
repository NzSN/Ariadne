//! Supported command-level report behavior over pinned captured-code fixtures.
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn binary() -> &'static str {
    env!("CARGO_BIN_EXE_ariadne-minidump")
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .expect("native gate sets decoder")
        .into()
}
fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}
fn unique_output() -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!("ariadne-stage-c-{}-{nanos}", std::process::id()))
}
fn run(name: &str, entry: &str, extra: &[&str]) -> Output {
    Command::new(binary())
        .arg(fixture(name))
        .arg("--decoder")
        .arg(decoder())
        .arg("--entry")
        .arg(entry)
        .args(extra)
        .output()
        .unwrap()
}

#[test]
#[ignore = "requires pinned LLVM decoder"]
fn one_query_publishes_consistent_text_dot_and_versioned_json_on_both_platforms() {
    for (fixture, entry, seed, artifact) in [
        (
            "stage_b_linux.dmp",
            "0x0000000000401000",
            "0x0000000000401006",
            "7e71f4926e615789815299b98e3c3c725180ed4dce4065937fa533beb1018824",
        ),
        (
            "stage_b_windows.dmp",
            "0x00007ff700001000",
            "0x00007ff700001006",
            "f3a0407bff881356c0128e7587c03ea9f143dbd5fee59abbe8fc5edb75ad30bf",
        ),
    ] {
        let directory = unique_output();
        let output = run(
            fixture,
            entry,
            &[
                "--seed-exception-rip",
                "--output-dir",
                directory.to_str().unwrap(),
            ],
        );
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(output.stdout.is_empty());
        let json: Value =
            serde_json::from_slice(&std::fs::read(directory.join("report.json")).unwrap()).unwrap();
        let text = std::fs::read_to_string(directory.join("report.txt")).unwrap();
        let dot = std::fs::read_to_string(directory.join("report.dot")).unwrap();
        assert_eq!(json["schema"], "ariadne-minidump-report-v1");
        assert_eq!(json["identity"]["input_package_version"], "0.1.0");
        assert_eq!(json["identity"]["core_package_version"], "0.1.0");
        assert_eq!(json["identity"]["artifact_sha256"], artifact);
        assert_eq!(json["query"]["entries"], serde_json::json!([entry]));
        assert_eq!(json["query"]["seeds"], serde_json::json!([seed]));
        assert_eq!(json["analysis"]["slice"], serde_json::json!([entry, seed]));
        assert_eq!(json["analysis"]["edges"].as_array().unwrap().len(), 3);
        assert_eq!(
            json["analysis"]["missing_slice_seeds"],
            serde_json::json!([])
        );
        assert_eq!(json["preparation"]["gaps"][0]["reason"], "opaque_effects");
        assert_eq!(json["preparation"]["sites"][2]["va"], seed);
        assert_eq!(json["preparation"]["sites"][2]["bytes_hex"], "c70005000000");
        assert_eq!(
            json["preparation"]["sites"][2]["rule"],
            "bap-bit-provenance-v2"
        );
        assert_eq!(
            json["preparation"]["sites"][3]["issues"],
            serde_json::json!(["unsupported_semantics"])
        );
        assert!(
            json["analysis"]["reaching"]
                .as_array()
                .unwrap()
                .iter()
                .any(|row| {
                    row["before"] == seed
                        && row["definitions"].as_array().unwrap().iter().any(|d| {
                            d["loc"] == "gpr:rax:0"
                                && d["site"] == entry
                                && d["origin"] == "instruction"
                        })
                })
        );
        for rendered in [&text, &dot] {
            assert!(rendered.contains(entry));
            assert!(rendered.contains(seed));
            assert!(rendered.contains(artifact));
            assert!(rendered.contains("c70005000000"));
            assert!(rendered.contains("bap-bit-provenance-v2"));
            assert!(rendered.contains("opaque_effects"));
        }
        assert!(text.contains("Reaching definitions (possible origins BEFORE each address)"));
        assert!(text.contains("Instruction overview (normalized operands"));
        assert!(text.contains(&format!(
            "{seed}  c70005000000  MOV32mi  mem32/addr64[RAX], imm32->32:0x0000000000000005"
        )));
        let seed_offset = json["input"]["reads"]
            .as_array()
            .unwrap()
            .iter()
            .find(|read| read["va"] == seed)
            .unwrap()["spans"][0]["contributors"][0]["file_offset"]
            .as_str()
            .unwrap();
        assert!(text.contains(&format!(
            "span=s5#0@{seed_offset} slice=yes possible-input-origins=instruction:1,entry:0 issues=none"
        )));
        assert!(
            text.contains("0x00007ff700001003  4889d1  MOV64rr  RCX, RDX")
                || text.contains("0x0000000000401003  4889d1  MOV64rr  RCX, RDX")
        );
        assert!(dot.contains("digraph Ariadne"));
        if let Some(dot_binary) = std::env::var_os("ARIADNE_DOT") {
            let checked = Command::new(dot_binary)
                .args(["-Tplain", "-o"])
                .arg(directory.join("graph.plain"))
                .arg(directory.join("report.dot"))
                .output()
                .unwrap();
            assert!(
                checked.status.success(),
                "{}",
                String::from_utf8_lossy(&checked.stderr)
            );
        }
        std::fs::remove_dir_all(directory).unwrap();
    }
}

#[test]
#[ignore = "requires pinned LLVM decoder"]
fn bad_options_missing_decoder_and_existing_output_do_not_publish_a_report() {
    let directory = unique_output();
    let malformed = run(
        "stage_b_linux.dmp",
        "0x401000",
        &["--seed", "0x401006", "--format", "invalid"],
    );
    assert!(!malformed.status.success());
    assert!(malformed.stdout.is_empty());
    let missing = Command::new(binary())
        .arg(fixture("stage_b_linux.dmp"))
        .args([
            "--decoder",
            "/nonexistent/ariadne-llvm-mc",
            "--entry",
            "0x401000",
            "--output-dir",
        ])
        .arg(&directory)
        .output()
        .unwrap();
    assert!(!missing.status.success());
    assert!(!directory.exists());
    let limited = run(
        "stage_b_linux.dmp",
        "0x401000",
        &[
            "--seed",
            "0x401006",
            "--max-starts",
            "1",
            "--output-dir",
            directory.to_str().unwrap(),
        ],
    );
    assert!(!limited.status.success());
    assert!(!directory.exists());
    let unavailable_parent = directory.join("missing").join("report");
    let unwritable = run(
        "stage_b_linux.dmp",
        "0x401000",
        &[
            "--seed",
            "0x401006",
            "--output-dir",
            unavailable_parent.to_str().unwrap(),
        ],
    );
    assert!(!unwritable.status.success());
    assert!(!unavailable_parent.exists());
    std::fs::create_dir(&directory).unwrap();
    std::fs::write(directory.join("sentinel"), b"keep").unwrap();
    let existing = run(
        "stage_b_linux.dmp",
        "0x401000",
        &[
            "--seed",
            "0x401006",
            "--output-dir",
            directory.to_str().unwrap(),
        ],
    );
    assert!(!existing.status.success());
    assert_eq!(std::fs::read(directory.join("sentinel")).unwrap(), b"keep");
    assert!(!directory.join("report.json").exists());
    std::fs::remove_dir_all(&directory).unwrap();
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink("missing", &directory).unwrap();
        let dangling = run(
            "stage_b_linux.dmp",
            "0x401000",
            &[
                "--seed",
                "0x401006",
                "--output-dir",
                directory.to_str().unwrap(),
            ],
        );
        assert!(!dangling.status.success());
        assert!(std::fs::symlink_metadata(&directory).is_ok());
        std::fs::remove_file(&directory).unwrap();
    }
}

#[test]
#[ignore = "requires pinned LLVM decoder"]
fn absent_entry_yields_typed_partial_report_with_unvisited_seed() {
    let output = run(
        "stage_b_linux.dmp",
        "0x402000",
        &["--seed-exception-rip", "--format", "json"],
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["analysis"]["decoded"], serde_json::json!([]));
    assert_eq!(
        report["analysis"]["missing_slice_seeds"],
        serde_json::json!(["0x0000000000401006"])
    );
    assert_eq!(
        report["preparation"]["sites"][0]["issues"],
        serde_json::json!(["unvisited_reference"])
    );
    assert_eq!(
        report["preparation"]["sites"][1]["issues"],
        serde_json::json!(["not_captured"])
    );
    assert!(
        !report["analysis"]["obligations"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let text = run(
        "stage_b_linux.dmp",
        "0x402000",
        &["--seed-exception-rip", "--format", "text"],
    );
    assert!(text.status.success());
    let text = String::from_utf8(text.stdout).unwrap();
    assert!(text.contains("unvisited references: [\"0x0000000000401006\"]"));
    assert!(text.contains("not_captured"));
    assert!(text.contains("0x0000000000402000  ?  ?  -"));
    assert!(text.contains("quality=unavailable source=unavailable span=none slice=no"));
}
