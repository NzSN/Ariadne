//! Evidence-bound domain explanations above the normalized analysis result.
mod explain;
mod model;
mod validate;
pub use explain::explain_fault_address;
pub use model::*;
pub use validate::{BoundInvestigation, request_fingerprint};
pub type Error = Box<dyn std::error::Error>;
pub(crate) fn invalid(s: impl Into<String>) -> Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, s.into()).into()
}
pub(crate) fn sha(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}
pub(crate) fn id(kind: &str, scope: &str, value: &impl serde::Serialize) -> String {
    format!(
        "{kind}:{}",
        sha(&serde_json::to_vec(&(kind, scope, value)).expect("owned serializable fact"))
    )
}
