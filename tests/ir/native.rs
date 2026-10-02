use ariadne::ir::{open_verified_ir, parse_verified_output};
use ariadne::llvm_ir as model;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::process::Command;

fn helper() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_IR")
        .expect("native gate sets LLVM IR helper")
        .into()
}
fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/ir/fixtures")
        .join(name)
}
fn id(name: &str) -> model::InstructionId {
    model::InstructionId(name.into())
}

#[test]
#[ignore = "requires pinned LLVM 20 IR helper"]
fn verified_text_and_bitcode_have_the_same_normalized_slice_and_distinct_artifact_ids() {
    let mut artifact_ids = Vec::new();
    for name in ["diamond.ll", "diamond.bc"] {
        let path = fixture(name);
        let bytes = std::fs::read(&path).unwrap();
        let hash = format!("{:x}", Sha256::digest(&bytes));
        let request = open_verified_ir(&path, &helper(), "diamond", [id("i11")].into()).unwrap();
        assert_eq!(request.artifact_id, format!("llvm-ir-artifact-v1:{hash}"));
        assert!(request.verified_ir);
        assert_eq!(request.blocks.len(), 4);
        assert_eq!(request.control_graph().len(), 4);
        assert!(request.call_graph().is_empty());
        assert!(request.obligations().contains(&model::Obligation {
            site: id("i8"),
            reason: model::ObligationReason::CallTargets,
        }));
        assert!(request.obligations().contains(&model::Obligation {
            site: id("i9"),
            reason: model::ObligationReason::Adapter(
                model::AdapterObligationReason::UnknownMemoryAlias
            ),
        }));
        assert_eq!(request.instructions[&id("i7")].phi_incoming.len(), 2);
        assert_eq!(
            request.instructions[&id("i9")].memory_preds,
            [id("i2"), id("i5"), id("i8")].into()
        );
        let result = model::analyze(request).unwrap();
        assert_eq!(
            result.state().slice,
            [
                id("i1"),
                id("i2"),
                id("i4"),
                id("i5"),
                id("i7"),
                id("i8"),
                id("i9"),
                id("i10"),
                id("i11")
            ]
            .into()
        );
        artifact_ids.push(result.request().artifact_id.clone());
    }
    assert_ne!(artifact_ids[0], artifact_ids[1]);
}

#[test]
#[ignore = "requires pinned LLVM 20 IR helper"]
fn verifier_failure_and_protocol_corruptions_fail_before_analysis() {
    let invalid =
        std::env::temp_dir().join(format!("ariadne-ir-invalid-{}.ll", std::process::id()));
    std::fs::write(&invalid, b"define i32 @bad() { entry: ret void }\n").unwrap();
    let failed = open_verified_ir(&invalid, &helper(), "bad", [id("i0")].into());
    std::fs::remove_file(invalid).unwrap();
    assert!(failed.is_err());

    let output = Command::new(helper())
        .arg(fixture("diamond.ll"))
        .arg("diamond")
        .output()
        .unwrap();
    assert!(output.status.success());
    let hash = format!(
        "{:x}",
        Sha256::digest(std::fs::read(fixture("diamond.ll")).unwrap())
    );
    let mut document: Value = serde_json::from_slice(&output.stdout).unwrap();
    document["verified_ir"] = Value::Bool(false);
    assert!(
        parse_verified_output(
            &serde_json::to_vec(&document).unwrap(),
            &hash,
            [id("i11")].into()
        )
        .is_err()
    );
    document["verified_ir"] = Value::Bool(true);
    document["instructions"][7]["phi_incoming"]
        .as_array_mut()
        .unwrap()
        .pop();
    assert!(
        parse_verified_output(
            &serde_json::to_vec(&document).unwrap(),
            &hash,
            [id("i11")].into()
        )
        .is_err()
    );
    let mut document: Value = serde_json::from_slice(&output.stdout).unwrap();
    let duplicate = document["blocks"][0].clone();
    document["blocks"].as_array_mut().unwrap().push(duplicate);
    assert!(
        parse_verified_output(
            &serde_json::to_vec(&document).unwrap(),
            &hash,
            [id("i11")].into()
        )
        .is_err()
    );
}

#[test]
#[ignore = "requires pinned LLVM 20 IR helper"]
fn verified_function_with_two_phi_nodes_keeps_both_dependencies() {
    use std::io::Write;
    let mut source = tempfile::Builder::new().suffix(".ll").tempfile().unwrap();
    source
        .write_all(
            br#"
define i32 @two_phi(i1 %choice) {
entry:
  br i1 %choice, label %left, label %right
left:
  br label %join
right:
  br label %join
join:
  %x = phi i32 [ 1, %left ], [ 2, %right ]
  %y = phi i32 [ 3, %left ], [ 4, %right ]
  %z = add i32 %x, %y
  ret i32 %z
}
"#,
        )
        .unwrap();
    let request = open_verified_ir(source.path(), &helper(), "two_phi", [id("i6")].into()).unwrap();
    assert_eq!(request.phi_nodes, [id("i3"), id("i4")].into());
    assert_eq!(request.instructions[&id("i3")].phi_incoming.len(), 2);
    assert_eq!(request.instructions[&id("i4")].phi_incoming.len(), 2);
    let result = model::analyze(request).unwrap();
    assert_eq!(
        result.state().slice,
        [id("i3"), id("i4"), id("i5"), id("i6")].into()
    );
}
