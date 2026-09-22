---------------------------- MODULE AMD64IO ----------------------------
EXTENDS AMD64Memory

\* Port-I/O permission and explicit device-event contract.
\* Authority: Volume 1 rev. 3.25 sections 3.8.1-3.8.3; Volume 2 rev. 3.45
\* section 12.2.4; Volume 3 rev. 3.38 IN/OUT/INS/OUTS entries.
\*
\* Device rules can supply data and events but cannot mutate CPU state. Missing
\* rules/captured permission bytes are modeling-unavailable, never zero/fault.

IODirections == {"input", "output"}
IOWidths == {1, 2, 4}
PermissionKinds == {"allowed", "generalProtection", "pageFault", "unavailable"}
PermissionSnapshotKinds == {"ready", "pageFault", "unavailable"}
TransferKinds == {"completed", "generalProtection", "pageFault",
  "permissionUnavailable", "boundaryUnspecified", "waitingForOrdering",
  "deviceUnavailable"}

\* @typeAlias: ioRequest = {direction: Str, base: Int, width: Int,
\*   writeData: Seq($amd64Byte), sequence: Int};
\* @typeAlias: ioPermissionSnapshot = {status: Str, covered: Set(Int),
\*   denied: Set(Int), fault: $amd64Fault};
\* @typeAlias: ioPermissionBit = {port: Int, available: Bool, denied: Bool};
\* @typeAlias: ioPermissionDecision = {kind: Str, fault: $amd64Fault};
\* @typeAlias: ioEvent = {direction: Str, base: Int, width: Int,
\*   data: Seq($amd64Byte), sequence: Int, stronglyOrdered: Bool,
\*   transactionOrder: Seq(Int)};
\* @typeAlias: ioDeviceRule = {direction: Str, base: Int, width: Int,
\*   writeData: Seq($amd64Byte), readData: Seq($amd64Byte),
\*   transactionOrder: Seq(Int)};
\* @typeAlias: ioOrdering = {priorWritesComplete: Bool, nextSequence: Int};
\* @typeAlias: ioTransferDisposition = {kind: Str, event: $ioEvent,
\*   fault: $amd64Fault};

\* Explicit architectural byte ports; no modulo wrap is inferred at FFFFh.
\* @type: (Int, Int) => Seq(Int);
PortSpan(base, width) ==
  CASE width = 1 -> <<base>>
    [] width = 2 -> <<base, base + 1>>
    [] OTHER -> <<base, base + 1, base + 2, base + 3>>

\* @type: $ioRequest => Bool;
RequestShapeValid(request) ==
  /\ request.direction \in IODirections
  /\ request.base \in 0..65535
  /\ request.width \in IOWidths
  /\ request.sequence >= 0
  /\ IF request.direction = "input" THEN Len(request.writeData) = 0
     ELSE Len(request.writeData) = request.width

\* @type: $ioRequest => Bool;
WithinPortBoundary(request) == request.base + request.width <= 65536

\* @type: Seq($amd64Byte) => $amd64Address;
InputBytesToWord(data) ==
  [bit \in 1..64 |->
    IF bit <= 8 * Len(data)
    THEN LET byteIndex == ((bit - 1) \div 8) + 1
             within == ((bit - 1) % 8) + 1
         IN data[byteIndex][within]
    ELSE FALSE]

\* AL/AX preserve upper bits; EAX clears 63:32 only in 64-bit mode.
\* @type: (Str, Int, $amd64Address, Seq($amd64Byte), $amd64Address) => Bool;
InputAccumulatorWriteAllowed(mode, width, before, data, after) ==
  /\ Len(data) = width
  /\ \A bit \in 1..64 :
       IF bit <= 8 * width THEN after[bit] = InputBytesToWord(data)[bit]
       ELSE IF mode = "long64" /\ width = 4 THEN ~after[bit]
       ELSE IF mode = "long64" \/ bit <= 32 THEN after[bit] = before[bit]
       ELSE TRUE

\* @type: (Int, Int, Int) => $ioRequest;
InputRequest(base, width, sequence) ==
  [direction |-> "input", base |-> base, width |-> width,
   writeData |-> <<>>, sequence |-> sequence]

