use super::*;
use serde_json::{Value, json};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);

struct Temporary(PathBuf);
impl Temporary {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "ariadne-lods-source-{}-{}",
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

fn var(name: &str, width: usize) -> Value {
    json!({"name":name,"index":0,"virtual":false,"width":width,
        "type":if name == "mem" { "mem" } else { "imm" }})
}
fn read(name: &str, width: usize) -> Value {
    json!({"kind":"var","var":var(name, width)})
}
fn integer(number: usize, width: usize) -> Value {
    json!({"kind":"int","value":format!("{number}:{width}u")})
}
fn binary(op: i32, lhs: Value, rhs: Value) -> Value {
    json!({"kind":"binop","op":op,"lhs":lhs,"rhs":rhs})
}
fn response() -> Value {
    json!({"schema":"ariadne.bap-source-lods/v1", "build_id":"a".repeat(64),
    "target":"windows-amd64", "snapshot":"b".repeat(64), "va":"0x0000000000401000",
    "bytes":"f348ad", "length":3, "bil":[{"kind":"move","var":{"name":"loop-flag","index":0,"virtual":true,"width":1,"type":"imm"},"value":integer(1,1)},{"kind":"while",
        "condition":binary(4,read("RCX",64),integer(0,64)),
        "body":[
            {"kind":"move","var":var("RAX",64),"value":{"kind":"load","width":64,
                "mem":read("mem",0),"addr":read("RSI",64)}},
            {"kind":"move","var":var("RSI",64),
                "value":binary(18,read("RSI",64),integer(8,64))},
            {"kind":"move","var":var("RCX",64),
                "value":binary(17,read("RCX",64),integer(1,64))}
        ]}]})
}
fn observer() -> LodsSource {
    LodsSource {
        directory: PathBuf::new(),
        manifest_hash: String::new(),
        executable_hash: String::new(),
        build_id: "a".repeat(64),
    }
}
fn bind(value: Value) -> Result<Vec<Stmt>, Error> {
    observer().bind_response(
        serde_json::from_value(value)?,
        "windows-amd64",
        &"b".repeat(64),
        "0x0000000000401000",
        "f348ad",
    )
}

#[test]
fn response_binds_every_query_identity_field_and_exact_extent() {
    assert!(bind(response()).is_ok());
    for (key, value) in [
        ("schema", json!("other")),
        ("build_id", json!("0".repeat(64))),
        ("target", json!("linux-amd64")),
        ("snapshot", json!("c".repeat(64))),
        ("va", json!("0x0000000000401001")),
        ("bytes", json!("f3ac")),
        ("length", json!(2)),
        ("unexpected", json!(true)),
    ] {
        let mut changed = response();
        changed[key] = value;
        assert!(bind(changed).is_err(), "{key}");
    }
}

#[test]
fn empty_nonloop_nested_control_and_unknown_bil_are_refused() {
    for statements in [
        json!([]),
        json!([{"kind":"move","var":var("RAX",64),"value":integer(0,64)}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[]}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[
            {"kind":"while","condition":integer(1,1),"body":[]}]}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[
            {"kind":"jump","target":integer(0,64)}]}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[
            {"kind":"exception","number":13}]}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[{"kind":"special"}]}]),
        json!([{"kind":"while","condition":integer(1,1),"body":[{"kind":"unsupported"}]}]),
    ] {
        let mut changed = response();
        let mut full = vec![response()["bil"][0].clone()];
        full.extend(statements.as_array().unwrap().iter().cloned());
        changed["bil"] = full.into();
        assert!(bind(changed).is_err());
    }
    for expression in [
        json!({"kind":"unknown","reason":"unmodeled"}),
        json!({"kind":"unsupported"}),
        json!({"kind":"store","width":64,"mem":read("mem",0),
            "addr":read("RSI",64),"value":integer(0,64)}),
        binary(100, read("RAX", 64), integer(0, 64)),
    ] {
        let mut changed = response();
        changed["bil"][1]["body"][0]["value"] = expression;
        assert!(bind(changed).is_err());
    }
}

