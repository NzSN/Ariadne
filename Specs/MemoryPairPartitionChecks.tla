---------------------- MODULE MemoryPairPartitionChecks ----------------------
EXTENDS MemoryPairChecks
\* @type: (Set($memoryFact), Set($memoryTransfer)) => Bool;
PairInitFor(facts,transfers) ==
  /\ Init
  /\ selectedFact \in facts
  /\ selectedTransfer \in transfers
CopyTransfers == {Transfer("copy",v) : v \in Values}
AddTransfers == {Transfer("add",v) : v \in Values}
SubTransfers == {Transfer("sub",v) : v \in Values}
AndTransfers == {Transfer("and",v) : v \in Values}
ConstantTransfers == {Transfer("constant",v) : v \in Values}
PairInitExactCopy == PairInitFor(ExactFacts,CopyTransfers)
PairInitExactAdd == PairInitFor(ExactFacts,AddTransfers)
PairInitExactSub == PairInitFor(ExactFacts,SubTransfers)
PairInitExactAnd == PairInitFor(ExactFacts,AndTransfers)
PairInitExactConstant == PairInitFor(ExactFacts,ConstantTransfers)
PairInitPlainCopy == PairInitFor(PlainConstraints,CopyTransfers)
PairInitPlainAdd == PairInitFor(PlainConstraints,AddTransfers)
PairInitPlainSub == PairInitFor(PlainConstraints,SubTransfers)
PairInitPlainAnd == PairInitFor(PlainConstraints,AndTransfers)
PairInitPlainConstant == PairInitFor(PlainConstraints,ConstantTransfers)
PairInitComposedCopy == PairInitFor(ComposedConstraints,CopyTransfers)
PairInitComposedAdd == PairInitFor(ComposedConstraints,AddTransfers)
PairInitComposedSub == PairInitFor(ComposedConstraints,SubTransfers)
PairInitComposedAnd == PairInitFor(ComposedConstraints,AndTransfers)
PairInitComposedConstant == PairInitFor(ComposedConstraints,ConstantTransfers)
PairInitUnknownCopy == PairInitFor({Fact("unknown",0,0,<<>>)},CopyTransfers)
PairInitUnknownAdd == PairInitFor({Fact("unknown",0,0,<<>>)},AddTransfers)
PairInitUnknownSub == PairInitFor({Fact("unknown",0,0,<<>>)},SubTransfers)
PairInitUnknownAnd == PairInitFor({Fact("unknown",0,0,<<>>)},AndTransfers)
PairInitUnknownConstant == PairInitFor({Fact("unknown",0,0,<<>>)},ConstantTransfers)
PairPartitionCoverInit ==
  \/ PairInitExactCopy
  \/ PairInitExactAdd
  \/ PairInitExactSub
  \/ PairInitExactAnd
  \/ PairInitExactConstant
  \/ PairInitPlainCopy
  \/ PairInitPlainAdd
  \/ PairInitPlainSub
  \/ PairInitPlainAnd
  \/ PairInitPlainConstant
  \/ PairInitComposedCopy
  \/ PairInitComposedAdd
  \/ PairInitComposedSub
  \/ PairInitComposedAnd
  \/ PairInitComposedConstant
  \/ PairInitUnknownCopy
  \/ PairInitUnknownAdd
  \/ PairInitUnknownSub
  \/ PairInitUnknownAnd
  \/ PairInitUnknownConstant
=============================================================================
