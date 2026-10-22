#!/usr/bin/env python3
"""Reproduce/check a pinned XED encoding-template inventory under ignored output.

fetch obtains exact official archives; generate verifies/extracts both archives,
runs their default just-prep and official reader, and checks the frozen record
denominator. check validates a generated inventory against that same pin.
AMD vendor-manual reconciliation and semantic coverage are separate evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

from amd64_inventory_xed import SCHEMA, canonical, digest, normalize, summarize
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tests/bap/fixtures/amd64-semantics/inventory.lock.json"
MAX_INVENTORY_BYTES = 64 * 1024 * 1024


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def hash_file(path, maximum):
    value = hashlib.sha256()
    total = 0
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            total += len(block)
            if total > maximum:
                raise ValueError("archive hash byte budget")
            value.update(block)
    return value.hexdigest()


def load_lock(path=LOCK):
    lock = strict_json(Path(path).read_bytes())
    if lock["schema"] != "ariadne.amd64-inventory-lock/v1":
        raise ValueError("inventory lock schema")
    if lock["normalizerSchema"] != SCHEMA:
        raise ValueError("inventory normalizer schema")
    return lock


def verify_archive(path, pin):
    path = Path(path)
    if path.stat().st_size != pin["bytes"] or hash_file(path, pin["bytes"]) != pin["sha256"]:
        raise ValueError("official archive differs from pin: " + pin["name"])


def extract_archive(path, pin, destination):
    verify_archive(path, pin)
    destination = Path(destination)
    destination.mkdir()
    prefix = pin["archivePrefix"]
    total = 0
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) != pin["archiveMembers"]:
            raise ValueError("source archive member count changed")
        names = set()
        for member in members:
            parts = PurePosixPath(member.name).parts
            if (not parts or parts[0] != prefix or "\\" in member.name
                    or any(part in (".", "..") for part in parts)
                    or member.name in names or not (member.isdir() or member.isfile())):
                raise ValueError("source archive path/type")
            names.add(member.name)
            total += member.size
            if total > pin["expandedBytes"]:
                raise ValueError("source archive expanded budget")
            relative = Path(*parts[1:])
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
                target.chmod(member.mode & 0o755)
        if total != pin["expandedBytes"]:
            raise ValueError("source archive expanded size changed")


def fetch(cache, lock):
    cache = run_output(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for pin in lock["sources"]:
        path = cache / pin["archive"]
        if not path.exists():
            descriptor, name = tempfile.mkstemp(prefix=pin["archive"] + ".", suffix=".download", dir=cache)
            os.close(descriptor)
            temporary = Path(name)
            try:
                with urllib.request.urlopen(pin["archiveUrl"], timeout=60) as source:
                    with temporary.open("wb") as output:
                        total = 0
                        while block := source.read(1024 * 1024):
                            total += len(block)
                            if total > pin["bytes"]:
                                raise ValueError("download exceeds pinned byte count")
                            output.write(block)
                verify_archive(temporary, pin)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        verify_archive(path, pin)
    return cache


def validate_inventory(inventory, lock):
    fields = {"schema", "scope", "selectedInputs", "preparedInputSha256", "operandWidths",
              "counts", "recordsSha256", "records"}
    if set(inventory) != fields or inventory.get("schema") != SCHEMA:
        raise ValueError("inventory schema")
    rows = inventory["records"]
    if rows != normalize([row["source"] for row in rows]):
        raise ValueError("inventory row identity, order or derived fields changed")
    if inventory["counts"] != summarize(rows):
        raise ValueError("inventory count mismatch")
    expected = lock["normalized"]
    if (digest(rows) != inventory["recordsSha256"]
            or digest(rows) != expected["recordsSha256"]
            or inventory["counts"] != expected["counts"]):
        raise ValueError("inventory differs from frozen template denominator")
    material = {key: inventory[key] for key in ("selectedInputs", "preparedInputSha256", "operandWidths", "scope")}
    if digest(material) != expected["inputsAndScopeSha256"]:
        raise ValueError("inventory grammar, source selection or scope changed")


def check(path, lock):
    path = Path(path)
    if path.stat().st_size > MAX_INVENTORY_BYTES:
        raise ValueError("inventory byte budget")
    with path.open("rb") as stream:
        data = stream.read(MAX_INVENTORY_BYTES + 1)
    if len(data) > MAX_INVENTORY_BYTES:
        raise ValueError("inventory byte budget")
    inventory = strict_json(data)
    validate_inventory(inventory, lock)
    return inventory


def generate(cache, output, lock):
    output = run_output(output)
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    for pin in lock["sources"]:
        extract_archive(Path(cache) / pin["archive"], pin, sources / pin["name"])
    environment = dict(os.environ, PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONPATH", None)
    for name, command in (
        ("prepare", [sys.executable, "mfile.py", "--build-dir=../../build", "just-prep"]),
        ("normalize", [sys.executable, str(ROOT / "tools/amd64_inventory_xed.py"),
                       "--source", str(sources / "xed"), "--mbuild", str(sources / "mbuild"),
                       "--build", str(output / "build"), "--output", str(output / "inventory.json")]),
    ):
        with (output / (name + ".log")).open("wb") as log:
            result = subprocess.run(command, cwd=sources / "xed", env=environment,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180)
        if result.returncode:
            raise ValueError(name + " failed; see " + str(output / (name + ".log")))
    inventory = check(output / "inventory.json", lock)
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("--cache", type=Path, default=ROOT / "target/amd64-inventory-sources")
    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("--cache", type=Path, default=ROOT / "target/amd64-inventory-sources")
    generate_parser.add_argument("--output", type=Path, required=True)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("inventory", type=Path)
    args = parser.parse_args(argv)
    lock = load_lock(args.lock)
    if args.command == "fetch":
        print(fetch(args.cache, lock))
        return 0
    inventory = (generate(args.cache, args.output, lock) if args.command == "generate"
                 else check(args.inventory, lock))
    print(json.dumps({"scope": "pinned-XED-symbolic-templates", "counts": inventory["counts"],
                      "recordsSha256": inventory["recordsSha256"],
                      "amdArchitectureCompleteness": "not-established"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
