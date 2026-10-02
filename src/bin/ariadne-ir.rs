use ariadne::reports::{Format, ir_report, publish_all, render_report, sha256};
use std::collections::BTreeSet;
use std::io::Write;
use std::path::PathBuf;

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let artifact=PathBuf::from(args.next().ok_or("usage: ariadne-ir IR --helper PATH --function NAME --seed ID [--seed ID ...] (--format text|dot|json | --output-dir NEW_DIR)")?);
    let mut helper = None;
    let mut function = None;
    let mut seeds = BTreeSet::new();
    let mut format = None;
    let mut output = None;
    while let Some(flag) = args.next() {
        let value = args.next().ok_or("option requires a value")?;
        match flag.as_str() {
            "--helper" if helper.is_none() => helper = Some(PathBuf::from(value)),
            "--function" if function.is_none() => function = Some(value),
            "--seed" => {
                if !seeds.insert(ariadne::llvm_ir::InstructionId(value)) {
                    return Err("duplicate seed".into());
                }
            }
            "--format" if format.is_none() => {
                format = Some(match value.as_str() {
                    "text" => Format::Text,
                    "dot" => Format::Dot,
                    "json" => Format::Json,
                    _ => return Err("format must be text, dot or json".into()),
                })
            }
            "--output-dir" if output.is_none() => output = Some(PathBuf::from(value)),
            _ => return Err(format!("unknown or duplicate option: {flag}").into()),
        }
    }
    if format.is_some() == output.is_some() || seeds.is_empty() {
        return Err("select seeds and exactly one output mode".into());
    }
    let helper = helper.ok_or("--helper is required")?;
    let function = function.ok_or("--function is required")?;
    let helper_hash = sha256(&std::fs::read(&helper)?);
    let request = ariadne::ir::open_verified_ir(&artifact, &helper, &function, seeds)?;
    if sha256(&std::fs::read(&helper)?) != helper_hash {
        return Err("helper changed during verification".into());
    }
    let report = ir_report(&ariadne::llvm_ir::analyze(request)?, Some(&helper_hash))?;
    if let Some(output) = output {
        let files = [
            ("report.txt", render_report(&report, Format::Text)?),
            ("report.dot", render_report(&report, Format::Dot)?),
            ("report.json", render_report(&report, Format::Json)?),
        ];
        publish_all(&output, &files)?;
    } else {
        std::io::stdout()
            .lock()
            .write_all(render_report(&report, format.unwrap())?.as_bytes())?;
    }
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("ariadne-ir: {error}");
        std::process::exit(1);
    }
}
