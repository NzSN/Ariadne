use ariadne::bap::core_protocol::{Observation, Response};
use ariadne::bap::core_session::{CoreConfig, CoreSession};
use serde_json::{Value, json};
use std::path::PathBuf;

const A: &str = "0x0000000000000010";
const B: &str = "0x0000000000000020";
const C: &str = "0x0000000000000030";
const H: &str = "0xfffffffffffffff0";
fn config() -> CoreConfig {
    CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
            }),
    )
}
fn instruction(
    address: &str,
    kind: &str,
    fall: &[&str],
    targets: &[&str],
    complete: bool,
) -> Value {
    json!({"address":address,"kind":kind,"fall":fall,"targets":targets,
        "targets_complete":complete,"uses":[],"may_defs":[],"must_defs":[]})
}
fn fixture(kind: &str) -> Value {
    let (fall, targets) = match kind {
        "ordinary" => (vec![B], vec![]),
        "conditional" => (vec![B], vec![B]),
        "call" => (vec![B], vec![C]),
        "jump" => (vec![], vec![A]),
        _ => (vec![], vec![]),
    };
    json!({"snapshot":"snapshot-one","addresses":[A,B,C,H],"locations":["rax"],
        "entry_points":[A],"slice_seeds":[C],"input_kind":"dump",
        "captured":[A,B,C,H],"file_backed":[],"trusted_fallback":[],"decodable":[A,B,C,H],
        "instructions":[instruction(A,kind,&fall,&targets,false),
        instruction(B,"return",&[],&[],true),instruction(C,"stop",&[],&[],true),
        instruction(H,"return",&[],&[],true)]})
}
fn expected(
    pending: &[&str],
    visited: &[&str],
    decoded: &[&str],
    edges: Value,
    obligations: Value,
) -> Observation {
    serde_json::from_value(
        json!({"phase":"recover","pending":pending,"visited":visited,
        "decoded":decoded,"provenance":([A,B,C,H].map(|a| json!({"address":a,
            "source":if decoded.contains(&a) {"captured"} else {"unavailable"}}))),
        "edges":edges,"obligations":obligations,"slice":[],
        "reaching":([A,B,C,H].map(|a| json!({"address":a,"definitions":[]})))}),
    )
    .unwrap()
}
fn visit(session: &mut CoreSession, address: &str) -> Response {
    session
        .request("advance", json!({"action":"Visit","address":address}))
        .unwrap()
}
fn reset(session: &mut CoreSession) {
    let pid = session.process_id();
    session.request("reset", json!({})).unwrap();
    assert!(
        !PathBuf::from(format!("/proc/{pid}")).exists(),
        "owned child not reaped"
    );
    assert!(session.request("observe", json!({})).is_err());
}

#[test]
#[ignore = "requires explicitly built isolated OCaml helper"]
fn native_full_observations() {
    for kind in [
        "ordinary",
        "conditional",
        "call",
        "jump",
        "indirect",
        "return",
    ] {
        let input = fixture(kind);
        let (mut session, init) =
            CoreSession::start(&config(), kind, "snapshot-one", &input).unwrap();
        assert_eq!(
            init.observation,
            expected(&[A], &[], &[], json!([]), json!([])),
            "Init {kind}"
        );
        assert!(init.attribution.is_empty());
        let (pending, edges, obligations) = match kind {
            "ordinary" => (vec![B], json!([{"src":A,"dst":B,"kind":"next"}]), json!([])),
            "conditional" => (
                vec![B],
                json!([{"src":A,"dst":B,"kind":"fallthrough"},
                {"src":A,"dst":B,"kind":"taken"}]),
                json!([]),
            ),
            "call" => (
                vec![B],
                json!([{"src":A,"dst":B,"kind":"summary"},
                {"src":A,"dst":C,"kind":"call"}]),
                json!([{"site":A,"reason":"call-targets"}]),
            ),
            "jump" => (vec![], json!([{"src":A,"dst":A,"kind":"jump"}]), json!([])),
            "indirect" => (
                vec![],
                json!([]),
                json!([{"site":A,"reason":"indirect-targets"}]),
            ),
            _ => (vec![], json!([]), json!([])),
        };
        let actual = visit(&mut session, A);
        assert_eq!(
            actual.observation,
            expected(&pending, &[A], &[A], edges, obligations),
            "Visit {kind}"
        );
        assert_eq!(actual.action_index, 1);
        let machine: Vec<_> = actual
            .attribution
            .iter()
            .filter(|r| r.origin == "machine")
            .collect();
        assert_eq!(machine.len(), 2);
        assert!(
            machine
                .iter()
                .all(|r| r.va.as_deref() == Some(A) && r.snapshot == "snapshot-one")
        );
        let synthetic = actual
            .attribution
            .iter()
            .find(|r| r.origin == "synthetic")
            .unwrap();
        assert!(synthetic.va.is_none());
        assert_eq!(synthetic.parents.len(), 2);
        for _ in 0..2 {
            let observed = session.request("observe", json!({})).unwrap();
            assert_eq!(
                observed.observation, actual.observation,
                "observe mutated state"
            );
            assert_eq!(observed.attribution, actual.attribution);
            assert_eq!(observed.action_index, 1);
        }
        reset(&mut session);
    }
}

