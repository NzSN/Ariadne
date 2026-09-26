//! External Breakpad-produced artifacts are supplied explicitly, not copied or
//! downloaded by tests. Exact hashes prevent a changed fixture inheriting evidence.
use ariadne::effects::PreparationOptions;
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, Platform, PrepareLimits};
#[test]
#[ignore = "requires ARIADNE_REAL_DUMPS and pinned decoder"]
fn real_windows_and_linux_crash_artifacts_preserve_bytes_and_report_semantic_gaps() {
    let root = std::path::PathBuf::from(
        std::env::var_os("ARIADNE_REAL_DUMPS").expect("external fixture directory required"),
    );
    let decoder =
        std::path::PathBuf::from(std::env::var_os("ARIADNE_LLVM_MC").expect("decoder required"));
    for (name, hash, platform, rip, modules, threads) in [
        (
            "linux_null_dereference.dmp",
            "1d82d1d98bb46fb9aa3498fce733e724e9b501824f8b8a36de22066d6d4bca33",
            Platform::Linux,
            0x401f26,
            8,
            1,
        ),
        (
            "write_av_non_canonical.dmp",
            "7012f0b943f5eacf681bcb29fc2766b75b87da1664280eaadc5dfa024f0a3abf",
            Platform::Windows,
            0x7ff738721331,
            15,
            2,
        ),
    ] {
        let s = FileSnapshot::open_minidump(root.join(name), OpenLimits::default()).unwrap();
        assert_eq!(s.metadata().artifact_sha256, hash);
        assert_eq!(s.metadata().platform, platform);
        assert_eq!(s.metadata().modules.len(), modules);
        assert_eq!(s.metadata().threads.len(), threads);
        assert_eq!(
            s.metadata()
                .exception
                .as_ref()
                .unwrap()
                .registers
                .get("rip"),
            Some(&rip)
        );
        let p = s
            .prepare(
                &AnalysisQuery {
                    entry_points: [rip].into(),
                    slice_seeds: [rip].into(),
                },
                &decoder,
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        assert_eq!(p.reads[&rip].bytes.len(), 15);
        assert_eq!(p.materialization.attempted, [rip].into());
        let r = ariadne::analyze(p.prepared.request).unwrap();
        // These captured crash instructions are currently outside the reviewed
        // effects registry. Do not report parser/decoder execution as ISA coverage.
        assert!(r.state.decoded.is_empty());
        assert_eq!(r.state.obligations.len(), 1);
    }
}
