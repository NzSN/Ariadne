-------------------------- MODULE AMD64Control --------------------------
EXTENDS Integers, FiniteSets, Sequences

Integer == INSTANCE AMD64IntegerCore
Memory == INSTANCE AMD64Memory

\* Source-grounded near-control foundation. It computes condition selection,
\* relative/direct targets, target-width truncation, next-RIP retirement and
\* stack requests. Memory resolution/commit and exception delivery remain
\* explicit relations; no target or stack result is supplied by an oracle.
\* Authority: AMD Volume 3 revision 3.38, pages 178-180, 245-251, 269-270,
\* and 353-359, plus Volume 1 control transfers and Volume 2 protection.

Conditions == {"o", "no", "b", "ae", "e", "ne", "be", "a",
  "s", "ns", "p", "np", "l", "ge", "le", "g"}
LoopConditions == {"loop", "e", "ne"}
ControlModes == {"real", "virtual8086", "protected", "compatibility", "long64"}

\* @typeAlias: amd64ControlState = {rip: $amd64Address, rcx: $amd64Address,
\*   rsp: $amd64Address, flags: $integerFlags, mode: Str,
\*   ssDefaultBig: Bool, csLimit: $amd64Address};
\* @typeAlias: amd64Relative = {value: $amd64Address, encodedWidth: Int,
\*   semanticWidth: Int, extension: Str};
\* @typeAlias: amd64Fallthrough = {instructionLength: Int,
\*   nextRIP: $amd64Address};
\* @typeAlias: amd64BranchPlan = {taken: Bool, fallthrough: $amd64Address,
\*   target: $amd64Address, nextRIP: $amd64Address};
\* @typeAlias: amd64StackRequest = {rawEffective: $amd64Address,
\*   addressSize: Int, segment: Str, access: Str, byteCount: Int};
\* @typeAlias: amd64StackPushPlan = {width: Int, oldRSP: $amd64Address,
\*   newRSP: $amd64Address, value: $amd64Address,
\*   request: $amd64StackRequest};
\* @typeAlias: amd64StackPopPlan = {width: Int, oldRSP: $amd64Address,
\*   newRSP: $amd64Address, request: $amd64StackRequest};
\* @typeAlias: amd64TentativeStack = {entry: $amd64ControlState,
\*   tentative: $amd64ControlState, visibility: Str};

AddressBits == 1..64
ZeroAddress == [bit \in AddressBits |-> FALSE]
OneAddress == [bit \in AddressBits |-> bit = 1]

\* @type: ($amd64Address, Int) => $amd64Address;
TruncateIP(address, width) ==
  [bit \in AddressBits |-> IF bit <= width THEN address[bit] ELSE FALSE]

\* The decoder supplies the following-instruction address and byte length.
\* This certificate checks it against current RIP rather than trusting it.
\* @type: ($amd64ControlState, $amd64Fallthrough, Int, $amd64Address,
\*   $amd64Carry) => Bool;
FallthroughValid(before, evidence, ipWidth, fullSum, carry) ==
  /\ evidence.instructionLength \in 1..15
  /\ ipWidth \in {16, 32, 64}
  /\ Memory!WordAddWithCarry(before.rip,
       [bit \in AddressBits |->
         IF bit <= 4 THEN (evidence.instructionLength \div (2 ^ (bit - 1))) % 2 = 1
         ELSE FALSE], fullSum, carry)
  /\ evidence.nextRIP = TruncateIP(fullSum, ipWidth)

\* @type: ($amd64Relative, Int) => Bool;
RelativeReady(displacement, operandWidth) ==
  /\ displacement.encodedWidth \in {8, 16, 32}
  /\ displacement.semanticWidth = operandWidth
  /\ displacement.extension = "sign"
  /\ operandWidth \in {16, 32, 64}

\* @type: ($amd64Address, $amd64Relative, Int, $amd64Address,
\*   $amd64Carry, $amd64Address) => Bool;
RelativeTarget(fallthrough, displacement, operandWidth, fullSum, carry, target) ==
  /\ RelativeReady(displacement, operandWidth)
  /\ Memory!WordAddWithCarry(fallthrough, displacement.value, fullSum, carry)
  /\ target = TruncateIP(fullSum, operandWidth)

\* @type: (Str, $integerFlags) => Bool;
ConditionHolds(condition, flags) == Integer!ConditionHolds(condition, flags)

\* @type: (Str, $integerFlags, $amd64Address, $amd64Address,
\*   $amd64BranchPlan) => Bool;
JccPlan(condition, flags, fallthrough, target, plan) ==
  /\ condition \in Conditions
  /\ plan.taken = ConditionHolds(condition, flags)
  /\ plan.fallthrough = fallthrough
  /\ plan.target = target
  /\ plan.nextRIP = IF plan.taken THEN target ELSE fallthrough

\* @type: ($amd64Address, Int) => Bool;
CountIsZero(count, addressSize) ==
  /\ addressSize \in {16, 32, 64}
  /\ \A bit \in 1..addressSize : ~count[bit]

