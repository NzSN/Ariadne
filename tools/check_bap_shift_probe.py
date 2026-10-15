#!/usr/bin/env python3
"""Compile/run a pinned BAP Word/constant-fold probe on the remote build host.

--check-source is a portable, non-building check of the finite independent
integer controls. The default operation compiles C++ and belongs on the root's
authorized remote WSL host. No runtime files or historical evidence are edited.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/bap/fixtures/shifts/pinned-shift-probe.cpp"
LOCK = ROOT / "native/bap/toolchain.lock.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_shift(op, data, count, width):
    """Unbounded integer equations, with bounded overshift before host shifts."""
    modulus = 1 << width
    data %= modulus
    if op == 11:
        return 0 if count >= width else (data * (1 << count)) % modulus
    if op == 10:
        return 0 if count >= width else data // (1 << count)
    if op == 9:
        signed = data - modulus if data >= modulus // 2 else data
        if count >= width:
            return modulus - 1 if signed < 0 else 0
        return (signed // (1 << count)) % modulus
    raise ValueError("not a BAP shift operator")


def cases():
    rows = []
    seen = set()

    def add(op, width, count_width, data, count, data_signed=False, count_signed=False):
        key = (op, width, count_width, data, count, data_signed, count_signed)
        if key in seen or count >= 1 << count_width:
            return
        seen.add(key)
        rows.append({"name": f"shift-{len(rows):04}", "op": op,
                     "data_width": width, "count_width": count_width,
                     "data": hex(data), "count": hex(count),
                     "data_signed": data_signed, "count_signed": count_signed,
                     "expected": hex(expected_shift(op, data, count, width))})

    for width in (1, 8, 32, 64, 128, 256):
        mask = (1 << width) - 1
        patterns = sorted({0, 1, 1 << (width - 1),
                           ((1 << (width - 1)) | 1) & mask, mask, 0xA5 & mask})
        for count_width in (1, 8, 64, 128, 256):
            counts = {0, 1, width - 1, width, width + 1,
                      (1 << count_width) - 1, 1 << (count_width - 1)}
            if count_width > 64:
                counts.add(1 << 64)
            for op in (9, 10, 11):
                for data in patterns:
                    for count in sorted(counts):
                        add(op, width, count_width, data, count)

    # Metadata must not convert the count to a negative host shift, nor control
    # ARSHIFT's sign fill: that fill is determined by the data's most significant bit.
    for width, count_width in ((8, 8), (128, 8), (128, 128), (256, 256)):
        for op in (9, 10, 11):
            for data in (1, (1 << (width - 1)) | 1):
                for count in (1, (1 << count_width) - 1):
                    for data_signed in (False, True):
                        for count_signed in (False, True):
                            add(op, width, count_width, data, count,
                                data_signed, count_signed)
    if not 1 <= len(rows) <= 8192:
        raise ValueError("probe case limit")
    assert any(r["data_width"] == 128 and r["count_width"] == 8 for r in rows)
    assert any(int(r["count"], 16) > (1 << 64) - 1 for r in rows)
    assert any(r["count_signed"] and int(r["count"], 16) >=
               1 << (r["count_width"] - 1) for r in rows)
    return rows


def verify_runtime(runtime, lock):
    actual = {}
    for relative, expected in lock["files"].items():
        path = runtime / relative
        if not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"pinned runtime file missing/changed: {path}")
        actual[relative] = sha(path)
    return actual


def word_value(text, width):
    match = re.fullmatch(r"([^:]+):([0-9]+)[us]?", text)
    if not match or int(match[2]) != width:
        raise ValueError(f"unexpected BAP word representation: {text}")
    return int(match[1], 0) % (1 << width)


def word_metadata(text, width):
    match = re.fullmatch(r"[^:]+:([0-9]+)([us])", text)
    if not match or int(match[1]) != width:
        raise ValueError(f"BAP did not expose requested word metadata: {text}")
    return match[2] == "s"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "target/bap-shift-probe")
    parser.add_argument("--output", type=Path, help="new qualification JSON record")
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--check-source", action="store_true")
    args = parser.parse_args()
    controls = cases()
    if args.check_source:
        assert SOURCE.is_file()
        for width in (1, 8, 32, 64, 128, 256):
            assert expected_shift(11, 1, width, width) == 0
            assert expected_shift(10, (1 << width) - 1, width, width) == 0
            assert expected_shift(9, (1 << width) - 1, width, width) == (1 << width) - 1
        print(f"Pinned shift probe portable source controls PASS: {len(controls)} cases; no compilation/runtime executed")
        return 0
    if args.output is None:
        parser.error("--output is required for the remote compile/run")
    runtime = args.runtime.resolve()
    build = args.build_dir.resolve()
    if not build.is_relative_to(ROOT / "target"):
        parser.error("--build-dir must be an isolated directory under the root target/")
    output = args.output.resolve()
    if output.exists():
        parser.error("--output already exists; preserve it and select a new evidence filename")
    build.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = json.loads(LOCK.read_text())
    source_paths = [SOURCE, Path(__file__).resolve(), LOCK]
    before = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    record = {"schema": "ariadne.bap-shift-primitive-probe/v1",
              "recordedUtc": datetime.now(timezone.utc).isoformat(), "passed": False,
              "sourceHashes": before, "runtimeRoot": str(runtime),
              "buildDirectory": str(build),
              "toolchainLock": lock, "cases": controls, "commands": [],
              "staticTypeInferenceExercised": False,
              "scope": "Exact pinned BAP library Word shifts and constant-folded literal BIL; no exported static type-inference API, no ISA/hardware or source-to-binary build proof.",
              "unexercised": ["BAP Exp.Type.infer through binary API", "hardware instruction stepping",
                              "source-to-binary reproducible build provenance", "Ariadne runtime projection"]}
    try:
        record["runtimeFilesBefore"] = verify_runtime(runtime, lock)
        compiler = shutil.which(args.cxx)
        if not compiler:
            raise RuntimeError("selected C++ compiler unavailable")
        compiler = str(Path(compiler).resolve())
        record["compiler"] = {"path": compiler, "sha256": sha(compiler),
                              "version": subprocess.check_output([compiler, "--version"], text=True)}
        executable = build / "ariadne-bap-shift-probe"
        library = runtime / "usr/local/lib/libbap.so.2.5.0"
        command = [compiler, "-std=c++23", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-parameter", "-I" + str(runtime / "usr/local/include"),
                   str(SOURCE), str(library), "-Wl,-rpath-link," +
                   str(runtime / "usr/lib/x86_64-linux-gnu"), "-ldl", "-o", str(executable)]
        record["commands"].append(command)
        compiled = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
        (build / "build.log").write_text(compiled.stdout + compiled.stderr)
        record["compileExitCode"] = compiled.returncode
        record["compileLogSha256"] = sha(build / "build.log")
        if compiled.returncode:
            raise RuntimeError("C++ probe compile failed; see private build.log")
        record["executableSha256"] = sha(executable)
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(runtime / "usr/local/lib") + ":" + str(
            runtime / "usr/lib/x86_64-linux-gnu") + (
                ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        protocol = "".join(" ".join(str(v) for v in (
            row["name"], row["op"], row["data_width"], row["count_width"],
            row["data"], row["count"], int(row["data_signed"]), int(row["count_signed"])
        )) + "\n" for row in controls)
        (build / "cases.txt").write_text(protocol)
        record["caseProtocolSha256"] = sha(build / "cases.txt")
        command = [str(executable), str(runtime / "usr/local/lib/bap")]
        record["commands"].append(command)
        record["runtimeEnvironment"] = {"LD_LIBRARY_PATH": env["LD_LIBRARY_PATH"]}
        ran = subprocess.run(command, cwd=ROOT, env=env, input=protocol,
                             text=True, capture_output=True, timeout=120)
        (build / "stdout.jsonl").write_text(ran.stdout)
        (build / "stderr.log").write_text(ran.stderr)
        record["runExitCode"] = ran.returncode
        record["stdoutSha256"] = sha(build / "stdout.jsonl")
        record["stderrSha256"] = sha(build / "stderr.log")
        if ran.returncode:
            raise RuntimeError("pinned API probe failed; see retained stdout/stderr")
        observed = [json.loads(line) for line in ran.stdout.splitlines()]
        ready, rows = observed[0], observed[1:]
        if (ready.get("schema") != "ariadne.bap-shift-probe-ready/v1" or
                ready.get("version") != lock["reportedLibraryVersion"] or
                ready.get("static_typing_api_exercised") is not False):
            raise RuntimeError("probe ready/version/scope mismatch")
        loaded = Path(ready["loaded_library"]).resolve()
        if sha(loaded) != lock["files"]["usr/local/lib/libbap.so.2.5.0"]:
            raise RuntimeError("actual loaded library does not match production pin")
        record["loadedLibrary"] = {"path": str(loaded), "sha256": sha(loaded)}
        record["ready"] = ready
        if len(rows) != len(controls):
            raise RuntimeError("probe row count mismatch")
        for expected, actual in zip(controls, rows):
            if (actual.get("schema") != "ariadne.bap-shift-probe-row/v1" or
                    actual.get("name") != expected["name"] or actual.get("op") != expected["op"] or
                    actual.get("static_type_inference_claimed") is not False):
                raise RuntimeError("probe row identity/scope mismatch")
            for field, width in (("data_width", expected["data_width"]),
                                 ("count_width", expected["count_width"]),
                                 ("input_expression_lhs_width", expected["data_width"]),
                                 ("input_expression_rhs_width", expected["count_width"]),
                                 ("primitive_width", expected["data_width"]),
                                 ("folded_width", expected["data_width"])):
                if actual[field] != width:
                    raise RuntimeError(f"{expected['name']} operand/result width mismatch: {field}")
            for field, width, number, signed in (
                    ("data_word", expected["data_width"], expected["data"], expected["data_signed"]),
                    ("count_word", expected["count_width"], expected["count"], expected["count_signed"])):
                if word_value(actual[field], width) != int(number, 16) or word_metadata(actual[field], width) != signed:
                    raise RuntimeError(f"{expected['name']} input payload/signed metadata mismatch: {field}")
            if actual["constructor_expression_tag"] == "binop":
                if (actual["constructor_operand_widths_observable"] is not True or
                        actual["constructor_lhs_width"] != expected["data_width"] or
                        actual["constructor_rhs_width"] != expected["count_width"] or
                        actual["constructor_folded_width"] is not None or
                        actual["constructor_folded_word"] is not None):
                    raise RuntimeError(f"{expected['name']} constructor operand observation mismatch")
            elif actual["constructor_expression_tag"] == "int":
                if (actual["constructor_operand_widths_observable"] is not False or
                        actual["constructor_lhs_width"] is not None or
                        actual["constructor_rhs_width"] is not None or
                        actual["constructor_folded_width"] != expected["data_width"] or
                        word_value(actual["constructor_folded_word"], expected["data_width"]) !=
                        int(expected["expected"], 16)):
                    raise RuntimeError(f"{expected['name']} smart-constructor literal result mismatch")
            else:
                raise RuntimeError(f"{expected['name']} unsupported constructor tag")
            for field in ("primitive_word", "folded_word"):
                if word_value(actual[field], expected["data_width"]) != int(expected["expected"], 16):
                    raise RuntimeError(f"{expected['name']} concrete value mismatch: {field}")
        record["observations"] = rows
        record["runtimeFilesAfter"] = verify_runtime(runtime, lock)
        after = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
        record["sourcesStable"] = after == before
        if after != before or record["runtimeFilesAfter"] != record["runtimeFilesBefore"]:
            raise RuntimeError("source/runtime changed during probe")
        record["primitiveAndConstantFoldComparisons"] = len(rows)
        record["constructorAlreadyFoldedCases"] = sum(r["constructor_expression_tag"] == "int" for r in rows)
        record["constructorRetainedBinopCases"] = sum(r["constructor_expression_tag"] == "binop" for r in rows)
        record["passed"] = True
    except Exception as error:
        record["failure"] = str(error)
    output.write_text(json.dumps(record, indent=2) + "\n")
    print("Pinned BAP shift probe:", "PASS" if record["passed"] else "FAIL")
    print("Report:", output)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