#[test]
#[ignore = "requires explicitly built isolated OCaml helper"]
fn native_failures_and_unsigned_schedule() {
    for (binary, captured, trusted, want) in [
        (true, true, false, "file"),
        (false, true, true, "captured"),
        (false, false, true, "file"),
        (false, false, false, "unavailable"),
    ] {
        let mut input = fixture("ordinary");
        input["input_kind"] = json!(if binary { "binary" } else { "dump" });
        input["file_backed"] = json!([A]);
        input["captured"] = if captured { json!([A]) } else { json!([]) };
        input["trusted_fallback"] = if trusted { json!([A]) } else { json!([]) };
        let (mut session, _) =
            CoreSession::start(&config(), "provenance", "snapshot-one", &input).unwrap();
        let actual = visit(&mut session, A);
        assert_eq!(actual.observation.provenance[0].source, want);
        assert_eq!(actual.observation.decoded.is_empty(), want == "unavailable");
        reset(&mut session);
    }
    for missing in [true, false] {
        let mut input = fixture("ordinary");
        input[if missing { "captured" } else { "decodable" }] = json!([B, C, H]);
        let (mut session, _) =
            CoreSession::start(&config(), "failure", "snapshot-one", &input).unwrap();
        let actual = visit(&mut session, A);
        assert_eq!(
            actual.observation,
            expected(
                &[],
                &[A],
                &[],
                json!([]),
                json!([{"site":A,"reason":if missing {"unavailable"} else {"decode-failed"}}])
            )
        );
        assert!(actual.attribution.is_empty());
        reset(&mut session);
    }
    let mut input = fixture("return");
    input["entry_points"] = json!([H, A]);
    let (mut session, _) =
        CoreSession::start(&config(), "unsigned", "snapshot-one", &input).unwrap();
    assert!(
        visit(&mut session, H).error.is_some(),
        "signed scheduling accepted"
    );
    assert_eq!(
        visit(&mut session, A).observation,
        expected(&[H], &[A], &[A], json!([]), json!([]))
    );
    let high = visit(&mut session, H);
    assert_eq!(
        high.observation,
        expected(&[], &[A, H], &[A, H], json!([]), json!([]))
    );
    assert!(high.attribution.iter().any(|r| r.va.as_deref() == Some(H)));
    reset(&mut session);
}

#[test]
#[ignore = "requires explicitly built isolated OCaml helper"]
fn native_rejections_and_fresh_sessions() {
    for cycle in 0..4 {
        let snapshot = format!("snapshot-{cycle}");
        let mut input = fixture("ordinary");
        input["snapshot"] = json!(snapshot);
        if cycle % 2 == 1 {
            input["captured"] = json!([]);
        }
        let (mut session, init) =
            CoreSession::start(&config(), &snapshot, &snapshot, &input).unwrap();
        assert_eq!(
            init.observation,
            expected(&[A], &[], &[], json!([]), json!([])),
            "reset leaked state"
        );
        for (op, payload) in [
            ("finish", json!({})),
            ("initialize", json!({})),
            ("advance", json!({"action":"FinishRecovery"})),
            ("advance", json!({"action":"Propagate","address":A})),
            ("advance", json!({"action":"Visit","address":B})),
            ("observe", json!({"unknown":true})),
        ] {
            let rejected = session.request(op, payload).unwrap();
            assert!(rejected.error.is_some());
            assert_eq!(rejected.observation, init.observation);
            assert_eq!(rejected.action_index, 0);
        }
        let first = visit(&mut session, A);
        assert_eq!(first.observation.decoded.is_empty(), cycle % 2 == 1);
        reset(&mut session);
    }
    let (mut first, _) =
        CoreSession::start(&config(), "first", "snapshot-one", &fixture("ordinary")).unwrap();
    let (mut second, init) =
        CoreSession::start(&config(), "second", "snapshot-one", &fixture("call")).unwrap();
    visit(&mut first, A);
    assert!(
        first
            .request("observe", json!({"oversize":"x".repeat(8*1024*1024)}))
            .is_err()
    );
    assert_eq!(
        second.request("observe", json!({})).unwrap().observation,
        init.observation
    );
    visit(&mut second, A);
    reset(&mut second);
}

