//! Decoded facts for an independent semantic producer. No legacy effect rules.
use super::{AdapterError, DecoderTarget, PreparedBatch, PreparedSite, hex, protocol};
use crate::{
    Address, ByteSource, Instruction, InstructionKind,
    effects::{
        EffectQuality, GapReason, InstructionEvidence, Operand, PreparationGap,
        PreparationIdentity, PreparationOptions, RegisterView,
    },
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
};

pub fn decode_captured_batch(
    snapshot: &str,
    candidates: &BTreeMap<Address, Option<Vec<u8>>>,
    decoder: &Path,
    options: &PreparationOptions,
    target: DecoderTarget,
) -> Result<PreparedBatch, AdapterError> {
    if snapshot.is_empty()
        || candidates.is_empty()
        || candidates
            .values()
            .flatten()
            .any(|b| b.is_empty() || b.len() > 15)
    {
        return Err(AdapterError::InvalidInput(
            "nonempty snapshot/candidates and 1..15-byte prefixes required".into(),
        ));
    }
    let available: BTreeMap<_, _> = candidates
        .iter()
        .filter_map(|(&a, b)| b.as_ref().map(|b| (a, b)))
        .collect();
    let input = available
        .iter()
        .map(|(a, b)| format!("{a} {}\n", hex(b)))
        .collect();
    #[cfg(feature = "investigation")]
    let decoder_digest = Some(crate::investigation::sha(&std::fs::read(decoder)?));
    #[cfg(not(feature = "investigation"))]
    let decoder_digest = None;
    let rows = protocol::invoke(decoder, input, available.len(), target)?;
    #[cfg(feature = "investigation")]
    if decoder_digest.as_deref()
        != Some(crate::investigation::sha(&std::fs::read(decoder)?).as_str())
    {
        return Err(AdapterError::DecoderProtocol(
            "decoder executable changed during preparation".into(),
        ));
    }
    let mut sites = BTreeMap::new();
    for raw in rows {
        let a = raw.decoded.address;
        let d = &raw.decoded;
        let bytes = available
            .get(&a)
            .ok_or_else(|| AdapterError::DecoderProtocol("unexpected reference VA".into()))?;
        if sites.contains_key(&a) || d.length > bytes.len() as u64 {
            return Err(AdapterError::DecoderProtocol(
                "duplicate VA/invalid reference length".into(),
            ));
        }
        let valid = d.status == "ok";
        let kind = d.kind.unwrap_or(InstructionKind::Stop);
        if valid
            && ((matches!(kind, InstructionKind::Conditional | InstructionKind::Jump)
                && d.target.is_none())
                || (!matches!(
                    kind,
                    InstructionKind::Conditional | InstructionKind::Jump | InstructionKind::Call
                ) && d.target.is_some()))
        {
            return Err(AdapterError::DecoderProtocol(
                "reference target contradicts kind".into(),
            ));
        }
        let next = a
            .checked_add(d.length)
            .ok_or_else(|| AdapterError::DecoderProtocol("reference next VA overflow".into()))?;
        let instruction = if valid {
            Instruction {
                kind,
                fall: if matches!(
                    kind,
                    InstructionKind::Ordinary
                        | InstructionKind::Conditional
                        | InstructionKind::Call
                ) {
                    [next].into()
                } else {
                    BTreeSet::new()
                },
                targets: d.target.into_iter().collect(),
                complete: kind != InstructionKind::Indirect
                    && (kind != InstructionKind::Call || d.target.is_some()),
                uses: options.catalogue.locations(),
                may_defs: options.catalogue.locations(),
                must_defs: BTreeSet::new(),
            }
        } else {
            Instruction::default()
        };
        let operands = decoded_operands(&raw, bytes);
        let decoded_address = if valid {
            super::address_reference::DecodedAddressReference::from_raw(
                &raw,
                &bytes[..d.length as usize],
                decoder_digest.clone(),
                target.triple(),
            )?
        } else {
            None
        };
        let short = d.status == "invalid" && bytes.len() < 15;
        let gaps = if valid {
            Vec::new()
        } else {
            vec![PreparationGap {
                address: a,
                reason: if short {
                    GapReason::MissingBytes
                } else if d.status == "invalid" {
                    GapReason::InvalidEncoding
                } else {
                    GapReason::UnsupportedControl
                },
            }]
        };
        sites.insert(
            a,
            PreparedSite {
                instruction,
                evidence: InstructionEvidence {
                    bytes: bytes[..if d.length == 0 {
                        bytes.len()
                    } else {
                        d.length as usize
                    }]
                        .to_vec(),
                    source: ByteSource::Captured,
                    opcode: (raw.opcode != "-").then_some(raw.opcode),
                    length: d.length as u8,
                    operands,
                    rule: None,
                    control: d.kind,
                    quality: if valid {
                        EffectQuality::Opaque
                    } else {
                        EffectQuality::Unavailable
                    },
                    undefined_flags: BTreeSet::new(),
                    decoder_record: Some(raw.record),
                    decoded_address,
                    decoder_control: d.kind,
                    semantic: None,
                },
                gaps,
                decodable: valid,
                complete_capture: !short,
            },
        );
    }
    if sites.len() != available.len() {
        return Err(AdapterError::DecoderProtocol(
            "reference omitted candidate".into(),
        ));
    }
    for &a in candidates.keys() {
        sites.entry(a).or_insert_with(|| PreparedSite {
            instruction: Instruction::default(),
            evidence: InstructionEvidence {
                bytes: Vec::new(),
                source: ByteSource::Unavailable,
                opcode: None,
                length: 0,
                operands: Vec::new(),
                rule: None,
                control: None,
                quality: EffectQuality::Unavailable,
                undefined_flags: BTreeSet::new(),
                decoder_record: None,
                decoded_address: None,
                decoder_control: None,
                semantic: None,
            },
            gaps: vec![PreparationGap {
                address: a,
                reason: GapReason::MissingBytes,
            }],
            decodable: false,
            complete_capture: false,
        });
    }
    Ok(PreparedBatch {
        sites,
        identity: PreparationIdentity {
            target: target.triple().into(),
            decoder: "LLVM MC 20.1.2 (decode reference)".into(),
            protocol: 2,
            ruleset: "decoded-facts-only-v1".into(),
            catalogue: options.catalogue.identity().into(),
        },
    })
}

