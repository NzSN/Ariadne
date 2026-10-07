#!/usr/bin/env python3
"""Prepare an isolated, pinned Crashpad source tree for the Windows demo."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request


CRASHPAD_REVISION = "7a884c25c84c46352fc6f16ef0a798ece2b77e84"
DEPENDENCIES = {
    "mini_chromium": (
        "https://chromium.googlesource.com/chromium/mini_chromium",
        "e5169551c51f3a52eee36b3b03f219cefe380237",
        "third_party/mini_chromium/mini_chromium",
    ),
    "googletest": (
        "https://chromium.googlesource.com/external/github.com/google/googletest",
        "3983f67e32fb3e9294487b9d4f9586efa6e5d088",
        "third_party/googletest/googletest",
    ),
    "lss": (
        "https://chromium.googlesource.com/linux-syscall-support.git",
        "9719c1e1e676814c456b55f5f070eabad6709d31",
        "third_party/lss/lss",
    ),
    "zlib": (
        "https://chromium.googlesource.com/chromium/src/third_party/zlib",
        "fef58692c1d7bec94c4ed3d030a45a1832a9615d",
        "third_party/zlib/zlib",
    ),
}
GN_REVISION = "5e19d2fb166fbd4f6f32147fbb2f497091a54ad8"
CLANG_ARCHIVE = "clang-llvmorg-20-init-17108-g29ed6000-2.tar.xz"
CLANG_SHA256 = "1c71efd923a91480480d4f31c2fd5f1369e01e14f15776a9454abbce0bc13548"
DEMO_FILES = ("BUILD.gn", "crash_demo.cc", "fault.cc", "bap_workload.asm", "zero_base_offset.asm")


def output(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd).decode().strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_revision(repository, revision, destination):
    data = subprocess.check_output(["git", "archive", revision], cwd=repository)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination, filter="data")


def limit_windows_toolchains(source):
    """Record a build-only delta; never invent an ARM64 compiler environment."""
    base = "third_party/mini_chromium/mini_chromium/build/"
    patches = {
        base + "win_helper.py": (
            "efab24ae793a93d65bafb0709d6524420281f01acbdce96c9bff156dd6528bc1",
            [
                ("archs = ('x86', 'amd64', 'arm64')", "archs = ('x86', 'amd64')"),
                ("        if arch == 'arm64':\n            script_arch_name = 'x86_arm64'\n", ""),
                ("x86_file, x64_file, arm64_file = _GenerateEnvironmentFiles(",
                 "x86_file, x64_file = _GenerateEnvironmentFiles("),
                ('x64_environment_file = "%s"\narm64_environment_file = "%s"',
                 'x64_environment_file = "%s"'),
                ("(install_dir, x86_file, x64_file, arm64_file)",
                 "(install_dir, x86_file, x64_file)"),
            ],
        ),
        base + "config/BUILD.gn": (
            "c5df57bd9f3677db903de978bd5747348a823fe998fc18b4ca6f0b1a94085da5",
            [
                ('if (mini_chromium_is_win) {\n  helper_path =',
                 'if (mini_chromium_is_win) {\n'
                 '  assert(target_cpu == "x64" || target_cpu == "x86",\n'
                 '         "This staged demo supports only installed x86/x64 Windows toolchains")\n'
                 '  helper_path ='),
                ('  msvc_toolchain("arm64") {\n'
                 '    environment_file = toolchain_data.arm64_environment_file\n'
                 '    current_cpu = "arm64"\n  }\n', ""),
            ],
        ),
    }
    records = []
    for name, (expected, replacements) in patches.items():
        path = source / name
        if sha(path) != expected:
            raise RuntimeError(f"unexpected upstream build helper: {name}")
        content = path.read_text()
        for old, new in replacements:
            if content.count(old) != 1:
                raise RuntimeError(f"ambiguous build adjustment in {name}: {old}")
            content = content.replace(old, new)
        path.write_text(content)
        records.append({"path": name, "upstreamSha256": expected,
                        "preparedSha256": sha(path)})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crashpad", type=Path,
                        default=Path.home() / "Repos/crashpad-nzsn")
    parser.add_argument("--output", type=Path, required=True,
                        help="new directory; existing output is never overwritten")
    parser.add_argument("--cache", type=Path, required=True,
                        help="Git cache used only for the four public pinned dependencies")
    args = parser.parse_args()
    checkout = args.crashpad.resolve()
    revision = output(["git", "rev-parse", "HEAD"], checkout)
    branch = output(["git", "branch", "--show-current"], checkout)
    if revision != CRASHPAD_REVISION or branch != "nzsn":
        parser.error(f"expected nzsn at {CRASHPAD_REVISION}; got {branch} at {revision}")
    if output(["git", "status", "--porcelain"], checkout):
        parser.error("Crashpad checkout has changes; this recipe requires its exact clean revision")
    deps_text = (checkout / "DEPS").read_text()
    for _, revision, _ in DEPENDENCIES.values():
        if revision not in deps_text:
            parser.error(f"dependency pin is absent from the fork's DEPS: {revision}")
    if GN_REVISION not in deps_text:
        parser.error("GN pin is absent from the fork's DEPS")
    if CLANG_ARCHIVE not in deps_text or CLANG_SHA256 not in deps_text:
        parser.error("Windows Clang pin is absent from the fork's DEPS")

    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / "source"
    extract_revision(checkout, CRASHPAD_REVISION, source)
    args.cache.mkdir(parents=True, exist_ok=True)
    for name, (url, revision, relative) in DEPENDENCIES.items():
        repository = args.cache.resolve() / name
        if not repository.exists():
            subprocess.run(["git", "init", "--bare", str(repository)], check=True,
                           stdout=subprocess.DEVNULL)
        present = subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                                 cwd=repository, capture_output=True).returncode == 0
        if not present:
            subprocess.run(["git", "fetch", "--depth=1", url, revision],
                           cwd=repository, check=True)
        actual = output(["git", "rev-parse", f"{revision}^{{commit}}"], repository)
        if actual != revision:
            raise RuntimeError(f"dependency identity mismatch: {name}")
        extract_revision(repository, revision, source / relative)
        print(f"Prepared {name} at {revision}", flush=True)

    build_adjustments = limit_windows_toolchains(source)
    clang_archive = args.cache.resolve() / CLANG_ARCHIVE
    if not clang_archive.exists():
        url = "https://storage.googleapis.com/chromium-browser-clang/Win/" + CLANG_ARCHIVE
        print(f"Downloading pinned Windows Clang: {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            clang_archive.write_bytes(response.read())
    if clang_archive.stat().st_size != 46357580 or sha(clang_archive) != CLANG_SHA256:
        raise RuntimeError("Windows Clang archive differs from the fork's DEPS pin")
    clang_directory = source / "third_party/windows/clang/win-amd64"
    clang_directory.mkdir(parents=True)
    with tarfile.open(clang_archive) as archive:
        archive.extractall(clang_directory, filter="data")
    demo_source = Path(__file__).resolve().parent
    integrated = source / "examples/ariadne_demo"
    integrated.mkdir(parents=True)
    for name in DEMO_FILES:
        shutil.copyfile(demo_source / name, integrated / name)
    compatibility_headers = {}
    for local_name, installed_name in [
        ("standalone_logging_settings.h", "base/logging/logging_settings.h"),
        ("standalone_rand_util.h", "base/rand_util.h"),
        ("standalone_ostream_operators.h", "base/numerics/ostream_operators.h"),
    ]:
        destination_header = source / installed_name
        destination_header.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(demo_source / local_name, destination_header)
        compatibility_headers[installed_name] = sha(destination_header)
    (destination / "tools.ensure").write_text(
        f"gn/gn/windows-amd64 git_revision:{GN_REVISION}\n"
        "infra/3pp/tools/ninja/windows-amd64 version:2@1.8.2.chromium.3\n"
    )
    manifest = {
        "schema": "ariadne.crashpad-demo-build-inputs/v1",
        "crashpadCheckout": str(checkout),
        "crashpadBranch": branch,
        "crashpadRevision": CRASHPAD_REVISION,
        "depsSha256": sha(checkout / "DEPS"),
        "dependencies": {name: {"url": url, "revision": revision}
                         for name, (url, revision, _) in DEPENDENCIES.items()},
        "demoSourceHashes": {name: sha(demo_source / name) for name in DEMO_FILES},
        "sourceHashes": {str(path.relative_to(source)): sha(path)
                         for path in sorted(source.rglob("*")) if path.is_file()},
        "gnRevision": GN_REVISION,
        "windowsClang": {"archive": CLANG_ARCHIVE, "sha256": CLANG_SHA256},
        "standaloneCompatibilityHeaders": compatibility_headers,
        "buildOnlyAdjustments": {
            "reason": "Pinned helper probes ARM64 even for x64; this demo exposes only installed x86/x64 toolchains and rejects other Windows targets.",
            "files": build_adjustments,
            "preparationScriptSha256": sha(Path(__file__).resolve()),
        },
        "scope": "Exact source preparation only; no build or capture claim.",
    }
    (destination / "build-inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tarfile.open(destination / "source.tar.gz", "w:gz") as archive:
        archive.add(source, arcname="source")
    print(f"Prepared source archive: {destination / 'source.tar.gz'}", flush=True)


if __name__ == "__main__":
    main()
