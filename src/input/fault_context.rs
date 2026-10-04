//! Reader-owned fault observations; the legacy public metadata/report stays intact.
use super::{ExceptionInfo, InputError, Platform, SnapshotMetadata, malformed};
use crate::investigation::{
    CapturedFaultContext, FaultDatum, FaultMetadata, FaultObservation, FaultSpan,
};
use std::sync::Arc;

#[derive(Clone, Debug)]
pub(crate) struct FaultCapture {
    pub metadata: Arc<SnapshotMetadata>,
    pub evidence: CapturedFaultContext,
}
fn span(bytes: &[u8], offset: usize, length: usize) -> Result<FaultSpan, InputError> {
    let data = bytes
        .get(
            offset
                ..offset
                    .checked_add(length)
                    .ok_or_else(|| malformed("fault extent overflow"))?,
        )
        .ok_or_else(|| malformed("fault extent outside artifact"))?;
    Ok(FaultSpan {
        file_offset: offset as u64,
        length,
        sha256: crate::reports::sha256(data),
    })
}
fn field(bytes: &[u8], name: &str, offset: usize, width: usize) -> Result<FaultDatum, InputError> {
    let source = span(bytes, offset, width)?;
    let raw = &bytes[offset..offset + width];
    let value = raw
        .iter()
        .enumerate()
        .fold(0u64, |n, (i, b)| n | (u64::from(*b) << (8 * i)));
    Ok(FaultDatum::Field {
        observation: FaultObservation {
            name: name.into(),
            value,
            source,
            bytes_hex: raw.iter().map(|b| format!("{b:02x}")).collect(),
        },
    })
}
const REGISTERS: [(&str, usize, usize); 18] = [
    ("rax", 120, 8),
    ("rcx", 128, 8),
    ("rdx", 136, 8),
    ("rbx", 144, 8),
    ("rsp", 152, 8),
    ("rbp", 160, 8),
    ("rsi", 168, 8),
    ("rdi", 176, 8),
    ("r8", 184, 8),
    ("r9", 192, 8),
    ("r10", 200, 8),
    ("r11", 208, 8),
    ("r12", 216, 8),
    ("r13", 224, 8),
    ("r14", 232, 8),
    ("r15", 240, 8),
    ("rip", 248, 8),
    ("rflags", 68, 4),
];
pub(crate) fn capture(
    bytes: &[u8],
    metadata: Arc<SnapshotMetadata>,
    exception_extent: Option<(u64, u64)>,
) -> Result<Arc<FaultCapture>, InputError> {
    let mut evidence = CapturedFaultContext {
        metadata: FaultMetadata {
            snapshot_id: metadata.snapshot_id.clone(),
            artifact_sha256: metadata.artifact_sha256.clone(),
            artifact_bytes: bytes.len() as u64,
            platform: match metadata.platform {
                Platform::Windows => "windows-amd64",
                Platform::Linux => "linux-amd64",
            }
            .into(),
            exception_present: exception_extent.is_some(),
            context_supported: false,
            gaps: Vec::new(),
        },
        data: Vec::new(),
    };
    if let Some((offset, length)) = exception_extent {
        let offset = usize::try_from(offset).map_err(|_| malformed("exception offset"))?;
        evidence.data.push(FaultDatum::Record {
            span: span(bytes, offset, length as usize)?,
        });
        for (name, at, width) in [
            ("thread_id", 0, 4),
            ("code", 8, 4),
            ("flags", 12, 4),
            ("chain", 16, 8),
            ("exception_location", 24, 8),
            ("number_parameters", 32, 4),
            ("context_size", 160, 4),
            ("context_offset", 164, 4),
        ] {
            evidence.data.push(field(bytes, name, offset + at, width)?);
        }
        let read32 = |at: usize| {
            u32::from_le_bytes(
                bytes[offset + at..offset + at + 4]
                    .try_into()
                    .expect("validated stream"),
            )
        };
        for i in 0..read32(32) as usize {
            evidence.data.push(field(
                bytes,
                &format!("parameter:{i}"),
                offset + 40 + 8 * i,
                8,
            )?);
        }
        let size = read32(160) as usize;
        let context_offset = read32(164) as usize;
        if size > 0 {
            evidence.data.insert(
                1,
                FaultDatum::Context {
                    span: span(bytes, context_offset, size)?,
                },
            );
            if size >= 52 {
                let flags = u32::from_le_bytes(
                    bytes[context_offset + 48..context_offset + 52]
                        .try_into()
                        .expect("checked context"),
                );
                evidence
                    .data
                    .push(field(bytes, "context_flags", context_offset + 48, 4)?);
                let decoded = metadata.exception.as_ref().map(|e| &e.registers);
                // Native reader validates the full AMD64 context before exposing registers.
                evidence.metadata.context_supported = size >= 1232
                    && flags & 0x00ff0000 == 0x00100000
                    && metadata
                        .exception
                        .as_ref()
                        .is_some_and(|e| !e.registers.is_empty() || flags & 3 == 0);
                if evidence.metadata.context_supported {
                    for (name, at, width) in REGISTERS {
                        if let Some(value) = decoded.and_then(|r| r.get(name)) {
                            let observation =
                                field(bytes, &format!("reg:{name}"), context_offset + at, width)?;
                            if !matches!(&observation,FaultDatum::Field { observation } if observation.value == *value)
                            {
                                return Err(malformed(
                                    "register normalization/source disagreement",
                                ));
                            }
                            evidence.data.push(observation);
                        }
                    }
                }
            }
        }
        if !evidence.metadata.context_supported {
            evidence
                .metadata
                .gaps
                .push("missing-or-unsupported-exception-context".into());
        }
        if let Some(ExceptionInfo {
            thread_id,
            code,
            reported_address,
            ..
        }) = &metadata.exception
        {
            let values = crate::investigation::fault_values(&evidence.data);
            if values["thread_id"] != u64::from(*thread_id)
                || values["code"] != u64::from(*code)
                || values["exception_location"] != *reported_address
            {
                return Err(malformed("exception normalization/source disagreement"));
            }
        }
    } else {
        evidence
            .metadata
            .gaps
            .push("missing-exception-stream".into());
    }
    evidence
        .validate(true)
        .map_err(|e| malformed(e.to_string()))?;
    Ok(Arc::new(FaultCapture { metadata, evidence }))
}
