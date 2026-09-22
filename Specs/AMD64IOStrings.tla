------------------------- MODULE AMD64IOStrings -------------------------
EXTENDS AMD64IO, AMD64StringsMemory

\* Successful INS/OUTS bindings. Mixed permission/memory failure priority stays
\* explicitly open. These relations end at body-applied string control; RIP and
\* architectural retirement are composed by the parent execution layer.

\* @type: ($ioEvent, $amd64Fault) => $ioTransferDisposition;
CompletedDisposition(event, faultTemplate) ==
  [kind |-> "completed", event |-> event, fault |-> faultTemplate]

\* OUTS reads source bytes before the explicit strongly ordered I/O event.
\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $stringByteSeq, $stringSpec, $stringControl, $stringControl,
\*   Str, Int, Int, $ioPermissionSnapshot, $ioOrdering, Set($ioDeviceRule),
\*   $ioRequest, $ioEvent, $amd64Fault) => Bool;
OUTSSuccess(memory, captured, sourceSpan, values, spec, beforeControl,
            afterControl, mode, cpl, iopl, snapshot, ordering, environment,
            request, event, faultTemplate) ==
  LET disposition == CompletedDisposition(event, faultTemplate)
  IN /\ spec.kind = "outs"
     /\ spec.elementBytes \in {1, 2, 4}
     /\ ReadResolvedBytes(memory, captured, sourceSpan, values)
     /\ request.direction = "output"
     /\ request.width = spec.elementBytes
     /\ request.writeData = values
     /\ TransferDispositionAllowed(mode, cpl, iopl, snapshot, ordering,
                                    environment, request, disposition)
     /\ CommitControlAllowed(spec, beforeControl, beforeControl.status,
                             afterControl)

\* INS receives device bytes before the destination replacement.
\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $stringSpec, $stringControl, $stringControl, Str, Int, Int,
\*   $ioPermissionSnapshot, $ioOrdering, Set($ioDeviceRule), $ioRequest,
\*   $ioEvent, $amd64Fault, Set($amd64ByteCell), Set($amd64Address)) => Bool;
INSSuccess(memory, captured, destinationSpan, spec, beforeControl, afterControl,
           mode, cpl, iopl, snapshot, ordering, environment, request, event,
           faultTemplate, afterMemory, afterCaptured) ==
  LET disposition == CompletedDisposition(event, faultTemplate)
  IN /\ spec.kind = "ins"
     /\ spec.elementBytes \in {1, 2, 4}
     /\ request.direction = "input"
     /\ request.width = spec.elementBytes
     /\ Len(event.data) = spec.elementBytes
     /\ TransferDispositionAllowed(mode, cpl, iopl, snapshot, ordering,
                                    environment, request, disposition)
     /\ WriteResolvedBytes(memory, destinationSpan, event.data, captured,
                            afterMemory, afterCaptured)
     /\ CommitControlAllowed(spec, beforeControl, beforeControl.status,
                             afterControl)

\* Architectural effect order for successful bound cases.
\* @type: Str => Seq(Str);
IOStringEffectOrder(kind) ==
  IF kind = "outs" THEN <<"memory-read", "io-write">>
  ELSE <<"io-read", "memory-write">>

\* Failure priority that the pinned sources do not close remains a named
\* obligation rather than an arbitrary choice of fault or side effect.
MixedFailureOrderingOpen(kind) == kind \in {"ins", "outs"}

\* @type: Str => Seq(Str);
MixedFailurePossibleEffects(kind) ==
  IF kind = "ins" THEN <<"io-read-before-destination-fault">>
  ELSE <<"memory-read-commit-versus-permission-fault">>

=============================================================================
