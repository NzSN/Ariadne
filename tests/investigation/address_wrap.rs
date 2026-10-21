//! W2 public-binding pilot; shared fixtures keep report tests on the same owned seam.
//! Five ordinary tests supply finite summaries; the ignored native gate remains separate.
#[path = "../common/address_wrap.rs"]
mod address_wrap_fixture;
use address_wrap_fixture::{
    SITE, assert_capture_identity, assert_oracle, limits, oracle, pipeline, prepare, question,
};
use ariadne::effects::PreparationOptions;
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::investigation::{AddressWrapLimits, FaultAddressQuestion, ZeroAddressConclusion};
use ariadne::{Analyzer, CompletedAnalysis};
use std::path::PathBuf;

#[test]
fn pilot_signed_displacement_answers_match_independent_integer_oracle() {
    assert_eq!(AddressWrapLimits::default().max_evidence, 64);
    assert_eq!(AddressWrapLimits::default().max_claims, 64);
    for name in [
        "mov32mi-upper",
        "mov32mi-upper-boundary",
        "mov32mi-ordinary-positive",
        "mov32mi-no-displacement",
        "mov32mi-negative-zero",
        "mov32mi-negative-nonzero",
    ] {
        let row = oracle(name);
        let (prepared, completed) = prepare(name, |_| {});
        let result = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
        assert_oracle(&result, &row);
    }
}

#[test]
fn late_fault_gaps_retain_arithmetic_with_an_unknown_assessment() {
    for name in ["mov32mi-underflow", "reported-before", "reported-after32"] {
        let row = oracle(name);
        let (prepared, completed) = prepare(name, |_| {});
        let result = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
        assert_oracle(&result, &row);
        assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
        assert!(result.arithmetic.is_some());
        assert!(!result.truncated);
    }
}

#[test]
fn early_gaps_do_not_publish_arithmetic_or_partial_derived_claims() {
    for name in [
        "missing-integer",
        "wrong-operation",
        "missing-decoded-receipt",
        "missing-decoder-identity",
        "decoder-bap-constant-disagreement",
    ] {
        let row = oracle(name);
        let (prepared, completed) = prepare(name, |_| {});
        let result = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
        assert_oracle(&result, &row);
        assert_eq!(result.conclusion, ZeroAddressConclusion::Unknown);
    }
}

#[test]
fn tiny_and_exact_budgets_follow_the_frozen_atomic_publication_boundary() {
    let (prepared, completed) = prepare("mov32mi-upper", |_| {});
    for name in [
        "budget-e0-c64",
        "budget-e1-c64",
        "budget-e31-c64",
        "budget-e32-c64",
        "budget-e33-c64",
        "budget-e34-c64",
        "budget-e64-c0",
        "budget-e64-c30",
        "budget-e64-c35",
        "budget-e64-c36",
        "budget-e64-c37",
        "budget-e0-c0",
    ] {
        let row = oracle(name);
        let result = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
        assert_oracle(&result, &row);
    }
    let exact = pipeline(
        &prepared,
        &completed,
        question(),
        AddressWrapLimits {
            max_evidence: 33,
            max_claims: 36,
        },
    )
    .unwrap();
    assert_eq!(
        exact.conclusion,
        ZeroAddressConclusion::ConsistentWithEvidence
    );
    assert_eq!(exact.evidence.len(), 33);
    assert_eq!(exact.claims.len(), 36);
    assert!(!exact.truncated);
}

#[test]
fn malformed_or_changed_bindings_fail_even_for_zero_output_limits() {
    let (prepared, completed) = prepare("mov32mi-upper", |_| {});
    let (malformed, malformed_completed) = prepare("mov32mi-upper", |site| {
        site.decoded_address.as_mut().unwrap().decoder_sha256 = Some("invalid".into());
    });
    let mut changed = prepared.clone();
    changed
        .prepared
        .instructions
        .get_mut(&SITE)
        .unwrap()
        .decoded_address = None;
    let mut other_request = prepared.prepared.request.clone();
    other_request.slice_seeds.clear();
    let other_query = CompletedAnalysis::from_analyzer(Analyzer::new(other_request).unwrap());
    for limits in [
        AddressWrapLimits {
            max_evidence: 0,
            max_claims: 0,
        },
        AddressWrapLimits::default(),
    ] {
        assert!(pipeline(&malformed, &malformed_completed, question(), limits).is_err());
        assert!(pipeline(&changed, &completed, question(), limits).is_err());
        assert!(pipeline(&prepared, &other_query, question(), limits).is_err());
        assert!(
            pipeline(
                &prepared,
                &completed,
                FaultAddressQuestion {
                    site: SITE + 1,
                    memory_access: 0
                },
                limits
            )
            .is_err()
        );
        assert!(
            pipeline(
                &prepared,
                &completed,
                FaultAddressQuestion {
                    site: SITE,
                    memory_access: 1
                },
                limits
            )
            .is_err()
        );
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime; explicitly qualify remotely"]
fn native_preparation_and_native_analysis_match_the_public_mov32mi_pilot() {
    use ariadne::bap::core_adapter::NativeAnalyzer;
    use ariadne::bap::core_session::CoreConfig;

    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/ariadne-llvm-mc"));
    let core = std::env::var_os("ARIADNE_BAP_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/qualification-native"));
    for name in [
        "mov32mi-upper",
        "mov32mi-ordinary-positive",
        "mov32mi-negative-zero",
        "mov32mi-negative-nonzero",
        "mov32mi-underflow",
        "missing-integer",
        "wrong-operation",
    ] {
        let row = oracle(name);
        let snapshot = FileSnapshot::open_minidump(
            root.join("tests/input/fixtures/i5c/dumps")
                .join(format!("{name}.dmp")),
            OpenLimits::default(),
        )
        .unwrap();
        assert_capture_identity(&snapshot, name);
        let prepared = snapshot
            .prepare(
                &AnalysisQuery {
                    entry_points: [SITE].into(),
                    slice_seeds: [SITE].into(),
                },
                &decoder,
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        let completed = NativeAnalyzer::from_capture(
            &CoreConfig::from_directory(core.clone()),
            "minidump-analysis",
            &prepared,
        )
        .unwrap()
        .complete()
        .unwrap();
        let result = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
        assert_oracle(&result, &row);
        if name == "mov32mi-upper" {
            for budget in [
                "budget-e32-c64",
                "budget-e64-c35",
                "budget-e64-c36",
                "budget-e0-c0",
            ] {
                let expected = oracle(budget);
                let result =
                    pipeline(&prepared, &completed, question(), limits(&expected)).unwrap();
                assert_oracle(&result, &expected);
            }
            for limits in [
                AddressWrapLimits {
                    max_evidence: 0,
                    max_claims: 0,
                },
                AddressWrapLimits::default(),
            ] {
                assert!(
                    pipeline(
                        &prepared,
                        &completed,
                        FaultAddressQuestion {
                            site: SITE,
                            memory_access: 1
                        },
                        limits,
                    )
                    .is_err()
                );
            }
        }
    }
}
