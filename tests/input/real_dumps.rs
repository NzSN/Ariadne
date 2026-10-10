//! External Breakpad-produced artifacts are supplied explicitly, not copied or
//! downloaded by tests. Exact hashes prevent a changed fixture inheriting evidence.
use ariadne::effects::{EffectQuality, GapReason, Operand, PreparationOptions, RegisterView};
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, Platform, PrepareLimits};
use ariadne::{ByteSource, InstructionKind};
#[test]
#[ignore = "requires ARIADNE_REAL_DUMPS and pinned decoder"]
fn real_windows_and_linux_crash_artifacts_preserve_bytes_and_report_semantic_gaps() {
    let root = std::path::PathBuf::from(
        std::env::var_os("ARIADNE_REAL_DUMPS").expect("external fixture directory required"),
    );
    let decoder =
        std::path::PathBuf::from(std::env::var_os("ARIADNE_LLVM_MC").expect("decoder required"));
    for (name, hash, platform, rip, modules, threads, opcode, width, length) in [
        (
            "linux_null_dereference.dmp",
            "1d82d1d98bb46fb9aa3498fce733e724e9b501824f8b8a36de22066d6d4bca33",
            Platform::Linux,
            0x401f26,
            8,
            1,
            "MOV32mi",
            32,
            6,
        ),
        (
            "write_av_non_canonical.dmp",
            "7012f0b943f5eacf681bcb29fc2766b75b87da1664280eaadc5dfa024f0a3abf",
            Platform::Windows,
            0x7ff738721331,
            15,
            2,
            "MOV64mi32",
            64,
            8,
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
        let evidence = &p.prepared.instructions[&rip];
        assert_eq!(evidence.opcode.as_deref(), Some(opcode));
        assert_eq!(evidence.quality, EffectQuality::ExternalLifted);
        assert_eq!(evidence.source, ByteSource::Captured);
        assert_eq!(evidence.length, length);
        assert_eq!(evidence.bytes, p.reads[&rip].bytes[..length as usize]);
        assert!(
            matches!(&evidence.operands[0], Operand::Memory{access_width,address_width:64,..} if *access_width==width)
        );
        assert!(
            matches!(&evidence.operands[1], Operand::Immediate{encoded_width:32,semantic_width,sign_extend,..} if *semantic_width==width && *sign_extend==(width==64))
        );
        assert!(evidence.undefined_flags.is_empty());
        let summary = &p.prepared.request.instructions[&rip];
        assert_eq!(summary.kind, InstructionKind::Ordinary);
        let mut expected_uses = RegisterView::new(0, 0, 64).unwrap().reads();
        if platform == Platform::Windows {
            expected_uses.extend(RegisterView::new(1, 0, 64).unwrap().reads());
        }
        assert_eq!(summary.uses, expected_uses);
        assert_eq!(summary.may_defs, ["memory:any".into()].into());
        assert!(summary.must_defs.is_empty());
        assert!(!summary.uses.contains("memory:any"));
        assert_eq!(summary.fall, [rip + u64::from(length)].into());
        assert!(p.prepared.request.decodable.contains(&rip));
        assert!(!p.prepared.gaps.iter().any(|gap| gap.address == rip));
        assert_eq!(p.materialization.entry_points, [rip].into());
        let r = ariadne::analyze(p.prepared.request.clone()).unwrap();
        assert!(r.state.decoded.contains(&rip));
        assert_eq!(r.state.provenance[&rip], ByteSource::Captured);
        assert!(r.state.slice.contains(&rip));
        assert!(r.missing_slice_seeds.is_empty());
        assert!(!r.state.obligations.iter().any(|gap| gap.site == rip));
        // A normal-continuation effect says nothing about whether the crash-time
        // store retired. Reviewed POP control closes this Linux local graph,
        // while RET effects remain explicitly opaque. V3 admits the captured
        // Windows self-XOR and retains its undefined-AF diagnostic.
        if platform == Platform::Linux {
            assert_eq!(r.state.decoded, [rip, rip + 6, rip + 7].into());
            assert!(r.state.obligations.is_empty());
            assert!(r.scope_closed());
            for site in [rip + 6, rip + 7] {
                assert_eq!(
                    p.prepared.instructions[&site].quality,
                    if site == rip + 6 {
                        EffectQuality::ExternalLifted
                    } else {
                        EffectQuality::Opaque
                    }
                );
                assert_eq!(
                    p.prepared
                        .gaps
                        .iter()
                        .any(|gap| gap.address == site && gap.reason == GapReason::OpaqueEffects),
                    site == rip + 7
                );
            }
        } else {
            let xor = rip + 18;
            let evidence = &p.prepared.instructions[&xor];
            assert_eq!(evidence.bytes, [0x33, 0xc0]); // xor eax, eax
            assert_eq!(evidence.opcode.as_deref(), Some("XOR32rr_REV"));
            assert_eq!(evidence.quality, EffectQuality::ExternalLifted);
            assert_eq!(evidence.rule.as_deref(), Some("bap-bit-provenance-v3"));
            let semantic = evidence.semantic.as_ref().unwrap();
            assert_eq!(semantic.status, "projected");
            assert!(semantic.fallback.is_none());
            assert!(
                semantic
                    .gaps
                    .iter()
                    .any(|gap| gap.contains("AF is undefined"))
            );
            // The self-XOR defines all eight RAX bytes, including the upper
            // bytes zeroed by a 32-bit write; no prior RAX origin survives it.
            let summary = &p.prepared.request.instructions[&xor];
            assert_eq!(summary.fall, [xor + 2].into());
            for loc in RegisterView::new(0, 0, 64).unwrap().reads() {
                assert!(summary.must_defs.contains(&loc));
                let definitions: Vec<_> = r.state.reaching[&(xor + 2)]
                    .iter()
                    .filter(|definition| definition.loc == loc)
                    .collect();
                assert_eq!(definitions.len(), 1);
                assert_eq!(definitions[0].site, xor);
            }
            assert_eq!(
                r.state.decoded,
                [0, 8, 13, 18, 20, 28, 31, 36, 43]
                    .map(|offset| rip + offset)
                    .into()
            );
            assert!(r.state.obligations.is_empty());
            assert!(r.scope_closed());
        }
    }
}
