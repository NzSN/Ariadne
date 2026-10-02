//! Strict Stage E inputs and identity-preserving result envelopes.
mod codecs;
mod investigation;
mod render;
pub use codecs::{
    decode_ir_request, decode_machine_request, decode_semantics, encode_ir_request,
    encode_machine_request, encode_semantics, sha256, strict_json, strict_json_with_limit,
};
pub use investigation::{decode_explanation, encode_explanation, render_explanation};
pub use render::{Format, ir_report, machine_report, publish_all, render_report};

pub type Error = Box<dyn std::error::Error>;
pub(crate) fn invalid(message: impl Into<String>) -> Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, message.into()).into()
}
