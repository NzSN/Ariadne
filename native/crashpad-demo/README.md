# Crashpad-nzsn controlled crash demo

## Context and follow-up

**Status.** Both profiles were built and run on native Windows x64 on 2026-10-03.
The original partial/full null-write captures pass independent inspection and
Ariadne's zero-address assessment. Their historical assessment-CLI medians
exceeded 1,500 ms. The 2026-10-05 native-default qualification passes all 14 fixture gates and
both controlled capture modes under the unchanged CLI and phase budgets, using
the recorded read-only dependency snapshot. The BAP profile has a separately inspected and
pinned partial capture.

**Why this document exists.** The [I5a design](../../docs/Ariadne/i5a-zero-address-design.md)
needed an independently controlled Windows capture in addition to synthetic fixtures.

**What this document establishes.** A small application embeds the `nzsn` fork's
client, starts its handler, disables uploads and deliberately writes through a null
pointer after recording its intended access. It offers the original `null-write`
profile and a Windows-only `bap-workload` checksum profile. Scripts reproduce the
isolated build, capture and independent verification.

**Where to go next.**

- [Delivery and evidence](../../docs/Ariadne/crashpad-demo-validation.md) gives
  the original captures, checks, source identities and historical measurements.
- [Native I5a qualification](../../docs/Ariadne/i5a-native-qualification.md)
  records the passing native measurements, aggregate gates and selected dependency snapshot.
- [BAP workload replacement](../../docs/Ariadne/bap-windows-repin-validation.md)
  records the separate 98-instruction capture and active BAP pin.
- [I5a contracts](../../docs/Ariadne/i5a-contracts.md) explain what the resulting
  assessment can conclude.
- [Input guide](../../docs/Ariadne/modules/input.md) describes captured-byte provenance.

**What remains unresolved.** Active Windows I4 performance and the separate BAP workload
retain their own contracts. Native I5a acceptance covers the recorded dependency
snapshot and captures; later changes need new qualification. The Linux source
path of this demo has not been built or run in this delivery. Full-dump flags do
not prove every process-memory read succeeded.

## Program and integration

`crash_demo.cc` initializes a fresh database with uploads disabled and launches
`CrashpadClient::StartHandler` synchronously, with no upload URL. It registers
the fault function's readable code range on Windows and a 4 MiB indirect-memory
budget. A new witness JSON is flushed before the call to `fault.cc`, which contains
a separate, non-inlined volatile four-byte store of `5` through its pointer argument.
The caller supplies null. A setup or witness-write failure exits before the store.

```text
ariadne_crash_demo.exe HANDLER NEW_DATABASE WITNESS_JSON [partial|full]
```

The compiled function was independently disassembled as `mov dword ptr [rcx], 5`
followed by `ret`. The witness records a function entry, not an assumed fault PC;
the inspector checks the actual exception address and executable bytes.

## Isolated source preparation

The original `~/Repos/crashpad-nzsn` checkout remains clean on `nzsn`, at
`7a884c25c84c46352fc6f16ef0a798ece2b77e84`. The recipe requires that revision and
archives it into a new build tree. It fetches the fork's exact mini_chromium,
googletest, LSS and zlib pins, plus its SHA-256-pinned Windows Clang package.

From the Ariadne root, with network access:

```sh
python3 native/crashpad-demo/prepare.py \
  --output target/crashpad-demo/prepared-replay \
  --cache target/crashpad-demo/dependency-cache
```

Three standalone compatibility headers bridge Chromium API moves to definitions
already present in mini_chromium: logging settings, numeric stream operators and
the `RandIntInclusive` name. A hash-guarded preparation adjustment limits the
mini_chromium Windows setup helper to installed x86/x64 toolchains and explicitly
rejects ARM64. The original fork's capture code is unchanged. Every prepared file,
compatibility header and build-only adjustment is recorded in `build-inputs.json`.

## Native Windows build and capture

Use native Windows Python, installed Visual Studio C++/Windows SDK tools, and
a depot_tools CIPD client. This tested host has Python 3.14, Visual Studio 18
Build Tools, MSVC libraries 14.51.36231 and Windows SDK 10.0.28000.0. Compilation
uses the fork-pinned Clang 20; installed MSVC itself cannot compile all fork code.

Example PowerShell commands for this WSL checkout; choose fresh output directories:

```powershell
$demo = "\\wsl.localhost\Ubuntu-NzSN\home\nzsn\Repos\Ariadne\native\crashpad-demo"
$prepared = "\\wsl.localhost\Ubuntu-NzSN\home\nzsn\Repos\Ariadne\target\crashpad-demo\prepared-replay"
$work = Join-Path $env:TEMP "ariadne-crashpad-demo-replay"
python "$demo\build_windows.py" --prepared $prepared --output $work `
  --cipd "D:\Programs\Google\depot_tools\.cipd_client.exe"
python "$demo\run_windows.py" --build "$work\build.json" `
  --output "$work\captures\partial" --mode partial --check-failures
python "$demo\run_windows.py" --build "$work\build.json" `
  --output "$work\captures\full" --mode full
