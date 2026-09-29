# Ariadne assurance priorities

Decision recorded **2026-09-29** after the first
[Stage D checkpoint](stage-d-progress.md). Ariadne's practical delivery is an
evidence-bounded **Windows/Linux AMD64 minidump → local graph → possible value
origins → backward slice → report** workflow. The
[49-case register-core acceptance plan](stage-d-register-core-implementation-plan.md)
is retained as a **long-term formal research purpose**, not a prerequisite
for using or improving that workflow.

## Claims remain separate

| Assurance level | What a passing result supports | What it does not support |
| --- | --- | --- |
| Input and decoder | Exact captured bytes, virtual addresses, provenance, pinned LLVM MC observations and explicit missing/conflicting data | Faithful CPU execution or historical path reconstruction |
| Reviewed analyzer effects | Source-reviewed `uses`, possible writes, justified definite replacements and conservative control for exact decoded shapes, with negative controls | A complete AMD64 instruction step, fault priority or proof that a crashing store committed |
| Formal user64 case | A source-hash-bound TLA+/Lean instruction-step claim for that exact form/profile case after all eight obligations close | Unlisted forms, a verified Rust ISA executor or automatic decoder-to-form correspondence |

The no-trust `UnknownInstructionFallback` remains the default for unsupported
forms. The formal `amd64-user64-v1` profile, its 49/72/156 case inventory,
coverage ledger, source hashes and `--require-milestone` checks keep their
existing meaning. **0/49 accepted** is an honest formal status, not a failure
of the delivered minidump reader, renderer or conservative analyzer.

## Practical priority queue and status

| Priority | Deliverable | Acceptance evidence |
| --- | --- | --- |
| [1. Representative real-capture investigation](priority-1-real-capture-plan.md) — delivered for one controlled Chromium/Linux crash | Run the supported CLI on a hash-pinned real Chromium/Electron Windows or Linux minidump with an independently established earlier captured entry and crash-IP seed. Where capture lacks that path, report the gap; do not infer a function entry by decoding backward from RIP or supply executable bytes from a companion file. | The [qualified case](priority-1-real-capture-validation.md) links a possible address producer to captured bytes, a matched-build entry witness, reviewed effects and explicit uncertainty. The tool-produced Stage B fixture remains a separate regression. |
| [2. Path-driven effect coverage](priority-2-path-driven-effects-plan.md) — no-change for the first real path | Inventory the exact unsupported instructions that stop real investigations. Add only source-reviewed opcode/operand/prefix bindings needed on those paths, preserving weak memory updates, flags/alias uncertainty and unknown control. | The [first case review](priority-2-effects-validation.md) found no source-reviewable binding needed to reach its possible producer; opaque calls remain. New real paths may reopen coverage work. |
| [3. Investigator presentation and release examples](priority-3-investigator-presentation-plan.md) — delivered | Make decoded instruction, exact bytes, normalized operands, rule quality and provenance easy to scan alongside possible origins and gaps. Retain versioned JSON as the machine contract and publish reproducible CLI examples for both platforms. | The [validation](priority-3-presentation-validation.md) confirms a readable overview, Linux/Windows [examples](minidump-investigator-examples.md), Graphviz parsing, partial-report behavior and unchanged JSON/DOT semantics. |
| [4. Workload-sized performance decision](priority-4-workload-performance-plan.md) — measured, qualification open | Measure larger representative captured graphs and dense aliases through the same CLI path. Optimize only a demonstrated bottleneck, such as predecessor scans, without changing the analyzer's observable schedule or result. | The [first measurement](priority-4-performance-validation.md) has a 34-node real query, bounded synthetic data and a 512-node timeout. A qualifying 64-node real capture is still needed. |

The designs behind these plans are the
[Priority 1 real-capture design](priority-1-real-capture-design.md),
[structured-operand/effect design](operand-effects-design.md) for Priority 2,
[Priority 3 presentation design](priority-3-investigator-presentation-design.md),
and [Priority 4 workload-performance design](priority-4-workload-performance-design.md).

Priority 1 was qualified on **2026-09-29** for one real, controlled Chromium
renderer crash. The independently anchored entry is a complete captured
instruction reached by forward decoding from a matching binary's function
symbol. Its slice is a set of possible origins, not an execution trace.
Priority 2 has a scoped no-change decision for that path, Priority 3 is
delivered, and Priority 4 remains open: the 34-node case does not satisfy its
larger-workload target.

The separate machine-state and directly supplied LLVM IR paths can advance
when a concrete investigation needs them; their generated model-based replay
and result envelopes remain independent acceptance work. A universal Rust
refinement proof and the full 49-case ISA campaign are long-term research
objectives. PE/ELF image and ELF core readers remain deferred under the
current minidump-only scope.

## Initial historical-capture audit at decision time

The two already hash-pinned Breakpad dumps each have a 256-byte MemoryList
capture containing the crash RIP, with **128 contiguous captured bytes before
RIP**:

| Dump | Crash RIP | Captured code range | Module-relative RIP |
| --- | --- | --- | --- |
| Linux `linux_null_dereference.dmp` | `0x401f26` | `0x401ea6` through `0x401fa5` | `driver` + `0x1f26` |
| Windows `write_av_non_canonical.dmp` | `0x7ff738721331` | `0x7ff7387212b1` through `0x7ff7387213b0` | `crash.exe` + `0x1331` |

Byte availability did not by itself settle priority 1 for these two dumps. A
qualifying case needed an **independently established earlier instruction start**
from matching producer/symbol evidence or a new representative capture. No
matching symbol artifact for those two module names was found alongside the
current Breakpad test fixtures. A module filename or backward decode from RIP
is not adequate evidence for a function entry; companion files, if used for
entry evidence, must be identity-checked and must never fill missing dump
bytes under the current reader scope. The later qualified case uses a
separate controlled Chromium dump and an exact build-matched companion.
