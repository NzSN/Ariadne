# Stages B and C: captured predecessor slice and investigator report

Validated **2026-09-29 10:16 CST** by the source-bound
[B–F progress run](stage-b-f-validation.json). These stages implement the
[remaining plan](remaining-implementation-plan.md#b--establish-a-useful-real-dump-backward-slice)
for the current minidump-only input scope. The two historical Breakpad dumps
remain independently pinned Stage A crash-IP regressions.

## B — Independently rooted captured code

[`make_stage_b.py`](../../input/tests/fixtures/make_stage_b.py) specifies a
four-instruction source program with entry VAs chosen by the fixture author,
before writing either dump. It places the exact bytes in a minidump MemoryList
capture and sets exception RIP to the third instruction, six bytes after the
entry. The tool-produced fixture is **not** evidence of a historical crash
path; it is a reproducible captured-byte predecessor case.

| Fixture | SHA-256 | Explicit entry | Exception RIP / seed |
| --- | --- | --- | --- |
| Linux `stage_b_linux.dmp` | `7e71f4926e615789815299b98e3c3c725180ed4dce4065937fa533beb1018824` | `0x0000000000401000` | `0x0000000000401006` |
| Windows `stage_b_windows.dmp` | `f3a0407bff881356c0128e7587c03ea9f143dbd5fee59abbe8fc5edb75ad30bf` | `0x00007ff700001000` | `0x00007ff700001006` |

The captured sequence is `MOV RAX,RBX`; unrelated `MOV RCX,RDX`; faulting
`MOV dword ptr [RAX],5`; `RET`. The reader keeps distinct entry and seed sets,
proves the decoded bytes came from stream 5 with aligned file offsets, and
discovers four nodes and three local edges on both target profiles. The
backward slice is exactly **entry + seed**: the RAX definition before the store
is present, the RCX write is absent. No missing seed or recovery obligation is
reported. The trailing `RET64` still carries an **opaque-effects preparation
gap**; recovery closure does not erase that limitation. A faulting store's
possible address input is not proof that it committed.

The fixture generator's `--check` mode compares committed binary bytes with
its source. [`stage_b.rs`](../../input/tests/stage_b.rs) pins both artifact
hashes and tests exact VAs, decoded opcodes/lengths, captured byte provenance,
effect reads/writes, reaching origin and unrelated-write exclusion.

## C — One query, three report formats

The supported `ariadne-minidump` binary in `input/src/bin/` accepts an
explicit dump path, pinned decoder, one or more entry VAs, explicit seeds or
`--seed-exception-rip`, and either one stdout format or `--output-dir`.
The exception RIP never becomes an earlier entry automatically. Output-dir
publication writes text, DOT and [JSON v1](stage-c-report-schema.md) to a
temporary sibling directory and renames it only after all writes succeed.
An existing destination, invalid option, missing decoder, I/O failure or
`--max-starts` exhaustion exits nonzero without publishing a complete report.

The report preserves artifact/query/decoder/ruleset identities, captured
prefixes and file-offset contributors, normalized operand/effect evidence,
the full structural graph, possible reaching origins, slice, missing seeds,
input/preparation gaps and typed uncertainty. Semantic VAs and wide values are
hex strings in JSON; the Windows high address round-trips exactly. Text and
DOT use the same frozen result and add per-site evidence, while DOT leaves the
core graph untouched and parsed successfully with Graphviz 2.42.2. A root
outside capture yields zero decoded nodes plus typed `not_captured` and
`unvisited_reference` issues, rather than a false complete result.

Example on the pinned Windows fixture from repository root:

```sh
cargo run --offline --locked --manifest-path input/Cargo.toml \
  --bin ariadne-minidump -- input/tests/fixtures/stage_b_windows.dmp \
  --decoder target/ariadne-llvm-mc --entry 0x7ff700001000 \
  --seed-exception-rip --output-dir /tmp/ariadne-investigation
```

## Acceptance boundary

All **11 nested minidump gates** passed within the 19-gate B–F source-bound
run: prior effects/MBT regression, input tests, formatting, Clippy, native
decoder matrix, fixture regeneration check, Stage B native slice, Stage C CLI,
the two external Breakpad artifacts, formal input checks and six reader
mutations. The source snapshot stayed stable across the run. The report does
not assert an ISA instruction step, a historical faulting path, or PE/ELF
reader support. DOT comments are report evidence; JSON v1 is the structured
consumer contract.
