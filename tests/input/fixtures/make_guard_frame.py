#!/usr/bin/env python3
"""Encode one synthetic captured frame with a conditional MOVAPS alignment proof."""
import hashlib
import json
from pathlib import Path
import struct

from make_frame_paths import build


def payload():
    data = bytearray(build("diamond"))
    count, directory = struct.unpack_from("<II", data, 8)
    streams = {}
    for index in range(count):
        kind, size, offset = struct.unpack_from("<III", data, directory + 12 * index)
        streams[kind] = (offset, size)
    memory, _ = streams[5]
    image = struct.unpack_from("<I", data, memory + 16)[0]
    stack = struct.unpack_from("<I", data, memory + 32)[0]
    # A conforming normal call enters with residue 8. This exact SUB makes 0;
    # the captured late RSP is not used as an entry observation.
    code = bytes.fromhex("4883ec080f29b42440020000c3")
    data[image + 0x200:image + 0x200 + len(code)] = code
    data[image + 0x905] = 0x02  # UWOP_ALLOC_SMALL, 8 bytes, prologue length 4.
    data[stack:stack + 256] = bytes(256)
    for offset, address in [(0x08, 0x400315), (0x30, 0x400415), (0x58, 0)]:
        struct.pack_into("<Q", data, stack + offset, address)
    thread, _ = streams[3]
    context = struct.unpack_from("<I", data, thread + 48)[0]
    struct.pack_into("<Q", data, context + 248, 0x400204)
    exception, _ = streams[6]
    struct.pack_into("<Q", data, exception + 24, 0x400204)
    return bytes(data)


if __name__ == "__main__":
    data = payload()
    target = Path(__file__).resolve().parent / "guard-frame.dmp"
    target.write_bytes(data)
    target.with_suffix(".json").write_text(json.dumps({
        "scope": "independent synthetic captured PE/unwind/stack fixture",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data), "thread_id": 17, "entry": "0x0000000000400200",
        "guard": "0x0000000000400204",
        "premise": "windows-amd64-normal-call-entry/v1",
        "entry_rsp_residue": 8,
    }, indent=2) + "\n")
