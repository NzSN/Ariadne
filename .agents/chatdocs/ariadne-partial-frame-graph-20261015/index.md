# Partial frame graph — dump03958

Historical presentation: 2026-10-15. Restored: 2026-10-16.

The [interactive graph](index.html) preserves the original HTML presentation template. Its four SVG views were reconstructed from the retained completed reports because original SVG bytes were unavailable. This restoration ran no Ariadne analysis or frame-path enumeration.

The historical outcome recovered two frames, while frame-to-frame path enumeration remained unavailable with `missing-or-ambiguous-active-call-anchor`: zero returned paths and zero expanded search states. The caller retained 9 decoded instructions and 9 edges; the callee retained 768 decoded instructions and 895 edges. The focus view projects 22 retained callee starts connected to the captured PC. These are possible structural connections under the original recorded premises, not an executed history or root cause.

## Assets

- [Overview SVG](overview.svg) and [DOT](overview.dot).
- [Caller SVG](caller.svg) and [DOT](caller.dot).
- [Callee focus SVG](callee-focus.svg) and [DOT](callee-focus.dot).
- [Full partial callee CFG SVG](callee-full.svg) and [DOT](callee-full.dot).
- [Exact retained nodes, edges and instruction sources](graph-data.json).
- [Historical renderer as inert text](render.py.txt), [literal page template](page-template.html.txt), and [restoration input identities](restoration.json).

## Context and follow-up

This is an archived conversation display of the result from `dump-20261014T121127`, inspected on 2026-10-15. It explains the partial relationship between caller frame 1 and captured callee frame 0 without introducing a cross-frame control edge. Read the [historical frame outcome](../ariadne-frame-to-frame-outcome-20261015.md) for exact fields and original evidence, and the [remaining blockers](../ariadne-remaining-blockers-before-loop-20261015.md) for its unresolved scope. The historical source-hash claim remains dated; restoration verifies the retained input files and introduces no current qualification claim.
