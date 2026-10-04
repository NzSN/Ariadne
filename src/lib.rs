//! An executable implementation of `Specs/Ariadne.tla`.
//!
//! Inputs are fixed byte-availability facts and normalized instruction summaries
//! supplied by trusted adapters. This crate implements local CFG recovery,
//! may-reaching definitions, and backward data slicing.
//!
//! ```
//! use ariadne::{analyze, AnalysisRequest, Instruction, InstructionKind};
//!
//! let request = AnalysisRequest {
//!     snapshot_id: "example-snapshot".into(),
//!     addresses: [4096, 4100].into(),
//!     locations: ["x".into()].into(),
//!     entry_points: [4096].into(),
//!     slice_seeds: [4100].into(),
//!     file_backed: [4096, 4100].into(),
//!     decodable: [4096, 4100].into(),
//!     instructions: [
//!         (4096, Instruction {
//!             kind: InstructionKind::Ordinary,
//!             fall: [4100].into(),
//!             must_defs: ["x".into()].into(),
//!             may_defs: ["x".into()].into(),
//!             ..Instruction::default()
//!         }),
//!         (4100, Instruction {
//!             kind: InstructionKind::Return,
//!             uses: ["x".into()].into(),
//!             ..Instruction::default()
//!         }),
//!     ].into(),
//!     ..AnalysisRequest::default()
//! };
//! let result = analyze(request)?;
//! assert_eq!(result.state.slice, [4096, 4100].into());
//! assert!(result.scope_closed());
//! # Ok::<(), ariadne::InvalidRequest>(())
//! ```

#![forbid(unsafe_code)]

#[cfg(feature = "bap")]
pub mod bap;
#[cfg(feature = "input")]
pub mod input;
#[cfg(feature = "investigation")]
pub mod investigation;
#[cfg(feature = "ir")]
pub mod ir;
#[cfg(feature = "mbt")]
pub mod mbt;
#[cfg(feature = "reports")]
pub mod reports;

mod analysis_view;
pub mod effects;
mod engine;
pub use analysis_view::{AnalysisView, CompletedAnalysis};
pub mod llvm_ir;
pub mod llvm_mc;
pub mod machine_state;
mod model;
pub mod render;

pub use engine::{Analyzer, AnalyzerMetrics, analyze};
pub use model::*;

/// Version of the analysis package, for report identity.
pub const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");
