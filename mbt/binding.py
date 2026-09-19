"""Compiler-owned Rust binding generation and read-only freshness checks."""

from pathlib import Path

from tools import MBT, run, sha256

TARGET = "mirrorrust-v1"
GENERATED = MBT / "generated"
OWNED_FILES = (".model-interface-generated.json", "AriadneReplayMirror.generated.rs")


def check_binding(compiler, model, log, directory=GENERATED):
    return run([
        compiler, "check", "--spec", model,
        "--contract", MBT / "AriadneReplay.interface.json",
        "--evidence", MBT / "corpus/type-evidence.json", "--param-var", "parameters",
        "--lock", MBT / "corpus/AriadneReplay.lock.json",
        "--target", TARGET, "--out", directory,
    ], log=log)


def generated_hashes(directory=GENERATED):
    directory = Path(directory)
    return {name: sha256(directory / name) for name in OWNED_FILES}
