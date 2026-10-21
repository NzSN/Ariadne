"""Evidence primitives shared by I5c campaigns; no acceptance from exit codes alone."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from i5a_native_contract import environment, strict_json
from with_mirrorrust_snapshot import active_identity
from check_target_resolution_mutations import stop_process_group

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/input/fixtures/i5c"
LFS = b"version https://git-lfs.github.com/spec/v1\n"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    require(not raw.startswith(LFS), "unhydrated LFS evidence: " + str(path))
    return strict_json(raw.decode("utf-8"))





def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def sources():
    # Share the broad native/performance inventory; do not qualify a narrowed
    # arithmetic-only subset. Its exact retained evidence inputs also bind reuse.
    paths = set()
    for tree in ("src", "tests", "native", "Specs", "mbt", "tools"):
        paths.update(p for p in (ROOT / tree).rglob("*") if p.is_file() and p.suffix != ".md"
                     and not set(p.parts) & {"target", ".work", "__pycache__", "results", "states", "_apalache-out"})
    paths.update(ROOT / name for name in (
        "Cargo.toml", "Cargo.lock", "docs/Ariadne/bap-analysis-core-design.md",
        ".agents/plans/completed/bap-stage2-implementation.md",
        "tests/input/fixtures/workloads/investigation-windows-workload-case.json",
        "tests/input/fixtures/workloads/windows-oracle.json",
        "tests/input/fixtures/workloads/windows-inputs.tar.gz",
        "tests/input/fixtures/workloads/real-capture-workload-case.json"))
    # Missing/unhydrated manifests must still permit a preflight failure record.
    # A real campaign additionally checks exact equality with the native owner.
    try:
        import real_capture_workload
        paths.update(real_capture_workload.source_paths())
    except (OSError, ValueError, KeyError):
        pass
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def artifact(path):
    path = Path(path).resolve()
    require(path.is_file(), "missing artifact: " + str(path))
    with path.open("rb") as stream:
        require(not stream.read(len(LFS)).startswith(LFS), "unhydrated LFS artifact: " + str(path))
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def prerequisite_report():
    """Read-only preflight, retaining every missing clause instead of installing tools."""
    missing = []
    selected = {}
    paths = {
        "decoder": ROOT / "target/ariadne-llvm-mc",
        "lifter": ROOT / "target/ariadne-bap-lift",
        "native-helper": ROOT / "target/bap-core-native/ariadne-bap-core",
        "native-manifest": ROOT / "target/bap-core-native/manifest.json",
        "sdk-manifest": ROOT / "target/bap-core-sdk/sdk-manifest.json",
        "bap-runtime": ROOT / "tmp/bap-setup/stable/usr/local/lib/libbap.so.2.5.0",
        "mirrorrust": ROOT.parent / "MirrorRust/Cargo.toml",
    }
    for name, path in paths.items():
        try:
            selected[name] = artifact(path)
        except (OSError, ValueError) as error:
            missing.append(str(error))
    for name in ("cargo", "rustc", "java", "bwrap"):
        path = shutil.which(name)
        if path:
            if name in ("cargo", "rustc") and Path(path).resolve().name == "rustup":
                try:
                    path = subprocess.check_output([str(Path(path).resolve()), "which", name],
                                                   text=True, stderr=subprocess.PIPE, timeout=10).strip()
                except (OSError, subprocess.SubprocessError) as error:
                    missing.append("cannot identify selected " + name + ": " + str(error))
                    continue
            selected[name] = artifact(path)
        else:
            missing.append("missing executable: " + name)
    dependency = None
    try:
        dependency = active_identity()
        require(dependency is not None, "sealed read-only MirrorRust snapshot is not active")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        missing.append(str(error))
    for name in sources():
        path = ROOT / name
        with path.open("rb") as stream:
            if stream.read(len(LFS)).startswith(LFS):
                missing.append("unhydrated qualification input: " + name)
    try:
        from check_bap_core import sources as native_sources
        require(sources() == native_sources(), "native qualification source closure differs")
    except (OSError, ValueError, KeyError) as error:
        missing.append("native qualification source closure unavailable: " + str(error))
    return {"schema": "ariadne.i5c-prerequisites/v1", "passed": not missing,
            "recordedUtc": datetime.now(timezone.utc).isoformat(),
            "qualificationEnvironment": dependency, "tools": selected,
            "missing": missing, "nativeExecutionPerformed": False}


def command(directory, label, argv, *, cwd=ROOT, env=None, timeout=1200):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    argv = [str(value) for value in argv]
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env or environment(),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_process_group(process)
            stdout, stderr = process.communicate()
        except BaseException:
            stop_process_group(process)
            process.communicate()
            raise
        code = process.returncode
    except OSError as error:
        stdout, stderr, code, timed_out = b"", str(error).encode(), None, False
    stdout_path, stderr_path = directory / (label + ".stdout"), directory / (label + ".stderr")
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    receipt = {"command": argv, "cwd": str(cwd), "exitCode": code, "timedOut": timed_out,
               "stdout": artifact(stdout_path), "stderr": artifact(stderr_path)}
    write_json(directory / (label + ".json"), receipt)
    return receipt, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def cargo_artifact(stdout, target, *, kind, test, target_dir):
    candidates = []
    for line in stdout.splitlines():
        row = strict_json(line)
        if (row.get("reason") == "compiler-artifact" and row.get("target", {}).get("name") == target
                and kind in row["target"].get("kind", []) and row.get("profile", {}).get("test") is test
                and row.get("executable")):
            path = Path(row["executable"]).resolve()
            require(path.is_relative_to(Path(target_dir).resolve()), "Cargo executable outside isolated target")
            source = Path(row["target"]["src_path"]).resolve()
            require(source.is_relative_to(ROOT) or "sut" in source.parts, "foreign Cargo artifact source")
            candidates.append(path)
    require(len(candidates) == 1, "Cargo must select exactly one executable for " + target)
    return artifact(candidates[0])


def build_test(directory, selector, target_dir, *, root=ROOT):
    kind, name = selector
    flags = ["--lib"] if kind == "lib" else ["--" + kind, name]
    receipt, stdout, _ = command(directory, "build", [
        "cargo", "test", "--offline", "--locked", "--release", "--no-run",
        "--message-format=json", "--manifest-path", root / "Cargo.toml",
        "--target-dir", target_dir, *flags], cwd=root)
    require(receipt["exitCode"] == 0 and not receipt["timedOut"], "test compilation failed")
    return cargo_artifact(stdout, name, kind=kind, test=True, target_dir=target_dir)


def observe(directory, executable, test, *, env=None, failed=False):
    before = artifact(executable)
    receipt, stdout, stderr = command(directory, "observe", [
        executable, "--exact", test, "--include-ignored", "--show-output", "--test-threads=1"], env=env)
    status = "FAILED" if failed else "ok"
    code = 101 if failed else 0
    summary = ("test result: FAILED. 0 passed; 1 failed; 0 ignored;" if failed
               else "test result: ok. 1 passed; 0 failed; 0 ignored;")
    valid = (receipt["exitCode"] == code and not receipt["timedOut"]
             and stdout.splitlines().count("test " + test + " ... " + status) == 1
             and sum(line.startswith(summary) for line in stdout.splitlines()) == 1
             and before == artifact(executable))
    require(valid, "missing intended compiled test outcome: " + test)
    return {"executable": before, "test": test, "receipt": receipt}, stdout, stderr


def named_rows(stdout, prefix, names):
    rows = [strict_json(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
    actual = [row.get("name") for row in rows]
    require(len(actual) == len(set(actual)) and set(actual) == set(names), "missing/duplicate named case rows")
    require(all(row.get("passed") is True for row in rows), "nonpassing named case row")
    return rows


def copy_sut(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for tree in ("src", "tests", "native", "Specs", "tools", "mbt"):
        shutil.copytree(ROOT / tree, destination / tree,
                        ignore=shutil.ignore_patterns("target", ".work", "__pycache__", "results", "states", "_apalache-out"))
    for name in ("Cargo.toml", "Cargo.lock"):
        shutil.copyfile(ROOT / name, destination / name)
    manifest = destination / "Cargo.toml"
    text = manifest.read_text()
    marker = 'path = "../MirrorRust"'
    require(text.count(marker) == 1, "MirrorRust manifest seam changed")
    manifest.write_text(text.replace(marker, "path = " + json.dumps(str(ROOT.parent / "MirrorRust")), 1))
    return {str(p.relative_to(destination)): sha(p) for tree in ("tests",)
            for p in (destination / tree).rglob("*") if p.is_file()}


def unchanged_observers(sut, expected):
    actual = {str(p.relative_to(sut)): sha(p) for p in (Path(sut) / "tests").rglob("*")
              if p.is_file() and "__pycache__" not in p.parts}
    return actual == expected
