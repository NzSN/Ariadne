#!/usr/bin/env python3
"""Build the standalone bootstrap with the checked isolated SDK."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sdk_setup", HERE / "setup-sdk.py")
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=sdk.ROOT / "target/bap-core-native")
    parser.add_argument("--source-dir", type=Path, default=HERE)
    args = parser.parse_args()
    subprocess.run(["python3", str(HERE / "setup-sdk.py"), "--check"], check=True)
    output = args.output.resolve()
    if not output.is_relative_to(sdk.ROOT / "target"):
        raise SystemExit("build output must be isolated under target/")
    output.mkdir(parents=True, exist_ok=True)
    sources = ["recovery.ml", "dense_completion.ml", "stateflow.ml", "terminal.ml", "legacy_capture.ml", "capture.ml",
               "legacy_guard.ml", "guard.ml", "legacy_composition.ml", "loop_closure.ml", "legacy_composition_v2.ml",
               "composition.ml", "project_state.ml", "main.ml"]
    source_hashes = {name: sdk.sha(args.source_dir / name) for name in sources}
    guard_model_sha256 = sdk.sha(sdk.ROOT / "Specs/AriadnePredicateAdmission.tla")
    guard_engine_sha256 = hashlib.sha256((
        "ariadne.guard-checker/v2\n"
        + sdk.sha(sdk.ROOT / "src/bap/guard_admission.rs") + "\n"
        + sdk.sha(sdk.ROOT / "src/bap/terminal_control.rs") + "\n").encode()).hexdigest()
    advanced_guard_engine_sha256 = hashlib.sha256((
        "ariadne.guard-checker/v3\n"
        + sdk.sha(sdk.ROOT / "src/bap/guard_admission.rs") + "\n"
        + sdk.sha(sdk.ROOT / "src/bap/terminal_control.rs") + "\n").encode()).hexdigest()
    caller_legacy = sdk.ROOT / "tests/bap/fixtures/caller-coverage/legacy-v2"
    legacy_guard_model_sha256 = sdk.sha(caller_legacy / "AriadnePredicateAdmission.tla.txt")
    legacy_guard_engine_sha256 = sdk.sha(caller_legacy / "guard_admission.rs.txt")
    caller_legacy_manifest = json.loads((caller_legacy.parent / "legacy-manifest.json").read_text())
    legacy_composition_v2_model_sha256 = caller_legacy_manifest["composition_v2_model_sha256"]
    legacy_composition_v2_engine_sha256 = caller_legacy_manifest["composition_v2_checker_sha256"]
    if (legacy_guard_model_sha256 != "10e870b21691946cd7985ff7d33819a8a58e4fea202ae6d2e771214b997f5bc9"
            or legacy_guard_engine_sha256 != "076b8a3fb6f776e53ea99336854c1a793b8658874c153f4ddd2e32c54128ce7d"
            or legacy_composition_v2_model_sha256 != "605fb57d42e755b7fee75511f66e6ad864a16c303bbf5ffb5bad8855c7d05675"
            or legacy_composition_v2_engine_sha256 != "dd277b844376234cce199ecae9e7bc9eee04dfa69390d2320c2349b4f11b6cb4"):
        raise SystemExit("frozen caller-coverage legacy identities changed")
    legacy = sdk.ROOT / "tests/bap/fixtures/loop-closure/legacy-v1"
    legacy_composition_model_sha256 = sdk.sha(legacy / "AriadneGuardedTargetResolution.tla.txt")
    legacy_composition_engine_sha256 = sdk.sha(legacy / "composition.rs.txt")
    if legacy_composition_model_sha256 != "e142a6fd22d78044c444c26211b7c659a56fedb5f9e555aa20e3aa1be23e8b10":
        raise SystemExit("legacy composition model source changed")
    if legacy_composition_engine_sha256 != "c36c8876810e35ed10b7e366e650d7854958b0ad7b07d33084039d39b68e9580":
        raise SystemExit("legacy composition checker source changed")
    loop_model_sha256 = sdk.sha(sdk.ROOT / "Specs/AriadneLoopTargetClosure.tla")
    loop_engine_sha256 = hashlib.sha256((
        "ariadne.loop-target-engine/v1\n"
        + sdk.sha(sdk.ROOT / "src/bap/target_resolution.rs") + "\n"
        + sdk.sha(sdk.ROOT / "src/bap/target_resolution/loop_closure.rs") + "\n").encode()).hexdigest()
    composition_model_sha256 = hashlib.sha256((
        "ariadne.guarded-target-model/v3\n"
        + sdk.sha(sdk.ROOT / "Specs/AriadneGuardedTargetResolution.tla") + "\n"
        + loop_model_sha256 + "\n" + guard_model_sha256 + "\n").encode()).hexdigest()
    composition_engine_sha256 = hashlib.sha256((
        "ariadne.guarded-target-checker/v3\n"
        + sdk.sha(sdk.ROOT / "src/bap/composition.rs") + "\n"
        + loop_engine_sha256 + "\n" + guard_engine_sha256 + "\n").encode()).hexdigest()
    advanced_composition_engine_sha256 = hashlib.sha256((
        "ariadne.guarded-target-checker/v4\n"
        + sdk.sha(sdk.ROOT / "src/bap/composition.rs") + "\n"
        + loop_engine_sha256 + "\n" + advanced_guard_engine_sha256 + "\n").encode()).hexdigest()
    lock = json.loads(sdk.LOCK.read_text())
    handshake = {"schema": "ariadne.bap-core-ready/v1", "abi": 2,
                 "compiler": "4.12.1", "bap_revision": lock["bapSourceRevision"],
                 "sdk_manifest_sha256": sdk.sha(sdk.BASE / "sdk-manifest.json"),
                 "source_hashes": source_hashes, "families": ["recovery", "stateflow"],
                 "guard_model_sha256": guard_model_sha256,
                 "guard_engine_sha256": guard_engine_sha256,
                 "advanced_guard_engine_sha256": advanced_guard_engine_sha256,
                 "advanced_composition_engine_sha256": advanced_composition_engine_sha256,
                 "legacy_guard_model_sha256": legacy_guard_model_sha256,
                 "legacy_guard_engine_sha256": legacy_guard_engine_sha256,
                 "composition_model_sha256": composition_model_sha256,
                 "composition_engine_sha256": composition_engine_sha256,
                 "legacy_composition_model_sha256": legacy_composition_model_sha256,
                 "legacy_composition_engine_sha256": legacy_composition_engine_sha256,
                 "legacy_composition_v2_model_sha256": legacy_composition_v2_model_sha256,
                 "legacy_composition_v2_engine_sha256": legacy_composition_v2_engine_sha256,
                 "loop_model_sha256": loop_model_sha256,
                 "loop_engine_sha256": loop_engine_sha256,
                 "profiles": ["normalized-fixed-input/v1", "captured-fixed-input/v1", "captured-indirect-targets/v1", "captured-guarded-input/v1", "captured-guarded-targets/v1", "captured-guarded-targets/v2", "captured-guarded-input/v2", "captured-guarded-targets/v3", "captured-indirect-targets/v2", "captured-guarded-input/v3", "captured-guarded-targets/v4"],
                 "operations": ["initialize", "advance:Visit", "advance:FinishRecovery",
                                "advance:Propagate", "advance:FinishDataflow",
                                "advance:ExpandSlice", "advance:FinishSlice", "advance:FinishStateflow",
                                "step", "observe", "finish", "reset",
                                "run-batch", "result-page", "result-close"],
                 "completion_codec": "bitmap/v1",
                 "max_frame_bytes": 8 * 1024 * 1024,
                 "max_request_bytes": 8 * 1024 * 1024,
                 "configurable_request_bytes": True, "max_addresses": 65536}
    encoded = json.dumps(handshake, sort_keys=True, separators=(",", ":"))
    (output / "build_identity.ml").write_text(
        "let handshake = {identity|" + encoded + "|identity}\n"
        + "let guard_model_sha256 = " + json.dumps(guard_model_sha256) + "\n"
        + "let guard_engine_sha256 = " + json.dumps(guard_engine_sha256) + "\n"
        + "let advanced_guard_engine_sha256 = " + json.dumps(advanced_guard_engine_sha256) + "\n"
        + "let advanced_composition_engine_sha256 = " + json.dumps(advanced_composition_engine_sha256) + "\n"
        + "let legacy_guard_model_sha256 = " + json.dumps(legacy_guard_model_sha256) + "\n"
        + "let legacy_guard_engine_sha256 = " + json.dumps(legacy_guard_engine_sha256) + "\n"
        + "let composition_model_sha256 = " + json.dumps(composition_model_sha256) + "\n"
        + "let composition_engine_sha256 = " + json.dumps(composition_engine_sha256) + "\n"
        + "let legacy_composition_model_sha256 = " + json.dumps(legacy_composition_model_sha256) + "\n"
        + "let legacy_composition_engine_sha256 = " + json.dumps(legacy_composition_engine_sha256) + "\n"
        + "let legacy_composition_v2_model_sha256 = " + json.dumps(legacy_composition_v2_model_sha256) + "\n"
        + "let legacy_composition_v2_engine_sha256 = " + json.dumps(legacy_composition_v2_engine_sha256) + "\n"
        + "let loop_model_sha256 = " + json.dumps(loop_model_sha256) + "\n"
        + "let loop_engine_sha256 = " + json.dumps(loop_engine_sha256) + "\n")
    for name in sources:
        shutil.copyfile(args.source_dir / name, output / name)
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    command = [str(sdk.PREFIX / "bin/ocamlfind"), "ocamlopt", "-linkpkg",
               "-package", "bap,yojson", "-o", "ariadne-bap-core",
               "build_identity.ml", *sources]
    result = subprocess.run(command, cwd=output, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "build.log").write_text(result.stdout)
    if result.returncode:
        raise SystemExit(result.stdout)
    manifest = {"schema": "ariadne.bap-core-build/v1", "handshake": handshake,
                "helper_sha256": sdk.sha(output / "ariadne-bap-core"),
                "lock_sha256": sdk.sha(sdk.LOCK)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(output / "ariadne-bap-core")


if __name__ == "__main__":
    main()
