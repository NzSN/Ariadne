//! The finite decoded-role checks shared by the two scalar MOV questions.
use super::AddressUse;
use super::fault_context::GPRS;
use crate::llvm_mc::address_reference::{DecodedAddressReference, gpr_bank};

pub(super) struct ScalarBaseDisplacementFacts {
    pub bank: u8,
    pub register: &'static str,
    pub displacement: i64,
}

/// Keep the historical I5b failure precedence and gap strings intact.
pub(super) fn scalar_base_displacement(
    receipt: Option<&DecodedAddressReference>,
    access: Option<&AddressUse>,
) -> Result<ScalarBaseDisplacementFacts, &'static str> {
    let r = receipt.ok_or("missing-decoded-address-reference")?;
    let bank = r
        .base
        .as_deref()
        .and_then(gpr_bank)
        .ok_or("unsupported-encoded-base")?;
    if r.index.is_some()
        || r.segment.is_some()
        || r.rip_relative
        || r.address_width != 64
        || !r.gaps.is_empty()
        || r.decoder_sha256.is_none()
        || r.target != "x86_64-pc-windows-msvc"
    {
        return Err("unsupported-decoded-address-profile");
    }
    if access.is_none_or(|a| {
        a.access_width != u16::from(r.access_width)
            || a.address_width != u16::from(r.address_width)
            || a.expression.as_ref().is_none_or(|x| {
                x.width != 64
                    || x.terms.len() != 1
                    || x.terms[0].bank != bank
                    || x.terms[0].coefficient != 1
                    || x.constant != r.displacement as u64
            })
    }) {
        return Err("decoded-bil-address-disagreement");
    }
    Ok(ScalarBaseDisplacementFacts {
        bank,
        register: GPRS[bank as usize],
        displacement: r.displacement,
    })
}
