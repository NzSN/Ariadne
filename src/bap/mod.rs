//! Optional BAP-owned instruction lifting and conservative projection.
pub(crate) mod address;
mod admission;
pub mod alignment_hypothesis;
pub(crate) mod ast;
pub mod composition;
pub mod core_adapter;
pub mod core_protocol;
pub mod core_session;
pub mod guard_admission;
mod prepare;
pub(crate) mod projection;
mod registers;
pub(crate) mod terminal_control;
pub(crate) const PROJECTION: &str = "bap-bit-provenance-v6";
pub(crate) const OPAQUE_ORDINARY_RULE: &str = "bap-opaque-ordinary-v4";
pub(crate) fn known_projection(profile: &str) -> bool {
    matches!(
        profile,
        "bap-bit-provenance-v3"
            | "bap-bit-provenance-v4"
            | "bap-bit-provenance-v5"
            | PROJECTION
            | source_extension::PROFILE
            | source_extension::ADVANCED_PROFILE
            | source_extension::ADVANCED_GUARDED_PROFILE
            | guard_admission::LEGACY_PRODUCER_PROFILE
            | guard_admission::PRODUCER_PROFILE
    )
}
#[cfg(test)]
#[path = "../../tests/bap/guard_admission_unit.rs"]
mod guard_admission_tests;
#[cfg(test)]
#[path = "../../tests/bap/shift_projection_unit.rs"]
mod shift_projection_tests;
#[cfg(test)]
#[path = "../../tests/bap/vector_projection_unit.rs"]
mod vector_projection_tests;
#[cfg(test)]
pub(crate) use projection::project as test_project;
pub(crate) mod refinement;
mod session;
mod source_extension;
pub mod stateflow_adapter;
pub mod target_resolution;
pub use prepare::{Backend, Metrics};
pub use session::{Config, Session, SourceExtensionMode, helper_identity};
pub(crate) fn advanced_projection(profile: &str) -> bool {
    matches!(
        profile,
        source_extension::ADVANCED_PROFILE | source_extension::ADVANCED_GUARDED_PROFILE
    )
}
pub type Error = Box<dyn std::error::Error>;
fn invalid(message: impl Into<String>) -> Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, message.into()).into()
}

pub(crate) mod work_schedule;
