# Verified 64-bit user-mode semantics

The immediate deliverable is an explicitly scoped, machine-checked formal
semantics library for Ariadne's crash-analysis needs. Full-manual coverage stays
on the roadmap. Acceptance is measured per **form/profile case**, and useful
component progress is recorded independently of completed instruction steps.

## Profile and milestones

The machine-readable definition is
[`user64-profile.json`](../Specs/AMD64/user64-profile.json). Its exact form IDs
and operand projections are fixed in the manifest; editing the profile
invalidates prior profile-bound acceptance evidence.

| Milestone | Targeted cases | Priority |
| --- | ---: | --- |
| `register-core` | 49 | Current: MOV, arithmetic, logic, comparisons and unary register forms |
| `near-control-stack` | 72 | Next: near CALL/RET/JMP/Jcc and selected PUSH/POP/LEAVE forms |
| `ram-data` | 156 | Next: selected common data-operation memory forms |

A case combines a source form with the declared execution profile and concrete
operand alternatives. These numbers are not tests, input combinations or
fully implemented mnemonics. A register projection of a reg/mem source form
retains the original source row and excludes memory only from this particular
case. The global catalogue retains both alternatives. Each case digest binds
the complete source-form record as well as the profile projection, so changing
source metadata, constraints or operands invalidates prior case evidence.

The initial profile uses long64 at CPL 3. Operand widths are 8/16/32/64 where
legal; address sizes are 32/64, and stack addresses are 64-bit. Control/stack
cases require CET disabled. Memory cases require ordinary write-back RAM with
explicit mapping and protection evidence and homogeneous type per access span.
The profile covers a single logical processor's instruction boundary and makes
no multiprocessor coherence claim. Undefined architectural values remain
relational; implementation-dependent fault priority uses a fixed profile.

Inputs are validated decoded instructions with successful fetch and an exact
length of 1..15 bytes. Outputs must include the appropriate completed step or
synchronous fault, state frames and restart information. OS handler entry and
asynchronous events between boundaries sit outside this library's initial
boundary. A kernel returning a value or a body result with unchanged RIP does
not satisfy this instruction-step contract.

Legacy modes, far/privileged control transfers, descriptor/task/interrupt
execution, CET paths, atomics/fences/concurrency claims, MMIO/port I/O,
LWP/monitor extensions and unlisted forms remain outside advertised support.
Existing broader modules remain available as checked or explicitly unfinished
research components; preserving them does not advertise support.

## Correctness and conservative fallback

Every accepted case must close decoding/payload binding, relevant state
validity, values/flags/frames, faults and commit behavior, instruction boundary,
TLA/Lean correspondence and conservative analysis projection. Untouched state
banks must be framed; implementing every operation on those banks is not a
prerequisite. TLA+ remains authoritative and Lean remains machine checked.

An unsupported instruction produces explicit uncertainty. It contributes no
successful no-op, retirement, fabricated #UD or known control-flow successor.
Potentially affected register/flag/memory facts and conclusions depending on
unresolved control flow cannot remain asserted. Missing captured data is a
separate knowledge gap, and architectural undefinedness is a separate specified
set of possible results. The fallback contract must be accepted before any
profile case is advertised as verified.

The current Rust analyzer consumes adapter-provided summaries and does not yet
run this AMD64 library. This profile gate certifies the formal deliverable;
it does not claim that a production decoder/runtime adapter has been shipped.

## Progress and acceptance

[`user64-coverage.json`](../Specs/AMD64/user64-coverage.json) records targeted
cases, source review, implementation stage, open obligations and semantic
acceptance references. Initially, 49 register cases have paired body bindings;
none is automatically promoted to a verified instruction step. Planned and
partial RAM/control cases remain explicitly unsupported until accepted.
The no-trust default fallback foundation is accepted for profile digest
`5c07adb4b1391d5b2ec29348b208789c2469b2728afd700f27cd3a90bef078cf`;
the expert selective helper and every instruction case remain unaccepted.
The profile router reports only an inventory candidate after all scoped
evidence closes; it is not a runtime semantic-handler selector and does not
validate decoded payloads or architectural preconditions.

```sh
# Lightweight profile integrity and progress report.
python3 tools/amd64_profile.py report
python3 tools/amd64_profile.py report --json

# Source-freshness and acceptance gate for the first milestone.
python3 tools/amd64_profile.py check --require-milestone register-core

# Run component checks, then require the selected milestone.
bash Specs/check-amd64.sh --require-milestone register-core

# Optional full-manual roadmap gate; not the first-release criterion.
python3 tools/amd64_inventory.py check --require-complete
```

The lightweight gate validates only the selected profile's recursively cited
evidence and current source hashes; unrelated open full-manual roadmap leaves
do not block it. The
full check script actually runs the model/proof checks. Accepted cases must cite
accepted semantic leaves in the existing coverage ledger, tied to both the
profile hash and exact case hash. Both formalizations, executable TLA checks,
Lean build/audit and closed obligations are required. Whole-mnemonic/manual
completion is not required. Merely changing a status, compiling a type, or
passing an unrelated helper fixture cannot promote a case.