\* Exact address-sized count decrement with upper physical GPR bits framed.
\* @type: ($amd64Address, Str, Int, $amd64Address, $amd64Carry,
\*   $amd64Address) => Bool;
DecrementCount(before, mode, addressSize, lowResult, carry, after) ==
  LET lowBefore == TruncateIP(before, addressSize)
      negativeOne == [bit \in AddressBits |-> bit <= addressSize]
  IN /\ addressSize \in {16, 32, 64}
     /\ Memory!WordAddWithCarry(lowBefore, negativeOne, lowResult, carry)
     /\ after = [bit \in AddressBits |->
          IF bit <= addressSize THEN lowResult[bit]
          ELSE IF mode = "long64" /\ addressSize = 32 THEN FALSE
          ELSE before[bit]]

\* @type: ($amd64Address, Int, $amd64Address, $amd64Address,
\*   $amd64BranchPlan) => Bool;
JrCXZPlan(count, addressSize, fallthrough, target, plan) ==
  /\ plan.taken = CountIsZero(count, addressSize)
  /\ plan.fallthrough = fallthrough /\ plan.target = target
  /\ plan.nextRIP = IF plan.taken THEN target ELSE fallthrough

\* `newCount` must be the actual address-sized decrement result produced by
\* the state layer. This predicate selects LOOP/LOOPcc only after that commit.
\* @type: (Str, $amd64Address, Int, $integerFlags) => Bool;
LoopTaken(loopCondition, newCount, addressSize, flags) ==
  /\ loopCondition \in LoopConditions
  /\ ~CountIsZero(newCount, addressSize)
  /\ CASE loopCondition = "loop" -> TRUE
       [] loopCondition = "e" -> flags.zf
       [] OTHER -> ~flags.zf

\* @type: (Str, $amd64Address, Int, $integerFlags, $amd64Address,
\*   $amd64Address, $amd64BranchPlan) => Bool;
LoopPlan(loopCondition, newCount, addressSize, flags, fallthrough, target, plan) ==
  /\ plan.taken = LoopTaken(loopCondition, newCount, addressSize, flags)
  /\ plan.fallthrough = fallthrough /\ plan.target = target
  /\ plan.nextRIP = IF plan.taken THEN target ELSE fallthrough

\* @type: (Str, $amd64Address, Int, $amd64Address) => Bool;
TargetWithinCurrentCode(mode, target, virtualBits, csLimit) ==
  IF mode = "long64" THEN Memory!Canonical(target, virtualBits)
  ELSE Memory!UnsignedLE(target, csLimit)

\* @type: ($amd64ControlState, $amd64Address, $amd64ControlState) => Bool;
RetireTo(before, target, after) ==
  /\ after = [before EXCEPT !.rip = target]
  /\ after.flags = before.flags
  /\ after.rcx = before.rcx
  /\ after.rsp = before.rsp

\* @type: $amd64ControlState => Int;
StackAddressSize(state) ==
  IF state.mode = "long64" THEN 64 ELSE IF state.ssDefaultBig THEN 32 ELSE 16

\* @type: ($amd64Address, $amd64Address, $amd64Carry) => Bool;
NegateAddress(value, negated, carry) ==
  Memory!WordAddWithCarry([bit \in AddressBits |-> ~value[bit]],
    OneAddress, negated, carry)

\* CALL pushes the following-instruction IP at operand width. The returned
\* request must be resolved and committed by AMD64Memory before retirement.
\* @type: ($amd64ControlState, $amd64Address, Int, $amd64Address,
\*   $amd64Carry, $amd64Carry, $amd64StackPushPlan) => Bool;
NearCallPushPlan(state, fallthrough, operandWidth, negativeSize,
                 negateCarry, subtractCarry, plan) ==
  LET byteCount == operandWidth \div 8
      addressSize == StackAddressSize(state)
      amount == [bit \in AddressBits |->
        IF bit <= 4 THEN (byteCount \div (2 ^ (bit - 1))) % 2 = 1 ELSE FALSE]
  IN /\ operandWidth \in {16, 32, 64}
     /\ IF state.mode = "long64" THEN operandWidth \in {16, 64}
          ELSE operandWidth \in {16, 32}
     /\ NegateAddress(amount, negativeSize, negateCarry)
     /\ \E fullSum \in [AddressBits -> BOOLEAN] :
          /\ Memory!WordAddWithCarry(state.rsp, negativeSize, fullSum, subtractCarry)
          /\ plan.newRSP = TruncateIP(fullSum, addressSize)
     /\ plan.width = operandWidth /\ plan.oldRSP = state.rsp
     /\ plan.value = TruncateIP(fallthrough, operandWidth)
     /\ plan.request = [rawEffective |-> plan.newRSP,
          addressSize |-> addressSize, segment |-> "ss",
          access |-> "write", byteCount |-> byteCount]

\* Generic architectural stack plans used by PUSH, POP, PUSHF/POPF,
\* ENTER/LEAVE and the all-register forms. Operand size controls transfer
\* width; SS.D/B (or long64) independently controls the stack-pointer view.
\* @type: (Str, Int) => Bool;
StackOperandReady(mode, operandWidth) ==
  /\ operandWidth \in {16, 32, 64}
  /\ IF mode = "long64" THEN operandWidth \in {16, 64}
       ELSE operandWidth \in {16, 32}