// Operand display/binding is a decoded representation, never an effect summary.
fn decoded_operands(raw: &protocol::Raw, bytes: &[u8]) -> Vec<Operand> {
    use protocol::RawOperand as R;
    if ["MOV32mi", "MOV64mi32"].contains(&raw.opcode.as_str()) && raw.operands.len() == 6 {
        let o = &raw.operands;
        let register = |r: &R| match r {
            R::Register(name) => RegisterView::parse(name),
            _ => None,
        };
        if let (R::Immediate(scale), R::Immediate(displacement), R::Immediate(value)) =
            (&o[1], &o[3], &o[5])
        {
            if [1, 2, 4, 8].contains(scale) {
                let width = if raw.opcode == "MOV64mi32" { 64 } else { 32 };
                let mut address_width = 64;
                for byte in bytes {
                    if *byte == 0x67 {
                        address_width = 32;
                    } else if ![0x66, 0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65]
                        .contains(byte)
                        && !(0x40..=0x4f).contains(byte)
                    {
                        break;
                    }
                }
                return vec![
                    Operand::Memory {
                        base: register(&o[0]),
                        index: register(&o[2]),
                        scale: *scale as u8,
                        displacement: *displacement,
                        address_width,
                        access_width: width,
                        next_ip: matches!(&o[0],R::Register(n) if n=="RIP")
                            .then(|| raw.decoded.address + raw.decoded.length),
                    },
                    Operand::Immediate {
                        bits: if width == 32 {
                            *value as u32 as u64
                        } else {
                            *value as i32 as i64 as u64
                        },
                        encoded_width: 32,
                        semantic_width: width,
                        sign_extend: width == 64,
                    },
                ];
            }
        }
    }
    raw.operands
        .iter()
        .filter_map(|o| match o {
            R::Register(n) => RegisterView::parse(n).map(Operand::Register),
            _ => None,
        })
        .collect()
}
