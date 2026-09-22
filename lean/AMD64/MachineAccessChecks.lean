import AMD64.MachineAccess

namespace AMD64.MachineAccess.Checks

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory
open AMD64.MachineAccess

theorem read_uses_exact_resolved_order (memory : Store) (span : ResolvedSpan) :
    read memory span = span.access.bytes.map (fun byte => memory.read byte.physical) := rfl

theorem resolved_span_preserves_memory_type (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (cpu : CPUState)
    (request : SpanRequest) (access : ResolvedAccess)
    (resolved : resolveAccess profile config cpu pages request.address = .ok access) :
    resolveSpan profile config pages cpu request =
      .resolved { access, memoryType := request.memoryType } :=
  resolveSpan_delegates_success profile config pages cpu request access resolved

theorem shape_mismatch_has_no_write_plan (memory : Store) (span : ResolvedSpan)
    (bytes : List Byte) (mismatch : span.access.bytes.length ≠ bytes.length) :
    planWrites memory span bytes = none := by
  simp [planWrites, mismatch]

theorem one_byte_prefix_applies_only_first (memory : Store)
    (first second : ByteEffect) :
    applyCommittedPrefix memory {
      writes := [first, second], commitPolicy := .committedPrefix, committed := 1
    } = applyEffects memory [first] := by
  rfl

theorem rollback_is_not_blanket_policy (writes : List ByteEffect) :
    EffectPlan.Valid {
      writes, commitPolicy := .instructionSpecific, committed := 0
    } ↔
    writes.Pairwise (fun left right => left.index ≠ right.index) ∧
    writes.Pairwise (fun left right => left.physical ≠ right.physical) := by
  simp [EffectPlan.Valid]

theorem body_applied_preserves_explicit_plan (before : MachineState)
    (afterCPU : CPUState) (plan : EffectPlan) (result : BodyResult)
    (applied : BodyApplied before afterCPU plan result) :
    result.plan = plan ∧ result.state.cpu = afterCPU ∧
      result.state.memory = applyCommittedPrefix before.memory plan := by
  exact ⟨applied.2.2.2.1, applied.2.2.2.2.1, applied.2.2.2.2.2⟩

end AMD64.MachineAccess.Checks
