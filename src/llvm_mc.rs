//! Snapshot byte spans to `AnalysisRequest` through the pinned native LLVM MC decoder.
//! The native tool is an explicit dependency of this adapter, never of the core.

mod prepare;
pub(crate) mod protocol;

use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::{
    Address, AddressSet, AnalysisRequest, InputKind, Instruction, InstructionKind, InvalidRequest,
    LocationSet,
};

/// Candidate byte spans, keyed by semantic virtual address.
/// The first 15 bytes at each start are offered to LLVM MC. Each map belongs to
/// one immutable snapshot. File fallback in a dump requires explicit trust.
#[derive(Clone, Debug, Default)]
pub struct ByteSnapshot {
    pub snapshot_id: String,
    pub input_kind: InputKind,
    pub captured: BTreeMap<Address, Vec<u8>>,
    pub file_backed: BTreeMap<Address, Vec<u8>>,
    pub trusted_fallback: AddressSet,
    pub entry_points: AddressSet,
    pub slice_seeds: AddressSet,
    pub locations: LocationSet,
}

#[derive(Debug)]
pub enum AdapterError {
    InvalidInput(String),
    DecoderIo(std::io::Error),
    DecoderFailure(String),
    DecoderProtocol(String),
    InvalidRequest(InvalidRequest),
}

impl fmt::Display for AdapterError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidInput(message) => write!(f, "invalid byte snapshot: {message}"),
            Self::DecoderIo(error) => write!(f, "LLVM MC decoder I/O: {error}"),
            Self::DecoderFailure(message) => write!(f, "LLVM MC decoder failed: {message}"),
            Self::DecoderProtocol(message) => write!(f, "LLVM MC decoder protocol: {message}"),
            Self::InvalidRequest(error) => write!(f, "normalized request: {error}"),
        }
    }
}

impl Error for AdapterError {}

impl From<std::io::Error> for AdapterError {
    fn from(error: std::io::Error) -> Self {
        Self::DecoderIo(error)
    }
}

pub(crate) struct Decoded {
    pub(crate) address: Address,
    pub(crate) status: String,
    pub(crate) length: u64,
    pub(crate) kind: Option<InstructionKind>,
    pub(crate) target: Option<Address>,
}

fn decode_row(row: &str) -> Result<Decoded, AdapterError> {
    let fields: Vec<_> = row.split_ascii_whitespace().collect();
    if fields.len() != 5 {
        return Err(AdapterError::DecoderProtocol(format!(
            "expected five fields, received {row:?}"
        )));
    }
    let number = |text: &str| {
        text.parse::<u64>().map_err(|_| {
            AdapterError::DecoderProtocol(format!("invalid unsigned integer {text:?}"))
        })
    };
    let kind = match fields[3] {
        "ordinary" => Some(InstructionKind::Ordinary),
        "conditional" => Some(InstructionKind::Conditional),
        "jump" => Some(InstructionKind::Jump),
        "indirect" => Some(InstructionKind::Indirect),
        "call" => Some(InstructionKind::Call),
        "return" => Some(InstructionKind::Return),
        "stop" => Some(InstructionKind::Stop),
        "-" => None,
        other => {
            return Err(AdapterError::DecoderProtocol(format!(
                "unknown instruction kind {other:?}"
            )));
        }
    };
    let target = if fields[4] == "-" {
        None
    } else {
        Some(number(fields[4])?)
    };
    Ok(Decoded {
        address: number(fields[0])?,
        status: fields[1].to_owned(),
        length: number(fields[2])?,
        kind,
        target,
    })
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        result.push(DIGITS[(byte >> 4) as usize] as char);
        result.push(DIGITS[(byte & 15) as usize] as char);
    }
    result
}

fn invoke_decoder(executable: &Path, input: String) -> Result<String, AdapterError> {
    let version = Command::new(executable).arg("--version").output()?;
    if !version.status.success() || version.stdout != b"ariadne-llvm-mc 20.1.2\n" {
        return Err(AdapterError::DecoderFailure(
            "expected ariadne-llvm-mc 20.1.2".into(),
        ));
    }
    let mut child = Command::new(executable)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| AdapterError::DecoderProtocol("decoder stdin was not piped".into()))?;
    let writer = std::thread::spawn(move || stdin.write_all(input.as_bytes()));
    let output = child.wait_with_output()?;
    writer
        .join()
        .map_err(|_| AdapterError::DecoderIo(std::io::Error::other("writer panicked")))??;
    if !output.status.success() {
        return Err(AdapterError::DecoderFailure(
            String::from_utf8_lossy(&output.stderr).trim().into(),
        ));
    }
    String::from_utf8(output.stdout)
        .map_err(|_| AdapterError::DecoderProtocol("non-UTF-8 decoder output".into()))
}