#[test]
fn architectural_namespace_type_and_temporary_bindings_are_checked() {
    for name in ["RIP", "RDI", "RSP", "ZF", "DF", "mem", "unknown"] {
        let mut changed = response();
        changed["bil"][1]["body"][0]["var"]["name"] = json!(name);
        assert!(bind(changed).is_err(), "{name}");
    }
    let mut changed = response();
    changed["bil"][1]["body"][0]["value"]["addr"] = read("RIP", 64);
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["bil"][1]["body"][0]["var"]["width"] = json!(63);
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["bil"][1]["condition"] = integer(1, 64);
    assert!(bind(changed).is_err());
    let mut changed = response();
    let mut temporary = var("unbound", 64);
    temporary["virtual"] = json!(true);
    changed["bil"][1]["body"][0]["value"] = json!({"kind":"var","var":temporary});
    assert!(bind(changed).is_err());
}

#[test]
fn loop_seed_must_be_one_initialized_virtual_bit_without_epilogue() {
    for (key, value) in [
        ("virtual", json!(false)),
        ("width", json!(64)),
        ("type", json!("mem")),
    ] {
        let mut changed = response();
        changed["bil"][0]["var"][key] = value;
        assert!(bind(changed).is_err());
    }
    let mut changed = response();
    changed["bil"][0]["value"] = integer(0, 1);
    assert!(bind(changed).is_err());
    let mut changed = response();
    changed["bil"].as_array_mut().unwrap().remove(0);
    assert!(bind(changed).is_err());
    let mut changed = response();
    let epilogue = json!({"kind":"move","var":var("RAX",64),"value":integer(0,64)});
    changed["bil"].as_array_mut().unwrap().push(epilogue);
    assert!(bind(changed).is_err());
}

#[test]
fn malformed_and_oversized_ast_fields_are_refused() {
    for (key, value) in [
        ("width", json!(0)),
        ("index", json!(-1)),
        ("name", json!("x".repeat(129))),
        ("type", json!("float")),
        ("virtual", json!("false")),
        ("unexpected", json!(0)),
    ] {
        let mut changed = response();
        changed["bil"][1]["body"][0]["var"][key] = value;
        assert!(bind(changed).is_err(), "{key}");
    }
    let mut changed = response();
    changed["bil"][1]["body"][0]["value"] = integer(1, 257);
    assert!(bind(changed).is_err());
    let mut changed = response();
    let mut expression = integer(1, 64);
    for _ in 0..66 {
        expression = binary(18, expression, integer(0, 64));
    }
    changed["bil"][1]["body"][0]["value"] = expression;
    assert!(bind(changed).is_err());
}

#[test]
fn measured_unsigned_cast_widens_lodsd_but_low_cast_cannot() {
    let mut changed = response();
    let mut load = changed["bil"][1]["body"][0]["value"].clone();
    load["width"] = json!(32);
    changed["bil"][1]["body"][0]["value"] = json!({"kind":"cast","op":3,"width":64,"arg":load});
    assert!(bind(changed.clone()).is_ok());
    changed["bil"][1]["body"][0]["value"]["op"] = json!(0);
    assert!(bind(changed).is_err());
}

#[test]
fn lods_forms_require_v14_and_explicit_two_bundle_configuration() {
    use crate::bap::{Config, SourceExtensionMode, repeated_strings};
    for (bytes, opcode) in [
        (&[0xf3, 0xac][..], "LODSB"),
        (&[0x66, 0xf3, 0xad][..], "LODSW"),
        (&[0xf3, 0xad][..], "LODSL"),
        (&[0xf3, 0x48, 0xad][..], "LODSQ"),
    ] {
        for earlier in [repeated_strings::PROFILE, repeated_strings::PROFILE13] {
            assert!(repeated_strings::opcode(bytes, earlier).is_none());
        }
        assert_eq!(
            repeated_strings::opcode(bytes, repeated_strings::PROFILE14),
            Some(opcode)
        );
        let mut neighbor = vec![0x67];
        neighbor.extend(bytes);
        assert!(repeated_strings::opcode(&neighbor, repeated_strings::PROFILE14).is_none());
        neighbor = bytes.to_vec();
        neighbor.push(0x90);
        assert!(repeated_strings::opcode(&neighbor, repeated_strings::PROFILE14).is_none());
    }
    let selected = Config::new("helper".into(), "runtime".into())
        .with_memory_repeated_strings_and_lods("flags".into(), "lods".into());
    assert!(selected.validate_source_mode().is_ok());
    let mut missing = selected.clone();
    missing.source_extension = None;
    assert!(missing.validate_source_mode().is_err());
    let mut missing = selected.clone();
    missing.lods_source_extension = None;
    assert!(missing.validate_source_mode().is_err());
    for mode in [
        SourceExtensionMode::Basic,
        SourceExtensionMode::Advanced,
        SourceExtensionMode::RepeatedStrings,
        SourceExtensionMode::MemoryRepeatedStrings,
    ] {
        let mut contradictory = selected.clone();
        contradictory.source_extension_mode = mode;
        assert!(contradictory.validate_source_mode().is_err());
    }
    for legacy in [
        selected.clone().with_source_extension("flags".into()),
        selected
            .clone()
            .with_advanced_source_extension("flags".into()),
        selected.clone().with_repeated_strings("flags".into()),
        selected.with_memory_repeated_strings("flags".into()),
    ] {
        assert!(legacy.lods_source_extension.is_none());
        assert!(legacy.validate_source_mode().is_ok());
    }
}

