import AMD64.IntegerCommonExecution
import AMD64.IntegerExecutionChecks

namespace AMD64.IntegerCommonExecution.Checks

open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.IntegerCommonExecution

def op (ref : OperandRef) (access : AccessIntent) (order : Nat) : ExecutableOperand := {
  ref, sourceText := "fixture", accessIntent := access, evaluationOrder := order,
  registerExtension := match ref with | .gpr r => decide (8 ≤ r.index.val) | _ => false,
  byteCode4To7 := match ref with
    | .gpr r => decide (r.view = .high8 ∨ 4 ≤ r.index.val % 8) | _ => false }

def rax : GPRRef := ⟨0,.full64⟩
def rbx : GPRRef := ⟨3,.full64⟩
def eax : GPRRef := ⟨0,.low32⟩

def regReg (id : String) (destination source : GPRRef) : ExecutableInstruction := {
  formId := id, operandSize := destination.width, addressSize := 64,
  prefixes := if destination.width = 64 then [.rexW] else [],
  operands := [op (.gpr destination) .readWrite 1, op (.gpr source) .read 2],
  implicitResources := [], encodingFamily := .legacy }

def imm32Sign : ImmediateRef := {
  encoded := wordOfNat 0xffffffff, encodedWidth := 32,
  semanticWidth := 64, extension := .sign }
def addRaxImm32 : ExecutableInstruction := {
  formId := "AMD64-F-0033", operandSize := 64, addressSize := 64,
  prefixes := [.rexW], operands := [op (.gpr rax) .readWrite 1,
    op (.immediate imm32Sign) .read 2], implicitResources := [],
  encodingFamily := .legacy }

def memoryAddress : AddressExpr := {
  base := none, index := none, scale := 1, displacement := 0,
  displacementWidth := 0, segment := none, addressSize := .bits64,
  ripRelative := false, baseExtended := false, indexExtended := false }
def movFromMemory : ExecutableInstruction := {
  formId := "AMD64-F-0485", operandSize := 64, addressSize := 64,
  prefixes := [.rexW], operands := [op (.gpr rax) .write 1,
    op (.memory memoryAddress 64) .read 2], implicitResources := [],
  encodingFamily := .legacy }

example : (BindingFor "AMD64-F-0044").map (·.operation) = some .add := by decide
example : BindingFor "AMD64-F-0322" = none := by decide
example : milestoneFormIds.length = 76 := by decide
example : MilestoneBindingFor "AMD64-F-0044" = BindingFor "AMD64-F-0044" := by decide
example : MilestoneBindingFor "AMD64-F-0033" = none := by decide

example : payloadValid ⟨.add,64,.registerOrMemory,0,.none,false,.readWrite⟩
    (regReg "AMD64-F-0044" rax rbx) = true := by decide
example : payloadValid ⟨.add,64,.immediate,32,.sign,false,.readWrite⟩
    addRaxImm32 = true := by decide
example : imm32Sign.value = fun bit => if bit.val < 32 then (wordOfNat 0xffffffff) bit else true := by
  rfl
example : payloadValid ⟨.mov,64,.registerOrMemory,0,.none,false,.write⟩
    movFromMemory = true := by decide
example : hasMemory movFromMemory = true := by decide

def sameRegisterAdd := regReg "AMD64-F-0044" rax rax
def before := AMD64.IntegerExecution.Checks.stateWithRax (wordOfNat 3)
def payloadAlias : BinaryPayload := ⟨rax,.gpr rax⟩
def aliasAfter := commitExactBinary .add payloadAlias before
example : ExecuteConditional .add sameRegisterAdd before (.bodyApplied aliasAfter) := by
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, sameRegisterAdd,
    regReg, op, BodyStep, aliasAfter, payloadAlias, GPRRef.width]

example : payloadValid ⟨.add,64,.registerOrMemory,0,.none,false,.readWrite⟩
    { sameRegisterAdd with prefixes := [.lock] } = true := by decide

end AMD64.IntegerCommonExecution.Checks
