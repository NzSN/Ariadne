//! Actual production preparation for a finite instruction-family survey.
//! This observer reports gaps; a decoded/projected instruction is not an ISA proof.
use ariadne::bap::{Backend, Config};
use ariadne::effects::PreparationOptions;
use ariadne::llvm_mc::DecoderTarget;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::PathBuf;

#[test]
#[ignore = "requires pinned BAP/LLVM helpers; run tools/probe_amd64_semantics.py --native"]
fn probe_catalogue() -> Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let catalogue_path = std::env::var_os("ARIADNE_SEMANTICS_CATALOGUE")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("tests/bap/fixtures/amd64-semantics/catalogue.json"));
    let output = PathBuf::from(
        std::env::var_os("ARIADNE_SEMANTICS_PROBE_OUTPUT")
            .ok_or("ARIADNE_SEMANTICS_PROBE_OUTPUT is required")?,
    );
    let catalogue_bytes = std::fs::read(catalogue_path)?;
    let catalogue: Value = serde_json::from_slice(&catalogue_bytes)?;
    let snapshot = ariadne::reports::sha256(&catalogue_bytes);
    let cases = catalogue["cases"].as_array().ok_or("catalogue cases")?;
    let config = Config::from_env();
    let decoder = std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("target/ariadne-llvm-mc"));
    let mut backend = Some(Backend::new(config.clone(), &decoder)?);
    let options = PreparationOptions::default();
    let mut rows = Vec::new();
    for (index, case) in cases.iter().enumerate() {
        let code = case["bytes"].as_str().ok_or("catalogue bytes")?;
        let bytes = (0..code.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&code[i..i + 2], 16))
            .collect::<Result<Vec<_>, _>>()?;
        let va = 0x401000 + index as u64 * 32;
        if backend.is_none() {
            backend = Some(Backend::new(config.clone(), &decoder)?);
        }
        let candidates: BTreeMap<_, _> = [(va, Some(bytes))].into();
        let result = backend.as_mut().unwrap().prepare(
            &snapshot,
            &candidates,
            &options,
            DecoderTarget::WindowsAmd64,
        );
        match result {
            Ok(batch) => {
                let site = batch.sites.get(&va).ok_or("missing requested site")?;
                let semantic = site.evidence.semantic.as_ref().map(|s| {
                    json!({
                        "backend": s.backend, "helperSha256": s.helper_sha256,
                        "runtimeSha256": s.runtime_sha256, "projection": s.projection,
                        "status": s.status, "astSha256": s.ast_sha256,
                        "fallback": s.fallback, "gaps": s.gaps,
                    })
                });
                rows.push(json!({
                    "id": case["id"], "bytes": code,
                    "address": format!("0x{va:016x}"), "error": null,
                    "decodable": site.decodable,
                    "consumedBytes": site.evidence.bytes.iter().map(|b| format!("{b:02x}")).collect::<String>(),
                    "length": site.evidence.length, "opcode": site.evidence.opcode,
                    "decoderRecord": site.evidence.decoder_record,
                    "quality": format!("{:?}", site.evidence.quality),
                    "control": format!("{:?}", site.instruction.kind),
                    "fall": site.instruction.fall, "targets": site.instruction.targets,
                    "targetsComplete": site.instruction.complete,
                    "effects": {"uses": site.instruction.uses,
                        "mayDefs": site.instruction.may_defs, "mustDefs": site.instruction.must_defs},
                    "semantic": semantic,
                    "preparationGaps": site.gaps.iter().map(|g| format!("{:?}", g.reason)).collect::<Vec<_>>(),
                }));
            }
            Err(error) => {
                rows.push(json!({"id": case["id"], "bytes": code,
                    "address": format!("0x{va:016x}"), "error": error.to_string()}));
                // A failed helper/projection query is never reused as a healthy session.
                backend.take();
            }
        }
    }
    if let Some(backend) = backend {
        backend.finish()?;
    }
    let report = json!({
        "schema": "ariadne.amd64-semantics-native-probe/v1",
        "catalogueSha256": snapshot,
        "decoderSha256": ariadne::reports::sha256(&std::fs::read(decoder)?),
        "helperSha256": ariadne::reports::sha256(&std::fs::read(config.helper)?),
        "target": "windows-amd64", "rows": rows,
    });
    std::fs::write(output, serde_json::to_vec_pretty(&report)?)?;
    Ok(())
}
