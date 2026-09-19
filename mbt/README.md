# Model-based tests for Ariadne

This integration uses the compiler-generated `mirrorrust-v1` binding described
in the [Rust target contract](../../Mirrors/Docs/model-interface-compiler/rust-target.md).
The evaluator requires an exact interface digest match before constructing the
application adapter. The adapter implements the generated `AriadneReplayPort`,
resets the actual Rust `Analyzer` for each trace, advances it through its
public `step()` method, and observes all nine fields of `AnalysisState`, plus the
public fixture identifier used to initialize it. That identifier is the only
input projected from the initial model state; the adapter never reads other
expected-state fields or previous reports.

The [replay model](model/AriadneReplay.tla) instantiates the original
`Specs/Ariadne.tla` and its six
fixtures. Its only behavioral restriction chooses the lowest eligible address,
matching the deterministic implementation's schedule. Model expected states
come from TLC, independently of the Rust implementation. Apalache supplies type
evidence; Mirrors resolves the reviewed interface, preflights the corpus, and
compares actual observations during negotiated replay. The core crate remains
dependency-free; this separate Cargo package depends on the sibling MirrorRust
client and has its own dependency lockfile.

| Owner | Files and responsibility |
| --- | --- |
| Mirrors compiler | `generated/AriadneReplayMirror.generated.rs`: native types, input decoding, observation codecs, dispatch, lifecycle checks, and the binding |
| Application | `src/adapter.rs`: typed port methods and observations of the real analyzer |
| Evaluator | `src/main.rs`: deferred factory, required negotiation, coverage, and outcome reporting |

`generated::model_interface()` supplies selection metadata, and
`generated::bind_ariadne_replay(...).into_local_binding()` creates the replay
binding inside the post-match factory. The application adapter contains no raw
`State`/`Value` encoding or wire-action dispatch. Generated source is owned by
the compiler and excluded from rustfmt; only its unused support helpers are
allowed at the module's lint boundary.

## Prepare and run

The sibling checkouts default to `/home/nzsn/Repos/{Mirrors,MirrorRust,MirrorGate}`
in this workspace. The Cargo manifest explicitly references `../../MirrorRust`.
Prepare Rust/Cargo, Java, TLC, Apalache, and the built Mirrors executables before
running the gate. Tested here: Rust 1.96.0, Apalache 0.61.0, and TLC revision
`1476e7f`; exact framework revisions and binary identities are in the evidence.

```sh
# Prepare the optional MBT client's dependencies once.
cargo fetch --locked --manifest-path mbt/Cargo.toml

# Required for the supplied Mirrors revision; see the compatibility note below.
python3 mbt/prepare_mirrors.py

# Generate/check the Rust binding from the existing reviewed interface lock.
python3 mbt/generate_binding.py

# Normal test gate: freshness, preflight, real replay, and negative controls.
python3 mbt/run.py
```

`prepare_mirrors.py` copies the prepared Mirrors checkout, including build
artifacts, into ignored test storage; it never patches the sibling checkout.
It builds the checker/compiler and runs the focused elaboration regression,
requires `mirrorrust-v1` support, rejects copies from an older source revision,
and records tool identities under `mbt/.work/toolchain.json`. Replay refuses
changed prepared binaries. `MIRRORS_ROOT` explicitly selects another compatible
prepared checkout instead of that local tool selection.

Fresh model-witness generation is separate from normal replay:

```sh
python3 mbt/test_projection.py
python3 mbt/generate.py
python3 mbt/generate_binding.py
```

`APALACHE_MC` and `TLC` may select prepared executables. Generation first obtains
an Apalache type witness, checks safety and fair termination for all six TLC
instances, and then intentionally violates `TraceComplete` at completion to
obtain each trace. Exit 12 counts as a witness only when the named completion
invariant failed; other model failures are rejected. Neither generation nor
projection imports or executes the Rust SUT.

Generation publishes a checked corpus only after Mirrors resolves the interface
and preflights all traces. `corpus/manifest.json` pins every oracle source,
converter, trace, type-evidence file, projection receipt, and lock. Normal replay
verifies these hashes and calls `model_interface_gen check` for both the
interface lock and the exact generated Rust files before replay preflight. It
never silently regenerates a stale corpus or binding. Binding-only generation
leaves the oracle and corpus unchanged. A standalone read-only check is:

```sh
python3 mbt/generate_binding.py --check
```

## Protocol representation and compatibility

The Rust-capable Mirrors revision `eb5cd001b990e6ac5e9b1e9b1c5a17ffb85e25fc`
still has two relevant integration boundaries:

- Its standard declaration catalogue omits `FiniteSets.IsFiniteSet`, which the
  existing Ariadne model uses. [The recorded patch](mirrors-isfinite.patch) adds
  that unary constant-level fact and gives the isolated build the distinct
  profile `mirrors-tla-frontend-profile-4-ariadne-isfinite-v1`. The original
  model already passes TLC and Apalache. The isolated elaboration regression
  passed its 34 accepted fixtures and the seven rejected fixtures owned by that
  test slice. This is a local compatibility build, not a released frontend
  profile or an upstream change.
