//! Retained decoded address roles, independently checked against finite MOV encodings.
//! This module supplies decoded facts only; it never produces instruction effects.
use super::{AdapterError, protocol};
#[cfg(feature = "investigation")]
use crate::effects::RegisterView;

#[derive(Clone, Debug, PartialEq, Eq)]
#[cfg_attr(
    feature = "investigation",
    derive(serde::Serialize, serde::Deserialize)
)]
#[cfg_attr(feature = "investigation", serde(deny_unknown_fields))]
pub struct DecodedAddressReference {
    #[cfg_attr(feature = "investigation", serde(with = "crate::investigation::va"))]
    pub address: u64,
    pub bytes_hex: String,
    pub length: u8,
    pub opcode: String,
    pub memory_operand: usize,
    pub base: Option<String>,
    pub index: Option<String>,
    pub scale: u8,
    pub displacement: i64,
    pub segment: Option<String>,
    pub address_width: u8,
    pub access_width: u8,
    pub rip_relative: bool,
    pub raw_record: String,
    pub decoder_sha256: Option<String>,
    pub decoder_version: String,
    pub protocol: u8,
    pub target: String,
    pub gaps: Vec<String>,
}

fn register(operand: &protocol::RawOperand) -> Result<Option<String>, AdapterError> {
    match operand {
        protocol::RawOperand::Register(name) => Ok((name != "NONE").then(|| name.clone())),
        _ => Err(AdapterError::DecoderProtocol(
            "decoded address register tag".into(),
        )),
    }
}
fn immediate(operand: &protocol::RawOperand) -> Result<i64, AdapterError> {
    match operand {
        protocol::RawOperand::Immediate(n) => Ok(*n),
        _ => Err(AdapterError::DecoderProtocol(
            "decoded address immediate tag".into(),
        )),
    }
}
#[cfg(feature = "investigation")]
pub(crate) fn gpr_bank(name: &str) -> Option<u8> {
    RegisterView::parse(name)
        .filter(|v| v.width() == 64 && v.bit_offset() == 0)
        .map(|v| v.bank())
}
const GPRS: [&str; 16] = [
    "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12", "R13",
    "R14", "R15",
];

// Reviewed finite ModRM/SIB facts, not another semantic lifter. Unsupported
// prefixes/shapes remain explicit and are never used to synthesize effects.
fn encoding_agrees(value: &DecodedAddressReference, bytes: &[u8]) -> bool {
    let mut at = 0;
    let mut rex = 0;
    while let Some(b) = bytes.get(at).filter(|b| (0x40..=0x4f).contains(*b)) {
        rex = *b;
        at += 1;
    }
    let Some(opcode) = bytes.get(at) else {
        return false;
    };
    at += 1;
    if ![0xc7, 0x8b, 0x89].contains(opcode) {
        return false;
    }
    let width = if rex & 8 != 0 { 64 } else { 32 };
    let expected = match (*opcode, width) {
        (0xc7, 32) => "MOV32mi",
        (0xc7, 64) => "MOV64mi32",
        (0x8b, 32) => "MOV32rm",
        (0x8b, 64) => "MOV64rm",
        (0x89, 32) => "MOV32mr",
        (0x89, 64) => "MOV64mr",
        _ => return false,
    };
    let Some(modrm) = bytes.get(at) else {
        return false;
    };
    at += 1;
    let mode = modrm >> 6;
    if mode == 3 || *opcode == 0xc7 && (modrm >> 3) & 7 != 0 {
        return false;
    }
    let rm = modrm & 7;
    let mut scale = 1;
    let mut index = None;
    let mut base = None;
    let mut disp_width = match mode {
        1 => 1,
        2 => 4,
        _ => 0,
    };
    let mut rip = false;
    if rm == 4 {
        let Some(sib) = bytes.get(at) else {
            return false;
        };
        at += 1;
        scale = 1 << (sib >> 6);
        let idx = (sib >> 3) & 7;
        if idx != 4 || rex & 2 != 0 {
            index = Some(GPRS[(idx | ((rex & 2) << 2)) as usize].to_string());
        }
        let b = sib & 7;
        if mode == 0 && b == 5 {
            disp_width = 4;
        } else {
            base = Some(GPRS[(b | ((rex & 1) << 3)) as usize].to_string());
        }
    } else if mode == 0 && rm == 5 {
        base = Some("RIP".into());
        rip = true;
        disp_width = 4;
    } else {
        base = Some(GPRS[(rm | ((rex & 1) << 3)) as usize].to_string());
    }
    let Some(displacement_bytes) = bytes.get(at..at + disp_width) else {
        return false;
    };
    let displacement = match disp_width {
        0 => 0,
        1 => i64::from(displacement_bytes[0] as i8),
        4 => i64::from(i32::from_le_bytes(
            displacement_bytes.try_into().expect("four bytes"),
        )),
        _ => return false,
    };
    at += disp_width;
    if *opcode == 0xc7 {
        at += 4;
    }
    value.opcode == expected
        && bytes.len() == at
        && value.base == base
        && value.index == index
        && value.scale == scale
        && value.displacement == displacement
        && value.segment.is_none()
        && value.address_width == 64
        && value.access_width == width
        && value.rip_relative == rip
}

