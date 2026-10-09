use ariadne::bap::{Backend, Config};
use ariadne::{
    effects::{Catalogue, EffectQuality, PreparationOptions},
    llvm_mc::DecoderTarget,
};
use std::collections::BTreeMap;
use std::path::PathBuf;
fn make_backend() -> Backend {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let helper = std::env::var_os("ARIADNE_BAP_HELPER")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/ariadne-bap-lift"));
    let runtime = std::env::var_os("BAP_RUNTIME_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("tmp/bap-setup/stable"));
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/ariadne-llvm-mc"));
    Backend::new(Config::new(helper, runtime), &decoder).unwrap()
}

#[test]
#[ignore = "requires pinned BAP/LLVM native helpers"]
fn independent_decoder_process_is_reused_across_snapshot_batches() {
    let mut backend = make_backend();
    let options = PreparationOptions::default();
    for (address, code) in [
        (0x401000, "c7400805000000"),
        (0x401007, "c3"),
        (0x402000, "488b4008"),
    ] {
        let candidates = [(address, Some(bytes(code)))].into();
        let result = backend
            .prepare(
                "single-decoder-snapshot",
                &candidates,
                &options,
                DecoderTarget::WindowsAmd64,
            )
            .unwrap();
        assert!(result.sites[&address].decodable);
        assert_eq!(result.sites[&address].evidence.bytes, bytes(code));
    }
    assert_eq!(
        backend.metrics().reference_processes,
        1,
        "one independent decoder process must serve this snapshot"
    );
    let candidates = (0..128)
        .map(|n| (0x403000 + n * 16, Some(bytes("c7400805000000"))))
        .collect();
    let batch = backend
        .prepare(
            "single-decoder-snapshot",
            &candidates,
            &options,
            DecoderTarget::WindowsAmd64,
        )
        .unwrap();
    assert_eq!(batch.sites.len(), 128);
    assert_eq!(backend.metrics().reference_processes, 1);
    backend.finish().unwrap();
}

#[test]
#[cfg(unix)]
#[ignore = "requires pinned BAP runtime"]
fn every_pinned_runtime_file_is_checked_before_preparation() {
    use std::os::unix::fs::symlink;
    let config = Config::from_env();
    config.validate().unwrap();
    let lock: serde_json::Value =
        serde_json::from_str(include_str!("../../native/bap/toolchain.lock.json")).unwrap();
    let files = lock["files"].as_object().unwrap();
    for (index, damaged) in files.keys().enumerate() {
        let directory = std::env::temp_dir().join(format!(
            "ariadne-runtime-control-{}-{index}",
            std::process::id()
        ));
        std::fs::create_dir(&directory).unwrap();
        for relative in files.keys() {
            let dest = directory.join(relative);
            std::fs::create_dir_all(dest.parent().unwrap()).unwrap();
            if relative == damaged {
                std::fs::write(dest, b"changed runtime bytes").unwrap();
            } else {
                symlink(config.runtime.join(relative), dest).unwrap();
            }
        }
        let changed = Config::new(config.helper.clone(), directory.clone());
        assert!(
            changed
                .validate()
                .unwrap_err()
                .to_string()
                .contains(damaged),
            "{damaged}"
        );
        let decoder = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc");
        assert!(Backend::new(changed, &decoder).is_err());
        std::fs::remove_dir_all(directory).unwrap();
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM native helpers"]
fn unavailable_batches_high_addresses_short_bytes_and_query_ownership_are_checked() {
    let mut backend = make_backend();
    let options = PreparationOptions::default();
    let absent = [(0xffff800000001000, None)].into();
    let first = backend
        .prepare(
            "high-address-fixture",
            &absent,
            &options,
            DecoderTarget::WindowsAmd64,
        )
        .unwrap();
    assert!(!first.sites[&0xffff800000001000].decodable);
    assert!(
        backend
            .prepare("other", &absent, &options, DecoderTarget::WindowsAmd64)
            .is_err()
    );
    let candidates = [
        (0xffff800000001020, Some(bytes("4889d8"))),
        (0xffff800000001040, Some(bytes("48"))),
    ]
    .into();
    let second = backend
        .prepare(
            "high-address-fixture",
            &candidates,
            &options,
            DecoderTarget::WindowsAmd64,
        )
        .unwrap();
    assert_eq!(first.identity, second.identity);
    assert_eq!(
        second.sites[&0xffff800000001020].instruction.must_defs,
        (0..8).map(|i| cell("rax", i)).collect()
    );
    assert_eq!(
        second.sites[&0xffff800000001020]
            .evidence
            .semantic
            .as_ref()
            .unwrap()
            .status,
        "projected"
    );
    assert!(!second.sites[&0xffff800000001040].decodable);
    assert!(
        backend
            .prepare(
                "high-address-fixture",
                &candidates,
                &options,
                DecoderTarget::LinuxAmd64
            )
            .is_err()
    );
    backend.finish().unwrap();
}
fn bytes(hex: &str) -> Vec<u8> {
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
        .collect()
}
fn cell(bank: &str, index: usize) -> String {
    format!("gpr:{bank}:{index}")
}

#[test]
#[ignore = "requires pinned BAP/LLVM helpers; independent P0 contract"]
fn observed_admission_forms_match_frozen_effects_and_address_footprints() {
    let contract: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/admission/contract.json")).unwrap();
    let rows = &contract["cases"].as_array().unwrap()[..16];
    for target in [DecoderTarget::LinuxAmd64, DecoderTarget::WindowsAmd64] {
        let mut backend = make_backend();
        let candidates = rows
            .iter()
            .enumerate()
            .map(|(i, row)| {
                (
                    0x401000 + i as u64 * 32,
                    Some(bytes(row["bytes"].as_str().unwrap())),
                )
            })
            .collect();
        let batch = backend
            .prepare(
                "admission-independent-contract",
                &candidates,
                &PreparationOptions::default(),
                target,
            )
            .unwrap();
        for (i, row) in rows.iter().enumerate() {
            let site = &batch.sites[&(0x401000 + i as u64 * 32)];
            let expected = &row["expected"];
            for (key, actual) in [
                ("uses", &site.instruction.uses),
                ("may_defs", &site.instruction.may_defs),
                ("must_defs", &site.instruction.must_defs),
            ] {
                let wanted: ariadne::LocationSet = expected[key]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_str().unwrap().into())
                    .collect();
                assert_eq!(*actual, wanted, "{} {key}", row["name"]);
            }
            let semantic = site.evidence.semantic.as_ref().unwrap();
            assert_eq!(semantic.status, "projected", "{}", row["name"]);
            assert_eq!(semantic.projection, "bap-bit-provenance-v3");
            assert!(semantic.fallback.is_none());
            if site.instruction.kind != ariadne::InstructionKind::Jump {
                assert_eq!(
                    site.instruction.fall,
                    [0x401000 + i as u64 * 32 + site.evidence.length as u64].into()
                );
            } else {
                assert!(site.instruction.fall.is_empty());
            }
            let flags: ariadne::LocationSet = expected["undefined_flags"]
                .as_array()
                .map(|a| a.iter().map(|v| v.as_str().unwrap().into()).collect())
                .unwrap_or_default();
            assert_eq!(site.evidence.undefined_flags, flags);
            if let Some(access) = expected.get("access") {
                // CMP BIL repeats its one decoded operand in several flag expressions.
                // Preserve every attributed expression and check each footprint.
                assert!(!semantic.memory_accesses.is_empty(), "{}", row["name"]);
                for actual in &semantic.memory_accesses {
                    assert_eq!(
                        actual.access_width as u64,
                        access["width"].as_u64().unwrap()
                    );
                    assert_eq!(actual.address_width, 64);
                    assert!(matches!(
                        actual.role,
                        ariadne::effects::MemoryAccessRole::Load
                    ));
                    let expression = actual.expression.as_ref().unwrap();
                    assert_eq!(
                        expression.constant,
                        access["displacement"].as_i64().unwrap() as u64
                    );
                    let inputs = actual.address_inputs.clone();
                    let bank = access["base"].as_str().unwrap();
                    let mut wanted: ariadne::LocationSet = (0..8).map(|n| cell(bank, n)).collect();
                    if let Some(bank) = access["index"].as_str() {
                        wanted.extend((0..8).map(|n| cell(bank, n)));
                    }
                    assert_eq!(inputs, wanted, "{} address inputs", row["name"]);
                    assert!(!inputs.contains("memory:any"));
                }
            }
        }
        backend.finish().unwrap();
    }
}
#[test]
#[ignore = "requires pinned BAP/LLVM native helpers"]
fn aliases_zero_extension_memory_and_conditional_writes_have_independent_effect_expectations() {
    for target in [DecoderTarget::LinuxAmd64, DecoderTarget::WindowsAmd64] {
        let mut backend = make_backend();
        let mut candidates = BTreeMap::new();
        for (i, hex) in [
            "4889d8",
            "88dc",
            "b878563412",
            "488b448b08",
            "488903",
            "480f45c3",
            "48f7d0",
            "480fbec0",
            "0fb6c0",
            "4801d8",
            "4811d8",
            "7502",
        ]
        .iter()
        .enumerate()
        {
            candidates.insert(0x1000 + i as u64 * 32, Some(bytes(hex)));
        }
        let batch = backend
            .prepare(
                "independent-effects-fixture",
                &candidates,
                &PreparationOptions::default(),
                target,
            )
            .unwrap();
        let site = |i: u64| &batch.sites[&(0x1000 + i * 32)];
        assert_eq!(
            site(0).instruction.uses,
            (0..8).map(|i| cell("rbx", i)).collect()
        );
        assert_eq!(
            site(0).instruction.must_defs,
            (0..8).map(|i| cell("rax", i)).collect()
        );
        assert_eq!(site(1).instruction.may_defs, [cell("rax", 1)].into());
        assert_eq!(site(1).instruction.must_defs, [cell("rax", 1)].into());
        assert_eq!(site(1).instruction.uses, [cell("rbx", 0)].into());
        assert_eq!(
            site(2).instruction.must_defs,
            (0..8).map(|i| cell("rax", i)).collect()
        );
        assert!(site(2).instruction.uses.is_empty());
        assert!(site(3).instruction.uses.contains("memory:any"));
        assert!(site(3).instruction.uses.contains(&cell("rbx", 0)));
        assert!(site(3).instruction.uses.contains(&cell("rcx", 0)));
        assert_eq!(site(4).instruction.may_defs, ["memory:any".into()].into());
        assert!(site(4).instruction.must_defs.is_empty());
        assert!(site(4).instruction.uses.contains(&cell("rbx", 0)));
        assert!(
            site(5).instruction.uses.contains("flag:zf"),
            "{:?}",
            site(5)
        );
        assert!(site(5).instruction.must_defs.is_empty());
        assert!(site(5).instruction.uses.contains(&cell("rax", 0)));
        assert_eq!(site(6).evidence.quality, EffectQuality::ExternalLifted);
        assert_eq!(
            site(6).instruction.must_defs,
            (0..8).map(|i| cell("rax", i)).collect()
        );
        assert_eq!(site(7).instruction.uses, [cell("rax", 0)].into());
        assert_eq!(
            site(8).instruction.must_defs,
            (0..8).map(|i| cell("rax", i)).collect()
        );
        assert!(site(9).instruction.may_defs.contains("flag:zf"));
        assert!(site(10).instruction.uses.contains("flag:cf"));
        assert!(site(11).instruction.uses.contains("flag:zf"));
        for s in batch.sites.values() {
            println!(
                "{} {:?} {:?}",
                s.evidence.opcode.as_deref().unwrap_or("?"),
                s.evidence.quality,
                s.evidence.semantic.as_ref().map(|m| (&m.status, &m.gaps))
            );
        }
    }
}
#[test]
#[ignore = "requires pinned BAP/LLVM native helpers"]
fn calls_special_empty_lifts_prefixes_and_snapshot_reset_remain_explicit() {
    let mut backend = make_backend();
    let mut candidates = BTreeMap::new();
    for (i, hex) in [
        "e800000000",
        "ffd0",
        "c3",
        "0f05",
        "0fa2",
        "0f0b",
        "f00118",
        "f3a4",
    ]
    .iter()
    .enumerate()
    {
        candidates.insert(0x2000 + i as u64 * 32, Some(bytes(hex)));
    }
    candidates.insert(0x4000, None);
    let batch = backend
        .prepare(
            "negative-fixture",
            &candidates,
            &PreparationOptions::default(),
            DecoderTarget::LinuxAmd64,
        )
        .unwrap();
    for i in 0..3 {
        let s = &batch.sites[&(0x2000 + i * 32)];
        assert_eq!(s.instruction.uses, Catalogue.locations());
        assert_eq!(s.instruction.may_defs, Catalogue.locations());
        assert!(s.instruction.must_defs.is_empty());
    }
    for i in 3..8 {
        let s = &batch.sites[&(0x2000 + i * 32)];
        assert_ne!(s.evidence.semantic.as_ref().unwrap().status, "projected");
        assert!(s.instruction.must_defs.is_empty());
    }
    assert!(!batch.sites[&0x4000].decodable);
    assert!(
        backend
            .prepare(
                "different-snapshot",
                &candidates,
                &PreparationOptions::default(),
                DecoderTarget::LinuxAmd64
            )
            .is_err()
    );
    let mut fresh = make_backend();
    let other = [(0x2000, Some(bytes("b800000000")))].into();
    let result = fresh
        .prepare(
            "different-snapshot",
            &other,
            &PreparationOptions::default(),
            DecoderTarget::LinuxAmd64,
        )
        .unwrap();
    assert!(result.sites[&0x2000].instruction.uses.is_empty());
}

#[test]
#[ignore = "requires pinned helpers; checks BAP-only behavior"]
fn partial_self_moves_define_written_cells_and_unsupported_bil_never_falls_back() {
    let mut backend = make_backend();
    let candidates = [
        (0x1000, Some(bytes("88c0"))),
        (0x1020, Some(bytes("88e4"))),
        (0x1040, Some(bytes("6689c0"))),
        (0x1050, Some(bytes("89c0"))),
        (0x1058, Some(bytes("480f44c0"))),
        (0x1060, Some(bytes("f8"))),
    ]
    .into();
    let batch = backend
        .prepare(
            "bap-only-alias-fixture",
            &candidates,
            &PreparationOptions::default(),
            DecoderTarget::LinuxAmd64,
        )
        .unwrap();
    for (va, cells) in [
        (0x1000, vec![cell("rax", 0)]),
        (0x1020, vec![cell("rax", 1)]),
        (0x1040, vec![cell("rax", 0), cell("rax", 1)]),
        (0x1050, (0..8).map(|i| cell("rax", i)).collect()),
    ] {
        let site = &batch.sites[&va];
        let expected: std::collections::BTreeSet<_> = cells.into_iter().collect();
        assert_eq!(site.instruction.may_defs, expected);
        assert_eq!(site.instruction.must_defs, expected);
        assert_eq!(
            site.instruction.uses,
            if va == 0x1050 {
                (0..4).map(|i| cell("rax", i)).collect()
            } else {
                expected
            }
        );
        assert_eq!(site.evidence.semantic.as_ref().unwrap().status, "projected");
    }
    let conditional = &batch.sites[&0x1058];
    assert_eq!(
        conditional.instruction.may_defs,
        (0..8).map(|i| cell("rax", i)).collect()
    );
    assert!(conditional.instruction.must_defs.is_empty());
    assert_eq!(
        conditional.instruction.uses,
        (0..8)
            .map(|i| cell("rax", i))
            .chain(["flag:zf".into()])
            .collect()
    );
    let unsupported = &batch.sites[&0x1060];
    assert!(!unsupported.decodable);
    assert_eq!(unsupported.instruction.kind, ariadne::InstructionKind::Stop);
    assert!(unsupported.instruction.fall.is_empty());
    assert!(unsupported.instruction.must_defs.is_empty());
    assert_eq!(
        unsupported.evidence.semantic.as_ref().unwrap().status,
        "opaque-unsupported"
    );
    assert!(
        unsupported
            .evidence
            .semantic
            .as_ref()
            .unwrap()
            .fallback
            .is_none()
    );
    assert!(unsupported.evidence.rule.is_none());
    backend.finish().unwrap();
}

#[test]
#[ignore = "requires pinned native helpers"]
fn memory_address_evidence_distinguishes_payload_index_displacement_and_rip() {
    let mut backend = make_backend();
    let candidates = [
        (0x5000, Some(bytes("488b448b08"))),
        (0x5020, Some(bytes("488903"))),
        (0x5040, Some(bytes("8985b8feffff"))),
        (0x5060, Some(bytes("488b0508000000"))),
        (0x5080, Some(bytes("c70005000000"))),
    ]
    .into();
    let batch = backend
        .prepare(
            "address-evidence-fixture",
            &candidates,
            &PreparationOptions::default(),
            DecoderTarget::LinuxAmd64,
        )
        .unwrap();
    let access = |va| {
        &batch.sites[&va]
            .evidence
            .semantic
            .as_ref()
            .unwrap()
            .memory_accesses[0]
    };
    let indexed = access(0x5000);
    let e = indexed.expression.as_ref().unwrap();
    assert_eq!(e.constant, 8);
    assert_eq!(
        e.terms,
        vec![
            ariadne::effects::AddressTerm {
                bank: 1,
                coefficient: 4
            },
            ariadne::effects::AddressTerm {
                bank: 3,
                coefficient: 1
            }
        ]
    );
    assert!(indexed.address_inputs.contains("gpr:rcx:0"));
    assert!(indexed.address_inputs.contains("gpr:rbx:0"));
    assert!(!indexed.address_inputs.contains("gpr:rax:0"));
    assert_eq!(
        access(0x5020).address_inputs,
        (0..8).map(|i| cell("rbx", i)).collect()
    );
    assert_eq!(
        access(0x5040).expression.as_ref().unwrap().constant,
        (-328i64) as u64
    );
    assert_eq!(
        access(0x5040).address_inputs,
        (0..8).map(|i| cell("rbp", i)).collect()
    );
    assert_eq!(
        access(0x5060).expression.as_ref().unwrap().constant,
        0x5060 + 7 + 8
    );
    assert!(access(0x5060).address_inputs.is_empty());
    assert_eq!(
        access(0x5080).address_inputs,
        (0..8).map(|i| cell("rax", i)).collect()
    );
    backend.finish().unwrap();
}
