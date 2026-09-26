-------------------------- MODULE AriadneInput --------------------------
EXTENDS AriadneMachineCommon, Sequences

\* A byte is usable only if at least one immutable contributor covers it and
\* every contributor agrees. Missing and conflicting data are not zero bytes.
\* @type: (Set({start: Int, data: Seq(Int), fileOffset: Int}), Int) => Set(Int);
ValuesAt(captures, va) ==
  {c.data[va-c.start+1] : c \in {c \in captures :
    c.start <= va /\ va < c.start + Len(c.data)}}
\* @type: (Set({start: Int, data: Seq(Int), fileOffset: Int}), Int) => Bool;
Readable(captures, va) == Cardinality(ValuesAt(captures, va)) = 1
\* @type: (Set({start: Int, data: Seq(Int), fileOffset: Int}), Int, Seq(Int)) => Bool;
PrefixEvidence(captures, va, bytes) == \A i \in 1..Len(bytes):
  /\ Readable(captures, va+i-1)
  /\ bytes[i] \in ValuesAt(captures, va+i-1)

\* Every capture's copied bytes must correspond to its recorded file offsets.
\* @type: (Seq(Int), Set({start: Int, data: Seq(Int), fileOffset: Int})) => Bool;
WellMapped(file, captures) == \A c \in captures:
  /\ c.fileOffset >= 0
  /\ c.fileOffset + Len(c.data) <= Len(file)
  /\ \A i \in 1..Len(c.data): c.data[i] = file[c.fileOffset+i]

\* @type: (Set({src: Int, dst: Int, kind: Str}), Int) => Set(Int);
LocalSuccessors(edges, a) == {e.dst : e \in
  {e \in edges : e.src = a /\ e.kind \in MachineLocalEdgeKinds}}
\* @type: (Set(Int), Set(Int), Set({src: Int, dst: Int, kind: Str})) => Bool;
Closed(roots, attempted, edges) ==
  /\ roots \subseteq attempted
  /\ \A a \in attempted: LocalSuccessors(edges,a) \subseteq attempted
=============================================================================