- The replay codec accepts string-keyed maps. Ariadne's `provenance` and
  `reaching` maps use integer VAs, including sparse VAs 4096 and 4100. The
  compiler's interval-only map projection does not cover this sparse domain.
  [The application projection](projection.py) therefore represents the complete
  maps as sets of `{va, source}` and `{va, definitions}` records, respectively.
  The actual-state observer applies the same representation to Rust map entries.

This second conversion changes only the wire representation. It preserves every
key and value, includes unavailable and unreached entries, rejects duplicate or
noncanonical keys, and checks an exact inverse for every projected trace. Its
output types are derived from the two checked Apalache map declarations. Other
fields are copied exactly. Raw typed traces and raw Apalache evidence remain in
the corpus alongside the projected files. The `ariadne.mbt-address-map-projection/v1`
receipts bind raw bytes, projected bytes, and converter source; they are
application-owned receipts, not compiler-generated projection certificates.

## Acceptance and recorded result

Acceptance requires complete replay of every fixture, repeated initialization,
all six transition kinds and the required adjacent transition pairs, actual
port release, deliberate implementation mutations rejected as genuine model
mismatches with the same observer, and wrong-digest rejection before adapter
creation. The adapter must never use previous or expected model state as its
observed state.

The runner requires each of the six fixtures twice within one negotiated
binding, every transition kind, and seven adjacent transition pairs. Action and
pair counters use the generated contract's stable IDs, such as `Visit` and
`FinishRecovery`. Counters
are reported as matched coverage only after Mirrors accepts the entire replay;
failed attempts expose dispatch counts without claiming matched coverage.
The 27 input-contract rejection cases and generated-request tests remain in the
ordinary Rust test suite; this MBT corpus exercises the six specified fixtures.

On 2026-09-19, [the complete gate passed](results/latest.json):

| Check | Result |
| --- | --- |
| Correct implementation | 12 complete traces, 168 matched states, one binding creation and one actual port `Drop` |
| Required coverage | All six transition kinds and all seven required adjacent pairs |
| Wrong semantic digest | Structured `interface_digest_mismatch` registration rejection; zero factories and SUT observations |
| Discover call-only targets | Genuine mismatch at `visit`; port `Drop` confirmed |
| Propagate across call edges | Genuine mismatch at `propagate`; port `Drop` confirmed |
| Treat may-writes as definite kills | Genuine mismatch at `propagate`; port `Drop` confirmed |
| Permit uncertified dump fallback | Genuine mismatch at `visit`; port `Drop` confirmed |
| Skip backward-slice expansion | Genuine mismatch at `expandSlice`; port `Drop` confirmed |

Mutants are mechanical edits to fresh copies of the actual `src/engine.rs`,
built with the same API, unchanged observer, and byte-identical generated binding.
A codec failure, timeout,
registration failure, or callback failure cannot count as a killed mutant.
The working Rust implementation is never edited by this tier. Binary hashes,
source and generated-file hashes, first mismatches, coverage, and port-drop counts are retained in
the report; detailed build and replay logs remain under ignored `mbt/.work/`.

The generated binding owns its port and releases it through Rust `Drop`. Its
`LocalBinding.dispose` callback is a no-op, so the v2 reports record `portDrops`
instead of treating a disposal callback invocation as resource release. Adapter
`Drop` first drops the real `Analyzer`, then records the cleanup event. Both
successful replay and every mutant require exactly one drop; wrong-digest
rejection requires no port construction or drop.

The refactor was checked against [the handwritten baseline](results/handwritten-baseline.json):
the corpus manifest, analyzer source hashes, semantic digest, all 168 matched
states, action/pair coverage, and each mutant's first mismatch position were
preserved. This comparison is optional for normal runs and reproducible with:

```sh
python3 mbt/run.py --compare-baseline mbt/results/handwritten-baseline.json
```

Focused binding checks cover generated input rejection before any reset,
poisoning, generated action coverage, and ownership release. The freshness test
alters only a temporary generated copy and requires rejection without repair:

```sh
cargo test --offline --locked --manifest-path mbt/Cargo.toml
python3 mbt/test_binding.py
cargo fmt --manifest-path mbt/Cargo.toml -- --check
cargo clippy --offline --locked --manifest-path mbt/Cargo.toml --all-targets -- -D warnings
```

This is local conformance testing. MirrorGate's Rust integration was inspected
for its supported lifecycle and language boundary; restricted workers and
restricted authoring are additional modes and are not claimed by this gate.
The Rust binding is compiler-generated; the domain adapter implements its typed
port. Port-drop evidence describes local lifecycle, not Gate-confirmed physical
cleanup. These finite traces and selected mutants do not prove refinement for
all requests, arbitrary schedules, or the correctness of external adapters.
