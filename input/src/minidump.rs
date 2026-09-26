use crate::address_space::{Capture, index};
use crate::*;
use ::minidump::system_info::Cpu;
use ::minidump::{
    Minidump, MinidumpException, MinidumpModuleList, MinidumpRawContext, MinidumpSystemInfo,
    MinidumpThreadList,
};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

fn range(bytes: &[u8], offset: u64, len: u64) -> Result<&[u8], InputError> {
    let end = offset
        .checked_add(len)
        .ok_or_else(|| malformed("file range overflow"))?;
    let (a, b) = (
        usize::try_from(offset).map_err(|_| malformed("file offset"))?,
        usize::try_from(end).map_err(|_| malformed("file end"))?,
    );
    bytes
        .get(a..b)
        .ok_or_else(|| malformed("file range outside artifact"))
}
fn u32_at(b: &[u8], o: usize) -> Result<u32, InputError> {
    Ok(u32::from_le_bytes(
        range(b, o as u64, 4)?.try_into().expect("length"),
    ))
}
fn u64_at(b: &[u8], o: usize) -> Result<u64, InputError> {
    Ok(u64::from_le_bytes(
        range(b, o as u64, 8)?.try_into().expect("length"),
    ))
}
fn location(b: &[u8], all: &[u8], o: usize) -> Result<(u64, u64), InputError> {
    let size = u32_at(b, o)? as u64;
    let off = u32_at(b, o + 4)? as u64;
    if size > 0 {
        range(all, off, size)?;
    }
    Ok((off, size))
}
fn list(b: &[u8], stride: usize, limits: &OpenLimits) -> Result<(usize, usize), InputError> {
    let n = u32_at(b, 0)? as usize;
    if n > limits.max_records {
        return Err(InputError::Limit("list records"));
    }
    let array = n
        .checked_mul(stride)
        .ok_or_else(|| malformed("list size overflow"))?;
    let start = b
        .len()
        .checked_sub(array)
        .ok_or_else(|| malformed("truncated list"))?;
    if start != 4 && start != 8 {
        return Err(malformed("invalid list padding/size"));
    }
    Ok((n, start))
}
fn utf16(all: &[u8], off: u32) -> Result<u64, InputError> {
    let len = u32_at(all, off as usize)? as u64;
    if len > 65536 {
        return Err(InputError::Limit("metadata string"));
    }
    if len % 2 != 0 {
        return Err(malformed("odd UTF-16 length"));
    }
    let bytes = range(all, u64::from(off) + 4, len)?;
    String::from_utf16(
        &bytes
            .chunks_exact(2)
            .map(|b| u16::from_le_bytes([b[0], b[1]]))
            .collect::<Vec<_>>(),
    )
    .map_err(|_| malformed("invalid UTF-16"))?;
    Ok(len)
}
fn capture(
    out: &mut Vec<Capture>,
    all: &[u8],
    start: u64,
    offset: u64,
    size: u64,
    source: (u32, usize),
    limits: &OpenLimits,
) -> Result<(), InputError> {
    if size == 0 {
        return Ok(());
    }
    range(all, offset, size)?;
    let end = u128::from(start) + u128::from(size);
    if end > u128::from(u64::MAX) + 1 {
        return Err(malformed("virtual range overflow"));
    }
    if out.len() >= limits.max_capture_ranges {
        return Err(InputError::Limit("capture ranges"));
    }
    out.push(Capture {
        start,
        end,
        offset: offset as usize,
        source: CaptureSource {
            stream: source.0,
            entry: source.1,
            file_offset: offset,
        },
    });
    Ok(())
}
fn registers(
    context: Option<std::borrow::Cow<'_, ::minidump::MinidumpContext>>,
    stream: u32,
    entry: usize,
    gaps: &mut Vec<MetadataGap>,
) -> BTreeMap<String, u64> {
    let Some(c) = context else {
        gaps.push(MetadataGap {
            stream,
            entry: Some(entry),
            reason: "missing or unsupported context".into(),
        });
        return BTreeMap::new();
    };
    let MinidumpRawContext::Amd64(raw) = &c.raw else {
        gaps.push(MetadataGap {
            stream,
            entry: Some(entry),
            reason: "non-AMD64 context".into(),
        });
        return BTreeMap::new();
    };
    let mut result = BTreeMap::new();
    // minidump 0.26.1's from_raw marks all registers valid. Honor the actual
    // AMD64 CONTEXT_CONTROL/INTEGER group flags instead of importing that claim.
    if raw.context_flags & 1 != 0 {
        result.extend([
            ("rip".into(), raw.rip),
            ("rsp".into(), raw.rsp),
            ("rflags".into(), u64::from(raw.eflags)),
        ]);
    }
    if raw.context_flags & 2 != 0 {
        for name in [
            "rax", "rcx", "rdx", "rbx", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12",
            "r13", "r14", "r15",
        ] {
            if let Some(value) = c.get_register(name) {
                result.insert(name.into(), value);
            }
        }
    }
    if raw.context_flags & 0x40 != 0 {
        gaps.push(MetadataGap {
            stream,
            entry: Some(entry),
            reason: "extended register state not interpreted".into(),
        });
    }
    result
}

