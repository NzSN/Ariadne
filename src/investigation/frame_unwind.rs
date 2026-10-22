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
const LEGACY_FRAME_UNWIND_PROFILE: &str = "captured-windows-amd64-unwind-v1";
const XMM_FRAME_UNWIND_PROFILE: &str = "captured-windows-amd64-unwind-v2";
const CONVENTIONAL_FRAME_UNWIND_PROFILE: &str = "captured-windows-amd64-unwind-v3";
pub const FRAME_UNWIND_PROFILE: &str = "captured-windows-amd64-unwind-v4";

#[derive(Clone, Copy, PartialEq, Eq)]
enum UnwindProfile {
    V1,
    V2,
    V3,
    V4,
}
impl UnwindProfile {
    fn parse(profile: &str) -> Result<Self, Error> {
        match profile {
            LEGACY_FRAME_UNWIND_PROFILE => Ok(Self::V1),
            XMM_FRAME_UNWIND_PROFILE => Ok(Self::V2),
            CONVENTIONAL_FRAME_UNWIND_PROFILE => Ok(Self::V3),
            FRAME_UNWIND_PROFILE => Ok(Self::V4),
            _ => Err(invalid("unsupported-frame-unwind-profile")),
        }
    }
    fn name(self) -> &'static str {
        match self {
            Self::V1 => LEGACY_FRAME_UNWIND_PROFILE,
            Self::V2 => XMM_FRAME_UNWIND_PROFILE,
            Self::V3 => CONVENTIONAL_FRAME_UNWIND_PROFILE,
            Self::V4 => FRAME_UNWIND_PROFILE,
        }
    }
    fn extended(self) -> bool {
        matches!(self, Self::V3 | Self::V4)
    }
}

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
#[cfg(feature = "input")]
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
    /// How this frame restores the next older context. Omitted in legacy profiles.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transition: Option<FrameTransition>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FrameTransition {
    NormalReturn,
    MachineFrame,
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
    #[cfg(feature = "bap")]
    pub(crate) fn artifact_bytes(&self) -> usize {
        self.seed.artifact_bytes
    }
    pub fn validate(&self) -> Result<(), Error> {
        let mut at = 0;
        let expected = recover_frames(
            self.seed.clone(),
            self.limits.clone(),
            &self.profile,
            &mut |va, n| {
                let r = self
                    .reads
                    .get(at)
                    .ok_or_else(|| invalid("missing unwind read receipt"))?;
                if r.address != va || r.requested != n {
                    return Err(invalid("unwind read sequence changed"));
                }
                at += 1;
                Ok(r.clone())
            },
        )?;
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
    fn stack_bytes(&mut self, va: u64, n: usize, lo: u64, hi: u128) -> Result<Vec<u8>, Error> {
        if va < lo || u128::from(va) + n as u128 > hi {
            return Err(invalid("return-or-save-outside-thread-stack"));
        }
        self.bytes(va, n)
    }
    fn stack(&mut self, va: u64, lo: u64, hi: u128) -> Result<u64, Error> {
        Ok(u64v(&self.stack_bytes(va, 8, lo, hi)?, 0))
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
            begin: m
                .base
                .checked_add(u64::from(begin))
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
            end: m
                .base
                .checked_add(u64::from(end))
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
            unwind: m
                .base
                .checked_add(u64::from(unwind))
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
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

// Ariadne profile v3 extends the captured adapter. It is independent of the
// Windows UNWIND_INFO version (the version-3/APX payload is not this format).
const MAX_UNWIND_CHAIN_DEPTH: usize = 32;
const MAX_EPILOGUE_BYTES: usize = 256;

enum UnwindOperationKind {
    Push(usize),
    Allocate(u64),
    SetFrame,
    Save(usize, u64),
    SaveXmm(u64),
    MachineFrame(bool),
}
struct UnwindOperation {
    offset: u8,
    opcode: u8,
    kind: UnwindOperationKind,
}
struct EpilogueDescriptor {
    start: u64,
    size: u8,
}
struct UnwindRecipe {
    version: u8,
    prologue: u8,
    bank: usize,
    frame_offset: u64,
    operations: Vec<UnwindOperation>,
    chained: Option<Runtime>,
    epilogues: Vec<EpilogueDescriptor>,
}
fn module_bytes<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    address: u64,
    length: usize,
) -> Result<Vec<u8>, Error> {
    if address < m.base
        || u128::from(address) + length as u128 > u128::from(m.base) + u128::from(m.size)
    {
        return Err(invalid("unwind-range-outside-captured-module"));
    }
    r.bytes(address, length)
}
fn read_recipe<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    runtime: &Runtime,
    profile: UnwindProfile,
) -> Result<UnwindRecipe, Error> {
    if runtime.unwind % 4 != 0 {
        return Err(invalid("unaligned-unwind-info"));
    }
    let h = module_bytes(r, m, runtime.unwind, 4)?;
    let version = h[0] & 7;
    if version != 1 && !(profile == UnwindProfile::V4 && version == 2) {
        return Err(invalid("unsupported-windows-unwind-version"));
    }
    let flags = h[0] >> 3;
    if flags & !7 != 0 || (flags & 4 != 0 && flags & 3 != 0) {
        return Err(invalid("invalid-unwind-flags"));
    }
    if u64::from(h[1]) > runtime.end - runtime.begin {
        return Err(invalid("unwind-prologue-outside-function"));
    }
    let bank = usize::from(h[3] & 15);
    let frame_offset = u64::from(h[3] >> 4) * 16;
    if (bank == 0 && frame_offset != 0) || (bank != 0 && !nonvolatile(bank)) {
        return Err(invalid("invalid-unwind-frame-register"));
    }
    let count = usize::from(h[2]);
    let code_address = runtime
        .unwind
        .checked_add(4)
        .ok_or_else(|| invalid("unwind-info-overflow"))?;
    let codes = module_bytes(r, m, code_address, count * 2)?;
    let mut operations = Vec::new();
    let mut at = 0;
    let mut epilogues = Vec::new();
    if version == 2 && count > 0 && codes[1] & 15 == 6 {
        let size = codes[0];
        let flags = codes[1] >> 4;
        if size == 0 || flags > 1 {
            return Err(invalid("invalid-unwind-v2-epilogue-header"));
        }
        let mut add_epilogue = |distance: u64| -> Result<(), Error> {
            let start = runtime
                .end
                .checked_sub(distance)
                .ok_or_else(|| invalid("unwind-v2-epilogue-range"))?;
            let end = start
                .checked_add(u64::from(size))
                .ok_or_else(|| invalid("unwind-v2-epilogue-range"))?;
            if start < runtime.begin
                || end > runtime.end
                || start < runtime.begin + u64::from(h[1])
                || epilogues.iter().any(|other: &EpilogueDescriptor| {
                    start < other.start + u64::from(other.size) && other.start < end
                })
            {
                return Err(invalid("unwind-v2-epilogue-range"));
            }
            epilogues.push(EpilogueDescriptor { start, size });
            Ok(())
        };
        if flags == 1 {
            add_epilogue(u64::from(size))?;
        }
        at = 1;
        while at < count && codes[at * 2 + 1] & 15 == 6 {
            let distance = u64::from(codes[at * 2]) + u64::from(codes[at * 2 + 1] >> 4) * 256;
            at += 1;
            if distance == 0 {
                if at % 2 != 0 || (at < count && codes[at * 2 + 1] & 15 == 6) {
                    return Err(invalid("invalid-unwind-v2-epilogue-padding"));
                }
                break;
            }
            add_epilogue(distance)?;
        }
        if at % 2 != 0 || epilogues.is_empty() {
            return Err(invalid("invalid-unwind-v2-epilogue-prefix"));
        }
    }
    let mut previous = 256u16;
    let mut set_frame = None;
    let mut pushed = false;
    while at < count {
        let pos = at * 2;
        let offset = codes[pos];
        let op = codes[pos + 1] & 15;
        let info = usize::from(codes[pos + 1] >> 4);
        if u16::from(offset) > previous || offset > h[1] {
            return Err(invalid("invalid-unwind-code-order"));
        }
        previous = u16::from(offset);
        let slots = match (op, info) {
            (0 | 2 | 3 | 10, _) => 1,
            (1, 0) | (4 | 8, _) => 2,
            (1, 1) | (5 | 9, _) => 3,
            _ => return Err(invalid("unsupported-unwind-operation")),
        };
        if at + slots > count {
            return Err(invalid("truncated-unwind-operation"));
        }
        // Secondary records can describe noncontiguous fragments or delayed
        // nonvolatile MOV saves. Additional allocation/PUSH recipes are not a
        // supported Windows chained-unwind contract.
        if flags & 4 != 0 && ![4, 5].contains(&op) {
            return Err(invalid("unsupported-chained-unwind-operation"));
        }
        let flags_cleanup = version == 2
            && op == 2
            && info == 0
            && (at + slots == count
                || (at + slots + 1 == count && codes[(at + slots) * 2 + 1] & 15 == 10));
        if pushed && ![0, 10].contains(&op) && !flags_cleanup {
            return Err(invalid("invalid-unwind-push-order"));
        }
        let kind = match op {
            0 => {
                if !nonvolatile(info) {
                    return Err(invalid("invalid-saved-register"));
                }
                pushed = true;
                UnwindOperationKind::Push(info)
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
                UnwindOperationKind::Allocate(size)
            }
            3 => {
                if bank == 0 || info != 0 || set_frame.is_some() {
                    return Err(invalid("invalid-set-frame-operation"));
                }
                set_frame = Some(operations.len());
                UnwindOperationKind::SetFrame
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
                if offset % 8 != 0 {
                    return Err(invalid("unaligned-saved-register-offset"));
                }
                UnwindOperationKind::Save(info, offset)
            }
            8 | 9 => {
                if !(6..=15).contains(&info) {
                    return Err(invalid("invalid-saved-xmm-register"));
                }
                let offset = if op == 8 {
                    u64::from(u16v(&codes, pos + 2)) * 16
                } else {
                    u64::from(u32v(&codes, pos + 2))
                };
                if offset % 16 != 0 {
                    return Err(invalid("unaligned-saved-xmm-slot"));
                }
                UnwindOperationKind::SaveXmm(offset)
            }
            10 => {
                if info > 1 || at + slots != count || flags & 4 != 0 {
                    return Err(invalid("invalid-machine-frame-operation"));
                }
                UnwindOperationKind::MachineFrame(info == 1)
            }
            _ => unreachable!(),
        };
        if bank != 0
            && set_frame.is_some()
            && matches!(
                kind,
                UnwindOperationKind::Save(_, _) | UnwindOperationKind::SaveXmm(_)
            )
        {
            return Err(invalid("save-before-frame-establishment"));
        }
        operations.push(UnwindOperation {
            offset,
            opcode: op,
            kind,
        });
        at += slots;
    }
    if bank != 0 && set_frame.is_none() && flags & 4 == 0 {
        return Err(invalid("missing-set-frame-operation"));
    }
    let trailer = code_address
        .checked_add(((count + 1) & !1) as u64 * 2)
        .ok_or_else(|| invalid("unwind-info-overflow"))?;
    let chained = if flags & 4 != 0 {
        let bytes = module_bytes(r, m, trailer, 12)?;
        let begin = u64::from(u32v(&bytes, 0));
        let end = u64::from(u32v(&bytes, 4));
        let unwind = u64::from(u32v(&bytes, 8));
        if begin >= end || end > m.size || unwind == 0 || unwind + 4 > m.size {
            return Err(invalid("invalid-chained-runtime-function"));
        }
        Some(Runtime {
            begin: m
                .base
                .checked_add(begin)
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
            end: m
                .base
                .checked_add(end)
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
            unwind: m
                .base
                .checked_add(unwind)
                .ok_or_else(|| invalid("runtime-function-address-overflow"))?,
        })
    } else {
        if flags & 3 != 0 {
            // Retain and range-check the handler RVA. Offline stack recovery
            // never calls the handler or interprets its language-specific data.
            let handler = module_bytes(r, m, trailer, 4)?;
            let offset = u64::from(u32v(&handler, 0));
            if offset == 0 || offset >= m.size {
                return Err(invalid("handler-outside-captured-module"));
            }
        }
        None
    };
    Ok(UnwindRecipe {
        version,
        prologue: h[1],
        bank,
        frame_offset,
        operations,
        chained,
        epilogues,
    })
}

