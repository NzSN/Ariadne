# I5a: zero-address consistency under a captured exception context

## Context and follow-up

**Status.** Implemented in the working tree on 2026-10-03, following the design
based on `c9eb4c5`. Historical source/fixture qualification passes; the current
[native refresh](i5a-native-qualification.md) qualifies both source/fixture and
controlled Windows tiers under its pinned dependency snapshot. Scope is
Windows AMD64 scalar MOV access violations; Linux and other hypotheses are deferred.

**Why this document exists.** The [first investigation question](investigation-layer-design.md)
explains possible producers but does not evaluate a fault-time address. A useful
next question is whether the selected access starts at zero. Answering it needs
valid captured operands, not guesses from producer alternatives or missing
registers.

**What this document establishes.** One precise hypothesis, a bounded admission
profile, evidence requirements, allowed conclusions and independent acceptance
cases. It explains how the question can use the existing analysis without
reconstructing an executed path or implementing another ISA model.

**Where to go next.**

- [Native-default qualification plan](../../Plans/i5a-native-qualification.md)
  refreshes phase measurements, backend identities and controlled Windows
  acceptance after Stage 2 adoption.
- [Native qualification guide](i5a-native-qualification.md) records the refreshed
  result and its limits separately from historical measurements.
- [Native Windows demo](crashpad-demo-validation.md) supplies controlled capture
  evidence and preserves its historical performance result.
- [Delivery and validation](i5a-validation.md) records the exercised implementation
  and the remaining Windows capture requirements.
- [Implemented I5a contracts](i5a-contracts.md) describe the working-tree
  interface, evidence, report and CLI; qualification is reported separately.
- [H0 source and fixture review](i5a-source-review.md) records the field layout,
  validity groups and finite independent oracle used for implementation.
- [I5a implementation plan](../../Plans/i5a-zero-address.md) sequences admission
  review, exception evidence, assessment, reports and qualification for this
  first Windows zero-address question and records its delivery status.
