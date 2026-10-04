# Ariadne investigation module

## Context and follow-up

**Status.** Current producer-explanation and I5a zero-address APIs.

**Why this document exists.** [Contracts](../investigation-contracts.md) define exact binding and the meaning of possible producers.

**What this document establishes.** Bound completed analysis supports possible-producer explanations and a separate captured-context zero-address assessment. Both return typed claims, gaps and evidence requirements without running another dataflow solver.

**Where to go next.**

- [Delivery evidence](../investigation-validation.md) — shows what the implementation has exercised.
- [I5a contracts](../i5a-contracts.md) — define exception-context binding and the separate numeric assessment.
- [Follow-up plan](../../../Plans/investigation-layer.md) — tracks missing capture acceptance and later questions.

**What remains unresolved.** Full original-Windows I4 and controlled real Windows I5a qualification remain open. Broader hypothesis, object/source-context and cross-capture questions remain later work.

For the wider context, see the optional [documentation map](../../documentation-map.md).

The first question asks which earlier definitions could
contribute to a selected captured memory-address operand, what evidence supports
them, and what prevents a stronger conclusion?

It consumes an owned `BoundInvestigation`, binds exact completed request/state
to normalized evidence, and produces typed claims, per-byte possible producers,
alternatives, gaps and concrete evidence requirements. It has no dependency on
the input reader, BAP runtime or report renderers. The concrete capture adapter
is `input::investigation::bind_investigation`.

```text
bind_investigation(prepared, completed_analyzer)
  -> BoundInvestigation
explain_fault_address(bound, FaultAddressQuestion, ExplainLimits)
  -> Explanation
```

The numeric question uses an owned `BoundFaultContext` built by
`input::investigation::bind_fault_context`. `assess_zero_address` evaluates the
selected access under the admitted Windows AMD64 scalar MOV profile and returns
consistent, refuted-under-premises or unknown. Captured values apply only at the
exception site. The [I5a contracts](../i5a-contracts.md) define evidence, limits
and its independently versioned report.

The root engine is reused; this module does not reconstruct a historical
instruction sequence or implement a second dataflow solver. The
[contracts](../investigation-contracts.md) define identity, bounded
address evidence, typed claim classes, negative behavior and actual CLI options.
The [design](../investigation-layer-design.md) and
[I0–I4 plan](../../../Plans/investigation-layer.md) define the release scope.

```sh
cargo test --offline --locked --manifest-path Cargo.toml
cargo clippy --offline --locked --manifest-path Cargo.toml --all-targets -- -D warnings
python3 tools/check_investigation.py
python3 tools/check_i5a.py
```

Other hypothesis, matched object/source and cross-capture questions remain
planned. Stronger lifetime/path conclusions require independently supplied
and accepted evidence rather than a suspicious pointer or fixture label.
