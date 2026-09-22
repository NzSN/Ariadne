import AMD64.LWPLayout

set_option maxRecDepth 10000

namespace AMD64.LWPLayout.Checks

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory

def byte (value : Nat) : Byte := fun bit => value.testBit bit.val
def zeros : List Byte := List.replicate 128 (byte 0)
def bytes : List Byte :=
  (((((zeros.set 0 (byte 3)).set 5 (byte 4)).set 16 (byte 33)).set 32 (byte 65)).set
    64 (byte 32)).set 91 (byte 2)

def profile : Profile := {
  controlBlockQuadwords := 16
  eventSize := 32
  maxEvents := 5
  eventOffset := 88
  minimumBufferUnits := 1
  availableFlag := fun bit => bit.val < 7
  minimumInterval := fun event => if event = 1 then 0 else 10
}

example : profile.validB = true := by decide
example : readLE bytes 4 4 = 1024 := by decide
example : readLE bytes 16 4 = 33 := by decide

example : (decode profile bytes).map (·.bufferSize) = some 1024 := by decide
example : (decode profile bytes >>= normalize profile).map
    (·.bufferHeadOffset) = some 32 := by decide
example : (decode profile bytes >>= normalize profile).map
    (·.threshold) = some 64 := by decide
example : (decode profile bytes >>= normalize profile).map
    (·.tailProtocolValid) = some true := by decide
example : (decode profile bytes >>= normalize profile).map
    (fun normalized => normalized.events.map (·.interval)) =
      some [0, 10, 10, 10, 10] := by decide

def emptyCapture : MemoryState := { cells := [], captured := [] }
def oneAddress : List PhysicalAddress := [fun _ => false]
example : decodeCaptured profile emptyCapture oneAddress = .unavailable := by rfl

end AMD64.LWPLayout.Checks
