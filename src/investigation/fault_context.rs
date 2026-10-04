//! Normalized, source-bound exception observations used by the numeric question.
use super::{BoundInvestigation, Error, Identity, invalid, sha, validate::digest};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub(crate) const GPRS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FaultSpan {
    #[serde(with = "super::model::va")]
    pub file_offset: u64,
    pub length: usize,
    pub sha256: String,
}
impl FaultSpan {
    pub(crate) fn validate(&self, artifact_bytes: u64) -> Result<(), Error> {
        if self.length == 0
            || !digest(&self.sha256)
            || self
                .file_offset
                .checked_add(self.length as u64)
                .is_none_or(|end| end > artifact_bytes)
        {
            return Err(invalid("invalid fault-evidence span"));
        }
        Ok(())
    }
    fn contains(&self, span: &Self) -> bool {
        span.file_offset >= self.file_offset
            && span
                .file_offset
                .checked_add(span.length as u64)
                .zip(self.file_offset.checked_add(self.length as u64))
                .is_some_and(|(end, limit)| end <= limit)
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FaultObservation {
    pub name: String,
    #[serde(with = "super::model::va")]
    pub value: u64,
    pub source: FaultSpan,
    pub bytes_hex: String,
}
impl FaultObservation {
    fn width(&self) -> Option<usize> {
        match self.name.as_str() {
            "thread_id" | "code" | "flags" | "number_parameters" | "context_size"
            | "context_offset" | "context_flags" | "reg:rflags" => Some(4),
            "chain" | "exception_location" | "reg:rip" => Some(8),
            name if name.strip_prefix("reg:").is_some_and(|r| GPRS.contains(&r)) => Some(8),
            name if name
                .strip_prefix("parameter:")
                .and_then(|i| i.parse::<usize>().ok())
                .is_some_and(|i| i < 15 && name == format!("parameter:{i}")) =>
            {
                Some(8)
            }
            _ => None,
        }
    }
    fn validate(&self, artifact_bytes: u64) -> Result<(), Error> {
        self.source.validate(artifact_bytes)?;
        let width = self
            .width()
            .ok_or_else(|| invalid("unknown fault observation"))?;
        if self.source.length != width
            || self.bytes_hex.len() != width * 2
            || !self
                .bytes_hex
                .bytes()
                .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
        {
            return Err(invalid("invalid observation width/bytes"));
        }
        let bytes: Vec<_> = (0..self.bytes_hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&self.bytes_hex[i..i + 2], 16).expect("checked hex"))
            .collect();
        let value = bytes
            .iter()
            .enumerate()
            .fold(0u64, |n, (i, b)| n | (u64::from(*b) << (i * 8)));
        if sha(&bytes) != self.source.sha256 || value != self.value {
            return Err(invalid("observation disagrees with retained bytes"));
        }
        Ok(())
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum FaultDatum {
    Record { span: FaultSpan },
    Context { span: FaultSpan },
    Field { observation: FaultObservation },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FaultMetadata {
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub artifact_bytes: u64,
    pub platform: String,
    pub exception_present: bool,
    pub context_supported: bool,
    pub gaps: Vec<String>,
}
#[derive(Clone, Debug)]
pub(crate) struct CapturedFaultContext {
    pub metadata: FaultMetadata,
    pub data: Vec<FaultDatum>,
}
impl CapturedFaultContext {
    pub fn digest(&self) -> String {
        sha(&serde_json::to_vec(&(&self.metadata, &self.data)).expect("owned fault observations"))
    }
    #[cfg(feature = "input")]
    pub fn validate(&self, complete: bool) -> Result<(), Error> {
        validate_context(&self.metadata, &self.data, complete)
    }
}

pub(crate) fn values(data: &[FaultDatum]) -> BTreeMap<&str, u64> {
    data.iter()
        .filter_map(|d| {
            if let FaultDatum::Field { observation: o } = d {
                Some((o.name.as_str(), o.value))
            } else {
                None
            }
        })
        .collect()
}
pub(crate) fn validate_context(
    meta: &FaultMetadata,
    data: &[FaultDatum],
    complete: bool,
) -> Result<(), Error> {
    if !digest(&meta.artifact_sha256)
        || meta.snapshot_id.is_empty()
        || meta.artifact_bytes == 0
        || !["windows-amd64", "linux-amd64"].contains(&meta.platform.as_str())
    {
        return Err(invalid("invalid fault context identity"));
    }
    let mut record = None;
    let mut context = None;
    let mut fields = BTreeMap::new();
    for d in data {
        match d {
            FaultDatum::Record { span } => {
                span.validate(meta.artifact_bytes)?;
                if span.length != 168 || record.replace(span).is_some() {
                    return Err(invalid("invalid/duplicate exception extent"));
                }
            }
            FaultDatum::Context { span } => {
                span.validate(meta.artifact_bytes)?;
                if context.replace(span).is_some() {
                    return Err(invalid("duplicate context extent"));
                }
            }
            FaultDatum::Field { observation } => {
                observation.validate(meta.artifact_bytes)?;
                if fields
                    .insert(observation.name.as_str(), observation)
                    .is_some()
                {
                    return Err(invalid("duplicate fault observation"));
                }
            }
        }
    }
    if !meta.exception_present && (!data.is_empty() || meta.context_supported) {
        return Err(invalid("observations without an exception"));
    }
    for (name, f) in &fields {
        let parent = if name.starts_with("reg:") || *name == "context_flags" {
            context
        } else {
            record
        };
        if parent.is_none_or(|p| !p.contains(&f.source)) {
            return Err(invalid("fault field outside owning extent"));
        }
        if let Some(reg) = name.strip_prefix("reg:") {
            let group = if ["rip", "rsp", "rflags"].contains(&reg) {
                1
            } else {
                2
            };
            if !meta.context_supported
                || fields
                    .get("context_flags")
                    .is_none_or(|f| f.value & group == 0)
            {
                return Err(invalid("register observation lacks validity evidence"));
            }
        }
    }
    if complete && meta.exception_present {
        for name in [
            "thread_id",
            "code",
            "flags",
            "chain",
            "exception_location",
            "number_parameters",
            "context_size",
            "context_offset",
        ] {
            if !fields.contains_key(name) {
                return Err(invalid("incomplete exception fields"));
            }
        }
        let n = fields["number_parameters"].value;
        if n > 15
            || (0..n).any(|i| !fields.contains_key(format!("parameter:{i}").as_str()))
            || fields
                .keys()
                .filter(|n| n.starts_with("parameter:"))
                .count()
                != n as usize
        {
            return Err(invalid("invalid defined exception parameters"));
        }
        let size = fields["context_size"].value;
        if size == 0 {
            if context.is_some() || meta.context_supported {
                return Err(invalid("unexpected context evidence"));
            }
        } else if context.is_none_or(|c| {
            c.length as u64 != size || c.file_offset != fields["context_offset"].value
        }) {
            return Err(invalid("context descriptor/source mismatch"));
        }
        if meta.context_supported
            && fields
                .get("context_flags")
                .is_none_or(|f| f.value & 0x00ff0000 != 0x00100000)
        {
            return Err(invalid("unsupported context architecture"));
        }
    }
    Ok(())
}

/// Owned binding. Only the capture adapter can construct this value.
pub struct BoundFaultContext {
    pub(crate) analysis: BoundInvestigation,
    pub(crate) fault: CapturedFaultContext,
}
impl BoundFaultContext {
    #[cfg(feature = "input")]
    pub(crate) fn new(
        analysis: BoundInvestigation,
        fault: CapturedFaultContext,
    ) -> Result<Self, Error> {
        fault.validate(true)?;
        if analysis.identity().snapshot_id != fault.metadata.snapshot_id
            || analysis.identity().artifact_sha256 != fault.metadata.artifact_sha256
        {
            return Err(invalid("fault context belongs to another snapshot"));
        }
        Ok(Self { analysis, fault })
    }
    pub fn identity(&self) -> &Identity {
        self.analysis.identity()
    }
}
