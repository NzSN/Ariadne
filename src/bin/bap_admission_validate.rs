//! Strict content-ID validation for the explicit projection-profile migration.
fn main() -> Result<(), ariadne::reports::Error> {
    let paths: Vec<_> = std::env::args_os().skip(1).collect();
    if paths.is_empty() {
        return Err("expected explanation JSON paths".into());
    }
    for path in &paths {
        ariadne::reports::decode_explanation(&std::fs::read(path)?)?;
    }
    println!("{} strict explanation envelopes validated", paths.len());
    Ok(())
}
