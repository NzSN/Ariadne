#!/usr/bin/env python3
"""Seal task evidence remotely without rewriting originals or claiming success.

Run after the producers stop. The export contains every attempt under evidence/,
referenced model run directories, native checker source/log/result trees and the
current source archive. Compiled executables/objects are identified or excluded.
Large text is losslessly gzipped inside the tar, with both identities retained.
No historical 2026-10-14 evidence tree is traversed separately.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid


ROOT = Path("/home/nzsn/Repos/Ariadne-loop-aware-20261015")
TASK = Path("/loop-work")
HOST = Path("/mnt/d/ariadne-loop-aware-20261015")
OBJECT_SUFFIXES = {".o", ".obj", ".a", ".so", ".dll", ".exe", ".rlib", ".rmeta",
                   ".cmx", ".cmi", ".cmo", ".cmxa", ".cmxs", ".pyc"}
TEXT_SUFFIXES = {".json", ".jsonl", ".ndjson", ".log", ".stdout", ".stderr", ".txt"}
MODEL_PREFIXES = ("ariadne-target-resolution.", "ariadne-guarded-target-resolution.",
                  "ariadne-loop-target-closure.")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def fingerprint(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def verify_sources(manifest):
    changed = [name for name, expected in manifest["files"].items()
               if sha(ROOT / name) != expected]
    if changed:
        raise RuntimeError("current source differs from task manifest: " + ", ".join(changed))


def tool_command(command):
    selected = shutil.which(command[0])
    record = {"command": command, "available": selected is not None}
    if selected:
        path = Path(selected)
        record.update(launcher=str(path), resolved=str(path.resolve()), sha256=sha(path))
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=45)
            record.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
        except subprocess.TimeoutExpired as error:
            record.update(error="version command timed out", timeout_seconds=45,
                          stdout=str(error.stdout or ""), stderr=str(error.stderr or ""))
    return record


def identities():
    commands = {"rustc": ["rustc", "--version", "--verbose"],
                "cargo": ["cargo", "--version", "--verbose"],
                "python": [sys.executable, "--version"],
                "tlc": [os.environ.get("TLC", "tlc"), "-help"],
                "apalache": [os.environ.get("APALACHE_MC", "apalache-mc"), "version"],
                "rustc_binary": ["rustup", "which", "rustc"],
                "cargo_binary": ["rustup", "which", "cargo"]}
    result = {"commands": {name: tool_command(command) for name, command in commands.items()},
              "platform": platform.platform(), "python_version": sys.version,
              "selected_pins": {key: os.environ[key] for key in (
                  "TLC_VERSION_PIN", "APALACHE_VERSION_PIN", "TLC_JAR", "APALACHE_JAR")
                                if key in os.environ}, "files": {}}
    paths = [ROOT / name for name in (
        "target/ariadne-bap-lift", "target/ariadne-llvm-mc",
        "target/loop-aware-native/ariadne-bap-core", "target/loop-aware-native/manifest.json",
        "target/loop-aware-build/release/libariadne.rlib",
        "target/loop-aware-build/release/ariadne-minidump",
        "target/bap-core-replay/debug/ariadne-mbt",
        "target/bap-core-replay/debug/ariadne-stage-e-mbt",
        "target/bap-core-sdk/sdk-manifest.json", "target/bap-core-sdk/bin/ocamlfind",
        "target/bap-core-sdk/bin/ocamlopt", "native/bap-core/sdk.lock.json",
        "native/bap/toolchain.lock.json")]
    paths.append(TASK / "dump-probe")
    toolchain_path = Path("/home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json")
    paths.append(toolchain_path)
    if toolchain_path.is_file():
        record = json.loads(toolchain_path.read_text())
        result["mirrors_toolchain"] = record
        framework = Path(record["root"])
        paths.extend(framework / ".lake/build/bin" / name for name in record["binaries"])
    for name in ("TLC_JAR", "APALACHE_JAR"):
        if os.environ.get(name):
            paths.append(Path(os.environ[name]))
    for name in ("rustc_binary", "cargo_binary"):
        row = result["commands"][name]
        if row.get("exit_code") == 0:
            paths.append(Path(row["stdout"].strip()))
    for path in paths:
        if path.is_file():
            result["files"][str(path)] = {"resolved": str(path.resolve()),
                                         "bytes": path.stat().st_size, "sha256": sha(path)}
        else:
            result["files"][str(path)] = {"available": False}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=TASK / "exports")
    parser.add_argument("--source-archive", type=Path)
    args = parser.parse_args()
    manifest_path = TASK / "source-manifest.json"
    if not manifest_path.is_file() or not ROOT.is_dir():
        raise SystemExit("Run inside the authorized remote loop-aware task wrapper.")
    manifest = json.loads(manifest_path.read_text())
    verify_sources(manifest)
    source_archive = args.source_archive or (TASK / "inputs" /
                                           ("source-" + manifest["archive_sha256"] + ".tar.gz"))
    if sha(source_archive) != manifest["archive_sha256"]:
        raise SystemExit("source archive differs from current task manifest")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = args.output_dir / ("evidence-" + stamp + "-" + uuid.uuid4().hex[:8])
    if not output.is_relative_to(TASK):
        raise SystemExit("collector exports must stay within the task directory")
    output.mkdir(parents=True, exist_ok=False)
    archive_path = output / "evidence.tar.gz"
    print("Collecting evidence into:", output, flush=True)
    selected = {}
    excluded = []
    missing = []
    native_baselines = []

    def select(path, archive_name):
        if path.is_symlink():
            excluded.append({"path": str(path), "reason": "symlink", "target": os.readlink(path)})
            return
        if not path.is_file():
            missing.append(str(path))
            return
        if path.suffix.lower() in OBJECT_SUFFIXES:
            excluded.append({"path": str(path), "reason": "compiled-object",
                             "bytes": path.stat().st_size, "sha256": sha(path)})
            return
        with path.open("rb") as source:
            magic = source.read(4)
        if magic.startswith(b"\x7fELF") or magic[:2] == b"MZ":
            excluded.append({"path": str(path), "reason": "compiled-executable",
                             "bytes": path.stat().st_size, "sha256": sha(path)})
            return
        # Keep standalone Rust reproduction outside src/tests as plain text.
        if archive_name.endswith(".rs"):
            archive_name += ".txt"
        if archive_name in selected and selected[archive_name] != path:
            raise RuntimeError("archive path collision: " + archive_name)
        selected[archive_name] = path

    def tree(directory, prefix):
        if not directory.is_dir():
            missing.append(str(directory))
            return
        for current, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name != "__pycache__")
            for name in sorted(files):
                path = Path(current) / name
                select(path, prefix + "/" + path.relative_to(directory).as_posix())

    evidence = TASK / "evidence"
    tree(evidence, "artifacts")
    model_dirs = set()
    reference_pattern = re.compile(r"/(?:loop-work/tmp|tmp)/ariadne-[A-Za-z0-9_.-]+")
    for path in evidence.rglob("*.log"):
        for reference in reference_pattern.findall(path.read_text(errors="replace")):
            candidate = Path(reference)
            if candidate.name.startswith(MODEL_PREFIXES):
                model_dirs.add(candidate)
    for directory in (TASK / "tmp").iterdir():
        if directory.is_dir() and directory.name.startswith(MODEL_PREFIXES):
            model_dirs.add(directory)
    for directory in sorted(model_dirs):
        tree(directory, "artifacts/model-runs/" + directory.name)
    for directory in sorted((ROOT / "target").glob("loop-aware-native-controls*")):
        if directory.is_dir():
            tree(directory, "artifacts/native-checkers/" + directory.name)
            result_path = directory / "result.json"
            if result_path.is_file():
                record = json.loads(result_path.read_text())
                source = ROOT / "native/bap-core/loop_closure.ml"
                expected = record.get("source_sha256")
                matching = expected == sha(source)
                native_baselines.append({"directory": str(directory),
                                         "expected_source_sha256": expected,
                                         "current_source_matches": matching})
                # Baseline links the original module instead of copying it.
                # Attach it only when its bytes match this attempt's record.
                if matching:
                    name = "artifacts/native-checkers/" + directory.name + "/baseline/loop_closure.ml"
                    if name not in selected:
                        select(source, name)
    for directory in sorted((ROOT / "target").glob("loop-aware-*mutant*")):
        if directory.is_dir() and "build" not in directory.name:
            tree(directory, "artifacts/native-checkers/" + directory.name)
    native = ROOT / "target/loop-aware-native"
    for name in ("manifest.json", "build.log", "build_identity.ml"):
        select(native / name, "artifacts/final-native/" + name)
    for name in ("sdk-manifest.json",):
        select(ROOT / "target/bap-core-sdk" / name, "artifacts/delivery/sdk/" + name)
    select(Path("/home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json"),
           "artifacts/delivery/mirrors-toolchain.json")
    select(manifest_path, "artifacts/delivery/source-manifest.json")
    select(source_archive, "reproduce/source-current.tar.gz")
    for path in sorted(TASK.iterdir()):
        if path.suffix in {".py", ".sh", ".rs"}:
            select(path, "reproduce/orchestration/" + path.name)
    for path in sorted((TASK / "orchestration-inputs").glob("*")):
        select(path, "reproduce/orchestration/uploads/" + path.name)

    before = {name: fingerprint(path) for name, path in selected.items()}
    tool_ids = identities()
    entries = []
    compression_threshold = 2 * 1024 * 1024
    with tarfile.open(archive_path, "x:gz", compresslevel=6) as archive:
        for archive_name, path in sorted(selected.items()):
            original_hash = sha(path)
            original_size = path.stat().st_size
            stored_name = archive_name
            stored_path = path
            compression = "none"
            temporary = None
            if path.suffix in TEXT_SUFFIXES and original_size >= compression_threshold:
                temporary = tempfile.NamedTemporaryFile(prefix="loop-collect-", suffix=".gz",
                                                        dir=TASK / "tmp", delete=False)
                temporary.close()
                stored_path = Path(temporary.name)
                with path.open("rb") as source, stored_path.open("wb") as raw:
                    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0,
                                       compresslevel=6) as compressed:
                        shutil.copyfileobj(source, compressed, length=4 * 1024 * 1024)
                stored_name += ".gz"
                compression = "gzip"
            if before[archive_name] != fingerprint(path):
                raise RuntimeError("artifact changed while collecting: " + str(path))
            record = {"origin_path": str(path), "original_archive_path": archive_name,
                      "archive_path": stored_name, "original_bytes": original_size,
                      "original_sha256": original_hash, "compression": compression,
                      "stored_bytes": stored_path.stat().st_size, "stored_sha256": sha(stored_path)}
            archive.add(stored_path, arcname=stored_name, recursive=False)
            entries.append(record)
            if temporary is not None:
                stored_path.unlink()
        for name, path in selected.items():
            if before[name] != fingerprint(path):
                raise RuntimeError("artifact changed before sealing: " + str(path))
        verify_sources(manifest)
        final_native = json.loads((native / "manifest.json").read_text())
        if sha(native / "ariadne-bap-core") != final_native["helper_sha256"]:
            raise RuntimeError("final native helper differs from its manifest")
        for name, expected in final_native["handshake"]["source_hashes"].items():
            if sha(ROOT / "native/bap-core" / name) != expected:
                raise RuntimeError("final native source differs from helper manifest: " + name)
        orchestration_hashes = {row["archive_path"]: row["original_sha256"] for row in entries
                                if row["archive_path"].startswith("reproduce/orchestration/")}
        payload = {"schema": "ariadne.loop-target-closure.evidence-payload/v1",
                   "scope": "all retained task attempts; this collection makes no all-pass claim",
                   "source_files_verified": len(manifest["files"]),
                   "current_source_archive_sha256": manifest["archive_sha256"],
                   "files": entries, "excluded": excluded, "unavailable_optional_paths": missing,
                   "native_baseline_source_bindings": native_baselines,
                   "orchestration_hashes": orchestration_hashes,
                   "lossless_compression": "original bytes/hash retained; gzip members decode to exact originals",
                   "model_run_directories": [str(path) for path in sorted(model_dirs)]}
        for name, value in (("artifacts/delivery/collection.json", payload),
                            ("artifacts/delivery/tool-identities.json", tool_ids)):
            data = canonical(value)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    # The sidecar binds the finished archive. Its hash is not embedded back into
    # that archive, avoiding a self-referential evidence identity.
    receipt = {"schema": "ariadne.loop-target-closure.evidence-export/v1",
               "archive": archive_path.name, "archive_sha256": sha(archive_path),
               "archive_bytes": archive_path.stat().st_size, "files": len(entries),
               "collection_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
               "tool_identities_sha256": hashlib.sha256(canonical(tool_ids)).hexdigest(),
               "source_files_verified": len(manifest["files"]),
               "source_archive_sha256": manifest["archive_sha256"],
               "inside_output": str(output),
               "host_output": str(HOST / output.relative_to(TASK)),
               "claim_boundary": "collection completeness only; per-attempt results remain authoritative"}
    receipt_path = output / "manifest.json"
    receipt_path.write_bytes(canonical(receipt))
    (output / "SHA256SUMS").write_text(receipt["archive_sha256"] + "  evidence.tar.gz\n"
                                      + sha(receipt_path) + "  manifest.json\n")
    print(json.dumps(receipt, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
