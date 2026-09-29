# Priority 3 design: readable minidump investigation reports

Design decision, **2026-09-29**. The scoped
[Priority 3 implementation plan](priority-3-investigator-presentation-plan.md)
applies this design. The existing [Stage C report schema](stage-c-report-schema.md)
remains the machine contract: one frozen query produces text, DOT and JSON v1.

## Investigator question

An investigator needs to scan from a crash-IP seed toward possible producers
without mistaking a decoder observation for a verified instruction step. Put
the decoded VA, exact captured bytes, normalized operands, effect rule and
quality, capture offsets, slice membership and outstanding issues together in
the text report. Present the possible input-origin count beside each decoded
site, with an explicit pointer to the unabridged reaching-definition section.

## Presentation contract

Add an **Instruction overview** before the detailed per-site JSON evidence in
`report.txt`. Sort by VA. Each site has a stable two-line form:

```text
0x...  <bytes or ?>  <opcode or ?>  <normalized operands>
  rule=<id or none> quality=<reviewed|opaque|unavailable> source=<captured|...> span=<stream/entry/file offset or none> slice=<yes|no> possible-input-origins=<count> issues=<list or none>
```

The operand text comes from structured `Operand` values, not decoder assembly
strings. Register views use canonical x86 names; memory views show access width,
base/index/scale/displacement and RIP-relative next IP when present. Missing or
unsupported operands stay explicit. Origin counts include only reaching
definitions for locations in that instruction's `uses` set, deduplicated by
site and origin tag; they are **possible** origins, not a chosen execution.
The full core text still contains every reaching definition and structural
edge. Avoid a truncated producer list that could appear complete.

The input package owns this join because the pure core renderer does not have
decoded operands, rule IDs or captured spans. JSON v1 field names and types
remain unchanged. DOT graph nodes and edges retain their current semantics;
its evidence comments continue to mirror JSON. A later visual redesign would
need its own report-contract review.

## Failure and uncertainty

An unvisited reference, missing capture, decoding failure or unsupported
control must not be printed as an ordinary instruction. Mark unknown bytes,
rule and operands plainly, while retaining typed issues and read-stop evidence
in the detailed report. `scope_closed` remains recovery-only. A faulting store
still receives no commit claim, and opaque calls retain all-location possible
effects without ABI preservation assumptions.

## Release examples and acceptance

Document reproducible Linux-host CLI commands for both Linux and Windows
minidumps using the pinned Stage B fixtures, plus the separate external
controlled Chromium case. Show stdout format selection and atomic three-file
publication. Example output must retain exact high VAs, bytes, provenance and
gaps. Test cross-format identity, VA/edge/obligation agreement, Graphviz DOT
parsing, partial results and output failures. The
[Priority 1 validation](priority-1-real-capture-validation.md) remains an
external-artifact acceptance case; its raw dump is not bundled as a release
example.
The scoped [Priority 3 validation](priority-3-presentation-validation.md)
records the delivered text overview and unchanged JSON/DOT contracts.
