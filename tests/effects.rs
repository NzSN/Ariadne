use ariadne::effects::{
    Catalogue, EffectQuality, GapReason, Operand, PreparationOptions, RegisterView,
};
use ariadne::llvm_mc::ByteSnapshot;
use ariadne::{DefinitionOrigin, EdgeKind, InputKind, InstructionKind, ObligationReason, analyze};
use std::path::Path;

fn decode(
    spans: &[(u64, &[u8])],
    entries: &[u64],
    seeds: &[u64],
) -> ariadne::effects::PreparedAnalysis {
    let snapshot = snapshot(spans, entries, seeds);
    snapshot
        .prepare(
            Path::new(&std::env::var("ARIADNE_LLVM_MC").expect("native gate sets decoder")),
            &PreparationOptions::default(),
        )
        .unwrap()
}
fn snapshot(spans: &[(u64, &[u8])], entries: &[u64], seeds: &[u64]) -> ByteSnapshot {
    ByteSnapshot {
        snapshot_id: "effects-test".into(),
        file_backed: spans.iter().map(|(a, b)| (*a, b.to_vec())).collect(),
        entry_points: entries.iter().copied().collect(),
        slice_seeds: seeds.iter().copied().collect(),
        locations: Catalogue.locations(),
        ..ByteSnapshot::default()
    }
}
fn cells(bank: u8, offset: u8, width: u8) -> ariadne::LocationSet {
    RegisterView::new(bank, offset, width).unwrap().reads()
}

#[test]
fn catalogue_is_disjoint_and_views_distinguish_reads_from_writes() {
    assert_eq!(Catalogue.locations().len(), 137);
    assert_eq!(cells(0, 8, 8), ["gpr:rax:1".into()].into());
    assert_eq!(
        RegisterView::new(0, 0, 32).unwrap().replacements(),
        cells(0, 0, 64)
    );
    assert_eq!(cells(0, 0, 32).len(), 4);
    for (bank, offset, width) in [(16, 0, 64), (4, 8, 8), (0, 1, 8), (0, 0, 7), (0, 8, 16)] {
        assert!(RegisterView::new(bank, offset, width).is_none());
    }
}
#[test]
fn prepare_rejects_independent_overlapping_locations_before_decoder_launch() {
    let mut s = snapshot(&[], &[1], &[]);
    s.locations = ["rax".into(), "eax".into()].into();
    assert!(
        s.prepare(Path::new("/nonexistent"), &PreparationOptions::default())
            .unwrap_err()
            .to_string()
            .contains("catalogue")
    );
}

