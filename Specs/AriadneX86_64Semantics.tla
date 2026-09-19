-------------------- MODULE AriadneX86_64Semantics --------------------
EXTENDS AriadneMachineCommon

\* Executable, register-only x86-64 semantics, not a byte decoder or full ISA.
\* See docs/x86-64-semantics.md for the supported forms and environment contract.
\* Execute computes outcomes from operands. No transition table is an input.
\* RIP is represented by the instruction site / outcome destination, not a GPR.
\* All instructions are validly decoded in 64-bit mode, without LOCK/REP/APX
\* variants. Fetch, canonical-target checks, interrupts and exception delivery
\* are outside this projected machine. UD2 records the pre-delivery #UD fault.

\* New aliases are local to this extension; the existing MBT-pinned type
\* catalogue and propagation modules remain unchanged.
\* @typeAlias: x86Word = Int -> Bool;
\* @typeAlias: x86Opcode = Str;
\* @typeAlias: x86OperandKind = Str;
\* @typeAlias: x86Condition = Str;
\* @typeAlias: x86State = {gpr: $location -> $x86Word, flags: $location -> Bool};
\* @typeAlias: x86Instruction = {op: $x86Opcode, width: Int, dst: $location,
\*   source: $x86OperandKind, sourceReg: $location, immediate: $x86Word,
\*   next: $address, target: $address, condition: $x86Condition};
\* @typeAlias: x86Outcome = {state: $x86State, dst: $address,
\*   kind: $edgeKind, status: $machineStatus};
X86Types == TRUE

GPRs == {"rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
         "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"}
Flags == {"cf", "pf", "af", "zf", "sf", "of"}
X86Locations == GPRs \cup Flags
Conditions == {"o", "no", "b", "ae", "e", "ne", "be", "a",
               "s", "ns", "p", "np", "l", "ge", "le", "g"}
ArithmeticOps == {"add", "sub", "cmp"}
LogicalOps == {"and", "or", "xor", "test"}
DataOps == {"mov"} \cup ArithmeticOps \cup LogicalOps

\* Bit 1 is the least significant bit. Never evaluate 2^32 or 2^64 in TLC.
\* @type: $x86Word => Bool;
WordWellFormed(word) ==
  /\ DOMAIN word = 1..64
  /\ \A bit \in 1..64 : word[bit] \in BOOLEAN

\* @type: (Int -> Int) => $x86Word;
WordFromBytes(bytes) ==
  [bit \in 1..64 |->
    ((bytes[((bit - 1) \div 8) + 1] \div (2 ^ ((bit - 1) % 8))) % 2) = 1]

ZeroWord == [bit \in 1..64 |-> FALSE]

\* @type: $x86State => Bool;
StateWellFormed(state) ==
  /\ DOMAIN state = {"gpr", "flags"}
  /\ DOMAIN state.gpr = GPRs
  /\ \A reg \in GPRs : WordWellFormed(state.gpr[reg])
  /\ DOMAIN state.flags = Flags
  /\ \A flag \in Flags : state.flags[flag] \in BOOLEAN

\* Shape validation is separate from instruction support. Unknown opcodes and
\* unsupported forms remain representable, but never execute as no-ops.
\* @type: $x86Instruction => Bool;
InstructionWellFormed(i) ==
  /\ DOMAIN i = {"op", "width", "dst", "source", "sourceReg", "immediate",
                  "next", "target", "condition"}
  /\ i.op # "" /\ i.width \in {0, 8, 16, 32, 64}
  /\ i.dst \in GPRs \cup {""}
  /\ i.source \in {"none", "reg", "imm", "memory"}
  /\ i.sourceReg \in GPRs \cup {""}
  /\ WordWellFormed(i.immediate)
  /\ i.next >= 0 /\ i.target >= 0
  /\ i.condition \in Conditions \cup {""}

