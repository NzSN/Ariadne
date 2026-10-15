#!/usr/bin/env python3
"""Compile and execute the project/term/storage SDK qualification probe."""
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
    subprocess.run(["python3", str(HERE / "setup-sdk.py"), "--check"], check=True)
    output = sdk.ROOT / "target/bap-core-sdk-smoke"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "sdk_smoke.ml"
    shutil.copyfile(HERE / source.name, source)
    env = sdk.environment()
    # A hostile inherited OCaml environment must not change library selection.
    env.pop("OPAMROOT", None)
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    command = [str(sdk.PREFIX / "bin/ocamlfind"), "ocamlopt", "-linkpkg",
               "-package", "bap", "-o", "sdk-smoke", source.name]
    result = subprocess.run(command, cwd=output, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / "build.log").write_text(result.stdout)
    result.check_returncode()
    execution = subprocess.run([str(output / "sdk-smoke")], env=env,
                               text=True, capture_output=True, timeout=30)
    (output / "run.log").write_text(execution.stdout + execution.stderr)
    execution.check_returncode()
    if execution.stdout.strip() != "isolated-sdk-project-term-storage-ok":
        raise SystemExit("SDK smoke observation mismatch")
    libraries = subprocess.run(["ldd", str(output / "sdk-smoke")], text=True,
                               capture_output=True, check=True).stdout
    (output / "ldd.log").write_text(libraries)
    loaded = {}
    for line in libraries.splitlines():
        for word in line.split():
            if word.startswith("/") and Path(word).is_file():
                loaded[word] = sdk.sha(word)
    report = {"sdkSmokePassed": True, "binarySha256": sdk.sha(output / "sdk-smoke"),
              "sourceSha256": sdk.sha(source), "dynamicLibraries": loaded,
              "sdkManifestSha256": sdk.sha(sdk.BASE / "sdk-manifest.json"),
              "command": command, "stdout": execution.stdout}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(execution.stdout, end="")


if __name__ == "__main__":
    main()
