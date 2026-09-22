------------- MODULE AMD64IntegerStateAdapterChecks -------------
EXTENDS AMD64IntegerStateAdapter

VARIABLE
  \* @type: Bool;
  checked

Zeros(width) == [bit \in 1..width |-> FALSE]

BaseFlags == [
  cf |-> FALSE, fixed1 |-> TRUE, pf |-> TRUE, reserved3 |-> FALSE,
  af |-> FALSE, reserved5 |-> FALSE, zf |-> TRUE, sf |-> FALSE,
  tf |-> TRUE, interruptEnable |-> TRUE, df |-> FALSE, of |-> TRUE,
  iopl |-> Zeros(2), nestedTask |-> FALSE, reserved15 |-> FALSE,
  resume |-> FALSE, virtual8086 |-> FALSE, ac |-> TRUE,
  virtualInterrupt |-> FALSE, virtualInterruptPending |-> FALSE,
  id |-> TRUE, reservedHigh |-> Zeros(42)]

Status == [flag \in StatusFlagNames |-> flag \in {"cf", "af", "sf"}]

AdapterChecks ==
  /\ RFlagsWellFormed(BaseFlags)
  /\ ProjectStatusFlags(ApplyStatusFlags(BaseFlags, Status)) = Status
  /\ ApplyStatusFlags(BaseFlags, ProjectStatusFlags(BaseFlags)) = BaseFlags
  /\ ApplyStatusFlags(BaseFlags, Status).df = BaseFlags.df
  /\ SetDirectionFlag(BaseFlags, TRUE).df
  /\ SetDirectionFlag(BaseFlags, TRUE).cf = BaseFlags.cf
  /\ RFlagsWellFormed(SetDirectionFlag(BaseFlags, TRUE))
  /\ StatusDomainsAllowed(BaseFlags, Core!ExactFlagDomains(Status),
                          ApplyStatusFlags(BaseFlags, Status))

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ AdapterChecks

=====================================================================
