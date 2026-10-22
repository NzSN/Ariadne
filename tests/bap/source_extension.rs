use super::*;
use serde_json::json;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Temporary(PathBuf);
impl Temporary {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "ariadne-source-extension-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Temporary {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn response() -> serde_json::Value {
    json!({"schema":"ariadne.bap-source-flags/v1", "build_id":"a".repeat(64),
        "target":"windows-amd64", "snapshot":"b".repeat(64), "va":"0x0000000000401000",
        "bytes":"f8", "length":1, "bil":[{"kind":"move", "var":{
            "name":"CF","index":0,"virtual":false,"width":1,"type":"imm"},
            "value":{"kind":"int","value":"0:1u"}}]})
}
fn observer() -> SourceExtension {
    SourceExtension {
        directory: PathBuf::new(),
        manifest_hash: String::new(),
        executable_hash: String::new(),
        build_id: "a".repeat(64),
    }
}
fn bind(value: serde_json::Value) -> Result<Vec<Stmt>, Error> {
    observer().bind_response(
        serde_json::from_value(value)?,
        "windows-amd64",
        &"b".repeat(64),
        "0x0000000000401000",
        "f8",
    )
}

#[test]
fn exact_flag_scope_excludes_prefixes_neighbors_and_multiple_instructions() {
    for byte in [0xf5, 0xf8, 0xf9, 0xfd] {
        assert!(SourceExtension::supports(&[byte]));
    }
    for bytes in [
        &[][..],
        &[0xfc],
        &[0xfa],
        &[0xfb],
        &[0xf0, 0xf8],
        &[0xf8, 0x90],
    ] {
        assert!(!SourceExtension::supports(bytes));
    }
}

#[test]
fn typed_output_requires_exact_query_identity_and_qualified_flag_shape() {
    assert!(bind(response()).is_ok());
    for (key, value) in [
        ("schema", json!("other")),
        ("build_id", json!("0".repeat(64))),
        ("target", json!("linux-amd64")),
        ("snapshot", json!("c".repeat(64))),
        ("va", json!("0x0000000000401001")),
        ("bytes", json!("f9")),
        ("length", json!(2)),
        ("bil", json!([])),
    ] {
        let mut changed = response();
        changed[key] = value;
        assert!(bind(changed).is_err(), "{key}");
    }
    let mut changed = response();
    changed["bil"][0]["var"]["name"] = json!("DF");
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["bil"][0]["value"]["value"] = json!("1:1u");
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["bil"][0]["var"]["width"] = json!(64);
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["unexpected"] = json!(true);
    assert!(bind(changed).is_err());
}

#[test]
fn malformed_manifest_is_not_a_user_supplied_semantic_certificate() {
    let work = Temporary::new();
    for bytes in [b"{}".as_slice(), b"not-json", LOCK] {
        std::fs::write(work.0.join("manifest.json"), bytes).unwrap();
        assert!(SourceExtension::load(&work.0).is_err());
    }
}

#[cfg(unix)]
#[test]
fn child_output_size_exit_and_time_limits_are_enforced() {
    use std::os::unix::fs::PermissionsExt;
    for script in [
        "print('x' * 5000)",
        "raise SystemExit(7)",
        "import time; time.sleep(5)",
        "print('{}\\n{}')",
    ] {
        let work = Temporary::new();
        std::fs::write(work.0.join("manifest.json"), b"unit transport fixture").unwrap();
        let executable = work.0.join("flag-lift");
        std::fs::write(&executable, format!("#!/usr/bin/python3\n{script}\n")).unwrap();
        std::fs::set_permissions(&executable, std::fs::Permissions::from_mode(0o755)).unwrap();
        let extension = SourceExtension {
            directory: work.0.clone(),
            manifest_hash: file_hash(&work.0.join("manifest.json"), 64 * 1024).unwrap(),
            executable_hash: file_hash(&executable, 256 * 1024 * 1024).unwrap(),
            build_id: "a".repeat(64),
        };
        let start = Instant::now();
        assert!(
            extension
                .lift(
                    "windows-amd64",
                    "test",
                    0x401000,
                    &[0xf8],
                    Duration::from_millis(100)
                )
                .is_err()
        );
        assert!(start.elapsed() < Duration::from_secs(3));
    }
}

fn native_config() -> super::super::Config {
    super::super::Config::from_env().with_source_extension(
        std::env::var_os("ARIADNE_BAP_SOURCE_EXTENSION")
            .expect("set source extension directory for ignored native test")
            .into(),
    )
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc"))
}

