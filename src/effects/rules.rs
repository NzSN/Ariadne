use super::{Catalogue, EffectQuality, Operand, RegisterView, Summary};
use crate::llvm_mc::protocol::{Raw, RawOperand};
use crate::{Address, InstructionKind, LocationSet};

fn reg(raw: &RawOperand, width: u8) -> Option<RegisterView> {
    match raw {
        RawOperand::Register(s) => RegisterView::parse(s).filter(|v| v.width() == width),
        _ => None,
    }
}
fn imm(raw: &RawOperand, encoded: u8, width: u8) -> Option<Operand> {
    let RawOperand::Immediate(value) = raw else {
        return None;
    };
    let sign = encoded < width;
    // LLVM sometimes prints an unsigned immediate and sometimes its signed
    // interpretation. Both must fit the exact encoded bit container.
    if encoded < 64
        && (*value < -(1i64 << (encoded - 1)) || (*value >= 0 && *value as u64 >= 1u64 << encoded))
    {
        return None;
    }
    Some(Operand::Immediate {
        bits: (*value as u64) & (u64::MAX >> (64 - encoded)),
        encoded_width: encoded,
        semantic_width: width,
        sign_extend: sign,
    })
}
fn reads(op: &Operand) -> LocationSet {
    match op {
        Operand::Register(v) => v.reads(),
        Operand::Memory { base, index, .. } => base
            .iter()
            .chain(index.iter())
            .flat_map(RegisterView::reads)
            .collect(),
        _ => LocationSet::new(),
    }
}
fn add_flags(s: &mut Summary, names: &[&str], undefined: &[&str]) {
    for flag in names {
        s.may_defs.insert(format!("flag:{flag}"));
        s.must_defs.insert(format!("flag:{flag}"));
    }
    for flag in undefined {
        s.may_defs.insert(format!("flag:{flag}"));
        s.undefined.insert(format!("flag:{flag}"));
    }
}

// Only one operand-size/address-size prefix, followed by at most one REX.
// REP, LOCK, segment, duplicate/reordered prefixes are deliberately not admitted.
fn prefixes(bytes: &[u8]) -> Option<(u8, bool)> {
    let (mut i, mut operand, mut address) = (0, false, false);
    while let Some(b) = bytes.get(i) {
        match b {
            0x66 if !operand => operand = true,
            0x67 if !address => address = true,
            0x66 | 0x67 => return None,
            _ => break,
        }
        i += 1;
    }
    let rex = bytes.get(i).is_some_and(|b| (0x40..=0x4f).contains(b));
    if rex {
        i += 1;
    }
    if bytes.get(i).is_none_or(|b| {
        matches!(
            b,
            0x26 | 0x2e | 0x36 | 0x3e | 0x64 | 0x65 | 0x66 | 0x67 | 0xf0 | 0xf2 | 0xf3 | 0x40
                ..=0x4f
        )
    }) {
        return None;
    }
    Some((if address { 32 } else { 64 }, rex))
}
fn memory(raw: &[RawOperand], width: u8, address_width: u8, next: Address) -> Option<Operand> {
    let [
        RawOperand::Register(b),
        RawOperand::Immediate(scale),
        RawOperand::Register(i),
        RawOperand::Immediate(displacement),
        RawOperand::Register(segment),
    ] = raw
    else {
        return None;
    };
    if segment != "NONE" || ![1, 2, 4, 8].contains(scale) {
        return None;
    }
    let relative = b == "RIP" || b == "EIP";
    let base = if b == "NONE" || relative {
        None
    } else {
        Some(RegisterView::parse(b).filter(|v| v.width() == address_width)?)
    };
    let index = if i == "NONE" {
        None
    } else {
        Some(RegisterView::parse(i).filter(|v| v.width() == address_width)?)
    };
    if relative && (index.is_some() || (b == "RIP") != (address_width == 64)) {
        return None;
    }
    Some(Operand::Memory {
        base,
        index,
        scale: *scale as u8,
        displacement: *displacement,
        address_width,
        access_width: width,
        next_ip: relative.then_some(next),
    })
}
fn opaque(s: &mut Summary) {
    s.uses = Catalogue.locations();
    s.may_defs = Catalogue.locations();
    s.must_defs.clear();
    s.quality = EffectQuality::Opaque;
}