impl DecodedAddressReference {
    pub(crate) fn from_raw(
        raw: &protocol::Raw,
        bytes: &[u8],
        decoder_sha256: Option<String>,
        target: &str,
    ) -> Result<Option<Self>, AdapterError> {
        let (memory_operand, access_width) = match raw.opcode.as_str() {
            "MOV32mi" | "MOV32mr" => (0, 32),
            "MOV64mi32" | "MOV64mr" => (0, 64),
            "MOV32rm" => (1, 32),
            "MOV64rm" => (1, 64),
            _ => return Ok(None),
        };
        if raw.operands.len() != 6 || raw.decoded.status != "ok" {
            return Ok(None);
        }
        let operands = &raw.operands[memory_operand..memory_operand + 5];
        let base = register(&operands[0])?;
        let index = register(&operands[2])?;
        let scale = immediate(&operands[1])?;
        if ![1, 2, 4, 8].contains(&scale) {
            return Ok(None);
        }
        let mut value = Self {
            address: raw.decoded.address,
            bytes_hex: super::hex(bytes),
            length: bytes.len() as u8,
            opcode: raw.opcode.clone(),
            memory_operand,
            rip_relative: base.as_deref() == Some("RIP"),
            base,
            index,
            scale: scale as u8,
            displacement: immediate(&operands[3])?,
            segment: register(&operands[4])?,
            address_width: 64,
            access_width,
            raw_record: raw.record.clone(),
            decoder_sha256,
            decoder_version: "LLVM MC 20.1.2".into(),
            protocol: 2,
            target: target.into(),
            gaps: Vec::new(),
        };
        for b in bytes {
            if *b == 0x67 {
                value.address_width = 32;
            } else if ![0x66, 0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65].contains(b)
                && !(0x40..=0x4f).contains(b)
            {
                break;
            }
        }
        if !encoding_agrees(&value, bytes) {
            value
                .gaps
                .push("decoded-encoding-disagreement-or-prefix".into());
        }
        Ok(Some(value))
    }
    pub fn validate(&self) -> Result<(), AdapterError> {
        if self.bytes_hex.len() % 2 != 0
            || self.bytes_hex.len() > 30
            || self.bytes_hex.is_empty()
            || !self
                .bytes_hex
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
            || self.decoder_sha256.as_ref().is_some_and(|s| {
                s.len() != 64
                    || !s
                        .bytes()
                        .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
            })
        {
            return Err(AdapterError::DecoderProtocol(
                "invalid decoded-address identity".into(),
            ));
        }
        let bytes: Vec<_> = (0..self.bytes_hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&self.bytes_hex[i..i + 2], 16).expect("checked hex"))
            .collect();
        let raw = protocol::parse(&self.raw_record)?;
        if raw.decoded.length != bytes.len() as u64
            || raw.decoded.address != self.address
            || !["x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"]
                .contains(&self.target.as_str())
            || Self::from_raw(&raw, &bytes, self.decoder_sha256.clone(), &self.target)?.as_ref()
                != Some(self)
        {
            return Err(AdapterError::DecoderProtocol(
                "decoded-address receipt differs from raw facts".into(),
            ));
        }
        Ok(())
    }
}
