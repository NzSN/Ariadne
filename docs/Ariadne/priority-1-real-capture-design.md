# Priority 1 design: evidence-linked predecessor slice from a real minidump

Design decision, **2026-09-29**. The scoped
[Priority 1 implementation plan](../../Plans/completed/priority-1-real-capture-plan.md) applies this
design. It uses the delivered Windows/Linux AMD64
[minidump reader](file-reader-design.md),
[Stage C report contract](stage-c-report-schema.md), and
[Ariadne analyzer](../implementation.md). The tool-produced
[Stage B fixture](stage-b-c-validation.md) tests the mechanics; a real-capture
finding needs independent entry evidence.
The first scoped case is recorded in the
[Priority 1 validation](priority-1-real-capture-validation.md).

## Question and claim

The investigator asks: **Which earlier captured instructions might have
supplied an address input used by the crash instruction?** The answer is a
possible backward data slice over a locally recovered graph. It is conditional
on the chosen entry, captured bytes, decoded instruction starts, reviewed
effects and the analyzer's conservative transfer rules.

This answer does not identify the path that actually executed. A minidump is a
snapshot, not a trace. The exception RIP can seed the question but cannot by
itself establish an earlier instruction boundary or a function entry. A
faulting memory write may not have committed; its address-register uses can
still be investigated without asserting the write occurred.

## Evidence chain

Keep these facts distinct and link them in a retained case manifest plus the
unchanged `ariadne-minidump-report-v1` output:

| Fact | Required witness | Meaning |
| --- | --- | --- |
| Artifact | SHA-256 of the exact owned dump bytes, format, platform and size | Identity of the analyzed capture, not proof of a coherent process snapshot |
| Crash seed | Exception-thread identity, valid captured AMD64 context and RIP | Address observed at the exception; not an earlier entry or fault-address substitute |
| Earlier entry | Independent producer/symbol/trace evidence, exact matching module/build identity, RVA-to-VA calculation and, when needed, forward decoding from a known symbol | Justification for one candidate instruction start before RIP |
| Instruction | Captured byte spans with stream/descriptors and file offsets, VA, LLVM MC target/opcode/length | Decode of dump-supplied bytes at an established or locally reached start |
| Local predecessor | Reviewed control classification and typed recovered edge | Possible graph predecessor; not an observed branch decision |
| Value origin | Reviewed effect rule, `uses`/`may_defs`/`must_defs`, reaching origin before the consumer | Possible supplier of a tracked location under the analyzer abstraction |
| Slice membership | Seed, dependency traversal and preserved gaps | Relevant possible producer, not a unique root cause |

The report already carries artifact/query identities, captured read contributors,
per-site preparation evidence, graph edges, reaching origins and the slice. The
**case manifest** is a separate, dated validation artifact that supplies the
entry witness and the expected-versus-observed finding. It must not silently
upgrade report v1 or add a global `complete` flag. If a product consumer later
needs the entry witness inside JSON, specify a new versioned schema first.

## Entry and byte trust rules

An admissible earlier entry is a function boundary or known target established
without decoding arbitrary bytes backward from RIP. Examples include matching
build/debug symbols or a retained producer/trace record. Bind the witness to
the dump module by its recorded build identifier, then calculate the runtime VA
from the recorded module base and module-relative address. Record the witness
artifact identity and the comparison used to match it. A module filename,
timestamp, approximate version, plausible instruction sequence, or crash-time
register value alone is insufficient.

If the trusted function start lies just outside capture, forward-disassemble
the **exact build-matched companion** from that start and choose a complete
instruction boundary inside capture. Independently compare its bytes with the
dump. This establishes a local query entry without pretending that the
function's uncaptured earlier instructions were analyzed. The companion still
supplies no bytes to Ariadne's reader or analyzer.

The entry and the route to the seed must lie in captured, unambiguous memory.
Only the minidump supplies instruction bytes. A matching binary or symbol file
may justify a boundary and help interpret names; it never fills a capture hole,
wins a conflicting overlap, or silently changes an instruction's bytes. Keep
unavailable, conflicting and unvisited starts separate. The materializer follows
only reviewed local successors from explicit roots; seeds do not become roots,
and call-only targets do not transmit reaching definitions.

The two existing Breakpad dumps each contain 128 contiguous captured bytes
before RIP, but no matching `driver` or `crash.exe` symbol artifact has been
identified beside those fixtures. Their byte availability is a candidate
property, not yet an independently anchored predecessor path.

## Result contract and failure behavior

A qualifying case has one explicit earlier entry and a valid exception-RIP
seed. At least one captured, decoded local route reaches the seed, and a
reviewed effect chain places a possible producer of the faulting memory
address register in the backward slice. The retained text, DOT and JSON
outputs agree on identity, VAs, edges, origins, slice and obligations. Every
displayed producer can be traced through its rule and decoded bytes to dump
file offsets. Entry definitions and opaque effects remain labeled as unknown
origins, not invented producer instructions.

An unsupported control form, missing byte, conflicting capture, missing seed,
opaque effect or resource limit must remain visible with its distinct meaning.
A partial report can guide [Priority 2 effect work](../../Plans/completed/priority-2-path-driven-effects-plan.md);
it cannot satisfy the qualifying-case claim until the independently anchored,
nontrivial producer slice is present. If no dump has a valid entry witness,
retain the candidate audit and leave this priority open.

## Design limits

This design adds no PE/ELF reader, executable-file byte fallback,
reverse-from-RIP disassembler heuristic, historical path reconstruction,
interprocedural return matching, fault/commit semantics or formal AMD64 case
promotion. It
preserves the practical-versus-formal separation in the
[assurance decision](practical-assurance-priorities.md).