/// Positive exact opcode/shape matching. No metadata-driven default fallthrough.
pub(crate) fn summarize(raw: &Raw, bytes: &[u8]) -> Option<Summary> {
    if !include_str!("forms.txt")
        .lines()
        .any(|code| code == raw.opcode)
    {
        return None;
    }
    let (address_width, rex) = prefixes(bytes)?;
    if rex
        && raw.operands.iter().any(
            |r| matches!(r,RawOperand::Register(s) if ["AH","BH","CH","DH"].contains(&s.as_str())),
        )
    {
        return None;
    }
    let next = raw.decoded.address.checked_add(raw.decoded.length)?;
    let mut s = Summary {
        rule: format!("effects-v1:{}", raw.opcode),
        operands: Vec::new(),
        kind: InstructionKind::Ordinary,
        uses: LocationSet::new(),
        may_defs: LocationSet::new(),
        must_defs: LocationSet::new(),
        undefined: LocationSet::new(),
        quality: EffectQuality::Reviewed,
    };
    let ops = &raw.operands;
    let code = raw.opcode.as_str();
    for width in [8u8, 16, 32, 64] {
        for operation in [
            "MOV", "ADD", "SUB", "ADC", "SBB", "CMP", "TEST", "AND", "OR", "XOR", "INC", "DEC",
        ] {
            let is_move = operation == "MOV";
            let is_compare = ["CMP", "TEST"].contains(&operation);
            let unary = ["INC", "DEC"].contains(&operation);
            let tied = !is_move && !is_compare;
            let stem = format!("{operation}{width}");
            let Some(suffix) = code.strip_prefix(&stem) else {
                continue;
            };
            let encoded = match suffix {
                "rr" if !unary => None,
                "r" if unary => None,
                "ri" if !unary => Some(if width == 64 && !is_move { 32 } else { width }),
                "ri8" if width > 8 && !is_move && !unary && operation != "TEST" => Some(8),
                "ri32" if width == 64 && !unary => Some(32),
                _ => continue,
            };
            let expected = if unary {
                2
            } else if tied {
                3
            } else {
                2
            };
            if ops.len() != expected {
                return None;
            }
            let dst = reg(&ops[0], width)?;
            if tied && reg(&ops[1], width)? != dst {
                return None;
            }
            s.operands.push(Operand::Register(dst.clone()));
            if !is_move {
                s.uses.extend(dst.reads());
            }
            if !unary {
                let source = ops.last()?;
                let source = if let Some(bits) = encoded {
                    imm(source, bits, width)?
                } else {
                    Operand::Register(reg(source, width)?)
                };
                s.uses.extend(reads(&source));
                s.operands.push(source);
            }
            if !is_compare {
                s.may_defs = dst.replacements();
                s.must_defs = s.may_defs.clone();
            }
            if ["ADC", "SBB"].contains(&operation) {
                s.uses.insert("flag:cf".into());
            }
            if ["AND", "OR", "XOR", "TEST"].contains(&operation) {
                add_flags(&mut s, &["cf", "of", "sf", "zf", "pf"], &["af"]);
            } else if unary {
                add_flags(&mut s, &["of", "sf", "zf", "af", "pf"], &[]);
            } else if !is_move {
                add_flags(&mut s, &["cf", "of", "sf", "zf", "af", "pf"], &[]);
            }
            return Some(s);
        }
        let load = code == format!("MOV{width}rm");
        let store = code == format!("MOV{width}mr");
        let lea = (width != 8 && code == format!("LEA{width}r"))
            || (width == 32 && address_width == 64 && code == "LEA64_32r");
        if load || store || lea {
            if ops.len() != 6 {
                return None;
            }
            let v = reg(&ops[if store { 5 } else { 0 }], width)?;
            let m = memory(
                &ops[if store { 0..5 } else { 1..6 }],
                width,
                address_width,
                next,
            )?;
            s.uses.extend(reads(&m));
            if store {
                s.uses.extend(v.reads());
                s.may_defs.insert("memory:any".into());
                s.operands = vec![m, Operand::Register(v)];
            } else {
                if load {
                    s.uses.insert("memory:any".into());
                }
                s.may_defs = v.replacements();
                s.must_defs = s.may_defs.clone();
                s.operands = vec![Operand::Register(v), m];
            }
            return Some(s);
        }
    }
    match code {
        "JCC_1" | "JCC_4" | "JMP_1" | "JMP_4" | "CALL64pcrel32" => {
            let conditional = code.starts_with("JCC");
            if ops.len() != if conditional { 2 } else { 1 } {
                return None;
            }
            let RawOperand::Immediate(displacement) = ops[0] else {
                return None;
            };
            let encoded = if code.ends_with("_1") { 8 } else { 32 };
            imm(&ops[0], encoded, 64)?;
            let target = next.wrapping_add_signed(displacement);
            if raw.decoded.target != Some(target) {
                return None;
            }
            s.operands.push(Operand::Relative {
                displacement,
                target,
                encoded_width: encoded,
            });
            s.kind = if conditional {
                InstructionKind::Conditional
            } else if code.starts_with("CALL") {
                InstructionKind::Call
            } else {
                InstructionKind::Jump
            };
            if conditional {
                let RawOperand::Immediate(condition) = ops[1] else {
                    return None;
                };
                let flags: &[&str] = match condition {
                    0 | 1 => &["of"],
                    2 | 3 => &["cf"],
                    4 | 5 => &["zf"],
                    6 | 7 => &["cf", "zf"],
                    8 | 9 => &["sf"],
                    10 | 11 => &["pf"],
                    12 | 13 => &["sf", "of"],
                    14 | 15 => &["zf", "sf", "of"],
                    _ => return None,
                };
                s.operands.push(Operand::Condition(condition as u8));
                s.uses.extend(flags.iter().map(|f| format!("flag:{f}")));
            }
        }
        "CALL64r" | "JMP64r" => {
            if ops.len() != 1 {
                return None;
            }
            let v = reg(&ops[0], 64)?;
            s.uses = v.reads();
            s.operands.push(Operand::Register(v));
            s.kind = if code == "CALL64r" {
                InstructionKind::Call
            } else {
                InstructionKind::Indirect
            };
        }
        "CALL64m" | "JMP64m" => {
            let m = memory(ops, 64, address_width, next)?;
            s.uses = reads(&m);
            s.uses.insert("memory:any".into());
            s.operands.push(m);
            s.kind = if code == "CALL64m" {
                InstructionKind::Call
            } else {
                InstructionKind::Indirect
            };
        }
        "RET64" if ops.is_empty() => {
            s.kind = InstructionKind::Return;
            opaque(&mut s);
        }
        "NOOP" if ops.is_empty() => {}
        "CLC" | "STC" if ops.is_empty() => {
            opaque(&mut s);
        }
        _ => return None,
    }
    if s.kind == InstructionKind::Call {
        opaque(&mut s);
    }
    Some(s)
}
