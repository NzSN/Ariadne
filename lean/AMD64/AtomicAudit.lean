import AMD64.Atomic
import AMD64.Exceptions

/-! Axiom surface for the atomic memory lane. -/

#print axioms AMD64.Atomic.xadd_flags_from_add
#print axioms AMD64.Atomic.cmpxchg_flags_from_sub
#print axioms AMD64.Atomic.xchg_memory_is_implicitly_atomic
#print axioms AMD64.Atomic.xadd_without_lock_is_not_atomic
#print axioms AMD64.Atomic.cmpxchg_without_lock_is_not_atomic
#print axioms AMD64.Atomic.operation_xchg_implicitly_locked
#print axioms AMD64.Atomic.operation_xadd_unlocked_without_prefix
#print axioms AMD64.Atomic.operation_cmpxchg_unlocked_without_prefix
#print axioms AMD64.Atomic.unavailable_cmpxchg16b_fails_before_access
#print axioms AMD64.Exceptions.alignment_fault_pushes_zero_error_code
#print axioms AMD64.Exceptions.ordinary_trap_has_no_iteration_progress
