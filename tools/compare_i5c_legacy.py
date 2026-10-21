#!/usr/bin/env python3
"""Compare all 666 regression outputs with the checked-in golden vector.

This tool never derives expected values from current SUT output. The vector
contains only expected byte counts and hashes, not prior passing results.
"""
import argparse
from pathlib import Path

from compare_i5a_cli import without_verified_receipt
from i5a_native_contract import environment, native_manifest, validate_backend_receipt
from i5c_qualification import (FIXTURES, ROOT, artifact, command, read_json,
                               require, sha, sources, write_json)

FORMATS = ("text", "json", "dot")
BUNDLE = ("report.txt", "report.json", "report.dot", "explanation.txt", "explanation.json", "explanation.dot")
BASE_CASES = ("linux-stage-b", "windows-stage-b", "bap-precision-not", "pinned-real-capture")
# Reviewed expected-value vector; a caller cannot substitute current outputs.
LEGACY_BASELINE_SHA256 = "c0108f5f92fb003ffa869c3fbcbb30b0b72b1918df5e33ac786de724d2b65af9"


def expected_keys():
    keys = []
    for profile in ("i5a", "i5b"):
        rows = read_json(ROOT / ("tests/input/fixtures/" + profile + "/manifest.json"))["cases"]
        for row in rows:
            for backend in ("rust", "bap"):
                keys.extend(f"{profile}/{row['name']}/{backend}/{fmt}" for fmt in FORMATS)
    keys.extend(f"i5b-upstream/{backend}/{fmt}" for backend in ("rust", "bap") for fmt in FORMATS)
    keys.extend(f"base/{case}/{backend}/{filename}" for case in BASE_CASES
                for backend in ("rust", "default", "bap") for filename in BUNDLE)
    require(len(keys) == len(set(keys)) == 666, "changed legacy case inventory")
    return set(keys)


def baseline(path, expected_digest):
    require(expected_digest == LEGACY_BASELINE_SHA256, "baseline pin differs from the checked-in expected vector")
    require(sha(path) == expected_digest, "expected vector digest differs")
    value = read_json(path)
    require(value.get("schema") == "ariadne.i5c-legacy-bytes/v1", "unsupported expected vector schema")
    require(set(value.get("outputs", {})) == expected_keys(), "retained baseline must cover all 666 named outputs")
    for row in value["outputs"].values():
        require(type(row.get("bytes")) is int and row["bytes"] >= 0, "invalid baseline byte count")
        digest = row.get("sha256")
        require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
                "invalid baseline output digest")
    return value


def base_cases():
    import real_capture_workload
    case = real_capture_workload.load_case()
    dump = real_capture_workload.selected_dump(case)
    return [
        (BASE_CASES[0], ROOT / "tests/input/fixtures/stage_b_linux.dmp", "401000", "401006"),
        (BASE_CASES[1], ROOT / "tests/input/fixtures/stage_b_windows.dmp", "7ff700001000", "7ff700001006"),
        (BASE_CASES[2], ROOT / "tests/input/fixtures/bap_precision_linux.dmp", "401000", "401006"),
        (BASE_CASES[3], dump, case["query"]["entry_va"], case["query"]["seed_va"]),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--expected-baseline-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    before, actual, failure, comparisons = sources(), {}, None, 0
    cli = ROOT / "target/release/ariadne-minidump"
    tools_before = {str(p): artifact(p) for p in (cli, ROOT / "target/ariadne-llvm-mc") if p.is_file()}
    def check(key, path):
        item = artifact(path)
        actual[key] = {"bytes": item["bytes"], "sha256": item["sha256"]}
        require(actual[key] == expected["outputs"][key], "legacy bytes differ: " + key)
    try:
        expected = baseline(args.baseline, args.expected_baseline_sha256)
        def run(label, dump, entry, site, flags):
            receipt, _, _ = command(work / "commands" / label, "cli", [
                cli, dump, "--decoder-reference", ROOT / "target/ariadne-llvm-mc", "--entry", entry,
                *flags], env=environment())
            require(receipt["exitCode"] == 0 and not receipt["timedOut"], "legacy CLI failed: " + label)
            return Path(receipt["stdout"]["path"])
        for profile, option in (("i5a", "--assess-zero-address"), ("i5b", "--assess-zero-base-offset")):
            for row in read_json(ROOT / f"tests/input/fixtures/{profile}/manifest.json")["cases"]:
                for backend in ("rust", "bap"):
                    for fmt in FORMATS:
                        key = f"{profile}/{row['name']}/{backend}/{fmt}"
                        site = f"0x{row['site']:016x}"
                        output = run(key, ROOT / f"tests/input/fixtures/{profile}/{row['name']}.dmp", site, site,
                                     [option, site, "--memory-access", "0", "--analysis-backend", backend,
                                      "--assessment-only", "--format", fmt])
                        check(key, output)
        for backend in ("rust", "bap"):
            for fmt in FORMATS:
                key = f"i5b-upstream/{backend}/{fmt}"
                output = run(key, ROOT / "tests/input/fixtures/i5b/upstream-call.dmp", "401000", "401005",
                             ["--assess-zero-base-offset", "401005", "--memory-access", "0",
                              "--analysis-backend", backend, "--assessment-only", "--format", fmt])
                check(key, output)
        manifest = native_manifest()
        for name, dump, entry, site in base_cases():
            outputs = {}
            for backend in ("rust", "default", "bap"):
                directory = work / "bundles" / name / backend
                directory.parent.mkdir(parents=True, exist_ok=True)
                flags = ["--explain-fault-address", site, "--memory-access", "0", "--output-dir", str(directory)]
                if backend != "default":
                    flags += ["--analysis-backend", backend]
                run(f"base/{name}/{backend}", dump, entry, site, flags)
                require({p.name for p in directory.iterdir()} == set(BUNDLE), "legacy bundle file inventory differs")
                outputs[backend] = directory
                for filename in BUNDLE:
                    check(f"base/{name}/{backend}/{filename}", directory / filename)
            for filename in BUNDLE:
                require((outputs["default"] / filename).read_bytes() == (outputs["bap"] / filename).read_bytes(),
                        "default/explicit native output differs")
                comparisons += 1
            for filename in BUNDLE[3:]:
                require((outputs["default"] / filename).read_bytes() == (outputs["rust"] / filename).read_bytes(),
                        "native/reference explanation differs")
                comparisons += 1
            native = read_json(outputs["default"] / "report.json")
            validate_backend_receipt(native, manifest)
            normalized = without_verified_receipt(native, (outputs["default"] / "report.txt").read_text(),
                                                  (outputs["default"] / "report.dot").read_text(), manifest)
            require(normalized == (read_json(outputs["rust"] / "report.json"),
                                   (outputs["rust"] / "report.txt").read_text(),
                                   (outputs["rust"] / "report.dot").read_text()), "native/reference core differs")
        require(set(actual) == expected_keys() and comparisons == 36, "legacy coverage incomplete")
        require(sources() == before, "sources changed during compatibility comparison")
        require(all(artifact(path) == identity for path, identity in tools_before.items()), "legacy tools changed")
    except (OSError, ValueError, KeyError) as error:
        failure = str(error)
    record = {"schema": "ariadne.i5c-legacy-comparison/v1", "passed": failure is None,
              "sourceHashes": before, "sourcesStable": sources() == before, "tools": tools_before,
              "baselineSha256": args.expected_baseline_sha256, "actual": actual,
              "parityComparisons": comparisons, "failure": failure, "baselineRegenerated": False}
    write_json(work / "report.json", record)
    print("Report:", work / "report.json", flush=True)
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