#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn mov_slice_excludes_unrelated_instruction_and_preserves_legacy_behavior() {
    let spans = [
        (0x1000, &[0x48, 0x89, 0xd8][..]),
        (0x1003, &[0x48, 0x89, 0xd1]),
        (0x1006, &[0x48, 0x89, 0xc6]),
        (0x1009, &[0xc3]),
    ];
    let p = decode(&spans, &[0x1000], &[0x1006]);
    let result = analyze(p.request).unwrap();
    assert_eq!(result.state.slice, [0x1000, 0x1006].into());
    let legacy = snapshot(&spans, &[0x1000], &[0x1006])
        .to_request(Path::new(&std::env::var("ARIADNE_LLVM_MC").unwrap()))
        .unwrap();
    assert!(analyze(legacy).unwrap().state.slice.contains(&0x1003));
    assert_eq!(p.instructions[&0x1000].quality, EffectQuality::Reviewed);
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn partial_writes_preserve_other_bytes_and_dword_replaces_upper_half() {
    for bytes in [
        &[0xb0, 1][..],
        &[0xb4, 1],
        &[0x66, 0xb8, 1, 0],
        &[0xb8, 1, 0, 0, 0],
    ] {
        let next = 0x1003 + bytes.len() as u64;
        let p = decode(
            &[
                (0x1000, &[0x48, 0x89, 0xd8]),
                (0x1003, bytes),
                (next, &[0x48, 0x89, 0xc6]),
            ],
            &[0x1000],
            &[next],
        );
        let replaced = p.request.instructions[&0x1003].must_defs.clone();
        let expected = match bytes[0] {
            0xb0 => cells(0, 0, 8),
            0xb4 => cells(0, 8, 8),
            0x66 => cells(0, 0, 16),
            _ => cells(0, 0, 64),
        };
        assert_eq!(replaced, expected);
        let r = analyze(p.request).unwrap();
        for loc in cells(0, 0, 64) {
            let sites: std::collections::BTreeSet<_> = r.state.reaching[&next]
                .iter()
                .filter(|d| d.loc == loc)
                .map(|d| d.site)
                .collect();
            assert_eq!(
                sites,
                [if replaced.contains(&loc) {
                    0x1003
                } else {
                    0x1000
                }]
                .into()
            );
        }
    }
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn arithmetic_matrix_checks_widths_flags_ties_and_immediates() {
    for width in [8, 16, 32, 64] {
        let prefix: Vec<u8> = match width {
            16 => vec![0x66],
            64 => vec![0x48],
            _ => vec![],
        };
        for (family, opcode, extension) in [
            ("ADD", 0x00, 0),
            ("OR", 0x08, 1),
            ("ADC", 0x10, 2),
            ("SBB", 0x18, 3),
            ("AND", 0x20, 4),
            ("SUB", 0x28, 5),
            ("XOR", 0x30, 6),
            ("CMP", 0x38, 7),
            ("TEST", 0x84, 0),
        ] {
            let logical = ["OR", "AND", "XOR", "TEST"].contains(&family);
            let compare = ["CMP", "TEST"].contains(&family);
            let mut cases = vec![];
            let mut rr = prefix.clone();
            rr.extend([opcode + u8::from(width != 8), 0xd8]);
            cases.push(rr);
            let mut ri = prefix.clone();
            ri.extend([
                if family == "TEST" {
                    if width == 8 { 0xf6 } else { 0xf7 }
                } else if width == 8 {
                    0x80
                } else {
                    0x81
                },
                0xc3 + 8 * extension,
            ]);
            ri.extend(std::iter::repeat_n(
                1,
                if width == 8 {
                    1
                } else if width == 16 {
                    2
                } else {
                    4
                },
            ));
            cases.push(ri);
            if width > 8 && family != "TEST" {
                let mut ri8 = prefix.clone();
                ri8.extend([0x83, 0xc3 + 8 * extension, 0xff]);
                cases.push(ri8);
            }
            for bytes in cases {
                let p = decode(&[(4096, &bytes)], &[4096], &[]);
                let e = &p.instructions[&4096];
                assert_eq!(
                    e.quality,
                    EffectQuality::Reviewed,
                    "{bytes:x?} {:?}",
                    e.opcode
                );
                let s = &p.request.instructions[&4096];
                assert!(s.uses.contains("flag:cf") == ["ADC", "SBB"].contains(&family));
                assert_eq!(
                    s.may_defs.iter().filter(|l| l.starts_with("gpr:")).count(),
                    if compare {
                        0
                    } else if width == 32 {
                        8
                    } else {
                        width / 8
                    }
                );
                assert_eq!(s.must_defs.contains("flag:af"), !logical);
                assert_eq!(e.undefined_flags.contains("flag:af"), logical);
                assert!(!s.may_defs.contains("state:other"));
            }
        }
        for (op, code) in [("INC", 0xc0), ("DEC", 0xc8)] {
            let mut bytes = prefix.clone();
            bytes.extend([if width == 8 { 0xfe } else { 0xff }, code]);
            let p = decode(&[(4096, &bytes)], &[4096], &[]);
            let s = &p.request.instructions[&4096];
            assert_eq!(
                p.instructions[&4096].quality,
                EffectQuality::Reviewed,
                "{op}/{width}"
            );
            assert!(!s.may_defs.contains("flag:cf"));
            assert!(s.must_defs.contains("flag:zf"));
        }
    }
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn carry_dependency_survives_increment_and_cmp_does_not_write_registers() {
    let p = decode(
        &[
            (1, &[0x48, 0x39, 0xd8]),
            (4, &[0x48, 0xff, 0xc0]),
            (7, &[0x48, 0x11, 0xd1]),
        ],
        &[1],
        &[7],
    );
    let r = analyze(p.request).unwrap();
    assert!(r.state.slice.contains(&1));
    assert!(
        r.state.reaching[&7].iter().any(|d| d.loc == "flag:cf"
            && d.site == 1
            && d.origin == DefinitionOrigin::Instruction)
    );
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn memory_keeps_possible_aliases_and_address_dependencies_lea_does_not_read_memory() {
    let p = decode(
        &[
            (1, &[0x48, 0x89, 0xcb]),
            (4, &[0x48, 0x89, 0x17]),
            (7, &[0x48, 0x89, 0x16]),
            (10, &[0x48, 0x8b, 0x43, 8]),
            (14, &[0x48, 0x8d, 0x43, 8]),
        ],
        &[1],
        &[10],
    );
    assert!(p.request.instructions[&4].must_defs.is_empty());
    assert!(!p.request.instructions[&14].uses.contains("memory:any"));
    assert!(
        p.request.instructions[&10]
            .uses
            .is_superset(&cells(3, 0, 64))
    );
    let r = analyze(p.request).unwrap();
    assert_eq!(r.state.slice, [1, 4, 7, 10].into());
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn memory_address_sizes_rip_and_prefix_rejections() {
    for (bytes, width, relative) in [
        (&[0x67, 0x8b, 0x43, 8][..], 32, false),
        (&[0x48, 0x8b, 0x05, 8, 0, 0, 0], 64, true),
    ] {
        let p = decode(&[(4096, bytes)], &[4096], &[]);
        assert!(
            matches!(&p.instructions[&4096].operands[1],Operand::Memory{address_width,next_ip,..} if *address_width==width && next_ip.is_some()==relative)
        );
    }
    for bytes in [
        &[0x64, 0x48, 0x8b, 0x03][..],
        &[0xf0, 0x48, 0x01, 0x03],
        &[0x66, 0x66, 0x89, 0xd8],
    ] {
        let p = decode(&[(4096, bytes)], &[4096], &[]);
        assert!(!p.request.decodable.contains(&4096));
    }
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn control_flags_calls_and_unrecognized_control_have_distinct_evidence() {
    for cc in 0..16 {
        let p = decode(&[(4096, &[0x70 + cc, 2])], &[4096], &[]);
        assert_eq!(
            p.request.instructions[&4096].kind,
            InstructionKind::Conditional
        );
        assert!(!p.request.instructions[&4096].uses.is_empty());
    }
    let p = decode(
        &[
            (1, &[0xe8, 10, 0, 0, 0]),
            (6, &[0xff, 0xd0]),
            (8, &[0xff, 0xe0]),
            (16, &[0xc3]),
        ],
        &[1],
        &[],
    );
    assert_eq!(p.request.instructions[&1].uses, Catalogue.locations());
    assert_eq!(p.request.instructions[&1].may_defs, Catalogue.locations());
    assert!(p.request.instructions[&1].must_defs.is_empty());
    let r = analyze(p.request).unwrap();
    assert!(!r.state.visited.contains(&16));
    assert!(r.state.edges.iter().any(|e| e.kind == EdgeKind::Call));
    assert!(
        r.state
            .obligations
            .iter()
            .any(|o| o.site == 6 && o.reason == ObligationReason::CallTargets)
    );
    for bytes in [&[0x0f, 0x05][..], &[0x0f, 0x31], &[0xc7, 0xf8, 0, 0, 0, 0]] {
        let p = decode(&[(1, bytes)], &[1], &[]);
        assert!(
            p.gaps
                .iter()
                .any(|g| g.reason == GapReason::UnsupportedControl)
        );
        let r = analyze(p.request).unwrap();
        assert!(r.state.edges.is_empty());
        assert!(
            r.state
                .obligations
                .iter()
                .any(|o| o.reason == ObligationReason::DecodeFailed)
        );
    }
    let p = decode(&[(1, &[0xf9])], &[1], &[]);
    assert_eq!(p.instructions[&1].quality, EffectQuality::Opaque);
    assert!(p.request.instructions[&1].must_defs.is_empty());
}
#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn dump_provenance_and_missing_targets_survive_preparation() {
    let mut s = snapshot(&[(1, &[0xc3]), (2, &[0xc3]), (3, &[0xc3])], &[1, 2, 3], &[]);
    s.input_kind = InputKind::Dump;
    s.captured = [(1, vec![0x0f]), (2, vec![0x0f; 15])].into();
    s.trusted_fallback = [1, 2].into();
    let p = s
        .prepare(
            Path::new(&std::env::var("ARIADNE_LLVM_MC").unwrap()),
            &PreparationOptions::default(),
        )
        .unwrap();
    assert!(p.request.decodable.is_empty());
    let r = analyze(p.request).unwrap();
    assert!(
        r.state
            .obligations
            .iter()
            .any(|o| o.site == 1 && o.reason == ObligationReason::Unavailable)
    );
    assert!(
        r.state
            .obligations
            .iter()
            .any(|o| o.site == 2 && o.reason == ObligationReason::DecodeFailed)
    );
    assert!(
        r.state
            .obligations
            .iter()
            .any(|o| o.site == 3 && o.reason == ObligationReason::Unavailable)
    );
}

#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn frozen_opcode_matrix_has_real_native_evidence_and_no_unexercised_rules() {
    let mut observed = std::collections::BTreeSet::new();
    for row in include_str!("fixtures/effects-v2.tsv")
        .lines()
        .filter(|l| !l.starts_with('#'))
    {
        let (hex, expected) = row.split_once('\t').unwrap();
        let bytes: Vec<_> = (0..hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
            .collect();
        let p = decode(&[(4096, &bytes)], &[4096], &[]);
        let e = &p.instructions[&4096];
        assert_eq!(e.decoder_record.as_deref(), Some(expected), "{hex}");
        assert_ne!(
            e.quality,
            EffectQuality::Unavailable,
            "{hex}: {:?}",
            e.opcode
        );
        observed.insert(e.opcode.clone().unwrap());
        let s = &p.request.instructions[&4096];
        if e.opcode.as_ref().unwrap().starts_with("MOV")
            || e.opcode.as_ref().unwrap().starts_with("LEA")
        {
            assert!(!s.may_defs.iter().any(|l| l.starts_with("flag:")));
            if let Operand::Register(dst) = &e.operands[0] {
                assert_eq!(s.must_defs, dst.replacements());
                assert!(!s.may_defs.contains("memory:any"));
            } else {
                assert_eq!(s.may_defs, ["memory:any".into()].into());
                assert!(s.must_defs.is_empty());
            }
        }
    }
    let declared: std::collections::BTreeSet<_> = include_str!("../src/effects/forms.txt")
        .lines()
        .map(str::to_owned)
        .collect();
    assert_eq!(observed, declared);
}

#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn batched_preparation_preserves_every_record_and_reports_measurement() {
    let mut s = snapshot(&[], &[4096], &[4096 + 3 * 255]);
    for i in 0..256 {
        s.file_backed.insert(4096 + 3 * i, vec![0x48, 0x89, 0xd8]);
    }
    let begin = std::time::Instant::now();
    let p = s
        .prepare(
            Path::new(&std::env::var("ARIADNE_LLVM_MC").unwrap()),
            &PreparationOptions::default(),
        )
        .unwrap();
    let preparation = begin.elapsed();
    assert_eq!(p.request.decodable.len(), 256);
    assert_eq!(p.instructions.len(), 257); // final unavailable continuation
    let begin = std::time::Instant::now();
    let r = analyze(p.request).unwrap();
    let analysis = begin.elapsed();
    assert_eq!(r.state.decoded.len(), 256);
    eprintln!("effects batch=256 locations=137 prepare={preparation:?} analyze={analysis:?}");
}

#[test]
#[ignore = "requires pinned LLVM; run native/llvm_mc/check.sh"]
fn extended_register_views_and_immediate_widths_are_preserved() {
    for (bytes, bank, width) in [
        (&[0x41, 0xb0, 0xff][..], 8, 8),
        (&[0x66, 0x41, 0xb8, 0xff, 0xff], 8, 16),
        (&[0x41, 0xb8, 0xff, 0xff, 0xff, 0xff], 8, 32),
        (&[0x49, 0xc7, 0xc0, 0xff, 0xff, 0xff, 0xff], 8, 64),
    ] {
        let p = decode(&[(1, bytes)], &[1], &[]);
        let e = &p.instructions[&1];
        assert_eq!(e.quality, EffectQuality::Reviewed);
        assert!(
            matches!(&e.operands[0],Operand::Register(r) if r.bank()==bank && r.width()==width)
        );
        assert!(
            matches!(&e.operands[1],Operand::Immediate{encoded_width,semantic_width,sign_extend,..}
            if *encoded_width==if width==64 {32}else{width} && *semantic_width==width && *sign_extend==(width==64))
        );
    }
}
