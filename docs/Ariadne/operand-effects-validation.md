# Operand/effects delivery evidence

2026-09-26; implementation in the working tree based on `fb7f142`.
No commit or push. P0–P6 of [the plan](operand-effects-plan.md) are delivered
within the scope below. Full instruction-step acceptance is unchanged.

## Delivered behavior

`ByteSnapshot::prepare()` consumes protocol 2 and returns a validated request,
per-instruction evidence, gaps and version identities. `to_request()` preserves
protocol 1 and its previous coarse summaries. The analyzer and `Ariadne.tla`
were not changed.

The [exact rule matrix](operand-effects-rules.md) contains 137 LLVM opcode
identities with actual native observations. Form matching also checks ordered
operand shape, widths and accepted prefixes. This is not a count of verified
architectural instructions or user64 profile cases. The separate location
catalogue also has 137 entries: 128 GPR bytes, seven flags, memory and an opaque
FP/vector/opmask data/status cell. System/debug/control state is outside it.

Reviewed register effects eliminate unrelated slice producers, preserve
untouched register bytes and account for dword zero extension. Arithmetic and
branches use relevant flags. Loads/stores retain address dependencies and
conservative memory aliases. Calls remain opaque even with a direct target.
Unknown control produces evidence and a core recovery obligation, not a guessed
fallthrough. Undefined flags remain annotated may-writes without a must-kill.

## Execution evidence

All gates passed in `/tmp/ariadne-effects-acceptance-n883e7y3`.
The [retained JSON report](operand-effects-validation.json) records commands,
source SHA-256 values, durations, log locations and source-stability results.
It snapshots broader TLA+ sources conservatively; their presence in that hash
map does not imply the full AMD64 model suite was executed.

| Gate | Fresh result |
| --- | --- |
| Offline Rust tests | 24 tests and one doctest passed; native tests intentionally excluded here |
| Format and Clippy | Passed, warnings denied |
| Native interfaces | Five legacy and eleven new tests passed against a freshly built LLVM helper |
| Exact opcode coverage | Each of the 137 registry entries matched its frozen real-decoder observation and produced the expected preparation disposition |
| Effect projection | Apalache 0.61.0 typechecked both modules; TLC revision `1476e7f` passed the fixture, 3 generated / 2 distinct driver states |
| Effect negative controls | Six isolated implementation mutations rejected by the intended test assertions |
| Existing core MBT | 12 complete traces / 168 matched states; wrong digest rejected before construction; all five engine mutants rejected |
| Batch observation | 256 decoded MOV instructions, 137 locations: preparation 48.2 ms, analysis 4.88 s in a debug test build |
| Source stability | All snapshotted source hashes unchanged throughout the integrated run and rechecked before recording |

TLC evaluates finite set/projection assertions inside its small driver graph;
its two states are not a count of architectural states validated. This is a
projection contract plus implementation tests, not a universal Rust/LLVM/AMD
refinement proof. No new Lean proof or full-ISA validation is claimed.

The six effect mutations were: AL killing all RAX bytes; omitted address-register
reads; omitted ADC/SBB carry reads; a store killing all memory; opaque calls
preserving RBX; and invented unknown-instruction fallthrough. The correct
implementation passed first. Each mutation changed a temporary SUT copy and
kept the same test observer. Compilation, decoder-launch and protocol failures
did not count as successful semantic rejection.

The batch figure is one debug-build observation, not a performance guarantee.
The existing ordered-set engine dominates this fixture's runtime. No core
optimization was introduced, and no large-binary scalability claim is made.

## Reproduction and provenance

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  python3 tools/check_effects.py
```

This creates a fresh temporary evidence directory and never refreshes decoder
snapshots, rule acceptance or the MBT oracle. Prepare the documented TLA+/MBT
prerequisites first. The script completes independent gates after failures and
returns failure unless every gate passes with stable sources.

Validation used Rust 1.96.0 and LLVM 20.1.2. Ubuntu's matching `llvm-20-dev`
package was downloaded/extracted into `/tmp`, not installed system-wide; its
SHA-256 is `e4b5cbfe19826dfb35ff3c2c33d4e3a9e8327de49ad5b7b4b780abb3f6d07b74`.
The native build used matching headers and the existing `libLLVM.so.20.1`.
Pinned AMD Volumes 1–3 were downloaded and their exact hashes verified. Source
review used the Volume 3 rule-entry pages listed in the matrix and Volume 1
GPR/flag sections, extracted with pinned `pdfminer.six==20260107` in `/tmp`.

## Explicit limits

Effects describe normal long64 user-mode continuation with ordinary RAM and CET
disabled. Exception handlers, asynchronous events, concurrent interference,
precise aliases, SIMD/x87 detail, unreviewed prefixes/forms and input file readers
remain outside this delivery. Individual opcode identities still require their
reviewed operand shapes. A core closed-scope result can contain preparation
precision gaps; keep the returned evidence with the analyzer result.

The user64 profile still reports 49 paired register bodies, 0/49 accepted
register steps, 0/72 control/stack steps and 0/156 RAM steps. No acceptance
ledger was promoted by this work.
