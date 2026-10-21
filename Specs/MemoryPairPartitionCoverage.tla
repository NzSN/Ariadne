--------------------- MODULE MemoryPairPartitionCoverage ---------------------
EXTENDS MemoryPairPartitionChecks
FactClasses == {ExactFacts,PlainConstraints,ComposedConstraints,
                {Fact("unknown",0,0,<<>>)}}
TransferClasses == {CopyTransfers,AddTransfers,SubTransfers,AndTransfers,ConstantTransfers}
PairClasses == {fs \X ts : fs \in FactClasses, ts \in TransferClasses}
CoverSafety ==
  /\ UNION FactClasses = Facts
  /\ UNION TransferClasses = Transfers
  /\ UNION PairClasses = Facts \X Transfers
  /\ Cardinality(ExactFacts) = 16
  /\ Cardinality(PlainConstraints) = 64
  /\ Cardinality(ComposedConstraints) = 42
  /\ Cardinality({Fact("unknown",0,0,<<>>)}) = 1
  /\ Cardinality(TransferClasses) = 5
  /\ \A ts \in TransferClasses: Cardinality(ts) = 16
  /\ Cardinality(PairClasses) = 20
  /\ Cardinality(Facts \X Transfers) = 9840
=============================================================================