#[test]
#[ignore = "requires explicitly built isolated OCaml helper"]
fn native_input_admission() {
    let controls = [
        ("entry_points", json!([])),
        ("entry_points", json!(["0x1"])),
        ("addresses", json!([A, A])),
        ("snapshot", json!("wrong")),
        ("trusted_fallback", json!([A])),
        ("instructions", json!([])),
        ("decodable", json!(["0x0000000000000099"])),
        ("unknown", json!(true)),
    ];
    for (key, value) in controls {
        let mut input = fixture("ordinary");
        input[key] = value;
        assert!(
            CoreSession::start(&config(), "invalid", "snapshot-one", &input).is_err(),
            "accepted {key}"
        );
    }
    for (key, value) in [
        ("fall", json!([])),
        ("targets", json!([B])),
        ("must_defs", json!(["rax"])),
        ("uses", json!(["unknown"])),
        ("targets_complete", json!("true")),
        ("kind", json!("unknown")),
        ("address", json!(B)),
    ] {
        let mut input = fixture("ordinary");
        input["instructions"][0][key] = value;
        assert!(
            CoreSession::start(&config(), "invalid", "snapshot-one", &input).is_err(),
            "accepted instruction {key}"
        );
    }
}

#[cfg(unix)]
#[test]
#[ignore = "requires the qualified helper manifest and Python failure fixtures"]
fn transport_failure_controls() {
    use std::os::unix::fs::PermissionsExt;
    use std::time::Duration;
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target/bap-core-transport-fixtures")
        .join(std::process::id().to_string());
    std::fs::create_dir_all(&root).unwrap();
    let real_manifest: Value =
        serde_json::from_slice(&std::fs::read(config().manifest).unwrap()).unwrap();
    for mode in [
        "query",
        "snapshot",
        "session",
        "family",
        "sequence",
        "partial",
        "eof",
        "oversized",
        "timeout",
        "broken-pipe",
        "exception",
        "nonzero-reset",
        "rejected-reset",
    ] {
        let directory = root.join(mode);
        std::fs::create_dir_all(&directory).unwrap();
        let script = directory.join("ariadne-bap-core");
        let source = format!(
            r##"#!/usr/bin/python3
import json,sys,time,os
mode={mode:?}
ready=json.loads({ready:?})
print(json.dumps(ready),flush=True)
if mode=='broken-pipe': sys.exit(2)
for line in sys.stdin:
    q=json.loads(line)
    if mode=='timeout': time.sleep(30)
    if mode=='exception': raise RuntimeError('controlled native exception')
    if mode=='eof': sys.exit(0)
    if mode=='partial':
        sys.stdout.write('{{');sys.stdout.flush();sys.exit(0)
    if mode=='oversized':
        sys.stdout.write('x'*(8*1024*1024+1));sys.stdout.flush();sys.exit(0)
    response={{k:q[k] for k in ['schema','session','snapshot','query','family','sequence']}}
    response.update(generation=1,action_index=0,changed=False,
        observation=json.loads({observation:?}),attribution=[],error=None)
    if mode in ['query','snapshot','session','family']: response[mode]='stale'
    if mode=='sequence': response['sequence']+=1
    if mode=='rejected-reset' and q['operation']=='reset': response['error']={{'kind':'semantic','message':'rejected reset'}}
    print(json.dumps(response),flush=True)
    if q['operation']=='reset': sys.exit(0 if mode=='rejected-reset' else 9)
"##,
            ready = real_manifest["handshake"].to_string(),
            observation =
                serde_json::to_string(&expected(&[A], &[], &[], json!([]), json!([]))).unwrap()
        );
        std::fs::write(&script, source).unwrap();
        std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
        let mut manifest = real_manifest.clone();
        manifest["helper_sha256"] =
            json!(ariadne::reports::sha256(&std::fs::read(&script).unwrap()));
        std::fs::write(directory.join("manifest.json"), manifest.to_string()).unwrap();
        let mut config = CoreConfig::from_directory(directory);
        config.timeout = Duration::from_millis(300);
        let started = CoreSession::start(&config, "fault", "snapshot-one", &fixture("ordinary"));
        if ["nonzero-reset", "rejected-reset"].contains(&mode) {
            let (mut session, _) = started.unwrap();
            let pid = session.process_id();
            assert!(session.request("reset", json!({})).is_err());
            assert!(!PathBuf::from(format!("/proc/{pid}")).exists());
            assert!(session.request("observe", json!({})).is_err());
        } else {
            assert!(started.is_err(), "accepted transport fault: {mode}");
        }
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
#[ignore = "requires explicitly built isolated OCaml helper"]
fn rust_reference_crosscheck() {
    use ariadne::{
        AnalysisRequest, Analyzer, ByteSource, EdgeKind, InputKind, Instruction, InstructionKind,
        ObligationReason, Phase,
    };
    let address = |s: &str| u64::from_str_radix(&s[2..], 16).unwrap();
    let hex = |a: u64| format!("0x{a:016x}");
    for (name, kind) in [
        ("ordinary", InstructionKind::Ordinary),
        ("conditional", InstructionKind::Conditional),
        ("call", InstructionKind::Call),
        ("jump", InstructionKind::Jump),
        ("indirect", InstructionKind::Indirect),
    ] {
        let input = fixture(name);
        let aset = |j: &Value| {
            j.as_array()
                .unwrap()
                .iter()
                .map(|v| address(v.as_str().unwrap()))
                .collect()
        };
        let request = AnalysisRequest {
            snapshot_id: "snapshot-one".into(),
            addresses: aset(&input["addresses"]),
            locations: ["rax".into()].into(),
            entry_points: [address(A)].into(),
            slice_seeds: [address(C)].into(),
            input_kind: InputKind::Dump,
            captured: aset(&input["captured"]),
            decodable: aset(&input["decodable"]),
            instructions: input["instructions"]
                .as_array()
                .unwrap()
                .iter()
                .enumerate()
                .map(|(n, row)| {
                    (
                        address(row["address"].as_str().unwrap()),
                        Instruction {
                            kind: if n == 0 {
                                kind
                            } else if n == 2 {
                                InstructionKind::Stop
                            } else {
                                InstructionKind::Return
                            },
                            fall: aset(&row["fall"]),
                            targets: aset(&row["targets"]),
                            complete: n != 0,
                            ..Instruction::default()
                        },
                    )
                })
                .collect(),
            ..AnalysisRequest::default()
        };
        let mut reference = Analyzer::new(request).unwrap();
        let (mut session, mut actual) =
            CoreSession::start(&config(), name, "snapshot-one", &input).unwrap();
        loop {
            let state = reference.state();
            assert_eq!(state.phase, Phase::Recover);
            let strings =
                |set: &ariadne::AddressSet| set.iter().map(|a| hex(*a)).collect::<Vec<_>>();
            assert_eq!(actual.observation.pending, strings(&state.pending));
            assert_eq!(actual.observation.visited, strings(&state.visited));
            assert_eq!(actual.observation.decoded, strings(&state.decoded));
            assert_eq!(actual.observation.slice, strings(&state.slice));
            assert_eq!(actual.observation.phase, "recover");
            assert_eq!(actual.observation.provenance.len(), state.provenance.len());
            for row in &actual.observation.provenance {
                assert_eq!(
                    row.source,
                    match state.provenance[&address(&row.address)] {
                        ByteSource::Captured => "captured",
                        ByteSource::File => "file",
                        ByteSource::Unavailable => "unavailable",
                    }
                );
            }
            let mut edges = state
                .edges
                .iter()
                .map(|e| {
                    (
                        hex(e.src),
                        hex(e.dst),
                        match e.kind {
                            EdgeKind::Next => "next",
                            EdgeKind::Taken => "taken",
                            EdgeKind::Fallthrough => "fallthrough",
                            EdgeKind::Jump => "jump",
                            EdgeKind::Indirect => "indirect",
                            EdgeKind::Summary => "summary",
                            EdgeKind::Call => "call",
                        }
                        .to_owned(),
                    )
                })
                .collect::<Vec<_>>();
            edges.sort();
            assert_eq!(
                actual
                    .observation
                    .edges
                    .iter()
                    .map(|e| (e.src.clone(), e.dst.clone(), e.kind.clone()))
                    .collect::<Vec<_>>(),
                edges
            );
            let obligations = state
                .obligations
                .iter()
                .map(|o| {
                    (
                        hex(o.site),
                        match o.reason {
                            ObligationReason::Unavailable => "unavailable",
                            ObligationReason::DecodeFailed => "decode-failed",
                            ObligationReason::IndirectTargets => "indirect-targets",
                            ObligationReason::CallTargets => "call-targets",
                        }
                        .to_owned(),
                    )
                })
                .collect::<Vec<_>>();
            assert_eq!(
                actual
                    .observation
                    .obligations
                    .iter()
                    .map(|o| (o.site.clone(), o.reason.clone()))
                    .collect::<Vec<_>>(),
                obligations
            );
            assert_eq!(actual.observation.reaching.len(), state.reaching.len());
            for row in &actual.observation.reaching {
                assert!(row.definitions.is_empty());
                assert!(state.reaching[&address(&row.address)].is_empty());
            }
            let Some(next) = state.pending.first().copied() else {
                break;
            };
            reference.step();
            actual = visit(&mut session, &hex(next));
        }
        reset(&mut session);
    }
}
