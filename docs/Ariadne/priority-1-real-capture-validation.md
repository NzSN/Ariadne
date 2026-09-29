# Priority 1: controlled Chromium real-capture investigation

Validated **2026-09-29 17:27 CST** against the
[Priority 1 design](priority-1-real-capture-design.md) and
[implementation plan](priority-1-real-capture-plan.md). The
[case manifest](priority-1-real-capture-case.json) pins the dump, matching
binary, selected VAs and bytes. The [source-bound gate record](priority-1-validation.json)
contains the focused acceptance result, all 11 existing minidump gates, source
and tool hashes, report hashes and negative controls.

## Artifact and independent entry witness

A fresh headless Chromium profile navigated explicitly to
`chrome://crash/renderer/member-dereference-after-free`. Crashpad recorded an
actual Linux AMD64 renderer SIGSEGV at a non-canonical memory read. The raw
237,600-byte dump has SHA-256
`31481f3f080b0b165cc0d0c70f555f127f882556b34129055e80b082225a45c9`.
It remains in the ignored local path
`tmp/priority1/chromium-member-uaf.dmp`; it is **not** part of the tracked
repository because a raw process dump may contain unrelated process memory.

The dump's `chrome` module has base `0x566807306000` and an ELF CodeView
build ID of `97676574663086478a8fe1b40f3a541a444bc634`. This equals the
`NT_GNU_BUILD_ID` of the local Chromium binary at
`/home/nzsn/Repos/chromium/src/out/Default/chrome`, whose SHA-256 is
`d665de26a68430eccf3ae2621d76738bb044619cf75d556cf6126268bbb0776a`.
The check requires the exact little-endian Crashpad `LEpB` CodeView signature,
not a filename match.

The matched ELF symbol
`base::debug::AsanHeapMemberDereferenceAfterFree()` begins at module-relative
`0x1061cda0` (187 bytes long). Its runtime start `0x566817922da0` lies 34
bytes before the captured code range `0x566817922dc2..0x566817922fc2`.
Forward disassembly **from that symbol**, independent of crash RIP, selects
`0x566817922dc5` as the first complete instruction boundary inside capture.
The checker compares 30 forward-decoded companion instructions from this
boundary through the seed with the exact captured bytes. The companion
supplies the boundary witness; Ariadne reads code bytes only from the dump.
The capture is MemoryList stream 5, entry 15, beginning at dump file offset
`0x39620`.

## Analyzer result

The explicit entry is `0x566817922dc5`; the exception-RIP seed is
`0x566817922e42`. The seed decodes from captured bytes `8b03` as reviewed
`MOV32rm EAX,[RBX]`. The earlier reviewed `MOV64rm RBX,[RBX]` at
`0x566817922de6` remains a possible origin for all eight RBX byte cells
before the seed; `MOV64rr RBX,RAX` at `0x566817922dcf` is an upstream slice
node. The local graph reaches the seed from the selected entry.

| Observation | Result |
| --- | --- |
| Captured decoded starts | 34 |
| Local graph edges | 36 |
| Backward data-slice nodes | 28, including the RBX load and faulting read |
| Missing slice seeds | 0 |
| Recovery scope | Open: one later unsupported `INT3` at `0x566817922e5b` |
| Effect uncertainty | Opaque call summaries and undefined AF results remain visible |

The locally retained reports in `tmp/priority1/accepted-report/` have
matching JSON/text decoded and slice sets; DOT edges agree with JSON and
Graphviz parsed the DOT. Every selected instruction is linked to captured
file offsets, including entry `0x39623`, producer `0x39644` and seed
`0x396a0`. A seed-only run yields exactly `{0x566817922e42}` as its slice,
so the earlier producer is not manufactured by using RIP as an entry. Altered
dump bytes and a wrong build ID were both rejected before report publication.

The 11-gate `tools/check_minidump.py` run passed effects/MBT regression,
input tests, format/Clippy, native decoding, Stage B/C fixtures and CLI,
the two previously pinned Breakpad dumps, formal input checks and reader
mutations. Its 57 source hashes stayed stable. The focused case checker
also retained 28 stable source hashes and the exact CLI, decoder and Graphviz
binary identities. Graphviz was extracted under `/tmp` for this run; no system
package was installed.

## Reproduction and limits

With the exact external dump and companion available, build the minidump CLI
and pinned LLVM MC helper, then run:

```sh
python3 tools/check_priority1_real_capture.py \
  --dump tmp/priority1/chromium-member-uaf.dmp \
  --companion /home/nzsn/Repos/chromium/src/out/Default/chrome \
  --decoder target/ariadne-llvm-mc \
  --cli input/target/debug/ariadne-minidump \
  --dot /path/to/dot \
  --report-dir tmp/priority1/recheck-report \
  --validation-json tmp/priority1/recheck-validation.json
```

The report directory and validation path must be new. A different Chromium
build or newly generated dump needs a new hash-pinned case manifest; this
one must not inherit its acceptance. Without the external artifacts the
real-capture gate is unavailable, not passed. This is one controlled Chromium
crash and a **possible** local predecessor slice. Opaque calls prevent a
unique historical value origin. It does not qualify larger-workload
performance, infer an actual path or fault commit, add PE/ELF readers, or
promote any formal AMD64 case; `register-core` remains **0/49**.