- [Investigation stage plan, I5a](../../Plans/investigation-layer.md#i5a--zero-address-consistency)
  places this design after the delivered first question and keeps active Windows
  I4 qualification separate.
- [Input module](modules/input.md) describes the snapshot reader that retains
  the exception evidence.
- [Current investigation contracts](investigation-contracts.md) define the
  existing query identity, address expressions and conservative claim rules.
- [Semantic assurance](semantic-assurance.md) retains BAP as a trusted semantic
  provider; this design does not revive independent instruction-step proofs.

**What remains unresolved.** The controlled Windows demo has valid capture and
answer evidence, but exceeds the frozen CLI latency condition. The finite
admitted forms do not establish whole-ISA coverage. The [active I4 replacement](i4-windows-repin-validation.md) passes correctness but exceeds its fixed CLI budget.

The [documentation map](../documentation-map.md) is optional navigation.

## Selected question and claim

For one selected captured memory access, assess:

> Under the admitted exception-context and instruction-semantics premises, does
> this operand begin an access at virtual address zero?

The hypothesis is **effective address equals zero**, not “a null pointer caused
the crash.” For `[RAX + 8]` with observed `RAX = 0`, the effective address is eight:
that refutes this exact hypothesis but does not refute a null-derived access.
Conversely, modular arithmetic can produce zero from nonzero inputs, so a zero
result does not identify a null base or its origin.

The output explains the expression, observations used, computed value and
premises. Existing possible-producer explanations remain separate: a fault-time
register observation may be used at the selected exception instruction only,
never applied backward to earlier producers or branch decisions.

Windows is the first profile because it gives this design an explicit exception
parameter interpretation to qualify. This is a scope choice, not evidence that
the missing original Windows capture is now available. The existing Linux
investigation remains supported; interpreting its signal/context records for
this new question requires a separate admission profile and tests.

## Baseline facts and implemented extension

| Source fact at the design baseline | Consequence |
| --- | --- |
| [AddressExpression](../../src/effects/address.rs) represents modular 64-bit affine arithmetic over before-instruction GPR values. | Reuse the expression and its semantic identity; no assembly-text inference or second symbolic solver. |
| [BIL address extraction](../../src/bap/address.rs) resolves supported temporaries and RIP-relative constants at the captured VA. | Evaluate the retained expression directly; do not add instruction length or substitute a different RIP again. |
| [ExceptionInfo](../../src/input/mod.rs) stores thread ID, code, `reported_address` and a register map. | It is insufficient for I5a: preserve parameter count/values, flags, record/context provenance and validity evidence. |
| [Reader normalization](../../src/input/minidump.rs) copies `reported_address` from `exception_record.exception_address`. | This field is not a normalized inaccessible-data address. Its name or a zero value cannot establish the selected hypothesis. |
| The register reader honors AMD64 context validity groups rather than trusting every field in the raw struct. | Preserve that behavior and the evidence for each retained register. A raw zero with its validity group absent is missing data. |
| [Stage B fixtures](../../tests/input/fixtures/make_stage_b.py) set the CONTROL group, omit INTEGER validity and exception parameters, and store zero in the exception-address field. | Keep these fixtures unchanged as first-question regressions. They must yield unknown for I5a; add separate fixtures with the required evidence. |

The [reader-owned extension](../../src/input/fault_context.rs) now retains the
missing exception fields and provenance alongside the legacy metadata. The
[source review](i5a-source-review.md) records its offsets/validity interpretation;
the old fixtures remain unknown-result regressions.

For Windows access violations, the exception record distinguishes its exception
location from the parameters describing operation kind and inaccessible data.
Parameter count determines which array entries are defined.
[Microsoft MINIDUMP_EXCEPTION reference](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception/).

The exception stream associates a thread identifier with a context descriptor;
the minidump writer's exception input describes the processor context at the
exception. Use that selected exception context, not a convenient thread-list
context or fallback register map.
[Exception stream](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_stream),
[writer exception information](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_information).

These records can also be supplied for software-generated exceptions. Agreement
between fields does not independently prove hardware fault origin. Treat precise
fault-context interpretation as an explicit premise, never infer it from a
reserved flag or from the exception code alone.
[Microsoft EXCEPTION_RECORD reference](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_record).

## Initial admission profile

Implemented profile ID: `windows-amd64-av-scalar-mov-v1`. A definite assessment needs
every applicable item below. Failure of an evidence prerequisite means unknown;
malformed structures and cross-query/snapshot substitutions remain errors.

1. The immutable snapshot is Windows AMD64. The selected exception stream and
   its context have unambiguous bounded source spans, matching artifact identity
   and one exception-thread association. Do not merge thread-list registers.
2. The exception code is access violation (`0xc0000005`), at least two parameters
   are defined, and the operation is read or write. Execute, in-page-error,
   breakpoint, chained/nested or unsupported exception profiles are out of scope.
3. Valid exception-context RIP equals the question's instruction VA, and the
   Windows exception-location field agrees. A disagreement is inconsistent
   evidence, not a refutation of the address hypothesis.
4. The instruction is reached/decoded in the bound completed query and its
   consumed captured bytes are unambiguous. Asking this question adds no root,
   reads no companion bytes and creates no alternate instruction stream.
5. BAP has admitted the site, and its address evidence contains one unconditional
   memory access with a supported 64-bit affine expression and no address gaps.
   The initial candidate form set is `MOV32rm`, `MOV64rm`, `MOV32mr`, `MOV64mr`,
   `MOV32mi` and `MOV64mi32`; each admission still requires exact-form review,
   prefix guards and independent cases. Names alone are not coverage evidence.
6. Exclude stack/control, string/repeated, atomic/locked, vector, segment-override,
   address-size-override and multiple-access instructions. The profile assumes
   flat 64-bit addressing and the supplied context describes the selected
   instruction before its ordinary memory access. No partial-progress or
   restart-state interpretation is introduced.
7. Every GPR term has a valid complete 64-bit observation from that exception
   context. Preserve register name/value, validity-group evidence and source
   location. A constant expression needs no unused GPRs, but still needs valid
   RIP and context association.
8. Evaluate the normalized expression modulo 2^64. For this first profile, admit
   only a nonwrapping access span wholly below `0x0000800000000000`; other ranges
   remain unknown instead of guessing a canonicality configuration. The reported
   inaccessible-data address must lie in that span, and its read/write kind must
   agree with the selected access. This is a consistency check, not a proof of
   memory permissions, retirement or hardware fault attribution.

The read/write/execute parameter meanings come from the
[Windows exception record contract](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_record).
The narrower instruction/range restrictions above are Ariadne design choices.

Missing data relevant to another predecessor does not automatically block this
numeric question. For example, an opaque earlier call can keep the producer
explanation partial while a valid fault-time register observation supports the
zero-address assessment. Keep the two claims and their premises distinguishable.

## Small interface and owned evidence

Implemented interface, shown schematically:

```text
input adapter:
  bind_fault_context(prepared, completed_analyzer) -> BoundFaultContext

investigation module:
  assess_zero_address(bound_fault_context, FaultAddressQuestion, AssessmentLimits)
    -> ZeroAddressAssessment
```

The input adapter reuses exact prepared/analyzer binding and constructs an owned,
read-only context from the immutable reader's data. It retains unsupported or
missing context as typed gaps; it does not accept an arbitrary register map as
a valid exception context. Raw acquisition, field extraction and normalization
stay in `src/input/`; normalized evidence is also checked by the pure domain
validator. The assessment lives in `src/investigation/` and depends
on normalized evidence and root model types, not the input reader, BAP runtime
or renderers. Avoid a generic hypothesis engine or new provider trait for this
single question.

The new scope identity includes the existing snapshot/artifact/query/request and
semantic profile, the selected question, normalized exception/context evidence
and admission-profile version. Evidence identifies raw exception fields,
context bytes and validity facts by artifact-relative spans/digests. Preserve
the current low-level report meaning; do not silently redefine `reported_address`.

The reported premises include that the captured instruction bytes still describe
the exception instruction and that the selected context supplies its pre-access
values. Snapshot hashes and equal PCs do not prove temporal coherence by
themselves; known conflicting evidence prevents a definite assessment.

The assessment retains expression terms, used observations, evaluated address,
access width/role, reported data address, source references, premises and gaps.
An independent checker must be able to recompute the bounded arithmetic from
the retained evidence. Formatting and file publication stay in reports/CLI.

## Conclusions and failure behavior

| Outcome | Required condition | Allowed wording |
| --- | --- | --- |
| `consistent_with_evidence` | All admission premises hold and the evaluated start address is zero. | The selected access starts at zero under the recorded context and semantic premises. |
| `refuted_under_premises` | All admission premises hold and the evaluated start address is nonzero. | This exact zero-start hypothesis is refuted under those premises. |
| `unknown` | A prerequisite is absent, unsupported, inconsistent or omitted by a budget. | Name the missing or conflicting evidence and what would permit an assessment. |

A reported data address of zero is not sufficient by itself. If context-based
evaluation and the exception record disagree, return unknown with both facts;
do not choose the more convenient source. No outcome asserts a null-pointer root
cause, object lifetime, actual predecessor path or numerical confidence.

Implemented separate schema: `ariadne.zero-address-assessment/v1`. These conclusion
values do not extend or reinterpret `Classification` in the existing strict
`ariadne.fault-address-explanation/v1` format. Raw captured values are observations;
the arithmetic and hypothesis conclusion are derived under stated premises.
The new schema must reject inconsistent conclusions, wrong identities, duplicate
fields and dangling references. Source observations and the derived result
remain visibly distinct in text, JSON and DOT.

Bound evaluation to the existing maximum of 16 affine terms and explicit
evidence/claim limits; no path search or producer traversal is required. Zero
budgets yield unknown with truncation diagnostics, preserving atomic reference
admission. The [fixture measurement contract](../../tests/input/fixtures/i5a/performance.json)
was frozen before qualification; the existing I4 ceilings remain unchanged.

## Independent acceptance cases

| Case | Expected assessment |
| --- | --- |
| Valid Windows read/write fixture, matching RIP/exception location, valid required GPRs, zero evaluated address and coherent data-address parameter | Consistent with this zero-start hypothesis. |
| Same profile, nonzero evaluated address and coherent parameter | Refuted under premises, with the computed value retained. |
| `RAX=0`, displacement eight, reported inaccessible byte within the resulting span | Refuted for zero-start only; no claim that null-derived access is ruled out. |
| Nonzero terms whose modular sum is zero | Consistent; no assertion that a base register was null. |
| Indexed or RIP-relative admitted form | Matches an independently computed expression; no extra RIP/length adjustment. |
| Raw register bytes are zero but the required validity group is absent | Unknown, not a zero observation. Existing Stage B fixtures remain in this category. |
| Missing parameter array, insufficient parameter count, unavailable context or unsupported platform/exception kind | Unknown with the specific requirement. |
| Different thread-list context supplies the desired value | Unknown; no fallback or merge into exception context. |
| RIP/site, exception-location, access-kind or data-span disagreement | Unknown with the conflicting observations; no false refutation. |
| Different snapshot/query or tampered observation source/identity | Binding/validation error. |
| Unsupported prefix, cast, multi-access/conditional operand, address range or restart profile | Unknown; no arithmetic or state guess. |
| Unrelated upstream entry/call gap but all fault-site prerequisites hold | A bounded numeric conclusion may coexist with a partial producer explanation. |
| Required evidence omitted by a limit | Unknown and truncated; all retained references remain valid. |

Use new fixtures with independently listed raw context flags, exception fields,
bytes and expected arithmetic. Test through the same binding/assessment interface
as callers; the oracle must not call the implementation's evaluator or merely
compare against BAP-generated expected values. Preserve existing fixture bytes
and first-question outputs. Mutations must catch zero-filling invalid registers,
using the exception-location field as a data address, substituting another
context, dropping index/displacement, misapplying RIP, bypassing admission and
promoting unknown evidence to a definite conclusion.

Source/fixture conformance and a controlled real Windows capture are separate
qualification tiers. A real case needs independently established exception-site,
context and access evidence. A new controlled case does not replace the original
Windows artifact required by I4, and existing Linux evidence does not qualify
this Windows-specific profile.

## Implementation sequence

The [I5a implementation plan](../../Plans/i5a-zero-address.md) defines H0–H5,
owning files, fixture/oracle requirements, report evolution and qualification
tiers. H0 closed the finite form/context review before admission code changes;
H1–H2 delivered the first store-form slice. H3–H4 complete the six-form matrix
and product modes. The [contracts](i5a-contracts.md) describe the delivered API;
the plan records the independently reported H5 tiers.
