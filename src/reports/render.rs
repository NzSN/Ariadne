use crate::reports::codecs::{edge_kind, ir_edge, ir_reason, ms_reason, outcome_name};
use crate::reports::{Error, invalid};
use crate::{ByteSource, ObligationReason, llvm_ir as ir, machine_state as ms};
use serde_json::{Value, json};
use std::fmt::Write as _;
use std::io::Write as _;
use std::path::Path;

#[derive(Clone, Copy, Debug)]
pub enum Format {
    Text,
    Dot,
    Json,
}
fn va(address: u64) -> String {
    format!("0x{address:016x}")
}
fn edges(values: &crate::EdgeSet) -> Value {
    json!(
        values
            .iter()
            .map(|e| json!({"src":va(e.src),"dst":va(e.dst),"kind":edge_kind(e.kind)}))
            .collect::<Vec<_>>()
    )
}
pub fn machine_report(
    result: &ms::AnalysisResult,
    context: Option<&ms::RecoveryContext>,
    semantics_hash: Option<&str>,
) -> Result<Value, Error> {
    if result.state().phase != ms::Phase::Done {
        return Err(invalid("machine result is not completed"));
    }
    let request = result.request();
    request.validate()?;
    if let Some(context) = context {
        let local: crate::EdgeSet = context
            .full_edges
            .iter()
            .filter(|e| e.kind.is_local())
            .copied()
            .collect();
        if context.snapshot_id != request.snapshot_id || local != request.structural_edges {
            return Err(invalid("recovery/report identity or graph mismatch"));
        }
    }
    let views = result.observations();
    let recovery=context.map(|c|json!({
        "snapshot_id":c.snapshot_id,"full_edges":edges(&c.full_edges),
        "byte_provenance":c.byte_provenance.iter().map(|(&address,source)|json!({"va":va(address),"source":match source{ByteSource::Captured=>"captured",ByteSource::File=>"file",ByteSource::Unavailable=>"unavailable"}})).collect::<Vec<_>>(),
        "obligations":c.recovery_obligations.iter().map(|o|json!({"site":va(o.site),"reason":match o.reason{ObligationReason::Unavailable=>"unavailable",ObligationReason::DecodeFailed=>"decode-failed",ObligationReason::IndirectTargets=>"indirect-targets",ObligationReason::CallTargets=>"call-targets"}})).collect::<Vec<_>>(),
        "missing_slice_seeds":c.missing_slice_seeds.iter().map(|&a|va(a)).collect::<Vec<_>>(),
    }));
    Ok(json!({
        "schema":"ariadne.machine-state-report/v1","phase":"done",
        "identity":{"snapshot_id":request.snapshot_id,"semantic_input_sha256":semantics_hash},
        "assumptions":{"instruction_transitions":"caller-supplied finite relation","complete_sites":"caller-supplied assertion","historical_execution":"not reconstructed","feasibility":"relative to supplied relation and entry facts"},
        "request":crate::reports::encode_machine_request(request)?,
        "states_at":result.state().states_at.iter().map(|(&address,states)|json!({"va":va(address),"states":states.iter().map(|s|&s.0).collect::<Vec<_>>()})).collect::<Vec<_>>(),
        "structural_edges":edges(&request.structural_edges),"feasible_edges":edges(&views.feasible_edges),
        "infeasible_edges":edges(&views.provably_infeasible_edges),"unknown_edges":edges(&views.unknown_feasibility_edges),
        "terminals":views.reached_terminal_transitions.iter().map(|t|json!({"site":va(t.site),"before":t.before.0,"after":t.after.0,"outcome":outcome_name(t.outcome)})).collect::<Vec<_>>(),
        "not_reached":views.not_reached_nodes.iter().map(|&a|va(a)).collect::<Vec<_>>(),
        "obligations":views.obligations.iter().map(|o|json!({"site":va(o.site),"reason":match o.reason{ms::ObligationReason::IncompleteSemantics=>"incomplete-semantics",ms::ObligationReason::Adapter(reason)=>ms_reason(reason)}})).collect::<Vec<_>>(),
        "recovery":recovery,
    }))
}
pub fn ir_report(result: &ir::AnalysisResult, helper_hash: Option<&str>) -> Result<Value, Error> {
    if result.state().phase != ir::Phase::Done {
        return Err(invalid("IR result is not completed"));
    }
    let request = result.request();
    request.validate()?;
    Ok(json!({
        "schema":"ariadne.llvm-ir-report/v1","phase":"done",
        "identity":{"artifact_id":request.artifact_id,"module_id":request.module_id,"function_id":request.function_id,"helper_sha256":helper_hash},
        "assumptions":{"verified_ir":request.verified_ir,"memory_predecessors":"adapter-supplied conservative relation","machine_address_correspondence":"not established"},
        "request":crate::reports::encode_ir_request(request)?,"slice":result.state().slice.iter().map(|i|&i.0).collect::<Vec<_>>(),
        "control_graph":request.control_graph().iter().map(|e|json!({"src":e.src.0,"dst":e.dst.0,"kind":ir_edge(e.kind)})).collect::<Vec<_>>(),
        "call_graph":request.call_graph().iter().map(|e|json!({"site":e.site.0,"callee":e.callee.0,"kind":"call"})).collect::<Vec<_>>(),
        "dependency_preds":request.instructions.keys().map(|i|json!({"instruction":i.0,"predecessors":request.dependency_preds(i).iter().map(|p|&p.0).collect::<Vec<_>>()})).collect::<Vec<_>>(),
        "obligations":request.obligations().iter().map(|o|json!({"site":o.site.0,"reason":match o.reason{ir::ObligationReason::CallTargets=>"call-targets",ir::ObligationReason::Adapter(r)=>ir_reason(r)}})).collect::<Vec<_>>(),
    }))
}
pub fn render_report(report: &Value, format: Format) -> Result<String, Error> {
    let schema = report["schema"]
        .as_str()
        .ok_or_else(|| invalid("missing report schema"))?;
    let machine = match schema {
        "ariadne.machine-state-report/v1" => true,
        "ariadne.llvm-ir-report/v1" => false,
        _ => return Err(invalid("unknown report schema")),
    };
    if report["phase"] != "done" {
        return Err(invalid("report phase must be done"));
    }
    match format {
        Format::Json => Ok(serde_json::to_string_pretty(report)? + "\n"),
        Format::Text => {
            let mut text = format!(
                "{schema}\nIdentity: {}\nAssumptions: {}\n",
                report["identity"], report["assumptions"]
            );
            if machine {
                for row in report["states_at"]
                    .as_array()
                    .ok_or_else(|| invalid("missing state rows"))?
                {
                    writeln!(
                        text,
                        "{} before: {}",
                        row["va"].as_str().unwrap_or("?"),
                        row["states"]
                    )?;
                }
                for field in [
                    "structural_edges",
                    "feasible_edges",
                    "infeasible_edges",
                    "unknown_edges",
                    "terminals",
                    "not_reached",
                    "obligations",
                    "recovery",
                    "minidump_report",
                ] {
                    writeln!(text, "{field}: {}", report[field])?;
                }
            } else {
                for field in [
                    "slice",
                    "control_graph",
                    "call_graph",
                    "dependency_preds",
                    "obligations",
                ] {
                    writeln!(text, "{field}: {}", report[field])?;
                }
            }
            Ok(text)
        }
        Format::Dot => {
            let quote = |text: &str| serde_json::to_string(text);
            let mut text = format!(
                "digraph stage_e {{\n  label={};\n",
                quote(&format!(
                    "{schema}\nIdentity: {}\nAssumptions: {}\nObligations: {}",
                    report["identity"], report["assumptions"], report["obligations"]
                ))?
            );
            if machine {
                for row in report["states_at"]
                    .as_array()
                    .ok_or_else(|| invalid("missing state rows"))?
                {
                    let address = row["va"].as_str().ok_or_else(|| invalid("invalid VA"))?;
                    writeln!(
                        text,
                        "  {} [label={}];",
                        quote(address)?,
                        quote(&format!("{address}\nbefore: {}", row["states"]))?
                    )?;
                }
                for edge in report["structural_edges"]
                    .as_array()
                    .ok_or_else(|| invalid("missing graph"))?
                {
                    let class = if report["feasible_edges"]
                        .as_array()
                        .is_some_and(|a| a.contains(edge))
                    {
                        "feasible"
                    } else if report["infeasible_edges"]
                        .as_array()
                        .is_some_and(|a| a.contains(edge))
                    {
                        "model-infeasible"
                    } else {
                        "unknown"
                    };
                    writeln!(
                        text,
                        "  {} -> {} [label={}];",
                        quote(
                            edge["src"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid edge"))?
                        )?,
                        quote(
                            edge["dst"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid edge"))?
                        )?,
                        quote(&format!(
                            "{} {class}",
                            edge["kind"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid kind"))?
                        ))?
                    )?;
                }
                writeln!(
                    text,
                    "  terminals [shape=note,label={}];",
                    quote(&format!(
                        "Terminals: {}\nNot reached: {}\nRecovery: {}\nMinidump evidence: {}",
                        report["terminals"],
                        report["not_reached"],
                        report["recovery"],
                        json!({"schema":report["minidump_report"]["schema"],"identity":report["minidump_report"]["identity"],"preparation_gaps":report["minidump_report"]["preparation"]["gaps"]})
                    ))?
                )?;
            } else {
                let instructions = report["request"]["instructions"]
                    .as_object()
                    .ok_or_else(|| invalid("missing IR instructions"))?;
                for id in instructions.keys() {
                    let sliced = report["slice"]
                        .as_array()
                        .is_some_and(|s| s.contains(&Value::String(id.clone())));
                    writeln!(
                        text,
                        "  {} [label={},style={}];",
                        quote(&format!("instruction:{id}"))?,
                        quote(id)?,
                        if sliced { "bold" } else { "dashed" }
                    )?;
                }
                for row in report["dependency_preds"]
                    .as_array()
                    .ok_or_else(|| invalid("missing dependencies"))?
                {
                    let id = row["instruction"]
                        .as_str()
                        .ok_or_else(|| invalid("invalid instruction"))?;
                    for pred in row["predecessors"]
                        .as_array()
                        .ok_or_else(|| invalid("invalid predecessors"))?
                    {
                        writeln!(
                            text,
                            "  {} -> {} [label=dependency];",
                            quote(&format!(
                                "instruction:{}",
                                pred.as_str()
                                    .ok_or_else(|| invalid("invalid predecessor"))?
                            ))?,
                            quote(&format!("instruction:{id}"))?
                        )?;
                    }
                }
                for edge in report["control_graph"]
                    .as_array()
                    .ok_or_else(|| invalid("missing CFG"))?
                {
                    writeln!(
                        text,
                        "  {} -> {} [label={}];",
                        quote(&format!(
                            "block:{}",
                            edge["src"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid block"))?
                        ))?,
                        quote(&format!(
                            "block:{}",
                            edge["dst"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid block"))?
                        ))?,
                        quote(
                            edge["kind"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid kind"))?
                        )?
                    )?;
                }
                for edge in report["call_graph"]
                    .as_array()
                    .ok_or_else(|| invalid("missing calls"))?
                {
                    writeln!(
                        text,
                        "  {} -> {} [label=call];",
                        quote(&format!(
                            "instruction:{}",
                            edge["site"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid call"))?
                        ))?,
                        quote(&format!(
                            "callee:{}",
                            edge["callee"]
                                .as_str()
                                .ok_or_else(|| invalid("invalid callee"))?
                        ))?
                    )?;
                }
            }
            text.push_str("}\n");
            Ok(text)
        }
    }
}
pub fn publish_all(directory: &Path, reports: &[(&str, String)]) -> Result<(), Error> {
    if std::fs::symlink_metadata(directory).is_ok() {
        return Err(invalid("output directory already exists"));
    }
    let parent = directory
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let name = directory
        .file_name()
        .ok_or_else(|| invalid("output directory needs a name"))?;
    let mut staging = None;
    for suffix in 0..100 {
        let candidate = parent.join(format!(
            ".{}.ariadne-stage-e-{}-{suffix}",
            name.to_string_lossy(),
            std::process::id()
        ));
        match std::fs::create_dir(&candidate) {
            Ok(()) => {
                staging = Some(candidate);
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e.into()),
        }
    }
    let staging = staging.ok_or_else(|| invalid("cannot reserve report staging directory"))?;
    let result = (|| -> Result<(), Error> {
        for (name, contents) in reports {
            if Path::new(name).components().count() != 1 || *name == "." || *name == ".." {
                return Err(invalid("report filename must be one normal component"));
            }
            let mut file = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(staging.join(name))?;
            file.write_all(contents.as_bytes())?;
            file.sync_all()?;
        }
        if std::fs::symlink_metadata(directory).is_ok() {
            return Err(invalid("output appeared during publication"));
        }
        std::fs::rename(&staging, directory)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_dir_all(staging);
    }
    result
}
