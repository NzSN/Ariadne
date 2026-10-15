#!/usr/bin/env python3
"""Seal task evidence remotely without rewriting originals or claiming success.

Run after the producers stop. The export contains every attempt under evidence/,
referenced model run directories, native checker source/log/result trees and the
current source archive. Compiled executables/objects are identified or excluded.
Large text is losslessly gzipped inside the tar, with both identities retained.
The requested initial RED/raw-helper/failed-compile attempts are read from the
read-only loop baseline. Collection itself makes no qualification claim.
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


ROOT = Path("/home/nzsn/Repos/Ariadne-caller-coverage-20261015")
TASK = Path("/caller-work")
HOST = Path("/mnt/d/ariadne-caller-coverage-20261015")
OBJECT_SUFFIXES = {".o", ".obj", ".a", ".so", ".dll", ".exe", ".rlib", ".rmeta",
                   ".cmx", ".cmi", ".cmo", ".cmxa", ".cmxs", ".cmt", ".cmti", ".pyc",
                   ".lib", ".dylib", ".wasm", ".bc"}
TEXT_SUFFIXES = {".json", ".jsonl", ".ndjson", ".log", ".stdout", ".stderr", ".txt"}
MODEL_PREFIXES = ("ariadne-target-resolution.", "ariadne-guarded-target-resolution.",
                  "ariadne-loop-target-closure.", "ariadne-predicate-admission.",
                  "predicate-sany.", "caller-oracle.")
SOURCE_SUFFIXES = {".ml", ".rs", ".py", ".sh", ".cpp", ".tla", ".cfg"}
BASELINE = Path("/loop-baseline/evidence")
BASELINE_ATTEMPTS = ("caller-barriers-20261015T060500", "caller-barriers-20261015T060640",
                     "caller-barriers-20261015T060803", "raw-bap-20261015T061711")


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
        "target/ariadne-bap-lift", "target/caller-llvm/ariadne-llvm-mc",
        "target/caller-native/ariadne-bap-core", "target/caller-native/manifest.json",
        "target/caller-build/release/libariadne.rlib",
        "target/caller-build/release/ariadne-minidump",
        "target/caller-replay-build/debug/ariadne-mbt",
        "target/caller-replay-build/debug/ariadne-stage-e-mbt",
        "target/bap-core-sdk/sdk-manifest.json", "target/bap-core-sdk/bin/ocamlfind",
        "target/bap-core-sdk/bin/ocamlopt", "native/bap-core/sdk.lock.json",
        "native/bap/toolchain.lock.json")]
    paths.append(TASK / "dump-probe")
    for build in sorted((ROOT / "target").glob("caller-qualification-*")):
        paths.extend(build / "replay-build/debug" / name for name in
                     ("ariadne-mbt", "ariadne-stage-e-mbt"))
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
    parser.add_argument("--source-archive", type=Path, required=True,
                        help="Explicit retained capsule under /caller-work/inputs")
    args = parser.parse_args()
    manifest_path = TASK / "source-manifest.json"
    if not manifest_path.is_file() or not ROOT.is_dir():
        raise SystemExit("Run inside the authorized remote caller-coverage task wrapper.")
    manifest = json.loads(manifest_path.read_text())
    verify_sources(manifest)
    source_archive = args.source_archive
    if not source_archive.resolve().is_relative_to((TASK / "inputs").resolve()) or source_archive.is_symlink():
        raise SystemExit("select an explicit source capsule under /caller-work/inputs")
    if sha(source_archive) != manifest["archive_sha256"]:
        raise SystemExit("source archive differs from current task manifest")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = args.output_dir / ("evidence-" + stamp + "-" + uuid.uuid4().hex[:8])
    if not output.resolve().is_relative_to(TASK.resolve()):
        raise SystemExit("collector exports must stay within the task directory")
    output.mkdir(parents=True, exist_ok=False)
    archive_path = output / "evidence.tar.gz"
    print("Collecting evidence into:", output, flush=True)
    selected = {}
    excluded = []
    missing = []
    native_baselines = []
    aliases = []
    aliases_by_name = {}
    source_dedup = {}
    selected_origins = {}
    retained_run_roots = []

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
        if archive_name in selected:
            if selected[archive_name] != path and sha(selected[archive_name]) != sha(path):
                raise RuntimeError("archive path collision: " + archive_name)
            return
        if archive_name in aliases_by_name:
            if aliases_by_name[archive_name]["sha256"] != sha(path):
                raise RuntimeError("source alias path collision: " + archive_name)
            return
        resolved = str(path.resolve())
        source_key = None
        if path.suffix in SOURCE_SUFFIXES:
            source_key = (path.suffix, path.stat().st_size, sha(path))
        existing = selected_origins.get(resolved) or source_dedup.get(source_key)
        if existing:
            alias = {"origin_path": str(path), "original_archive_path": archive_name,
                     "canonical_archive_path": existing, "bytes": path.stat().st_size,
                     "sha256": sha(path)}
            aliases.append(alias)
            aliases_by_name[archive_name] = alias
            return
        selected[archive_name] = path
        selected_origins[resolved] = archive_name
        if source_key is not None:
            source_dedup[source_key] = archive_name

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
    retained_run_roots.append(str(evidence))
    for name in BASELINE_ATTEMPTS:
        directory = BASELINE / name
        tree(directory, "artifacts/baseline/" + name)
        if directory.is_dir():
            retained_run_roots.append(str(directory))
    model_dirs = set()
    model_files = set()
    reference_pattern = re.compile(r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
    for directory in (evidence, *(BASELINE / name for name in BASELINE_ATTEMPTS)):
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix not in {".log", ".stdout", ".stderr", ".json"}:
                continue
            if path.stat().st_size > 32 * 1024 * 1024:
                continue
            for reference in reference_pattern.findall(path.read_text(errors="replace")):
                path_reference = Path(reference)
                for candidate in (path_reference,*path_reference.parents):
                    if candidate.name.startswith(MODEL_PREFIXES):
                        (model_dirs if candidate.is_dir() else model_files).add(candidate)
                        break
    for temporary in (TASK / "tmp",ROOT / "tmp"):
        if temporary.is_dir():
            for directory in temporary.iterdir():
                if directory.name.startswith(MODEL_PREFIXES):
                    (model_dirs if directory.is_dir() else model_files).add(directory)
    model_dirs = {path.resolve() if path.exists() else path for path in model_dirs}
    model_files = {path.resolve() if path.exists() else path for path in model_files}
    for directory in sorted(model_dirs):
        name=directory.name+"-"+hashlib.sha256(str(directory).encode()).hexdigest()[:8]
        tree(directory, "artifacts/model-runs/" + name)
    for path in sorted(model_files):
        name=path.name+"-"+hashlib.sha256(str(path).encode()).hexdigest()[:8]
        select(path, "artifacts/model-scratch/" + name)
    checker_dirs = set()
    for pattern in ("native-controls-*", "caller-native-controls*", "caller-native-feedback*",
                    "caller-coverage-native-controls*"):
        checker_dirs.update(path for path in (ROOT / "target").glob(pattern) if path.is_dir())
    for qualification in (ROOT / "target").glob("caller-qualification-*"):
        for name in ("native-controls", "opaque-mutations"):
            directory = qualification / name
            if directory.is_dir():
                checker_dirs.add(directory)
    for directory in sorted(checker_dirs):
        prefix = "artifacts/native-checkers/" + directory.relative_to(ROOT / "target").as_posix()
        tree(directory, prefix)
        result_path = directory / "result.json"
        if result_path.is_file():
            record = json.loads(result_path.read_text())
            identities_record = record.get("source_sha256", {})
            if isinstance(identities_record, str):
                identities_record = {"capture.ml": identities_record}
            bindings = {}
            for name, expected in identities_record.items():
                source = ROOT / "native/bap-core" / name
                matching = source.is_file() and expected == sha(source)
                bindings[name] = {"expected_source_sha256": expected,
                                  "current_source_matches": matching}
                if matching:
                    select(source, prefix + "/baseline/" + name)
            native_baselines.append({"directory": str(directory), "sources": bindings})
    native = ROOT / "target/caller-native"
    for name in ("manifest.json", "build.log", "build_identity.ml"):
        select(native / name, "artifacts/final-native/" + name)
    # Retain every available source capsule and its identity; current-source is
    # an explicit argument, never inferred from an overwritten upload.
    for path in sorted((TASK / "inputs").glob("*")):
        if path.is_file():
            select(path, "reproduce/source-capsules/" + path.name)
    for name in ("sdk-manifest.json",):
        select(ROOT / "target/bap-core-sdk" / name, "artifacts/delivery/sdk/" + name)
    select(Path("/home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json"),
           "artifacts/delivery/mirrors-toolchain.json")
    select(manifest_path, "artifacts/delivery/source-manifest.json")
    select(source_archive, "reproduce/source-current.tar.gz")
    for path in sorted(TASK.iterdir()):
        if path.suffix in {".py", ".sh", ".rs", ".cpp"}:
            select(path, "reproduce/orchestration/" + path.name)
    for directory in sorted(TASK.glob("qualification*")):
        if directory.is_dir():
            tree(directory, "reproduce/orchestration/" + directory.name)
    for path in sorted((TASK / "orchestration-inputs").glob("*")):
        select(path, "reproduce/orchestration/uploads/" + path.name)

    before = {name: fingerprint(path) for name, path in selected.items()}
    alias_before = {row["origin_path"]: fingerprint(Path(row["origin_path"])) for row in aliases}
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
                temporary = tempfile.NamedTemporaryFile(prefix="caller-collect-", suffix=".gz",
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
        for row in aliases:
            path=Path(row["origin_path"])
            if fingerprint(path)!=alias_before[str(path)] or sha(path)!=row["sha256"]:
                raise RuntimeError("aliased artifact changed before sealing: "+str(path))
        verify_sources(manifest)
        final_native = json.loads((native / "manifest.json").read_text())
        if sha(native / "ariadne-bap-core") != final_native["helper_sha256"]:
            raise RuntimeError("final native helper differs from its manifest")
        for name, expected in final_native["handshake"]["source_hashes"].items():
            if sha(ROOT / "native/bap-core" / name) != expected:
                raise RuntimeError("final native source differs from helper manifest: " + name)
        def aggregate(domain, *hashes):
            return hashlib.sha256((domain + "\n" + "\n".join(hashes) + "\n").encode()).hexdigest()
        loop = aggregate("ariadne.loop-target-engine/v1", sha(ROOT / "src/bap/target_resolution.rs"),
                         sha(ROOT / "src/bap/target_resolution/loop_closure.rs"))
        guard_model = sha(ROOT / "Specs/AriadnePredicateAdmission.tla")
        guard_engine = aggregate("ariadne.guard-checker/v2", sha(ROOT / "src/bap/guard_admission.rs"),
                                 sha(ROOT / "src/bap/terminal_control.rs"))
        expected_identities = {"loop_engine_sha256": loop,
            "guard_model_sha256": guard_model, "guard_engine_sha256": guard_engine,
            "composition_model_sha256": aggregate("ariadne.guarded-target-model/v3",
                sha(ROOT / "Specs/AriadneGuardedTargetResolution.tla"),
                sha(ROOT / "Specs/AriadneLoopTargetClosure.tla"), guard_model),
            "composition_engine_sha256": aggregate("ariadne.guarded-target-checker/v3",
                sha(ROOT / "src/bap/composition.rs"), loop, guard_engine)}
        for key, expected in expected_identities.items():
            if final_native["handshake"][key] != expected:
                raise RuntimeError("final helper proof source identity differs: " + key)
        if loop != "afc1b4b991a2bdf402dc8036eb0cfba0d0232505ea5dab31a6e2e2d267a15d95":
            raise RuntimeError("the retained loop checker identity changed")
        orchestration_hashes = {row["archive_path"]: row["original_sha256"] for row in entries
                                if row["archive_path"].startswith("reproduce/orchestration/")}
        orchestration_hashes.update({row["original_archive_path"]: row["sha256"] for row in aliases
                                     if row["original_archive_path"].startswith("reproduce/orchestration/")})
        payload = {"schema": "ariadne.caller-semantic-coverage.evidence-payload/v1",
                   "scope": "all retained task attempts; this collection makes no all-pass claim",
                   "source_files_verified": len(manifest["files"]),
                   "current_source_archive_sha256": manifest["archive_sha256"],
                   "files": entries, "source_aliases": aliases, "excluded": excluded,
                   "unavailable_optional_paths": missing,
                   "retained_run_roots": retained_run_roots,
                   "native_baseline_source_bindings": native_baselines,
                   "final_proof_identities": expected_identities,
                   "orchestration_hashes": orchestration_hashes,
                   "lossless_compression": "original bytes/hash retained; gzip members decode to exact originals",
                   "model_run_directories": [str(path) for path in sorted(model_dirs)],
                   "model_scratch_files": [str(path) for path in sorted(model_files)],
                   "source_text_relocations": [{"origin_path": row["origin_path"],
                       "archive_path": row.get("original_archive_path", row.get("archive_path")),
                       "sha256": row.get("original_sha256", row.get("sha256"))}
                       for row in [*entries,*aliases] if row["origin_path"].endswith(".rs")]}
        for name, value in (("artifacts/delivery/collection.json", payload),
                            ("artifacts/delivery/tool-identities.json", tool_ids)):
            data = canonical(value)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    # The sidecar binds the finished archive. Its hash is not embedded back into
    # that archive, avoiding a self-referential evidence identity.
    receipt = {"schema": "ariadne.caller-semantic-coverage.evidence-export/v1",
               "archive": archive_path.name, "archive_sha256": sha(archive_path),
               "archive_bytes": archive_path.stat().st_size, "files": len(entries),
               "source_aliases": len(aliases),
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