struct UnwindStep {
    registers: BTreeMap<String, u64>,
    restored: BTreeMap<String, u64>,
    slot: u64,
    pc: u64,
    sp: u64,
    sp_slot: Option<u64>,
    transition: FrameTransition,
    function: Option<(u64, Option<u64>)>,
    method: &'static str,
}
fn adjusted(value: u64, amount: i64) -> Result<u64, Error> {
    value
        .checked_add_signed(amount)
        .ok_or_else(|| invalid("stack overflow"))
}
fn ensure_epilogue_bytes<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    pc: u64,
    bytes: &mut Vec<u8>,
    needed: usize,
) -> Result<(), Error> {
    if needed > MAX_EPILOGUE_BYTES {
        return Err(invalid("epilogue-byte-budget"));
    }
    if needed > bytes.len() {
        let address = pc
            .checked_add(bytes.len() as u64)
            .ok_or_else(|| invalid("epilogue address overflow"))?;
        bytes.extend(module_bytes(r, m, address, needed - bytes.len())?);
    }
    Ok(())
}
fn is_tail_target<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    primary: &Runtime,
    target: u64,
    limits: &FrameRecoveryLimits,
    profile: UnwindProfile,
) -> Result<bool, Error> {
    if target == primary.begin {
        return Ok(true);
    }
    if target > primary.begin && target < primary.end {
        return Ok(false);
    }
    if target < m.base || u128::from(target) >= u128::from(m.base) + u128::from(m.size) {
        return Ok(true);
    }
    let table = runtime_table(r, m, limits.max_runtime_entries)?;
    let Some(mut function) = table
        .into_iter()
        .find(|f| target >= f.begin && target < f.end)
    else {
        return Ok(true);
    };
    let mut seen = BTreeSet::new();
    for _ in 0..MAX_UNWIND_CHAIN_DEPTH {
        if !seen.insert(function.unwind) {
            return Err(invalid("cyclic-unwind-chain"));
        }
        let recipe = read_recipe(r, m, &function, profile)?;
        if let Some(parent) = recipe.chained {
            function = parent;
        } else {
            return Ok(function.begin != primary.begin || function.unwind != primary.unwind);
        }
    }
    Err(invalid("unwind-chain-budget"))
}
fn unwind_epilogue<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    functions: (Option<&Runtime>, Option<&Runtime>),
    original: &BTreeMap<String, u64>,
    stack: (u64, u128),
    limits: &FrameRecoveryLimits,
    code: (usize, Vec<u8>, UnwindProfile),
) -> Result<Option<UnwindStep>, Error> {
    let (runtime, primary) = functions;
    let (bank, mut bytes, profile) = code;
    if !potential_epilogue(&bytes) {
        return Ok(None);
    }
    let pc = original["rip"];
    let (lo, hi) = stack;
    let mut registers = original.clone();
    let mut restored = BTreeMap::new();
    let mut at = 0;
    // Only the documented stack-adjusting first instruction belongs here.
    // A partial epilogue can instead start at any remaining POP or terminal.
    if bytes.starts_with(&[0x48, 0x83, 0xc4]) || bytes.starts_with(&[0x48, 0x81, 0xc4]) {
        let (size, length) = if bytes[1] == 0x83 {
            (i64::from(bytes[3] as i8), 4)
        } else {
            (
                i64::from(i32::from_le_bytes(bytes[3..7].try_into().expect("prefix"))),
                7,
            )
        };
        if size <= 0 {
            return Err(invalid("invalid-epilogue-stack-adjustment"));
        }
        registers.insert("rsp".into(), adjusted(registers["rsp"], size)?);
        at = length;
    } else if bytes[0] & 0xf8 == 0x48 && bytes[1] == 0x8d && (bytes[2] >> 3) & 7 == 4 {
        let rex = bytes[0];
        let modrm = bytes[2];
        let mode = modrm >> 6;
        if bank == 0 || rex & 4 != 0 || ![1, 2].contains(&mode) {
            return Err(invalid("unsupported-epilogue-stack-address"));
        }
        let mut base = usize::from(modrm & 7);
        let mut displacement = 3;
        if base == 4 {
            let sib = bytes[3];
            if sib & 0x38 != 0x20 || rex & 2 != 0 {
                return Err(invalid("unsupported-epilogue-stack-address"));
            }
            base = usize::from(sib & 7);
            displacement += 1;
        }
        base += usize::from(rex & 1) * 8;
        if base != bank {
            return Err(invalid("epilogue-frame-register-mismatch"));
        }
        let delta = if mode == 1 {
            i64::from(bytes[displacement] as i8)
        } else {
            i64::from(i32::from_le_bytes(
                bytes[displacement..displacement + 4]
                    .try_into()
                    .expect("prefix"),
            ))
        };
        let value = registers
            .get(BANKS[base])
            .copied()
            .ok_or_else(|| invalid("missing-unwind-frame-register"))?;
        registers.insert("rsp".into(), adjusted(value, delta)?);
        at = displacement + if mode == 1 { 1 } else { 4 };
    }
    loop {
        ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 1)?;
        let start = at;
        let rex = if (0x40..=0x4f).contains(&bytes[at]) {
            let value = bytes[at];
            at += 1;
            ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 1)?;
            value
        } else {
            0
        };
        let opcode = bytes[at];
        if (0x58..=0x5f).contains(&opcode) {
            let bank = usize::from(opcode - 0x58) + usize::from(rex & 1) * 8;
            if !nonvolatile(bank) {
                return Err(invalid("unsupported-epilogue-pop-register"));
            }
            let sp = registers["rsp"];
            registers.insert(BANKS[bank].into(), r.stack(sp, lo, hi)?);
            restored.insert(BANKS[bank].into(), sp);
            registers.insert(
                "rsp".into(),
                sp.checked_add(8).ok_or_else(|| invalid("stack overflow"))?,
            );
            at += 1;
            if runtime.is_some_and(|f| u128::from(pc) + at as u128 >= u128::from(f.end)) {
                return Err(invalid("epilogue-outside-runtime-function"));
            }
            continue;
        }
        let length = match opcode {
            0xc3 if rex == 0 => 1,
            0xc2 if rex == 0 => {
                ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 3)?;
                // Windows RtlVirtualUnwind reconstructs the caller's virtual
                // context by popping the return PC only, including RET imm16.
                // Retain the complete instruction bytes; applying the immediate
                // would instead simulate CPU execution and disagree with that
                // independently exercised Windows unwind contract.
                3
            }
            0xf3 if rex == 0 => {
                ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 2)?;
                if bytes[at + 1] != 0xc3 {
                    return Err(invalid("unsupported-epilogue-or-tail-transfer"));
                }
                2
            }
            0xe9 | 0xeb if rex == 0 => {
                let length = if opcode == 0xe9 { 5 } else { 2 };
                ensure_epilogue_bytes(r, m, pc, &mut bytes, at + length)?;
                let offset = if opcode == 0xe9 {
                    i64::from(i32::from_le_bytes(
                        bytes[at + 1..at + 5].try_into().expect("ensured"),
                    ))
                } else {
                    i64::from(bytes[at + 1] as i8)
                };
                let next = pc
                    .checked_add((at + length) as u64)
                    .ok_or_else(|| invalid("epilogue address overflow"))?;
                let target = next
                    .checked_add_signed(offset)
                    .ok_or_else(|| invalid("epilogue target overflow"))?;
                let primary =
                    primary.ok_or_else(|| invalid("unsupported-epilogue-internal-jump"))?;
                if !is_tail_target(r, m, primary, target, limits, profile)? {
                    return Err(invalid("unsupported-epilogue-internal-jump"));
                }
                length
            }
            0xff => {
                ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 2)?;
                let modrm = bytes[at + 1];
                if (modrm >> 3) & 7 != 4 {
                    return Err(invalid("unsupported-epilogue-or-tail-transfer"));
                }
                let mode = modrm >> 6;
                let mut length = 2;
                if mode == 0 {
                    match modrm & 7 {
                        5 => length += 4,
                        4 => {
                            ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 3)?;
                            length += 1;
                            if bytes[at + 2] & 7 == 5 {
                                length += 4;
                            }
                        }
                        _ => {}
                    }
                } else if mode != 3 || rex & 8 == 0 {
                    return Err(invalid("unsupported-epilogue-indirect-jump"));
                }
                ensure_epilogue_bytes(r, m, pc, &mut bytes, at + length)?;
                length
            }
            _ => return Err(invalid("unsupported-epilogue-or-tail-transfer")),
        };
        let end = at + length;
        if end <= start || runtime.is_some_and(|f| u128::from(pc) + end as u128 > u128::from(f.end))
        {
            return Err(invalid("epilogue-outside-runtime-function"));
        }
        break;
    }
    let slot = registers["rsp"];
    let next_pc = r.stack(slot, lo, hi)?;
    let sp = slot
        .checked_add(8)
        .ok_or_else(|| invalid("stack overflow"))?;
    if sp <= original["rsp"] {
        return Err(invalid("nonprogressing-stack-unwind"));
    }
    if u128::from(sp) > hi {
        return Err(invalid("return-or-save-outside-thread-stack"));
    }
    if sp - original["rsp"] > limits.max_stack_adjustment {
        return Err(invalid("unwind-stack-adjustment-budget"));
    }
    Ok(Some(UnwindStep {
        registers,
        restored,
        slot,
        pc: next_pc,
        sp,
        sp_slot: None,
        transition: FrameTransition::NormalReturn,
        function: None,
        method: "runtime-v1-epilogue",
    }))
}
fn read_epilogue_terminal<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    pc: u64,
    function_end: u64,
) -> Result<Vec<u8>, Error> {
    let mut bytes = module_bytes(r, m, pc, 1)?;
    let at = if (0x40..=0x4f).contains(&bytes[0]) {
        ensure_epilogue_bytes(r, m, pc, &mut bytes, 2)?;
        1
    } else {
        0
    };
    let length = match bytes[at] {
        0xc3 => at + 1,
        0xc2 => at + 3,
        0xf3 => {
            ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 2)?;
            if bytes[at + 1] != 0xc3 {
                return Err(invalid("unsupported-epilogue-or-tail-transfer"));
            }
            at + 2
        }
        0xe9 => at + 5,
        0xeb => at + 2,
        0xcf if at == 1 && bytes[0] == 0x48 => 2,
        0xff => {
            ensure_epilogue_bytes(r, m, pc, &mut bytes, at + 2)?;
            let modrm = bytes[at + 1];
            if (modrm >> 3) & 7 != 4 {
                return Err(invalid("unsupported-epilogue-or-tail-transfer"));
            }
            let mode = modrm >> 6;
            let mut length = at + 2;
            if mode != 3 && modrm & 7 == 4 {
                ensure_epilogue_bytes(r, m, pc, &mut bytes, length + 1)?;
                let sib = bytes[length];
                length += 1;
                if mode == 0 && sib & 7 == 5 {
                    length += 4;
                }
            } else if mode == 0 && modrm & 7 == 5 {
                length += 4;
            }
            if mode == 1 {
                length += 1;
            }
            if mode == 2 {
                length += 4;
            }
            length
        }
        _ => return Err(invalid("unsupported-epilogue-or-tail-transfer")),
    };
    if pc
        .checked_add(length as u64)
        .is_none_or(|end| end > function_end)
    {
        return Err(invalid("epilogue-outside-runtime-function"));
    }
    ensure_epilogue_bytes(r, m, pc, &mut bytes, length)?;
    Ok(bytes)
}
fn unwind_epilogue_v2<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    recipes: &[(Runtime, UnwindRecipe)],
    original: &BTreeMap<String, u64>,
    stack: (u64, u128),
    limits: &FrameRecoveryLimits,
    location: (&EpilogueDescriptor, u64, UnwindProfile),
) -> Result<UnwindStep, Error> {
    let (descriptor, lookup, profile) = location;
    let offset = usize::try_from(lookup - descriptor.start)
        .map_err(|_| invalid("unwind-v2-epilogue-range"))?;
    let bytes = module_bytes(r, m, descriptor.start, usize::from(descriptor.size))?;
    // Windows v2 excludes the ADD/LEA cleanup from the described epilogue.
    // The primary PUSH suffix describes the remaining POPs, then an optional
    // flags cleanup, then a return or a machine-frame terminal. Capture bytes
    // must corroborate that recipe, even though the OS can trust its producer.
    let suffix = recipes
        .iter()
        .find_map(|(_, recipe)| {
            recipe
                .operations
                .iter()
                .position(|op| {
                    matches!(
                        op.kind,
                        UnwindOperationKind::Push(_) | UnwindOperationKind::MachineFrame(_)
                    )
                })
                .map(|index| &recipe.operations[index..])
        })
        .unwrap_or(&[]);
    let mut registers = original.clone();
    let mut restored = BTreeMap::new();
    let (lo, hi) = stack;
    let mut at = 0;
    let mut index = 0;
    let mut boundary = false;
    while let Some(UnwindOperation {
        kind: UnwindOperationKind::Push(bank),
        ..
    }) = suffix.get(index)
    {
        let length = if *bank < 8 { 1 } else { 2 };
        if at + length >= bytes.len() {
            return Err(invalid("unwind-v2-epilogue-size-mismatch"));
        }
        let matches = if *bank < 8 {
            bytes[at] == 0x58 + *bank as u8
        } else {
            bytes[at] & 0xf1 == 0x41 && bytes[at + 1] == 0x58 + (*bank as u8 - 8)
        };
        if !matches {
            return Err(invalid("unwind-v2-epilogue-byte-mismatch"));
        }
        boundary |= at == offset;
        if at >= offset {
            let sp = registers["rsp"];
            registers.insert(BANKS[*bank].into(), r.stack(sp, lo, hi)?);
            restored.insert(BANKS[*bank].into(), sp);
            registers.insert(
                "rsp".into(),
                sp.checked_add(8).ok_or_else(|| invalid("stack overflow"))?,
            );
        }
        at += length;
        index += 1;
    }
    if suffix
        .get(index)
        .is_some_and(|op| op.opcode == 2 && matches!(op.kind, UnwindOperationKind::Allocate(8)))
    {
        if at + 1 >= bytes.len() || ![0x58, 0x59, 0x5a].contains(&bytes[at]) {
            return Err(invalid("unwind-v2-flags-pop-byte-mismatch"));
        }
        boundary |= at == offset;
        if at >= offset {
            let sp = registers["rsp"];
            // Keep the discarded captured flags slot as evidence, without
            // publishing a reconstructed volatile register or RFLAGS context.
            r.stack_bytes(sp, 8, lo, hi)?;
            registers.insert(
                "rsp".into(),
                sp.checked_add(8).ok_or_else(|| invalid("stack overflow"))?,
            );
        }
        at += 1;
        index += 1;
    }
    let machine = if let Some(op) = suffix.get(index) {
        if !matches!(op.kind, UnwindOperationKind::MachineFrame(_)) || index + 1 != suffix.len() {
            return Err(invalid("unsupported-unwind-v2-epilogue-suffix"));
        }
        true
    } else {
        false
    };
    if at + 1 != bytes.len() {
        return Err(invalid("unwind-v2-epilogue-size-mismatch"));
    }
    boundary |= at == offset;
    if !boundary {
        return Err(invalid("unwind-v2-epilogue-pc-not-instruction-boundary"));
    }
    let terminal = descriptor
        .start
        .checked_add(at as u64)
        .ok_or_else(|| invalid("epilogue address overflow"))?;
    if machine {
        let instruction = read_epilogue_terminal(r, m, terminal, recipes[0].0.end)?;
        if instruction != [0x48, 0xcf] {
            return Err(invalid("unwind-v2-machine-terminal-mismatch"));
        }
        let slot = registers["rsp"];
        // An error code has already been removed before the v2 epilogue.
        // Unlike body PUSH_MACHFRAME decoding, both variants now start at RIP.
        let machine_bytes = r.stack_bytes(slot, 40, lo, hi)?;
        let sp = u64v(&machine_bytes, 24);
        if sp < lo || u128::from(sp) > hi {
            return Err(invalid("machine-frame-rsp-outside-thread-stack"));
        }
        if sp <= original["rsp"] {
            return Err(invalid("nonprogressing-machine-frame-stack"));
        }
        if sp - original["rsp"] > limits.max_stack_adjustment {
            return Err(invalid("unwind-stack-adjustment-budget"));
        }
        return Ok(UnwindStep {
            registers,
            restored,
            slot,
            pc: u64v(&machine_bytes, 0),
            sp,
            sp_slot: Some(
                slot.checked_add(24)
                    .ok_or_else(|| invalid("stack overflow"))?,
            ),
            transition: FrameTransition::MachineFrame,
            function: None,
            method: "runtime-v2-machine-frame",
        });
    }
    let terminal_bytes = read_epilogue_terminal(r, m, terminal, recipes[0].0.end)?;
    let opcode = if (0x40..=0x4f).contains(&terminal_bytes[0]) {
        terminal_bytes[1]
    } else {
        terminal_bytes[0]
    };
    if ![0xc2, 0xc3, 0xf3, 0xe9, 0xeb, 0xff].contains(&opcode) {
        return Err(invalid("unwind-v2-epilogue-byte-mismatch"));
    }
    registers.insert("rip".into(), terminal);
    let mut step = unwind_epilogue(
        r,
        m,
        (Some(&recipes[0].0), recipes.last().map(|(f, _)| f)),
        &registers,
        stack,
        limits,
        (recipes[0].1.bank, terminal_bytes, profile),
    )?
    .ok_or_else(|| invalid("unwind-v2-epilogue-byte-mismatch"))?;
    if step.sp <= original["rsp"] {
        return Err(invalid("nonprogressing-stack-unwind"));
    }
    if step.sp - original["rsp"] > limits.max_stack_adjustment {
        return Err(invalid("unwind-stack-adjustment-budget"));
    }
    step.restored = restored;
    step.function = (recipes.len() == 1).then_some((recipes[0].0.begin, Some(recipes[0].0.end)));
    step.method = if recipes.len() == 1 {
        "runtime-v2-epilogue"
    } else {
        "runtime-v2-chained"
    };
    Ok(step)
}
fn recover_step<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    r: &mut Reader<'_, F>,
    m: &FrameModule,
    runtime: Option<&Runtime>,
    original: &BTreeMap<String, u64>,
    location: (u64, bool, UnwindProfile),
    stack: (u64, u128),
    limits: &FrameRecoveryLimits,
) -> Result<UnwindStep, Error> {
    let (lookup, exact_pc, profile) = location;
    let (lo, hi) = stack;
    let mut registers = original.clone();
    let mut restored = BTreeMap::new();
    let prefix = if exact_pc && profile != UnwindProfile::V4 {
        Some(module_bytes(r, m, original["rip"], 15)?)
    } else {
        None
    };
    let mut recipes = Vec::new();
    if let Some(runtime) = runtime {
        let mut current = runtime.clone();
        let mut seen = BTreeSet::new();
        loop {
            if !seen.insert(current.unwind) {
                return Err(invalid("cyclic-unwind-chain"));
            }
            if recipes.len() >= MAX_UNWIND_CHAIN_DEPTH {
                return Err(invalid("unwind-chain-budget"));
            }
            let recipe = read_recipe(r, m, &current, profile)?;
            if let Some((_, first)) = recipes.first() {
                let first: &UnwindRecipe = first;
                if recipe.bank != first.bank || recipe.frame_offset != first.frame_offset {
                    return Err(invalid("inconsistent-chained-frame-register"));
                }
            }
            let next = recipe.chained.clone();
            recipes.push((current, recipe));
            match next {
                Some(next) => current = next,
                None => break,
            }
        }
    }
    let bank = recipes.first().map_or(0, |(_, recipe)| recipe.bank);
    let function = if recipes.len() == 1 {
        runtime.map(|f| (f.begin, Some(f.end)))
    } else {
        None
    };
    let windows_v2 = recipes
        .first()
        .is_some_and(|(_, recipe)| recipe.version == 2);
    if windows_v2 {
        if let Some(descriptor) = recipes[0].1.epilogues.iter().find(|descriptor| {
            lookup >= descriptor.start && lookup - descriptor.start < u64::from(descriptor.size)
        }) {
            if !exact_pc {
                return Err(invalid("return-context-inside-unwind-v2-epilogue"));
            }
            return unwind_epilogue_v2(
                r,
                m,
                &recipes,
                original,
                stack,
                limits,
                (descriptor, lookup, profile),
            );
        }
        // V2 counts only the terminal's first byte in its descriptor. A PC
        // inside the remaining RET/JMP/IRETQ encoding is not a body context.
        // Read only a nearby declared terminal to establish that boundary;
        // ordinary body/prologue recovery needs no unrelated code capture.
        for descriptor in &recipes[0].1.epilogues {
            let terminal = descriptor.start + u64::from(descriptor.size) - 1;
            if lookup > terminal && lookup - terminal < 15 {
                let bytes = read_epilogue_terminal(r, m, terminal, recipes[0].0.end)?;
                if lookup - terminal < bytes.len() as u64 {
                    return Err(invalid("unwind-v2-epilogue-pc-not-instruction-boundary"));
                }
            }
        }
        // Outside its explicit epilogue ranges, v2 uses the ordinary recipe.
        // In particular, cleanup immediately before a range is not executed
        // twice by applying the v1 instruction-scanning heuristic.
    } else if let Some(prefix) = if exact_pc && profile == UnwindProfile::V4 {
        Some(module_bytes(r, m, original["rip"], 15)?)
    } else {
        prefix
    } {
        if let Some(mut step) = unwind_epilogue(
            r,
            m,
            (runtime, recipes.last().map(|(f, _)| f)),
            original,
            stack,
            limits,
            (bank, prefix, profile),
        )? {
            step.function = function;
            if recipes.len() > 1 {
                step.method = "runtime-v1-chained";
            }
            return Ok(step);
        }
    }
    let mut machine = None;
    for (index, (function, recipe)) in recipes.iter().enumerate() {
        let prologue_offset = if index == 0 {
            lookup - function.begin
        } else {
            u64::MAX
        };
        let in_prologue = prologue_offset <= u64::from(recipe.prologue);
        let frame_established = !in_prologue
            || recipe.chained.is_some()
            || recipe.operations.iter().any(|op| {
                matches!(op.kind, UnwindOperationKind::SetFrame)
                    && u64::from(op.offset) <= prologue_offset
            });
        let base = if recipe.bank == 0 || !frame_established {
            original["rsp"]
        } else {
            original
                .get(BANKS[recipe.bank])
                .copied()
                .ok_or_else(|| invalid("missing-unwind-frame-register"))?
                .checked_sub(recipe.frame_offset)
                .ok_or_else(|| invalid("frame offset underflow"))?
        };
        for op in &recipe.operations {
            if u64::from(op.offset) > prologue_offset {
                continue;
            }
            let sp = registers["rsp"];
            match op.kind {
                UnwindOperationKind::Push(bank) => {
                    let value = r.stack(sp, lo, hi)?;
                    registers.insert(BANKS[bank].into(), value);
                    restored.insert(BANKS[bank].into(), sp);
                    registers.insert(
                        "rsp".into(),
                        sp.checked_add(8).ok_or_else(|| invalid("stack overflow"))?,
                    );
                }
                UnwindOperationKind::Allocate(size) => {
                    if size > limits.max_stack_adjustment {
                        return Err(invalid("unwind-stack-adjustment-budget"));
                    }
                    registers.insert(
                        "rsp".into(),
                        sp.checked_add(size)
                            .ok_or_else(|| invalid("stack overflow"))?,
                    );
                }
                UnwindOperationKind::SetFrame => {
                    registers.insert("rsp".into(), base);
                }
                UnwindOperationKind::Save(bank, offset) => {
                    let address = base
                        .checked_add(offset)
                        .ok_or_else(|| invalid("saved register overflow"))?;
                    registers.insert(BANKS[bank].into(), r.stack(address, lo, hi)?);
                    restored.insert(BANKS[bank].into(), address);
                }
                UnwindOperationKind::SaveXmm(offset) => {
                    let address = base
                        .checked_add(offset)
                        .ok_or_else(|| invalid("saved register overflow"))?;
                    if address % 16 != 0 {
                        return Err(invalid("unaligned-saved-xmm-slot"));
                    }
                    r.stack_bytes(address, 16, lo, hi)?;
                }
                UnwindOperationKind::MachineFrame(error_code) => {
                    let bytes = r.stack_bytes(sp, if error_code { 48 } else { 40 }, lo, hi)?;
                    let offset = usize::from(error_code) * 8;
                    let slot = sp
                        .checked_add(offset as u64)
                        .ok_or_else(|| invalid("stack overflow"))?;
                    let next = u64v(&bytes, offset + 24);
                    if next < lo || u128::from(next) > hi {
                        return Err(invalid("machine-frame-rsp-outside-thread-stack"));
                    }
                    if next <= original["rsp"] {
                        return Err(invalid("nonprogressing-machine-frame-stack"));
                    }
                    machine = Some((
                        slot,
                        u64v(&bytes, offset),
                        next,
                        slot.checked_add(24)
                            .ok_or_else(|| invalid("stack overflow"))?,
                    ));
                }
            }
        }
    }
    let (slot, pc, sp, sp_slot, transition) = if let Some((slot, pc, sp, sp_slot)) = machine {
        (slot, pc, sp, Some(sp_slot), FrameTransition::MachineFrame)
    } else {
        let slot = registers["rsp"];
        (
            slot,
            r.stack(slot, lo, hi)?,
            slot.checked_add(8)
                .ok_or_else(|| invalid("stack overflow"))?,
            None,
            FrameTransition::NormalReturn,
        )
    };
    if transition == FrameTransition::NormalReturn && sp <= original["rsp"] {
        return Err(invalid("nonprogressing-stack-unwind"));
    }
    if sp.abs_diff(original["rsp"]) > limits.max_stack_adjustment {
        return Err(invalid("unwind-stack-adjustment-budget"));
    }
    let (function, method) = if transition == FrameTransition::MachineFrame {
        (
            None,
            if windows_v2 {
                "runtime-v2-machine-frame"
            } else {
                "runtime-v1-machine-frame"
            },
        )
    } else if recipes.len() > 1 {
        (
            None,
            if windows_v2 {
                "runtime-v2-chained"
            } else {
                "runtime-v1-chained"
            },
        )
    } else if runtime.is_some() {
        (
            function,
            if windows_v2 {
                "runtime-v2"
            } else {
                "runtime-v1"
            },
        )
    } else {
        (None, "leaf-under-windows-abi")
    };
    Ok(UnwindStep {
        registers,
        restored,
        slot,
        pc,
        sp,
        sp_slot,
        transition,
        function,
        method,
    })
}
pub(crate) fn recover_frames<F: FnMut(u64, usize) -> Result<FrameMemoryEvidence, Error>>(
    seed: FrameSeed,
    limits: FrameRecoveryLimits,
    profile: &str,
    read: &mut F,
) -> Result<CapturedFrameChain, Error> {
    let profile = UnwindProfile::parse(profile)?;
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
        let mut exact_pc = true;
        for index in 0..limits.max_frames {
            let pc = registers["rip"];
            let original_sp = registers["rsp"];
            if pc == 0 && index > 0 && (!profile.extended() || !exact_pc) {
                reason = "zero-return-boundary".into();
                break;
            }
            if !seen.insert((pc, original_sp)) {
                reason = "cyclic-frame-context".into();
                break;
            }
            let lookup = if index == 0 || (profile.extended() && exact_pc) {
                pc
            } else {
                pc - 1
            };
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
                transition: None,
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
                function_begin: runtime
                    .as_ref()
                    .filter(|_| !profile.extended())
                    .map(|f| f.begin),
                function_end: runtime
                    .as_ref()
                    .filter(|_| !profile.extended())
                    .map(|f| f.end),
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
                transition: None,
            };
            let step = (|| -> Result<(), Error> {
                if profile.extended() {
                    let step = recover_step(
                        &mut r,
                        m,
                        runtime.as_ref(),
                        &registers,
                        (lookup, exact_pc, profile),
                        (lo, hi),
                        &limits,
                    )?;
                    frame.return_slot = Some(step.slot);
                    frame.return_pc = Some(step.pc);
                    frame.function_begin = step.function.map(|(begin, _)| begin);
                    frame.function_end = step.function.and_then(|(_, end)| end);
                    frame.method = step.method.into();
                    frame.transition = Some(step.transition);
                    exact_pc = step.transition == FrameTransition::MachineFrame;
                    registers = step.registers;
                    registers.retain(|name, _| {
                        name == "rsp"
                            || BANKS
                                .iter()
                                .enumerate()
                                .any(|(i, b)| nonvolatile(i) && b == name)
                    });
                    registers.insert("rip".into(), step.pc);
                    registers.insert("rsp".into(), step.sp);
                    register_evidence = registers
                        .keys()
                        .map(|name| {
                            let (source, stack_slot) = if name == "rip" {
                                (
                                    if exact_pc {
                                        "machine-frame-rip"
                                    } else {
                                        "return-slot"
                                    },
                                    Some(step.slot),
                                )
                            } else if name == "rsp" {
                                (
                                    if exact_pc {
                                        "machine-frame-rsp"
                                    } else {
                                        "unwind-rsp"
                                    },
                                    Some(step.sp_slot.unwrap_or(step.slot)),
                                )
                            } else if let Some(slot) = step.restored.get(name) {
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
                    return Ok(());
                }
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
                    let code_address = f
                        .unwind
                        .checked_add(4)
                        .ok_or_else(|| invalid("unwind-info-overflow"))?;
                    let codes = r.bytes(code_address, count * 2)?;
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
                            8 if profile == UnwindProfile::V2 => 2,
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
                            8 => {
                                if !(6..=15).contains(&info) {
                                    return Err(invalid("invalid-saved-xmm-register"));
                                }
                                // Saves using a frame pointer must occur after its
                                // establishment in the prologue, hence before its
                                // SET_FPREG operation during reverse unwinding.
                                if bank != 0 && set_frame {
                                    return Err(invalid("xmm-save-before-frame-establishment"));
                                }
                                let offset = u64::from(u16v(&codes, pos + 2)) * 16;
                                let addr = base
                                    .checked_add(offset)
                                    .ok_or_else(|| invalid("saved register overflow"))?;
                                if addr % 16 != 0 {
                                    return Err(invalid("unaligned-saved-xmm-slot"));
                                }
                                // The public context contains GPRs only. Preserve
                                // all saved XMM bytes as checked capture evidence;
                                // this operation changes neither RSP nor a GPR.
                                r.stack_bytes(addr, 16, lo, hi)?;
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
            if registers["rip"] == 0 && (!profile.extended() || !exact_pc) {
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
        profile: profile.name().into(),
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
