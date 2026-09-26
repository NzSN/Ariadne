#![cfg(unix)]
// These helpers exercise the preparation interface's process/protocol errors.
// They are never counted as native decoder conformance evidence.
use ariadne::effects::{Catalogue, PreparationOptions};
use ariadne::llvm_mc::{AdapterError, ByteSnapshot};
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::sync::atomic::{AtomicUsize, Ordering};
static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Helper(PathBuf);
impl Helper {
    fn new(body: &str) -> Self {
        let path = std::env::temp_dir().join(format!(
            "ariadne-protocol-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        let program = path.join("decoder");
        std::fs::write(&program,format!("#!/bin/sh\nif [ \"$1\" = --protocol-version ]; then\n printf 'ariadne-llvm-mc 20.1.2 protocol 2\\n'\n exit 0\nfi\ncat >/dev/null\n{body}\n")).unwrap();
        std::fs::set_permissions(&program, std::fs::Permissions::from_mode(0o700)).unwrap();
        Self(path)
    }
    fn run(&self) -> Result<ariadne::effects::PreparedAnalysis, AdapterError> {
        let snapshot = ByteSnapshot {
            snapshot_id: "protocol".into(),
            file_backed: [(1, vec![0x90]), (2, vec![0x90])].into(),
            entry_points: [1].into(),
            locations: Catalogue.locations(),
            ..ByteSnapshot::default()
        };
        snapshot.prepare(&self.0.join("decoder"), &PreparationOptions::default())
    }
}
impl Drop for Helper {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).unwrap();
    }
}
const ONE: &str = "v2 NOOP 0 0 0 0 0 1 ok 1 ordinary -";
const TWO: &str = "v2 NOOP 0 0 0 0 0 2 ok 1 ordinary -";
#[test]
fn preparation_rejects_missing_duplicate_unexpected_and_contradictory_rows() {
    for output in [
        format!("{ONE}\n"),
        format!("{ONE}\n{ONE}\n"),
        format!("{ONE}\n{}\n", TWO.replace("2 ok", "9 ok")),
        format!("{ONE}\n{}\n", TWO.replace("ordinary -", "ordinary 10")),
        format!("{ONE}\n{TWO}"),
        format!("{ONE}\n{}\n", TWO.replace("ok 1", "ok 2")),
    ] {
        assert!(matches!(
            Helper::new(&format!("printf '%s' '{output}'")).run(),
            Err(AdapterError::DecoderProtocol(_))
        ));
    }
}
#[test]
fn preparation_bounds_both_output_streams_and_reports_process_failure() {
    for redirect in ["", ">&2"] {
        let result = Helper::new(&format!("printf '%s' '{}' {redirect}", "x".repeat(9000))).run();
        assert!(
            matches!(result,Err(AdapterError::DecoderProtocol(ref s)) if s.contains("limit")),
            "{result:?}"
        );
    }
    let result = Helper::new("printf 'native failure' >&2; exit 7").run();
    assert!(matches!(result,Err(AdapterError::DecoderFailure(ref s)) if s=="native failure"));
}
