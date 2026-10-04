# Crashpad-nzsn controlled crash demo

## Context and follow-up

**Status.** Both profiles were built and run on native Windows x64 on 2026-10-03.
The original partial/full null-write captures pass independent inspection and
Ariadne's zero-address assessment; their 1,500 ms assessment-CLI condition is not
met. The new BAP profile has a separately inspected and pinned partial capture.

**Why this document exists.** The [I5a design](../../docs/Ariadne/i5a-zero-address-design.md)
needed an independently controlled Windows capture in addition to synthetic fixtures.

**What this document establishes.** A small application embeds the `nzsn` fork's
client, starts its handler, disables uploads and deliberately writes through a null
pointer after recording its intended access. It offers the original `null-write`
profile and a Windows-only `bap-workload` checksum profile. Scripts reproduce the
isolated build, capture and independent verification.

**Where to go next.**

- [Delivery and evidence](../../docs/Ariadne/crashpad-demo-validation.md) gives
  actual captures, checks, source identities and measurements.
- [BAP workload replacement](../../docs/Ariadne/bap-windows-repin-validation.md)
  records the separate 98-instruction capture and active BAP pin.
- [I5a contracts](../../docs/Ariadne/i5a-contracts.md) explain what the resulting
  assessment can conclude.
- [Input guide](../../docs/Ariadne/modules/input.md) describes captured-byte provenance.

**What remains unresolved.** These are bounded controlled cases. Their respective
CLI timing conditions require separate measurements; the original Windows I4
capture is separate.
The Linux source path has not been built or run in this delivery. Full-dump flags
do not prove every process-memory read succeeded.

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
unchanged 2,000 ms qualification limit.

## Inspect and analyze

Keep raw dumps and the matching executable external or under ignored `tmp/`.
The inspector uses the Python standard library and an explicit byte oracle;
it does not obtain its expected conclusion from Ariadne or BAP.

```sh
python3 native/crashpad-demo/inspect_capture.py \
  --dump tmp/crashpad-demo/20261003/partial/capture.dmp \
  --witness tmp/crashpad-demo/20261003/partial/witness.json \
  --executable tmp/crashpad-demo/20261003/partial/ariadne_crash_demo.exe \
  --output tmp/crashpad-demo/20261003/partial/inspection-recheck.json
```

It checks Windows/AMD64 identity, access-violation parameters, valid exception
registers, process identity, module/PE agreement and unambiguous captured code.
Its `query` provides explicit entry and fault-site addresses for the regular
`ariadne-minidump --assess-zero-address` command. It accepts only the reviewed
`[rax]` and `[rcx]` six-byte store encodings used by this demo recipe.

With `build/`, `partial/` and `full/` records copied into one local directory,
the existing source/fixture-qualified analysis binaries can be exercised with:

```sh
python3 native/crashpad-demo/assess.py \
  --captures tmp/crashpad-demo/20261003 \
  --output tmp/crashpad-demo/20261003/measurements-recheck
```

This checks unchanged base reports, exact identities, repeatable assessments,
one warm-up/five repeats and the existing I5a timing criteria. An over-budget
run records its samples and exits nonzero; a valid capture is not thereby lost.
