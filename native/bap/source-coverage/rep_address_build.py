#!/usr/bin/env python3
"""Build and check a separate address-size REP upstream BAP source producer.

The original source archive, SDK and previous producers remain unchanged.
Generated source copies, observations and binaries stay under ignored target/.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = importlib.util.spec_from_file_location("ariadne_rep_address_source_base", HERE / "build.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
DEFAULTS = ('f3a4', '66f3a5', 'f3a5', 'f348a5', 'f3aa', '66f3ab', 'f3ab', 'f348ab', 'f3ac', '66f3ad', 'f3ad', 'f348ad', 'f3a6', '66f3a7', 'f3a7', 'f348a7', 'f2a6', '66f2a7', 'f2a7', 'f248a7', 'f3ae', '66f3af', 'f3af', 'f348af', 'f2ae', '66f2af', 'f2af', 'f248af')
DEFAULT_LODS = ('f3ac', '66f3ad', 'f3ad', 'f348ad')
ADDRESS32 = tuple("67" + code for code in DEFAULTS)
CODES = (*DEFAULT_LODS, *ADDRESS32)
NEGATIVES = tuple(dict.fromkeys(
    [prefix + code for prefix in ("f0", "f2", "f3", "64", "65", "67", "48") for code in ADDRESS32]
    + [code.replace("67", "", 1).replace("f3", "f367", 1).replace("f2", "f267", 1)
       for code in ADDRESS32]
    + ["6740" + code for code in DEFAULTS]))
BASELINES = ("90", "fc", "f8", "4889e0", *(code for code in DEFAULTS if code not in DEFAULT_LODS))
TRAILING = tuple(code + "90" for code in CODES)
CASES = (*CODES, *NEGATIVES, *BASELINES, *TRAILING)
SOURCES = ("rep_address_build.py", "rep_address_lift.ml", "rep_address_probe.ml", "rep_address.patch", "lods.patch", "build.py")



def bind_observations(text):
    rows = [json.loads(line) for line in text.splitlines()]
    base.require(len(rows) == len(CASES), "REP address-size source observation count")
    for code, row in zip(CASES, rows):
        base.require(row.get("schema") == "ariadne.bap-source-rep-address-observation/v1"
                     and row.get("bytes") == code and row.get("production") is False,
                     "REP address-size source observation identity")
    return dict(zip(CASES, rows))


def verify_transition(before, after):
    wrong = {"67f3a4", "6766f3a5", "67f3a5", "67f348a5"}
    for code in CODES:
        if code in wrong:
            base.require(before[code]["status"] == "lifted", "original address32 MOVS gap not reproduced")
            base.require(before[code]["bilText"] != after[code]["bilText"], "incorrect address32 MOVS lift unchanged")
        else:
            base.require(before[code]["status"] == "missing-semantics", "original REP source gap not reproduced: " + code)
        base.require(after[code]["status"] == "lifted" and after[code].get("wellTyped") is True
                     and after[code].get("length") == len(code) // 2, "patched REP must be typed and complete: " + code)
    for code in NEGATIVES:
        base.require(after[code]["status"] in {"missing-semantics", "error"},
                     "non-admitted address32 form gained semantics: " + code)
    for code in TRAILING:
        base.require(after[code]["status"] == "trailing-bytes", "REP trailing bytes accepted as one form")
    for code in BASELINES:
        base.require(before[code] == after[code], "unrelated original BAP observation changed: " + code)
    return {"newTypedForms": len(CODES) - len(wrong), "correctedTypedForms": len(wrong),
            "typedForms": len(CODES), "refusedNeighbors": len(NEGATIVES),
            "trailingSequences": len(TRAILING), "unchangedBaselineObservations": len(BASELINES)}


def build_variant(folder, sdk, env):
    build = folder / "build"
    build.mkdir()
    for relative in base.MODULES:
        shutil.copyfile(folder / relative, build / Path(relative).name)
    shutil.copyfile(HERE / "rep_address_probe.ml", build / "rep_address_probe.ml")
    base.command(folder / "build.log", [sdk.PREFIX / "bin/ocamlfind", "ocamlopt", "-linkpkg",
                 "-package", "bap,core_kernel,ppx_bap,yojson", "-o", "rep-address-probe",
                 *(Path(path).name for path in base.MODULES), "rep_address_probe.ml"], cwd=build, env=env)
    # A fresh process per instruction keeps temporary Var indices independent
    # of the newly implemented preceding cases in the comparison corpus.
    text = "".join(base.command(folder / ("probe-" + code + ".log"),
                               [build / "rep-address-probe", code], cwd=build, env=env) for code in CASES)
    rows = bind_observations(text)
    base.write_json(folder / "observations.json", rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    base.require(output != ROOT / "target" and output.is_relative_to((ROOT / "target").resolve()),
                 "output must be a fresh child of root target/")
    output.mkdir(parents=True, exist_ok=False)
    sdk = base.load_sdk()
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    lock = json.loads(sdk.LOCK.read_text())
    archive = ROOT / lock["bapSourceArchive"]["path"]
    base.require(base.sha(archive) == lock["bapSourceArchive"]["sha256"], "upstream archive differs")
    identities = {str(path.relative_to(ROOT)): base.sha(path) for path in (
        *(HERE / name for name in SOURCES), sdk.LOCK, sdk.BASE / "sdk-manifest.json",
        sdk.PREFIX / "bin/ocamlopt.opt", HERE / "runtime.lock.json", HERE / "advanced.runtime.lock.json",
        HERE / "lods.runtime.lock.json")}
    base.command(output / "sdk-before.log", [sys.executable, base.SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    before, after = output / "baseline", output / "patched"
    before.mkdir()
    after.mkdir()
    upstream = base.extract_sources(archive, lock["bapSourceRevision"], before)
    base.require(base.extract_sources(archive, lock["bapSourceRevision"], after) == upstream, "extraction differs")
    old = build_variant(before, sdk, env)
    base.command(output / "patch.log", ["patch", "--batch", "--fuzz=0", "-p1", "-i", HERE / "lods.patch"],
                 cwd=after, env=env)
    base.command(output / "address-patch.log", ["patch", "--batch", "--fuzz=0", "-p1", "-i", HERE / "rep_address.patch"],
                 cwd=after, env=env)
    new = build_variant(after, sdk, env)
    transition = verify_transition(old, new)
    binding = dict(base_revision=lock["bapSourceRevision"], source_archive_sha256=base.sha(archive),
                   upstream_modules=upstream, patched_modules={p: base.sha(after / p) for p in base.MODULES},
                   sources={name: base.sha(HERE / name) for name in SOURCES},
                   sdk_lock_sha256=base.sha(sdk.LOCK), sdk_manifest_sha256=base.sha(sdk.BASE / "sdk-manifest.json"),
                   compiler_sha256=base.sha(sdk.PREFIX / "bin/ocamlopt.opt"))
    build_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    build = after / "build"
    (build / "build_identity.ml").write_text("let build_id = " + json.dumps(build_id) + "\n")
    shutil.copyfile(HERE / "rep_address_lift.ml", build / "rep_address_lift.ml")
    base.command(after / "runtime-build.log", [sdk.PREFIX / "bin/ocamlfind", "ocamlopt", "-linkpkg",
                 "-package", "bap,core_kernel,ppx_bap,yojson", "-o", "rep-address-lift",
                 *(Path(path).name for path in base.MODULES), "build_identity.ml", "rep_address_lift.ml"], cwd=build, env=env)
    runtime = output / "runtime"
    runtime.mkdir()
    shutil.copyfile(build / "rep-address-lift", runtime / "rep-address-lift")
    (runtime / "rep-address-lift").chmod(0o755)
    manifest = dict(schema="ariadne.bap-source-rep-address-build/v1", profiles=["bap-bit-provenance-v15"],
                    runtime_role="rep-address-source", vendor="AMD",
                    semantic_premises=["amd-long-mode-memory-rep", "address32-zero-count-preserves-upper-lanes"],
                    cases=sorted(CODES), binding=binding, build_id=build_id,
                    executable="rep-address-lift", executable_sha256=base.sha(runtime / "rep-address-lift"), max_response_bytes=65536,
                    scope="Four exact default-address REP LODS and 28 exact AMD address32 memory REP forms; separately admitted analysis and consumer receipts required.")
    base.write_json(runtime / "manifest.json", manifest)
    for target in ("windows-amd64", "linux-amd64"):
        for code in CODES:
            snapshot, va = "c" * 64, "0xffff800000401000"
            text = base.command(output / ("runtime-" + target + "-" + code + ".log"),
                                [runtime / "rep-address-lift", target, snapshot, va, code], cwd=ROOT, env=env)
            row = json.loads(text)
            base.require(set(row) == {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}
                         and row["schema"] == "ariadne.bap-source-rep-address/v1" and row["build_id"] == build_id
                         and row["target"] == target and row["snapshot"] == snapshot and row["va"] == va
                         and row["bytes"] == code and row["length"] == len(code) // 2 and bool(row["bil"])
                         and len(text.encode()) <= manifest["max_response_bytes"], "REP address-size runtime binding/extent")
    for code in (*NEGATIVES, *TRAILING, *BASELINES):
        result = subprocess.run([str(runtime / "rep-address-lift"), "linux-amd64", "c" * 64,
                                 "0xffff800000401000", code], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=10)
        base.require(result.returncode != 0 and not result.stdout, "runtime accepted non-admitted bytes: " + code)
    base.command(output / "sdk-after.log", [sys.executable, base.SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    base.require(all(base.sha(ROOT / p) == digest for p, digest in identities.items()), "SDK/source/old lock changed")
    report = dict(schema="ariadne.bap-source-rep-address-build-check/v1", passed=True, transition=transition,
                  identities=identities, runtimeManifestSha256=base.sha(runtime / "manifest.json"),
                  runtimeExecutableSha256=manifest["executable_sha256"],
                  scope="Typechecked upstream source transition and bounded typed transport; independent numeric oracle and host admission separate.")
    base.write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
