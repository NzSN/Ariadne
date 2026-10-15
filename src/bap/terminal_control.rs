//! Narrow captured exception exits in the explicit local-normal-flow scope.
//! This certificate selects no scalar, vector or memory effects and says nothing
//! about exception-handler or debugger resumption.
use super::ast::{Lift, Properties, Stmt};
use super::guard_admission::{CandidateSite, ControlKind};
use super::{Error, invalid};
use serde::{Deserialize, Serialize};

pub const SCOPE: &str = "local-normal-completion/v1";
pub const RULE: &str = "captured-normal-terminal/v1";
pub const STATUS: &str = "normal-flow-terminal";
pub const EXIT: &str = "exception-exit";
pub const RESUMPTION: &str = "exception-resumption-outside-local-scope";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NormalFlowKind {
    LocalNormalCompletion,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NormalFlowEvidence {
    pub kind: NormalFlowKind,
    pub scope: String,
    pub terminals: Vec<TerminalReceipt>,
}
impl NormalFlowEvidence {
    pub fn empty() -> Self {
        Self {
            kind: NormalFlowKind::LocalNormalCompletion,
            scope: SCOPE.into(),
            terminals: Vec::new(),
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TerminalProperties {
    pub jump: bool,
    pub conditional: bool,
    pub indirect: bool,
    pub call: bool,
    #[serde(rename = "return")]
    pub return_: bool,
    pub control: bool,
}
impl From<&Properties> for TerminalProperties {
    fn from(p: &Properties) -> Self {
        Self {
            jump: p.jump,
            conditional: p.conditional,
            indirect: p.indirect,
            call: p.call,
            return_: p.return_,
            control: p.control,
        }
    }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TerminalBap {
    pub status: String,
    pub length: u8,
    pub bytes_hex: String,
    pub opcode: String,
    pub properties: TerminalProperties,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TerminalReference {
    pub length: u8,
    pub opcode: String,
    pub control: String,
    pub decoder_record: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TerminalReceipt {
    pub schema: String,
    pub rule: String,
    pub site: String,
    pub bytes_hex: String,
    pub ast_sha256: String,
    pub exception: u8,
    pub annotation: String,
    pub resumption: String,
    pub bap: TerminalBap,
    pub reference: TerminalReference,
}
fn address(value: &str) -> Result<u64, Error> {
    let n = value
        .strip_prefix("0x")
        .and_then(|s| u64::from_str_radix(s, 16).ok())
        .ok_or_else(|| invalid("terminal address"))?;
    if format!("0x{n:016x}") != value {
        return Err(invalid("noncanonical terminal address"));
    }
    Ok(n)
}
fn bytes(value: &str) -> Result<Vec<u8>, Error> {
    if value.is_empty()
        || value.len() > 30
        || value.len() % 2 != 0
        || !value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err(invalid("terminal captured byte encoding"));
    }
    (0..value.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&value[i..i + 2], 16).map_err(|_| invalid("terminal captured bytes"))
        })
        .collect()
}
/// Complete reviewed UD1 /r extent, optionally with exactly one address-size
/// prefix. Operand decoding contributes no register or memory semantics.
fn ud1_extent(b: &[u8]) -> Option<usize> {
    let prefix = usize::from(b.first() == Some(&0x67));
    if b.get(prefix..prefix + 2)? != [0x0f, 0xb9] {
        return None;
    }
    let m = *b.get(prefix + 2)?;
    let mode = m >> 6;
    let rm = m & 7;
    let mut n = prefix + 3;
    if mode != 3 && rm == 4 {
        let sib = *b.get(n)?;
        n += 1;
        if mode == 0 && sib & 7 == 5 {
            n += 4;
        }
    } else if mode == 0 && rm == 5 {
        n += 4;
    }
    n += match mode {
        1 => 1,
        2 => 4,
        _ => 0,
    };
    (b.len() == n).then_some(n)
}
fn all_false(p: &TerminalProperties) -> bool {
    !p.jump && !p.conditional && !p.indirect && !p.call && !p.return_ && !p.control
}
fn source_rule(receipt: &TerminalReceipt, ast: &str) -> Result<(), Error> {
    if receipt.schema != "ariadne.normal-terminal/v1"
        || receipt.annotation != EXIT
        || receipt.resumption != RESUMPTION
    {
        return Err(invalid("terminal rule scope or exception annotation"));
    }
    let site = address(&receipt.site)?;
    let b = bytes(&receipt.bytes_hex)?;
    if receipt.ast_sha256 != crate::reports::sha256(ast.as_bytes())
        || receipt.bap.status != "decoded"
        || !all_false(&receipt.bap.properties)
    {
        return Err(invalid("terminal original BAP source"));
    }
    let bil: Vec<Stmt> = serde_json::from_value(crate::reports::strict_json(ast.as_bytes())?)?;
    let consumed = bytes(&receipt.bap.bytes_hex)?;
    if consumed.len() != usize::from(receipt.bap.length) {
        return Err(invalid("terminal BAP consumed extent"));
    }
    let reference = crate::llvm_mc::protocol::parse(&receipt.reference.decoder_record)?;
    if reference.decoded.address != site
        || reference.decoded.status != "ok"
        || reference.decoded.kind != Some(crate::InstructionKind::Stop)
        || reference.decoded.target.is_some()
        || reference.decoded.length != b.len() as u64
        || usize::from(receipt.reference.length) != b.len()
        || receipt.reference.opcode != reference.opcode
        || receipt.reference.control != "stop"
    {
        return Err(invalid("terminal independent reference facts"));
    }
    match receipt.rule.as_str() {
        "int3-exception/v1"
            if b == [0xcc]
                && consumed == b
                && receipt.bap.opcode == "INT3"
                && receipt.reference.opcode == "INT3"
                && receipt.exception == 3
                && matches!(bil.as_slice(), [Stmt::Exception { number: 3 }]) => {}
        "ud2-empty-lift/v1"
            if b == [0x0f, 0x0b]
                && consumed == b
                && receipt.bap.opcode == "TRAP"
                && receipt.reference.opcode == "TRAP"
                && receipt.exception == 6
                && bil.is_empty() => {}
        "ud1-pinned-extent/v1"
            if ud1_extent(&b).is_some()
                && receipt.bap.opcode == "UD2B"
                && receipt.exception == 6
                && bil.is_empty() =>
        {
            let prefix = usize::from(b[0] == 0x67);
            let opcode_extent = prefix + 2;
            let expected_reference = if b[prefix + 2] >> 6 == 3 {
                "UD1Lr"
            } else {
                "UD1Lm"
            };
            if consumed != b[..opcode_extent] || receipt.reference.opcode != expected_reference {
                return Err(invalid("terminal pinned UD1 extent disagreement"));
            }
        }
        _ => return Err(invalid("unrecognized terminal source rule")),
    }
    Ok(())
}
pub(crate) fn recognize(
    site: u64,
    full_bytes: &[u8],
    ast: &str,
    lift: &Lift,
    decoder_record: &str,
) -> Result<Option<TerminalReceipt>, Error> {
    let reference = crate::llvm_mc::protocol::parse(decoder_record)?;
    if reference.decoded.kind != Some(crate::InstructionKind::Stop)
        || reference.decoded.status != "ok"
    {
        return Ok(None);
    }
    let (rule, exception) = if full_bytes == [0xcc] {
        ("int3-exception/v1", 3)
    } else if full_bytes == [0x0f, 0x0b] {
        ("ud2-empty-lift/v1", 6)
    } else if ud1_extent(full_bytes).is_some() {
        ("ud1-pinned-extent/v1", 6)
    } else {
        return Ok(None);
    };
    let Some(properties) = lift.properties.as_ref() else {
        return Ok(None);
    };
    let receipt = TerminalReceipt {
        schema: "ariadne.normal-terminal/v1".into(),
        rule: rule.into(),
        site: format!("0x{site:016x}"),
        bytes_hex: full_bytes.iter().map(|b| format!("{b:02x}")).collect(),
        ast_sha256: crate::reports::sha256(ast.as_bytes()),
        exception,
        annotation: EXIT.into(),
        resumption: RESUMPTION.into(),
        bap: TerminalBap {
            status: lift.status.clone(),
            length: lift.length,
            bytes_hex: lift.bytes.clone(),
            opcode: lift.opcode.clone().unwrap_or_default(),
            properties: properties.into(),
        },
        reference: TerminalReference {
            length: u8::try_from(reference.decoded.length)
                .map_err(|_| invalid("terminal reference extent"))?,
            opcode: reference.opcode,
            control: "stop".into(),
            decoder_record: decoder_record.into(),
        },
    };
    match source_rule(&receipt, ast) {
        Ok(()) => Ok(Some(receipt)),
        Err(_) => Ok(None),
    }
}
pub fn validate_source(site: &CandidateSite, receipt: &TerminalReceipt) -> Result<(), Error> {
    if site.site != receipt.site
        || site.bytes_hex != receipt.bytes_hex
        || site.control.kind != ControlKind::Stop
        || !site.control.complete
        || !site.control.fall.is_empty()
        || !site.control.targets.is_empty()
        || !site.opaque
    {
        return Err(invalid(
            "terminal candidate has a normal successor or unsupported effects",
        ));
    }
    source_rule(receipt, &site.ast)
}
pub fn validate_capture(receipt: &TerminalReceipt, prefix: &[u8]) -> Result<(), Error> {
    let captured = bytes(&receipt.bytes_hex)?;
    if !prefix.starts_with(&captured) {
        return Err(invalid("terminal full captured span mismatch"));
    }
    Ok(())
}
#[cfg(test)]
#[path = "../../tests/bap/terminal_control_unit.rs"]
mod tests;
