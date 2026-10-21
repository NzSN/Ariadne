#!/usr/bin/env python3
"""Raw PE/minidump witness oracle for exactly eight owned I5c capture cases.

No Ariadne, BAP, LLVM, debugger, demo execution or file-backed memory fallback.
The independently supplied build digest authenticates the producer receipt;
source hashes and binary comparisons do not prove compiler correctness.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tempfile

from inspect_capture import (BinaryFile, InspectionError, Minidump,
                             PortableExecutable, STREAM_NAMES, checked_end,
                             require, unique_object, witness_address)

M = 1 << 64
CRASHPAD_REVISION = "7a884c25c84c46352fc6f16ef0a798ece2b77e84"
BINARY_NAMES = {"ariadne_crash_demo.exe", "crashpad_handler.exe",
                "crashpad_database_util.exe"}
ENVIRONMENT_KEYS = ["PATH", "SystemRoot", "TEMP", "TMP", "WINDIR"]
# Independent byte worksheet frozen by W0: recipe, RCX, signed displacement,
# exact MOV bytes, optional address index, expected question answer.
RECIPES = {
    "upper": ("address-wrap-upper", M - 8, 16, "c7411005000000", None,
              "consistent_with_evidence"),
    "none": ("address-wrap-no-wrap", 8, 0, "c70105000000", None,
             "refuted_under_premises"),
    "negative": ("address-wrap-negative", 16, -8, "c741f805000000", None,
                 "refuted_under_premises"),
    "indexed": ("address-wrap-indexed", M - 8, 16, "c744111005000000", "rdx",
                "unknown"),
}


def hx(value):
    return f"0x{value:016x}"


def json_file(raw):
    require(raw.size <= 16 * 1024 * 1024, "JSON metadata exceeds 16 MiB")
    value = json.loads(raw.read(0, raw.size, "JSON metadata"),
                       object_pairs_hook=unique_object)
    require(type(value) is dict, "JSON metadata must be an object")
    return value


def digest(value, label):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
            f"{label}: invalid SHA-256")
    return value


def typed_equal(actual, expected, label):
    require(type(actual) is type(expected) and actual == expected,
            f"{label} differs from controlled contract")


def read_witness(raw):
    require(raw.size <= 16384, "witness exceeds 16 KiB")
    witness = json_file(raw)
    require(set(witness) == {"schema_version", "process_id", "fault_function_entry",
            "expected_data_address", "expected_access", "expected_width_bytes",
            "expected_store_value", "dump_mode", "integration_profile",
            "expected_code_extent", "explicit_code_range_registered", "address_wrap"},
            "unexpected or missing witness fields")
    wrap = witness["address_wrap"]
    require(type(wrap) is dict and wrap.get("recipe") in RECIPES,
            "unsupported address-wrap recipe")
    name = wrap["recipe"]
    profile, base, displacement, encoding, _index, conclusion = RECIPES[name]
    typed_equal(wrap, {"recipe": name, "expected_rcx": hx(base), "expected_rdx": hx(0),
                      "displacement": displacement, "instruction_bytes": encoding,
                      "expected_conclusion": conclusion}, "address-wrap witness")
    require(type(wrap["displacement"]) is int, "displacement must be signed integer")
    for key, expected in {"schema_version": 1, "expected_data_address": "0x8",
                          "expected_access": "write", "expected_width_bytes": 4,
                          "expected_store_value": 5,
                          "explicit_code_range_registered": True,
                          "integration_profile": f"ariadne-crashpad-{profile}-v1"}.items():
        typed_equal(witness.get(key), expected, "witness " + key)
    require(witness.get("dump_mode") in ("partial", "full"), "unsupported dump mode")
    require(type(witness["process_id"]) is int and 0 < witness["process_id"] < 1 << 32,
            "invalid witness process ID")
    entry = witness_address(witness["fault_function_entry"], "entry")
    require(entry > 0, "zero controlled entry")
    extent = witness["expected_code_extent"]
    require(type(extent) is dict and set(extent) == {"address", "size_bytes"},
            "unexpected code extent fields")
    require(witness_address(extent["address"], "code extent") == entry,
            "code extent does not begin at entry")
    size = extent["size_bytes"]
    require(type(size) is int and len(bytes.fromhex(encoding)) + 1 <= size <= 256,
            "invalid code extent size")
    checked_end(entry, size, "code extent")
    return witness, name, entry, size


def exception(dump):
    raw = dump.raw
    stream = dump.stream(6, 168)
    thread, alignment, code, flags, chain, site, count, unused = raw.unpack(
        "<IIIIQQII", stream.offset, "exception record")
    require(thread > 0 and alignment == unused == 0 and code == 0xC0000005
            and flags in (0, 1) and chain == 0 and count == 2,
            "unsupported access-violation record")
    operation, address = raw.unpack("<QQ", stream.offset + 40, "AV parameters")
    require(operation == 1 and address == 8, "AV must report a write to byte eight")
    size, offset = dump.location(stream.offset + 160, "exception context")
    require(1232 <= size <= 65536, "unsupported exception context extent")
    flags, = raw.unpack("<I", offset + 48, "context flags")
    require(flags & 0x00FF0000 == 0x00100000 and flags & 3 == 3,
            "exception context lacks AMD64 CONTROL/INTEGER validity")
    rcx, rdx = raw.unpack("<QQ", offset + 128, "captured RCX/RDX")
    rip, = raw.unpack("<Q", offset + 248, "captured RIP")
    require(rip == site, "ExceptionAddress differs from captured RIP")
    return {"thread_id": thread, "exception_code": "0xc0000005", "operation": operation,
            "inaccessible_byte": hx(address), "rcx": hx(rcx), "rdx": hx(rdx), "rip": hx(rip),
            "context_flags": hex(flags), "exception_file_offset": stream.offset,
            "context_file_offset": offset, "context_size_bytes": size}, rcx, rdx, site


def source_path(root, relative):
    require(type(relative) is str and ":" not in relative, "invalid source inventory path")
    relative = relative.replace("\\", "/")
    name = PurePosixPath(relative)
    require(not name.is_absolute() and name.parts and ".." not in name.parts,
            "unsafe source inventory path")
    path = (root / relative).resolve(strict=True)
    require(path.is_relative_to(root.resolve(strict=True)), "source inventory escapes source tree")
    return path


def inspect(directory, build_path, expected_build_sha256):
    directory, build_path = Path(directory), Path(build_path)
    digest(expected_build_sha256, "independent expected build digest")
    with ExitStack() as stack:
        raws = {}

        def open_raw(key, path):
            raw = BinaryFile(path)
            stack.callback(raw.close)
            raws[key] = raw
            return raw

        def identify(key):
            return raws[key].identity()

        def hash_file(path):
            # Streaming, including a full-memory dump or prepared source archive.
            raw = BinaryFile(path)
            try:
                return raw.identity()
            finally:
                raw.close()

        build_raw = open_raw("build", build_path)
        build_identity = identify("build")
        require(build_identity["sha256"] == expected_build_sha256,
                "build record does not match independent expected SHA-256")
        build = json_file(build_raw)
        for key, expected in {"schema": "ariadne.crashpad-demo-windows-build/v1", "passed": True,
                              "architecture": "x64", "sourcesStable": True,
                              "stableGnRegeneration": True, "unsupportedArm64Rejected": True,
                              "crashpadRevision": CRASHPAD_REVISION}.items():
            typed_equal(build.get(key), expected, "build " + key)
        require(type(build.get("binaryHashes")) is dict and set(build["binaryHashes"]) == BINARY_NAMES,
                "build binary inventory differs")
        prepared = json_file(open_raw("build_inputs", build_path.parent / "build-inputs.json"))
        archive_identity = hash_file(build_path.parent / "source.tar.gz")
        require(identify("build_inputs")["sha256"] == build["inputs"]["inputsSha256"]
                and archive_identity["sha256"] == build["inputs"]["sourceArchiveSha256"],
                "prepared source inputs/archive differ from build receipt")
        typed_equal(prepared.get("schema"), "ariadne.crashpad-demo-build-inputs/v1", "prepared schema")
        typed_equal(prepared.get("crashpadRevision"), CRASHPAD_REVISION, "prepared revision")
        typed_equal(prepared.get("crashpadBranch"), "nzsn", "prepared branch")
        typed_equal(prepared.get("gnRevision"), "5e19d2fb166fbd4f6f32147fbb2f497091a54ad8", "prepared GN pin")
        typed_equal(prepared.get("windowsClang"), {
            "archive": "clang-llvmorg-20-init-17108-g29ed6000-2.tar.xz",
            "sha256": "1c71efd923a91480480d4f31c2fd5f1369e01e14f15776a9454abbce0bc13548"},
            "prepared Clang pin")
        require(prepared["buildOnlyAdjustments"] == build["buildOnlyAdjustments"],
                "build adjustments differ from prepared source")
        source_root = build_path.parent / "source"
        hashes = prepared["sourceHashes"]
        require(type(hashes) is dict and 0 < len(hashes) <= 100000, "invalid source inventory")
        for relative, expected in hashes.items():
            require(hash_file(source_path(source_root, relative))["sha256"] == digest(expected, relative),
                    "prepared source changed: " + relative)
        normalized_hashes = {key.replace("\\", "/"): value for key, value in hashes.items()}
        require(len(normalized_hashes) == len(hashes), "duplicate normalized source inventory path")
        demo_sources = prepared["demoSourceHashes"]
        require(set(demo_sources) == {"BUILD.gn", "crash_demo.cc", "fault.cc", "bap_workload.asm",
                                      "zero_base_offset.asm", "address_wrap.asm"},
                "prepared demo source inventory differs")
        for name, expected in demo_sources.items():
            require(normalized_hashes.get("examples/ariadne_demo/" + name) == expected
                    and hash_file(Path(__file__).with_name(name))["sha256"] == expected,
                    "inspector recipe sources differ from prepared source: " + name)
        require(hash_file(Path(__file__).with_name("build_windows.py"))["sha256"] == build["buildScriptSha256"]
                and hash_file(Path(__file__).with_name("prepare.py"))["sha256"] ==
                    prepared["buildOnlyAdjustments"]["preparationScriptSha256"],
                "preparation/build script differs from bound receipt")
        tool_paths = {"gn.exe": build_path.parent / "tools/gn.exe",
                      "ninja.exe": build_path.parent / "tools/ninja.exe"}
        for name in ("clang-cl.exe", "lld-link.exe", "llvm-ml.exe"):
            tool_paths[name] = source_root / "third_party/windows/clang/win-amd64/bin" / name
        for name, path in tool_paths.items():
            require(hash_file(path)["sha256"] == build["toolHashes"][name], "build tool changed: " + name)
        for name, expected in build["binaryHashes"].items():
            require(hash_file(Path(build["binaryDirectory"]) / name)["sha256"] == digest(expected, name),
                    "built binary changed: " + name)

        capture = json_file(open_raw("capture_record", directory / "capture.json"))
        dump_raw = open_raw("dump", directory / "capture.dmp")
        witness_raw = open_raw("witness", directory / "witness.json")
        pe_raw = open_raw("executable", directory / "ariadne_crash_demo.exe")
        witness, name, entry, extent = read_witness(witness_raw)
        profile, base, displacement, encoding, index, conclusion = RECIPES[name]
        for key, expected in {"schema": "ariadne.crashpad-demo-capture/v1", "captureCreated": True,
                              "mode": witness["dump_mode"], "profile": profile,
                              "integrationProfile": witness["integration_profile"],
                              "processId": witness["process_id"], "exitCode": "0xc0000005",
                              "uploadsEnabled": False, "crashpadRevision": CRASHPAD_REVISION,
                              "buildRecordSha256": expected_build_sha256,
                              "buildInputsSha256": identify("build_inputs")["sha256"],
                              "sourceArchiveSha256": archive_identity["sha256"],
                              "addressWrapRecipe": name,
                              "childEnvironment": {"policy": "minimal-windows/v1", "keys": ENVIRONMENT_KEYS}}.items():
            typed_equal(capture.get(key), expected, "capture " + key)
        identities = {key: identify(key) for key in ("dump", "witness", "executable")}
        require(identities["dump"]["sha256"] == capture["dump"]["sha256"]
                and identities["dump"]["size_bytes"] == capture["dump"]["bytes"]
                and identities["witness"]["sha256"] == capture["witnessSha256"]
                and identities["executable"]["sha256"] == capture["executableSha256"]
                and identities["executable"]["sha256"] == build["binaryHashes"]["ariadne_crash_demo.exe"]
                and capture["handlerSha256"] == build["binaryHashes"]["crashpad_handler.exe"],
                "capture input/binary identities differ from receipts")
        dump = Minidump(dump_raw)
        system = dump.system()
        require(dump.process_id() == witness["process_id"], "captured process differs from witness")
        observed, rcx, rdx, site = exception(dump)
        require(site == entry and rcx == base and rdx == 0, "captured entry/base/index differs from recipe")
        module = dump.module(entry, site)
        require(entry + extent <= module["base_address"] + module["size_of_image"],
                "declared code extent crosses module boundary")
        pe = PortableExecutable(pe_raw)
        require(module["timestamp"] == pe.timestamp and module["size_of_image"] == pe.image_size,
                "captured module metadata differs from PE")
        require(3 in dump.streams, "controlled capture requires ThreadList")
        dump.memory(observed["thread_id"])
        full = witness["dump_mode"] == "full"
        require(dump.header["mini_dump_with_full_memory"] == full, "full-memory flag differs")
        require((9 in dump.streams and 5 not in dump.streams) if full else
                (5 in dump.streams and 9 not in dump.streams), "memory stream/mode differs")
        code, contributors = dump.read_code(entry, extent)
        reviewed = bytes.fromhex(encoding + "c3")
        require(code[:len(reviewed)] == reviewed, "entry must be exact reviewed MOV followed by RET")
        pe_bytes, mapping = pe.code(entry - module["base_address"], len(reviewed))
        require(pe_bytes == reviewed, "captured entry MOV/RET differs from executable PE")
        wide_sum = rcx + (rdx if index else 0) + displacement
        quotient, ea = divmod(wide_sum, M)
        require(ea == 8 and wide_sum == quotient * M + ea, "independent wide arithmetic differs from AV")
        for key in raws:
            observed_identity = identify(key)
            prior_identity = {"build": build_identity, **identities}.get(key)
            if prior_identity is not None:
                require(observed_identity["sha256"] == prior_identity["sha256"], "input changed during inspection")
        local = {filename: hash_file(Path(__file__).with_name(filename))
                 for filename in ("inspect_i5c.py", "inspect_capture.py")}
        return {"schema": "ariadne.i5c-controlled-inspection/v1", "passed": True,
                "case": name + "-" + witness["dump_mode"], "recipe": name, "profile": profile,
                "expectedConclusion": conclusion, "mode": witness["dump_mode"], "system": system,
                "inputs": {**identities, "build": build_identity,
                           "build_inputs": identify("build_inputs"), "source_archive": archive_identity,
                           "capture_record": identify("capture_record")},
                "sourceBinding": {"independentExpectedBuildSha256": expected_build_sha256,
                                  "crashpadRevision": CRASHPAD_REVISION,
                                  "verifiedPreparedSourceFiles": len(hashes), "demoSourceHashes": demo_sources,
                                  "toolHashes": build["toolHashes"], "localInspectorSources": local},
                "query": {"entry": hx(entry), "site": hx(site), "memory_access": 0},
                "observed": observed, "module": module, "dumpHeader": dump.header,
                "streamInventory": [{"type": kind, "name": STREAM_NAMES.get(kind, "uninterpreted"),
                                     "file_offset": stream.offset, "size_bytes": stream.size}
                                    for kind, stream in dump.streams.items()],
                "instruction": {"bytes": encoding, "size_bytes": len(reviewed) - 1,
                                "following_ret": "c3", "form": "MOV32mi", "address_width": 64,
                                "base": "rcx", "index": index, "scale": 1,
                                "signed_displacement": displacement, "access": "write", "width_bytes": 4,
                                "immediate_payload": 5, "payload_contributes_to_address": False},
                "arithmetic": {"wide_sum_decimal": str(wide_sum), "quotient": quotient,
                               "effective_address": hx(ea), "modulus_decimal": str(M),
                               "wrap_kind": "upper" if quotient == 1 else "none",
                               "question_admitted_shape": index is None},
                "codeCapture": contributors,
                "peComparison": {"mapping": mapping, "bytes": pe_bytes.hex(), "equal": True},
                "scope": "Exact owned recipe observations and independently computed arithmetic; no Ariadne/BAP/LLVM invocation or production PE fallback.",
                "limits": ["Pinned build receipt is a trusted producer declaration, not proof of compiler correctness",
                           "Witness intent alone is not observation or execution history",
                           "Module metadata and compared MOV/RET bytes are not a whole loaded-image hash",
                           "Full-memory mode does not establish all process memory was captured",
                           "Expected conclusion is an oracle value; product assessment is a separate gate"]}


def publish_new(path, result):
    payload = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".i5c-inspection-", suffix=".tmp", dir=path.parent)
    committed = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic publication of complete bytes, with no overwrite race.
        os.link(temporary, path)
        committed = True
    finally:
        try:
            os.unlink(temporary)
        except OSError as error:
            # The hardlink is the commit point. Cleanup must neither revoke
            # committed validation nor mask the original precommit failure.
            phase = "committed" if committed else "not committed"
            try:
                print(f"I5c publication {phase}; temporary cleanup warning: {temporary}: {error}",
                      file=sys.stderr)
            except (OSError, ValueError):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--expected-build-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True, help="new JSON file")
    args = parser.parse_args()
    try:
        require(not os.path.lexists(args.output), "output already exists")
        result = inspect(args.capture, args.build, args.expected_build_sha256)
        publish_new(args.output, result)
    except (InspectionError, OSError, UnicodeError, ValueError, KeyError, TypeError, struct.error) as error:
        print("I5c inspection FAILED:", error, file=sys.stderr)
        return 1
    print("Independent I5c capture inspection PASS:", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
