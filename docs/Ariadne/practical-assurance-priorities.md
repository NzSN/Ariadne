# Ariadne assurance priorities

Updated **2026-10-02**: the independent instruction-step project is retired.
Ariadne's delivery is an evidence-bounded **Windows/Linux AMD64 minidump → local
graph → possible value origins → backward slice → report** workflow using BAP.
The [semantic assurance decision](semantic-assurance.md) supersedes the former
long-term Stage D commitment.

## Claims remain separate

| Assurance level | What a passing result supports | What it does not support |
| --- | --- | --- |
| Captured input and decode reference | Bytes, VAs, provenance and independent decode/control observations | Historical execution |
| BAP projection | Tested typed-BIL transport, dependencies, aliases and conservative effects for the exercised corpus | Universal lifter correctness or full ISA coverage |
| Analysis and investigation | Model-relative CFG/dataflow/slicing and evidence-bound claims | A root-cause or historical-path proof |

The practical queue below retains dated delivery results. Earlier LLVM-backed
Windows performance evidence does not qualify the current BAP path; the original
capture remains required for its separate workload gate.

## Practical priority queue and status

| Priority | Deliverable | Acceptance evidence |
| --- | --- | --- |
| [1. Representative real-capture investigation](../../Plans/completed/priority-1-real-capture-plan.md) — delivered for one controlled Chromium/Linux crash | Run the supported CLI on a hash-pinned real Chromium/Electron Windows or Linux minidump with an independently established earlier captured entry and crash-IP seed. Where capture lacks that path, report the gap; do not infer a function entry by decoding backward from RIP or supply executable bytes from a companion file. | The [qualified case](priority-1-real-capture-validation.md) links a possible address producer to captured bytes, a matched-build entry witness, reviewed effects and explicit uncertainty. The tool-produced Stage B fixture remains a separate regression. |
| [2. Path-driven effect coverage](../../Plans/completed/priority-2-path-driven-effects-plan.md) — delivered for the selected paths | Inventory the exact unsupported instructions that stop real investigations. Add only source-reviewed opcode/operand/prefix bindings needed on those paths, preserving weak memory updates, flags/alias uncertainty and unknown control. | The [first case review](priority-2-effects-validation.md) required no change. The larger Windows query gained [eight reviewed control-only bindings](priority-4-control-source-review.md), with opaque effects and negative controls. New paths may reopen coverage work. |
| [3. Investigator presentation and release examples](../../Plans/completed/priority-3-investigator-presentation-plan.md) — delivered | Make decoded instruction, exact bytes, normalized operands, rule quality and provenance easy to scan alongside possible origins and gaps. Retain versioned JSON as the machine contract and publish reproducible CLI examples for both platforms. | The [validation](priority-3-presentation-validation.md) confirms a readable overview, Linux/Windows [examples](minidump-investigator-examples.md), Graphviz parsing, partial-report behavior and unchanged JSON/DOT semantics. |
| [4. Workload-sized performance decision](../../Plans/completed/priority-4-workload-performance-plan.md) — delivered for one larger Windows capture | Measure larger representative captured graphs and dense aliases through the same CLI path. Optimize only a demonstrated bottleneck, such as predecessor scans, without changing the analyzer's observable schedule or result. | The [qualified measurement](priority-4-performance-validation.md) has 98 captured decoded instructions and a 19-node slice. CLI median improved from 3,846 to 1,788 ms against the fixed 2,000 ms budget. All 277 visible actions and text/DOT/JSON hashes are preserved; 128/256/512-node synthetic families complete. |

The designs behind these plans are the
[Priority 1 real-capture design](priority-1-real-capture-design.md),
[structured-operand/effect design](operand-effects-design.md) for Priority 2,
[Priority 3 presentation design](priority-3-investigator-presentation-design.md),
and [Priority 4 workload-performance design](priority-4-workload-performance-design.md).

Priority 1 was qualified on **2026-09-29** for one real, controlled Chromium
renderer crash. The independently anchored entry is a complete captured
instruction reached by forward decoding from a matching binary's function
symbol. Its slice is a set of possible origins, not an execution trace.
Priority 2 has a scoped no-change decision for that path and eight conservative
control bindings for the later Windows workload. Priority 3 is delivered.
Priority 4 was qualified on **2026-09-30** for a separately hash-pinned,
98-instruction Windows Electron query with a matched-PE entry witness. Its
measured optimization preserves the visible schedule and report bytes. The
median meets the budget; this is not a worst-case or universal scale guarantee.

The separate machine-state and directly supplied LLVM IR paths can advance
when a concrete investigation needs them; their generated model-based replay
and result envelopes remain independent acceptance work. A universal Rust
refinement proof remains a separate research boundary. The ISA campaign is retired. PE/ELF image and ELF core readers remain deferred under the
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
