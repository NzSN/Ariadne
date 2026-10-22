#!/usr/bin/env python3
"""Check exact v9 target-dispatch refusal in freshly compiled native modules."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = run_output(parser.parse_args().output)
    output.mkdir(parents=True, exist_ok=False)
    path = ROOT / "native/bap-core/setup-sdk.py"
    spec = importlib.util.spec_from_file_location("source_flags_sdk", path)
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    subprocess.run([sys.executable, str(path), "--check"], cwd=ROOT, env=env, check=True)
    sources = [ROOT / "native/bap-core" / name for name in ("recovery.ml", "legacy_capture.ml", "capture.ml")]
    sources.append(ROOT / "tests/bap/source_extension_capture.ml")
    bindings = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    for source in sources:
        shutil.copyfile(source, output / source.name)
    command = [str(sdk.PREFIX / "bin/ocamlfind"), "ocamlopt", "-linkpkg", "-package", "bap,yojson",
               "-o", "check-source-flags", *(p.name for p in sources)]
    for name, cmd in (("build", command), ("check", [str(output / "check-source-flags")])):
        result = subprocess.run(cmd, cwd=output, env=env, capture_output=True, text=True, timeout=120)
        (output / (name + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise SystemExit(f"{name} failed: see {output / (name + '.log')}")
    if bindings != {str(p.relative_to(ROOT)): sha(p) for p in sources}:
        raise SystemExit("native source changed during control")
    report = dict(schema="ariadne.source-flags-target-refusal/v1", passed=True,
                  controls=["current-v3-refuses-v9", "legacy-v2-refuses-v9",
                            "current-v3-preserves-v8-dispatch", "legacy-v2-preserves-v8-dispatch"],
                  sources=bindings, sdkManifestSha256=sha(sdk.BASE / "sdk-manifest.json"),
                  compilerSha256=sha(sdk.PREFIX / "bin/ocamlopt.opt"),
                  observerSha256=sha(output / "check-source-flags"))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Four native source-profile dispatch controls passed:", output / "report.json")


if __name__ == "__main__":
    main()
