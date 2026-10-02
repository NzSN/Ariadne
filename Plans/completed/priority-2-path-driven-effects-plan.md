# Priority 2 implementation plan: effects demanded by captured paths

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Plan dated **2026-09-29** for practical priority 2 in the
[assurance queue](../../docs/Ariadne/practical-assurance-priorities.md). This is a narrow
continuation of the [structured-operand/effect design](../../docs/Ariadne/operand-effects-design.md)
and the delivered [Stage A memory-immediate MOV rules](../../docs/Ariadne/stage-a-validation.md).
Its input is the pinned real-capture candidate and gap list from
[priority 1](priority-1-real-capture-plan.md), not a request to implement a
mnemonic family or the AMD64 user64 profile.
The first controlled Chromium case has a
[source-bound no-change decision](../../docs/Ariadne/priority-2-effects-validation.md): reviewed
forms reach the seed, while call effects remain deliberately opaque. New
real-path blockers reopen this plan.

## 1. Turn observed gaps into a bounded queue

Capture the pre-change text/DOT/JSON reports and source hashes. For each site on the
independently rooted, captured path, record dump hash, VA, exact bytes, target profile,
LLVM opcode and structured operands, prefixes, current rule/quality, and the precise
`unsupported_semantics` or `unsupported_control` issue. Rank a site only if it blocks
local discovery or materially broadens a dependency needed for the selected crash seed.
Keep unrelated unreviewed opcodes on `UnknownInstructionFallback`.

For each ranked site make a written decision: **exact effect rule**,
**reviewed control-only rule with opaque effects**, or **remain unsupported**. An
unsupported-control site cannot acquire a guessed fallthrough. A call summary remains
opaque across the callee; an apparent address producer after a call is not proof the
call preserved that register.

Exit: a short candidate matrix tied to the priority-1 artifact, with the expected change
to graph/slice precision and the selected review source for each proposed binding. If no
independently anchored real path is available, label any inventory exploratory and do
not claim path-driven completion.

## 2. Review one exact form at a time

Match the pinned LLVM 20.1.2 opcode, operand tuple, mode and admissible prefix shape to
the exact AMD manual form, citing the locked source hash and page. Review widths,
register aliases, implicit inputs/outputs, flags including undefined outputs, memory
address inputs, possible faults and normal-continuation control. Record any LLVM/source
discrepancy before changing code. A descriptor's definition flag alone cannot justify
`must_defs`.

Specify `uses`, `may_defs`, justified full-cell `must_defs`, control successors and
quality for that shape. Preserve weak updates for `memory:any`; include segment and
address-register inputs where needed; retain old origins for conditional or partial
writes. A normal-continuation summary does not assert that the crashing instruction
retired or committed. If the review cannot justify a precise rule, use a reviewed
control-only classification where possible and keep opaque effects visible.

## 3. Implement and falsify the binding

Change only the relevant normalization/rule table and its source-review matrix unless
the observed payload requires a separately justified adapter change. Add actual native
decoder observations for both Windows and Linux target profiles where the form is
supported, then focused bytes → preparation → Analyzer tests over the pinned real path.
Assert the intended producer appears, prior possible origins survive weak updates,
unrelated precise producers are excluded when justified, and every remaining issue is
reported.

Add negative variants for at least the rule's adjacent width, operand shape and
disallowed prefixes, plus the material semantic risks it exposes: omitted address/flag
input, unjustified whole-register or whole-memory kill, lost uncertainty, or invented
control. The mutants must fail the intended behavioral assertion; compiler errors and
timeouts do not count. A rule is admitted only for the reviewed exact shape; all
neighboring shapes stay on the existing fallback or their own reviewed rules.

## 4. Source-bound acceptance

Run the focused native/effect tests, `python3 tools/check_effects.py`, and
`python3 tools/check_minidump.py` with its pinned external Breakpad dumps.
Run the separate hash-checked priority-1 real-capture acceptance command with
its candidate available. Re-run that CLI query unchanged and compare its
before/after identities, graph, origins, slice and gaps. Keep existing model/MBT and
mutation gates at their required scope; record unavailable prerequisites separately.
Verify source hashes stayed stable during the final run and update the effect-rule
matrix with exact source, admitted payload and limitation.

Retain a dated `priority-2-effects-validation.md` with a per-rule evidence table and the
new priority-1 report. The priority is complete for the selected real path when every
selected, source-reviewable blocker has the required exact binding, the claimed producer
slice passes its acceptance test, and any nonblocking unknowns remain visible. A
material blocker that cannot be reviewed keeps this priority **partial**, with its
reason recorded; a path with no material effect blocker may instead close with a
source-bound no-change decision. Neither outcome claims complete AMD64 effects, faithful
fault execution, or an accepted formal `register-core`/`ram-data` case.
