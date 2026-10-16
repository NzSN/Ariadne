use ariadne::input::{MaterializationReport, PreparationError};
use ariadne::investigation::{
    FrameStructureDiagnostic, FrameStructureDiagnosticKind, FrameStructureLimits,
};

#[test]
fn hard_preparation_limit_reports_referenced_minus_attempted_without_trusted_graph() {
    let progress = MaterializationReport {
        attempted: [0x1000, 0x1004].into(),
        referenced: [0x1000, 0x1004, 0x1008].into(),
        // An early hard failure has not finalized this cached report field.
        unattempted_references: Default::default(),
        ..MaterializationReport::default()
    };
    let error = PreparationError::LimitReached {
        reason: "fixture-start-cap",
        progress: Box::new(progress),
    };
    let diagnostic = FrameStructureDiagnostic::from_preparation_error(2, &error);
    assert_eq!(
        diagnostic.kind,
        FrameStructureDiagnosticKind::PreparationLimit
    );
    assert_eq!(diagnostic.unattempted_references, vec![0x1008]);
    assert_eq!(diagnostic.attempted, vec![0x1000, 0x1004]);
}

#[test]
fn independent_structural_policy_carries_large_runtime_tables_and_proofs() {
    let limits = FrameStructureLimits::default();
    assert!(limits.unwind_limits().max_runtime_entries >= 131_072);
    assert!(limits.max_proof_bytes >= 33 * 1024 * 1024);
    assert!(limits.max_graph_nodes > 10_000);
    assert_eq!(limits.open_limits().max_read_bytes, limits.max_read_bytes);
    let mut raw = serde_json::to_value(&limits).unwrap();
    raw["unknown_policy"] = serde_json::json!(1);
    assert!(serde_json::from_value::<FrameStructureLimits>(raw).is_err());
}
