//! Captured Windows AMD64 unwind profile; no stack scanning or image fallback.
use super::{Error, Span, invalid, sha};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const BANKS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];
fn nonvolatile(bank: usize) -> bool {
    [3, 5, 6, 7, 12, 13, 14, 15].contains(&bank)
}
pub const FRAME_UNWIND_PROFILE: &str = "captured-windows-amd64-unwind-v1";

#[derive(Serialize, Deserialize)]
#[serde(transparent)]
struct CanonicalAddress(#[serde(with = "super::model::va")] u64);
pub(crate) mod optional_address {
    use super::*;
    pub fn serialize<S: serde::Serializer>(v: &Option<u64>, s: S) -> Result<S::Ok, S::Error> {
        v.map(CanonicalAddress).serialize(s)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Option<u64>, D::Error> {
        Ok(Option::<CanonicalAddress>::deserialize(d)?.map(|v| v.0))
    }
}
pub(crate) mod address_list {
    use super::*;
    pub fn serialize<S: serde::Serializer>(v: &[u64], s: S) -> Result<S::Ok, S::Error> {
        v.iter()
            .map(|v| CanonicalAddress(*v))
            .collect::<Vec<_>>()
            .serialize(s)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<u64>, D::Error> {
        Ok(Vec::<CanonicalAddress>::deserialize(d)?
            .into_iter()
            .map(|v| v.0)
            .collect())
    }
}
mod register_values {
    use super::*;
    pub fn serialize<S: serde::Serializer>(
        v: &BTreeMap<String, u64>,
        s: S,
    ) -> Result<S::Ok, S::Error> {
        v.iter()
            .map(|(k, v)| (k, CanonicalAddress(*v)))
            .collect::<BTreeMap<_, _>>()
            .serialize(s)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(
        d: D,
    ) -> Result<BTreeMap<String, u64>, D::Error> {
        Ok(BTreeMap::<String, CanonicalAddress>::deserialize(d)?
            .into_iter()
            .map(|(k, v)| (k, v.0))
            .collect())
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameRecoveryLimits {
    pub max_frames: usize,
    pub max_runtime_entries: usize,
    pub max_read_bytes: usize,
    pub max_stack_adjustment: u64,
}
impl Default for FrameRecoveryLimits {
    fn default() -> Self {
        Self {
            max_frames: 64,
            max_runtime_entries: 4096,
            max_read_bytes: 1024 * 1024,
            max_stack_adjustment: 16 * 1024 * 1024,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct FrameModule {
    #[serde(with = "super::model::va")]
    pub base: u64,
    pub size: u64,
    pub timestamp: u32,
    pub checksum: u32,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct FrameSeed {
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub artifact_bytes: usize,
    pub platform: String,
    pub thread_id: u32,
    pub context_stream: u32,
    pub context_offset: u64,
    pub context_hex: String,
    pub thread_record_hex: String,
    pub modules: Vec<FrameModule>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameMemoryEvidence {
    #[serde(with = "super::model::va")]
    pub address: u64,
    pub requested: usize,
    pub bytes_hex: String,
    pub spans: Vec<Span>,
}
pub(crate) fn unhex(s: &str) -> Result<Vec<u8>, Error> {
    if s.len() % 2 != 0
        || !s
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid("noncanonical evidence bytes"));
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).map_err(|e| invalid(e.to_string())))
        .collect()
}
pub(crate) fn hex(b: &[u8]) -> String {
    b.iter().map(|b| format!("{b:02x}")).collect()
}
fn u16v(b: &[u8], i: usize) -> u16 {
    u16::from_le_bytes(b[i..i + 2].try_into().expect("checked layout"))
}
fn u32v(b: &[u8], i: usize) -> u32 {
    u32::from_le_bytes(b[i..i + 4].try_into().expect("checked layout"))
}
fn u64v(b: &[u8], i: usize) -> u64 {
    u64::from_le_bytes(b[i..i + 8].try_into().expect("checked layout"))
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecoveredFrame {
    pub index: usize,
    #[serde(with = "super::model::va")]
    pub pc: u64,
    #[serde(with = "super::model::va")]
    pub sp: u64,
    #[serde(with = "optional_address")]
    pub function_begin: Option<u64>,
    #[serde(with = "optional_address")]
    pub function_end: Option<u64>,
    #[serde(with = "register_values")]
    pub registers: BTreeMap<String, u64>,
    pub register_evidence: BTreeMap<String, FrameRegisterEvidence>,
    pub method: String,
    #[serde(with = "optional_address")]
    pub return_slot: Option<u64>,
    #[serde(with = "optional_address")]
    pub return_pc: Option<u64>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrameRegisterEvidence {
    pub classification: super::Classification,
    pub source: String,
    pub context_file_offset: Option<u64>,
    #[serde(with = "optional_address")]
    pub stack_slot: Option<u64>,
    pub younger_frame: Option<usize>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedFrameChain {
    pub profile: String,
    pub chain_id: String,
    pub snapshot_id: String,
    pub artifact_sha256: String,
    pub thread_id: u32,
    pub limits: FrameRecoveryLimits,
    pub frames: Vec<RecoveredFrame>,
    pub reads: Vec<FrameMemoryEvidence>,
    pub read_bytes: usize,
    pub stop_reason: String,
    pub truncated: bool,
    seed: FrameSeed,
}
impl CapturedFrameChain {
    pub fn validate(&self) -> Result<(), Error> {
        let mut at = 0;
        let expected = recover_frames(self.seed.clone(), self.limits.clone(), &mut |va, n| {
            let r = self
                .reads
                .get(at)
                .ok_or_else(|| invalid("missing unwind read receipt"))?;
            if r.address != va || r.requested != n {
                return Err(invalid("unwind read sequence changed"));
            }
            at += 1;
            Ok(r.clone())
        })?;
        if at != self.reads.len() || expected != *self {
            return Err(invalid("frame chain recomputation mismatch"));
        }
        Ok(())
    }
}
struct Reader<'a, F> {
    read: &'a mut F,
    evidence: Vec<FrameMemoryEvidence>,
    used: usize,
    max: usize,
    artifact_bytes: usize,
}
impl<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>> Reader<'_, F> {
    fn bytes(&mut self, va: u64, n: usize) -> Result<Vec<u8>, Error> {
        self.used = self
            .used
            .checked_add(n)
            .filter(|v| *v <= self.max)
            .ok_or_else(|| invalid("unwind-read-budget"))?;
        let r = (self.read)(va, n)?;
        let b = unhex(&r.bytes_hex)?;
        if r.address != va || r.requested != n || b.len() > n {
            return Err(invalid("invalid unwind read receipt"));
        }
        let mut end = u128::from(va);
        for s in &r.spans {
            if u128::from(s.va) != end || s.length == 0 || s.contributors.is_empty() {
                return Err(invalid("invalid unwind read provenance"));
            }
            for c in &s.contributors {
                if c.file_offset
                    .checked_add(s.length as u64)
                    .is_none_or(|e| e > self.artifact_bytes as u64)
                {
                    return Err(invalid("unwind contributor outside artifact"));
                }
            }
            end += s.length as u128;
        }
        if end != u128::from(va) + b.len() as u128 {
            return Err(invalid("unwind evidence coverage"));
        }
        self.evidence.push(r);
        if b.len() != n {
            return Err(invalid("missing-or-conflicting-unwind-bytes"));
        }
        Ok(b)
    }
    fn stack(&mut self, va: u64, lo: u64, hi: u128) -> Result<u64, Error> {
        if va < lo || u128::from(va) + 8 > hi {
            return Err(invalid("return-or-save-outside-thread-stack"));
        }
        Ok(u64v(&self.bytes(va, 8)?, 0))
    }
}
#[derive(Clone)]
struct Runtime {
    begin: u64,
    end: u64,
    unwind: u64,
}
fn runtime_table<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    max: usize,
) -> Result<Vec<Runtime>, Error> {
    let module_end = u128::from(m.base) + u128::from(m.size);
    let mut read = |va: u64, n: usize| {
        if va < m.base || u128::from(va) + n as u128 > module_end {
            return Err(invalid("PE range outside captured module"));
        }
        r.bytes(va, n)
    };
    let dos = read(m.base, 64)?;
    if &dos[..2] != b"MZ" {
        return Err(invalid("missing-captured-PE-header"));
    }
    let nt = m
        .base
        .checked_add(u64::from(u32v(&dos, 60)))
        .ok_or_else(|| invalid("PE header overflow"))?;
    let coff = read(nt, 24)?;
    if &coff[..4] != b"PE\0\0" || u16v(&coff, 4) != 0x8664 || u32v(&coff, 8) != m.timestamp {
        return Err(invalid("PE module identity mismatch"));
    }
    let size = usize::from(u16v(&coff, 20));
    if !(144..=4096).contains(&size) {
        return Err(invalid("unsupported-PE-optional-header"));
    }
    let opt = read(
        nt.checked_add(24)
            .ok_or_else(|| invalid("PE VA overflow"))?,
        size,
    )?;
    if u16v(&opt, 0) != 0x20b
        || u64::from(u32v(&opt, 56)) != m.size
        || (m.checksum != 0 && u32v(&opt, 64) != m.checksum)
        || u32v(&opt, 108) < 4
    {
        return Err(invalid("PE metadata mismatch"));
    }
    let off = u32v(&opt, 136);
    let len = u32v(&opt, 140) as usize;
    if len == 0 && off == 0 {
        return Ok(Vec::new());
    }
    if off == 0 || len == 0 || len % 12 != 0 {
        return Err(invalid("invalid-runtime-table-shape"));
    }
    if len / 12 > max {
        return Err(invalid("runtime-table-budget"));
    }
    let data = read(
        m.base
            .checked_add(u64::from(off))
            .ok_or_else(|| invalid("runtime VA overflow"))?,
        len,
    )?;
    let mut rows = Vec::new();
    let mut previous = 0;
    for b in data.chunks_exact(12) {
        let begin = u32v(b, 0);
        let end = u32v(b, 4);
        let unwind = u32v(b, 8);
        if begin >= end
            || begin < previous
            || u64::from(end) > m.size
            || u64::from(unwind) + 4 > m.size
            || unwind == 0
        {
            return Err(invalid("invalid-runtime-function-table"));
        }
        previous = end;
        rows.push(Runtime {
            begin: m.base + u64::from(begin),
            end: m.base + u64::from(end),
            unwind: m.base + u64::from(unwind),
        });
    }
    Ok(rows)
}
fn potential_epilogue(b: &[u8]) -> bool {
    let b = if b.first().is_some_and(|b| (0x40..=0x4f).contains(b)) {
        &b[1..]
    } else {
        b
    };
    b.first()
        .is_some_and(|b| (0x58..=0x5f).contains(b) || [0xc2, 0xc3, 0xe9, 0xeb].contains(b))
        || b.starts_with(&[0xf3, 0xc3])
        || b.starts_with(&[0x83, 0xc4])
        || b.starts_with(&[0x81, 0xc4])
        || (b.len() > 1 && b[0] == 0x8d && (b[1] >> 3) & 7 == 4)
        || (b.len() > 1 && b[0] == 0xff && (b[1] >> 3) & 7 == 4)
}
pub(crate) fn recover_frames<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    seed: FrameSeed,
    limits: FrameRecoveryLimits,
    read: &mut F,
) -> Result<CapturedFrameChain, Error> {
    if !super::validate::digest(&seed.artifact_sha256)
        || seed.snapshot_id != format!("minidump-captured-amd64-v1:{}", seed.artifact_sha256)
        || ![3, 6].contains(&seed.context_stream)
        || seed.modules.len() > 1024
    {
        return Err(invalid("invalid frame seed identity"));
    }
    if seed.context_hex.len() != 1232 * 2
        || seed.thread_record_hex.len() != 48 * 2
        || seed
            .context_offset
            .checked_add(1232)
            .is_none_or(|v| v > seed.artifact_bytes as u64)
    {
        return Err(invalid("invalid frame seed extent"));
    }
    if seed.modules.iter().any(|m| {
        m.size > u64::from(u32::MAX)
            || u128::from(m.base) + u128::from(m.size) > u128::from(u64::MAX) + 1
    }) {
        return Err(invalid("invalid frame module range"));
    }
    let context = unhex(&seed.context_hex)?;
    let thread = unhex(&seed.thread_record_hex)?;
    if u32v(&thread, 0) != seed.thread_id {
        return Err(invalid("frame seed thread mismatch"));
    }
    let flags = u32v(&context, 48);
    let mut registers: BTreeMap<String, u64> = BTreeMap::new();
    let mut register_evidence = BTreeMap::new();
    let mut reason = "frame-budget".to_string();
    let mut truncated = false;
    let mut frames = Vec::new();
    let mut r = Reader {
        read,
        evidence: Vec::new(),
        used: 0,
        max: limits.max_read_bytes,
        artifact_bytes: seed.artifact_bytes,
    };
    if seed.platform != "windows-amd64" {
        reason = "unsupported-frame-platform".into();
    } else if flags & 0x00ff0000 != 0x00100000 || flags & 1 == 0 {
        reason = "missing-or-unsupported-frame-context".into();
    } else {
        registers.insert("rip".into(), u64v(&context, 248));
        registers.insert("rsp".into(), u64v(&context, 152));
        if flags & 2 != 0 {
            for (i, name) in BANKS.iter().enumerate() {
                if i != 4 {
                    registers.insert((*name).into(), u64v(&context, 120 + i * 8));
                }
            }
        }
        for name in registers.keys() {
            let offset = if name == "rip" {
                248
            } else if name == "rsp" {
                152
            } else {
                120 + BANKS.iter().position(|b| *b == name).expect("GPR") * 8
            };
            register_evidence.insert(
                name.clone(),
                FrameRegisterEvidence {
                    classification: super::Classification::Observed,
                    source: "captured-context".into(),
                    context_file_offset: Some(seed.context_offset + offset as u64),
                    stack_slot: None,
                    younger_frame: None,
                },
            );
        }
        let lo = u64v(&thread, 24);
        let hi = u128::from(lo) + u128::from(u32v(&thread, 32));
        let mut cache: BTreeMap<u64, Vec<Runtime>> = BTreeMap::new();
        let mut seen = BTreeSet::new();
        for index in 0..limits.max_frames {
            let pc = registers["rip"];
            let original_sp = registers["rsp"];
            if pc == 0 && index > 0 {
                reason = "zero-return-boundary".into();
                break;
            }
            if !seen.insert((pc, original_sp)) {
                reason = "cyclic-frame-context".into();
                break;
            }
            let lookup = if index == 0 { pc } else { pc - 1 };
            let modules: Vec<_> = seed
                .modules
                .iter()
                .filter(|m| {
                    lookup >= m.base && u128::from(lookup) < u128::from(m.base) + u128::from(m.size)
                })
                .collect();
            let unresolved = || RecoveredFrame {
                index,
                pc,
                sp: original_sp,
                function_begin: None,
                function_end: None,
                registers: registers.clone(),
                register_evidence: register_evidence.clone(),
                method: "unresolved-frame".into(),
                return_slot: None,
                return_pc: None,
            };
            if modules.len() != 1 {
                frames.push(unresolved());
                reason = "missing-or-ambiguous-frame-module".into();
                break;
            }
            let m = modules[0];
            if let std::collections::btree_map::Entry::Vacant(entry) = cache.entry(m.base) {
                match runtime_table(&mut r, m, limits.max_runtime_entries) {
                    Ok(rows) => {
                        entry.insert(rows);
                    }
                    Err(e) => {
                        frames.push(unresolved());
                        reason = e.to_string();
                        break;
                    }
                }
            }
            let runtime = cache[&m.base]
                .iter()
                .find(|row| lookup >= row.begin && lookup < row.end)
                .cloned();
            let mut frame = RecoveredFrame {
                index,
                pc,
                sp: original_sp,
                function_begin: runtime.as_ref().map(|f| f.begin),
                function_end: runtime.as_ref().map(|f| f.end),
                registers: registers.clone(),
                register_evidence: register_evidence.clone(),
                method: if runtime.is_some() {
                    "runtime-v1"
                } else {
                    "leaf-under-windows-abi"
                }
                .into(),
                return_slot: None,
                return_pc: None,
            };
            let step = (|| -> Result<(), Error> {
                let mut restored: BTreeMap<String, u64> = BTreeMap::new();
                if index == 0 {
                    // Body-only profile. A short capture is a gap, never zero padding.
                    if potential_epilogue(&r.bytes(pc, 15)?) {
                        return Err(invalid("unsupported-epilogue-or-tail-transfer"));
                    }
                }
                if let Some(f) = runtime {
                    let h = r.bytes(f.unwind, 4)?;
                    if h[0] & 7 != 1 || h[0] >> 3 != 0 {
                        return Err(invalid("unsupported-unwind-version-or-flags"));
                    }
                    if lookup - f.begin <= u64::from(h[1]) {
                        return Err(invalid("unsupported-prologue-context"));
                    }
                    let count = usize::from(h[2]);
                    let bank = usize::from(h[3] & 15);
                    let offset = u64::from(h[3] >> 4) * 16;
                    if (bank == 0 && offset != 0) || (bank != 0 && !nonvolatile(bank)) {
                        return Err(invalid("invalid-unwind-frame-register"));
                    }
                    let base = if bank == 0 {
                        original_sp
                    } else {
                        registers
                            .get(BANKS[bank])
                            .copied()
                            .ok_or_else(|| invalid("missing-unwind-frame-register"))?
                            .checked_sub(offset)
                            .ok_or_else(|| invalid("frame offset underflow"))?
                    };
                    let codes = r.bytes(f.unwind + 4, count * 2)?;
                    let mut at = 0;
                    let mut previous = 256u16;
                    let mut set_frame = false;
                    while at < count {
                        let pos = at * 2;
                        let code_offset = codes[pos];
                        let op = codes[pos + 1] & 15;
                        let info = usize::from(codes[pos + 1] >> 4);
                        if u16::from(code_offset) > previous || code_offset > h[1] {
                            return Err(invalid("invalid-unwind-code-order"));
                        }
                        previous = u16::from(code_offset);
                        let slots = match op {
                            0 | 2 | 3 => 1,
                            1 if info == 0 => 2,
                            1 if info == 1 => 3,
                            4 => 2,
                            5 => 3,
                            _ => return Err(invalid("unsupported-unwind-operation")),
                        };
                        if at + slots > count {
                            return Err(invalid("truncated-unwind-operation"));
                        }
                        let sp = registers["rsp"];
                        match op {
                            0 => {
                                if !nonvolatile(info) {
                                    return Err(invalid("invalid-saved-register"));
                                }
                                let v = r.stack(sp, lo, hi)?;
                                registers.insert(BANKS[info].into(), v);
                                restored.insert(BANKS[info].into(), sp);
                                registers.insert(
                                    "rsp".into(),
                                    sp.checked_add(8).ok_or_else(|| invalid("stack overflow"))?,
                                );
                            }
                            1 | 2 => {
                                let size = if op == 2 {
                                    info as u64 * 8 + 8
                                } else if info == 0 {
                                    u64::from(u16v(&codes, pos + 2)) * 8
                                } else {
                                    u64::from(u32v(&codes, pos + 2))
                                };
                                if size == 0 || size % 8 != 0 {
                                    return Err(invalid("invalid-unwind-stack-allocation"));
                                }
                                if size > limits.max_stack_adjustment {
                                    return Err(invalid("unwind-stack-adjustment-budget"));
                                }
                                registers.insert(
                                    "rsp".into(),
                                    sp.checked_add(size)
                                        .ok_or_else(|| invalid("stack overflow"))?,
                                );
                            }
                            3 => {
                                if bank == 0 || info != 0 || set_frame {
                                    return Err(invalid("invalid-set-frame-operation"));
                                }
                                set_frame = true;
                                registers.insert("rsp".into(), base);
                            }
                            4 | 5 => {
                                if !nonvolatile(info) {
                                    return Err(invalid("invalid-saved-register"));
                                }
                                let offset = if op == 4 {
                                    u64::from(u16v(&codes, pos + 2)) * 8
                                } else {
                                    u64::from(u32v(&codes, pos + 2))
                                };
                                let addr = base
                                    .checked_add(offset)
                                    .ok_or_else(|| invalid("saved register overflow"))?;
                                registers.insert(BANKS[info].into(), r.stack(addr, lo, hi)?);
                                restored.insert(BANKS[info].into(), addr);
                            }
                            _ => unreachable!(),
                        }
                        at += slots;
                    }
                    if bank != 0 && !set_frame {
                        return Err(invalid("missing-set-frame-operation"));
                    }
                }
                let slot = registers["rsp"];
                let ret = r.stack(slot, lo, hi)?;
                let next = slot
                    .checked_add(8)
                    .ok_or_else(|| invalid("stack overflow"))?;
                if next <= original_sp {
                    return Err(invalid("nonprogressing-stack-unwind"));
                }
                if next - original_sp > limits.max_stack_adjustment {
                    return Err(invalid("unwind-stack-adjustment-budget"));
                }
                frame.return_slot = Some(slot);
                frame.return_pc = Some(ret);
                registers.retain(|name, _| {
                    name == "rsp"
                        || BANKS
                            .iter()
                            .enumerate()
                            .any(|(i, b)| nonvolatile(i) && b == name)
                });
                registers.insert("rip".into(), ret);
                registers.insert("rsp".into(), next);
                register_evidence = registers
                    .keys()
                    .map(|name| {
                        let (source, stack_slot) = if name == "rip" {
                            ("return-slot", Some(slot))
                        } else if name == "rsp" {
                            ("unwind-rsp", Some(slot))
                        } else if let Some(slot) = restored.get(name) {
                            ("saved-nonvolatile-slot", Some(*slot))
                        } else {
                            ("preserved-nonvolatile", None)
                        };
                        (
                            name.clone(),
                            FrameRegisterEvidence {
                                classification: super::Classification::DerivedUnderPremises,
                                source: source.into(),
                                context_file_offset: None,
                                stack_slot,
                                younger_frame: Some(index),
                            },
                        )
                    })
                    .collect();
                Ok(())
            })();
            frames.push(frame);
            if let Err(e) = step {
                reason = e.to_string();
                break;
            }
            if registers["rip"] == 0 {
                reason = "zero-return-boundary".into();
                break;
            }
            if index + 1 == limits.max_frames {
                truncated = true;
            }
        }
        if limits.max_frames == 0 {
            truncated = true;
        }
    }
    if reason.contains("budget") {
        truncated = true;
    }
    let mut result = CapturedFrameChain {
        profile: FRAME_UNWIND_PROFILE.into(),
        chain_id: String::new(),
        snapshot_id: seed.snapshot_id.clone(),
        artifact_sha256: seed.artifact_sha256.clone(),
        thread_id: seed.thread_id,
        limits,
        frames,
        reads: r.evidence,
        read_bytes: r.used,
        stop_reason: reason,
        truncated,
        seed,
    };
    result.chain_id = sha(&serde_json::to_vec(&result)?);
    Ok(result)
}
