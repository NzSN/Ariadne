# Is the partial result expected?

Yes—**under the current resolver profile and limits.**

- All **45 table targets** were recovered, but `cyclic-incoming-state` prevents certifying that they exhaust every incoming state.
- Unknown entry origins, memory/call effects and **13 decode failures** remain.
- The explanation hits its **32,768-origin-link limit**, so it is also marked truncated.

The core dataflow computation finished successfully. Increasing the reporting limit could remove truncation; the semantic gaps would still justify `Partial`.

Ariadne · Original dump retry at `b5d56b7` · `dump_048B10C302A4460D8A1FC75088`

## Context and follow-up

**Status.** Historical browser report moved from `target/dump048B-retry-b5d56b7/partial-answer.html` on 2026-10-16. This Markdown is a transcription of that preserved HTML.

**Why this document exists.** It preserves the explanation shown for the original dump retry; the [assurance contract](../../docs/Ariadne/semantic-assurance.md) defines the limits of retained results.

**What this document establishes.** It records why that bounded query returned `Partial` at revision `b5d56b7`.

**Where to go next.** Use the [report index](ariadne-reports-index.md) for later explanations and the [target-resolution contract](../../docs/Ariadne/indirect-target-resolution.md) for current semantics.

**What remains unresolved.** This archived answer does not refresh the dump result or establish executed history; later dated reports may supersede its limits.