fn fixture_manifest(executable: &Path) -> Value {
    let sdk_bytes = include_bytes!("../../native/bap-core/sdk.lock.json");
    let sdk: Value = serde_json::from_slice(sdk_bytes).unwrap();
    let mut sources = serde_json::Map::new();
    for (name, bytes) in [
        (
            "lods_build.py",
            include_bytes!("../../native/bap/source-coverage/lods_build.py").as_slice(),
        ),
        (
            "lods_lift.ml",
            include_bytes!("../../native/bap/source-coverage/lods_lift.ml").as_slice(),
        ),
        (
            "lods_probe.ml",
            include_bytes!("../../native/bap/source-coverage/lods_probe.ml").as_slice(),
        ),
        (
            "lods.patch",
            include_bytes!("../../native/bap/source-coverage/lods.patch").as_slice(),
        ),
        (
            "build.py",
            include_bytes!("../../native/bap/source-coverage/build.py").as_slice(),
        ),
    ] {
        sources.insert(name.into(), crate::reports::sha256(bytes).into());
    }
    let modules: serde_json::Map<String, Value> = [
        "lib/x86_cpu/x86_types.ml",
        "lib/x86_cpu/x86_env.ml",
        "lib/x86_cpu/x86_cpu.ml",
        "plugins/x86/x86_utils.ml",
        "plugins/x86/x86_disasm.ml",
        "plugins/x86/x86_lifter.ml",
    ]
    .into_iter()
    .map(|name| (name.into(), "d".repeat(64).into()))
    .collect();
    let binding = json!({"base_revision":sdk["bapSourceRevision"],
        "source_archive_sha256":sdk["bapSourceArchive"]["sha256"],
        "sources":sources,"sdk_lock_sha256":crate::reports::sha256(sdk_bytes),
        "sdk_manifest_sha256":"e".repeat(64),"compiler_sha256":"f".repeat(64),
        "upstream_modules":modules,"patched_modules":modules});
    json!({"schema":"ariadne.bap-source-lods-build/v1", "profiles":["bap-bit-provenance-v14"],
        "runtime_role":"lods-source", "cases":CASES, "binding":binding,
        "build_id":crate::reports::sha256(&serde_json::to_vec(&binding).unwrap()),
        "executable":"lods-lift", "executable_sha256":file_hash(executable,MAX_EXECUTABLE).unwrap(),
        "max_response_bytes":MAX_RESPONSE})
}
fn write_manifest(work: &Temporary, manifest: &Value) -> Vec<u8> {
    let bytes = serde_json::to_vec(manifest).unwrap();
    std::fs::write(work.0.join("manifest.json"), &bytes).unwrap();
    serde_json::to_vec(&json!({"schema":"ariadne.bap-source-lods-lock/v1",
        "manifest_sha256":crate::reports::sha256(&bytes),
        "executable_sha256":manifest["executable_sha256"]}))
    .unwrap()
}

