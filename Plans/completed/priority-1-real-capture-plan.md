# Priority 1 implementation plan: a real-capture predecessor slice

## Context and follow-up

**Status.** Completed plan, archived; acceptance is limited to the recorded scope.

**Why this document exists.** [Motivating design](../../docs/Ariadne/priority-1-real-capture-design.md) defines the problem and contract this plan implements.

**What this document establishes.** The controlled Chromium/Linux case demonstrates a captured predecessor slice from an independently established earlier entry and retains a possible address producer with explicit gaps.

**Where to go next.**

- [Delivery and follow-up](../../docs/Ariadne/priority-1-real-capture-validation.md) — records what was exercised and which limits remain.
- [Active plan index](../README.md) — prevents completed steps from being mistaken for pending work.

**What remains unresolved.** The implementation steps below are archived, not a current task list. These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. The later investigation delivery explains the origins; it still does not establish an executed path or root cause.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Plan dated **2026-09-29** for practical priority 1 in the
[assurance queue](../../docs/Ariadne/practical-assurance-priorities.md). It executes the
[real-capture predecessor-slice design](../../docs/Ariadne/priority-1-real-capture-design.md)
and extends the delivered, tool-produced
[Stage B/C fixture and CLI](../../docs/Ariadne/stage-b-c-validation.md); that fixture
remains a regression, not evidence of a historical execution. The relevant
[reader design](../../docs/Ariadne/file-reader-design.md) and [report contract](../../docs/Ariadne/stage-c-report-schema.md)
still limit input to Windows/Linux AMD64 minidumps and captured bytes.
The 2026-09-29 controlled Chromium/Linux case is now
[qualified by source-bound evidence](../../docs/Ariadne/priority-1-real-capture-validation.md).
The steps below remain the acceptance procedure for that exact case or a new
candidate; they do not license reusing its result for a changed artifact.

## Result and boundary

Retain one reproducible report in which an independently justified instruction start
**before** the exception RIP reaches a captured, decoded crash instruction. The backward
slice must show at least one possible producer of an address register used by the
faulting memory instruction. The report is a possible data-dependence result under
reviewed effects, not an execution trace, proof of the actual predecessor, or proof that
a faulting store committed. Do not use decoder success at arbitrary earlier bytes as
evidence of a valid entry.

## 1. Select and pin a candidate

1. Audit the two existing hash-pinned Breakpad dumps first. They each contain 128
   contiguous captured bytes before RIP, but no matching `driver`/`crash.exe` symbol
   artifact has yet been found beside them. Record the exact dump SHA-256, platform,
   exception thread/context validity, RIP, module identity and base, captured ranges,
   and any missing or conflicting byte spans.
2. Seek a representative Chromium/Electron Windows or Linux crash minidump with an
   **exactly matching** producer binary or debug/symbol artifact, or create a new real
   crash capture from a controlled Chromium/Electron build while retaining its build
   identity and boundary evidence. A filename, approximate version, timestamp alone, or
   plausible backward disassembly does not establish a match. Keep the tool-produced
   Stage B dumps separate.
3. Identify an earlier function entry or known branch target independently of decoding
   backward from RIP. Record the symbol/producer source, its module/build identifier,
   the module-relative address and relocated VA, and its relationship to the selected
   captured range. Any companion artifact supplies **boundary evidence only**; the
   analyzer still reads instruction bytes exclusively from the minidump. If the
   function start lies just before capture, forward-disassemble the exact
   build-matched binary from that symbol and choose a complete captured
   instruction boundary, comparing its bytes independently with the dump.
   If the selected entry or route is not captured, reject that candidate.

Exit: a small candidate manifest with the dump hash, exact entry/seed VAs, entry
justification, matching-identity check, capture-span map and tool/source versions. If no
candidate qualifies, publish the failed candidate audit and leave priority 1 open; do
not substitute a guessed entry.

## 2. Run the existing investigator path

Use the supported `ariadne-minidump` CLI with explicit `--entry`,
`--seed-exception-rip`, a pinned LLVM MC helper and a fresh `--output-dir`. Keep the
decoder target selected from the dump's platform. Freeze the command, dump and helper
identities before reviewing results. Do not raise limits merely to hide a resource
failure; record the old limit, reason and any reviewed increase.

Inspect `report.json`, `report.txt` and `report.dot` from the same query. Check,
independently of the renderer, the entry-to-seed local edges, each decoded instruction's
VA/length/bytes and contributing dump offsets, the seed's operand `uses`, reaching
origins **before** the seed, the slice membership, and every missing-seed, capture,
decode, control or effect issue. A symbolized label is context, not captured-byte
provenance. The expected producer must precede the seed through supported local edges; a
call-only target does not become a predecessor without an explicit root.

If a captured path stops at an unsupported form, retain the partial report and put its
exact byte/VA/opcode/operand/prefix and issue into
[priority 2](priority-2-path-driven-effects-plan.md). Re-run this same pinned candidate
after a reviewed rule is added; do not silently change the dump, entry or seed to obtain
a pass.

## 3. Qualify and retain the finding

Add an exact-artifact regression or a separate acceptance command for an external,
hash-checked fixture. Assert at least one relevant address-register producer in
the slice, expected reaching-origin and local-edge facts, and the unchanged gap
set. Include a negative
control where a wrong or unobserved entry cannot manufacture that predecessor; preserve
the existing Stage B exclusion of an unrelated write. Parse JSON, parse DOT with
Graphviz and compare identity, VAs, edges, slice and obligations across formats. Re-run
the existing minidump gate for its pinned fixtures and the separate hash-checked
real-capture acceptance command. Run the effect gate if priority 2 changed rules.
Hash the source snapshot before and after.

Retain a dated `priority-1-real-capture-validation.md` with candidate manifest, exact
command, output hashes or retained report paths, expected-versus-observed table, gate
results and remaining uncertainty. A useful partial report is valid diagnostic evidence,
but priority 1 completes only when an independently anchored earlier captured path
yields the nontrivial address-producer slice. Missing artifacts or symbols are
unavailable prerequisites, not passing tests.

## Scope controls

No PE/ELF reader, executable-byte fallback, reverse-from-RIP entry heuristic,
crash-time-register pruning of earlier paths, inferred interprocedural return, or formal
user64 case promotion is part of this plan. The existing 49-case gate remains a separate
long-term purpose.
