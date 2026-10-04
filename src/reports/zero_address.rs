//! Independent zero-address assessment encoding and pure presentation.
use super::{Error, Format, strict_json};
use crate::investigation::{FaultDatum, ZeroAddressAssessment, ZeroAddressEvidenceData};
use std::fmt::Write;

pub fn encode_zero_address(value: &ZeroAddressAssessment) -> Result<serde_json::Value, Error> {
    value.validate()?;
    Ok(serde_json::to_value(value)?)
}
pub fn decode_zero_address(bytes: &[u8]) -> Result<ZeroAddressAssessment, Error> {
    let result: ZeroAddressAssessment = serde_json::from_value(strict_json(bytes)?)?;
    result.validate()?;
    Ok(result)
}
pub fn render_zero_address(value: &ZeroAddressAssessment, format: Format) -> Result<String, Error> {
    value.validate()?;
    if matches!(format, Format::Json) {
        return Ok(format!("{}\n", serde_json::to_string_pretty(value)?));
    }
    let mut out = String::new();
    if matches!(format, Format::Dot) {
        writeln!(
            out,
            "// zero_address_assessment: {}",
            serde_json::to_string(value)?
        )
        .unwrap();
        writeln!(
            out,
            "digraph ZeroAddress {{\n  label={};",
            serde_json::to_string(&format!(
                "Access starts at zero: {:?}; conditional on captured context",
                value.conclusion
            ))?
        )
        .unwrap();
        for e in &value.evidence {
            let label = match &e.data {
                ZeroAddressEvidenceData::Instruction { instruction, .. } => format!(
                    "Captured bytes at 0x{:016x}: {}",
                    instruction.va, instruction.bytes_hex
                ),
                ZeroAddressEvidenceData::Fault {
                    datum: FaultDatum::Field { observation },
                } => format!("{} = 0x{:016x}", observation.name, observation.value),
                ZeroAddressEvidenceData::Fault {
                    datum: FaultDatum::Record { .. },
                } => "Exception record extent".into(),
                ZeroAddressEvidenceData::Fault {
                    datum: FaultDatum::Context { .. },
                } => "Exception context extent".into(),
            };
            writeln!(
                out,
                "  {} [label={}];",
                serde_json::to_string(&e.id)?,
                serde_json::to_string(&label)?
            )
            .unwrap();
        }
        for claim in &value.claims {
            writeln!(
                out,
                "  {} [shape=box,label={}];",
                serde_json::to_string(&claim.id)?,
                serde_json::to_string(&format!(
                    "{:?}: {:?}",
                    claim.classification, claim.assertion
                ))?
            )
            .unwrap();
            for e in &claim.evidence_refs {
                writeln!(
                    out,
                    "  {} -> {};",
                    serde_json::to_string(e)?,
                    serde_json::to_string(&claim.id)?
                )
                .unwrap();
            }
        }
        writeln!(out, "}}").unwrap();
        return Ok(out);
    }
    writeln!(out, "Ariadne zero-address assessment ({})", value.schema).unwrap();
    writeln!(out,"Question: does the selected access begin at virtual address zero?\nSnapshot: {}\nQuery: {}\nInstruction: 0x{:016x}; access: {}\nConclusion: {:?}\nProfile: {}\nTruncated: {}",value.identity.snapshot_id,value.identity.query_id,value.question.site,value.question.memory_access,value.conclusion,value.profile,value.truncated).unwrap();
    if let Some(v) = &value.evaluated_address {
        writeln!(out, "Computed address under premises: 0x{:016x}", v.value).unwrap();
    }
    if let Some(v) = &value.reported_data_address {
        writeln!(out, "Reported inaccessible data: 0x{:016x}", v.value).unwrap();
    }
    writeln!(
        out,
        "Required address registers: {}",
        value.used_registers.join(", ")
    )
    .unwrap();
    for e in &value.evidence {
        match &e.data {
            ZeroAddressEvidenceData::Instruction { instruction, .. } => writeln!(
                out,
                "Instruction evidence {}: 0x{:016x} {} accesses={:?}",
                e.id, instruction.va, instruction.bytes_hex, instruction.accesses
            )
            .unwrap(),
            ZeroAddressEvidenceData::Fault {
                datum: FaultDatum::Field { observation },
            } => writeln!(
                out,
                "Observed {} = 0x{:016x}; file offset=0x{:016x}, bytes={}, evidence={}",
                observation.name,
                observation.value,
                observation.source.file_offset,
                observation.bytes_hex,
                e.id
            )
            .unwrap(),
            ZeroAddressEvidenceData::Fault {
                datum: FaultDatum::Record { span } | FaultDatum::Context { span },
            } => writeln!(
                out,
                "Extent evidence {}: offset=0x{:016x}, length={}, sha256={}",
                e.id, span.file_offset, span.length, span.sha256
            )
            .unwrap(),
        }
    }
    for claim in &value.claims {
        writeln!(
            out,
            "Claim {}: {:?} {:?}; evidence={:?}",
            claim.id, claim.classification, claim.assertion, claim.evidence_refs
        )
        .unwrap();
    }
    for premise in &value.premises {
        writeln!(out, "Premise: {premise}").unwrap();
    }
    for (gap, requirement) in value.gaps.iter().zip(&value.evidence_requirements) {
        writeln!(out, "Gap: {gap}\nRequired evidence: {requirement}").unwrap();
    }
    writeln!(out,"A zero address does not identify a null base, object lifetime, historical path or root cause.").unwrap();
    Ok(out)
}
