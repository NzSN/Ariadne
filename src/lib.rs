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

pub mod effects;
mod engine;
pub mod llvm_mc;
mod model;

pub use engine::{Analyzer, analyze};
pub use model::*;