\* Immediates have already been extended by the decoder to operand width:
\* zero above bit 32 for a 32-bit operation, sign-extended imm32 for 64-bit
\* arithmetic/logical operations; MOV r64,imm64 can use all 64 bits.
\* @type: $x86Instruction => Bool;
Supported(i) ==
  IF ~InstructionWellFormed(i) THEN FALSE
  ELSE IF i.op \in DataOps THEN
    /\ i.width \in {32, 64} /\ i.dst \in GPRs /\ i.condition = ""
    /\ IF i.source = "reg" THEN i.sourceReg \in GPRs
       ELSE IF i.source = "imm" THEN
         IF i.width = 32 THEN \A bit \in 33..64 : ~i.immediate[bit]
         ELSE i.op = "mov" \/
              (\A bit \in 33..64 : i.immediate[bit] = i.immediate[32])
       ELSE FALSE
  ELSE
    /\ i.width = 0 /\ i.dst = "" /\ i.source = "none"
    /\ IF i.op = "jcc" THEN i.condition \in Conditions
       ELSE i.op \in {"nop", "jmp", "ud2"} /\ i.condition = ""

\* Carry look-ahead expressed without recursion or large host integers.
\* carry is the incoming carry at bit 1; position may be width+1.
\* @type: ($x86Word, $x86Word, Bool, Int) => Bool;
CarryInto(left, right, carry, position) ==
  \/ carry /\ (\A bit \in 1..(position - 1) : left[bit] \/ right[bit])
  \/ \E generated \in 1..(position - 1) :
       /\ left[generated] /\ right[generated]
       /\ \A bit \in (generated + 1)..(position - 1) :
            left[bit] \/ right[bit]

