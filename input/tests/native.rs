mod common;
use ariadne::effects::{EffectQuality, PreparationOptions};
use ariadne::{ObligationReason, analyze};
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PreparationError, PrepareLimits};
use common::*;
use std::path::PathBuf;
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .expect("native gate sets decoder")
        .into()
}
fn open(d: Dump) -> FileSnapshot {
    FileSnapshot::from_minidump_bytes(d.finish(), OpenLimits::default()).unwrap()
}
fn query(roots: &[u64], seeds: &[u64]) -> AnalysisQuery {
    AnalysisQuery {
        entry_points: roots.iter().copied().collect(),
        slice_seeds: seeds.iter().copied().collect(),
    }
}
#[test]
#[ignore = "requires pinned decoder"]
fn both_platforms_discover_interior_starts_and_produce_precise_slices() {
    for linux in [false, true] {
        let mut d = Dump::new(linux);
        d.memory(&[(
            4096,
            &[0x48, 0x89, 0xd8, 0x48, 0x89, 0xd1, 0x48, 0x89, 0xc6, 0xc3],
        )]);
        let s = open(d);
        let p = s
            .prepare(
                &query(&[4096], &[4102]),
                &decoder(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        assert!(
            p.prepared
                .identity
                .target
                .contains(if linux { "linux" } else { "windows" })
        );
        assert_eq!(p.materialization.attempted, [4096, 4099, 4102, 4105].into());
        assert_eq!(
            p.reads[&4099].spans[0].contributors[0].file_offset,
            p.reads[&4096].spans[0].contributors[0].file_offset + 3
        );
        let r = analyze(p.prepared.request).unwrap();
        assert_eq!(r.state.visited, p.materialization.attempted);
        assert_eq!(r.state.slice, [4096, 4102].into());
        assert!(r.scope_closed());
    }
}
#[test]
#[ignore = "requires pinned decoder"]
fn calls_and_seeds_do_not_discover_callees_but_explicit_roots_do() {
    for roots in [&[0x1000][..], &[0x1000, 0x2000]] {
        let mut d = Dump::new(true);
        d.memory64(&[(0x1000, &[0xe8, 0xfb, 0x0f, 0, 0, 0xc3]), (0x2000, &[0xc3])]);
        let s = open(d);
        let p = s
            .prepare(
                &query(roots, &[0x2000]),
                &decoder(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        assert_eq!(p.reads.contains_key(&0x2000), roots.len() == 2);
        if roots.len() == 1 {
            assert!(p.materialization.unattempted_references.contains(&0x2000));
            assert!(!p.prepared.gaps.iter().any(|g| g.address == 0x2000));
        }
        let r = analyze(p.prepared.request).unwrap();
        assert_eq!(r.state.visited, p.materialization.attempted);
        assert_eq!(r.missing_slice_seeds.contains(&0x2000), roots.len() == 1);
    }
}
#[test]
#[ignore = "requires pinned decoder"]
fn loops_conditional_paths_and_overlapping_starts_are_preserved() {
    let mut d = Dump::new(false);
    d.memory(&[(1, &[0x75, 2, 0xeb, 0xfc, 0xc3])]);
    let s = open(d);
    let p = s
        .prepare(
            &query(&[1], &[]),
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    let r = analyze(p.prepared.request).unwrap();
    assert_eq!(r.state.visited, [1, 3, 5].into());
    assert_eq!(r.state.edges.len(), 3);
    let mut d = Dump::new(false);
    d.memory(&[(1, &[0x48, 0x89, 0xd8, 0xc3])]);
    let s = open(d);
    let p = s
        .prepare(
            &query(&[1, 2], &[]),
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    assert!(p.materialization.overlapping_starts.contains(&(1, 2)));
}
#[test]
#[ignore = "requires pinned decoder"]
fn complete_short_prefix_conflict_and_unsupported_control_remain_distinct() {
    let mut d = Dump::new(true);
    d.memory(&[
        (1, &[0x90, 0xc3]),
        (2, &[0xff]),
        (10, &[0x0f]),
        (20, &[0x0f, 0x05]),
    ]);
    let s = open(d);
    let p = s
        .prepare(
            &query(&[1, 10, 20], &[]),
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    assert_eq!(p.prepared.instructions[&1].quality, EffectQuality::Reviewed);
    let r = analyze(p.prepared.request).unwrap();
    assert!(r.state.decoded.contains(&1));
    assert!(!r.state.decoded.contains(&2));
    for (a, reason) in [
        (2, ObligationReason::Unavailable),
        (10, ObligationReason::Unavailable),
        (20, ObligationReason::DecodeFailed),
    ] {
        assert!(
            r.state
                .obligations
                .iter()
                .any(|o| o.site == a && o.reason == reason)
        );
    }
}
#[test]
#[ignore = "requires pinned decoder"]
fn budgets_fail_without_publishing_partial_requests() {
    let mut d = Dump::new(false);
    d.memory(&[(1, &[0x90, 0x90, 0xc3])]);
    let s = open(d);
    for limits in [
        PrepareLimits {
            max_starts: 1,
            ..PrepareLimits::default()
        },
        PrepareLimits {
            max_candidates: 1,
            ..PrepareLimits::default()
        },
        PrepareLimits {
            max_prefix_bytes: 1,
            ..PrepareLimits::default()
        },
        PrepareLimits {
            max_decoder_batches: 1,
            ..PrepareLimits::default()
        },
    ] {
        assert!(matches!(
            s.prepare(
                &query(&[1], &[]),
                &decoder(),
                &PreparationOptions::default(),
                limits
            ),
            Err(PreparationError::LimitReached { .. })
        ));
    }
}
#[test]
#[ignore = "requires pinned decoder"]
fn linux_and_windows_profiles_exercise_the_frozen_effect_registry() {
    for linux in [false, true] {
        for row in include_str!("../../tests/fixtures/effects-v2.tsv")
            .lines()
            .filter(|l| !l.starts_with('#'))
        {
            let (hex, expected) = row.split_once('\t').unwrap();
            let bytes: Vec<_> = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                .collect();
            let mut d = Dump::new(linux);
            d.memory(&[(4096, &bytes)]);
            let s = open(d);
            let p = s
                .prepare(
                    &query(&[4096], &[]),
                    &decoder(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                )
                .unwrap();
            let evidence = &p.prepared.instructions[&4096];
            assert_eq!(evidence.decoder_record.as_deref(), Some(expected));
            assert_ne!(evidence.quality, EffectQuality::Unavailable, "{hex}");
        }
    }
}
