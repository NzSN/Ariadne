//! Fresh BAP witnesses for the address-32 MOV8 producer gap.
//! The existing prefix barrier must stop these lifts before a known address,
//! target transfer or memory-refinement receipt can be published. This does not
//! introduce a repaired lift or ordinary continuation for an unmodeled prefix.
use super::{common, core, decoder, locations, producer, target};
use crate::bap::core_adapter::NativeAnalyzer;
use crate::bap::{Backend, Session};
use crate::effects::{EffectQuality, MemoryAccessRole, PreparationOptions};
use crate::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{
    AnalysisView, Analyzer, CompletedAnalysis, InstructionKind, Obligation, ObligationReason,
};
use std::collections::{BTreeMap, BTreeSet};

#[test]
#[ignore = "requires current pinned BAP/LLVM, actual bad address-32 lifts and native core"]
fn native_address32_mov8_producer_errors_stay_behind_prefix_barrier() {
    let cases: Vec<(&str, Vec<u8>)> = vec![
        ("eip-relative-high-pc", vec![0x67, 0x8a, 0x05, 0, 0, 0, 0]),
        ("sib-register-overflow", vec![0x67, 0x8a, 0x04, 0x00]),
        (
            "sib-no-base-negative",
            vec![0x67, 0x8a, 0x04, 0x25, 0, 0, 0, 0x80],
        ),
    ];
    let mut raw_witnesses = 0;
    let mut profile_refusals = 0;
    let mut native_preparations = 0;
    for linux in [false, true] {
        let blocks: Vec<_> = cases
            .iter()
            .enumerate()
            .map(|(index, (_, bytes))| {
                let site = 0x0000_0001_0040_1000 + index as u64 * 0x1000;
                let mut code = bytes.clone();
                code.extend([0x90, 0xc3]);
                (site, site + bytes.len() as u64, code)
            })
            .collect();
        let ranges: Vec<_> = blocks
            .iter()
            .map(|(site, _, code)| (*site, code.as_slice()))
            .collect();
        let mut dump = common::Dump::new(linux);
        dump.memory64(&ranges);
        let snapshot =
            FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
        let query = AnalysisQuery {
            entry_points: blocks.iter().map(|(site, _, _)| *site).collect(),
            slice_seeds: blocks.iter().map(|(_, consumer, _)| *consumer).collect(),
        };
        let inputs: BTreeMap<_, _> = cases
            .iter()
            .zip(&blocks)
            .map(|((_, bytes), (site, _, _))| (*site, bytes.clone()))
            .collect();
        let mut source =
            Session::start(&producer(), &snapshot.metadata().snapshot_id, target(linux)).unwrap();
        let lifts = source.lift(&inputs).unwrap();
        source.finish().unwrap();
        for ((name, bytes), (site, _, _)) in cases.iter().zip(&blocks) {
            let lift = &lifts[site];
            assert_eq!(lift.status, "decoded");
            assert_eq!(usize::from(lift.length), bytes.len());
            assert!(!lift.bil.is_empty());
            let access = crate::bap::address::extract(&lift.bil, *site);
            assert_eq!(access.len(), 1, "{name}");
            assert_eq!(access[0].role, MemoryAccessRole::Load);
            assert_eq!(access[0].access_width, 8);
            assert_eq!(access[0].address_width, 64);
            let raw = access[0]
                .expression
                .as_ref()
                .expect("pinned producer exposes the incorrect known address");
            let rax = 0x0000_0001_8000_0001_u64;
            assert!(raw.terms.iter().all(|term| term.bank == 0));
            let observed = raw.terms.iter().fold(raw.constant, |value, term| {
                value.wrapping_add(rax.wrapping_mul(term.coefficient))
            });
            let expected = match *name {
                "eip-relative-high-pc" => {
                    assert!(raw.terms.is_empty());
                    assert_eq!(observed, site + bytes.len() as u64);
                    u64::from((site + bytes.len() as u64) as u32)
                }
                "sib-register-overflow" => {
                    assert_eq!(raw.constant, 0);
                    assert_eq!(raw.terms.len(), 1);
                    assert_eq!(raw.terms[0].coefficient, 2);
                    assert_eq!(observed, rax.wrapping_mul(2));
                    u64::from((rax as u32).wrapping_mul(2))
                }
                "sib-no-base-negative" => {
                    assert!(raw.terms.is_empty());
                    assert_eq!(observed, 0xffff_ffff_8000_0000);
                    0x8000_0000
                }
                _ => unreachable!(),
            };
            assert_ne!(
                observed, expected,
                "bad producer witness disappeared: {name}"
            );
            raw_witnesses += 1;
            for generation in 3..=15 {
                let profile = format!("bap-bit-provenance-v{generation}");
                assert!(crate::bap::known_projection(&profile));
                assert!(crate::bap::admission::guarded_prefix_with_profile(
                    bytes, &profile
                ));
                let error = crate::bap::projection::project_with_destination_profile(
                    &lift.bil,
                    lift.opcode.as_deref().unwrap(),
                    bytes,
                    *site,
                    None,
                    &profile,
                )
                .unwrap_err();
                assert!(error.to_string().contains("unmodeled instruction prefix"));
                assert!(!crate::bap::admission::ordinary_unknown_with_profile(
                    &lift.bil, bytes, &error, &profile
                ));
                profile_refusals += 1;
            }
            assert!(!crate::bap::admission::guarded_prefix_with_profile(
                &bytes[1..],
                "bap-bit-provenance-v6"
            ));
            assert!(
                Backend::guard_normal_projection(
                    &serde_json::to_string(&lift.bil).unwrap(),
                    lift.opcode.as_deref().unwrap(),
                    bytes,
                    *site,
                )
                .err()
                .unwrap()
                .to_string()
                .contains("unmodeled instruction prefix")
            );
        }
        for mode in ["plain", "refinement", "targets"] {
            let prepared = match mode {
                "plain" => snapshot.prepare_with_bap(
                    &query,
                    &decoder(),
                    &producer(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                ),
                "refinement" => snapshot.prepare_with_bap_refinement(
                    &query,
                    &decoder(),
                    &producer(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                ),
                "targets" => snapshot.prepare_with_bap_target_resolution(
                    &query,
                    &decoder(),
                    &producer(),
                    &PreparationOptions::default(),
                    PrepareLimits::default(),
                    crate::bap::target_resolution::Limits::default(),
                ),
                _ => unreachable!(),
            }
            .unwrap();
            assert!(prepared.refinement.is_empty());
            if let Some(report) = prepared.target_resolution() {
                assert!(report.transfers.is_empty());
                assert!(report.resolutions.is_empty());
            }
            assert_eq!(prepared.materialization.attempted, query.entry_points);
            let request = &prepared.prepared.request;
            for (site, consumer, _) in &blocks {
                let evidence = &prepared.prepared.instructions[site];
                assert_eq!(evidence.decoder_control, Some(InstructionKind::Ordinary));
                assert_eq!(evidence.control, Some(InstructionKind::Stop));
                assert_eq!(evidence.quality, EffectQuality::Opaque);
                let semantic = evidence.semantic.as_ref().unwrap();
                assert_eq!(semantic.status, "opaque-unsupported");
                assert!(
                    semantic
                        .gaps
                        .iter()
                        .any(|gap| gap.contains("unmodeled instruction prefix"))
                );
                assert!(semantic.memory_accesses.is_empty());
                assert!(semantic.fallback.is_none());
                let instruction = &request.instructions[site];
                assert_eq!(instruction.kind, InstructionKind::Stop);
                assert!(instruction.fall.is_empty());
                assert!(instruction.targets.is_empty());
                assert!(instruction.must_defs.is_empty());
                assert_eq!(instruction.uses, locations());
                assert_eq!(instruction.may_defs, locations());
                assert!(!request.decodable.contains(site));
                assert!(!prepared.materialization.attempted.contains(consumer));
            }
            let reference =
                CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
            let native = NativeAnalyzer::from_capture(&core(), "mov8-address32-barrier", &prepared)
                .unwrap()
                .complete()
                .unwrap();
            assert_eq!(native.state(), reference.state());
            assert_eq!(native.state().visited, query.entry_points);
            assert!(native.state().decoded.is_empty());
            assert!(native.state().edges.is_empty());
            assert!(native.state().slice.is_empty());
            let expected: BTreeSet<_> = query
                .entry_points
                .iter()
                .map(|&site| Obligation {
                    site,
                    reason: ObligationReason::DecodeFailed,
                })
                .collect();
            assert_eq!(native.state().obligations, expected);
            let result = native.into_result();
            assert_eq!(result.missing_slice_seeds, query.slice_seeds);
            assert!(!result.scope_closed());
            native_preparations += blocks.len();
        }
    }
    assert_eq!(raw_witnesses, 6);
    assert_eq!(profile_refusals, 78);
    assert_eq!(native_preparations, 18);
    eprintln!(
        "MOV8_ADDRESS32_BARRIER actual_bad_lifts=6 profile_refusals=78 native_stopped_instances=18 known_address_claims=0 target_transfers=0 refinement_receipts=0"
    );
}
