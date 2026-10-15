---------------------- MODULE AriadneMachineCommon ----------------------
EXTENDS AriadneTypes, Naturals, FiniteSets

\* Shared vocabulary and contracts for Ariadne's machine-code models.
\* This module is intentionally stateless. CFG recovery and abstract-state
\* propagation retain separate variables, transitions, obligations and phases.

MachineLocalEdgeKinds ==
  {"next", "taken", "fallthrough", "jump", "indirect", "summary"}

\* One request uses nonnegative virtual addresses from one nonempty immutable
\* snapshot identity. Finiteness and nonemptiness make the analysis domains
\* suitable for the checked fixed-point machines.
\* @type: ($snapshotId, Set($address)) => Bool;
MachineAddressSpaceContract(snapshot, addresses) ==
  /\ snapshot # ""
  /\ IsFiniteSet(addresses)
  /\ addresses # {}
  /\ \A address \in addresses : address >= 0

\* @type: ($snapshotId, $address)
\*          => {snapshot: $snapshotId, va: $address};
MachineAddressIdentity(snapshot, address) ==
  [snapshot |-> snapshot, va |-> address]

\* Edge kind is part of structural identity, so two differently labeled edges
\* between the same addresses remain distinct.
\* @type: ($address, $address, $edgeKind)
\*          => {src: $address, dst: $address, kind: $edgeKind};
MachineEdge(src, dst, kind) ==
  [src |-> src, dst |-> dst, kind |-> kind]

\* Shared well-formedness of normalized location-effect summaries. This checks
\* shape, not whether a decoder or ISA-semantics adapter supplied sound effects.
\* @type: (Set($location), Set($location), Set($location), Set($location))
\*          => Bool;
MachineEffectWellFormed(locations, uses, mustDefs, mayDefs) ==
  /\ uses \subseteq locations
  /\ mustDefs \subseteq mayDefs
  /\ mayDefs \subseteq locations

=============================================================================
