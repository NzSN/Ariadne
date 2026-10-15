//! Strict separate frame-path result; existing report schemas are unchanged.
use super::{Error, Format, strict_json};
use crate::investigation::{FramePathLimits, FramePathListing};
use std::fmt::Write;
pub fn decode_frame_path_limits(bytes: &[u8]) -> Result<FramePathLimits, Error> {
    Ok(serde_json::from_value(strict_json(bytes)?)?)
}
pub fn encode_frame_paths(value: &FramePathListing) -> Result<serde_json::Value, Error> {
    value.validate()?;
    Ok(serde_json::to_value(value)?)
}
pub fn decode_frame_paths(bytes: &[u8]) -> Result<FramePathListing, Error> {
    decode_frame_paths_with_limit(bytes, 8 * 1024 * 1024)
}
/// A caller-selected finite saved-report bound; the default decoder is unchanged.
pub fn decode_frame_paths_with_limit(
    bytes: &[u8],
    max_bytes: usize,
) -> Result<FramePathListing, Error> {
    let value: FramePathListing =
        serde_json::from_value(super::strict_json_with_limit(bytes, max_bytes)?)?;
    value.validate()?;
    Ok(value)
}
pub fn render_frame_paths(value: &FramePathListing, format: Format) -> Result<String, Error> {
    value.validate()?;
    let mut out = String::new();
    match format {
        Format::Json => out = format!("{}\n", serde_json::to_string_pretty(value)?),
        Format::Text => {
            writeln!(out, "Ariadne frame paths ({})", value.schema).unwrap();
            writeln!(out,"Snapshot: {}\nThread: {}\nFrames: {} -> {}\nReturned: {} < {}\nCoverage: {}; truncated: {}\nStop: {}",value.frame_chain().snapshot_id,value.frame_chain().thread_id,value.question.from_frame,value.question.to_frame,value.returned_count,value.question.np,value.coverage,value.truncated,value.stop_reason).unwrap();
            if [
                crate::investigation::COMPOSED_FRAME_PATH_SCHEMA,
                crate::investigation::LEGACY_COMPOSED_FRAME_PATH_SCHEMA,
                crate::investigation::LEGACY_V2_COMPOSED_FRAME_PATH_SCHEMA,
                crate::investigation::GUARDED_FRAME_PATH_SCHEMA,
            ]
            .contains(&value.schema.as_str())
            {
                writeln!(
                    out,
                    "Paired proof and original capture input: {}",
                    serde_json::to_string(value)?
                )
                .unwrap();
            }
            for (i, path) in value.paths.iter().enumerate() {
                writeln!(out, "Path {} ({}):", i + 1, path.path_id).unwrap();
                for (j, node) in path.nodes.iter().enumerate() {
                    writeln!(
                        out,
                        "  frame {}: 0x{:016x}{}",
                        node.frame,
                        node.site,
                        path.edges
                            .get(j)
                            .map_or(String::new(), |e| format!(" --{:?}-->", e.kind))
                    )
                    .unwrap();
                }
            }
            writeln!(
                out,
                "Gaps: {}\nPremises: {}",
                value.gaps.join(", "),
                value.premises.join("; ")
            )
            .unwrap();
        }
        Format::Dot => {
            writeln!(out, "// frame-paths: {}", serde_json::to_string(value)?).unwrap();
            writeln!(out, "digraph FramePaths {{").unwrap();
            for (i, path) in value.paths.iter().enumerate() {
                for (j, node) in path.nodes.iter().enumerate() {
                    writeln!(
                        out,
                        "  p{i}_{j} [label={}];",
                        serde_json::to_string(&format!(
                            "frame {}: 0x{:016x}",
                            node.frame, node.site
                        ))?
                    )
                    .unwrap();
                }
                for (j, edge) in path.edges.iter().enumerate() {
                    writeln!(
                        out,
                        "  p{i}_{j} -> p{i}_{} [label={}];",
                        j + 1,
                        serde_json::to_string(&format!("{:?}", edge.kind))?
                    )
                    .unwrap();
                }
            }
            writeln!(out, "}}").unwrap();
        }
    }
    if out.len() > value.limits.max_output_bytes {
        return Err("frame formatted output exceeds byte budget".into());
    }
    Ok(out)
}
