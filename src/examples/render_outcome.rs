//! A completed partial analysis demonstrating call references and missing bytes.
use ariadne::render::{Format, render};
use ariadne::{AnalysisRequest, Instruction, InstructionKind, analyze};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let format = match std::env::args().nth(1).as_deref().unwrap_or("text") {
        "text" => Format::Text,
        "dot" => Format::Dot,
        _ => return Err("usage: render_outcome [text|dot]".into()),
    };
    let request = AnalysisRequest {
        snapshot_id: "render-example".into(),
        addresses: [0x1000, 0x1004, 0x1008, 0x2000].into(),
        locations: ["x".into()].into(),
        entry_points: [0x1000].into(),
        slice_seeds: [0x1004, 0x1008].into(),
        file_backed: [0x1000, 0x1004, 0x2000].into(),
        decodable: [0x1000, 0x1004, 0x2000].into(),
        instructions: [
            (
                0x1000,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [0x1004].into(),
                    uses: ["x".into()].into(),
                    must_defs: ["x".into()].into(),
                    may_defs: ["x".into()].into(),
                    ..Instruction::default()
                },
            ),
            (
                0x1004,
                Instruction {
                    kind: InstructionKind::Call,
                    fall: [0x1008].into(),
                    targets: [0x2000].into(),
                    complete: false,
                    uses: ["x".into()].into(),
                    may_defs: ["x".into()].into(),
                    ..Instruction::default()
                },
            ),
            (0x1008, Instruction::default()),
            (
                0x2000,
                Instruction {
                    kind: InstructionKind::Return,
                    ..Instruction::default()
                },
            ),
        ]
        .into(),
        ..AnalysisRequest::default()
    };
    let result = analyze(request)?;
    use std::io::Write;
    std::io::stdout()
        .lock()
        .write_all(render(&result, format).as_bytes())?;
    Ok(())
}
