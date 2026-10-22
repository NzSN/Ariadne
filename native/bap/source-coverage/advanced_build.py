#!/usr/bin/env python3
"""Build the separately pinned producer for advanced analysis profiles.

Reuses the reviewed upstream four-flag patch and independent numeric controls.
The old v9 builder and runtime lock are immutable inputs. Building this bundle
does not by itself qualify any advanced analysis or full instruction coverage.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("ariadne_basic_source_flags", HERE / "build.py")
basic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(basic)
PROFILES = ["bap-bit-provenance-v10", "bap-bit-provenance-v11"]
SOURCES = ("advanced_build.py", "advanced_flag_lift.ml", "build.py", "flag_probe.ml", "flags.patch")


def manifest(binding, executable):
    build_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "ariadne.bap-source-advanced-build/v1",
        "profiles": PROFILES,
        "runtime_role": "advanced-source-flags",
        "scope": "Actual BAP BIL for exact unprefixed F5/F8/F9/FD; advanced analysis requires separate host/native receipt admission and executable validation.",
        "cases": sorted(basic.NEW_FLAGS),
        "binding": binding,
        "build_id": build_id,
        "executable": "flag-lift",
        "executable_sha256": basic.sha(executable),
        "max_response_bytes": 4096,
    }


def build_runtime(folder, sdk, env, binding):
    build = folder / "build"
    build_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (build / "build_identity.ml").write_text("let build_id = " + json.dumps(build_id) + "\n")
    shutil.copyfile(HERE / "advanced_flag_lift.ml", build / "advanced_flag_lift.ml")
    basic.command(folder / "runtime-build.log", [sdk.PREFIX / "bin/ocamlfind", "ocamlopt", "-linkpkg",
                  "-package", "bap,core_kernel,ppx_bap,yojson", "-o", "flag-lift",
                  *(Path(p).name for p in basic.MODULES), "build_identity.ml", "advanced_flag_lift.ml"],
                  cwd=build, env=env)
    for target in ("windows-amd64", "linux-amd64"):
        for code in basic.NEW_FLAGS:
            snapshot, va = "b" * 64, "0xffff800000401000"
            text = basic.command(folder / ("runtime-" + target + "-" + code + ".log"),
                                 [build / "flag-lift", target, snapshot, va, code], cwd=build, env=env)
            row = json.loads(text)
            basic.require(set(row) == {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}
                          and row["schema"] == "ariadne.bap-source-flags/v1" and row["build_id"] == build_id
                          and row["target"] == target and row["snapshot"] == snapshot
                          and row["va"] == va and row["bytes"] == code and row["length"] == 1,
                          "advanced runtime identity/extent differs")

            def expression(value):
                if value["kind"] == "int":
                    return dict(value, width=int(value["value"].split(":")[1].rstrip("us")))
                if value["kind"] == "var":
                    return value
                basic.require(value["kind"] == "unop" and value["op"] == 0, "unexpected runtime operator")
                return dict(kind="not", arg=expression(value["arg"]))

            basic.verify_flag(code, dict(status="lifted", wellTyped=True, length=1,
                                        bil=[dict(s, value=expression(s["value"])) for s in row["bil"]]))
    runtime = folder.parent / "runtime"
    runtime.mkdir()
    shutil.copyfile(build / "flag-lift", runtime / "flag-lift")
    (runtime / "flag-lift").chmod(0o755)
    result = manifest(binding, runtime / "flag-lift")
    basic.write_json(runtime / "manifest.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="fresh ignored target/ directory")
    args = parser.parse_args()
    output = args.output.resolve()
    basic.require(output != ROOT / "target" and output.is_relative_to((ROOT / "target").resolve()),
                  "output must be a fresh child of root target/")
    output.mkdir(parents=True, exist_ok=False)
    sdk = basic.load_sdk()
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    lock = json.loads(sdk.LOCK.read_text())
    archive = ROOT / lock["bapSourceArchive"]["path"]
    basic.require(basic.sha(archive) == lock["bapSourceArchive"]["sha256"], "upstream source archive differs")
    identities = {str(path.relative_to(ROOT)): basic.sha(path) for path in (
        *(HERE / name for name in SOURCES), HERE / "runtime.lock.json", sdk.LOCK,
        sdk.BASE / "sdk-manifest.json", sdk.PREFIX / "bin/ocamlopt.opt")}
    basic.command(output / "sdk-before.log", [sys.executable, basic.SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    baseline, patched = output / "baseline", output / "patched"
    baseline.mkdir()
    patched.mkdir()
    upstream = basic.extract_sources(archive, lock["bapSourceRevision"], baseline)
    basic.require(basic.extract_sources(archive, lock["bapSourceRevision"], patched) == upstream,
                  "upstream source extraction differs")
    old = basic.build_variant(baseline, sdk, env)
    basic.command(output / "patch.log", ["patch", "--batch", "--fuzz=0", "-p1", "-i", HERE / "flags.patch"],
                  cwd=patched, env=env)
    new = basic.build_variant(patched, sdk, env)
    equations = basic.verify_transition(old, new)
    result = build_runtime(patched, sdk, env, dict(
        base_revision=lock["bapSourceRevision"], source_archive_sha256=basic.sha(archive),
        upstream_modules=upstream, patched_modules={p: basic.sha(patched / p) for p in basic.MODULES},
        sources={name: basic.sha(HERE / name) for name in SOURCES},
        sdk_lock_sha256=basic.sha(sdk.LOCK), sdk_manifest_sha256=basic.sha(sdk.BASE / "sdk-manifest.json"),
        compiler_sha256=basic.sha(sdk.PREFIX / "bin/ocamlopt.opt")))
    basic.command(output / "sdk-after.log", [sys.executable, basic.SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    basic.require(all(basic.sha(ROOT / path) == digest for path, digest in identities.items()),
                  "source/SDK/basic lock changed during advanced build")
    report = dict(schema="ariadne.bap-source-advanced-build-check/v1", passed=True,
                  scope="Source producer equations and transport only; not advanced analysis qualification or full AMD64 coverage",
                  independentEquations=equations, identities=identities,
                  observationCountPerVariant=len(basic.CASES), profiles=PROFILES,
                  runtimeManifestSha256=basic.sha(output / "runtime/manifest.json"),
                  runtimeExecutableSha256=result["executable_sha256"])
    basic.write_json(output / "report.json", report)
    print(json.dumps({"passed": True, "runtime": str(output / "runtime"),
                      "manifestSha256": report["runtimeManifestSha256"],
                      "executableSha256": result["executable_sha256"]}))


if __name__ == "__main__":
    main()
