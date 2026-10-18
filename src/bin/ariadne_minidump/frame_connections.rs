//! Connection mode shares only Stage 5.1 preparation, never full analysis.
use super::{Args, frame_structure, invalid, publish_all};
use ariadne::investigation::{FrameConnectionLimits, summarize_frame_connections};
use ariadne::reports::frame_connections as report;
use std::error::Error;
use std::io::Write;
use std::path::Path;
pub(super) fn read_limits(path: &Path) -> Result<FrameConnectionLimits, Box<dyn Error>> {
    let policy: FrameConnectionLimits = serde_json::from_value(frame_structure::read_json(
        path,
        frame_structure::MAX_POLICY_BYTES,
    )?)?;
    policy.validate()?;
    Ok(policy)
}
pub(super) fn run(args: &Args) -> Result<(), Box<dyn Error>> {
    let limits = args
        .connection_limits
        .as_ref()
        .ok_or_else(|| invalid("connection host policy absent"))?;
    let source = frame_structure::prepare(args)?;
    let bound = summarize_frame_connections(source, args.example_count_bound, limits.clone())?;
    if let Some(directory) = &args.output_dir {
        let files = vec![
            ("frame-connections.json", report::render_json(&bound)?),
            ("frame-connections.txt", report::render_text(&bound)?),
            ("frame-connections.dot", report::render_dot(&bound)?),
        ];
        if files
            .iter()
            .try_fold(0usize, |n, (_, s)| n.checked_add(s.len()))
            .is_none_or(|n| n > limits.max_output_bytes)
        {
            return Err(invalid("connection publication byte budget").into());
        }
        publish_all(directory, &files)?;
    } else {
        let text = match args.format.as_ref().unwrap() {
            ariadne::input::report::ReportFormat::Json => report::render_json(&bound)?,
            ariadne::input::report::ReportFormat::Text => report::render_text(&bound)?,
            ariadne::input::report::ReportFormat::Dot => report::render_dot(&bound)?,
        };
        std::io::stdout().lock().write_all(text.as_bytes())?;
    }
    Ok(())
}
