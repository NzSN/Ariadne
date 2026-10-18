//! Opt-in bounded frame question mode, before any full caller analysis.
use super::{Args, frame_structure, invalid, publish_all};
use ariadne::investigation::{
    FrameQuestionLimits, FrameQuestionRequest, investigate_frame_question,
};
use ariadne::reports::frame_question as report;
use std::{error::Error, io::Write, path::Path};
pub(super) fn read_limits(path: &Path) -> Result<FrameQuestionLimits, Box<dyn Error>> {
    let limits: FrameQuestionLimits =
        serde_json::from_value(frame_structure::read_json(path, 65536)?)?;
    limits.validate()?;
    Ok(limits)
}
pub(super) fn read_request(path: &Path) -> Result<FrameQuestionRequest, Box<dyn Error>> {
    Ok(serde_json::from_value(frame_structure::read_json(
        path, 65536,
    )?)?)
}
pub(super) fn run(args: &Args) -> Result<(), Box<dyn Error>> {
    let question = args
        .question
        .as_ref()
        .ok_or_else(|| invalid("frame question absent"))?;
    let limits = args
        .question_limits
        .as_ref()
        .ok_or_else(|| invalid("frame question host policy absent"))?;
    let (snapshot, source) = frame_structure::prepare_with_snapshot(args)?;
    let mut config = ariadne::bap::Config::from_env();
    if let Some(helper) = &args.bap_helper {
        config.helper = helper.clone();
    }
    if let Some(runtime) = &args.bap_runtime {
        config.runtime = runtime.clone();
    }
    let options = ariadne::effects::PreparationOptions::default();
    let setup = ariadne::input::FramePreparation {
        decoder: &args.decoder,
        config: &config,
        options: &options,
        limits: source.limits().prepare_limits(),
    };
    let evidence = snapshot.frame_question_evidence(&source, &setup)?;
    let bound = investigate_frame_question(source, question.clone(), evidence, limits.clone())?;
    if let Some(dir) = &args.output_dir {
        let files = vec![
            ("frame-question.json", report::render_json(&bound)?),
            ("frame-question.txt", report::render_text(&bound)?),
            ("frame-question.dot", report::render_dot(&bound)?),
        ];
        if files
            .iter()
            .try_fold(0usize, |n, (_, s)| n.checked_add(s.len()))
            .is_none_or(|n| n > limits.max_output_bytes)
        {
            return Err(invalid("question publication byte cap").into());
        }
        publish_all(dir, &files)?;
    } else {
        let text = match args.format.as_ref().expect("validated format") {
            ariadne::input::report::ReportFormat::Json => report::render_json(&bound)?,
            ariadne::input::report::ReportFormat::Text => report::render_text(&bound)?,
            ariadne::input::report::ReportFormat::Dot => report::render_dot(&bound)?,
        };
        std::io::stdout().lock().write_all(text.as_bytes())?;
    }
    Ok(())
}
