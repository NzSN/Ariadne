-------------------------- MODULE AMD64Atomic --------------------------
EXTENDS AMD64ConcreteMemory

Arithmetic == INSTANCE AMD64IntegerArithmetic
Core == INSTANCE AMD64IntegerCore

\* Atomicity here means one indivisible architectural RMW event. Ordering
\* between events is supplied separately; the concrete byte store is not SC.

\* @typeAlias: amd64AtomicEvent = {kind: Str, physical: $amd64Address,
\*   width: Int, before: Seq($amd64Byte), after: Seq($amd64Byte),
\*   locked: Bool, atomic: Bool, memoryType: Str};

\* @type: Seq($amd64Byte) => $integerWord;
BytesToWord(bytes) ==
  [bit \in 1..64 |->
    IF bit <= Len(bytes) * 8
    THEN bytes[((bit - 1) \div 8) + 1][((bit - 1) % 8) + 1]
    ELSE FALSE]

\* @type: ($integerWord, Int) => Seq($amd64Byte);
WordBytes(word, width) ==
  CASE width = 8 -> <<[bit \in ByteBits |-> word[bit]]>>
    [] width = 16 -> <<[bit \in ByteBits |-> word[bit]],
                       [bit \in ByteBits |-> word[8 + bit]]>>
    [] width = 32 -> <<[bit \in ByteBits |-> word[bit]],
                       [bit \in ByteBits |-> word[8 + bit]],
                       [bit \in ByteBits |-> word[16 + bit]],
                       [bit \in ByteBits |-> word[24 + bit]]>>
    [] OTHER -> <<[bit \in ByteBits |-> word[bit]],
                   [bit \in ByteBits |-> word[8 + bit]],
                   [bit \in ByteBits |-> word[16 + bit]],
                   [bit \in ByteBits |-> word[24 + bit]],
                   [bit \in ByteBits |-> word[32 + bit]],
                   [bit \in ByteBits |-> word[40 + bit]],
                   [bit \in ByteBits |-> word[48 + bit]],
                   [bit \in ByteBits |-> word[56 + bit]]>>

\* @type: (Set($amd64Address), Seq($amd64Address), Seq($amd64Byte),
\*   $amd64ConcreteMemory, $amd64ConcreteMemory) => Bool;
AtomicWriteOnDomain(domain, addresses, bytes, before, after) ==
  /\ Len(addresses) = Len(bytes)
  /\ ConcreteMemoryWellFormed(before) /\ ConcreteMemoryWellFormed(after)
  /\ \A index \in 1..Len(bytes) :
       ConcreteRead(after, addresses[index]) = bytes[index]
  /\ \A physical \in domain \ {addresses[index] : index \in 1..Len(addresses)} :
       ConcreteRead(after, physical) = ConcreteRead(before, physical)

\* @type: ($integerWord, $integerWord, Int) => $xaddResult;
XAddKernel(destination, source, width) == Arithmetic!XAdd(destination, source, width)

\* @type: ($integerWord, $integerWord, $integerWord, Int) => $compareExchangeResult;
CompareExchangeKernel(accumulator, destination, source, width) ==
  Arithmetic!CompareExchange(accumulator, destination, source, width)

\* @type: ($amd64Address, Int) => Bool;
AlignedForBytes(physical, byteCount) ==
  \A bit \in 1..(CASE byteCount = 16 -> 4 [] byteCount = 8 -> 3 [] OTHER -> 0) :
    ~physical[bit]

\* A memory RMW is not thereby an atomic RMW. XADD and CMPXCHG acquire the
\* indivisible event only from a validated LOCK prefix. Memory XCHG is the
\* exception: the architecture applies locking implicitly, independent of the
\* encoded prefix. `atomic` remains explicit so fixtures cannot accidentally
\* interpret every event produced by this module as serialized.
\* @type: (Str, Bool) => Bool;
AtomicityFor(kind, lockPrefix) == kind = "xchg" \/ lockPrefix

\* @type: (Str, $amd64Address, Int, Seq($amd64Byte), Seq($amd64Byte),
\*   Bool, Str) => $amd64AtomicEvent;
AtomicEvent(kind, physical, width, before, after, lockPrefix, memoryType) ==
  LET locked == AtomicityFor(kind, lockPrefix)
  IN
  [kind |-> kind, physical |-> physical, width |-> width,
   before |-> before, after |-> after, locked |-> locked,
   atomic |-> locked,
   memoryType |-> memoryType]

\* The instruction adapter must ask the ordinary memory layer for a read/write
\* access of exactly the operand width before it may construct an RMW event.
\* `faults` is the ordered memory/protection pipeline's candidate set. Keeping
\* this predicate here prevents a successful arithmetic kernel from bypassing
\* segment, paging, write-permission, or #AC checks.
\* @type: ($amd64Access, Int, Seq($amd64Address), Set($amd64Fault)) => Bool;
AtomicAccessPermitted(access, width, physicalBytes, faults) ==
  /\ access.kind = "readWrite"
  /\ width \in {8, 16, 32, 64, 128}
  /\ Len(physicalBytes) = width \div 8
  /\ faults = {}

\* These form/profile checks precede any data-memory translation. Volume 2
\* Table 8-9 puts invalid opcode above a data-access page fault. The returned
\* string is an adapter decision, not exception delivery.
\* @type: (Str, Int, Bool, Bool, Str) => Str;
AtomicPreAccessLegality(kind, width, cmpxchg8b, cmpxchg16b, mode) ==
  IF kind = "cmpxchg8b" /\ width = 64 /\ ~cmpxchg8b
  THEN "UD-feature"
  ELSE IF kind = "cmpxchg16b" /\ width = 128 /\ ~cmpxchg16b
  THEN "UD-feature"
  ELSE IF kind = "cmpxchg16b" /\ width = 128 /\ mode /= "long64"
  THEN "UD-mode"
  ELSE IF kind \in {"xchg", "xadd", "cmpxchg"} /\
          width \notin {8, 16, 32, 64}
  THEN "invalid-width"
  ELSE IF kind = "cmpxchg8b" /\ width /= 64
  THEN "invalid-width"
  ELSE IF kind = "cmpxchg16b" /\ width /= 128
  THEN "invalid-width"
  ELSE "allowed"

\* CMPXCHG8B/16B compare blocks exactly. On failure the expected block is
\* replaced by the observed memory block and memory remains unchanged.
\* @type: (Seq($amd64Byte), Seq($amd64Byte)) => Bool;
BlockEqual(left, right) == left = right

\* @type: (Seq($amd64Byte), Seq($amd64Byte), Seq($amd64Byte))
\*   => {memory: Seq($amd64Byte), expected: Seq($amd64Byte), zf: Bool};
CompareExchangeBlock(expected, observed, replacement) ==
  IF BlockEqual(expected, observed)
  THEN [memory |-> replacement, expected |-> expected, zf |-> TRUE]
  ELSE [memory |-> observed, expected |-> observed, zf |-> FALSE]

\* @type: (Bool, $amd64Address, Int) => Str;
BlockLegality(cx16, physical, byteCount) ==
  IF byteCount \notin {8, 16} THEN "invalid-length"
  ELSE IF byteCount = 16 /\ ~cx16 THEN "feature-unavailable"
  ELSE IF byteCount = 16 /\ ~AlignedForBytes(physical, 16) THEN "GP0"
  ELSE "allowed"

==========================================================================
