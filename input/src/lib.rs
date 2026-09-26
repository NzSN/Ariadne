//! Immutable Windows/Linux AMD64 minidump input. No image-file fallback.
mod address_space;
mod materialize;
mod minidump;

pub use address_space::{ByteRead, CaptureSource, ReadSpan, ReadStop};
use ariadne::Address;
use ariadne::llvm_mc::DecoderTarget;
pub use materialize::{
    AnalysisQuery, FilePreparedAnalysis, MaterializationReport, PreparationError, PrepareLimits,
};
use std::collections::BTreeMap;
use std::fmt;
use std::path::Path;
use std::sync::Arc;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Platform {
    Windows,
    Linux,
}
impl Platform {
    pub fn decoder_target(self) -> DecoderTarget {
        match self {
            Self::Windows => DecoderTarget::WindowsAmd64,
            Self::Linux => DecoderTarget::LinuxAmd64,
        }
    }
}
#[derive(Clone, Debug)]
pub struct OpenLimits {
    pub max_file_bytes: usize,
    pub max_streams: usize,
    pub max_records: usize,
    pub max_metadata_bytes: usize,
    pub max_capture_ranges: usize,
    pub max_overlap: usize,
    pub max_read_bytes: usize,
}
impl Default for OpenLimits {
    fn default() -> Self {
        Self {
            max_file_bytes: 256 * 1024 * 1024,
            max_streams: 1024,
            max_records: 131072,
            max_metadata_bytes: 16 * 1024 * 1024,
            max_capture_ranges: 131072,
            max_overlap: 64,
            max_read_bytes: 65536,
        }
    }
}
#[derive(Debug)]
pub enum InputError {
    Io(std::io::Error),
    Malformed(String),
    Unsupported(String),
    Limit(&'static str),
}
impl fmt::Display for InputError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(e) => write!(f, "input I/O: {e}"),
            Self::Malformed(e) => write!(f, "malformed minidump: {e}"),
            Self::Unsupported(e) => write!(f, "unsupported minidump: {e}"),
            Self::Limit(e) => write!(f, "input limit: {e}"),
        }
    }
}
impl std::error::Error for InputError {}
impl From<std::io::Error> for InputError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}
pub(crate) fn malformed(s: impl Into<String>) -> InputError {
    InputError::Malformed(s.into())
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamInfo {
    pub kind: u32,
    pub file_offset: u64,
    pub size: u64,
    pub supported: bool,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModuleInfo {
    pub name: String,
    pub base: Address,
    pub size: u64,
    pub timestamp: u32,
    pub checksum: u32,
    /// Opaque CodeView identity evidence, not authorization to open another file.
    pub codeview: Vec<u8>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ThreadInfo {
    pub id: u32,
    pub registers: BTreeMap<String, u64>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExceptionInfo {
    pub thread_id: u32,
    pub code: u32,
    pub reported_address: Address,
    pub registers: BTreeMap<String, u64>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MemoryInfo {
    pub base: Address,
    pub size: u64,
    pub protection: u32,
    pub state: u32,
    pub kind: u32,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MetadataGap {
    pub stream: u32,
    pub entry: Option<usize>,
    pub reason: String,
}
#[derive(Clone, Debug)]
pub struct SnapshotMetadata {
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub platform: Platform,
    pub artifact_bytes: usize,
    pub streams: Vec<StreamInfo>,
    pub modules: Vec<ModuleInfo>,
    pub threads: Vec<ThreadInfo>,
    pub exception: Option<ExceptionInfo>,
    pub memory_info: Vec<MemoryInfo>,
    pub gaps: Vec<MetadataGap>,
}

/// Owns the exact bytes whose digest identifies this snapshot. No live file or
/// module-path lookup is retained. All memory contributors remain inspectable.
#[derive(Debug)]
pub struct FileSnapshot {
    pub(crate) bytes: Arc<[u8]>,
    pub(crate) metadata: Arc<SnapshotMetadata>,
    pub(crate) captures: Vec<address_space::Capture>,
    pub(crate) tree: Option<Box<address_space::Node>>,
    pub(crate) limits: OpenLimits,
}
impl FileSnapshot {
    pub fn open_minidump(path: impl AsRef<Path>, limits: OpenLimits) -> Result<Self, InputError> {
        use std::io::Read;
        let file = std::fs::File::open(path)?;
        if file.metadata()?.len() > limits.max_file_bytes as u64 {
            return Err(InputError::Limit("artifact bytes"));
        }
        let mut bytes = Vec::new();
        file.take((limits.max_file_bytes as u64).saturating_add(1))
            .read_to_end(&mut bytes)?;
        Self::from_minidump_bytes(bytes, limits)
    }
    pub fn from_minidump_bytes(bytes: Vec<u8>, limits: OpenLimits) -> Result<Self, InputError> {
        minidump::parse(bytes, limits)
    }
    pub fn metadata(&self) -> &SnapshotMetadata {
        &self.metadata
    }
}
