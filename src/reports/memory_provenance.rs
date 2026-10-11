//! Independently versioned, recomputation-checked memory assessment reporting.
use super::{Error, Format, strict_json};
use crate::investigation::MemoryProvenanceAssessment;
use std::fmt::Write;
pub fn encode_memory_provenance(
    value: &MemoryProvenanceAssessment,
) -> Result<serde_json::Value, Error> {
    value.validate()?;
    Ok(serde_json::to_value(value)?)
}
pub fn decode_memory_provenance(bytes: &[u8]) -> Result<MemoryProvenanceAssessment, Error> {
    let value: MemoryProvenanceAssessment = serde_json::from_value(strict_json(bytes)?)?;
    value.validate()?;
    Ok(value)
}
pub fn render_memory_provenance(
    value: &MemoryProvenanceAssessment,
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
            "// memory-provenance: {}",
            serde_json::to_string(value)?
        )
        .unwrap();
        writeln!(out, "digraph MemoryProvenance {{").unwrap();
        writeln!(
            out,
            "  label={};",
            serde_json::to_string("Possible memory writers under bound premises")?
        )
        .unwrap();
        for (index, c) in value.candidates.iter().enumerate() {
            writeln!(
                out,
                "  c{index} [label={}];",
                serde_json::to_string(&format!(
                    "0x{:016x} {:?}: {} ({})",
                    c.site, c.origin, c.disposition, c.reason
                ))?
            )
            .unwrap();
        }
        writeln!(out, "}}").unwrap();
        return Ok(out);
    }
    writeln!(out, "Ariadne memory provenance ({})", value.schema).unwrap();
    writeln!(out,"Snapshot: {}\nQuery: {}\nLoad: 0x{:016x} access {}\nCandidates: {}\nAvailable: {}; truncated: {}",value.identity.snapshot_id,value.identity.query_id,value.question.site,value.question.memory_access,value.original_candidate_count,value.available,value.truncated).unwrap();
    for c in &value.candidates {
        writeln!(
            out,
            "  0x{:016x} {:?}: {} ({})",
            c.site, c.origin, c.disposition, c.reason
        )
        .unwrap();
    }
    for n in &value.numerical {
        writeln!(
            out,
            "  Numerical 0x{:016x} {}: {:?}; boundary={:?}",
            n.site, n.register, n.value, n.reason
        )
        .unwrap();
    }
    for d in &value.diagnostics {
        writeln!(
            out,
            "  Diagnostic 0x{:016x}: {} ({})",
            d.site,
            d.kind,
            d.original_gaps.join(", ")
        )
        .unwrap();
    }
    writeln!(
        out,
        "Gaps: {}\nPremises: {}",
        value.gaps.join(", "),
        value.premises.join("; ")
    )
    .unwrap();
    Ok(out)
}
