# Priority 3: readable minidump reports and release examples

## Context and follow-up

**Status.** Historical presentation delivery and output-equivalence evidence.

**Why this document exists.** [Presentation design](priority-3-investigator-presentation-design.md) requires readable instruction evidence without changing graph meaning.

**What this document establishes.** The presentation delivery adds the instruction overview and Linux/Windows examples and records unchanged JSON/DOT semantics for the exercised case.

**Where to go next.**

- [Usage examples](minidump-investigator-examples.md) — show the delivered CLI presentation.
- [Domain explanations](investigation-layer-design.md) — addresses questions beyond displaying raw slices.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. This resolves the scoped readability work, not new investigation capabilities.

For the wider context, see the optional [documentation map](../documentation-map.md).

Validated **2026-09-29 23:26 CST** against the
[Priority 3 design](priority-3-investigator-presentation-design.md) and
[implementation plan](../../Plans/completed/priority-3-investigator-presentation-plan.md). The
[source-bound record](../../evidence/Ariadne/priority-2-3-validation.json) retains the exact
Windows/Linux example identities, format hashes, real-capture replay and
11-gate minidump run. The [example guide](minidump-investigator-examples.md)
contains commands for both platforms and partial-report behavior.

`report.txt` now starts with a scan-friendly Instruction overview. Each VA
shows exact captured bytes, opcode, normalized typed operands, reviewed or
opaque rule quality, capture stream/file offset, slice membership, typed
issues and counts of possible input-origin sites. The full per-site evidence
and reaching-definition sections still follow. Unknown bytes and unsupported
sites remain visibly unknown; the overview does not claim a historical path.

The pinned Stage B Linux and Windows minidumps were run through the CLI
with fresh output directories. Tests assert the high Windows VA, the
faulting memory operand, captured file offset, relevant producer count, an
unrelated instruction outside the slice and the opaque return. A partial
Linux query shows `not_captured` and an unvisited seed. Malformed input,
missing decoder, exhausted limits and failed publication remain nonzero
errors without a misleading completed directory. Graphviz parsed the DOT
in the integrated Stage C gate.

On the controlled real Chromium case, the new text hash differs as intended.
The JSON v1 and DOT hashes are **byte-identical** to the previous accepted
result; decoded sites, graph edges, reaching origins, slice and obligations
are unchanged. The integrated minidump gate passed 11/11 components with
57 stable source hashes. This delivery changes presentation, not reader,
effect, analyzer or formal AMD64 semantics.
