#!/usr/bin/env python3
"""Prepare an explicitly identified local compatibility build; preserve siblings."""

import argparse
import json
import os
from pathlib import Path

from tools import MBT, ROOT, run, sha256, work_directory, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-built-copy", type=Path,
                        help="register an already-built isolated copy with the exact recorded patch")
    args = parser.parse_args()
    original = Path(os.environ.get("MIRRORS_ROOT", ROOT.parent / "Mirrors")).resolve()
    run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=original)
    source_revision = run(["git", "rev-parse", "HEAD"], cwd=original).stdout.strip()
    patch = MBT / "mirrors-isfinite.patch"
    work = work_directory("toolchain")
    if args.use_built_copy:
        isolated = args.use_built_copy.resolve()
        if isolated == original:
            raise RuntimeError("the compatibility build must not modify or reuse the original checkout")
    else:
        isolated = work / "Mirrors"
        print(f"Copying prepared framework into {isolated}", flush=True)
        run(["cp", "-a", "--reflink=auto", original, isolated], timeout=600)
        run(["git", "apply", "--check", patch], cwd=isolated)
        run(["git", "apply", patch], cwd=isolated)
        run(["lake", "build", "mirror", "model_interface_gen", "tla_elaboration_spec"],
            cwd=isolated, log=work / "build.log", timeout=900)
    revision = run(["git", "rev-parse", "HEAD"], cwd=isolated).stdout.strip()
    if revision != source_revision:
        raise RuntimeError("isolated copy is from an older framework revision; prepare a fresh copy")
    actual_patch = run(["git", "diff"], cwd=isolated).stdout
    if actual_patch != patch.read_text():
        raise RuntimeError("isolated framework changes do not equal the recorded compatibility patch")
    check = run([isolated / ".lake/build/bin/tla_elaboration_spec"], cwd=isolated,
                log=work / "elaboration.log")
    if "TLA ELABORATION SPEC GREEN" not in check.stdout:
        raise RuntimeError("focused framework elaboration checks did not confirm success")
    compiler = isolated / ".lake/build/bin/model_interface_gen"
    usage = run([compiler, "--help"], expected=(0, 2)).stdout
    if "mirrorrust-v1" not in usage:
        raise RuntimeError("prepared compiler does not support the required mirrorrust-v1 target")
    identity = {
        "schema": "ariadne.mbt-toolchain/v1", "root": str(isolated),
        "originalRoot": str(original),
        "revision": revision,
        "requiredTargets": ["mirrorrust-v1"],
        "patchSha256": sha256(patch),
        "profile": "mirrors-tla-frontend-profile-4-ariadne-isfinite-v1",
        "binaries": {name: sha256(isolated / ".lake/build/bin" / name)
                     for name in ("mirror", "model_interface_gen")},
        "elaborationCheck": check.stdout.strip(),
    }
    write_json(MBT / ".work/toolchain.json", identity)
    print(json.dumps(identity, indent=2), flush=True)


if __name__ == "__main__":
    main()