```

The build checks repeated GN generation, explicit ARM64 rejection and source
stability, then records tool/binary hashes. The runner checks the owned process's
`0xc0000005` exit, matching witness PID, exactly one dump and disabled uploads.
`--check-failures` verifies that a missing handler and invalid mode produce neither
a witness nor a dump. Existing capture directories are rejected.

## Controlled BAP workload profile

Use `--profile bap-workload` with `run_windows.py` to select the separate Windows
AMD64 assembly workload. The default remains `--profile null-write`. A direct
demo invocation accepts `HANDLER NEW_DATABASE WITNESS_JSON [partial|full]
[null-write|bap-workload]`.

The BAP profile has exactly 98 instructions in 379 bytes. Eight checksum rounds,
an indexed-load loop, a conditional diamond and stack spill/reload operations
feed an explicit `mov rcx, rax` producer and null-write fault. The caller's
independent unsigned checksum is `0x4bea2`. The witness records the exact
entry/producer/fault/end addresses and input-array address. Crashpad captures
the complete function and array; executable bytes cannot fill captured holes.
The build records the pinned `llvm-ml.exe` assembler identity as well as the
compiler and linker identities.

The runner gives this profile only a minimal Windows environment, with temporary
files confined to the owned capture directory. Developer environment variables
are not inherited. The negative controls also cover an invalid profile.

```powershell
python "$demo\run_windows.py" --build "$work\build.json" `
  --output "$work\captures\bap-workload" --mode partial `
  --profile bap-workload --check-failures
```

After copying the capture outputs to Linux, run the independent inspector:

```sh
python3 native/crashpad-demo/inspect_workload.py \
  --dump CAPTURE_DIR/capture.dmp --witness CAPTURE_DIR/witness.json \
  --executable CAPTURE_DIR/ariadne_crash_demo.exe \
  --output CAPTURE_DIR/inspection.json
python3 -m unittest discover -s tools -p test_crashpad_workload_inspector.py
```

This inspector uses an explicit reviewed byte recipe and a separate integer
checksum calculation, plus raw minidump/PE parsing. It checks every instruction
boundary and short-branch target, full captured code, inputs, process/module
identity and fault context. It does not derive expected results from Ariadne or
BAP. The [replacement plan](../../Plans/bap-windows-repin.md) defines the pin and
its historical 2,000 ms criterion; the later
[unlimited BAP policy](../../docs/Ariadne/bap-unlimited-validation.md) supersedes
that timing ceiling. I5a keeps its separate 1,500 ms CLI criterion.

## Inspect and analyze

Keep raw dumps and the matching executable external or under ignored `tmp/`.
The inspector uses the Python standard library and an explicit byte oracle;
it does not obtain its expected conclusion from Ariadne or BAP.

```sh
mkdir -p target/crashpad-demo/inspection-recheck/partial \
  target/crashpad-demo/inspection-recheck/full
for mode in partial full; do
  python3 native/crashpad-demo/inspect_capture.py \
    --dump "tmp/crashpad-demo/20261003/$mode/capture.dmp" \
    --witness "tmp/crashpad-demo/20261003/$mode/witness.json" \
    --executable "tmp/crashpad-demo/20261003/$mode/ariadne_crash_demo.exe" \
    --output "target/crashpad-demo/inspection-recheck/$mode/inspection.json"
done
```

It checks Windows/AMD64 identity, access-violation parameters, valid exception
registers, process identity, module/PE agreement and unambiguous captured code.
Its `query` provides explicit entry and fault-site addresses for the regular
`ariadne-minidump --assess-zero-address` command. It accepts only the reviewed
`[rax]` and `[rcx]` six-byte store encodings used by this demo recipe.
Choose a new inspection directory for each rerun. Preserve the original
`partial/inspection.json`, `full/inspection.json`, build and capture records.
The new inspection records bind the current inspector; their nearby source-file
metadata does not identify the source that produced the historical executable.

With `build/`, `partial/` and `full/` records copied into one local directory,
first select the read-only dependency snapshot used for qualification, following
[the snapshot procedure](../../Plans/i5a-native-qualification.md#reproduce-with-a-stable-dependency-snapshot).
Use its path and the digest printed when it was created for all commands:

```sh
qualification_snapshot=target/qualification-deps/mirrorrust-recheck
qualification_sha=REPLACE_WITH_PRINTED_MANIFEST_SHA256
qualify() {
  python3 tools/with_mirrorrust_snapshot.py run \
    --snapshot "$qualification_snapshot" --sha256 "$qualification_sha" -- "$@"
}
```

Then produce a fresh source/fixture qualification:

```sh
qualify python3 tools/check_i5a.py
```

Continue only after that command succeeds and its printed `Report:` path names
a passing `ariadne.i5a-acceptance/v2` record with the exact current source/tool
inventory. The historical 12/14-gate partial record and the older v1 pass are ineligible.
The accepted native record uses the pinned environment; reruns must use the same
snapshot or obtain new matching evidence. Use the passing v2 path below:

```sh
i5a_fixture_record=/absolute/path/to/fresh/passing/report.json
qualify python3 native/crashpad-demo/assess.py \
  --captures tmp/crashpad-demo/20261003 \
  --source-fixture-record "$i5a_fixture_record" \
  --inspection-dir target/crashpad-demo/inspection-recheck \
  --output target/crashpad-demo/native-assessment-recheck
```

Both `--source-fixture-record` and `--inspection-dir` are required. This checks
historical build/capture links, fresh inspection identities, unchanged base
reports, native backend receipts
and repeatable assessments. Separate untimed default/explicit-native runs must
match all reports. One warm-up/five repeats retain the 10 ms combined phase and
1,500 ms assessment-CLI median limits. Both capture modes and source/tool/input
stability must pass. An over-budget run records its samples and exits nonzero;
the historical original-Windows I4 flag remains false in every I5a result.
The [separate active I4 re-pin](../../docs/Ariadne/i4-windows-repin-validation.md)
uses the 98-instruction workload and remains over its fixed CLI budget.
