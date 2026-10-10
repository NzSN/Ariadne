#!/usr/bin/env python3
"""Build the standalone bootstrap with the checked isolated SDK."""
import argparse
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
    sources = ["recovery.ml", "stateflow.ml", "capture.ml", "project_state.ml", "main.ml"]
    source_hashes = {name: sdk.sha(args.source_dir / name) for name in sources}
    lock = json.loads(sdk.LOCK.read_text())
    handshake = {"schema": "ariadne.bap-core-ready/v1", "abi": 2,
                 "compiler": "4.12.1", "bap_revision": lock["bapSourceRevision"],
                 "sdk_manifest_sha256": sdk.sha(sdk.BASE / "sdk-manifest.json"),
                 "source_hashes": source_hashes, "families": ["recovery", "stateflow"],
                 "profiles": ["normalized-fixed-input/v1", "captured-fixed-input/v1"],
                 "operations": ["initialize", "advance:Visit", "advance:FinishRecovery",
                                "advance:Propagate", "advance:FinishDataflow",
                                "advance:ExpandSlice", "advance:FinishSlice", "advance:FinishStateflow",
                                "step", "observe", "finish", "reset",
                                "run-batch", "result-page", "result-close"],
                 "max_frame_bytes": 8 * 1024 * 1024, "max_addresses": 65536}
    encoded = json.dumps(handshake, sort_keys=True, separators=(",", ":"))
    (output / "build_identity.ml").write_text("let handshake = {identity|" + encoded + "|identity}\n")
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