impl ByteSnapshot {
    /// Build the core's fixed request. Unknown instruction effects read and may
    /// write every tracked location; they never kill an earlier origin.
    pub fn to_request(&self, decoder: &Path) -> Result<AnalysisRequest, AdapterError> {
        if self.snapshot_id.is_empty() || self.entry_points.is_empty() {
            return Err(AdapterError::InvalidInput(
                "snapshot_id and entry_points must be nonempty".into(),
            ));
        }
        if !self
            .trusted_fallback
            .iter()
            .all(|address| self.file_backed.contains_key(address))
        {
            return Err(AdapterError::InvalidInput(
                "trusted_fallback must be a subset of file_backed".into(),
            ));
        }
        let mut request = AnalysisRequest {
            snapshot_id: self.snapshot_id.clone(),
            input_kind: self.input_kind,
            entry_points: self.entry_points.clone(),
            slice_seeds: self.slice_seeds.clone(),
            locations: self.locations.clone(),
            ..AnalysisRequest::default()
        };
        request.addresses.extend(self.entry_points.iter().copied());
        request.addresses.extend(self.slice_seeds.iter().copied());
        request.addresses.extend(self.captured.keys().copied());
        request.addresses.extend(self.file_backed.keys().copied());

        let selected: BTreeMap<_, _> = request
            .addresses
            .iter()
            .filter_map(|address| {
                let bytes = match self.input_kind {
                    InputKind::Binary => self.file_backed.get(address),
                    InputKind::Dump => self.captured.get(address).or_else(|| {
                        self.trusted_fallback
                            .contains(address)
                            .then(|| self.file_backed.get(address))
                            .flatten()
                    }),
                }?;
                Some((*address, bytes))
            })
            .collect();
        if selected.values().any(|bytes| bytes.is_empty()) {
            return Err(AdapterError::InvalidInput(
                "available byte spans must be nonempty".into(),
            ));
        }
        let input = selected
            .iter()
            .map(|(address, bytes)| format!("{address} {}\n", hex(&bytes[..bytes.len().min(15)])))
            .collect::<String>();
        let output = invoke_decoder(decoder, input)?;
        let mut seen = BTreeSet::new();
        for row in output.lines() {
            let decoded = decode_row(row)?;
            let Some(bytes) = selected.get(&decoded.address) else {
                return Err(AdapterError::DecoderProtocol(format!(
                    "unexpected VA {}",
                    decoded.address
                )));
            };
            if !seen.insert(decoded.address) {
                return Err(AdapterError::DecoderProtocol(format!(
                    "duplicate VA {}",
                    decoded.address
                )));
            }
            // A failed decode with fewer than 15 bytes may be truncated. Do
            // not claim a complete instruction span in the fixed TLA+ input.
            // A captured partial span also blocks file fallback at that VA.
            if decoded.status != "invalid" || bytes.len() >= 15 {
                match self.input_kind {
                    InputKind::Binary => {
                        request.file_backed.insert(decoded.address);
                    }
                    InputKind::Dump if self.captured.contains_key(&decoded.address) => {
                        request.captured.insert(decoded.address);
                    }
                    InputKind::Dump => {
                        request.file_backed.insert(decoded.address);
                        request.trusted_fallback.insert(decoded.address);
                    }
                }
            }
            if decoded.status != "ok" {
                if decoded.status != "invalid" && decoded.status != "unsupported" {
                    return Err(AdapterError::DecoderProtocol(format!(
                        "unknown status {:?}",
                        decoded.status
                    )));
                }
                if decoded.kind.is_some() || decoded.target.is_some() {
                    return Err(AdapterError::DecoderProtocol(
                        "failed decode supplied a kind or target".into(),
                    ));
                }
                if (decoded.status == "invalid" && decoded.length != 0)
                    || (decoded.status == "unsupported"
                        && (decoded.length == 0 || decoded.length > bytes.len().min(15) as u64))
                {
                    return Err(AdapterError::DecoderProtocol(
                        "failed decode has invalid length".into(),
                    ));
                }
                continue;
            }
            if decoded.length == 0 || decoded.length > bytes.len().min(15) as u64 {
                return Err(AdapterError::DecoderProtocol(
                    "successful decode has invalid length".into(),
                ));
            }
            let kind = decoded.kind.ok_or_else(|| {
                AdapterError::DecoderProtocol("successful decode has no kind".into())
            })?;
            let needs_fall = matches!(
                kind,
                InstructionKind::Ordinary | InstructionKind::Conditional | InstructionKind::Call
            );
            let fall = if needs_fall {
                [decoded.address.checked_add(decoded.length).ok_or_else(|| {
                    AdapterError::DecoderProtocol("fallthrough VA overflow".into())
                })?]
                .into()
            } else {
                AddressSet::new()
            };
            if matches!(kind, InstructionKind::Conditional | InstructionKind::Jump)
                != decoded.target.is_some()
                && kind != InstructionKind::Call
            {
                return Err(AdapterError::DecoderProtocol(
                    "branch target shape does not match kind".into(),
                ));
            }
            if !matches!(
                kind,
                InstructionKind::Conditional | InstructionKind::Jump | InstructionKind::Call
            ) && decoded.target.is_some()
            {
                return Err(AdapterError::DecoderProtocol(
                    "non-branch supplied a target".into(),
                ));
            }
            let targets: AddressSet = decoded.target.into_iter().collect();
            request.addresses.extend(fall.iter().copied());
            request.addresses.extend(targets.iter().copied());
            request.decodable.insert(decoded.address);
            request.instructions.insert(
                decoded.address,
                Instruction {
                    kind,
                    fall,
                    targets,
                    complete: kind != InstructionKind::Indirect
                        && (kind != InstructionKind::Call || decoded.target.is_some()),
                    uses: self.locations.clone(),
                    may_defs: self.locations.clone(),
                    must_defs: LocationSet::new(),
                },
            );
        }
        if seen.len() != selected.len() {
            return Err(AdapterError::DecoderProtocol(
                "decoder omitted one or more addresses".into(),
            ));
        }
        for address in &request.addresses {
            request.instructions.entry(*address).or_default();
        }
        request.validate().map_err(AdapterError::InvalidRequest)?;
        Ok(request)
    }
}

