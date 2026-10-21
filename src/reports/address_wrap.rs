//! Strict I5c encoding and evidence-preserving presentation.
use super::{Error, Format, strict_json};
use crate::investigation::{AddressWrapAssessment, AddressWrapEvidenceData};
use std::fmt::Write;

pub fn encode_address_wrap(value: &AddressWrapAssessment) -> Result<serde_json::Value, Error> {
    value.validate()?;
    Ok(serde_json::to_value(value)?)
}

pub fn decode_address_wrap(bytes: &[u8]) -> Result<AddressWrapAssessment, Error> {
    let value: AddressWrapAssessment = serde_json::from_value(strict_json(bytes)?)?;
    value.validate()?;
    Ok(value)
}

pub fn render_address_wrap(value: &AddressWrapAssessment, format: Format) -> Result<String, Error> {
    value.validate()?;
    if matches!(format, Format::Json) {
        return Ok(format!("{}\n", serde_json::to_string_pretty(value)?));
    }
    let mut out = String::new();
    if matches!(format, Format::Dot) {
        writeln!(
            out,
            "// address_wrap_assessment: {}",
            serde_json::to_string(value)?
        )
        .unwrap();
        writeln!(
            out,
            "digraph AddressWrap {{\n  label={};",
            serde_json::to_string(&format!(
                "Address-wrap assessment: {:?}; conditional on captured context",
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
        return Ok(out);
    }
    writeln!(out, "Ariadne address-wrap assessment ({})", value.schema).unwrap();
    writeln!(out, "conclusion: {:?}", value.conclusion).unwrap();
    // Unknown and every reason/premise requirement precede conditional math.
    for gap in &value.gaps {
        writeln!(out, "gap: {gap}").unwrap();
    }
    for requirement in &value.evidence_requirements {
        writeln!(out, "requires: {requirement}").unwrap();
    }
    writeln!(
        out,
        "snapshot: {}\nquery: {}\nscope: {}\ncontent: {}",
        value.identity.snapshot_id, value.identity.query_id, value.scope_id, value.content_id
    )
    .unwrap();
    writeln!(
        out,
        "question: 0x{:016x} memory access {}",
        value.question.site, value.question.memory_access
    )
    .unwrap();
    writeln!(
        out,
        "inputs complete: {}; evidence retained: {} of {}",
        value.inputs_complete,
        value.evidence.len(),
        value.input_evidence_count
    )
    .unwrap();
    writeln!(
        out,
        "limits: {} evidence, {} claims; truncated: {}",
        value.limits.max_evidence, value.limits.max_claims, value.truncated
    )
    .unwrap();
    for evidence in &value.evidence {
        if let AddressWrapEvidenceData::Instruction { instruction, .. } = &evidence.data {
            writeln!(
                out,
                "instruction: {}\nbytes: {}",
                instruction.opcode.as_deref().unwrap_or("unknown"),
                instruction.bytes_hex
            )
            .unwrap();
        }
    }
    if let Some(reported) = &value.reported_data_address {
        writeln!(out, "reported inaccessible byte: 0x{:016x}", reported.value).unwrap();
    }
    if let Some(arithmetic) = &value.arithmetic {
        writeln!(out, "conditional arithmetic under the declared premises:").unwrap();
        writeln!(
            out,
            "  captured base: {} = 0x{:016x}",
            arithmetic.base_register.to_uppercase(),
            arithmetic.base_value.value
        )
        .unwrap();
        writeln!(
            out,
            "  signed encoded displacement: {:+}; bit pattern: 0x{:016x}",
            arithmetic.signed_displacement, arithmetic.displacement_bits.value
        )
        .unwrap();
        writeln!(
            out,
            "  wide sum before reduction: {}",
            arithmetic.sum_before_reduction
        )
        .unwrap();
        writeln!(out, "  wrap kind: {:?}", arithmetic.wrap_kind).unwrap();
        writeln!(
            out,
            "  effective address: 0x{:016x}",
            arithmetic.effective_address.value
        )
        .unwrap();
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
    Ok(out)
}
