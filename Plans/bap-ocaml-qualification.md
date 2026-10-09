# Qualify the OCaml foundation for Stage 2

## Context and follow-up

**Status.** OQ0–OQ6 completed and checked on 2026-10-03. The isolated SDK,
bounded native state and Rust transport qualify the full A0 foundation; the [qualification guide](../docs/Ariadne/bap-ocaml-qualification.md)
and retained record report the exercised gates and final decision. This plan
closed the A0 foundation before the later [complete Stage 2 delivery](../docs/Ariadne/bap-core-qualification.md).

**Why this document exists.** The [A0 delivery](../docs/Ariadne/bap-stage2-a0-validation.md)
qualified contract admission and packaged-runtime graph facilities, but did not
build our own OCaml pass or exercise its real initialize/observe transport.

**What this document establishes.** Ordered work, concrete deliverables, failure
conditions and evidence needed to qualify an isolated OCaml/BAP SDK, a custom
helper and a bounded native state/protocol slice.

**Where to go next.**

- [Analysis-core design](../docs/Ariadne/bap-analysis-core-design.md) — supplies
  ownership, wire and formal observation contracts implemented by this plan.
- [A0 plan](bap-stage2-a0.md) — receives the foundation qualification result.
- [Stage 2 sequence](bap-integration.md#stage-2-bap-analysis-core) — continues with
  complete A1 recovery, A2 definitions/slicing and A3 stateflow.
- [Native analysis module](../native/bap-core/README.md) — current helper setup,
  completed Stage 2 and historical foundation commands.

**What remains unresolved.** This completed foundation itself does not qualify
the complete analyzer, generated helper replay, product integration or adoption.
The later [Stage 2 result](../docs/Ariadne/bap-core-qualification.md) supplies
those separate claims; the [documentation audit](../docs/Ariadne/bap-documentation-sync.md)
identifies its matching source-bound refresh. The bootstrap sequence below is
historical, not a list of missing current capabilities.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Scope and fixed decisions

Build a **standalone OCaml executable** with its own pinned BAP SDK. Keep the
existing packaged Stage 1 lifter unchanged and in its separate process. No
unverified plugin is loaded into that packaged runtime, and no existing user
opam switch is modified.

The current toolchain lock is the source-selection starting point, not a
compiler/SDK compatibility certificate: release assets say v2.5.0, the installed
CLI reports `2.5.0-alpha+baa9022`, and the library reports `2.5.0-alpha`. Resolve
the exact source identity before selecting an OCaml compiler or dependency set.
Do not assume that either installed compiler is suitable merely because it runs.

The helper must own its BAP project, instruction/TID attribution, typed edge
relation and mutable state. The Rust reference is used only by external tests.
The current TID graph collapses parallel labels; keep `(src, dst, kind)` facts
in a separate OCaml relation. Actual observations are serialized from owned
state and never copied from an expected result or a Rust execution.

Qualification uses a deliberately narrow recovery bootstrap: complete admission
of the recovery input contract, actual initialization, one real `Visit` at a
time, read-only observation, and reset/exit. This overlaps the first vertical
slice of A1 without claiming complete recovery. Advertise only implemented
capabilities. Stateflow, dataflow, slicing, phase completion and result publication
remain unavailable until their stages implement and qualify them.

## Ordered gates

| Gate | Work and deliverable | Passing condition |
| --- | --- | --- |
| OQ0 — Freeze baseline and scope | Verify the Stage 1 prerequisite and A0 records; write SDK selection and bootstrap capability decisions. | Complete relevant source/tool inventories checked; exact scope and source identity recorded; previous results preserved. |
| OQ1 — Build isolated SDK | Select a supported compiler from verified source/package constraints; pin BAP, dependencies and repository snapshots; build locally. | Custom code can compile and link using this SDK with no ambient BAP or user-switch dependency. |
| OQ2 — Build and launch helper | Implement the native executable, manifest-bound handshake, bounded framing and an empty reader-scoped project. | The executable runs through the intended launcher, reports exact identities/capabilities, and starts with no speculative instructions. |
| OQ3 — Qualify native state | Implement immutable recovery-input admission, actual Init state, restricted Visit and full observation. | Independent expected states match all nine fields before/after each supported action; state lives in the OCaml helper. |
| OQ4 — Qualify transport/lifecycle | Exercise identity, sequencing, errors, observe/reset and cleanup through the future production transport. | Invalid operations cannot silently mutate state; failed processes cannot publish results or contaminate the next session. |
| OQ5 — Rebuild and verify sensitivity | Perform a second clean helper build and targeted mutations of actual OCaml/transport code. | Rebuild uses the same locked inputs; intended behavioral assertions reject each required mutant. |
| OQ6 — Freeze evidence and decide | Run applicable regressions, verify manifests and archive logs/artifacts. | Every required OQ gate passes with stable source/tool identities; A0 foundation qualified, Stage 2 release qualification still false. |

Run OQ0 → OQ1 → OQ2 → OQ3 → OQ4 → OQ5 → OQ6. Later gates cannot turn a missing
SDK, failed build or skipped native test into a pass.

## OQ0: baseline and source selection

1. Verify the Stage 1 prerequisite's complete current source inventory and tools.
   Record its artifact hash and whether it is fresh or reused evidence.
2. Verify the A0 contract/probe record against the files relevant to this run.
   This plan adds a design link, changing a design file covered by that record;
   preserve the previous record and refresh its affected checks before claiming
   current A0 qualification. Do not rewrite old hashes to relabel a prior run.
3. Resolve the BAP source archive and full source revision associated with the
   proposed SDK. Record the relationship to the Stage 1 packaged runtime,
   including any known mismatch or unavailable build provenance.
4. Select and pin a compiler only after examining the exact BAP/package constraints.
   Record the solver inputs/output, package-source digests, native prerequisites,
   linker/compiler identities and any source patches.

Prefer an SDK built from the selected BAP source line. If it cannot be built on
the host, retain the concrete error and assess a compatible isolated build
environment. Any different BAP revision becomes an explicit design/pin change
with a new comparison scope; it cannot be called the same qualified runtime.

## OQ1: isolated SDK and repeatable build

Use workspace-local SDK, package-root and build directories. Invoke tools with
explicit paths and an explicit environment. Record every archive/repository pin;
do not rely on a floating opam repository, switch name or version string.
Acquisition may use the network; locked rebuilds must not silently resolve newer
dependencies. Record platform, libc, native-library and linker requirements.

Required development artifacts include the BAP compiled interfaces and libraries,
compiler tools and the libraries needed by the helper. Prove usability by compiling
and linking a small OCaml program that uses the selected project, term and typed
storage facilities. Record actual loaded library paths and digests where dynamic
loading is used. A file-count check alone does not qualify the SDK.

Run the built program with inherited OCaml package/load-path settings removed.
It must still use the isolated SDK artifacts and run successfully. Demonstrate
that replacing a declared library, compiler identity or lock input causes an
explicit build/admission failure. Failures must identify the unmet prerequisite.

## OQ2: helper and capability handshake

Implement the helper under `native/bap-core/` and use an isolated output directory
under `target/`. The handshake declares protocol/ABI version, compiler/BAP/helper
identities, supported family/profile/operations and resource limits. The launcher
verifies those identities before sending an input request.

Construct an empty target/project and populate it only from the admitted request.
No default image loader, whole-image scan or speculative entry discovery is
allowed. The helper receives no filesystem path from which it could fill missing
capture bytes. Production lifting continues through its already separate module.

Freeze the restricted bootstrap capability set in the design and handshake before
implementation. Initially permit recovery initialization, `Visit`, observation
and reset. Unsupported actions/families must be explicitly rejected, including
dataflow/stateflow actions and a request for a completed result. Do not implement
a placeholder `finish` that returns a synthetic result.

## OQ3: actual owned state and one-action semantics

Implement the complete **recovery** input contract, rather than merely accepting
an object-shaped payload. Validate finite domains, total instruction maps,
continuation/target cardinalities, effects (`must_defs ⊆ may_defs`), byte-source
sets and identities. Reject duplicate JSON keys, duplicate set/map rows, unknown
fields, malformed addresses and budget violations before publishing state.
Stateflow payload admission remains a separately advertised, unavailable capability.

Implement the exact nine-field Init state from `Specs/Ariadne.tla`. Then implement
the real `Visit(a)` action with the selected unsigned lowest-VA scheduling rule.
It must update owned state atomically: visited/pending, decoded/provenance,
typed edges and obligations. Reaching sets, slice and phase remain unchanged.
Do not use a test-only counter or arbitrary graph edit as evidence for Visit.

Validate the entire observation against independently specified fixture states.
Use the existing Rust analyzer externally as an additional cross-check; the
helper and observation code must not depend on it. Comparisons cover total maps,
including empty rows, rather than selected counts or a final summary.

| Required fixture/control | What it establishes |
| --- | --- |
| Ordinary captured instruction with continuation | Init and one real Visit update every required field correctly. |
| Missing bytes and decode failure | The failed start is visited, an obligation is retained, and no instruction is invented. |
| Call with continuation | Both call and summary edges survive; only the summary continuation enters local pending discovery. |
| Conditional target equal to fallthrough | Two typed edge kinds survive even though the BAP TID graph would collapse their endpoint pair. |
| Self-loop and two roots | No requeue of a visited self-loop; unsigned lowest-VA scheduling matches the reference. |
| Seed that is not a root | Initialization and Visit do not turn the slice seed into discovery work. |
| Address above `2^63-1` | Full-width unsigned identity, ordering and attribution survive the round-trip. |
| Several terms at one VA; synthetic term | Machine terms share a captured source correctly; synthetic terms have ancestry and no invented VA. |

The bootstrap does not establish recovery termination, reaching-definition fixed
points, slicing, stateflow or general BIR transformations. Those remain A1–A3.

## OQ4: production-path transport and lifecycle

Use the intended Rust transport implementation for acceptance tests. A Python
driver may help diagnosis, but its success alone cannot qualify the Rust caller.
Put Rust sources under `src/bap/` and standalone tests under `tests/bap/`; retain
the existing root Cargo package and no-default-features dependency boundary.

Required checks:

- Initialize returns real Init state; observe twice returns identical state,
  action index and generation. A successful Visit increments the action index
  exactly once; transport request sequence remains a separate counter.
- A wrong action/address/guard or premature finish is rejected without changing
  any observable state. Unknown capabilities cannot become a successful no-op.
- Wrong snapshot/query/session, duplicate/skipped/out-of-order sequences,
  malformed/oversized frames and nonfinite JSON numbers are rejected consistently.
  Fatal protocol failures poison the session and prevent publication.
- Broken pipe, partial response, unexpected EOF, native exception, timeout and
  nonzero exit are visible failures. The launcher terminates and reaps owned
  processes and bounds captured output; no stale result is returned.
- Reset acknowledges shutdown and the process exits. A fresh process with the
  same VAs but different snapshot/bytes starts with fresh state and attribution.
  Repeat initialization/action/reset cycles and check for leaked child processes.
- Input, sequence and state are not shared between concurrently independent
  sessions. An error in one session cannot alter the other's observations.

Keep operational watchdogs/resource limits even though workload latency has no
acceptance ceiling. Unlimited timing does not authorize hangs or partial responses.

## OQ5: clean rebuild and real mutation sensitivity

Build the helper a second time from the frozen inputs in a separate clean output
directory. Record source and dependency equality and both output hashes. Compare
handshakes and normalized observations on the same fixture/action corpus. If
binary hashes differ, identify and record the source of nondeterminism; do not
claim bit-for-bit reproducibility without equality.

Mutate isolated copies of actual OCaml state/serialization or Rust transport code,
keeping observers, expected fixtures and bindings unchanged. At minimum detect:

| Mutation | Required rejecting observation |
| --- | --- |
| Omit a real Visit state update | Full post-action state differs. |
| Return the previous observation | Post-action state/action index mismatch. |
| Truncate or signed-sort addresses | High-VA identity/scheduling mismatch. |
| Collapse typed parallel edges | Conditional/call edge relation mismatch. |
| Mutate state during observe | Repeated observation or index mismatch. |
| Preserve session state across reset | New-session Init or attribution mismatch. |
| Accept a stale identity/sequence | Transport negative control fails. |

A build error, missing SDK or timeout is not detection of the intended mutant.
Retain the precise assertion mismatch and source diff for every credited case.
This is bootstrap mutation sensitivity, not the later full A5 campaign.

## Proposed files and commands

These are implementation deliverables. The implementation selects `ocamlfind
ocamlopt` through `build.py`/`build.sh`, rather than Dune:

| Proposed path | Responsibility |
| --- | --- |
| `native/bap-core/sdk.lock.json` | Exact compiler, BAP, package-repository and native dependency identities. |
| `native/bap-core/setup-sdk.py` | Isolated acquisition/build and strict check-only mode. |
| `native/bap-core/recovery.ml`, `project_state.ml`, `main.ml` | Delivered bootstrap state, project attribution, admission and observation; later Stage 2 also adds `stateflow.ml` and `capture.ml`. |
| `native/bap-core/build.sh` | Locked helper build with explicit SDK/output arguments. |
| `src/bap/core_protocol.rs`, `core_session.rs` | Typed framing, identity checks and process lifecycle. |
| `tests/bap/core_bootstrap.rs` | Real native transport and independent state assertions. |
| `tools/check_bap_ocaml.py` | Ordered OQ gates and source/tool-bound evidence. |
| `tools/check_bap_ocaml_mutations.py` | Separate native/transport mutation builds and expected mismatches. |

The delivered build uses `build.py` and `ocamlfind ocamlopt`; no Dune helper
files were delivered. The selected BAP SDK retains its own pinned build system.
Keep SDK, clean rebuild, replay and mutation outputs in distinct directories
under `target/`.

Existing checks available now remain:

```sh
python3 tools/check_bap_core_a0.py
python3 -m unittest discover -s tools -p test_bap_core_contract.py
python3 tools/check_doc_links.py
```

When Rust transport is added, run the affected native test target through the
normal launcher and the applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
```

Do not assume ignored native tests ran in ordinary Cargo tests. Record their
explicit invocation and prerequisites. New Rust/test files change complete
source inventories: refresh affected Stage 1/native regressions when required,
and reuse an old record only when its entire relevant inventory and tools match.

## OQ6: final decision and handoff

Retain a new record and archive under `evidence/Ariadne/`, with a readable guide
under `docs/Ariadne/`. Preserve the previous A0 and Stage 1 records as historical
results. Required evidence includes locked inputs, build/loader provenance,
helper hashes/handshake, native request/response traces, full observations,
negative controls, mutation diffs/assertions, cleanup checks and all source/tool
hashes. Verify every archive entry after writing it.

Report separate booleans for `sdkQualified`, `helperBuildQualified`,
`nativeStateExchangeQualified`, `transportLifecycleQualified` and
`bootstrapMutationChecksPassed`. Set `a0ExitPassed=true` only when all required
gates pass with stable identities. Keep `stage2Qualified=false`; list the exact
implemented bootstrap capabilities and remaining A1–A6 clauses.

After qualification, A1 completes reader-scoped recovery on the same pinned
helper interface. A2/A3 then add their own real algorithms and full-observation
checks. Generated replay and broad mutation/product acceptance remain A4/A5;
the default production analyzer changes only after A6.
