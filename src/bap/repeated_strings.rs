//! Finite, explicitly selected byte-string REP projection contract.
//!
//! v12 retains its three byte forms. v13 adds only reviewed default-address
//! memory forms with actual, nonempty producer BIL. v14 adds its separate LODS
//! producer; v15 adds canonical address-32 forms under an explicit AMD premise.
//! Each has an independent numeric oracle. No profile grants generic prefix,
//! proof-consumer or partial-fault permission.

pub(crate) const PROFILE: &str = "bap-bit-provenance-v12";
pub(crate) const PROFILE13: &str = "bap-bit-provenance-v13";
pub(crate) const PROFILE14: &str = "bap-bit-provenance-v14";
pub(crate) const PROFILE15: &str = "bap-bit-provenance-v15";

pub(crate) fn is_profile(profile: &str) -> bool {
    matches!(profile, PROFILE | PROFILE13 | PROFILE14 | PROFILE15)
}

pub(crate) fn opcode(bytes: &[u8], profile: &str) -> Option<&'static str> {
    if !is_profile(profile) {
        return None;
    }
    if profile == PROFILE15 && bytes.first() == Some(&0x67) {
        return opcode(&bytes[1..], PROFILE14);
    }
    let legacy = match bytes {
        [0xf3, 0xa4] => Some("MOVSB"),
        [0xf3, 0xaa] => Some("STOSB"),
        [0xf3, 0xa6] => Some("CMPSB"),
        _ => None,
    };
    if legacy.is_some() || profile == PROFILE {
        return legacy;
    }
    if matches!(profile, PROFILE14 | PROFILE15) {
        match bytes {
            [0xf3, 0xac] => return Some("LODSB"),
            [0x66, 0xf3, 0xad] => return Some("LODSW"),
            [0xf3, 0xad] => return Some("LODSL"),
            [0xf3, 0x48, 0xad] => return Some("LODSQ"),
            _ => {}
        }
    }
    // Exact reviewed prefix order only: 66 before F2/F3, REX.W after it.
    // BAP names the 32-bit string forms with L, not the ambiguous D suffix.
    // LODS is intentionally absent: the pinned producer returns empty BIL.
    match bytes {
        [0x66, 0xf3, 0xa5] => Some("MOVSW"),
        [0xf3, 0xa5] => Some("MOVSL"),
        [0xf3, 0x48, 0xa5] => Some("MOVSQ"),
        [0x66, 0xf3, 0xab] => Some("STOSW"),
        [0xf3, 0xab] => Some("STOSL"),
        [0xf3, 0x48, 0xab] => Some("STOSQ"),
        [0x66, 0xf3, 0xa7] | [0x66, 0xf2, 0xa7] => Some("CMPSW"),
        [0xf3, 0xa7] | [0xf2, 0xa7] => Some("CMPSL"),
        [0xf3, 0x48, 0xa7] | [0xf2, 0x48, 0xa7] => Some("CMPSQ"),
        [0xf2, 0xa6] => Some("CMPSB"),
        [0xf3, 0xae] | [0xf2, 0xae] => Some("SCASB"),
        [0x66, 0xf3, 0xaf] | [0x66, 0xf2, 0xaf] => Some("SCASW"),
        [0xf3, 0xaf] | [0xf2, 0xaf] => Some("SCASL"),
        [0xf3, 0x48, 0xaf] | [0xf2, 0x48, 0xaf] => Some("SCASQ"),
        _ => None,
    }
}
