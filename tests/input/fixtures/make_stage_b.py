#!/usr/bin/env python3
"""Produce the two pinned Stage B minidumps from independently listed code.

The instruction start is the source program's entry, not a backward guess from
the exception RIP. The MemoryList stream captures these exact instruction bytes.
This deliberately small fixture is tool-produced, not a historical crash.
"""

import argparse
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
CODE = bytes.fromhex(
    "48 89 d8"           # mov rax, rbx: fault-address producer
    "48 89 d1"           # mov rcx, rdx: unrelated write
    "c7 00 05 00 00 00"  # mov dword ptr [rax], 5: exception RIP
    "c3"                 # ret: normal-continuation fixture only
)
PROGRAMS = (
    ("stage_b_linux.dmp", 0x8201, 0x0000000000401000),
    ("stage_b_windows.dmp", 2, 0x00007FF700001000),
)


def build(platform: int, entry: int) -> bytes:
    data = bytearray(32)
    streams = []

    def append(payload: bytes) -> int:
        offset = len(data)
        data.extend(payload)
        return offset

    def stream(kind: int, payload: bytes) -> None:
        offset = append(payload)
        streams.append((kind, len(payload), offset))

    system = bytearray(56)
    system[0] = 9  # PROCESSOR_ARCHITECTURE_AMD64
    system[6] = 1  # one CPU
    struct.pack_into("<I", system, 20, platform)
    stream(7, system)

    code_offset = append(CODE)
    memory = struct.pack("<IQII", 1, entry, len(CODE), code_offset)
    stream(5, memory)

    crash_rip = entry + 6
    context = bytearray(1232)
    struct.pack_into("<I", context, 48, 0x100001)  # AMD64 | CONTROL
    struct.pack_into("<Q", context, 248, crash_rip)
    context_offset = append(context)
    exception = bytearray(168)
    struct.pack_into("<I", exception, 0, 17)  # thread ID
    struct.pack_into("<I", exception, 8, 0xC0000005)
    struct.pack_into("<Q", exception, 24, 0)  # reported fault address
    struct.pack_into("<II", exception, 160, len(context), context_offset)
    stream(6, exception)

    directory_offset = len(data)
    struct.pack_into("<4sIII", data, 0, b"MDMP", 0xA793, len(streams), directory_offset)
    for record in streams:
        data.extend(struct.pack("<III", *record))
    return bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare with committed bytes")
    args = parser.parse_args()
    for name, platform, entry in PROGRAMS:
        output = HERE / name
        generated = build(platform, entry)
        if args.check:
            if output.read_bytes() != generated:
                raise SystemExit(f"fixture differs from source: {output}")
        else:
            output.write_bytes(generated)
        print(f"{name}: {len(generated)} bytes, entry=0x{entry:016x}, seed=0x{entry+6:016x}")


if __name__ == "__main__":
    main()
