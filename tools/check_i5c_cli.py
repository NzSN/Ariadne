#!/usr/bin/env python3
"""Run all twelve frozen W4 controls against Cargo-selected native CLI artifacts."""
import argparse
from pathlib import Path

from i5a_native_contract import environment
from with_mirrorrust_snapshot import active_identity
from i5c_qualification import (ROOT, artifact, build_test, cargo_artifact, command,
                               observe, prerequisite_report, read_json, require,
                               sources, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    prerequisites = prerequisite_report()
    write_json(work / "prerequisites.json", prerequisites)
    rows, failure = [], None
    unit = cli = suite = None
    tools_before = prerequisites["tools"]
    try:
        require(prerequisites["passed"], "native/dependency prerequisites unavailable; see prerequisites.json")
        target = ROOT / "target/i5c-cli" / work.name
        unit = build_test(work / "unit-build", ("bin", "ariadne-minidump"), target)
        suite = build_test(work / "suite-build", ("test", "input_address_wrap_cli"), target)
        receipt, stdout, _ = command(work / "cli-build", "build", [
            "cargo", "build", "--offline", "--locked", "--release", "--message-format=json",
            "--bin", "ariadne-minidump", "--target-dir", target])
        require(receipt["exitCode"] == 0, "normal CLI build failed")
        cli = cargo_artifact(stdout, "ariadne-minidump", kind="bin", test=False, target_dir=target)
        # Integration tests use Cargo's embedded CARGO_BIN_EXE value; both the
        # normal CLI and the test suite must come from this one target directory.
        env = {**environment(), "ARIADNE_CLI_UNIT_TEST_BINARY": unit["path"],
               "ARIADNE_CLI_UNIT_TEST_SHA256": unit["sha256"],
               "ARIADNE_CLI_TEST_OUTPUT_ROOT": str(work / "cli-artifacts")}
        names = read_json(ROOT / "tests/input/fixtures/i5c/qualification-matrix.json")["cli_cases"]
        require(len(names) == 12 and len(set(names)) == 12, "changed frozen CLI inventory")
        for name in names:
            test = name.replace("-", "_")
            row, _, _ = observe(work / name, suite["path"], test, env=env)
            require(artifact(cli["path"]) == cli, "normal CLI changed during controls")
            rows.append({"name": name, "passed": True, **row})
            print(name + ": PASS", flush=True)
        require(prerequisite_report()["tools"] == tools_before, "native tools changed during CLI controls")
        require(sources() == before, "source inventory changed during CLI controls")
        require(active_identity() == prerequisites["qualificationEnvironment"], "dependency changed during CLI controls")
    except (OSError, ValueError, KeyError) as error:
        failure = str(error)
    passed = failure is None and len(rows) == 12
    record = {"schema": "ariadne.i5c-w4-cli/v1", "passed": passed,
              "sourceHashes": before, "sourcesStable": sources() == before,
              "tools": tools_before, "qualificationEnvironment": prerequisites["qualificationEnvironment"],
              "cases": rows, "cli": cli, "suite": suite, "unit": unit,
              "failure": failure, "ownedCapturesQualified": False}
    write_json(work / "report.json", record)
    print("Report:", work / "report.json", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
