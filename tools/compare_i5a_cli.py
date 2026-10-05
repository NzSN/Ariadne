#!/usr/bin/env python3
"""Preserve the pre-I5a Rust oracle and compare the native default independently."""
import json
from pathlib import Path
import subprocess
import tempfile

from i5a_native_contract import (
    PROFILE, environment, native_manifest, sha, source_inventory, strict_json,
    tool_hashes, validate_backend_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
sources = source_inventory


def without_verified_receipt(report, text, dot, manifest):
    """Remove only the exact validated native receipt from all three formats."""
    receipt = validate_backend_receipt(report, manifest)
    text_lines = text.splitlines(keepends=True)
    prefix = "analysis backend: "
    candidates = [line for line in text_lines if line.startswith(prefix)]
    if len(candidates) != 1 or candidates[0] != text_lines[-1]:
        raise ValueError("missing, duplicate, or misplaced text backend receipt")
    if strict_json(candidates[0][len(prefix):]) != receipt:
        raise ValueError("text backend receipt differs from JSON receipt")
    dot_lines = dot.splitlines(keepends=True)
    prefix = "// analysis backend: "
    candidates = [line for line in dot_lines if line.startswith(prefix)]
    if len(candidates) != 1 or candidates[0] != dot_lines[0]:
        raise ValueError("missing, duplicate, or misplaced DOT backend receipt")
    if strict_json(candidates[0][len(prefix):]) != receipt:
        raise ValueError("DOT backend receipt differs from JSON receipt")
    normalized = dict(report)
    del normalized["analysis_backend"]
    return normalized, "".join(text_lines[:-1]), "".join(dot_lines[1:])


def main():
    before = sources()
    work = Path(tempfile.mkdtemp(prefix="ariadne-i5a-equivalence-"))
    baseline = ROOT / "evidence/Ariadne/investigation-correctness-validation.json"
    expected = strict_json(baseline.read_text())["defaultOutputEquivalence"]["after"]
    build = subprocess.run(["cargo", "build", "--offline", "--locked", "--release", "--bin",
                            "ariadne-minidump"], cwd=ROOT, capture_output=True, text=True)
    if build.returncode:
        raise SystemExit(build.stdout + build.stderr)
    env, manifest = environment(), native_manifest()
    tools_before = tool_hashes()
    cases = [("linux", "tests/input/fixtures/stage_b_linux.dmp", "401000", "401006"),
             ("windows", "tests/input/fixtures/stage_b_windows.dmp", "7ff700001000", "7ff700001006"),
             ("not", "tests/input/fixtures/bap_precision_linux.dmp", "401000", "401006"),
             ("real-linux", "tmp/priority1/chromium-member-uaf.dmp", "566817922dc5", "566817922e42")]
    actual, native_hashes, explicit_hashes, receipts, bindings = {}, {}, {}, {}, {}
    comparisons = 0
    for label, dump, entry, site in cases:
        directories = {}
        for backend in ["rust", "default", "bap"]:
            out = work / f"{label}-{backend}"
            command = [ROOT / "target/release/ariadne-minidump", ROOT / dump, "--decoder-reference",
                       ROOT / "target/ariadne-llvm-mc", "--entry", entry, "--explain-fault-address",
                       site, "--memory-access", "0", "--output-dir", out]
            if backend != "default":
                command += ["--analysis-backend", backend]
            result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            directories[backend] = out
        hashes = {backend: {p.name: sha(p) for p in out.iterdir() if p.is_file()}
                  for backend, out in directories.items()}
        actual[label], native_hashes[label], explicit_hashes[label] = (
            hashes["rust"], hashes["default"], hashes["bap"])
        if hashes["default"] != hashes["bap"]:
            raise RuntimeError("default CLI differs from explicit BAP: " + label)
        reports = {backend: strict_json((out / "report.json").read_text())
                   for backend, out in directories.items()}
        for backend, report in reports.items():
            if (report["identity"]["artifact_sha256"] != sha(ROOT / dump)
                    or report["query"]["entries"] != [f"0x{int(entry, 16):016x}"]
                    or report["query"]["seeds"] != [f"0x{int(site, 16):016x}"]):
                raise RuntimeError("changed comparison artifact/query")
            if backend != "rust":
                validate_backend_receipt(report, manifest)
            elif "analysis_backend" in report:
                raise RuntimeError("explicit Rust comparison unexpectedly contains native receipt")
        receipts[label] = reports["default"]["analysis_backend"]
        bindings[label] = dict(artifactSha256=sha(ROOT / dump), query=reports["default"]["query"],
                               reportIdentity=reports["default"]["identity"])
        native = directories["default"]
        reference = directories["rust"]
        normalized = without_verified_receipt(reports["default"], (native / "report.txt").read_text(),
                                               (native / "report.dot").read_text(), manifest)
        if normalized != (reports["rust"], (reference / "report.txt").read_text(),
                          (reference / "report.dot").read_text()):
            raise RuntimeError("native/reference core report mismatch: " + label)
        expected_names = {"report.txt", "report.json", "report.dot", "explanation.txt", "explanation.json", "explanation.dot"}
        if any(set(values) != expected_names for values in hashes.values()):
            raise RuntimeError("missing or unexpected comparison output")
        for name in ["explanation.txt", "explanation.json", "explanation.dot"]:
            if (native / name).read_bytes() != (reference / name).read_bytes():
                raise RuntimeError("native/reference explanation bytes differ: " + label + "/" + name)
        comparisons += len(expected_names)
    stable, tools_after = before == sources(), tool_hashes()
    report_count = sum(map(len, actual.values()))
    passed = stable and tools_before == tools_after and actual == expected and report_count == comparisons == 24
    result = dict(schema="ariadne.i5a-cli-equivalence/v2", passed=passed,
                  sourcesStable=stable, toolsStable=tools_before == tools_after,
                  sourceHashes=before, tools=tools_after, analysisBackend="bap", analysisProfile=PROFILE,
                  defaultNativeVerified=True, helperManifest=manifest, nativeBackendReceipts=receipts,
                  queryBindings=bindings, baselineRecordSha256=sha(baseline),
                  legacyComparisonBackend="rust", baselineUsedAsCurrentAcceptance=False,
                  expected=expected, actual=actual, reports=report_count,
                  nativeOutputHashes=native_hashes, explicitBapOutputHashes=explicit_hashes,
                  nativeReferenceComparisons=comparisons, byteExactExplanationComparisons=12,
                  scope="24 retained pre-I5a output hashes checked through explicit Rust; 24 native/reference comparisons with only verified backend receipts removed from core reports and byte-exact explanations. The historical oracle supplies no current acceptance credit.")
    (work / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    if not passed:
        raise SystemExit("legacy reference reports changed or source/tool identity unstable")


if __name__ == "__main__":
    main()
