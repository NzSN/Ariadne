//! The finite vector namespace of the pinned AMD64 BAP producer.
use super::ast::Var;

/// XMM is the low half of the canonical 256-bit YMM backing register.
/// ZMM, opmask, noncanonical spellings and extended register banks are excluded.
pub(crate) fn vector_backing(var: &Var) -> Option<Var> {
    if var.virtual_ || var.index != 0 || var.type_ != "imm" {
        return None;
    }
    let (number, width) = if let Some(number) = var.name.strip_prefix("XMM") {
        (number, 128)
    } else {
        (var.name.strip_prefix("YMM")?, 256)
    };
    let bank: u8 = number.parse().ok()?;
    if bank >= 16 || number != bank.to_string() || var.width != width {
        return None;
    }
    Some(Var {
        name: format!("YMM{bank}"),
        index: 0,
        virtual_: false,
        width: 256,
        type_: "imm".into(),
    })
}
