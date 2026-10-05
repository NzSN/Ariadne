# I5a zero-address assessment contracts

## Context and follow-up

**Status.** Implemented and source/fixture-qualified in the working tree on
2026-10-03. Controlled Windows capture/answer checks pass. The later
[native refresh](i5a-native-qualification.md) qualifies both timing budgets and
both controlled capture modes under a read-only dependency snapshot.

**Why this document exists.** The [I5a design](i5a-zero-address-design.md) needs
valid fault-time observations to distinguish a zero access start from unknown
evidence, without converting producer alternatives into an executed history.

**What this document establishes.** The implemented interface, admission profile,
strict report, resource behavior and CLI modes for one numeric hypothesis.

**Where to go next.**

- [Native Windows demo](crashpad-demo-validation.md) supplies real partial/full
  captures and records its historical CLI timing miss.
- [Native qualification](i5a-native-qualification.md) records the passing native
  gates, controlled-capture acceptance and dependency-snapshot scope.
- [Delivery and validation](i5a-validation.md) records the exercised corpus,
  measurements and independently reported qualification tiers.
- [Source review](i5a-source-review.md) explains field layouts and the independent
  fixture oracle.
- [Execution plan](../../Plans/i5a-zero-address.md) defines implementation and
  separate qualification tiers.
- [First-question contracts](investigation-contracts.md) retain the distinct
  meaning of possible producers and their uncertainty.

**What remains unresolved.** The [active Windows I4 re-pin](i4-windows-repin-validation.md) remains over its unchanged CLI budget. Linux numeric
admission, root-cause/lifetime assertions and other hypotheses are not implemented.

The [documentation map](../documentation-map.md) is optional navigation.

## Interface and identity

```text
input::investigation::bind_fault_context(prepared, completed_analyzer)
  -> BoundFaultContext
investigation::assess_zero_address(bound, FaultAddressQuestion, AssessmentLimits)
  -> ZeroAddressAssessment
```

Binding reuses exact prepared/analyzer identity checks. Reader-owned exception
observations are retained separately from the public legacy snapshot metadata;
changing that metadata after capture fails binding. The bound value owns its
analysis/context and exposes no mutation or arbitrary-register-map constructor.
The original analyzer and reports are unchanged by assessment.

Schema: `ariadne.zero-address-assessment/v1`.
Profile: `windows-amd64-av-scalar-mov-v1`.
Scope binds snapshot/artifact/query/request/semantic identity, selected question,
the context digest and profile. Full context evidence must match its digest;
truncated inputs cannot support a definite conclusion.

## Evidence and admission

The reader retains exception/descriptor fields, defined parameters, context flags
and valid GPR/RIP/RFLAGS observations with artifact-relative offsets, lengths,
raw field bytes and SHA-256 identities. Record/context extents have separate
digests. RIP/RSP/RFLAGS require CONTROL; other GPRs require INTEGER. Thread-list
registers are never a fallback. These are captured observations, not proof of
hardware exception origin or temporal coherence.

The assessment requires Windows AMD64, a supported read/write access violation,
non-chained record, supported exception flags, valid matching RIP and exception
location, a reached captured site and admitted BAP address evidence. Initial
forms are the reviewed scalar `MOV32rm`, `MOV64rm`, `MOV32mr`, `MOV64mr`,
`MOV32mi` and `MOV64mi32`, with matching access width/role. Guarded legacy prefixes,
multiple/conditional accesses and unsupported projections/shapes are excluded.

Only required valid GPR values enter the existing modular 64-bit affine
expression. Its RIP-relative constant is used directly. The nonwrapping access
span must lie below `0x0000800000000000`; the reported data byte must lie in it
and its operation kind must agree. The exception-location field is never used
as the inaccessible-data parameter.

## Result and limits

| Conclusion | Meaning |
| --- | --- |
| `consistent_with_evidence` | All premises/admission checks hold and the access starts at zero. |
| `refuted_under_premises` | All premises/admission checks hold and its start is nonzero. This does not rule out a zero base plus displacement. |
| `unknown` | Missing, unsupported, conflicting or budget-omitted evidence prevents the assessment. |

The result retains observations, instruction/address evidence, used register
names, the computed candidate and reported data address when justified, typed
claims, explicit premises and per-gap evidence requirements. A computed candidate
may remain diagnostic when subsequent span/data-address consistency fails; the
conclusion is still unknown. Unadmitted context/form evidence produces no numeric
fact. No result asserts null-pointer causation, lifetime or a predecessor path.

Default limits are 32 evidence records and 32 claims. Source extents, individual
field observations and the selected instruction count as evidence records. Zero
and exhausted limits produce unknown/truncated answers with valid references.
Question-site/access-index errors remain errors independently of budgets.

Strict decoding rejects duplicate/unknown fields, noncanonical values, invalid
source spans/bytes/digests, wrong identities, dangling or altered claim records,
missing premises and conclusions inconsistent with recomputed admission and
arithmetic. This checks internal evidence consistency, not authenticity of an
arbitrary externally supplied minidump. The first explanation's v1 schema remains
independent.

## CLI and publication

```sh
target/release/ariadne-minidump tests/input/fixtures/i5a/zero-store.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 401000 \
  --assess-zero-address 401000 --memory-access 0 \
  --assessment-only --format json
```

For a bundle, replace `--assessment-only --format json` with
`--output-dir NEW_DIR`. The original three reports and
`zero-address-assessment.{txt,json,dot}` are staged and published together.
Existing output paths are rejected. Unknown is a valid published answer;
invalid options, binding, schema or infrastructure failures produce no complete
bundle. The question adds a seed, never a discovery root.

Assessment and explanation question flags are mutually exclusive in this first
CLI delivery. Assessment cannot be combined with stateflow. Assessment-only mode
requires `--format`; combined directory mode requires a new output directory.
Library callers can separately obtain producer and numeric results for the same
bound query.

## Qualification entry points

```sh
python3 tests/input/fixtures/make_i5a.py --check
cargo test --offline --locked --release --test input_i5a -- --include-ignored
python3 tools/check_i5a.py
```

Native checks require the pinned BAP/LLVM helpers and Graphviz. The
[fixture measurement contract](../../tests/input/fixtures/i5a/performance.json)
freezes one warm-up/five repeats, a 10 ms combined phase median and a 1,500 ms
assessment-CLI median for its small synthetic workloads. These are separate from
the unchanged I4 timing conditions on its independently re-pinned case; they make no universal scale claim.
