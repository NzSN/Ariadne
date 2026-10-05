#!/usr/bin/env python3
"""Run qualification with a hash-pinned, read-only MirrorRust dependency view."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT.parent / "MirrorRust"
SCHEMA = "ariadne.mirrorrust-qualification-snapshot/v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root, selected=None):
    root = Path(root)
    result = {}
    if selected is None:
        paths = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            if Path(directory) == root:
                dirs[:] = [name for name in dirs if name not in {".git", "target"}]
            paths.extend(Path(directory) / name for name in dirs + files
                         if name not in {".git", ".projectile-cache.eld"})
    else:
        paths = [root / name for name in selected]
    for item in paths:
        if item.is_symlink() or any(parent.is_symlink() for parent in item.parents if parent != root):
            raise ValueError("dependency snapshot cannot contain symlinks: " + str(item))
        if item.is_file():
            result[str(item.relative_to(root))] = sha(item)
    if "Cargo.toml" not in result or "src/lib.rs" not in result:
        raise ValueError("incomplete MirrorRust source tree")
    return dict(sorted(result.items()))


def source_inventory(root):
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root).decode().split("\0")
    return inventory(root, sorted({name for name in names if name and name != ".projectile-cache.eld"}))


def revision(root):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def validate_snapshot(directory, digest):
    directory = Path(directory).resolve()
    manifest = directory / "manifest.json"
    if manifest.is_symlink() or sha(manifest) != digest:
        raise ValueError("dependency snapshot manifest digest mismatch")
    record = json.loads(manifest.read_text())
    client = directory / "MirrorRust"
    if (record.get("schema") != SCHEMA or client.is_symlink()
            or inventory(client) != record.get("files")
            or revision(client) != record.get("originRevision")):
        raise ValueError("dependency snapshot source or revision mismatch")
    if set(record.get("contentsBase64", {})) != set(record["files"]):
        raise ValueError("dependency snapshot content inventory mismatch")
    for name, expected in record["files"].items():
        raw = base64.b64decode(record["contentsBase64"][name], validate=True)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("dependency snapshot retained bytes mismatch: " + name)
    if set(record.get("inputContentsBase64", {})) != set(record.get("inputFiles", {})):
        raise ValueError("dependency snapshot original content inventory mismatch")
    for name, expected in record["inputFiles"].items():
        raw = base64.b64decode(record["inputContentsBase64"][name], validate=True)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("dependency snapshot original bytes mismatch: " + name)
    return record


def active_identity():
    directory = os.environ.get("ARIADNE_MIRRORRUST_SNAPSHOT")
    digest = os.environ.get("ARIADNE_MIRRORRUST_SNAPSHOT_SHA256")
    if directory is None and digest is None:
        return None
    if not directory or not digest:
        raise ValueError("incomplete dependency snapshot selection")
    record = validate_snapshot(directory, digest)
    if (not os.statvfs(CLIENT).f_flag & os.ST_RDONLY
            or not os.path.samefile(CLIENT, Path(directory) / "MirrorRust")
            or inventory(CLIENT) != record["files"]):
        raise ValueError("selected dependency snapshot is not the active read-only view")
    return {"schema": SCHEMA, "manifestPath": str(Path(directory).resolve() / "manifest.json"),
            "manifestSha256": digest, "originRevision": record["originRevision"],
            "readOnly": True, "wrapperSha256": sha(__file__)}


def create_snapshot(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("choose a new snapshot directory outside the source checkout")
    before, original_revision = source_inventory(source), revision(source)
    output.mkdir(parents=True)
    client = output / "MirrorRust"
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
                    str(source), str(client)], check=True)
    for name in before:
        destination = client / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, destination)
    if inventory(client) != before or source_inventory(source) != before or revision(source) != original_revision:
        raise ValueError("source changed while copying; discard this incomplete snapshot and retry")
    original_contents = {name: base64.b64encode((client / name).read_bytes()).decode("ascii")
                         for name in before}
    subprocess.run(["cargo", "fmt", "--manifest-path", str(client / "Cargo.toml"), "--all"], check=True)
    subprocess.run(["cargo", "fmt", "--manifest-path", str(client / "Cargo.toml"),
                    "--all", "--", "--check"], check=True)
    after = inventory(client)
    record = {"schema": SCHEMA, "origin": str(source), "originRevision": original_revision,
              "inputFiles": before, "files": after, "formattedSnapshotOnly": True,
              "inputContentsBase64": original_contents,
              "contentsBase64": {name: base64.b64encode((client / name).read_bytes()).decode("ascii")
                                 for name in after}}
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    digest = sha(manifest)
    validate_snapshot(output, digest)
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("create")
    create.add_argument("--source", type=Path, default=CLIENT)
    create.add_argument("--output", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--snapshot", type=Path, required=True)
    execute.add_argument("--sha256", required=True)
    execute.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == "create":
        digest = create_snapshot(args.source, args.output)
        print("Snapshot:", args.output.resolve())
        print("Manifest SHA-256:", digest)
        return
    validate_snapshot(args.snapshot, args.sha256)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("run requires a command after --")
    bubblewrap = shutil.which("bwrap")
    if bubblewrap is None:
        parser.error("Linux bubblewrap is required for the read-only dependency view")
    snapshot = args.snapshot.resolve()
    os.environ["ARIADNE_MIRRORRUST_SNAPSHOT"] = str(snapshot)
    os.environ["ARIADNE_MIRRORRUST_SNAPSHOT_SHA256"] = args.sha256
    os.execv(bubblewrap, [bubblewrap, "--die-with-parent", "--bind", "/", "/",
                         "--dev-bind", "/dev", "/dev", "--proc", "/proc",
                         "--ro-bind", str(snapshot), str(snapshot),
                         "--ro-bind", str(snapshot / "MirrorRust"), str(CLIENT), "--", *command])


if __name__ == "__main__":
    main()
