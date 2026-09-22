------------------------- MODULE AMD64IOChecks -------------------------
EXTENDS AMD64IO

ZeroByte == [bit \in 1..8 |-> FALSE]
ZeroFault == [stage |-> 0, vector |-> "GP", reason |-> "fixture",
  errorCode |-> NoPageFaultCode, linear |-> ZeroAddress]
AllCovered == 0..65535
NoDenied == {}
Denied11 == {11}
Ready == [status |-> "ready", covered |-> AllCovered,
          denied |-> NoDenied, fault |-> ZeroFault]
Denied == [Ready EXCEPT !.denied = Denied11]
Unavailable == [Ready EXCEPT !.status = "unavailable"]
CapturedBits == {
  [port |-> 10, available |-> TRUE, denied |-> FALSE],
  [port |-> 11, available |-> TRUE, denied |-> FALSE]}
MissingBits == {
  [port |-> 10, available |-> TRUE, denied |-> FALSE],
  [port |-> 11, available |-> FALSE, denied |-> FALSE]}

\* @type: $ioRequest;
Read16 == [direction |-> "input", base |-> 10, width |-> 2,
           writeData |-> <<>>, sequence |-> 4]
\* @type: $ioRequest;
Cross32 == [direction |-> "input", base |-> 65534, width |-> 4,
            writeData |-> <<>>, sequence |-> 4]
\* @type: $ioRequest;
Write8 == [direction |-> "output", base |-> 32, width |-> 1,
           writeData |-> <<ZeroByte>>, sequence |-> 4]
\* @type: $ioDeviceRule;
ReadRule == [direction |-> "input", base |-> 10, width |-> 2,
             writeData |-> <<>>, readData |-> <<ZeroByte, ZeroByte>>,
             transactionOrder |-> <<0, 1>>]
\* @type: $ioDeviceRule;
UnalignedRule == [direction |-> "input", base |-> 11, width |-> 2,
                  writeData |-> <<>>, readData |-> <<ZeroByte, ZeroByte>>,
                  transactionOrder |-> <<1, 0>>]
ReadEvent == RuleEvent(ReadRule, Read16)
Ordering == [priorWritesComplete |-> TRUE, nextSequence |-> 4]

IOChecks ==
  /\ PermissionDecision("protected", 0, 0, Unavailable, Read16).kind = "allowed"
  /\ PermissionDecision("virtual8086", 3, 3, Unavailable, Read16).kind = "unavailable"
  /\ PermissionDecision("protected", 3, 0, Denied, Read16).kind = "generalProtection"
  /\ PermissionSnapshotFromBits(Read16, CapturedBits, ZeroFault).status = "ready"
  /\ PermissionSnapshotFromBits(Read16, MissingBits, ZeroFault).status = "unavailable"
  /\ DeviceRuleWellFormed(ReadRule)
  /\ DeviceRuleWellFormed(UnalignedRule)
  /\ DeviceStep({ReadRule}, Read16, ReadEvent)
  /\ ReadEvent.stronglyOrdered
  /\ PortSpan(10, 2) = <<10, 11>>
  /\ ~WithinPortBoundary(Cross32)
  /\ RequestShapeValid(Write8)
  /\ RequestShapeValid(InputRequest(10, 2, 4))
  /\ InputAccumulatorWriteAllowed("long64", 4, ZeroAddress,
       <<ZeroByte, ZeroByte, ZeroByte, ZeroByte>>, ZeroAddress)
  /\ DirectExecution("protected", 0, 0, Ready, Ordering, {ReadRule}, Read16,
       [kind |-> "completed", event |-> ReadEvent, fault |-> ZeroFault],
       ZeroAddress, ZeroAddress)

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ IOChecks
=============================================================================