#[test]
fn manifest_pin_source_sdk_and_build_binding_are_independent_checks() {
    let work = Temporary::new();
    let executable = work.0.join("lods-lift");
    std::fs::write(&executable, b"fixture executable").unwrap();
    let manifest = fixture_manifest(&executable);
    let lock = write_manifest(&work, &manifest);
    assert!(LodsSource::load(&work.0, &lock).is_ok());
    std::fs::write(work.0.join("manifest.json"), b"{}").unwrap();
    assert!(LodsSource::load(&work.0, &lock).is_err());
    for (path, value) in [
        (vec!["profiles"], json!(["bap-bit-provenance-v13"])),
        (vec!["runtime_role"], json!("advanced-source-flags")),
        (vec!["cases"], json!(["f3ad"])),
        (vec!["max_response_bytes"], json!(65537)),
        (vec!["build_id"], json!("0".repeat(64))),
        (
            vec!["binding", "sources", "lods.patch"],
            json!("0".repeat(64)),
        ),
        (
            vec!["binding", "sources", "extra.py"],
            json!("0".repeat(64)),
        ),
        (vec!["binding", "sdk_lock_sha256"], json!("0".repeat(64))),
        (vec!["binding", "base_revision"], json!("other")),
        (
            vec!["binding", "source_archive_sha256"],
            json!("0".repeat(64)),
        ),
        (vec!["binding", "compiler_sha256"], json!("not-a-digest")),
        (vec!["binding", "upstream_modules"], json!({})),
    ] {
        let mut changed = manifest.clone();
        let mut current = &mut changed;
        for part in &path {
            current = &mut current[*part];
        }
        *current = value;
        // Even a test-local matching manifest pin cannot make a contradictory
        // source/SDK/build assertion satisfy the compiled transport contract.
        let lock = write_manifest(&work, &changed);
        assert!(LodsSource::load(&work.0, &lock).is_err(), "{path:?}");
    }
    let lock = write_manifest(&work, &manifest);
    std::fs::write(&executable, b"changed executable").unwrap();
    assert!(LodsSource::load(&work.0, &lock).is_err());
}

#[cfg(unix)]
fn scripted_source(script: &str) -> (Temporary, LodsSource) {
    use std::os::unix::fs::PermissionsExt;
    let work = Temporary::new();
    let executable = work.0.join("lods-lift");
    std::fs::write(&executable, format!("#!/usr/bin/python3\n{script}\n")).unwrap();
    std::fs::set_permissions(&executable, std::fs::Permissions::from_mode(0o755)).unwrap();
    std::fs::write(work.0.join("manifest.json"), b"unit transport fixture").unwrap();
    let source = LodsSource {
        directory: work.0.clone(),
        manifest_hash: file_hash(&work.0.join("manifest.json"), MAX_RESPONSE as u64).unwrap(),
        executable_hash: file_hash(&executable, MAX_EXECUTABLE).unwrap(),
        build_id: "a".repeat(64),
    };
    (work, source)
}

#[cfg(unix)]
fn emit_response() -> String {
    format!(
        "import json,sys\nrow=json.loads({:?})\nfor key,value in zip(['target','snapshot','va','bytes'],sys.argv[1:]): row[key]=value\nprint(json.dumps(row),flush=True)\n",
        serde_json::to_string(&response()).unwrap()
    )
}

#[cfg(unix)]
#[test]
fn output_exit_timeout_duplicate_fields_and_stream_limits_are_enforced() {
    for script in [
        "print('x' * 65537)".to_owned(),
        "raise SystemExit(7)".to_owned(),
        "import time; time.sleep(5)".to_owned(),
        "print('{}\\n{}')".to_owned(),
        "print('{\"schema\":\"a\",\"schema\":\"b\"}')".to_owned(),
        format!("{}\nraise SystemExit(7)", emit_response()),
        format!(
            "{}\nimport os,time\nos.close(1)\ntime.sleep(5)",
            emit_response()
        ),
    ] {
        let (_work, source) = scripted_source(&script);
        let start = Instant::now();
        assert!(
            source
                .lift(
                    "windows-amd64",
                    "test",
                    0x401000,
                    &[0xf3, 0x48, 0xad],
                    Duration::from_millis(100)
                )
                .is_err()
        );
        assert!(start.elapsed() < Duration::from_secs(3));
    }
}

#[cfg(unix)]
#[test]
fn hostile_prefixes_targets_and_wrapping_extents_do_not_spawn() {
    let (work, source) =
        scripted_source("from pathlib import Path\nPath(__file__).with_name('spawned').touch()");
    let accepted = [
        &[0xf3, 0xac][..],
        &[0x66, 0xf3, 0xad],
        &[0xf3, 0xad],
        &[0xf3, 0x48, 0xad],
    ];
    let mut refused = vec![
        vec![],
        vec![0xac],
        vec![0xad],
        vec![0xf2, 0xac],
        vec![0xf3, 0x66, 0xad],
    ];
    for bytes in accepted {
        for prefix in [0xf0, 0xf2, 0xf3, 0x64, 0x65, 0x67, 0x48] {
            let mut changed = vec![prefix];
            changed.extend(bytes);
            refused.push(changed);
        }
        let mut trailing = bytes.to_vec();
        trailing.push(0x90);
        refused.push(trailing);
    }
    for bytes in refused {
        assert!(
            source
                .lift(
                    "windows-amd64",
                    "test",
                    0x401000,
                    &bytes,
                    Duration::from_secs(1)
                )
                .is_err()
        );
    }
    assert!(
        source
            .lift(
                "windows-x86",
                "test",
                0x401000,
                &[0xf3, 0xac],
                Duration::from_secs(1)
            )
            .is_err()
    );
    assert!(
        source
            .lift(
                "windows-amd64",
                "test",
                u64::MAX - 1,
                &[0xf3, 0xac],
                Duration::from_secs(1)
            )
            .is_err()
    );
    assert!(!work.0.join("spawned").exists());
}

