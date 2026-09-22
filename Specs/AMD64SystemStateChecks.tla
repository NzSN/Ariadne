-------------------- MODULE AMD64SystemStateChecks --------------------
EXTENDS AMD64SystemState

Zero64 == [bit \in 1..64 |-> FALSE]
Profile == [x87 |-> TRUE, mmx |-> TRUE, sse |-> TRUE, avx |-> TRUE,
  avx512 |-> TRUE, xsave |-> TRUE, fsgsbase |-> TRUE,
  rdpru |-> TRUE, lwp |-> TRUE]
XFeatures == [supported |-> DefinedXFeatures]
XCR0 == [enabled |-> {0, 1, 2, 5, 6, 7, 62}]
MSR == [hwcrCpuidUserDisable |-> FALSE, tscAux |-> Zero64,
  mperf |-> Zero64, aperf |-> Zero64, lwpCfg |-> Zero64,
  lwpCbAddress |-> Zero64]
Base == [cr0 |-> [pe |-> TRUE, mp |-> TRUE, em |-> FALSE, ts |-> FALSE,
                   wp |-> TRUE, am |-> TRUE],
  cr4 |-> [vme |-> FALSE, tsd |-> FALSE, osfxsr |-> TRUE, osxmmexcpt |-> TRUE,
           fsgsbase |-> TRUE, osxsave |-> TRUE],
  xcr0 |-> XCR0, msr |-> MSR, inSMM |-> FALSE,
  x87ExceptionPending |-> FALSE]
Features == [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
  avxEnabled |-> TRUE, avx512Enabled |-> TRUE]

SystemStateChecks ==
  /\ FeatureProfileWellFormed(Profile)
  /\ XCR0WellFormed(XFeatures, XCR0)
  /\ MediaGuard(Profile, Base, "legacySSE") = "allowed"
  /\ MediaGuard(Profile, [Base EXCEPT !.cr0.ts = TRUE], "legacySSE") = "NM"
  /\ MediaGuard(Profile, [Base EXCEPT !.cr4.osfxsr = FALSE], "legacySSE") = "UD"
  /\ MediaGuard(Profile, [Base EXCEPT !.cr0.em = TRUE], "wait") = "allowed"
  /\ MediaGuard(Profile, [Base EXCEPT !.cr0.ts = TRUE], "wait") = "NM"
  /\ ContextProjection(Profile, Base, Features)
  /\ FSGSBaseGuard(Profile, Base, "protected") = "UD"
  /\ RDPRUGuard(Profile, [Base EXCEPT !.cr4.tsd = TRUE], 3) = "UD"
  /\ LWPGuard(Profile, XFeatures, Base, "long64") = "allowed"
  /\ LWPGuard(Profile, XFeatures, [Base EXCEPT !.cr4.osxsave = FALSE],
              "long64") = "UD"
  /\ LWPGuard(Profile, XFeatures, Base, "virtual8086") = "UD"

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ SystemStateChecks
=======================================================================
