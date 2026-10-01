use ariadne::effects::PreparationOptions;
use ariadne::llvm_mc::DecoderTarget;
use ariadne::{
    AnalysisRequest, Analyzer, ByteSource, DefinitionOrigin, EdgeKind, InputKind, InstructionKind,
    ObligationReason, Phase,
};
use ariadne_bap::{Backend, Config};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::PathBuf;
fn edge(kind: EdgeKind) -> &'static str {
    match kind {
        EdgeKind::Next => "next",
        EdgeKind::Taken => "taken",
        EdgeKind::Fallthrough => "fallthrough",
        EdgeKind::Jump => "jump",
        EdgeKind::Indirect => "indirect",
        EdgeKind::Summary => "summary",
        EdgeKind::Call => "call",
    }
}
fn observe(a: &Analyzer) -> Value {
    let s = a.state();
    json!({
     "phase":match s.phase{Phase::Recover=>"recover",Phase::Dataflow=>"dataflow",Phase::Slice=>"slice",Phase::Done=>"done"},
     "pending":s.pending,"visited":s.visited,"decoded":s.decoded,"slice":s.slice,
     "provenance":s.provenance.iter().map(|(&va,source)|json!({"va":va,"source":match source{ByteSource::Captured=>"captured",ByteSource::File=>"file",ByteSource::Unavailable=>"unavailable"}})).collect::<Vec<_>>(),
     "edges":s.edges.iter().map(|e|json!({"src":e.src,"dst":e.dst,"kind":edge(e.kind)})).collect::<Vec<_>>(),
     "obligations":s.obligations.iter().map(|o|json!({"site":o.site,"reason":match o.reason{ObligationReason::Unavailable=>"unavailable",ObligationReason::DecodeFailed=>"decode-failed",ObligationReason::IndirectTargets=>"indirect-targets",ObligationReason::CallTargets=>"call-targets"}})).collect::<Vec<_>>(),
     "reaching":s.reaching.iter().map(|(&va,defs)|json!({"va":va,"definitions":defs.iter().map(|d|json!({"loc":d.loc,"site":d.site,"origin":match d.origin{DefinitionOrigin::Entry=>"entry",DefinitionOrigin::Instruction=>"instruction"}})).collect::<Vec<_>>()})).collect::<Vec<_>>()
    })
}
fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 1 {
        return Err("case required: pipeline|alias|conditional".into());
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf();
    let code: Vec<(u64, &str)> = match args[0].as_str() {
        "pipeline" => vec![
            (4096, "4889d8"),
            (4099, "48f7d0"),
            (4102, "c70005000000"),
            (4108, "c3"),
        ],
        "alias" => vec![
            (4096, "4889d8"),
            (4099, "88dc"),
            (4101, "c70005000000"),
            (4107, "c3"),
        ],
        "conditional" => vec![(4096, "480f45c3"), (4100, "c70005000000"), (4106, "c3")],
        "branch" => vec![
            (4096, "4839d8"),
            (4099, "7506"),
            (4101, "c70005000000"),
            (4107, "c3"),
        ],
        "loop" => vec![
            (4096, "4889d8"),
            (4099, "48ffc0"),
            (4102, "75fb"),
            (4104, "c70005000000"),
            (4110, "c3"),
        ],
        "weak-store" => vec![
            (4096, "4889d8"),
            (4099, "488903"),
            (4102, "b800000000"),
            (4107, "488903"),
            (4110, "c3"),
        ],
        "opaque-call" => vec![(4096, "e8fbffffff"), (4101, "c70005000000"), (4107, "c3")],
        "indirect" => vec![(4096, "ffe0"), (4098, "c3")],
        _ => return Err("unknown case".into()),
    };
    let seed = code[code.len() - 2].0;
    let candidates: BTreeMap<_, _> = code
        .iter()
        .map(|(a, hex)| {
            (
                *a,
                Some(
                    (0..hex.len())
                        .step_by(2)
                        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                        .collect(),
                ),
            )
        })
        .collect();
    let options = PreparationOptions::default();
    let snapshot = format!("bap-model-fixture:{}", args[0]);
    let mut backend = Backend::new(
        Config::new(
            root.join("target/ariadne-bap-lift"),
            root.join("tmp/bap-setup/stable"),
        ),
        &root.join("target/ariadne-llvm-mc"),
    )?;
    let batch = backend.prepare(&snapshot, &candidates, &options, DecoderTarget::LinuxAmd64)?;
    backend.finish()?;
    let request = AnalysisRequest {
        snapshot_id: snapshot.clone(),
        addresses: candidates.keys().copied().collect(),
        locations: options.catalogue.locations(),
        entry_points: [4096].into(),
        slice_seeds: [seed].into(),
        input_kind: InputKind::Dump,
        captured: candidates.keys().copied().collect(),
        file_backed: Default::default(),
        trusted_fallback: Default::default(),
        decodable: batch
            .sites
            .iter()
            .filter_map(|(&a, s)| s.decodable.then_some(a))
            .collect(),
        instructions: batch
            .sites
            .iter()
            .map(|(&a, s)| (a, s.instruction.clone()))
            .collect(),
    };
    request.validate()?;
    let inputs = json!({"snapshot":snapshot,"addresses":request.addresses,"locations":request.locations,"entries":request.entry_points,"seeds":request.slice_seeds,"captured":request.captured,"decodable":request.decodable,
 "instructions":request.instructions.iter().map(|(&a,i)|json!({"va":a,"kind":match i.kind{InstructionKind::Ordinary=>"ordinary",InstructionKind::Conditional=>"conditional",InstructionKind::Jump=>"jump",InstructionKind::Indirect=>"indirect",InstructionKind::Call=>"call",InstructionKind::Return=>"return",InstructionKind::Stop=>"stop"},"fall":i.fall,"targets":i.targets,"complete":i.complete,"uses":i.uses,"may_defs":i.may_defs,"must_defs":i.must_defs})).collect::<Vec<_>>()});
    let mut analyzer = Analyzer::new(request)?;
    let mut states = vec![observe(&analyzer)];
    while analyzer.step() {
        states.push(observe(&analyzer));
    }
    println!(
        "{}",
        json!({"case":args[0],"inputs":inputs,"observations":states})
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