#[cfg(unix)]
#[test]
fn successful_child_uses_exact_query_and_cleared_environment() {
    let script = format!(
        "import os\nassert 'HOME' not in os.environ\nassert not any(k in os.environ for k in ['LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT','CAML_LD_LIBRARY_PATH'])\n{}",
        emit_response()
    );
    let (_work, source) = scripted_source(&script);
    for target in ["windows-amd64", "linux-amd64"] {
        assert!(
            source
                .lift(
                    target,
                    "test",
                    0x401000,
                    &[0xf3, 0x48, 0xad],
                    Duration::from_secs(2)
                )
                .is_ok()
        );
    }
}

#[cfg(unix)]
#[test]
fn artifact_changes_before_and_during_a_query_are_rejected() {
    for name in ["manifest.json", "lods-lift"] {
        let script = format!(
            "from pathlib import Path\nPath(__file__).with_name({name:?}).write_bytes(b'changed')\n{}",
            emit_response()
        );
        let (_work, source) = scripted_source(&script);
        assert!(
            source
                .lift(
                    "windows-amd64",
                    "test",
                    0x401000,
                    &[0xf3, 0x48, 0xad],
                    Duration::from_secs(2)
                )
                .is_err()
        );
    }
    let (work, source) = scripted_source(&emit_response());
    std::fs::write(work.0.join("manifest.json"), b"changed").unwrap();
    assert!(source.validate().is_err());
    assert!(
        source
            .lift(
                "windows-amd64",
                "test",
                0x401000,
                &[0xf3, 0x48, 0xad],
                Duration::from_secs(2)
            )
            .is_err()
    );
}

#[test]
#[ignore = "requires separately pinned native REP LODS bundle"]
fn native_pinned_bundle_transports_actual_typed_loops_for_both_targets() {
    let directory = std::env::var_os("ARIADNE_BAP_LODS_SOURCE_EXTENSION")
        .map(PathBuf::from)
        .expect("set ARIADNE_BAP_LODS_SOURCE_EXTENSION to the pinned REP LODS bundle");
    let source = LodsSource::load(&directory, LOCK).unwrap();
    for target in ["windows-amd64", "linux-amd64"] {
        for code in CASES {
            let bytes: Vec<_> = (0..code.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&code[i..i + 2], 16).unwrap())
                .collect();
            let bil = source
                .lift(
                    target,
                    "native-lods-transport",
                    0xffff800000401000,
                    &bytes,
                    Duration::from_secs(10),
                )
                .unwrap();
            assert!(matches!(
                bil.as_slice(),
                [Stmt::Move { .. }, Stmt::While { .. }]
            ));
            let opcode = crate::bap::repeated_strings::opcode(
                &bytes,
                crate::bap::repeated_strings::PROFILE14,
            )
            .unwrap();
            let projected = crate::bap::projection::project_with_destination_profile(
                &bil,
                opcode,
                &bytes,
                0xffff800000401000,
                None,
                crate::bap::repeated_strings::PROFILE14,
            )
            .unwrap();
            assert!(projected.must_defs.is_empty());
            assert!(projected.targets.is_empty());
            assert!(projected.uses.contains("memory:any"));
            assert!(projected.uses.contains("flag:df"));
            assert!(!projected.may_defs.contains("memory:any"));
            for bank in ["rax", "rsi", "rcx"] {
                assert!(projected.may_defs.contains(&format!("gpr:{bank}:0")));
            }
            assert!(
                crate::bap::projection::project_with_destination_profile(
                    &bil,
                    opcode,
                    &bytes,
                    0xffff800000401000,
                    None,
                    crate::bap::repeated_strings::PROFILE13,
                )
                .is_err()
            );
        }
    }
    source.validate().unwrap();
}
