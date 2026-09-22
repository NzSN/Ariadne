# AMD64 Lean formalization

This package contains the staged proof foundations of the
[accepted AMD64 design](../docs/amd64-semantics-design.md), not a complete ISA
formalization. It uses the pinned Lean 4.33.1 standard library and no external
Lake packages. `lake-manifest.json` records that dependency boundary.

The immediate delivery target is the [verified user64 subset](../docs/amd64-user64.md).
Per-form/profile acceptance replaces whole-manual completion as the first
milestone. Existing broader modules are preserved without advertising them as
supported. The conservative `Unsupported` projection is an analysis contract;
it cannot invent a no-op, retirement, fault or known successor.
Only its no-trust `UnknownInstructionFallback` entry is accepted for the
current profile hash. The selective helper remains an expert-only contract and
is not profile acceptance.

| Module | Current boundary |
| --- | --- |
| `RegisterViews` | Five physical GPR storage views in 64-bit mode and representation correspondence |
| `ArchitecturalState` | CPU-local state, canonical alias banks, profile/mode predicates and field inventory; delegated validity constraints remain |
| `InstructionForms` | Reviewed-constraint validation over decoded operand shapes; executable payload coupling is separate work |
| `Memory` | Full-width addressing and constrained access/captured-byte projection; complete page walks and ordering remain separate |
| `Exceptions` | Exception/commit/restart contracts; complete delivery is not implemented |
| `IntegerSemantics` | Value/flag kernels, selected general proofs and directed checks; full correspondence and instruction binding remain open |
| `Operands`, `InstructionFormsCore` | Actual operand payloads, shape/identity coupling and a bounded reviewed core-form registry |
| `PageWalk`, `ConcreteMemory` | Byte-backed common translation certificates and architectural/captured-memory separation; explicit remaining system contracts |
| `IntegerExecution` | CPU register/immediate body application, including a reviewed core dispatcher; retirement/event composition remains open |
| `Strings`, `StringsMemory` | Repetition controls and resolved RAM element bodies; device I/O and complete instruction binding remain open |
| `Unsupported` | No-trust default discards concrete/undefined facts and exposes no retirement, fault, success or successor; selective trusted summaries and runtime integration remain separate |

Follow-up operand, page-walk and string modules are developed under the same
package. The [task list](../docs/amd64-semantics-tasks.md) records their state.
`bash Specs/check-amd64.sh` from the repository root discovers and builds every
module, audits their combined namespace, and runs TLA+ component checks. It can
expose in-progress failures and is not a full-coverage certificate.

```sh
cd lean
lake build
lake env lean Audit.lean
```

The original `AMD64/RegisterViews.lean` foundation proves:

- View bounds for all five physical GPR views.
- Read-after-write for every input word and payload.
- Preservation outside byte/word/qword views.
- Upper-half clearing for dword writes in 64-bit mode.
- Whole-word replacement for qword writes.
- Both round trips between zero-based typed words and one-based source words.
- Read and write correspondence with the reviewed TLA+ operator transcription.

All operations in this first kernel concern GPR storage in 64-bit mode. High-byte
encoding legality, other execution modes, architectural state beyond one word,
and instruction execution are not proved here.

`Audit.lean` checks declarations under the `AMD64` namespace and declarations
originating in AMD64 modules, including private helpers/examples and otherwise
unused axioms. Only Lean's usual logical axioms
`propext`, `Quot.sound`, and `Classical.choice` are permitted. The audit rejects
admitted proofs and native-computation proof axioms. `lake build` alone does not
run the audit; the combined foundation script always runs both.

The TLA+ source and Lean transcription are pinned in
`Specs/AMD64/correspondence.lock.json`. Hash checking detects changes requiring
review; it does not prove semantic equivalence to the source text. After a
source change, review the operator mapping, recheck the proofs and TLA+ fixtures,
then deliberately update the hashes. Do not automatically refresh the lock as
part of a check.

The long-term target includes complete typed architectural state, instruction
relations, environment contracts, and refinement to Ariadne's analysis model.
Their pending tasks are recorded in [the task list](../docs/amd64-semantics-tasks.md).
