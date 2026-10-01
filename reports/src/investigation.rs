//! Strict, independently versioned fault-address explanation reporting.
use crate::{Error, Format, strict_json};
use ariadne_investigation::{Assertion, Explanation, OriginKind};
use std::fmt::Write;
pub fn encode_explanation(e: &Explanation) -> Result<serde_json::Value, Error> {
    e.validate()?;
    Ok(serde_json::to_value(e)?)
}
pub fn decode_explanation(bytes: &[u8]) -> Result<Explanation, Error> {
    let e: Explanation = serde_json::from_value(strict_json(bytes)?)?;
    e.validate()?;
    Ok(e)
}
pub fn render_explanation(e: &Explanation, format: Format) -> Result<String, Error> {
    e.validate()?;
    if matches!(format, Format::Json) {
        return Ok(format!("{}\n", serde_json::to_string_pretty(e)?));
    }
    let mut out = String::new();
    if matches!(format, Format::Dot) {
        writeln!(out, "// explanation: {}", serde_json::to_string(e)?).unwrap();
        writeln!(out, "digraph Investigation {{").unwrap();
        writeln!(
            out,
            "  label={};",
            serde_json::to_string(&format!(
                "Fault-address explanation: {:?}; possible dependencies only",
                e.status
            ))?
        )
        .unwrap();
        for record in &e.evidence {
            writeln!(
                out,
                "  {} [label={}];",
                serde_json::to_string(&record.id)?,
                serde_json::to_string(&format!(
                    "0x{:016x} {}",
                    record.instruction.va,
                    record.instruction.opcode.as_deref().unwrap_or("?")
                ))?
            )
            .unwrap();
        }
        for fact in &e.facts {
            writeln!(
                out,
                "  {} [shape=box,label={}];",
                serde_json::to_string(&fact.id)?,
                serde_json::to_string(&format!("{:?}", fact.assertion))?
            )
            .unwrap();
            for r in &fact.evidence_refs {
                writeln!(
                    out,
                    "  {} -> {};",
                    serde_json::to_string(r)?,
                    serde_json::to_string(&fact.id)?
                )
                .unwrap();
            }
        }
        writeln!(out, "}}").unwrap();
        return Ok(out);
    }
    writeln!(out, "Ariadne fault-address explanation ({})", e.schema).unwrap();
    writeln!(out,"Snapshot: {}\nArtifact: {}\nQuery: {}\nStatus: {:?}\nInstruction: 0x{:016x}; memory access: {}",e.identity.snapshot_id,e.identity.artifact_sha256,e.identity.query_id,e.status,e.question.site,e.question.memory_access).unwrap();
    if let Some(a) = &e.address {
        writeln!(
            out,
            "Address expression (modular {}-bit): {:?}",
            a.address_width, a.expression
        )
        .unwrap();
        writeln!(out, "Address inputs: {}", a.address_inputs.join(", ")).unwrap();
    }
    for group in &e.origins {
        writeln!(out, "Possible origins for {}:", group.location).unwrap();
        for p in &group.producers {
            writeln!(
                out,
                "  {} 0x{:016x}; evidence={}",
                match p.origin {
                    OriginKind::Entry => "entry",
                    OriginKind::Instruction => "instruction",
                },
                p.site,
                p.evidence_id.as_deref().unwrap_or("none")
            )
            .unwrap();
        }
    }
    for record in &e.evidence {
        writeln!(
            out,
            "Evidence {}: 0x{:016x} {} {} spans={:?}",
            record.id,
            record.instruction.va,
            record.instruction.bytes_hex,
            record.instruction.opcode.as_deref().unwrap_or("?"),
            record.instruction.spans
        )
        .unwrap();
    }
    for claim in &e.claims {
        let wording = match &claim.assertion {
            Assertion::CapturedInstruction { .. } => "captured instruction bytes",
            Assertion::AddressInputs { .. } => "address-input fact under admitted semantics",
            Assertion::PossibleOrigin { .. } => "possible producer; not an execution witness",
            Assertion::Dependency { .. } => "dependency under local graph/effects",
            Assertion::Uncertainty { .. } => "unresolved evidence requirement",
        };
        writeln!(
            out,
            "Claim {} [{:?}]: {}; assertion={:?}; facts={:?}; evidence={:?}",
            claim.id,
            claim.classification,
            wording,
            claim.assertion,
            claim.fact_refs,
            claim.evidence_refs
        )
        .unwrap();
    }
    for gap in &e.gaps {
        writeln!(out, "Gap {} at 0x{:016x}", gap.code, gap.site).unwrap();
    }
    for requirement in &e.evidence_requirements {
        writeln!(
            out,
            "Required evidence [{}] at 0x{:016x} for {:?}: {}",
            requirement.code, requirement.site, requirement.locations, requirement.observation
        )
        .unwrap();
    }
    for assumption in &e.assumptions {
        writeln!(out, "Scope: {assumption}").unwrap();
    }
    if e.truncated {
        writeln!(
            out,
            "Explanation limits exhausted; omitted facts remain unresolved."
        )
        .unwrap();
    }
    Ok(out)
}
