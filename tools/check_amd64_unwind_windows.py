#!/usr/bin/env python3
"""Compare fresh positive synthetic Ariadne unwind results with Windows itself.

Run the ignored export test first. This runner uses no retained successful
baseline and writes its report only to a caller-selected ignored work directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/input/fixtures/amd64-unwind-reference.ps1"


def windows_path(path):
    if os.name == "nt":
        return str(path)
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve()
    if not work.is_relative_to(ROOT / "target"):
        parser.error("output must be disposable work under target/")
    work.mkdir(parents=True, exist_ok=False)
    directory = args.cases.resolve()
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    required_sources = ("src/investigation/frame_unwind.rs", "src/input/frame_paths.rs",
                        "tests/input/unwind_operations.rs", "tests/input/unwind_v2.rs")
    expected_sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                        for name in required_sources}
    if manifest.get("sources") != expected_sources:
        parser.error("export is not bound to the current compiled unwind/test sources")
    cases = manifest["cases"]
    if not cases or len({row["name"] for row in cases}) != len(cases):
        parser.error("nonempty unique positive cases required")
    before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in [REFERENCE, Path(__file__).resolve(), *(ROOT / name for name in required_sources)]}
    rows = []
    for case in cases:
        capture = (directory / case["file"]).resolve()
        if not capture.is_relative_to(directory) or not capture.is_file():
            raise ValueError("capture must be inside the exported directory")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", windows_path(REFERENCE), "-Dump", windows_path(capture)],
            text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)
        row = {"name": case["name"], "captureSha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
               "exitCode": result.returncode, "passed": False}
        try:
            if result.returncode:
                raise ValueError(result.stderr.strip() or result.stdout.strip())
            observed = json.loads(result.stdout.strip())
            expected = case["ariadne"]
            differences = []
            for key in ("pc", "sp"):
                if observed[key] != expected[key]:
                    differences.append(key)
            for bank, value in expected["registers"].items():
                if observed["registers"].get(bank) != value:
                    differences.append("registers." + bank)
            row.update(observed=observed, ariadne=expected, differences=differences, passed=not differences)
        except (ValueError, KeyError, TypeError) as error:
            row["error"] = str(error)
        rows.append(row)
        print(case["name"] + (": PASS" if row["passed"] else ": FAIL"), flush=True)
    stable = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in before.items())
    report = {"schema": "ariadne.amd64-unwind-windows-reference/v1", "passed": stable and all(row["passed"] for row in rows),
              "scope": "fresh positive synthetic captures, first-frame PC/SP and available GPR agreement; no full ISA or real-capture qualification",
              "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "sources": before,
              "sourcesStable": stable, "cases": rows, "skipped": manifest.get("skipped", []),
              "fullUnwindCoverage": False}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
