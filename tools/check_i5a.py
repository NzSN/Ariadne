#!/usr/bin/env python3
"""Native-default source/fixture I5a acceptance; real-Windows tiers stay separate."""
import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from with_mirrorrust_snapshot import active_identity

from i5a_native_contract import (
    PROFILE, environment, native_manifest, sha, source_inventory, strict_json,
    tool_hashes, validate_source_fixture_record,
)

ROOT = Path(__file__).resolve().parents[1]
sources = source_inventory


def retained(path, name):
    """Require the producer's entire current inventory, including new files."""
    data = strict_json(path.read_text())
    producer = {"mutations": "check_i5a_mutations", "measurements": "measure_i5a",
                "equivalence": "compare_i5a_cli", "investigation": "check_investigation"}[name]
    expected_sources = importlib.import_module(producer).sources()
    if (data.get("passed") is not True or data.get("sourcesStable") is not True
            or data.get("sourceHashes") != expected_sources):
        raise RuntimeError("stale, incomplete, or nonpassing retained record: " + str(path))
    if name in {"measurements", "equivalence"}:
        schema = {"measurements": "ariadne.i5a-fixture-measurements/v2",
                  "equivalence": "ariadne.i5a-cli-equivalence/v3"}[name]
        if (data.get("schema") != schema or data.get("analysisBackend") != "bap"
                or data.get("analysisProfile") != PROFILE or data.get("defaultNativeVerified") is not True
                or data.get("toolsStable") is not True or data.get("tools") != tool_hashes()
                or data.get("helperManifest") != native_manifest()):
            raise RuntimeError("retained record lacks exact native source/tool binding: " + str(path))
        if name == "equivalence" and (data.get("historicalOracleVerified") is not True
                or data.get("projectionMigrationVerified") is not True
                or data.get("validatorSha256") != sha(ROOT / "target/release/bap-admission-validate")):
            raise RuntimeError("retained equivalence lacks validated profile migration")
    elif name == "investigation":
        if data.get("qualificationEnvironment") != active_identity():
            raise RuntimeError("retained investigation qualification dependency differs")
        expected_tools = {p: sha(ROOT / p) for p in ["target/ariadne-bap-lift", "target/ariadne-llvm-mc"]}
        if data.get("tools") != expected_tools:
            raise RuntimeError("retained investigation tool inventory differs")
    elif data.get("schema") != "ariadne.i5a-mutations/v1" or data.get("observersUnchanged") is not True:
        raise RuntimeError("invalid retained I5a mutation record")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["mutations", "measurements", "equivalence", "investigation"]:
        parser.add_argument("--" + name + "-record", type=Path)
    args = parser.parse_args()
    before = sources()
    work = Path(tempfile.mkdtemp(prefix="ariadne-i5a-acceptance-"))
    env = environment()
    graph = ROOT / "tmp/graphviz-headers/root"
    if (graph / "usr/bin/dot").is_file():
        env.update(ARIADNE_DOT=str(graph / "usr/bin/dot"),
                   GVBINDIR=str(graph / "usr/lib/x86_64-linux-gnu/graphviz"),
                   LD_LIBRARY_PATH=str(graph / "usr/lib/x86_64-linux-gnu")
                   + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""))
    # Freeze executable identities only after making both required release tools
    # current. Later nested builds must reproduce these exact binaries.
    for binary, flags in [("ariadne-minidump", []), ("i5a", ["--features", "bench"])]:
        build = subprocess.run(["cargo", "build", "--offline", "--locked", "--release", *flags,
                                "--bin", binary], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        (work / (binary + "-build.log")).write_text(build.stdout + build.stderr)
        if build.returncode:
            raise RuntimeError("release prerequisite build failed: " + binary)
    tools_before, manifest = tool_hashes(), native_manifest()
    gates = [
        ("fixtures", ["python3", "tests/input/fixtures/make_i5a.py", "--check"]),
        ("format", ["cargo", "fmt", "--all", "--", "--check"]),
        ("root-tests", ["cargo", "test", "--offline", "--locked"]),
        ("core-tests", ["cargo", "test", "--offline", "--locked", "--no-default-features"]),
        ("clippy", ["cargo", "clippy", "--offline", "--locked", "--all-features", "--all-targets", "--", "-D", "warnings"]),
        ("investigation-feature", ["cargo", "clippy", "--offline", "--locked", "--no-default-features",
                                   "--features", "investigation", "--all-targets", "--", "-D", "warnings"]),
        ("layout", ["python3", "tools/check_rust_layout.py"]),
        ("native-contract-regressions", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_i5a_native_contract.py"]),
        ("controlled-contract-regressions", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_crashpad_assessment.py"]),
        ("native-corpus-cli", ["cargo", "test", "--offline", "--locked", "--release", "--test", "input_i5a", "--", "--include-ignored"]),
        ("mutations", ["python3", "tools/check_i5a_mutations.py"]),
        ("equivalence", ["python3", "tools/compare_i5a_cli.py"]),
        ("measurements", ["python3", "tools/measure_i5a.py"]),
        ("investigation", ["python3", "tools/check_investigation.py"]),
    ]
    rows, nested = [], {}
    print("I5a acceptance artifacts:", work, flush=True)
    for name, command in gates:
        start, reuse = time.monotonic(), getattr(args, name + "_record", None)
        try:
            if reuse:
                nested[name] = retained(reuse, name)
                code, output = 0, f"Reused complete source/tool-checked record: {reuse}\n"
            else:
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=2400)
                code, output = result.returncode, result.stdout + result.stderr
                for line in output.splitlines():
                    if line.startswith("Report: "):
                        path = Path(line[8:])
                        nested[name] = retained(path, name)
            if name in ["mutations", "equivalence", "measurements", "investigation"]:
                if code == 0 and nested.get(name, {}).get("passed") is not True:
                    raise RuntimeError("no passing nested " + name)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            code, output = -1, str(error)
        log = work / (name + ".log")
        log.write_text(output)
        rows.append(dict(gate=name, command=["source-tool-check", str(reuse)] if reuse else command,
                         exitCode=code, seconds=round(time.monotonic() - start, 3), log=str(log)))
        print(name, "PASS" if code == 0 else "FAIL", flush=True)
    stable, tools_after = before == sources(), tool_hashes()
    passed = stable and tools_before == tools_after and all(r["exitCode"] == 0 for r in rows)
    native_verified = all(nested.get(name, {}).get("defaultNativeVerified") is True
                          for name in ["equivalence", "measurements"])
    result = dict(schema="ariadne.i5a-acceptance/v2", recordedUtc=datetime.now(timezone.utc).isoformat(),
                  passed=passed and native_verified, sourceFixtureAcceptancePassed=passed and native_verified,
                  controlledRealWindowsAcceptancePassed=False, originalWindowsI4AcceptancePassed=False,
                  sourcesStable=stable, toolsStable=tools_before == tools_after,
                  sourceHashes=before, tools=tools_after, analysisBackend="bap", analysisProfile=PROFILE,
                  defaultNativeVerified=native_verified, helperManifest=manifest, gates=rows, records=nested,
                  missing=["No independently qualified controlled real Windows I5a case supplied; source/fixture tier only.",
                           "Original pinned Windows I4 artifact remains a separate unmet requirement."],
                  scope="Finite windows-amd64-av-scalar-mov-v1 source/fixture conformance using native captured BAP analysis; captured context and lifting premises remain explicit. No real Windows, root-cause or ISA-step qualification.")
    result["qualificationEnvironment"] = active_identity()
    if result["passed"]:
        validate_source_fixture_record(result, before, tools_after,
                                       qualification_environment=active_identity())
    (work / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
