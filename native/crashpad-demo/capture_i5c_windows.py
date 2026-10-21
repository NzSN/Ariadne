#!/usr/bin/env python3
"""Produce and independently inspect all eight new owned I5c Windows captures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from inspect_i5c import inspect, publish_new

PROFILES = {"upper": "address-wrap-upper", "none": "address-wrap-no-wrap",
            "negative": "address-wrap-negative", "indexed": "address-wrap-indexed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--expected-build-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("native Windows Python is required; no capture was attempted")
    build = args.build.resolve()
    if hashlib.sha256(build.read_bytes()).hexdigest() != args.expected_build_sha256:
        parser.error("build receipt differs from the independently pinned digest")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    try:
        for recipe, profile in PROFILES.items():
            for mode in ("partial", "full"):
                name = recipe + "-" + mode
                destination = root / name
                subprocess.run([
                    sys.executable, str(Path(__file__).with_name("run_windows.py")),
                    "--build", str(build), "--output", str(destination), "--mode", mode,
                    "--profile", profile, "--minimal-environment", "--check-failures"],
                    check=True, timeout=180)
                result = inspect(destination, build, args.expected_build_sha256)
                if result["case"] != name or result["mode"] != mode or result["recipe"] != recipe:
                    raise ValueError("independent observation belongs to another owned case")
                publish_new(destination / "inspection.json", result)
                rows.append({"case": name, "inspection": result})
                publish_new(root / (name + "-receipt.json"), {"case": name, "inspection": result})
                print(name + ": capture and independent inspection PASS", flush=True)
    except BaseException:
        # Keep actual successful captures and failure artifacts; never relabel
        # an incomplete bundle as a completed eight-case capture campaign.
        publish_new(root / "incomplete.json", {"schema": "ariadne.i5c-capture-bundle/v1",
                    "passed": False, "buildSha256": args.expected_build_sha256, "cases": rows})
        raise
    publish_new(root / "i5c-capture-bundle.json", {"schema": "ariadne.i5c-capture-bundle/v1",
                "passed": len(rows) == 8, "buildSha256": args.expected_build_sha256, "cases": rows,
                "productAssessmentQualified": False})


if __name__ == "__main__":
    main()
