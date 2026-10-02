# Repository instructions

## Rust layout

Keep Rust implementation, example and generated binding sources under `src/`,
and standalone test sources and fixtures under `tests/`. Use the root Cargo
manifest, lockfile and `target/` directory. After layout changes, run
`python3 tools/check_rust_layout.py`.

Give replay and mutation campaigns separate build subdirectories under `target/`;
shared executable names can otherwise cause one SUT's binary to be copied as another.

## Design and implementation plans

When creating or updating an implementation plan for an existing design, add
a direct relative link to the plan in the design document in the same change.
Name the stage if the plan covers only part of the design. Verify the link
resolves before finishing.
