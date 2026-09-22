import Std

/-!
Register-view foundation for the accepted AMD64 expansion.

Authority: AMD Volume 1, 24592 revision 3.25, sections 3.1.2 and 3.4.5.
All storage-write operations here concern 64-bit mode. Encoding legality is
not inferred from the existence of a register view.

`Source` is a reviewed transcription of `Specs/AMD64RegisterViews.tla`, using
one-based finite indices. Correspondence theorems below connect that Lean
transcription to zero-based typed operations, NOT directly to a parsed TLA+
module or all AMD64 instructions. The source lock detects transcription drift.
-/

namespace AMD64

abbrev Word := Fin 64 → Bool

inductive GPRView where
  | low8 | high8 | low16 | low32 | full64
  deriving DecidableEq, Repr

def GPRView.offset : GPRView → Nat
  | .high8 => 8
  | _ => 0

def GPRView.width : GPRView → Nat
  | .low8 | .high8 => 8
  | .low16 => 16
  | .low32 => 32
  | .full64 => 64

theorem GPRView.bounds (view : GPRView) : view.offset + view.width ≤ 64 := by
  cases view <;> decide

/-- Extract a view into the low bits of a 64-bit container. -/
def readView (word : Word) (view : GPRView) : Word := fun bit =>
  if h : bit.val < view.width then
    word ⟨bit.val + view.offset, by have := view.bounds; omega⟩
  else false

/-- Physical GPR storage update in 64-bit mode, independent of encoding legality. -/
def writeView64 (before value : Word) (view : GPRView) : Word := fun bit =>
  if h : view.offset ≤ bit.val ∧ bit.val < view.offset + view.width then
    value ⟨bit.val - view.offset, by omega⟩
  else if view = .low32 then false else before bit

/-- Every in-view payload bit is recovered, for all words (not sampled vectors). -/
theorem read_after_write (before value : Word) (view : GPRView) :
    readView (writeView64 before value view) view =
      fun bit => if bit.val < view.width then value bit else false := by
  funext bit
  simp only [readView]
  split
  next h =>
    have hin : view.offset ≤ bit.val + view.offset ∧
        bit.val + view.offset < view.offset + view.width := by omega
    simp [writeView64, hin]
  next h => rfl

/-- Non-dword writes preserve every bit outside the selected view. -/
theorem preserves_outside (before value : Word) (view : GPRView) (bit : Fin 64)
    (hview : view ≠ .low32)
    (outside : ¬ (view.offset ≤ bit.val ∧ bit.val < view.offset + view.width)) :
    writeView64 before value view bit = before bit := by
  simp [writeView64, outside, hview]

theorem dword_zero_extends (before value : Word) (bit : Fin 64)
    (upper : 32 ≤ bit.val) :
    writeView64 before value .low32 bit = false := by
  simp [writeView64, GPRView.offset, GPRView.width, show ¬ bit.val < 32 by omega]

theorem qword_replaces (before value : Word) :
    writeView64 before value .full64 = value := by
  funext bit
  simp [writeView64, GPRView.offset, GPRView.width, bit.isLt]

namespace Source

/-- Structural counterpart of the valid domain `1..64` in WordWellFormed. -/
abbrev Index := { n : Nat // 1 ≤ n ∧ n ≤ 64 }
abbrev Word := Index → Bool

def toIndex (bit : Fin 64) : Index := ⟨bit.val + 1, by omega⟩
def fromIndex (bit : Index) : Fin 64 := ⟨bit.val - 1, by have := bit.property; omega⟩

def encode (word : AMD64.Word) : Word := fun bit => word (fromIndex bit)
def decode (word : Word) : AMD64.Word := fun bit => word (toIndex bit)

theorem decode_encode (word : AMD64.Word) : decode (encode word) = word := by
  funext bit
  simp [decode, encode, toIndex, fromIndex]

theorem encode_decode (word : Word) : encode (decode word) = word := by
  funext bit
  simp only [encode, decode]
  congr 1
  apply Subtype.ext
  simp only [toIndex, fromIndex]
  have := bit.property
  omega

/-- Direct one-based transcription of the TLA+ ReadView expression. -/
def readView (word : Word) (view : GPRView) : Word := fun bit =>
  if h : bit.val ≤ view.width then
    word ⟨bit.val + view.offset, by have := bit.property; have := view.bounds; omega⟩
  else false

/-- Direct one-based transcription of the TLA+ WriteView64 expression. -/
def writeView64 (before value : Word) (view : GPRView) : Word := fun bit =>
  if h : view.offset < bit.val ∧ bit.val ≤ view.offset + view.width then
    value ⟨bit.val - view.offset, by have := bit.property; omega⟩
  else if view = .low32 then false else before bit

theorem read_correspondence (word : AMD64.Word) (view : GPRView) :
    encode (AMD64.readView word view) = readView (encode word) view := by
  funext bit
  have hb := bit.property
  simp only [encode, AMD64.readView, readView]
  by_cases h : bit.val ≤ view.width
  · have ht : (fromIndex bit).val < view.width := by simp only [fromIndex]; omega
    simp only [dif_pos h, dif_pos ht]
    congr 1
    apply Fin.ext
    simp only [fromIndex]
    omega
  · have ht : ¬ (fromIndex bit).val < view.width := by simp only [fromIndex]; omega
    simp only [dif_neg h, dif_neg ht]

theorem write_correspondence (before value : AMD64.Word) (view : GPRView) :
    encode (AMD64.writeView64 before value view) =
      writeView64 (encode before) (encode value) view := by
  funext bit
  have hb := bit.property
  simp only [encode, AMD64.writeView64, writeView64]
  by_cases h : view.offset < bit.val ∧ bit.val ≤ view.offset + view.width
  · have ht : view.offset ≤ (fromIndex bit).val ∧
        (fromIndex bit).val < view.offset + view.width := by simp only [fromIndex]; omega
    simp only [dif_pos h, dif_pos ht]
    congr 1
    apply Fin.ext
    simp only [fromIndex]
    omega
  · have ht : ¬ (view.offset ≤ (fromIndex bit).val ∧
        (fromIndex bit).val < view.offset + view.width) := by simp only [fromIndex]; omega
    simp only [dif_neg h, dif_neg ht]

end Source
end AMD64
