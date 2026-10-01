# Ariadne investigation module

This module answers one higher-level question: which earlier definitions could
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

The root engine is reused; this module does not reconstruct a historical
instruction sequence or implement a second dataflow solver. The
[contracts](../docs/Ariadne/investigation-contracts.md) define identity, bounded
address evidence, typed claim classes, negative behavior and actual CLI options.
The [design](../docs/Ariadne/investigation-layer-design.md) and
[I0–I4 plan](../Plans/investigation-layer.md) define the release scope.

```sh
cargo test --offline --locked --manifest-path investigation/Cargo.toml
cargo clippy --offline --locked --manifest-path investigation/Cargo.toml --all-targets -- -D warnings
python3 tools/check_investigation.py
```

Later hypothesis, matched object/source and cross-capture questions remain
planned. Stronger lifetime/path conclusions require independently supplied
and accepted evidence rather than a suspicious pointer or fixture label.
