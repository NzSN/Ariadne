---------------------- MODULE AMD64ConcreteMemory ----------------------
EXTENDS AMD64Memory

\* Concrete architectural bytes versus captured analysis knowledge.
\*
\* A concrete store denotes one byte at every full-width physical address in
\* its modeled domain. The representation is a default byte plus finite,
\* unique overrides, so TLC fixtures never enumerate 2^64 addresses. The
\* default is part of a concrete architectural state; it is never inferred
\* from an absent snapshot byte.
\*
\* Captured memory remains the finite cells/domain representation from
\* AMD64Memory. ConcreteRefinesCaptured constrains exactly captured addresses;
\* an address outside that domain imposes no value constraint.

\* @typeAlias: amd64ConcreteMemory = {physicalBits: Int,
\*   defaultByte: $amd64Byte, overrides: Set($amd64ByteCell)};

\* @type: ($amd64Address, Int) => Bool;
PhysicalAddressValid(address, physicalBits) ==
  /\ physicalBits \in 1..64
  /\ \A bit \in (physicalBits + 1)..64 : ~address[bit]

\* @type: $amd64ConcreteMemory => Bool;
ConcreteMemoryWellFormed(memory) ==
  /\ memory.physicalBits \in 1..64
  /\ ByteWellFormed(memory.defaultByte)
  /\ MemoryWellFormed(memory.overrides)
  /\ \A cell \in memory.overrides :
       /\ PhysicalAddressValid(cell.physical, memory.physicalBits)
       /\ cell.value /= memory.defaultByte

\* The CHOOSE branch is unique under ConcreteMemoryWellFormed. It selects from
\* the explicit finite override set, not from an unconstrained environment.
\* @type: ($amd64ConcreteMemory, $amd64Address) => $amd64Byte;
ConcreteRead(memory, physical) ==
  IF \E cell \in memory.overrides : cell.physical = physical
  THEN (CHOOSE cell \in memory.overrides : cell.physical = physical).value
  ELSE memory.defaultByte

\* @type: ($amd64ConcreteMemory, $amd64Address, $amd64Byte) => $amd64ConcreteMemory;
ConcreteWrite(memory, physical, value) ==
  [physicalBits |-> memory.physicalBits,
   defaultByte |-> memory.defaultByte,
   overrides |-> {cell \in memory.overrides : cell.physical /= physical} \cup
     (IF value = memory.defaultByte THEN {}
      ELSE {[physical |-> physical, value |-> value]})]

\* @type: ($amd64ConcreteMemory, $amd64Address) => Bool;
ConcreteWriteAllowed(memory, physical) ==
  ConcreteMemoryWellFormed(memory) /\
  PhysicalAddressValid(physical, memory.physicalBits)

\* @type: ($amd64ConcreteMemory, Set($amd64ByteCell), Set($amd64Address)) => Bool;
ConcreteRefinesCaptured(concrete, capturedCells, capturedDomain) ==
  /\ ConcreteMemoryWellFormed(concrete)
  /\ CapturedMemoryWellFormed(capturedCells, capturedDomain)
  /\ \A physical \in capturedDomain :
       PhysicalAddressValid(physical, concrete.physicalBits)
  /\ \A cell \in capturedCells :
       ConcreteRead(concrete, cell.physical) = cell.value

\* @type: ($amd64ConcreteMemory, $amd64Address, $amd64Byte,
\*   Set($amd64ByteCell), Set($amd64Address),
\*   Set($amd64ByteCell), Set($amd64Address)) => Bool;
SnapshotWrite(concrete, physical, value, beforeCells, beforeDomain,
              afterCells, afterDomain) ==
  /\ afterCells = {cell \in beforeCells : cell.physical /= physical} \cup
       {[physical |-> physical, value |-> value]}
  /\ afterDomain = beforeDomain \cup {physical}
  /\ ConcreteRefinesCaptured(ConcreteWrite(concrete, physical, value),
                            afterCells, afterDomain)

\* Small explicit offset words are used only to validate at most eight bytes
\* of page-table-entry evidence. Architectural addresses remain 64-bit maps.
\* @type: Int => $amd64Address;
SmallOffset(value) ==
  CASE value = 0 -> ZeroAddress
    [] value = 1 -> [bit \in AddressBits |-> bit = 1]
    [] value = 2 -> [bit \in AddressBits |-> bit = 2]
    [] value = 3 -> [bit \in AddressBits |-> bit \in {1, 2}]
    [] value = 4 -> [bit \in AddressBits |-> bit = 3]
    [] value = 5 -> [bit \in AddressBits |-> bit \in {1, 3}]
    [] value = 6 -> [bit \in AddressBits |-> bit \in {2, 3}]
    [] value = 7 -> [bit \in AddressBits |-> bit \in {1, 2, 3}]
    [] OTHER -> ZeroAddress

\* @type: ($amd64ConcreteMemory, $amd64Address, Seq($amd64Byte),
\*   Seq($amd64Address), Seq($amd64Carry)) => Bool;
ConcreteBytesAt(memory, start, bytes, addresses, carries) ==
  /\ Len(bytes) \in 1..8
  /\ Len(addresses) = Len(bytes)
  /\ Len(carries) = Len(bytes)
  /\ \A index \in 1..Len(bytes) :
       /\ WordAddWithCarry(start, SmallOffset(index - 1),
                           addresses[index], carries[index])
       /\ PhysicalAddressValid(addresses[index], memory.physicalBits)
       /\ ConcreteRead(memory, addresses[index]) = bytes[index]

============================================================================
