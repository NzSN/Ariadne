# Stage E completion: replay and investigator reports

The [completion implementation plan](../../Plans/stage-e-completion.md) closes
Stage E's validators, generated replay, mutation sensitivity, handoffs and
independent report/CLI delivery. The
[source-bound completion record](stage-e-completion-validation.json) is the
acceptance authority; the earlier two-fixture integration remains historical.

The campaign contains 16 machine-state and 16 IR inputs, replayed twice per
engine: 64 complete traces and 326 matched observations. All mutable fields
and public derived views are compared through generated MirrorRust ports.
All 15 real-engine mutants produce genuine model mismatches. The high-address
case preserves exact u64 values using Apalache because TLC has bounded integers;
its safety evidence is bounded, with a complete four-transition witness.

## Minidump stateflow

```sh
cargo build --offline --locked --manifest-path Cargo.toml
target/debug/ariadne-minidump DUMP --decoder target/ariadne-llvm-mc \
  --entry 0x0000000000401000 --seed-exception-rip \
  --stateflow-input semantics.json --output-dir NEW_DIR
```

`semantics.json` uses the strict
[`ariadne.machine-state-semantics/v1` contract](modules/reports.md).
It supplies a finite state catalogue, entry facts, transitions and explicit
completeness assertions bound to the dump's snapshot ID. Recovery supplies the
frozen graph/effects; call-only edges remain in the context, not stateflow.
Wrong snapshot identities or invalid contracts fail before publication.

Output-directory mode emits the original `report.txt/.dot/.json` and additional
`machine-state.txt/.dot/.json`. With `--format`, stateflow mode emits the selected
machine-state envelope, which retains the independently versioned minidump
input/preparation evidence. Unknown control/effects, missing seeds, byte
provenance and incomplete semantics remain visible. No entry facts are inferred
from captured crash-time registers; feasibility is model-relative.

## Direct verified IR

```sh
cargo build --offline --locked --manifest-path Cargo.toml
target/debug/ariadne-ir tests/ir/fixtures/diamond.ll \
  --helper target/ariadne-llvm-ir --function diamond --seed i11 \
  --output-dir NEW_DIR
```

The helper parses and verifies owned `.ll`/`.bc` bytes with LLVM 20.1.2 before
analysis. The CLI binds the helper hash and exact artifact/function identity,
then emits text, DOT and JSON from one owned result. Verifier failures,
malformed protocols, wrong seeds/options and output reuse fail before
publishing a complete report. SSA/phi and conservative memory dependencies,
call obligations and block/instruction identities remain explicit.

The full gate parses both CLIs' DOT output with Graphviz, checks JSON identity
and uncertainty, exercises native text/bitcode and frozen recovery, and reruns
the minidump regression/mutation gates. This completes finite Stage E
conformance/report acceptance. Stage D's 0/49 instruction-step gate and Stage F's
universal Rust refinement remain open; no historical execution or machine/IR
correspondence is claimed.