\* @type: (Int, Int, Seq($amd64Byte), Int) => $ioRequest;
OutputRequest(base, width, data, sequence) ==
  [direction |-> "output", base |-> base, width |-> width,
   writeData |-> data, sequence |-> sequence]

\* @type: (Str, Int, Int) => Bool;
BitmapRequired(mode, cpl, iopl) == mode = "virtual8086" \/ cpl > iopl

\* @type: $ioPermissionSnapshot => Bool;
PermissionSnapshotWellFormed(snapshot) ==
  /\ snapshot.status \in PermissionSnapshotKinds
  /\ snapshot.covered \subseteq 0..65535
  /\ snapshot.denied \subseteq snapshot.covered
  /\ (snapshot.status = "pageFault" => snapshot.fault.vector = "PF")

\* @type: ($ioRequest, Set($ioPermissionBit), $amd64Fault)
\*   => $ioPermissionSnapshot;
PermissionSnapshotFromBits(request, reads, faultTemplate) ==
  LET ports == {read.port : read \in reads}
      exact == ports = {PortSpan(request.base, request.width)[index] :
                         index \in 1..Len(PortSpan(request.base, request.width))}
      complete == \A read \in reads : read.available
  IN IF exact /\ complete
     THEN [status |-> "ready", covered |-> ports,
           denied |-> {read.port : read \in {candidate \in reads : candidate.denied}},
           fault |-> faultTemplate]
     ELSE [status |-> "unavailable", covered |-> {}, denied |-> {},
           fault |-> faultTemplate]

\* @type: (Str, Int, Int, $ioPermissionSnapshot, $ioRequest)
\*   => $ioPermissionDecision;
PermissionDecision(mode, cpl, iopl, snapshot, request) ==
  IF ~BitmapRequired(mode, cpl, iopl)
  THEN [kind |-> "allowed", fault |-> snapshot.fault]
  ELSE IF snapshot.status = "pageFault"
       THEN [kind |-> "pageFault", fault |-> snapshot.fault]
       ELSE IF snapshot.status = "unavailable"
            THEN [kind |-> "unavailable", fault |-> snapshot.fault]
            ELSE IF \A port \in 1..Len(PortSpan(request.base, request.width)) :
                         /\ PortSpan(request.base, request.width)[port] \in snapshot.covered
                         /\ PortSpan(request.base, request.width)[port] \notin snapshot.denied
                 THEN [kind |-> "allowed", fault |-> snapshot.fault]
                 ELSE [kind |-> "generalProtection", fault |-> snapshot.fault]

\* @type: Int => Seq(Int);
NaturalOrder(width) ==
  CASE width = 1 -> <<0>>
    [] width = 2 -> <<0, 1>>
    [] OTHER -> <<0, 1, 2, 3>>

\* @type: (Seq(Int), Int) => Bool;
TransactionOrderValid(order, width) ==
  /\ Len(order) = width
  /\ {order[index] : index \in 1..Len(order)} = 0..(width - 1)

\* @type: $ioDeviceRule => Bool;
DeviceRuleWellFormed(rule) ==
  /\ rule.direction \in IODirections
  /\ rule.base \in 0..65535
  /\ rule.width \in IOWidths
  /\ rule.base + rule.width <= 65536
  /\ IF rule.direction = "input"
     THEN Len(rule.writeData) = 0 /\ Len(rule.readData) = rule.width
     ELSE Len(rule.writeData) = rule.width /\ Len(rule.readData) = 0
  /\ TransactionOrderValid(rule.transactionOrder, rule.width)
  /\ (rule.base % rule.width = 0 =>
        rule.transactionOrder = NaturalOrder(rule.width))

\* @type: ($ioDeviceRule, $ioRequest) => Bool;
DeviceRuleMatches(rule, request) ==
  /\ rule.direction = request.direction
  /\ rule.base = request.base
  /\ rule.width = request.width
  /\ (request.direction = "output" => rule.writeData = request.writeData)

\* @type: ($ioDeviceRule, $ioRequest) => $ioEvent;
RuleEvent(rule, request) ==
  [direction |-> request.direction, base |-> request.base,
   width |-> request.width,
   data |-> IF request.direction = "input" THEN rule.readData ELSE request.writeData,
   sequence |-> request.sequence, stronglyOrdered |-> TRUE,
   transactionOrder |-> rule.transactionOrder]

