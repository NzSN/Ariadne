---------------- MODULE AMD64AtomicOrderingChecks ----------------
EXTENDS AMD64AtomicOrdering

\* Explicit wrapper required by the aggregate checker: the configuration base
\* name maps to `<base>Checks.tla`. The ordering model itself owns Init, Next,
\* and Safety; this module intentionally adds no stronger AMD ordering claim.

==================================================================
