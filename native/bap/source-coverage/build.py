#!/usr/bin/env python3
"""Compare original/patched BAP flag lifters and build the opt-in flag runtime.

The source comparison remains a separate finite pilot. Its checked four-flag
runtime requires an exact dependency lock and explicit production selection;
this command installs nothing and changes no SDK. Six hash-bound upstream
modules are copied only into a fresh ignored target directory.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SDK_SCRIPT = ROOT / "native/bap-core/setup-sdk.py"
MODULES = (
    "lib/x86_cpu/x86_types.ml", "lib/x86_cpu/x86_env.ml", "lib/x86_cpu/x86_cpu.ml",
    "plugins/x86/x86_utils.ml", "plugins/x86/x86_disasm.ml", "plugins/x86/x86_lifter.ml",
)
FLAGS = {"f8": ("CF", "clear"), "f9": ("CF", "set"),
         "f5": ("CF", "complement"), "fd": ("DF", "set"), "fc": ("DF", "clear")}
NEW_FLAGS = ("f8", "f9", "f5", "fd")
NEGATIVES = tuple(prefix + opcode for prefix in ("f0", "f2", "f3", "66", "48") for opcode in NEW_FLAGS)
CASES = (*FLAGS, "90", "fa", "fb", *NEGATIVES, "f890", "f5f9")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def load_sdk():
    spec = importlib.util.spec_from_file_location("source_coverage_sdk", SDK_SCRIPT)
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    return sdk


def extract_sources(archive_path, revision, output):
    prefix = "bap-" + revision + "/"
    hashes = {}
    with tarfile.open(archive_path) as archive:
        for relative in MODULES:
            member = archive.getmember(prefix + relative)
            require(member.isfile() and member.size <= 1024 * 1024,
                    "upstream source must be a bounded regular file: " + relative)
            content = archive.extractfile(member).read()
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            hashes[relative] = hashlib.sha256(content).hexdigest()
    return hashes


def flag_variable(var):
    require(var.get("name") in ("CF", "DF") and var.get("width") == 1
            and var.get("virtual") is False, "unexpected architectural variable")
    return var["name"]


def evaluate(expression, state, reads):
    kind = expression.get("kind")
    if kind == "int":
        require(expression.get("width") == 1, "flag constant width")
        number, width = expression["value"].split(":")
        require(width.rstrip("us") == "1", "flag constant serialized width")
        value = int(number, 0)
        require(value in (0, 1), "flag constant value")
        return value
    if kind == "var":
        name = flag_variable(expression["var"])
        reads.add(name)
        return state[name]
    if kind == "not":
        return evaluate(expression["arg"], state, reads) ^ 1
    raise ValueError("unexpected expression in independent flag evaluator")


def verify_flag(hex_code, row):
    destination, operation = FLAGS[hex_code]
    require(row.get("status") == "lifted" and row.get("wellTyped") is True
            and row.get("length") == 1, "flag must have a complete typed one-byte lift: " + hex_code)
    bil = row["bil"]
    require(len(bil) == 1 and bil[0].get("kind") == "move", "exactly one flag assignment required")
    require(flag_variable(bil[0]["var"]) == destination, "flag destination mismatch")
    expected_reads = {destination} if operation == "complement" else set()
    for cf in (0, 1):
        for df in (0, 1):
            old = {"CF": cf, "DF": df, "ZF": 1, "OF": 0, "AF": 1, "SF": 0, "PF": 1}
            state, reads = dict(old), set()
            state[destination] = evaluate(bil[0]["value"], state, reads)
            wanted = old[destination] ^ 1 if operation == "complement" else int(operation == "set")
            require(state[destination] == wanted, "independent flag equation differs")
            require(reads == expected_reads, "independent flag dependencies differ")
            require(all(state[name] == value for name, value in old.items() if name != destination),
                    "unrelated state changed")
    return dict(bytes=hex_code, destination=destination, operation=operation,
                uses=sorted("flag:" + name.lower() for name in expected_reads),
                mayDefs=["flag:" + destination.lower()], mustDefs=["flag:" + destination.lower()],
                inputCombinations=4, independentEquationsMatch=True)


def bind_observations(text):
    rows = [json.loads(line) for line in text.splitlines()]
    require(len(rows) == len(CASES), "omitted or duplicate source observations")
    for case, row in zip(CASES, rows):
        require(row.get("schema") == "ariadne.bap-source-flag-observation/v1"
                and row.get("bytes") == case and row.get("production") is False
                and row.get("entry") == "X86_lifter.disasm_instr"
                and row.get("bilEncoding") == "flag-bil-subset/v1", "source observation binding")
    return dict(zip(CASES, rows))


def verify_transition(baseline, patched):
    for case in NEW_FLAGS:
        require(baseline[case].get("status") == "missing-semantics"
                and baseline[case].get("bil") == [], "original source gap not reproduced: " + case)
    verify_flag("fc", baseline["fc"])
    equations = [verify_flag(case, patched[case]) for case in FLAGS]
    for case in (*NEGATIVES, "fa", "fb"):
        require(patched[case].get("status") == "missing-semantics",
                "non-admitted form gained semantics: " + case)
    for case in ("f890", "f5f9"):
        require(patched[case].get("status") == "trailing-bytes", "multiple instructions mislabeled one form")
    require(baseline["90"]["status"] == patched["90"]["status"] == "empty-bil", "NOP baseline differs")
    require(baseline["fc"] == patched["fc"], "existing CLD producer output changed")
    return equations


def command(log, args, *, cwd, env, timeout=300):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=timeout, check=False)
    log.write_text(result.stdout + result.stderr)
    require(result.returncode == 0, f"command exited {result.returncode}: see {log}")
    return result.stdout


def build_variant(folder, sdk, env):
    build = folder / "build"
    build.mkdir()
    for relative in MODULES:
        shutil.copyfile(folder / relative, build / Path(relative).name)
    shutil.copyfile(HERE / "flag_probe.ml", build / "flag_probe.ml")
    args = [sdk.PREFIX / "bin/ocamlfind", "ocamlopt", "-linkpkg", "-package",
            "bap,core_kernel,ppx_bap,yojson", "-o", "flag-probe",
            *(Path(p).name for p in MODULES), "flag_probe.ml"]
    command(folder / "build.log", args, cwd=build, env=env)
    text = command(folder / "probe.log", [build / "flag-probe", *CASES], cwd=build, env=env)
    rows = bind_observations(text)
    write_json(folder / "observations.json", rows)
    return rows


def build_runtime(folder, sdk, env, binding):
    build = folder / "build"
    build_id = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (build / "build_identity.ml").write_text("let build_id = " + json.dumps(build_id) + "\n")
    shutil.copyfile(HERE / "flag_lift.ml", build / "flag_lift.ml")
    command(folder / "runtime-build.log", [sdk.PREFIX / "bin/ocamlfind", "ocamlopt", "-linkpkg",
            "-package", "bap,core_kernel,ppx_bap,yojson", "-o", "flag-lift",
            *(Path(p).name for p in MODULES), "build_identity.ml", "flag_lift.ml"], cwd=build, env=env)
    snapshot, va = "a" * 64, "0xffff800000401000"
    for code in NEW_FLAGS:
        text = command(folder / ("runtime-" + code + ".log"),
                       [build / "flag-lift", "windows-amd64", snapshot, va, code], cwd=build, env=env)
        row = json.loads(text)
        require(set(row) == {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}
                and row["schema"] == "ariadne.bap-source-flags/v1" and row["build_id"] == build_id
                and row["target"] == "windows-amd64" and row["snapshot"] == snapshot
                and row["va"] == va and row["bytes"] == code and row["length"] == 1,
                "runtime protocol identity/extent differs")
        # Convert only wire syntax for the independent numeric evaluator.
        def expression(e):
            if e["kind"] == "int":
                return dict(e, width=int(e["value"].split(":")[1].rstrip("us")))
            if e["kind"] == "var":
                return e
            require(e["kind"] == "unop" and e["op"] == 0, "unexpected runtime operator")
            return dict(kind="not", arg=expression(e["arg"]))
        verify_flag(code, dict(status="lifted", wellTyped=True, length=1,
                              bil=[dict(s, value=expression(s["value"])) for s in row["bil"]]))
    runtime = folder.parent / "runtime"
    runtime.mkdir()
    shutil.copyfile(build / "flag-lift", runtime / "flag-lift")
    (runtime / "flag-lift").chmod(0o755)
    manifest = dict(schema="ariadne.bap-source-flags-build/v1", profile="bap-bit-provenance-v9",
                    runtime_role="explicit-opt-in-four-flag-preparation",
                    scope="Only exact unprefixed F5/F8/F9/FD after an empty pinned legacy BAP lift and independent ordinary one-byte decode; no guards, refinement or target resolution.",
                    cases=sorted(NEW_FLAGS), binding=binding, build_id=build_id,
                    executable="flag-lift", executable_sha256=sha(runtime / "flag-lift"),
                    max_response_bytes=4096)
    write_json(runtime / "manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="fresh directory below root target/")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(output != ROOT / "target" and output.is_relative_to((ROOT / "target").resolve()),
            "source pilot output must be a fresh child of root target/")
    output.mkdir(parents=True, exist_ok=False)
    sdk = load_sdk()
    env = sdk.environment()
    env["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    lock = json.loads(sdk.LOCK.read_text())
    archive = ROOT / lock["bapSourceArchive"]["path"]
    require(sha(archive) == lock["bapSourceArchive"]["sha256"], "upstream source archive hash differs")
    command(output / "sdk-before.log", [sys.executable, SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    identity_paths = [HERE / "build.py", HERE / "flag_probe.ml", HERE / "flag_lift.ml", HERE / "flags.patch",
                      sdk.LOCK, sdk.BASE / "sdk-manifest.json", sdk.PREFIX / "bin/ocamlopt.opt",
                      ROOT / "native/bap/toolchain.lock.json"]
    identities = {str(path.relative_to(ROOT)): sha(path) for path in identity_paths}
    baseline_dir, patched_dir = output / "baseline", output / "patched"
    baseline_dir.mkdir()
    patched_dir.mkdir()
    upstream = extract_sources(archive, lock["bapSourceRevision"], baseline_dir)
    require(extract_sources(archive, lock["bapSourceRevision"], patched_dir) == upstream,
            "upstream extraction differs")
    # Execute original source before applying the extension.
    baseline = build_variant(baseline_dir, sdk, env)
    for case in NEW_FLAGS:
        require(baseline[case]["status"] == "missing-semantics", "baseline already supplies new semantics")
    command(output / "patch.log", ["patch", "--batch", "--fuzz=0", "-p1", "-i", HERE / "flags.patch"],
            cwd=patched_dir, env=env)
    patched = build_variant(patched_dir, sdk, env)
    equations = verify_transition(baseline, patched)
    runtime_manifest = build_runtime(patched_dir, sdk, env, dict(
        base_revision=lock["bapSourceRevision"], source_archive_sha256=sha(archive),
        upstream_modules=upstream, patched_modules={p: sha(patched_dir / p) for p in MODULES},
        sources={name: sha(HERE / name) for name in ("build.py", "flag_lift.ml", "flag_probe.ml", "flags.patch")},
        sdk_lock_sha256=sha(sdk.LOCK), sdk_manifest_sha256=sha(sdk.BASE / "sdk-manifest.json"),
        compiler_sha256=sha(sdk.PREFIX / "bin/ocamlopt.opt")))
    command(output / "sdk-after.log", [sys.executable, SDK_SCRIPT, "--check"], cwd=ROOT, env=env)
    require(all(sha(ROOT / path) == digest for path, digest in identities.items()),
            "pilot source or SDK identity changed during run")
    report = dict(schema="ariadne.bap-source-flag-pilot/v1", production=False,
                  scope="Four exact unprefixed AMD64 flag forms in patched upstream BAP source; CLD baseline, 20 excluded prefix forms, CLI/STI and trailing-byte controls. No production transport, default selection, instruction execution or full-ISA claim.",
                  passed=True, fullAmd64Support=False, baseRevision=lock["bapSourceRevision"],
                  sourceArchiveSha256=sha(archive), identities=identities, upstreamModules=upstream,
                  patchedModules={p: sha(patched_dir / p) for p in MODULES},
                  binaries={name: sha(output / name / "build/flag-probe") for name in ("baseline", "patched")},
                  originalGapReproduced=list(NEW_FLAGS), independentEquations=equations,
                  observationCountPerVariant=len(CASES), sdkUnchanged=True,
                  runtimeManifestSha256=sha(output / "runtime/manifest.json"),
                  runtimeExecutableSha256=runtime_manifest["executable_sha256"],
                  next="The generated runtime is admitted only through its exact dependency lock and explicit source-extension selection. Guard, target-resolution and refinement modes remain excluded; default packaged behavior is unchanged.")
    write_json(output / "report.json", report)
    print(json.dumps(dict(passed=True, production=False, newFlagForms=4, inputCombinations=20,
                          observationsPerVariant=len(CASES), report=str(output / "report.json"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
