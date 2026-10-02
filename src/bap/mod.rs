//! Optional BAP-owned instruction lifting and conservative projection.
mod address;
mod ast;
mod prepare;
mod projection;
mod session;
pub use prepare::{Backend, Metrics};
pub use session::{Config, Session, helper_identity};
pub type Error = Box<dyn std::error::Error>;
fn invalid(message: impl Into<String>) -> Error {
    std::io::Error::new(std::io::ErrorKind::InvalidData, message.into()).into()
}