\* @type: ($x86Word, $x86Word, Bool, Int) => $x86Word;
AddWord(left, right, carry, width) ==
  [bit \in 1..64 |->
    IF bit <= width
    THEN (left[bit] # right[bit]) # CarryInto(left, right, carry, bit)
    ELSE FALSE]

\* @type: $x86Word => $x86Word;
NotWord(word) == [bit \in 1..64 |-> ~word[bit]]

\* @type: ($x86Opcode, $x86Word, $x86Word, Int) => $x86Word;
LogicWord(op, left, right, width) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE CASE op \in {"and", "test"} -> left[bit] /\ right[bit]
           [] op = "or" -> left[bit] \/ right[bit]
           [] OTHER -> left[bit] # right[bit]]

\* @type: ($x86Word, Int, Bool, Bool, Bool) => ($location -> Bool);
ResultFlags(result, width, carry, auxiliary, overflow) ==
  [flag \in Flags |->
    CASE flag = "cf" -> carry
      [] flag = "pf" -> Cardinality({bit \in 1..8 : result[bit]}) % 2 = 0
      [] flag = "af" -> auxiliary
      [] flag = "zf" -> \A bit \in 1..width : ~result[bit]
      [] flag = "sf" -> result[width]
      [] OTHER -> overflow]

\* @type: ($x86Condition, $location -> Bool) => Bool;
ConditionHolds(condition, flags) ==
  CASE condition = "o" -> flags["of"]
    [] condition = "no" -> ~flags["of"]
    [] condition = "b" -> flags["cf"]
    [] condition = "ae" -> ~flags["cf"]
    [] condition = "e" -> flags["zf"]
    [] condition = "ne" -> ~flags["zf"]
    [] condition = "be" -> flags["cf"] \/ flags["zf"]
    [] condition = "a" -> ~flags["cf"] /\ ~flags["zf"]
    [] condition = "s" -> flags["sf"]
    [] condition = "ns" -> ~flags["sf"]
    [] condition = "p" -> flags["pf"]
    [] condition = "np" -> ~flags["pf"]
    [] condition = "l" -> flags["sf"] # flags["of"]
    [] condition = "ge" -> flags["sf"] = flags["of"]
    [] condition = "le" -> flags["zf"] \/ (flags["sf"] # flags["of"])
    [] condition = "g" -> ~flags["zf"] /\ (flags["sf"] = flags["of"])

\* @type: ($x86State, $address, $edgeKind, $machineStatus) => $x86Outcome;
Outcome(state, destination, kind, status) ==
  [state |-> state, dst |-> destination, kind |-> kind, status |-> status]

\* @type: ($x86Instruction, $x86State) => Set($x86State);
DataResults(i, state) ==
  LET left == state.gpr[i.dst]
      right == IF i.source = "reg" THEN state.gpr[i.sourceReg] ELSE i.immediate
      subtract == i.op \in {"sub", "cmp"}
      rhs == IF subtract THEN NotWord(right) ELSE right
      result ==
        CASE i.op = "mov" ->
               [bit \in 1..64 |-> IF bit <= i.width THEN right[bit] ELSE FALSE]
          [] i.op \in ArithmeticOps -> AddWord(left, rhs, subtract, i.width)
          [] OTHER -> LogicWord(i.op, left, right, i.width)
      written == IF i.op \in {"cmp", "test"} THEN state.gpr
                 ELSE [state.gpr EXCEPT ![i.dst] = result]
      carry == CarryInto(left, rhs, subtract, i.width + 1)
      auxiliary == CarryInto(left, rhs, subtract, 5)
      overflow == IF subtract
                  THEN (left[i.width] # right[i.width]) /\
                       (result[i.width] # left[i.width])
                  ELSE (left[i.width] = right[i.width]) /\
                       (result[i.width] # left[i.width])
  IN IF i.op = "mov" THEN {[gpr |-> written, flags |-> state.flags]}
     ELSE IF i.op \in ArithmeticOps THEN
       {[gpr |-> written,
         flags |-> ResultFlags(result, i.width,
                    IF subtract THEN ~carry ELSE carry,
                    IF subtract THEN ~auxiliary ELSE auxiliary, overflow)]}
     ELSE
       \* AF is undefined after logical operations, not preserved or set to 0.
       {[gpr |-> written,
         flags |-> ResultFlags(result, i.width, FALSE, af, FALSE)] : af \in BOOLEAN}

\* Public single-instruction interface. Precondition: StateWellFormed(state).
\* Unsupported forms return no modeled outcomes; Supported must be consulted.
\* Terminal dst=0 and kind="" are unused sentinels, never CFG destinations.
\* @type: ($x86Instruction, $x86State) => Set($x86Outcome);
Execute(i, state) ==
  IF ~Supported(i) THEN {}
  ELSE CASE i.op \in DataOps ->
              {Outcome(after, i.next, "next", "running") : after \in DataResults(i, state)}
         [] i.op = "nop" -> {Outcome(state, i.next, "next", "running")}
         [] i.op = "jmp" -> {Outcome(state, i.target, "jump", "running")}
         [] i.op = "jcc" ->
              IF ConditionHolds(i.condition, state.flags)
              THEN {Outcome(state, i.target, "taken", "running")}
              ELSE {Outcome(state, i.next, "fallthrough", "running")}
         [] i.op = "ud2" -> {Outcome(state, 0, "", "faulted")}

\* @type: $x86Condition => Set($location);
ConditionUses(condition) ==
  CASE condition \in {"o", "no"} -> {"of"}
    [] condition \in {"b", "ae"} -> {"cf"}
    [] condition \in {"e", "ne"} -> {"zf"}
    [] condition \in {"be", "a"} -> {"cf", "zf"}
    [] condition \in {"s", "ns"} -> {"sf"}
    [] condition \in {"p", "np"} -> {"pf"}
    [] condition \in {"l", "ge"} -> {"sf", "of"}
    [] OTHER -> {"zf", "sf", "of"}

\* @type: $x86Instruction => Set($location);
UsesOf(i) ==
  IF ~Supported(i) THEN X86Locations
  ELSE IF i.op = "jcc" THEN ConditionUses(i.condition)
  ELSE IF i.op \in DataOps
       THEN (IF i.op = "mov" THEN {} ELSE {i.dst})
            \cup (IF i.source = "reg" THEN {i.sourceReg} ELSE {})
       ELSE {}

\* @type: $x86Instruction => Set($location);
MustDefsOf(i) ==
  IF ~Supported(i) THEN {}
  ELSE (IF i.op \in DataOps \ {"cmp", "test"} THEN {i.dst} ELSE {})
       \cup (IF i.op \in ArithmeticOps \cup LogicalOps THEN Flags ELSE {})

\* @type: $x86Instruction => Set($location);
MayDefsOf(i) == IF Supported(i) THEN MustDefsOf(i) ELSE X86Locations

\* Finite exact-state bridge to AriadneMachineState. A catalogue is only a
\* naming/indexing device; Execute, not the catalogue, determines the outputs.
\* No CHOOSE discards nondeterministic outcomes or duplicate matching IDs.
\* @type: ($x86Outcome, $abstractStateId -> $x86State,
\*         $abstractStateId -> $machineStatus) => Set($abstractStateId);
MatchingIds(outcome, catalogue, statuses) ==
  {id \in DOMAIN catalogue :
    catalogue[id] = outcome.state /\ statuses[id] = outcome.status}

\* @type: ($address -> $x86Instruction, $abstractStateId -> $x86State,
\*         $abstractStateId -> $machineStatus,
\*         Set({src: $address, dst: $address, kind: $edgeKind}))
\*   => Set({src: $address, before: $abstractStateId, dst: $address,
\*           after: $abstractStateId, kind: $edgeKind});
RunningSteps(instructions, catalogue, statuses, edges) ==
  UNION {UNION {
    UNION {{[src |-> site, before |-> before, dst |-> outcome.dst,
             after |-> after, kind |-> outcome.kind]
            : after \in MatchingIds(outcome, catalogue, statuses)}
           : outcome \in {o \in Execute(instructions[site], catalogue[before]) :
               o.status = "running" /\ MachineEdge(site, o.dst, o.kind) \in edges}}
    : before \in {id \in DOMAIN catalogue : statuses[id] = "running"}}
    : site \in DOMAIN instructions}

\* @type: ($address -> $x86Instruction, $abstractStateId -> $x86State,
\*         $abstractStateId -> $machineStatus)
\*   => Set({site: $address, before: $abstractStateId,
\*           after: $abstractStateId, outcome: $terminalOutcome});
TerminalSteps(instructions, catalogue, statuses) ==
  UNION {UNION {
    UNION {{[site |-> site, before |-> before, after |-> after, outcome |-> o.status]
            : after \in MatchingIds(o, catalogue, statuses)}
           : o \in {outcome \in Execute(instructions[site], catalogue[before]) :
                      outcome.status # "running"}}
    : before \in {id \in DOMAIN catalogue : statuses[id] = "running"}}
    : site \in DOMAIN instructions}

\* A supported opcode alone is not a completeness certificate. Every computed
\* outcome for every supplied running state must have an ID and, if running,
\* its exact labeled edge. Missing states/edges never silently certify pruning.
\* @type: ($address -> $x86Instruction, $abstractStateId -> $x86State,
\*         $abstractStateId -> $machineStatus,
\*         Set({src: $address, dst: $address, kind: $edgeKind})) => Set($address);
CompleteSitesFor(instructions, catalogue, statuses, edges) ==
  {site \in DOMAIN instructions :
    /\ Supported(instructions[site])
    /\ \A before \in {id \in DOMAIN catalogue : statuses[id] = "running"} :
         \A outcome \in Execute(instructions[site], catalogue[before]) :
           /\ MatchingIds(outcome, catalogue, statuses) # {}
           /\ outcome.status = "running" =>
                MachineEdge(site, outcome.dst, outcome.kind) \in edges}

\* Reporting names are injective and cover the register words in the catalogue.
\* They do not participate in Execute. Unknown registers must not be zero-filled.
\* @type: ($abstractStateId -> $x86State, $abstractStateId -> $machineStatus,
\*         $abstractValue -> $x86Word) => Bool;
CatalogueWellFormed(catalogue, statuses, names) ==
  /\ IsFiniteSet(DOMAIN catalogue) /\ DOMAIN catalogue # {}
  /\ DOMAIN statuses = DOMAIN catalogue
  /\ \A id \in DOMAIN catalogue :
       /\ StateWellFormed(catalogue[id])
       /\ statuses[id] \in {"running", "faulted"}
  /\ IsFiniteSet(DOMAIN names)
  /\ \A name \in DOMAIN names : WordWellFormed(names[name])
  /\ \A a, b \in DOMAIN names : names[a] = names[b] => a = b
  /\ \A id \in DOMAIN catalogue : \A reg \in GPRs :
       \E name \in DOMAIN names : names[name] = catalogue[id].gpr[reg]

\* @type: ($abstractStateId -> $x86State, $abstractValue -> $x86Word)
\*   => ($abstractStateId -> ($location -> Set($abstractValue)));
ValuationFor(catalogue, names) ==
  [id \in DOMAIN catalogue |->
    [location \in X86Locations |->
      IF location \in GPRs
      THEN {CHOOSE name \in DOMAIN names : names[name] = catalogue[id].gpr[location]}
      ELSE {IF catalogue[id].flags[location] THEN "true" ELSE "false"}]]

=============================================================================