\* @type: ($amd64ControlState, $amd64Address, Int, $amd64Address,
\*   $amd64Carry, $amd64Carry, $amd64StackPushPlan) => Bool;
StackPushPlan(state, value, operandWidth, negativeSize,
              negateCarry, subtractCarry, plan) ==
  /\ StackOperandReady(state.mode, operandWidth)
  /\ NearCallPushPlan(state, value, operandWidth, negativeSize,
       negateCarry, subtractCarry, plan)

\* @type: ($amd64ControlState, Int, $amd64Address, $amd64Carry,
\*   $amd64StackPopPlan) => Bool;
StackPopPlan(state, operandWidth, fullSum, carry, plan) ==
  LET byteCount == operandWidth \div 8
      addressSize == StackAddressSize(state)
      amount == [bit \in AddressBits |->
        IF bit <= 4 THEN (byteCount \div (2 ^ (bit - 1))) % 2 = 1 ELSE FALSE]
  IN /\ StackOperandReady(state.mode, operandWidth)
     /\ Memory!WordAddWithCarry(state.rsp, amount, fullSum, carry)
     /\ plan.width = operandWidth /\ plan.oldRSP = state.rsp
     /\ plan.newRSP = TruncateIP(fullSum, addressSize)
     /\ plan.request = [rawEffective |-> state.rsp,
          addressSize |-> addressSize, segment |-> "ss",
          access |-> "read", byteCount |-> byteCount]

\* The pseudocode order can expose a tentative stack update to later checks,
\* but does not by itself prove that a restartable fault commits that update.
\* The architectural fault projection therefore retains the entry state.
\* @type: ($amd64ControlState, $amd64ControlState,
\*   $amd64TentativeStack) => Bool;
TentativeStackFault(entry, tentative, effect) ==
  /\ effect.entry = entry
  /\ effect.tentative = tentative
  /\ effect.visibility = "uncommitted-until-delivery-contract"

\* @type: Seq(Str);
PushaOrder == <<"rax", "rcx", "rdx", "rbx", "original-rsp", "rbp", "rsi", "rdi">>
\* @type: Seq(Str);
PopaOrder == <<"rdi", "rsi", "rbp", "discard-rsp", "rbx", "rdx", "rcx", "rax">>

\* @type: (Str, Int) => Bool;
AllRegisterStackReady(mode, operandWidth) ==
  /\ mode \in {"real", "virtual8086", "protected", "compatibility"}
  /\ operandWidth \in {16, 32}

\* Protected-mode POPF writes IOPL only at CPL 0 and writes IF only when
\* CPL <= the old IOPL. Real mode permits both; virtual-8086 VME handling is
\* a separate configuration-dependent transition.
\* @type: (Str, Int, Int, Str) => Bool;
FlagWritePermitted(mode, cpl, oldIOPL, flag) ==
  CASE flag = "iopl" -> mode = "real" \/ (mode \in {"protected", "compatibility", "long64"} /\ cpl = 0)
    [] flag = "if" -> mode \in {"real", "virtual8086"} \/
         (mode \in {"protected", "compatibility", "long64"} /\ cpl <= oldIOPL)
    [] OTHER -> flag \notin {"vif", "vip", "vm", "rf"}

\* RFLAGS uses zero-based bit names in the manual but AMD64Address uses the
\* one-based map domain 1..64. Map index 17 is RF (manual bit 16), and index
\* 18 is VM (manual bit 17).
\* @type: (Str, $amd64Address) => $amd64Address;
PushFlagImage(mode, flags) ==
  [bit \in AddressBits |->
    IF bit = 17 THEN FALSE
    ELSE IF bit = 18 /\ mode \in {"real", "virtual8086"} THEN FALSE
    ELSE flags[bit]]

ReservedFlagIndices == {2, 4, 6, 16} \cup 23..64

\* @type: (Str, Int, Int, Int) => Bool;
PopFlagBitWritable(mode, cpl, oldIOPL, bit) ==
  /\ bit \notin ReservedFlagIndices
  /\ bit \notin {17, 18, 20, 21}
  /\ IF bit \in {13, 14} THEN FlagWritePermitted(mode, cpl, oldIOPL, "iopl")
       ELSE IF bit = 10 THEN FlagWritePermitted(mode, cpl, oldIOPL, "if")
       ELSE TRUE

\* @type: ($amd64Address, $amd64Address, Int, Str, Int, Int) => $amd64Address;
PopFlagImage(before, popped, operandWidth, mode, cpl, oldIOPL) ==
  [bit \in AddressBits |->
    IF bit = 17 THEN FALSE
    ELSE IF bit <= operandWidth /\ PopFlagBitWritable(mode, cpl, oldIOPL, bit)
      THEN popped[bit]
    ELSE before[bit]]

UndefinedOpcodes == {"ud0", "ud1", "ud2"}

\* @type: (Str, Str) => Bool;
UndefinedOpcodeOutcome(opcode, outcome) ==
  /\ opcode \in UndefinedOpcodes
  /\ outcome = "invalid-opcode-fault"

=============================================================================
