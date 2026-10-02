#!/usr/bin/env python3
"""Verify the requested single-package Rust layout against Cargo metadata."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).decode().split("\0")
    files = sorted({name for name in listed if name and (ROOT / name).is_file()})
    rust = [name for name in files if name.endswith(".rs")]
    bad = [name for name in rust if not name.startswith(("src/", "tests/"))]
    assert not bad, f"Rust files outside src/tests: {bad}"
    assert [name for name in files if Path(name).name == "Cargo.toml"] == ["Cargo.toml"]
    assert [name for name in files if Path(name).name == "Cargo.lock"] == ["Cargo.lock"]
    metadata = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--offline", "--locked", "--no-deps", "--format-version", "1"],
        cwd=ROOT,
    ))
    assert len(metadata["packages"]) == len(metadata["workspace_members"]) == 1
    assert Path(metadata["target_directory"]) == ROOT / "target"
    package = metadata["packages"][0]
    for target in package["targets"]:
        relative = str(Path(target["src_path"]).relative_to(ROOT))
        assert relative.startswith("tests/" if "test" in target["kind"] else "src/"), relative
    assert {"ariadne-minidump", "ariadne-ir"} <= {
        target["name"] for target in package["targets"] if "bin" in target["kind"]
    }
    for name in ("bap", "input", "ir", "reports", "investigation", "bench"):
        assert not (ROOT / name).exists(), f"Former package directory remains: {name}"
    print(f"Rust layout PASS: {len(rust)} Rust files in src/tests; one manifest/lock; root target.")


if __name__ == "__main__":
    main()
