# BAP v3 admission and ordinary-continuation contract

## Context and follow-up

**Status.** P0 contract frozen before runtime edits on 2026-10-09. The
[freeze receipt](../../evidence/Ariadne/bap-admission/p0-contract-freeze.json)
binds the original projection sources, installed provider and independent
expectations. The [initial execution checkpoint](bap-admission-checkpoint.md)
preserves P0–P3 checks and earlier P4 failures. The
[accepted successor](real-capture-repin-79938.md) supplies current remote
qualification with remaining historical real-Linux clauses excluded.

**Why this document exists.** The [P0–P4 plan](../../Plans/bap-projection-admission.md)
addresses nonempty lifts rejected solely by an opcode whitelist and recovery
stops that conflate unavailable data effects with unknown control.

**What this document establishes.** Supported typed-BIL admission, effect/control
failure classes, the v3 profile and independent initial expectations. Removing
an opcode whitelist changes producer coverage, not the core transfer equations.

**Where to go next.**

- [Implementation plan](../../Plans/bap-projection-admission.md) — P1–P4 delivery
  and accepted release-runtime, native and external-capture scope.
- [Backend design](bap-semantic-backend-design.md) — transport, capture and
  projection invariants preserved by this extension.
- [Independent contract](../../tests/bap/fixtures/admission/contract.json) and
  [oracle](../../tests/bap/fixtures/admission/oracle.py) — exact initial encodings,
  byte-cell effects, access footprints and unbounded-integer flag equations.
- [Analysis model](../../Specs/Ariadne.tla) and
  [effects model](../../Specs/AriadneEffects.tla) — existing admissible ordinary
  summaries, weak/must update rules and local successor policy.

**What remains unresolved.** Finite producer admission does not prove universal
AMD64 lifting correctness. Prefix/system/SIMD/x87/loop semantics, general alias
precision, indirect-target enumeration and historical execution remain outside
this contract. External Electron acceptance requires its exact capture bytes.

See the [documentation map](../documentation-map.md) for wider navigation.

## Admission order and identity

1. Validate protocol identity, exact consumed bytes/length and typed AST budgets.
2. Require compatible independent decoded control and applicable prefixes.
3. Check architectural namespace, scalar/memory types, widths, extraction/cast
   bounds and virtual binding. Validate all alternatives before evaluation.
4. Interpret supported BIL capabilities without an opcode membership gate.
5. Bind instruction-specific obligations: decoded MOV footprints, conditional
   preservation, reviewed undefined flags and direct/indirect control targets.

The producer profile becomes `bap-bit-provenance-v3`. Existing report envelopes
can carry it and the new `opaque-ordinary` semantic status without a schema
change. Query/semantic identities already bind projection profile and evidence.
I5a must explicitly admit v3 for its unchanged six scalar MOV forms; it must
continue rejecting opaque or unsupported semantics. Earlier v2 reports remain
historical and are never rewritten to obtain v3 acceptance.

Opcode strings are descriptive metadata and may select a reviewed exceptional
obligation; they are not a generic permission list. The exact `90` NOP exception
remains byte-bound. Calls and returns retain the separate opaque all-location
policy rather than deriving callee behavior from their BIL.

## Decision matrix

| Input | Outcome |
| --- | --- |
| Valid supported BIL and compatible control/operands | Projected effects; unknown output values retain dependencies, possible writes and explicit gaps. |
| Valid ordinary control, known architectural namespace and typed data-only BIL with an unsupported scalar operation | `opaque-ordinary`; keep the decoded structural continuation, all tracked uses/may-defs, no must-defs and a data-effect gap. |
| Empty lift except exact `90` | Stop with an unavailable-semantics gap. |
| Unmodeled architectural state, RIP assignment, jump/exception/special/loop uncertainty or control disagreement | Stop; no ordinary continuation. |
| Guarded LOCK/REP/segment/address-size semantics | Stop with a specific prefix gap. |
| Malformed AST/type/width, unbound virtual read or invalid extraction | Query failure; no incomplete result publication. |
| Operand or consumed-byte disagreement | Explicit disagreement stop; never opaque ordinary continuation. |
| AST/path/resource exhaustion | Query failure; an operational failure is not an unknown data-effect result. |

Both the ordinary classification and the absence of unmodeled control must be
established. LLVM classification alone cannot turn an empty, malformed or
control-bearing BIL program into fallthrough. A `Special` is not a pure scalar
operation. Unknown architectural namespaces remain excluded even if their
printed instruction looks ordinary.

## Effects and independent expectations

The frozen contract covers the four observed forms and boundary encodings:
SUB64ri8 sign-extended immediate limits, MOVZX32rm8 REX/index/negative displacement,
distinct/self XOR64rr and CMP8mi byte boundaries. Python arithmetic computes
result/CF/OF/AF/PF/SF/ZF independently of Ariadne's provenance evaluator.
Self-XOR's numeric result is zero; a generic unknown AF still retains all
possible input origins and cannot establish a definite flag kill.

MOVZX memory addresses use the base/index/displacement and `memory:any`; a
32-bit destination replaces all eight destination bytes by zero extension.
CMP writes flags, not a GPR. Address-access evidence excludes store payload
dependencies. Stores never must-kill `memory:any`.

P2 paired real encodings include short/long Jcc/JMP and immediate arithmetic.
Generated BIL cases cover composition, typed scalar/memory distinctions and
conditional writes; opcode spoofing is not producer acceptance evidence.

## Core, native and report compatibility

The existing `Ariadne.tla` and effects contracts already admit an ordinary
summary with all uses/may-defs and empty must-defs. No new core action or transfer
rule is introduced. The producer must supply the structural next edge and retain
its preparation/semantic gap. Active model replay therefore remains required,
while an instruction-step ISA/Lean model is not revived.

Native capture admission must bind `opaque-ordinary` to the v3 profile, captured
bytes, ordinary normalized control, all-location possible effects and empty
definite writes. Rust report binding must reject mutated classifications or
effects. Text/JSON/DOT retain the semantic status and data-effect gap. Consumers
and explanations remain partial where an opaque predecessor is relevant.

A producer–opaque–consumer regression must retain both the earlier producer and
the opaque alternative. Native/reference comparison uses the same immutable
request and an available source-bound native helper. Failed builds/timeouts do
not count as mutation sensitivity or native parity.


## Historical-output profile migration

The existing pre-I5a byte oracle remains unchanged. A separate comparison first
builds the frozen pre-change sources in an isolated target directory and requires
all 24 historical output hashes to match that oracle. The v3 outputs then differ
only by the explicit projection-profile labels, the resulting semantic-profile
binding and content-addressed scope/evidence/fact/claim identifiers. All captured
bytes, operands, control, effects, graph/state/slice fields, address uses, claims,
premises and gaps must otherwise match. Native/reference comparisons remain
byte-exact after removing only validated native backend receipts.

The comparison record advances to `ariadne.i5a-cli-equivalence/v3` and reports
`legacyReportsUnchanged` separately from `projectionMigrationVerified`. It does
not relabel changed v3 bytes as the historical v2 outputs. Unsupported ordinary
continuation is tested on its new owned corpus, not normalized away in this
legacy comparison. Mutated effects, claims, capture/tool hashes or unresolved
references must fail the migration comparison.
