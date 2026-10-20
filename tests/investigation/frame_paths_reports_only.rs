//! Feature-boundary control using the tiny fixture exported by the BAP unit test.
use super::*;

#[test]
#[ignore = "requires ARIADNE_FRAME_PATH_FEATURE_FIXTURE exported by the explicit graph policy test"]
fn explicit_policy_requires_proof_feature_for_known_profiles() {
    let path = std::env::var_os("ARIADNE_FRAME_PATH_FEATURE_FIXTURE")
        .expect("set the tiny explicit-policy fixture path");
    let bytes = std::fs::read(path).unwrap();
    let listing = crate::reports::decode_frame_paths(&bytes).unwrap();
    assert_eq!(listing.schema, LIMITED_FRAME_PATH_SCHEMA);
    for profile in [
        "bap-guard-admission-v1",
        "bap-guard-admission-v2",
        "captured-guarded-targets/v1",
        "captured-guarded-targets/v2",
        "captured-guarded-targets/v3",
    ] {
        let mut source = listing.input.clone();
        source.graphs[0].identity.semantic_profile = format!("fixture:{profile}:evidence");
        let error = list(
            source.clone(),
            listing.question.clone(),
            listing.limits.clone(),
            Some(usize::MAX),
        )
        .unwrap_err();
        assert_eq!(
            error.to_string(),
            "explicit frame graph proof profile requires bap feature",
            "{profile}"
        );
        // Preserve the preexisting generic-v1 premise behavior; this change
        // closes only the same-v7-schema feature gap.
        source.graph_limits = None;
        let legacy = list(
            source,
            listing.question.clone(),
            listing.limits.clone(),
            Some(usize::MAX),
        )
        .unwrap();
        assert_eq!(legacy.schema, FRAME_PATH_SCHEMA);
        legacy.validate().unwrap();
    }
    let mut source = listing.input;
    source.graphs[0].identity.semantic_profile = "independent-normalized-graph-fixture/v99".into();
    let ordinary = list(source, listing.question, listing.limits, Some(usize::MAX)).unwrap();
    assert_eq!(ordinary.schema, LIMITED_FRAME_PATH_SCHEMA);
    ordinary.validate().unwrap();
}
