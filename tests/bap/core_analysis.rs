use ariadne::bap::core_adapter::NativeAnalyzer;
use ariadne::bap::core_session::CoreConfig;
use ariadne::*;
use std::path::PathBuf;

fn config() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-stage2")
            }),
    )
}
fn request() -> AnalysisRequest {
    AnalysisRequest {
        snapshot_id: "native-analysis-fixture".into(),
        addresses: [0x10, 0x20, 0x30, u64::MAX].into(),
        locations: ["rax".into()].into(),
        entry_points: [0x10].into(),
        slice_seeds: [0x30, u64::MAX].into(),
        input_kind: InputKind::Dump,
        captured: [0x10, 0x20, 0x30, u64::MAX].into(),
        decodable: [0x10, 0x20, 0x30, u64::MAX].into(),
        instructions: [
            (
                0x10,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [0x20].into(),
                    may_defs: ["rax".into()].into(),
                    must_defs: ["rax".into()].into(),
                    ..Instruction::default()
                },
            ),
            (
                0x20,
                Instruction {
                    kind: InstructionKind::Ordinary,
                    fall: [0x30].into(),
                    uses: ["rax".into()].into(),
                    may_defs: ["rax".into()].into(),
                    ..Instruction::default()
                },
            ),
            (
                0x30,
                Instruction {
                    kind: InstructionKind::Return,
                    uses: ["rax".into()].into(),
                    ..Instruction::default()
                },
            ),
            (u64::MAX, Instruction::default()),
        ]
        .into(),
        ..AnalysisRequest::default()
    }
}
fn wide_request(nodes: usize) -> AnalysisRequest {
    let addresses: Vec<_> = (0..nodes).map(|i| 0x1000 + i as u64 * 16).collect();
    let locations: LocationSet = (0..1000).map(|i| format!("loc-{i:04}")).collect();
    AnalysisRequest {
        snapshot_id: "completion-page-regression".into(),
        addresses: addresses.iter().copied().collect(),
        locations: locations.clone(),
        entry_points: [addresses[0]].into(),
        slice_seeds: [*addresses.last().unwrap()].into(),
        input_kind: InputKind::Dump,
        captured: addresses.iter().copied().collect(),
        decodable: addresses.iter().copied().collect(),
        instructions: addresses
            .iter()
            .enumerate()
            .map(|(i, &va)| {
                (
                    va,
                    Instruction {
                        kind: if i + 1 == nodes {
                            InstructionKind::Stop
                        } else {
                            InstructionKind::Ordinary
                        },
                        fall: addresses.get(i + 1).copied().into_iter().collect(),
                        uses: locations.clone(),
                        may_defs: locations.clone(),
                        complete: true,
                        ..Instruction::default()
                    },
                )
            })
            .collect(),
        ..AnalysisRequest::default()
    }
}
#[test]
#[ignore = "requires source-bound native helper with completion pages"]
fn native_completion_pages_preserve_large_final_state() {
    let request = wide_request(20);
    let reference = Analyzer::new(request.clone()).unwrap().finish();
    let rows: Vec<_>=reference.state.reaching.iter().map(|(&va,defs)| serde_json::json!({
        "address":format!("0x{va:016x}"),"definitions":defs.iter().map(|d| serde_json::json!({
            "loc":d.loc,"site":format!("0x{:016x}",d.site),"origin":if d.origin==DefinitionOrigin::Entry {"entry"} else {"instruction"}
        })).collect::<Vec<_>>()
    })).collect();
    assert!(serde_json::to_vec(&rows).unwrap().len() > ariadne::bap::core_protocol::MAX_FRAME);
    let native = NativeAnalyzer::new(&config(), "large-pages", request)
        .unwrap()
        .finish()
        .unwrap();
    assert_eq!(native, reference);
}
#[cfg(unix)]
#[test]
#[ignore = "requires native helper; hostile completion proxy must not publish"]
fn completion_rejects_page_and_lifecycle_tampering() {
    use std::os::unix::fs::PermissionsExt;
    let original = config();
    let folder =
        std::env::temp_dir().join(format!("ariadne-completion-proxy-{}", std::process::id()));
    std::fs::create_dir_all(&folder).unwrap();
    let manifest: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&original.manifest).unwrap()).unwrap();
    for mode in [
        "good",
        "offset",
        "duplicate",
        "checksum",
        "identity",
        "total",
        "oversize",
        "truncate",
        "closed",
        "failed-exit",
        "counter",
        "result-counter",
        "close-offset",
    ] {
        let directory = folder.join(mode);
        std::fs::create_dir_all(&directory).unwrap();
        let helper = directory.join("ariadne-bap-core");
        let script = format!(
            r#"#!/usr/bin/env python3
import json,sys,subprocess
mode={mode:?}
p=subprocess.Popen([{helper:?},*sys.argv[1:]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
print(p.stdout.readline().strip(),flush=True)
pages=0
for line in sys.stdin:
 q=json.loads(line);p.stdin.write(line);p.stdin.flush();raw=p.stdout.readline()
 if not raw:sys.exit(2)
 r=json.loads(raw)
 if r.get('schema')=='ariadne.bap-core-completion/v1':
  op=q['operation']
  if mode=='identity':r['query']='0'*64
  if mode=='oversize':r['total_bytes']=268435457
  if mode=='counter':r['action_index']+=1
  if mode=='result-counter':r['result_sequence']=18446744073709551615
  if op=='result-page':
   pages+=1
   if mode=='offset':r['offset']+=1
   if mode=='duplicate' and pages>1:r['offset']=0
   if mode=='checksum':r['data_hex']='00'+r['data_hex'][2:]
   if mode=='total':r['total_bytes']+=1
   if mode=='truncate':r['data_hex']=r['data_hex'][:-2]
  if op=='result-close' and mode=='closed':r['closed']=False
  if op=='result-close' and mode=='close-offset':r['offset']=1
 print(json.dumps(r),flush=True)
 if q['operation']=='result-close':
  p.stdin.close();code=p.wait();sys.exit(7 if mode=='failed-exit' else code)
p.stdin.close();sys.exit(p.wait())
"#,
            mode = mode,
            helper = original.helper.to_string_lossy()
        );
        std::fs::write(&helper, script).unwrap();
        std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o755)).unwrap();
        let mut build = manifest.clone();
        build["helper_sha256"] =
            serde_json::json!(ariadne::reports::sha256(&std::fs::read(&helper).unwrap()));
        std::fs::write(
            directory.join("manifest.json"),
            serde_json::to_vec(&build).unwrap(),
        )
        .unwrap();
        let request = wide_request(3);
        let result = NativeAnalyzer::new(
            &CoreConfig::from_directory(directory),
            mode,
            request.clone(),
        )
        .unwrap()
        .finish();
        if mode == "good" {
            assert_eq!(result.unwrap(), Analyzer::new(request).unwrap().finish());
        } else {
            assert!(result.is_err(), "accepted completion tampering: {mode}");
        }
    }
}
#[test]
#[ignore = "requires explicitly built Stage 2 native helper"]
fn native_complete_state_actions_match_reference_and_independent_origins() {
    let request = request();
    let mut native = NativeAnalyzer::new(&config(), "complete", request.clone()).unwrap();
    let mut reference = Analyzer::new(request).unwrap();
    let mut count = 0;
    loop {
        assert_eq!(
            native.state(),
            reference.state(),
            "complete state after action {count}"
        );
        let advanced = reference.step();
        assert_eq!(native.step().unwrap(), advanced);
        if !advanced {
            break;
        }
        count += 1;
        assert!(count < 100);
    }
    assert_eq!(count, 10);
    let result = native.finish().unwrap();
    assert_eq!(result, reference.finish());
    assert_eq!(result.state.slice, [0x10, 0x20, 0x30].into());
    assert_eq!(result.missing_slice_seeds, [u64::MAX].into());
    assert_eq!(
        result.state.reaching[&0x30],
        [
            Definition {
                loc: "rax".into(),
                site: 0x10,
                origin: DefinitionOrigin::Instruction
            },
            Definition {
                loc: "rax".into(),
                site: 0x20,
                origin: DefinitionOrigin::Instruction
            }
        ]
        .into()
    );
    assert_eq!(
        result.state.reaching[&0x10],
        [Definition {
            loc: "rax".into(),
            site: 0x10,
            origin: DefinitionOrigin::Entry
        }]
        .into()
    );
}
#[test]
#[ignore = "requires explicitly built Stage 2 native helper"]
fn native_loops_calls_parallel_edges_and_failed_starts_match_full_reference() {
    for case in ["loop", "call", "parallel", "missing", "decode", "two-roots"] {
        let mut r = request();
        match case {
            "loop" => {
                let i = r.instructions.get_mut(&0x20).unwrap();
                i.kind = InstructionKind::Conditional;
                i.targets.insert(0x10);
            }
            "call" => {
                let i = r.instructions.get_mut(&0x10).unwrap();
                i.kind = InstructionKind::Call;
                i.targets.insert(u64::MAX);
                i.must_defs.clear();
            }
            "parallel" => {
                let i = r.instructions.get_mut(&0x10).unwrap();
                i.kind = InstructionKind::Conditional;
                i.targets.insert(0x20);
            }
            "missing" => {
                r.captured.remove(&0x20);
            }
            "decode" => {
                r.decodable.remove(&0x20);
            }
            "two-roots" => {
                r.entry_points.insert(u64::MAX);
            }
            _ => unreachable!(),
        }
        let mut native = NativeAnalyzer::new(&config(), case, r.clone()).unwrap();
        let mut reference = Analyzer::new(r).unwrap();
        let mut count = 0;
        loop {
            assert_eq!(native.state(), reference.state(), "{case}: action {count}");
            let advanced = reference.step();
            assert_eq!(native.step().unwrap(), advanced);
            if !advanced {
                break;
            }
            count += 1;
            assert!(count < 200);
        }
        assert_eq!(native.finish().unwrap(), reference.finish(), "{case}");
    }
}
