import AMD64.Memory
import Std

namespace AMD64.MemoryTypes

open AMD64.MemoryModel

inductive MemoryType where
  | uc | ucMinus | cd | wc | wcPlus | wp | wt | wb
  deriving DecidableEq, Repr

inductive Resolution where
  | resolved (memoryType : MemoryType)
  | undefinedCombination
  | unsupportedProfile
  | unknownConfiguration
  deriving DecidableEq, Repr

def combinePATMTRR (pat mtrr : MemoryType) : Resolution :=
  if pat = .uc ∨ mtrr = .uc then .resolved .uc
  else if pat = .ucMinus then
    if mtrr = .wc then .resolved .wc else .resolved .uc
  else if pat = mtrr then .resolved pat
  else if mtrr = .wb then .resolved pat
  else if pat = .wb then .resolved mtrr
  else .unsupportedProfile

def effective (cacheDisabled mtrrsEnabled : Bool)
    (pat mtrr : MemoryType) : Resolution :=
  if cacheDisabled then .resolved .cd
  else if !mtrrsEnabled then .resolved .uc
  else combinePATMTRR pat mtrr

structure MTRRRegion where
  base : PhysicalAddress
  limit : PhysicalAddress
  memoryType : MemoryType

structure Config where
  cacheDisabled : Bool
  mtrrsEnabled : Bool
  defaultMTRR : MemoryType
  mtrrRegions : List MTRRRegion
  patFields : Fin 8 -> MemoryType

def patIndex (patBit pcd pwt : Bool) : Fin 8 :=
  ⟨(if patBit then 4 else 0) + (if pcd then 2 else 0) +
    (if pwt then 1 else 0), by
      cases patBit <;> cases pcd <;> cases pwt <;> decide⟩

def MTRRRegion.matches (region : MTRRRegion) (physical : PhysicalAddress) : Bool :=
  unsignedLE region.base physical && unsignedLE physical region.limit

def mtrrTypeAt (config : Config) (physical : PhysicalAddress) : Resolution :=
  if !config.mtrrsEnabled then .resolved .uc
  else match config.mtrrRegions.filter (·.matches physical) with
    | [] => .resolved config.defaultMTRR
    | [region] => .resolved region.memoryType
    | _ => .unsupportedProfile

def resolve (config : Config) (physical : PhysicalAddress)
    (patBit pcd pwt : Bool) : Resolution :=
  if config.cacheDisabled then .resolved .cd
  else match mtrrTypeAt config physical with
    | .resolved mtrr => combinePATMTRR (config.patFields (patIndex patBit pcd pwt)) mtrr
    | other => other

theorem uc_dominates_left (mtrr : MemoryType) :
    combinePATMTRR .uc mtrr = .resolved .uc := by
  simp [combinePATMTRR]

theorem uc_dominates_right (pat : MemoryType) :
    combinePATMTRR pat .uc = .resolved .uc := by
  simp [combinePATMTRR]

theorem wb_mtrr_accepts_pat (pat : MemoryType) (notUC : pat ≠ .uc) :
    combinePATMTRR pat .wb =
      if pat = .ucMinus then .resolved .uc else .resolved pat := by
  cases pat <;> simp_all [combinePATMTRR]

end AMD64.MemoryTypes
