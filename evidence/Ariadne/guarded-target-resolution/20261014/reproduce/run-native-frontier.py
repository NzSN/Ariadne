#!/usr/bin/env python3
"""Compile/run the standalone native source coverage controls on remote WSL."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "native/bap-core/setup-sdk.py"
spec = importlib.util.spec_from_file_location("ariadne_sdk_setup", SETUP)
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--test-file", type=Path, default=ROOT / "tests/bap/target_resolution_frontier.ml")
    parser.add_argument("--cases", type=int, default=9)
    parser.add_argument("--output", type=Path, default=ROOT / "target/composition-frontier-controls")
    parser.add_argument("--arg", action="append", default=[])
    args = parser.parse_args()
    native = args.native_dir.resolve()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "target"):
        raise SystemExit("control output must stay isolated under target/")
    for name in ("recovery.cmx", "capture.cmx", "recovery.cmi", "capture.cmi"):
        if not (native / name).is_file():
            raise SystemExit(f"compiled native module missing: {name}")
    out.mkdir(parents=True, exist_ok=True)
    source = args.test_file.resolve()
    copied = out / source.name
    shutil.copyfile(source, copied)
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    command = [str(sdk.PREFIX / "bin/ocamlfind"), "ocamlopt", "-linkpkg",
               "-package", "bap,yojson", "-I", str(native),
               str(native / "recovery.cmx"), str(native / "capture.cmx"),
               copied.name, "-o", "frontier-controls"]
    build = subprocess.run(command, cwd=out, env=env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / "build.log").write_text(build.stdout)
    if build.returncode:
        raise SystemExit(build.stdout)
    result = subprocess.run([str(out / "frontier-controls"), *args.arg], cwd=out, env=env,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (out / "run.log").write_text(result.stdout)
    record = dict(schema="ariadne.native-frontier-controls/v1",
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  native_manifest_sha256=hashlib.sha256((native / "manifest.json").read_bytes()).hexdigest(),
                  source_cases=args.cases, build_command=command,
                  build_exit=build.returncode, run_exit=result.returncode)
    (out / "validation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(result.stdout, end="")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