#[test]
#[ignore = "requires pinned BAP/LLVM and explicitly selected source flag extension"]
fn native_four_flags_and_unchanged_corpus_use_actual_source_bil() {
    use crate::bap::Backend;
    use crate::effects::PreparationOptions;
    use crate::llvm_mc::DecoderTarget;
    let config = native_config();
    let mut original = config.clone();
    original.source_extension = None;
    let mut baseline = Backend::new(original, &decoder()).unwrap();
    let mut extended = Backend::new(config, &decoder()).unwrap();
    let options = PreparationOptions::default();
    for (byte, flag, reads) in [
        (0xf8, "flag:cf", false),
        (0xf9, "flag:cf", false),
        (0xf5, "flag:cf", true),
        (0xfd, "flag:df", false),
    ] {
        let va = 0x401000 + byte as u64 * 16;
        let candidates = [(va, Some(vec![byte]))].into();
        let before = baseline
            .prepare(
                "flag-native",
                &candidates,
                &options,
                DecoderTarget::WindowsAmd64,
            )
            .unwrap();
        let after = extended
            .prepare(
                "flag-native",
                &candidates,
                &options,
                DecoderTarget::WindowsAmd64,
            )
            .unwrap();
        let a = &after.sites[&va];
        let b = &before.sites[&va];
        assert!(!b.decodable);
        assert!(a.decodable);
        assert_eq!(a.instruction.may_defs, [flag.into()].into());
        assert_eq!(a.instruction.must_defs, [flag.into()].into());
        assert_eq!(
            a.instruction.uses,
            if reads {
                [flag.into()].into()
            } else {
                Default::default()
            }
        );
        let semantic = a.evidence.semantic.as_ref().unwrap();
        assert_eq!(semantic.projection, PROFILE);
        assert_eq!(semantic.status, "projected");
        assert!(semantic.fallback.is_none());
        assert_ne!(
            semantic.runtime_sha256,
            b.evidence.semantic.as_ref().unwrap().runtime_sha256
        );
    }
    let corpus: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/corpus.json")).unwrap();
    for (index, case) in corpus["rows"].as_array().unwrap().iter().enumerate() {
        let hex = case["prefix"].as_str().unwrap();
        let bytes: Vec<_> = (0..hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
            .collect();
        if SourceExtension::supports(&bytes) {
            continue;
        }
        let va = 0x500000 + index as u64 * 32;
        let candidates = [(va, Some(bytes))].into();
        let before = baseline
            .prepare(
                "flag-native",
                &candidates,
                &options,
                DecoderTarget::WindowsAmd64,
            )
            .unwrap();
        let after = extended
            .prepare(
                "flag-native",
                &candidates,
                &options,
                DecoderTarget::WindowsAmd64,
            )
            .unwrap();
        let a = &after.sites[&va];
        let b = &before.sites[&va];
        assert_eq!(a.instruction, b.instruction, "{}", case["name"]);
        assert_eq!(a.decodable, b.decodable);
        assert_eq!(a.gaps, b.gaps);
        let mut expected = b.evidence.clone();
        expected.rule = expected.rule.map(|rule| {
            if rule == crate::bap::PROJECTION {
                PROFILE.into()
            } else {
                rule
            }
        });
        let semantic = expected.semantic.as_mut().unwrap();
        semantic.projection = PROFILE.into();
        semantic.runtime_sha256 = a.evidence.semantic.as_ref().unwrap().runtime_sha256.clone();
        assert_eq!(a.evidence, expected, "{}", case["name"]);
    }
    baseline.finish().unwrap();
    extended.finish().unwrap();
}

#[test]
#[ignore = "requires pinned BAP/LLVM and explicitly selected source flag extension"]
fn native_composed_modes_are_refused_and_tampering_poisoned() {
    use crate::bap::Backend;
    use crate::effects::PreparationOptions;
    use crate::llvm_mc::DecoderTarget;
    let config = native_config();
    for mode in 0..3 {
        let mut backend = Backend::new(config.clone(), &decoder()).unwrap();
        match mode {
            0 => backend.enable_guard_admission(),
            1 => backend.enable_target_resolution(),
            _ => backend.enable_refinement(),
        }
        assert!(
            backend
                .prepare(
                    "modes",
                    &Default::default(),
                    &PreparationOptions::default(),
                    DecoderTarget::WindowsAmd64
                )
                .is_err()
        );
        assert!(backend.finish().is_err());
    }
    let work = Temporary::new();
    let directory = config.source_extension.as_ref().unwrap();
    for name in ["manifest.json", "flag-lift"] {
        std::fs::copy(directory.join(name), work.0.join(name)).unwrap();
    }
    let mut config = config;
    config.source_extension = Some(work.0.clone());
    let mut backend = Backend::new(config, &decoder()).unwrap();
    let manifest = std::fs::read(work.0.join("manifest.json")).unwrap();
    std::fs::write(work.0.join("manifest.json"), b"{}").unwrap();
    assert!(SourceExtension::load(&work.0).is_err());
    let candidates = [(0x401000, Some(vec![0xf8]))].into();
    assert!(
        backend
            .prepare(
                "tamper",
                &candidates,
                &PreparationOptions::default(),
                DecoderTarget::WindowsAmd64
            )
            .is_err()
    );
    std::fs::write(work.0.join("manifest.json"), manifest).unwrap();
    assert!(
        backend
            .prepare(
                "tamper",
                &candidates,
                &PreparationOptions::default(),
                DecoderTarget::WindowsAmd64
            )
            .is_err()
    );
    assert!(backend.finish().is_err());
}

#[cfg(feature = "input")]
#[test]
#[ignore = "requires current native core, BAP/LLVM and explicitly selected source flag extension"]
fn native_capture_v9_matches_rust_and_binds_opaque_sites() {
    use crate::AnalysisView;
    use crate::bap::core_adapter::NativeAnalyzer;
    use crate::bap::core_session::CoreConfig;
    use crate::effects::PreparationOptions;
    use crate::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
    for (fixture, entry) in [
        (
            include_bytes!("../input/fixtures/bap_precision_windows.dmp").as_slice(),
            0x00007ff700001000,
        ),
        (
            include_bytes!("../input/fixtures/bap_precision_linux.dmp").as_slice(),
            0x401000,
        ),
    ] {
        // Reuse the generated minidump container and replace only its unique code
        // capture. This test makes no claim about the synthetic exception's cause.
        let original = [
            0x48, 0x89, 0xd8, 0x48, 0xf7, 0xd0, 0xc7, 0x00, 0x05, 0, 0, 0, 0xc3,
        ];
        let offsets: Vec<_> = fixture
            .windows(original.len())
            .enumerate()
            .filter_map(|(offset, bytes)| (bytes == original).then_some(offset))
            .collect();
        assert_eq!(offsets.len(), 1);
        let mut dump = fixture.to_vec();
        dump[offsets[0]..offsets[0] + original.len()].fill(0x90);
        dump[offsets[0]..offsets[0] + 7]
            .copy_from_slice(&[0xf8, 0xf9, 0xf5, 0xfd, 0x0f, 0xa2, 0xc3]);
        let snapshot = FileSnapshot::from_minidump_bytes(dump, OpenLimits::default()).unwrap();
        let prepared = snapshot
            .prepare_with_bap(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [entry + 2].into(),
                },
                &decoder(),
                &native_config(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        assert_eq!(prepared.prepared.identity.ruleset, PROFILE);
        assert_eq!(
            prepared.prepared.instructions[&(entry + 4)]
                .semantic
                .as_ref()
                .unwrap()
                .status,
            "opaque-ordinary"
        );
        let rust = crate::CompletedAnalysis::from_analyzer(
            crate::Analyzer::new(prepared.prepared.request.clone()).unwrap(),
        );
        let config = CoreConfig::from_directory(
            std::env::var_os("ARIADNE_BAP_CORE_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| {
                    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
                }),
        );
        let native = NativeAnalyzer::from_capture(&config, "source-flags-capture", &prepared)
            .unwrap()
            .complete()
            .unwrap();
        assert_eq!(native.state(), rust.state());
        assert_eq!(native.state().slice, [entry + 1, entry + 2].into());
        crate::input::investigation::bind_investigation(&prepared, &native).unwrap();
        // A saved target-resolution envelope must not acquire v9 acceptance
        // through the shared captured-input validator, including legacy dispatch.
        for schema in [
            "ariadne.indirect-target-resolution/v3",
            "ariadne.indirect-target-resolution/v2",
        ] {
            let mut wire = NativeAnalyzer::capture_wire_for_test(&prepared).unwrap();
            wire["target_resolution"] = json!({"schema": schema});
            let result = crate::bap::core_session::CoreSession::start_profile(
                &config,
                "source-flags-target-refusal",
                &prepared.prepared.request.snapshot_id,
                crate::bap::core_protocol::TARGET_PROFILE,
                &wire,
            );
            let message = match result {
                Ok((_session, response)) => {
                    response
                        .error
                        .expect("v9 target input must be rejected")
                        .message
                }
                Err(error) => error.to_string(),
            };
            assert!(
                message.contains("source flag extension does not admit target resolution")
                    || message == "core partial frame/EOF",
                "{message}"
            );
        }
    }
}
