//! Strict I5b encoding and evidence-preserving presentation.
use super::{Error, Format, strict_json};
use crate::investigation::{ZeroBaseOffsetAssessment, ZeroBaseOffsetEvidenceData};
use std::fmt::Write;

pub fn encode_zero_base_offset(
    value: &ZeroBaseOffsetAssessment,
) -> Result<serde_json::Value, Error> {
    value.validate()?;
    Ok(serde_json::to_value(value)?)
}
pub fn decode_zero_base_offset(bytes: &[u8]) -> Result<ZeroBaseOffsetAssessment, Error> {
    let result: ZeroBaseOffsetAssessment = serde_json::from_value(strict_json(bytes)?)?;
    result.validate()?;
    Ok(result)
}
pub fn render_zero_base_offset(
    value: &ZeroBaseOffsetAssessment,
    format: Format,
) -> Result<String, Error> {
    value.validate()?;
    if matches!(format, Format::Json) {
        return Ok(format!("{}\n", serde_json::to_string_pretty(value)?));
    }
    let mut out = String::new();
    if matches!(format, Format::Dot) {
        writeln!(
            out,
            "// zero_base_offset_assessment: {}",
            serde_json::to_string(value)?
        )
        .unwrap();
        writeln!(
            out,
            "digraph ZeroBaseOffset {{\n  label={};",
            serde_json::to_string(&format!(
                "Zero base plus nonzero displacement: {:?}; conditional on captured context",
                value.conclusion
            ))?
        )
        .unwrap();
        for evidence in &value.evidence {
            writeln!(
                out,
                "  {} [label={}];",
                serde_json::to_string(&evidence.id)?,
                serde_json::to_string(&format!("{:?}", evidence.data))?
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
            for reference in &claim.evidence_refs {
                writeln!(
                    out,
                    "  {} -> {};",
                    serde_json::to_string(reference)?,
                    serde_json::to_string(&claim.id)?
                )
                .unwrap();
            }
        }
        writeln!(out, "}}").unwrap();
    } else {
        writeln!(
            out,
            "Ariadne zero-base-plus-displacement assessment ({})",
            value.schema
        )
        .unwrap();
        writeln!(
            out,
            "snapshot: {}\nquery: {}\nscope: {}",
            value.identity.snapshot_id, value.identity.query_id, value.scope_id
        )
        .unwrap();
        writeln!(
            out,
            "question: 0x{:016x} memory access {}",
            value.question.site, value.question.memory_access
        )
        .unwrap();
        writeln!(out, "conclusion: {:?}", value.conclusion).unwrap();
        for e in &value.evidence {
            match &e.data {
                ZeroBaseOffsetEvidenceData::Instruction { instruction, .. } => {
                    writeln!(
                        out,
                        "instruction: {}\nbytes: {}",
                        instruction.opcode.as_deref().unwrap_or("unknown"),
                        instruction.bytes_hex
                    )
                    .unwrap();
                }
                ZeroBaseOffsetEvidenceData::DecodedAddress { receipt } => {
                    writeln!(out,"decoded address: base={}, index={}, scale={}, signed displacement={:+}; access={} bits",
                        receipt.base.as_deref().unwrap_or("none"),receipt.index.as_deref().unwrap_or("none"),
                        receipt.scale,receipt.displacement,receipt.access_width).unwrap();
                }
                _ => {}
            }
        }
        if let (Some(base), Some(observation)) = (&value.base_register, &value.base_value) {
            writeln!(
                out,
                "captured base: {} = 0x{:016x}",
                base.to_uppercase(),
                observation.value
            )
            .unwrap();
        }
        if let Some(displacement) = value.signed_displacement {
            writeln!(out, "admitted displacement: {displacement:+}").unwrap();
        }
        if let Some(address) = &value.evaluated_address {
            writeln!(out, "effective address: 0x{:016x}", address.value).unwrap();
        }
        if let Some(address) = &value.reported_data_address {
            writeln!(out, "reported inaccessible byte: 0x{:016x}", address.value).unwrap();
        }
        for premise in &value.premises {
            writeln!(out, "premise: {premise}").unwrap();
        }
        for evidence in &value.evidence {
            writeln!(out, "evidence {}: {:?}", evidence.id, evidence.data).unwrap();
        }
        for claim in &value.claims {
            writeln!(
                out,
                "claim {}: {:?} {:?}; evidence {:?}",
                claim.id, claim.classification, claim.assertion, claim.evidence_refs
            )
            .unwrap();
        }
        for (gap, requirement) in value.gaps.iter().zip(&value.evidence_requirements) {
            writeln!(out, "gap: {gap}\nrequires: {requirement}").unwrap();
        }
        writeln!(out, "truncated: {}", value.truncated).unwrap();
    }
    Ok(out)
}
