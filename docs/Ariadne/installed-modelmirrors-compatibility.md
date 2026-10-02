# Installed ModelMirrors and MirrorRust compatibility

## Context and follow-up

**Status.** Historical installed-tool compatibility; initial fixtures are narrower than later Stage E completion.

**Why this document exists.** [Replay workflow](../../mbt/README.md) depends on negotiated compiler, server and client behavior.

**What this document establishes.** The recorded local stdio run checked negotiated replay, digest rejection and cleanup against exact installed-server/client identities. It was an initial fixture tier, not the later complete Stage E campaign.

**Where to go next.**

- [Later Stage E completion](stage-e-completion.md) — addresses the broader generated-scenario and report coverage left open here.
- [Current replay procedure](../../mbt/stage-e/README.md) — defines how to recheck the actual toolchain.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. Later Stage E completion addresses the broader scenario/mutation/report gap stated in the original record.

For the wider context, see the optional [documentation map](../documentation-map.md).

Checked **2026-10-01** against `/home/nzsn/.local/bin/ModelMirrors` and the
MirrorRust checkout used by Ariadne's core and Stage E integration.
The [retained validation record](../../evidence/Ariadne/installed-modelmirrors-compatibility-validation.json)
contains exact commands, evaluator hashes, server/client identities and results.

The installed server is compatible for the exercised **local stdio negotiated
replay** path:

| Check | Result |
| --- | --- |
| Core correct evaluator | 12 complete traces, 168 matched states, action/pair coverage and one actual port drop |
| Stage E machine-state | Two complete fixture traces, 10 matched observations and one actual port drop |
| Stage E LLVM IR | Two complete fixture traces, 10 matched observations and one actual port drop |
| Wrong semantic digests | All three interfaces reject before any port factory or observation |
| Five existing core engine mutants | Genuine model mismatches at the expected actions, with port cleanup |

All **11 checks** passed in this recorded run. Its Stage E fixture coverage
was bounded; the broader scenario/mutation/report gap was subsequently addressed
by [Stage E completion](stage-e-completion.md). That later campaign remains
finite and does not broaden this installed-tool record retroactively.

## Identity and version boundary

- Installed executable SHA-256:
  `e5eab73138ad380b039e3312f6e9d860bbd99126c13a3bb84b90f206dacb41dd`.
- Its `--version` output is **`Mirrors 0.0.3`**.
- Local Mirrors source tag **`v0.0.3.1`** resolves to
  `1a069cd3e34d7bfea272e3ee7e10f51acedcc7cb`.
- MirrorRust HEAD is `a3f826f6590bea1bbbffe095353bf9a104c4c1d1`; its runtime
  sources and Cargo manifest have no diff from the documented client tag
  `v0.0.1.0` (`a51149e6832d9fa2ead232c1f7157294a72557af`).

The product-version string and source tag are distinct identifiers. The local
Mirrors checkout is dirty, and its current build has a different hash from
the installed executable. Exact clean-tag build provenance is therefore
unverified. These checks establish compatibility of the **actual installed
binary**, identified by its hash, with the recorded client/evaluators.

The compiler-generated bindings and checked corpora retain their existing
prepared-compiler identities. This verification selects the installed runtime
server; it does not qualify a compiler/corpus migration or TCP/mTLS transport.

The core gate leaves mutation artifacts in its target directory. This check
uses the retained correct evaluator and each retained mutant, validates their
hashes against the previous integration record, and records their actual
commands. An initial probe of the target-directory binary encountered the
last intentional mutant; it was not counted as a compatibility failure.