\* @type: (Set($ioDeviceRule), $ioRequest, $ioEvent) => Bool;
DeviceStep(environment, request, event) ==
  /\ RequestShapeValid(request)
  /\ WithinPortBoundary(request)
  /\ \E rule \in environment :
       /\ DeviceRuleWellFormed(rule)
       /\ DeviceRuleMatches(rule, request)
       /\ event = RuleEvent(rule, request)

\* @type: ($ioOrdering, $ioRequest) => Bool;
OrderingAllows(ordering, request) ==
  ordering.priorWritesComplete /\ request.sequence = ordering.nextSequence

\* @type: (Str, Int, Int, $ioPermissionSnapshot, $ioOrdering,
\*   Set($ioDeviceRule), $ioRequest, $ioTransferDisposition) => Bool;
TransferDispositionAllowed(mode, cpl, iopl, snapshot, ordering,
                           environment, request, result) ==
  LET permission == PermissionDecision(mode, cpl, iopl, snapshot, request)
      deviceEvents == {RuleEvent(rule, request) :
        rule \in {candidate \in environment :
          DeviceRuleWellFormed(candidate) /\ DeviceRuleMatches(candidate, request)}}
  IN /\ PermissionSnapshotWellFormed(snapshot)
     /\ RequestShapeValid(request)
     /\ result.kind \in TransferKinds
     /\ CASE result.kind = "completed" ->
            /\ permission.kind = "allowed"
            /\ OrderingAllows(ordering, request)
            /\ result.event \in deviceEvents
       [] result.kind = "generalProtection" ->
            permission.kind = "generalProtection"
       [] result.kind = "pageFault" ->
            permission.kind = "pageFault" /\ result.fault = permission.fault
       [] result.kind = "permissionUnavailable" ->
            permission.kind = "unavailable"
       [] result.kind = "boundaryUnspecified" ->
            permission.kind = "allowed" /\ ~WithinPortBoundary(request)
       [] result.kind = "waitingForOrdering" ->
            permission.kind = "allowed" /\ WithinPortBoundary(request) /\
            ~OrderingAllows(ordering, request)
       [] OTHER ->
            /\ permission.kind = "allowed"
            /\ WithinPortBoundary(request)
            /\ OrderingAllows(ordering, request)
            /\ deviceEvents = {}

\* Direct IN/OUT body binding.  A completed IN writes only the selected
\* accumulator view; OUT frames the entire CPU state.  Every pre-body failure
\* frames CPU state and retains its distinct disposition.
\* @type: ($amd64Address, Int) => Seq($amd64Byte);
DirectAccumulatorBytes(accumulator, width) ==
  LET byte(index) == [bit \in 1..8 |-> accumulator[(index - 1) * 8 + bit]]
  IN CASE width = 1 -> <<byte(1)>>
       [] width = 2 -> <<byte(1), byte(2)>>
       [] OTHER -> <<byte(1), byte(2), byte(3), byte(4)>>

\* @type: (Str, Int, $amd64Address, Int, Int) => $ioRequest;
DirectRequest(direction, base, accumulator, width, sequence) ==
  IF direction = "input"
  THEN InputRequest(base, width, sequence)
  ELSE OutputRequest(base, width, DirectAccumulatorBytes(accumulator, width), sequence)

\* @type: (Str, Int, $amd64Address, Seq($amd64Byte), $amd64Address) => Bool;
DirectAccumulatorEffect(direction, width, before, data, after) ==
  IF direction = "input"
  THEN InputAccumulatorWriteAllowed("long64", width, before, data, after)
  ELSE after = before

\* @type: (Str, Int, Int, $ioPermissionSnapshot, $ioOrdering,
\*   Set($ioDeviceRule), $ioRequest, $ioTransferDisposition,
\*   $amd64Address, $amd64Address) => Bool;
DirectExecution(mode, cpl, iopl, snapshot, ordering, environment, request,
                disposition, beforeAccumulator, afterAccumulator) ==
  /\ TransferDispositionAllowed(mode, cpl, iopl, snapshot, ordering,
                                 environment, request, disposition)
  /\ IF disposition.kind = "completed"
     THEN DirectAccumulatorEffect(request.direction, request.width,
             beforeAccumulator, disposition.event.data, afterAccumulator)
     ELSE afterAccumulator = beforeAccumulator

=============================================================================
