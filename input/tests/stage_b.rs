//! Tool-produced minidumps with an independently listed code entry preceding
//! the exception RIP. These test a captured predecessor path, not crash history.
use ariadne::effects::{EffectQuality, PreparationOptions, RegisterView};
use ariadne::{ByteSource, DefinitionOrigin, analyze};
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, Platform, PrepareLimits};

const FIXTURES: [(&[u8], &str, Platform, u64); 2] = [
    (
        include_bytes!("fixtures/stage_b_linux.dmp"),
        "7e71f4926e615789815299b98e3c3c725180ed4dce4065937fa533beb1018824",
        Platform::Linux,
        0x401000,
    ),
    (
        include_bytes!("fixtures/stage_b_windows.dmp"),
        "f3a0407bff881356c0128e7587c03ea9f143dbd5fee59abbe8fc5edb75ad30bf",
        Platform::Windows,
        0x7ff700001000,
    ),
];
const CODE: &[u8] = &[
    0x48, 0x89, 0xd8, // mov rax, rbx: address producer
    0x48, 0x89, 0xd1, // mov rcx, rdx: unrelated write
    0xc7, 0x00, 5, 0, 0, 0,    // mov dword ptr [rax], 5: seed
    0xc3, // ret
];

#[test]
fn pinned_fixture_source_entry_and_capture_are_independent_of_exception_rip() {
    for (bytes, digest, platform, entry) in FIXTURES {
        let snapshot = FileSnapshot::from_minidump_bytes(bytes.to_vec(), OpenLimits::default())
            .expect("valid tool-produced minidump");
        assert_eq!(snapshot.metadata().artifact_sha256, digest);
        assert_eq!(snapshot.metadata().platform, platform);
        assert_eq!(
            snapshot.metadata().exception.as_ref().unwrap().registers["rip"],
            entry + 6
        );
        assert_eq!(snapshot.read_prefix(entry, CODE.len()).unwrap().bytes, CODE);
        assert_ne!(entry, entry + 6);
    }
}

#[test]
#[ignore = "requires pinned LLVM decoder"]
fn captured_predecessor_path_yields_address_producer_slice_on_both_platforms() {
    let decoder = std::path::PathBuf::from(
        std::env::var_os("ARIADNE_LLVM_MC").expect("native gate sets decoder"),
    );
    for (bytes, digest, platform, entry) in FIXTURES {
        let snapshot = FileSnapshot::from_minidump_bytes(bytes.to_vec(), OpenLimits::default())
            .expect("valid tool-produced minidump");
        assert_eq!(snapshot.metadata().artifact_sha256, digest);
        assert_eq!(snapshot.metadata().platform, platform);
        let seed = entry + 6;
        let prepared = snapshot
            .prepare(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [seed].into(),
                },
                &decoder,
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        assert_eq!(
            prepared.materialization.attempted,
            [entry, entry + 3, seed, entry + 12].into()
        );
        assert_eq!(prepared.materialization.entry_points, [entry].into());
        assert_eq!(prepared.materialization.slice_seeds, [seed].into());
        for (va, opcode, length, quality) in [
            (entry, "MOV64rr", 3, EffectQuality::ExternalLifted),
            (entry + 3, "MOV64rr", 3, EffectQuality::ExternalLifted),
            (seed, "MOV32mi", 6, EffectQuality::ExternalLifted),
            (entry + 12, "RET64", 1, EffectQuality::Opaque),
        ] {
            let evidence = &prepared.prepared.instructions[&va];
            assert_eq!(evidence.opcode.as_deref(), Some(opcode));
            assert_eq!(evidence.quality, quality);
            assert_eq!(evidence.source, ByteSource::Captured);
            assert_eq!(evidence.length, length);
            assert_eq!(
                evidence.bytes,
                CODE[(va - entry) as usize..][..length as usize]
            );
        }
        let root_offset = prepared.reads[&entry].spans[0].contributors[0].file_offset;
        let seed_offset = prepared.reads[&seed].spans[0].contributors[0].file_offset;
        assert_eq!(seed_offset, root_offset + 6);
        let seed_summary = &prepared.prepared.request.instructions[&seed];
        assert_eq!(
            seed_summary.uses,
            RegisterView::new(0, 0, 64).unwrap().reads()
        );
        assert_eq!(seed_summary.may_defs, ["memory:any".into()].into());
        assert!(seed_summary.must_defs.is_empty());
        assert!(
            prepared
                .prepared
                .gaps
                .iter()
                .any(|gap| gap.address == entry + 12)
        );
        let result = analyze(prepared.prepared.request).unwrap();
        assert!(result.missing_slice_seeds.is_empty());
        assert!(result.state.obligations.is_empty());
        assert_eq!(result.state.slice, [entry, seed].into());
        assert!(result.state.reaching[&seed].iter().any(|definition| {
            definition.loc == "gpr:rax:0"
                && definition.site == entry
                && definition.origin == DefinitionOrigin::Instruction
        }));
        assert!(!result.state.slice.contains(&(entry + 3)));
    }
}
