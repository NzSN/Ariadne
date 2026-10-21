# Memory provenance refinement implementation

## Context and follow-up

**Status.** M0–M4 pass the selected bounded memory-refinement profile with
[remote qualification dated 2026-10-19](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md). The complete declared Scanner
candidate-table case, independent oracles, revised component model and five
dedicated compiled mutations pass. Earlier source/local records remain historical.

**Why this document exists.** The [canonical design](../../docs/Ariadne/memory-provenance-refinement.md)
defines candidate-preserving writer assessment and scoped backward scalar facts.

**What this document establishes.** The implementation and finite acceptance
ledger for that design, including source-bound mathematical, semantic-receipt,
product and captured-Scanner evidence.

**Where to go next.** Read the canonical design, [new qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md),
[section-5 integration](frame-question-investigation.md),
[Scanner follow-up](scanner-partial-explanation.md),
[model guide](../../Specs/README.md) and [BAP trust boundary](../../docs/Ariadne/semantic-assurance.md).

**What remains unresolved.** The selected Scanner retains all 12 origins as
unresolved; qualification does not identify a historical writer. General alias
precision, joint-state/loop-instance reconstruction, root cause and universal
refinement remain outside the profile. Scanner S2–S4, caller S6, frame-path F4
and broad release acceptance remain separate.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Execution ledger

The [specification synchronization](specification-sync.md) updates M0's finite
component model for represented constrained values, expression-cap boundaries
and unavailable/candidate preservation. It preserves the original freeze and
receipts; remote qualification must bind the revised model's own hashes.

| Stage | Work | Acceptance |
| --- | --- | --- |
| M0 — independent contract | 784 range / 1,280 inverse expectations frozen; TLA+ source and remote check command specified. | Oracle and 2026-10-18 local Apalache/TLC checks pass; a sequence type annotation resolves the initial local typecheck failure. Remote component checks pass on the 2026-10-19 source/tool inventory. |
| M1 — symbolic assessment | Source implemented with full candidate coverage, bounded constant/common-base comparisons and immutable witnesses. | Finite oracle and source controls pass; broader qualification is M4. |
| M2 — transfers and backward values | Opt-in canonical BIL sidecars, receipt validation, exact/constrained/unknown scalar rules and path-scoped worklist implemented. | Source controls and captured RBX/RCX seed probe pass; no general joint-state or loop-instance inference. |
| M3 — product and reporting | Separate strict v1 codec, recomputation, JSON/text/DOT and explicit CLI mode implemented. | Finite probe preserves original JSON bytes and native/Rust assessments agree on one controlled capture. |
| M4 — qualification | Root default/core-only and all-feature Clippy checks pass in bounded local checks; accepted helper restored for finite probes. | Remote component model, five dedicated mutation cases and complete selected Scanner candidate-table clauses pass, 2026-10-19. |

## Resume commands

Use the task-owned remote workspace and read-only MirrorRust snapshot for the
heavy campaign. Transfer only the reviewed source/test/model changes; preserve
raw captures as external artifacts. Bind fresh source/tool hashes before credit.

```sh
python3 tests/investigation/fixtures/memory_refinement_oracle.py
bash Specs/check-memory-refinement.sh
python3 tools/check_memory_refinement_mutations.py --remote \
  --output-dir target/memory-refinement-mutations-current
cargo test --offline --locked --test input_bap_backend memory_provenance \
  -- --ignored --nocapture
```

The mutation runner gives each mutant its own source/build directory and credits
only compiled behavioral test rejection, preserving compilation/prerequisite
failures without turning them into detections. Use a current manifest-verified
native helper; the older cached helper lacks completion-page capabilities.

## Source ownership

- `src/bap/refinement.rs`: normalized transfer extraction and canonical sidecar.
- `src/bap/prepare.rs`, `src/input/materialize.rs`: opt-in receipt retention.
- `src/investigation/memory_refinement.rs`, `backward_values.rs`: binding,
  candidates, range witnesses and numerical worklist.
- `src/input/investigation.rs`: capture-owned binding and fault observations.
- `src/reports/memory_provenance.rs`, `src/bin/ariadne-minidump.rs`: strict report
  and explicit product invocation.
- `tests/investigation/` and `tests/reports/`: standalone regressions and oracles.

## Required validation

Run affected independent oracle and Rust suites, layout and documentation checks.
Rust behavior changes require the root format/default/core-only/Clippy checks
specified by [repository instructions](../../AGENTS.md). Follow the native and
investigation gates from the owning feature documents. Isolate mutation/replay
build outputs under separate `target/` subdirectories. Retain missing prerequisites
and failures as such; no old performance or accepted P4 receipt qualifies these
changed sources automatically.

## 2026-10-19 remote M4 completion

The [remote record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md)
retains the current component typecheck/TLC run, 784 range/1,280 inverse oracle
cases, five compiled behavioral mutations with passing original controls,
finite live probes and the complete declared Scanner case. The hardened
mutation driver records executable/log/source hashes and rejects compile or
transport failures as mutation credit; final builds live under the root target.

For capture `ed82b433…`, entry D960, fault DD6E and selected load DD6A, the new
assessment preserves the default base report byte-for-byte and matches native
and Rust results exactly. An independent comparison to the completed baseline
reaching set checks all 12 original candidate keys: entry memory, eight pushes
and three stores. All remain unresolved, with the appropriate unsupported
address/scope reasons; numerical facts are scoped, and the report is untruncated.
This closes the selected candidate-table acceptance, leaving the Scanner
control/decode and earlier-entry investigation in their owning follow-up plan.
