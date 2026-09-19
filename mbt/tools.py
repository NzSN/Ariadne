"""Trusted artifact preparation shared by generation and replay."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MBT = ROOT / "mbt"
FIXTURES = ("Binary", "Dump", "Loop", "Closed", "Pipeline", "Calls")
MODEL_FILES = (
    "Specs/Ariadne.tla", "Specs/AriadneTypes.tla", "Specs/AriadneMachineCommon.tla",
    "Specs/AriadneExample.tla", "Specs/AriadnePipeline.tla", "Specs/AriadneCalls.tla",
    "mbt/model/AriadneReplay.tla",
)
ORACLE_FILES = MODEL_FILES + ("mbt/AriadneReplay.interface.json", "mbt/generate.py", "mbt/tools.py", "mbt/projection.py")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(command, *, cwd=ROOT, expected=(0,), log=None, timeout=120):
    command = [str(part) for part in command]
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if log is not None:
        Path(log).write_text(result.stdout)
    if result.returncode not in expected:
        raise RuntimeError(f"command exited {result.returncode}: {command!r}\n{result.stdout[-12000:]}")
    return result


def work_directory(prefix):
    work = MBT / ".work"
    work.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix + "-", dir=work))


def prepare_model(work):
    destination = work / "model"
    destination.mkdir()
    for relative in MODEL_FILES:
        shutil.copyfile(ROOT / relative, destination / Path(relative).name)
    return destination / "AriadneReplay.tla"


def mirrors_tools():
    selected = MBT / ".work/toolchain.json"
    identity = None
    if "MIRRORS_ROOT" not in os.environ and selected.is_file():
        identity = json.loads(selected.read_text())
        root = Path(identity["root"])
        if sha256(MBT / "mirrors-isfinite.patch") != identity["patchSha256"]:
            raise RuntimeError("compatibility patch changed; prepare the toolchain again")
    else:
        root = Path(os.environ.get("MIRRORS_ROOT", ROOT.parent / "Mirrors")).resolve()
    compiler = root / ".lake/build/bin/model_interface_gen"
    mirror = root / ".lake/build/bin/mirror"
    for path in (compiler, mirror):
        if not path.is_file():
            raise RuntimeError(f"missing prepared framework tool: {path}; build it in Mirrors first")
        if identity is not None and sha256(path) != identity["binaries"][path.name]:
            raise RuntimeError(f"prepared tool identity changed: {path}")
    return root, compiler, mirror


def resolve(compiler, model, evidence, lock, log):
    return run([compiler, "resolve", "--spec", model, "--contract", MBT / "AriadneReplay.interface.json",
                "--evidence", evidence, "--param-var", "parameters", "--lock", lock,
                "--diagnostics", "json"], log=log)


def verify_corpus():
    manifest = json.loads((MBT / "corpus/manifest.json").read_text())
    for path, digest in manifest["oracleSources"].items():
        if sha256(ROOT / path) != digest:
            raise RuntimeError(f"stale oracle input: {path}; explicitly run mbt/generate.py")
    for filename, digest in manifest["artifacts"].items():
        if sha256(MBT / "corpus" / filename) != digest:
            raise RuntimeError(f"corpus artifact changed: {filename}; explicitly regenerate and review")
    return manifest
