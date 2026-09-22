# AMD64 mul/div execution worktree checkpoint

The Lean module binds the 27 MUL, IMUL, DIV, IDIV and MULX form IDs to CPU
register effects. It snapshots explicit and implicit operands before writes,
orders MULX writes so an overlapping destination retains the documented upper
half, validates IMUL immediate sign extension, and represents divide error as
an outcome containing the unchanged pre-state.

This module is outside the immediate long64/CPL3 common-integer milestone. It
is intentionally not imported by the root library or presented as paired
TLA+/Lean coverage. Memory operands remain unavailable and the authoritative
TLA+ execution transcription is still pending. Its focused Lean checks preserve
the work without broadening the admitted milestone.