pub(crate) fn parse(bytes: Vec<u8>, limits: OpenLimits) -> Result<FileSnapshot, InputError> {
    if bytes.len() > limits.max_file_bytes {
        return Err(InputError::Limit("artifact bytes"));
    }
    if range(&bytes, 0, 4)? != b"MDMP" {
        return Err(InputError::Unsupported(
            "expected little-endian minidump".into(),
        ));
    }
    range(&bytes, 0, 32)?;
    if u32_at(&bytes, 4)? & 0xffff != 0xa793 {
        return Err(InputError::Unsupported("minidump version".into()));
    }
    let count = u32_at(&bytes, 8)? as usize;
    let directory = u32_at(&bytes, 12)? as u64;
    if count > limits.max_streams {
        return Err(InputError::Limit("directory streams"));
    }
    let entries = range(&bytes, directory, (count as u64) * 12)?;
    let mut streams = Vec::new();
    let mut selected = BTreeMap::new();
    for i in 0..count {
        let row = &entries[i * 12..i * 12 + 12];
        let kind = u32_at(row, 0)?;
        let (off, len) = location(row, &bytes, 4)?;
        let supported = matches!(kind, 3 | 4 | 5 | 6 | 7 | 9 | 16);
        if supported && selected.insert(kind, (off, len)).is_some() {
            return Err(malformed("duplicate supported stream"));
        }
        streams.push(StreamInfo {
            kind,
            file_offset: off,
            size: len,
            supported,
        });
    }
    let mut metadata_budget = limits.max_metadata_bytes as u64;
    let mut charge = |n: u64| -> Result<(), InputError> {
        metadata_budget = metadata_budget
            .checked_sub(n)
            .ok_or(InputError::Limit("metadata payload bytes"))?;
        Ok(())
    };
    let mut captures = Vec::new();
    let mut infos = Vec::new();
    // Bound counts and nested extents before invoking permissive parser APIs.
    for (&kind, &(offset, len)) in &selected {
        let b = range(&bytes, offset, len)?;
        match kind {
            3 => {
                let (n, start) = list(b, 48, &limits)?;
                let mut ids = BTreeSet::new();
                for i in 0..n {
                    let t = &b[start + i * 48..start + (i + 1) * 48];
                    if !ids.insert(u32_at(t, 0)?) {
                        return Err(malformed("duplicate thread id"));
                    }
                    let (off, size) = location(t, &bytes, 32)?;
                    capture(
                        &mut captures,
                        &bytes,
                        u64_at(t, 24)?,
                        off,
                        size,
                        (kind, i),
                        &limits,
                    )?;
                    charge(location(t, &bytes, 40)?.1)?;
                }
            }
            4 => {
                let (n, start) = list(b, 108, &limits)?;
                for i in 0..n {
                    let m = &b[start + i * 108..start + (i + 1) * 108];
                    if u128::from(u64_at(m, 0)?) + u128::from(u32_at(m, 8)?)
                        > u128::from(u64::MAX) + 1
                    {
                        return Err(malformed("module range overflow"));
                    }
                    charge(utf16(&bytes, u32_at(m, 20)?)?)?;
                    charge(location(m, &bytes, 76)?.1)?;
                    charge(location(m, &bytes, 84)?.1)?;
                }
            }
            5 => {
                let (n, start) = list(b, 16, &limits)?;
                for i in 0..n {
                    let m = &b[start + i * 16..start + (i + 1) * 16];
                    let (off, size) = location(m, &bytes, 8)?;
                    capture(
                        &mut captures,
                        &bytes,
                        u64_at(m, 0)?,
                        off,
                        size,
                        (kind, i),
                        &limits,
                    )?;
                }
            }
            9 => {
                let n = u64_at(b, 0)?;
                let mut off = u64_at(b, 8)?;
                if n > limits.max_records as u64 {
                    return Err(InputError::Limit("memory64 records"));
                }
                if n.checked_mul(16).and_then(|n| n.checked_add(16)) != Some(b.len() as u64) {
                    return Err(malformed("memory64 table size"));
                }
                for i in 0..n as usize {
                    let start = u64_at(b, 16 + i * 16)?;
                    let size = u64_at(b, 24 + i * 16)?;
                    capture(&mut captures, &bytes, start, off, size, (kind, i), &limits)?;
                    off = off
                        .checked_add(size)
                        .ok_or_else(|| malformed("memory64 payload overflow"))?;
                }
            }
            6 => {
                if b.len() != 168 || u32_at(b, 32)? > 15 {
                    return Err(malformed("exception stream shape"));
                }
                charge(location(b, &bytes, 160)?.1)?;
            }
            7 => {
                range(b, 0, 56)?;
                let csd = u32_at(b, 24)?;
                if csd != 0 {
                    charge(utf16(&bytes, csd)?)?;
                }
            }
            16 => {
                let header = u32_at(b, 0)? as u64;
                let stride = u32_at(b, 4)? as u64;
                let n = u64_at(b, 8)?;
                if n > limits.max_records as u64 {
                    return Err(InputError::Limit("memory-info records"));
                }
                if header < 16
                    || stride < 48
                    || header.checked_add(
                        n.checked_mul(stride)
                            .ok_or_else(|| malformed("memory-info count"))?,
                    ) != Some(b.len() as u64)
                {
                    return Err(malformed("memory-info shape"));
                }
                for i in 0..n {
                    let m = range(b, header + i * stride, 48)?;
                    let base = u64_at(m, 0)?;
                    let size = u64_at(m, 24)?;
                    if u128::from(base) + u128::from(size) > u128::from(u64::MAX) + 1 {
                        return Err(malformed("memory-info VA overflow"));
                    }
                    infos.push(MemoryInfo {
                        base,
                        size,
                        protection: u32_at(m, 36)?,
                        state: u32_at(m, 32)?,
                        kind: u32_at(m, 40)?,
                    });
                }
            }
            _ => unreachable!(),
        }
    }
    let dump = Minidump::read(bytes.as_slice()).map_err(|e| malformed(e.to_string()))?;
    let system = dump
        .get_stream::<MinidumpSystemInfo>()
        .map_err(|e| malformed(format!("system info: {e}")))?;
    if system.cpu != Cpu::X86_64 {
        return Err(InputError::Unsupported("requires AMD64 system info".into()));
    }
    // Use the on-disk Win32 NT (2) and Breakpad Linux (0x8201) IDs directly.
    let platform = match system.raw.platform_id {
        2 => Platform::Windows,
        0x8201 => Platform::Linux,
        _ => {
            return Err(InputError::Unsupported(
                "requires Windows or Linux platform".into(),
            ));
        }
    };
    let mut gaps: Vec<_> = streams
        .iter()
        .filter(|s| !s.supported)
        .map(|s| MetadataGap {
            stream: s.kind,
            entry: None,
            reason: "stream retained in inventory but not interpreted".into(),
        })
        .collect();
    let mut modules = Vec::new();
    if selected.contains_key(&4) {
        let list = dump
            .get_stream::<MinidumpModuleList>()
            .map_err(|e| malformed(e.to_string()))?;
        for m in list.iter() {
            let cv = &m.raw.cv_record;
            let codeview = if cv.data_size == 0 {
                Vec::new()
            } else {
                range(&bytes, u64::from(cv.rva), u64::from(cv.data_size))?.to_vec()
            };
            modules.push(ModuleInfo {
                name: m.name.clone(),
                base: m.raw.base_of_image,
                size: u64::from(m.raw.size_of_image),
                timestamp: m.raw.time_date_stamp,
                checksum: m.raw.checksum,
                codeview,
            });
        }
    }
    let mut threads = Vec::new();
    if selected.contains_key(&3) {
        let list = dump
            .get_stream::<MinidumpThreadList>()
            .map_err(|e| malformed(e.to_string()))?;
        for (i, t) in list.threads.iter().enumerate() {
            threads.push(ThreadInfo {
                id: t.raw.thread_id,
                registers: registers(t.context(&system, None), 3, i, &mut gaps),
            });
        }
    }
    let exception = if selected.contains_key(&6) {
        let ex = dump
            .get_stream::<MinidumpException>()
            .map_err(|e| malformed(e.to_string()))?;
        Some(ExceptionInfo {
            thread_id: ex.thread_id,
            code: ex.raw.exception_record.exception_code,
            reported_address: ex.raw.exception_record.exception_address,
            registers: registers(ex.context(&system, None), 6, 0, &mut gaps),
        })
    } else {
        None
    };
    let artifact_sha256 = format!("{:x}", Sha256::digest(&bytes));
    let snapshot_id = format!("minidump-captured-amd64-v1:{artifact_sha256}");
    let tree = index(&mut captures, limits.max_overlap)?;
    let metadata = Arc::new(SnapshotMetadata {
        snapshot_id,
        artifact_sha256,
        platform,
        artifact_bytes: bytes.len(),
        streams,
        modules,
        threads,
        exception,
        memory_info: infos,
        gaps,
    });
    Ok(FileSnapshot {
        bytes: bytes.into(),
        metadata,
        captures,
        tree,
        limits,
    })
}
