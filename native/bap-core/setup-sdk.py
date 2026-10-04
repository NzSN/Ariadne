#!/usr/bin/env python3
"""Build/check the workspace-local OCaml SDK from pinned repository/source inputs."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "target/bap-core-sdk"
SWITCH = BASE / "prefix"
PREFIX = SWITCH / "_opam"
LOCK = Path(__file__).with_name("sdk.lock.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment():
    env = dict(os.environ)
    for name in ("OPAMROOT", "OPAMSWITCH", "OPAM_SWITCH_PREFIX", "OCAMLPATH", "OCAMLLIB",
                 "CAML_LD_LIBRARY_PATH", "OCAML_TOPLEVEL_PATH", "OCAMLTOP_INCLUDE_PATH",
                 "LD_LIBRARY_PATH"):
        env.pop(name, None)
    for name in list(env):
        if name.startswith("OCAMLFIND_") or name == "LD_PRELOAD":
            env.pop(name)
    env.update(OPAMROOT=str(BASE / "opam-root"), OPAMYES="1", OPAMJOBS="4",
               OPAMNOENVNOTICE="1")
    env["PATH"] = str(PREFIX / "bin") + os.pathsep + env["PATH"]
    return env


def run(name, args, timeout=7200):
    logs = BASE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    print(name, flush=True)
    with (logs / (name + ".log")).open("w") as output:
        result = subprocess.run([str(x) for x in args], cwd=ROOT, env=environment(),
                                stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise SystemExit(f"{name} failed ({result.returncode}); see {logs / (name + '.log')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    BASE.mkdir(parents=True, exist_ok=True)
    for key in ("bapSourceArchive", "repositorySnapshot", "resolvedPackages"):
        if sha(ROOT / lock[key]["path"]) != lock[key]["sha256"]:
            raise SystemExit(f"{key} hash mismatch")
    if args.check:
        manifest = json.loads((BASE / "sdk-manifest.json").read_text())
        if manifest["lockSha256"] != sha(LOCK):
            raise SystemExit("SDK lock mismatch")
        for relative, digest in manifest["files"].items():
            if sha(PREFIX / relative) != digest:
                raise SystemExit("SDK file mismatch: " + relative)
        if sha(BASE / "installed.export") != manifest["installedExportSha256"]:
            raise SystemExit("SDK package export mismatch")
        for path, digest in manifest.get("nativeTools", {}).items():
            if sha(path) != digest:
                raise SystemExit("SDK native tool mismatch: " + path)
        print("SDK inventory verified")
        return
    repository = BASE / "repository"
    stamp = BASE / "repository-source.json"
    identity = {key: lock[key]["sha256"] for key in ("bapSourceArchive", "repositorySnapshot")}
    if stamp.exists():
        if json.loads(stamp.read_text()) != identity:
            raise SystemExit("SDK repository belongs to different inputs")
    else:
        if repository.exists():
            raise SystemExit("Unstamped SDK repository exists")
        with tarfile.open(ROOT / lock["repositorySnapshot"]["path"]) as archive:
            archive.extractall(BASE, filter="data")
        changed = []
        for path in repository.glob("packages/*/*.2.5.0/opam"):
            text = path.read_text()
            if "https://github.com/BinaryAnalysisPlatform/bap/archive/v2.5.0.tar.gz" not in text:
                continue
            replacement = 'url {\n  src: "' + lock["bapSourceArchive"]["url"] + '"\n  checksum: "sha256=' + lock["bapSourceArchive"]["sha256"] + '"\n}'
            text, count = re.subn(r"url\s*\{[^}]*\}", replacement, text, flags=re.S)
            if count != 1:
                raise SystemExit("Unexpected BAP package URL shape: " + str(path))
            path.write_text(text)
            changed.append(str(path.relative_to(repository)))
        if not changed:
            raise SystemExit("No pinned BAP SDK packages found")
        (BASE / "repository-overrides.json").write_text(json.dumps(changed, indent=2) + "\n")
        stamp.write_text(json.dumps(identity, indent=2) + "\n")
    opam = shutil.which("opam")
    if not opam:
        raise SystemExit("Missing prerequisite: opam")
    native_tools = {}
    for name in ("opam", "gcc", "ld", "as", "make", "pkg-config"):
        path = shutil.which(name)
        if not path:
            raise SystemExit("Missing prerequisite: " + name)
        native_tools[str(Path(path).resolve())] = sha(path)
    if not (BASE / "opam-root/config").exists():
        run("opam-init", [opam, "init", "--bare", "--no-setup", "--disable-sandboxing",
                          "--kind=local", "frozen", repository, "-y"])
    digest = lock["bapSourceArchive"]["sha256"]
    cache = BASE / "opam-root/download-cache/sha256" / digest[:2] / digest
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        shutil.copyfile(ROOT / lock["bapSourceArchive"]["path"], cache)
    prefix = PREFIX
    if not (prefix / ".opam-switch/switch-state").exists():
        run("compiler", [opam, "switch", "create", SWITCH, lock["compiler"], "-y"])
    run("compiler-install", [opam, "install", "--switch", SWITCH, lock["compiler"], "-y", "--no-depexts"])
    run("sdk-plan", [opam, "install", "--switch", SWITCH, *lock["roots"], "--show-actions", "--no-depexts"])
    run("sdk-install", [opam, "switch", "import", "--switch", SWITCH,
                         ROOT / lock["resolvedPackages"]["path"], "-y", "--no-depexts"])
    run("sdk-export", [opam, "switch", "export", "--switch", SWITCH, BASE / "installed.export", "--freeze"])
    run("sdk-list", [opam, "list", "--switch", SWITCH, "--installed", "--columns=name,version", "--short"])
    files = {str(path.relative_to(prefix)): sha(path)
             for tree in ("bin", "lib") for path in sorted((prefix / tree).rglob("*")) if path.is_file()}
    manifest = {"schema": "ariadne.bap-core-sdk-inventory/v1", "lockSha256": sha(LOCK),
                "files": files, "installedExportSha256": sha(BASE / "installed.export"),
                "nativeTools": native_tools, "platform": platform.platform(),
                "libc": platform.libc_ver(),
                "scope": "SDK build inventory; native smoke and qualification remain separate."}
    (BASE / "sdk-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("SDK built:", prefix, flush=True)


if __name__ == "__main__":
    main()
