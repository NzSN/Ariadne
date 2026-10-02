# Minidump investigator examples

## Context and follow-up

**Status.** Practical CLI examples; scope follows the current BAP/input contracts.

**Why this document exists.** [CLI/report contract](stage-c-report-schema.md) defines entries, seeds, formats and publication behavior.

**What this document establishes.** The examples show how to select an entry and seed, invoke the CLI and read the instruction overview and graph. They make the report contract operational for investigators.

**Where to go next.**

- [Backend setup](modules/bap.md) — resolves native helper/runtime prerequisites.
- [Fault-address example](investigation-validation.md) — demonstrates the additional domain-question output and its limits.

**What remains unresolved.** Examples require matching helpers and available captured bytes. They illustrate usage rather than qualify a new dump or prove that a listed producer actually executed.

For the wider context, see the optional [documentation map](../documentation-map.md).

These commands run from the Ariadne repository root. Build the pinned LLVM MC
helper as described in the [input guide](modules/input.md#build-and-verification),
then set `ARIADNE_LLVM_MC` to its executable path. The CLI selects its Windows
or Linux decoder target from the dump, independent of the host platform.
The [Priority 3 design](priority-3-investigator-presentation-design.md) defines
the readable text overview; [JSON v1](stage-c-report-schema.md) remains the
machine contract.

```sh
export ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
mkdir -p tmp/priority3
report_root=$(mktemp -d tmp/priority3/run-XXXXXX)

cargo run --offline --locked --manifest-path Cargo.toml \
  --bin ariadne-minidump -- tests/input/fixtures/stage_b_linux.dmp \
  --decoder "$ARIADNE_LLVM_MC" --entry 0x401000 \
  --seed-exception-rip --output-dir "$report_root/linux-report"

cargo run --offline --locked --manifest-path Cargo.toml \
  --bin ariadne-minidump -- tests/input/fixtures/stage_b_windows.dmp \
  --decoder "$ARIADNE_LLVM_MC" --entry 0x7ff700001000 \
  --seed-exception-rip --output-dir "$report_root/windows-report"
```

Each destination must be new. A successful command publishes `report.txt`,
`report.dot` and `report.json` together. In both fixtures, the overview shows
an earlier captured `MOV64rr RAX,RBX`, an unrelated `MOV64rr RCX,RDX` outside
the slice, and the faulting `MOV32mi` at the exception RIP. The rule and
capture file offset appear beside each instruction. The trailing `RET64`
remains opaque. The Windows example preserves its full high virtual address.

To inspect one format on stdout, replace `--output-dir DIR` with
`--format text`, `--format dot` or `--format json`. To validate published
machine and graph formats, use:

```sh
python3 -m json.tool "$report_root/linux-report/report.json" >/dev/null
dot -Tsvg "$report_root/linux-report/report.dot" \
  -o "$report_root/linux-report/report.svg"
```

Graphviz is needed only for the SVG conversion or DOT parsing check; the CLI
itself writes DOT without launching Graphviz. The text report keeps the full
reaching-definition and gap sections after its brief overview. The overview's
input-origin counts are possible producer sites under the current graph and
effect rules, not a concrete execution path.

For a partial report with an uncaptured entry, run the Linux fixture with
`--entry 0x402000 --seed-exception-rip --format text`. It shows unknown bytes,
`not_captured`, an unvisited seed and the recovery obligation; it does not
invent an earlier instruction. Invalid arguments, missing decoder, exhausted
limits and failed output publication instead exit nonzero.

The separate [controlled Chromium real-capture case](priority-1-real-capture-validation.md)
uses an external raw dump and matching build. Its
[checker](../../tools/check_priority1_real_capture.py) verifies the entry
witness before accepting a report; the committed Stage B fixtures above
only demonstrate the supported CLI and presentation mechanics.
