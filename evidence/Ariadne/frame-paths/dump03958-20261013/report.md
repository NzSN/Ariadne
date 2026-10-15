# Frame-to-frame application: dump03958, 2026-10-13

## Context and follow-up

**Status.** Executed the production CLI and a separate public-API probe against
the original full-memory dump. Both returned `coverage: unavailable`, zero
paths, and no search states. This attempt does not satisfy F4 full-dump
qualification.

**Why this document exists.** The user requested application of the
[bounded frame-path contract](../../../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing)
to [dump_03958DA4FCA844A786262A1053](https://192.168.150.219:4080/dumps/dump_03958DA4FCA844A786262A1053),
using the DumpLedger CDB symbols skill.

**What this document establishes.** Exact captured frame/call facts, matched
symbol identity, declared limits, executed results and their admission blockers.
[summary.json](summary.json) indexes the results; [artifact-manifest.json](artifact-manifest.json)
binds retained bytes and [remote-artifact-manifest.json](remote-artifact-manifest.json)
preserves original remote artifact, source and executable identities.

**Where to go next.** The [canonical investigation design](../../../../docs/Ariadne/investigation-design.md#full-dump-application-attempt-2026-10-13)
records this application boundary. The [F0–F4 plan](../../../../Plans/frame-path-enumeration.md#implementation-checkpoint)
retains the pending qualification gates. Consult the
[BAP trust boundary](../../../../docs/Ariadne/semantic-assurance.md) before
changing semantic admission.

**What remains unresolved.** No possible path was certified. This is not evidence
that no path exists. Older-frame unwinding, vector projection and production
budget configuration need separate follow-up; no implementation changes were
made. Full-memory capture does not establish an executed path, corruption
writer or root cause.

## Input and symbol provenance

- Original dump: 962,600,678 bytes; SHA-256
  `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`.
- Remote original:
  `D:/Services/dump-ledger-runtime/data/vault/dump_03958DA4FCA844A786262A1053/original.dmp`.
- Electron base `0x00007ff76fbc0000`, image size `0x0d708000`, timestamp
  `0x6a87c949`. Dump CodeView and PDB MSF Info Stream 1 independently match GUID
  `A7877FFB-94F2-DB3E-4C4C-44205044422E`, age 1.
- Existing identity-keyed cache:
  `D:\symcache-dump03958-20261009\electron.exe.pdb\A7877FFB94F2DB3E4C4C44205044422E1\electron.exe.pdb`.
  PDB size 3,762,233,344 bytes; SHA-256
  `eab012ef555c641b2e10d314e58f02d01baa277b28f9ad5442e31c918c920ed9`.

Fresh CDB load reported `private symbols & lines` and successful symbol-server
loading from the cache. The exact HTTPS PDB route returned HTTP 200 with the
matching content length; this was not an uncached PDB download. The configured
endpoint was `https://192.168.150.219:4080/symbols`, with a Windows-style cache
and the HTTP store last. Existing certificate trust was inspected without
modification: account `win10`, CurrentUser Trusted Root present, LocalMachine
Root absent, certificate SHA-256 fingerprint
`4f4490e5d47d2cdf316cc02306c5d8895108b0aab3e67dd77be2054c3f6766ff`.

Raw records: [symbol identity](symbol-identity.json), [certificate trust](certificate-trust.json),
[HTTPS probe](https-symbol-probe.log), [CDB frames](cdb-frames.log) and
[CDB call/unwind](cdb-call-unwind.log). CDB's checksum warnings do not override
the directly matched PDB identity; the loaded image was captured memory. No
whole-EXE validation or automatic image-byte fallback is claimed. Symbols were
used for independent inspection, not supplied as Ariadne instruction/unwind bytes.

## Selected physical frame pair

Exception thread 23668 (`0x5c74`, CDB index `048`); physical frames 1→0;
`NP = 10`, allowing at most nine retained paths. CDB's inline annotations between
`Scanner::Next` and its physical caller were not counted as stack activations.
CDB numbered frame 6 corresponds to Ariadne physical frame 1.

| Physical frame | Function | Captured/saved PC | Bound function entry | SP |
| --- | --- | --- | --- | --- |
| 0 | `Scanner::Next` | `0x00007ff77443dd6e` | `0x00007ff77443d960` | `0x000000bea89fa890` |
| 1 | `ParserBase<PreParser>::ParsePrimaryExpression` | `0x00007ff77440410d` | `0x00007ff7744033a0` | `0x000000bea89fa930` |

Captured slot `0x000000bea89fa928` contains return PC `0x00007ff77440410d`.
Independent CDB disassembly identifies the preceding active direct call:

```text
0x00007ff774404108  e853980300  call 0x00007ff77443d960
0x00007ff77440410d              continuation
```

An earlier call to the same callee at `0x00007ff774403407` is not selected by
this return slot. The frame-path start would be the verified active call site,
not the saved continuation. Frame 0's fault PC is captured `cmp byte ptr
[rax+0x38],0x76` (bytes `80783876`); RAX `0x0000001100000020` gives effective
address `0x0000001100000058`. These observations do not establish earlier
branch outcomes.

## Executed attempts

Execution used windows-dev WSL and the existing isolated pinned-native setup.
CLI/helper artifacts were compiled from `b5d56b7`. All 104 source files in the
remote `src/` and `native/bap-core/` manifest match current checkout
`da7308aecda19b45c9257a5414b7d405fcd8a7dd`; this task changes documentation and
evidence only. Executable hashes are retained in the remote manifest. No new
release qualification is inferred from reuse of these binaries.

The CLI command, with only artifact admission enlarged for this dump:

```sh
target/retry-build/release/ariadne-minidump original.dmp \
  --max-artifact-bytes 2147483648 \
  --decoder-reference target/ariadne-llvm-mc \
  --bap-core-response-timeout-ms 30000 \
  --list-frame-paths 1:0 --path-count-bound 10 \
  --output-dir cli-default
```

| Attempt | Result | Truncated | Stop/gap | Paths/search states |
| --- | --- | --- | --- | --- |
| CLI, default frame-recovery limits | unavailable | true | `requested-frame-not-recovered`; `runtime-table-budget` | 0 / 0 |
| Explicit larger-budget public API | unavailable | false | `missing-or-ambiguous-active-call-anchor` | 0 / 0 |

Both processes exited 0, reporting the explicit unavailable result. CLI elapsed
2.38 s including input/preparation; API probe elapsed 6,716 ms. Enumeration's
own elapsed counter was 0 and `enumeration_exhausted` was false in both reports.

The CLI admits 4,096 runtime entries and 1 MiB aggregate unwind-read evidence;
the reader's one-read default is 65,536 bytes. Electron's captured complete
runtime table has 440,520 entries / 5,286,240 bytes. Recovery stops at its entry
budget with only the unresolved innermost frame, before CFG preparation.

The API probe separately raises the reader's one-read cap to 16 MiB, runtime
entries to 440,520, aggregate unwind-read evidence to 6,334,816 bytes, recovery
frames to six and enumeration output to 32 MiB. Other search limits are the
defaults. It uses the explicit Rust reference analysis core with pinned BAP
preparation and LLVM MC reference decode; captured bytes retain precedence.
The probe changes no production defaults and adds no call-site discovery root
or slice seed. Driver: [frame_probe.rs.txt](frame_probe.rs.txt).

Raw results: [CLI JSON](cli-default/frame-paths.json), [CLI text](cli-default/frame-paths.txt),
[API text](api-probe/frame-paths.txt), [API JSON, gzip](api-probe/frame-paths.json.gz),
[expanded frame chain, gzip](api-probe/frames-expanded-budget.json.gz),
[API run summary](api-probe/probe-summary.json) and [run log](api-probe.log).
Gzip artifacts retain the complete reports; decompress to inspect captured
read evidence. The retrieval archive's SHA-256 was verified before extraction,
and every remote-manifest artifact hash was checked locally. Original dump,
PDB and executables remain external, with their identities recorded.

## Why the larger-budget probe still cannot enumerate

The API recovers the two named physical frames. Frame 0's unwind recipe is
within the finite supported profile. Frame 1's recipe includes opcode 8,
`UWOP_SAVE_XMM128`, saving XMM6 at offset `0x240`. Recovery of the next older
frame stops with `unsupported-unwind-operation`; this is a separate broader
chain limit, rather than the direct reason pair 1→0 lacks an anchor.

The bound caller graph has nine decoded nodes, ending with the stack allocation
at `0x00007ff7744033ac`. The next instruction is captured and valid:

```text
0x00007ff7744033b3  0f29b42440020000  movaps [rsp+0x240],xmm6
```

The [isolated instruction diagnostic](blocker-instruction.json) shows LLVM MC
decodes `MOVAPSmr`, eight bytes, ordinary control. BAP projection rejects
`unmodeled architectural namespace/type: YMM6`, yielding opaque unsupported
semantics, normalized stop control and no fallback. The core's `decode_failed`
obligation here is an admission stop, not proof of an invalid CPU encoding.
Its diagnostic root is a separate query, never a root added to the frame listing.

Frame 0's graph contains 768 decoded nodes including the fault instruction.
Frame 1's graph cannot reach/admit the active call at `0x00007ff774404108`.
The contract requires that witness from the independently bound caller root;
the CDB-observed call alone cannot substitute for it. Binding therefore reports
`missing-or-ambiguous-active-call-anchor` before path search.

The next technical boundaries are runtime/read budget configuration, BAP
architectural namespace/projection support for vector instructions, and captured
XMM unwind support. Until those are qualified, zero returned paths remains an
unavailable answer and cannot exclude a memory writer or establish a root cause.
