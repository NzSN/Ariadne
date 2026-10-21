#!/usr/bin/env python3
"""Run generated correctness tests with transient output under target/."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import tempfile
import time

import hashlib

def payload(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEEDS = (0x61C4982B30A7DF05, 0x61C4982B30A7DF06)
RESULT = re.compile(r"test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def inventory():
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode().split("\0")
    paths = {name: ROOT / name for name in listed if name and
             (name.startswith(("src/", "tests/", "Specs/", "tools/", "mbt/"))
              or name in ("Cargo.toml", "Cargo.lock")) and
             not name.startswith(("mbt/results/", "mbt/stage-e/results/"))}
    client = ROOT.parent / "MirrorRust"
    for path in (client / "Cargo.toml", *sorted((client / "src").rglob("*.rs"))):
        if path.is_file():
            paths["../MirrorRust/" + str(path.relative_to(client))] = path
    return {name: payload(path) for name, path in sorted(paths.items()) if path.is_file()}


def suite_plan(seeds, cases, mbt):
    cargo = ["cargo", "test", "--offline", "--locked", "--features", "property-tests"]
    end = ["--", "--test-threads=1", "--show-output"]
    suites = [dict(name="test-output-policy", command=["python3", "-m", "unittest", "discover",
                   "-s", "tools", "-p", "test_validation_policy.py", "-q"], expectedPythonTests=4)]
    suites += [dict(name=f"core-{i}", command=cargo + ["--test", "core_properties"] + end,
                   expectedTests=3, generatedCasesPerTest=cases, seed=seed,
                   environment={"ARIADNE_CORE_PROPERTY_SEED": str(seed),
                                "ARIADNE_CORE_PROPERTY_CASES": str(cases)})
              for i, seed in enumerate(seeds)]
    suites.extend([
        dict(name="frame-path-properties", command=cargo + ["--lib", "frame_paths::properties"] + end,
             expectedTests=10, generatedCasesPerTest=128, seed=0xF0A117E58B29403C),
        dict(name="unwind-properties", command=cargo + ["--test", "frame_unwind_properties"] + end,
             expectedTests=3, generatedCasesPerTest=128, seed=0x1D82769B0AF433C5),
    ])
    if mbt in ("core", "all"):
        suites.append(dict(name="tlaplus-core-replay", command=["python3", "mbt/run.py"],
                           replayReport="mbt/results/latest.json"))
    if mbt == "all":
        suites.append(dict(name="tlaplus-stage-e-replay", command=["python3", "mbt/stage-e/run.py"],
                           replayReport="mbt/stage-e/results/latest.json"))
    return suites


def tool_identities():
    result = {}
    for name in ("cargo", "rustc", "python3"):
        executable = shutil.which(name)
        try:
            version = subprocess.check_output([name, "--version"], text=True).strip()
            result[name] = dict(version=version, executableSha256=payload(executable))
        except (OSError, subprocess.CalledProcessError) as error:
            result[name] = dict(unavailable=str(error))
    return result


def run_suites(work, suites, *, timeout=1800, identity=inventory):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=False)
    before = identity()
    tools_before = tool_identities()
    write_json(work / "inputs.json", before)
    rows = []
    for suite in suites:
        name = suite["name"]
        print("Generated validation:", name, flush=True)
        stdout, stderr = work / (name + ".stdout"), work / (name + ".stderr")
        start = time.monotonic()
        error = None
        timed_out = False
        # A nested replay report from an older run must never give a new run
        # credit. Remove only its machine-specific, ignored latest report.
        report_path = ROOT / suite["replayReport"] if "replayReport" in suite else None
        if report_path is not None:
            report_path.unlink(missing_ok=True)
        with stdout.open("wb") as out, stderr.open("wb") as err:
            try:
                with subprocess.Popen(suite["command"], cwd=ROOT,
                                      env={**os.environ, **suite.get("environment", {})},
                                      stdout=out, stderr=err, start_new_session=True) as process:
                    try:
                        code = process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                        raise
            except (OSError, subprocess.TimeoutExpired) as failure:
                code = -1
                timed_out = isinstance(failure, subprocess.TimeoutExpired)
                error = str(failure)
        row = {key: value for key, value in suite.items() if key != "environment"}
        row.update(exitCode=code, timedOut=timed_out, seconds=time.monotonic() - start,
                   stdoutSha256=payload(stdout), stderrSha256=payload(stderr))
        if code == 0 and "expectedTests" in suite:
            counts = [tuple(map(int, m)) for m in RESULT.findall(stdout.read_text(errors="replace"))]
            if counts != [(suite["expectedTests"], 0, 0)]:
                error = "expected property tests did not all execute"
            else:
                row["generatedCases"] = suite["expectedTests"] * suite["generatedCasesPerTest"]
        if code == 0 and "expectedPythonTests" in suite:
            counts = re.findall(r"Ran (\d+) tests? in", stderr.read_text(errors="replace"))
            if counts != [str(suite["expectedPythonTests"])]:
                error = "expected policy tests did not all execute"
        if code == 0 and report_path is not None:
            try:
                replay = json.loads(report_path.read_text())
                if replay.get("passed") is not True:
                    raise ValueError("nested replay did not pass")
                destination = work / (name + ".json")
                shutil.copyfile(report_path, destination)
                row["replayReportSha256"] = payload(destination)
                # Keep replay coverage/mutation results small and preserve the
                # full nested receipt beside the local raw work products.
                row["replaySummary"] = {k: replay[k] for k in
                                        ("positive", "scope", "schema") if k in replay}
                row["detectedMutants"] = len(replay.get("mutants", replay.get("mutations", [])))
            except (OSError, ValueError) as failure:
                error = "missing/invalid fresh replay report: " + str(failure)
        row["error"] = error
        row["passed"] = code == 0 and error is None
        rows.append(row)
        print(name + (": PASS" if row["passed"] else ": FAIL"), flush=True)
    stable = before == identity()
    tools_stable = tools_before == tool_identities()
    passed = bool(rows) and stable and tools_stable and all(row["passed"] for row in rows)
    receipt = dict(schema="ariadne.generated-validation/v1", passed=passed,
                   recordedUtc=datetime.now(timezone.utc).isoformat(), sourcesStable=stable,
                   gitRevision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   inputsSha256=payload(work / "inputs.json"), inputFiles=len(before),
                   generator=dict(package="proptest", version="1.9.0", maxShrinkIterations=4096),
                   tools=tools_before, toolsStable=tools_stable,
                   suites=rows, generatedCases=sum(row.get("generatedCases", 0) for row in rows),
                   unexercised=["native/capture qualification", "performance qualification",
                                "release qualification", "universal refinement"],
                   scope="finite generated Rust core/reference and selected existing property/replay tests")
    if not any("replayReport" in suite for suite in suites):
        receipt["unexercised"].append("TLA+-generated MirrorRust replay")
    if not any(suite["name"] == "tlaplus-stage-e-replay" for suite in suites):
        receipt["unexercised"].append("Stage E generated replay")
    write_json(work / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="fresh work directory under target/")
    parser.add_argument("--seed", type=lambda value: int(value, 0), action="append")
    parser.add_argument("--cases", type=int, default=256, help="cases per new core property per seed")
    parser.add_argument("--mbt", choices=("skip", "core", "all"), default="core")
    args = parser.parse_args()
    seeds = args.seed or DEFAULT_SEEDS
    if args.cases <= 0 or any(not 0 <= seed < 2**64 for seed in seeds):
        parser.error("cases must be positive; seeds must fit u64")
    root = ROOT / "target/generated-validation"
    root.mkdir(parents=True, exist_ok=True)
    if args.output:
        work = args.output.resolve()
        if not work.is_relative_to((ROOT / "target").resolve()):
            parser.error("raw work directories must live under target/")
    else:
        work = Path(tempfile.mkdtemp(prefix="run-", dir=root))
        work.rmdir()  # run_suites requires a new directory, never a reused run.
    receipt = run_suites(work, suite_plan(seeds, args.cases, args.mbt))
    print("Receipt:", work / "receipt.json", flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
