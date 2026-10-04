# Replace the unavailable BAP Windows workload

## Context and follow-up

**Status.** Completed capture/repin campaign, retained as historical evidence. Its 2,000 ms timing condition was later superseded by the user-authorized [unlimited policy](../docs/Ariadne/bap-unlimited-validation.md). Measurements and original verdicts below retain their historical meaning.

**Why this document exists.** The user confirmed that the original pinned
Windows dump no longer exists and requested a new Crashpad capture and pin.
The [BAP integration plan](bap-integration.md) previously blocked S4/S5 on that
artifact after completing the runner repairs and available-corpus refresh.

**What this document establishes.** A reproducible controlled Windows workload,
independent capture/query evidence, a durable input bundle and an explicit
replacement contract. Correct capture and performance acceptance remain separate.

**Where to go next.**

- [Unlimited timing policy](../docs/Ariadne/bap-unlimited-validation.md) — supersedes this campaign's former 2,000 ms condition by explicit user instruction.

- [Backend design](../docs/Ariadne/bap-semantic-backend-design.md) — defines the
  semantic boundary exercised by the new workload.
- [Replacement validation](../docs/Ariadne/bap-windows-repin-validation.md) — records
  the captured artifact and observed acceptance result.
- [Crashpad demo](../native/crashpad-demo/README.md) — provides the existing
  isolated native Windows build and owned-process capture mechanism.
- [Integration plan](bap-integration.md) — receives the final Stage 1 decision;
  Stage 2 implementation is outside this replacement task.

**What remains unresolved.** Stage 2 implementation is unstarted. Historical Priority 4/I4 remain separate. Latency remains measured, while the current BAP policy no longer imposes a timing ceiling.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Frozen replacement scope

The new case is a controlled application that crashes under native Windows x64
with `crashpad-nzsn` revision `7a884c25c84c46352fc6f16ef0a798ece2b77e84`.
Ariadne, LLVM MC and BAP analyze its captured bytes on Linux. Uploads stay disabled.
The existing default null-write demo remains available as its separate I5a case.

The explicit `bap-workload` profile contains exactly **98 local instruction
starts**, with no padding added merely to reach a count:

| Component | Instructions | Purpose |
| --- | ---: | --- |
| Argument and accumulator setup | 4 | Establish data and expected-checksum inputs. |
| Eight checksum rounds | 72 | Feed each array value through arithmetic and stack spill/reload dependencies. |
| Four-iteration loop | 6 | Exercise an indexed memory read and a local back edge. |
| Conditional diamond | 6 | Retain both possible local control paths in static recovery. |
| Final computation and fault | 10 | Cancel the independently computed checksum, define RCX, fault on a four-byte write, and retain the return instruction. |

Input words `{3, 5, 8, 13, 21, 34, 55, 89}` yield checksum `0x4bea2` under
unsigned 64-bit wraparound. The native caller supplies that independently checked
value. The assembly computes its negation plus the supplied value, then executes
the explicit producer `mov rcx, rax` and fault `mov dword ptr [rcx], 5`.
All checksum rounds feed the address computation. Crash registers are used only
to verify the controlled capture; they do not prune the static graph.

The capture registers the exact complete function range and input array.
Independent inspection must verify process/module identity, exception/context,
the full captured function bytes against the matching executable, all 98
instruction boundaries, exported entry/producer/fault/end labels and checksum.
No executable bytes may fill a hole in captured memory.

## Pin and evidence rules

- Preserve `priority-4-real-capture-case.json` byte-for-byte for historical
  Priority 4 and I4 consumers.
- Create `bap-windows-workload-case.json` with a new workload identity, capture
  kind, exact artifact/query hashes, independent witness and explicit replacement
  relation scoped to active BAP Stage 1 S4/S5.
- Retain the controlled dump, matching executable, witness and inspection/build
  records in a separately hashed input archive. The benchmark may materialize
  its pinned dump after verifying the archive, member size/type and content hash.
- Use workload schema v3 and aggregate schema v4. Replace `windows98*` with
  `windowsWorkload*`, and use `ARIADNE_BAP_WINDOWS_DUMP` for an explicit override.
  The old I4 environment variable must not select the new BAP case.
- Retain the **2,000 ms** CLI median limit, one warm-up and at least five release
  samples. Require exactly 98 recovered starts and the independently witnessed
  RCX producer in the slice and reaching definitions. An over-budget result
  remains an over-budget result; it does not invalidate a correct capture or
  authorize a budget change.

## Execution and acceptance

1. Implement the profile and independent byte/checksum inspector; exercise
   controlled negative cases for malformed or mismatched evidence.
2. Prepare the isolated pinned source, build with native Windows tools and
   generate a fresh partial-mode Crashpad dump. Inspect it before pinning.
3. Freeze the new manifest and durable input archive. Migrate only BAP's active
   workload consumers and their controlled tests.
4. Run the new exact query and release samples on Linux. Refresh affected BAP
   evidence; reuse other components only when their complete source/tool
   identities still match.
5. Retain the new campaign separately, update the active documentation and record
   the observed Stage 1/prerequisite result. Historical evidence remains intact.

All five steps are complete. The [delivery record](../docs/Ariadne/bap-windows-repin-validation.md)
retains 17 passing implementation gates, 68 controlled tests across both tiers,
the exact 98/99/90/0 result and the failed timing condition. The next performance
investigation should keep this pin fixed and examine the measured reference-decode
cost before proposing an optimization.
