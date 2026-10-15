#!/usr/bin/env python3
"""Encode a captured Windows frame with aligned MOVAPS then XORPS xmm0,xmm0."""
import hashlib
import json
from pathlib import Path
import struct
import sys

from make_guard_frame import payload as guard_payload


HERE = Path(__file__).resolve().parent
BASE = 0x400000


def payload():
    base = guard_payload()
    data = bytearray(base)
    count, directory = struct.unpack_from("<II", data, 8)
    streams = {}
    for index in range(count):
        kind, size, offset = struct.unpack_from("<III", data, directory + 12 * index)
        streams[kind] = (offset, size)
    memory, _ = streams[5]
    image = struct.unpack_from("<I", data, memory + 16)[0]
    # SUB RSP,8 ; MOVAPS [RSP+240h],XMM6 ; XORPS XMM0,XMM0 ; RET.
    code = bytes.fromhex("4883ec080f29b424400200000f57c0c3")
    assert len(code) == 0x10
    data[image + 0x200:image + 0x210] = code
    # The captured runtime function ends exactly after the RET. The unwind
    # recipe remains the same ALLOC_SMALL 8-byte prologue as the guard fixture.
    struct.pack_into("<I", data, image + 0x804, 0x210)
    thread, _ = streams[3]
    context = struct.unpack_from("<I", data, thread + 48)[0]
    struct.pack_into("<Q", data, context + 248, BASE + 0x20c)
    exception, _ = streams[6]
    struct.pack_into("<Q", data, exception + 24, BASE + 0x20c)
    return bytes(data), hashlib.sha256(base).hexdigest()


def write_or_check(regenerate=False):
    data, base_sha = payload()
    target = HERE / "shift-frame.dmp"
    manifest = HERE / "shift-frame.json"
    expected = {
        "scope": "independent captured Windows frame with aligned MOVAPS and XORPS",
        "base_guard_fixture_sha256": base_sha,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "thread_id": 17,
        "entry": "0x0000000000400200",
        "guard": "0x0000000000400204",
        "shift": "0x000000000040020c",
        "ret": "0x000000000040020f",
        "function_end": "0x0000000000400210",
        "premise": "windows-amd64-normal-call-entry/v1",
        "entry_rsp_residue": 8,
    }
    encoded = json.dumps(expected, indent=2) + "\n"
    if not regenerate and target.exists():
        if target.read_bytes() != data or manifest.read_text() != encoded:
            raise SystemExit("shift frame fixture differs from generator")
    else:
        target.write_bytes(data)
        manifest.write_text(encoded)
    print("Shift frame fixture PASS:", expected["sha256"])


if __name__ == "__main__":
    write_or_check("--regenerate" in sys.argv)