/// Decoder profile records target OS without importing calling-convention claims.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DecoderTarget {
    WindowsAmd64,
    LinuxAmd64,
}
impl DecoderTarget {
    pub fn triple(self) -> &'static str {
        match self {
            Self::WindowsAmd64 => "x86_64-pc-windows-msvc",
            Self::LinuxAmd64 => "x86_64-unknown-linux-gnu",
        }
    }
}

/// One explicitly requested candidate. Referenced successors are not implicitly
/// included; an input materializer decides which prefixes to acquire next.
#[derive(Clone, Debug)]
pub struct PreparedSite {
    pub instruction: Instruction,
    pub evidence: crate::effects::InstructionEvidence,
    pub gaps: Vec<crate::effects::PreparationGap>,
    pub decodable: bool,
    pub complete_capture: bool,
}
#[derive(Clone, Debug)]
pub struct PreparedBatch {
    pub sites: BTreeMap<Address, PreparedSite>,
    pub identity: crate::effects::PreparationIdentity,
}

/// Shared bounded-batch seam for captured-memory providers. None means no
/// available prefix; Some must contain 1..15 bytes. No Analyzer is run here.
/// The candidate set is used only to validate preparation's finite input domain;
/// it does not turn candidates into entry roots of the eventual analysis.
pub fn prepare_captured_batch(
    snapshot_id: &str,
    candidates: &BTreeMap<Address, Option<Vec<u8>>>,
    decoder: &Path,
    options: &crate::effects::PreparationOptions,
    target: DecoderTarget,
) -> Result<PreparedBatch, AdapterError> {
    if candidates.is_empty()
        || candidates
            .values()
            .flatten()
            .any(|b| b.is_empty() || b.len() > 15)
    {
        return Err(AdapterError::InvalidInput(
            "batch must have candidates with absent or 1..15-byte prefixes".into(),
        ));
    }
    let snapshot = ByteSnapshot {
        snapshot_id: snapshot_id.into(),
        input_kind: InputKind::Dump,
        captured: candidates
            .iter()
            .filter_map(|(a, b)| b.as_ref().map(|b| (*a, b.clone())))
            .collect(),
        entry_points: candidates.keys().copied().collect(),
        locations: options.catalogue.locations(),
        ..ByteSnapshot::default()
    };
    let mut prepared = snapshot.prepare_with_target(decoder, options, target)?;
    let mut sites = BTreeMap::new();
    for &address in candidates.keys() {
        sites.insert(
            address,
            PreparedSite {
                instruction: prepared
                    .request
                    .instructions
                    .remove(&address)
                    .expect("total domain"),
                evidence: prepared
                    .instructions
                    .remove(&address)
                    .expect("candidate evidence"),
                gaps: prepared
                    .gaps
                    .iter()
                    .filter(|g| g.address == address)
                    .cloned()
                    .collect(),
                decodable: prepared.request.decodable.contains(&address),
                complete_capture: prepared.request.captured.contains(&address),
            },
        );
    }
    Ok(PreparedBatch {
        sites,
        identity: prepared.identity,
    })
}
