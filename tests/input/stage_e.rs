use ariadne::effects::PreparationOptions;
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use ariadne::machine_state as ms;
use std::path::{Path, PathBuf};
use std::process::Command;

fn scratch() -> PathBuf {
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "ariadne-stage-e-cli-{}-{nonce}",
        std::process::id()
    ));
    std::fs::create_dir(&path).unwrap();
    path
}
fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/input/fixtures")
        .join(name)
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .expect("native gate supplies decoder")
        .into()
}

#[test]
#[ignore = "requires pinned native decoder"]
fn minidump_stateflow_reports_preserve_identity_graph_and_uncertainty_on_both_platforms() {
    for (name, entry) in [
        ("stage_b_linux.dmp", 0x401000u64),
        ("stage_b_windows.dmp", 0x7ff700001000u64),
    ] {
        let tmp = scratch();
        let dump = fixture(name);
        let decoder = decoder();
        let snapshot = FileSnapshot::open_minidump(&dump, OpenLimits::default()).unwrap();
        let prepared = snapshot
            .prepare(
                &AnalysisQuery {
                    entry_points: [entry].into(),
                    slice_seeds: [entry + 6, entry + 0x100].into(),
                },
                &decoder,
                &PreparationOptions::default(),
                PrepareLimits::default(),
            )
            .unwrap();
        let mut recovery = ariadne::Analyzer::new(prepared.prepared.request.clone()).unwrap();
        while recovery.step() {}
        let domain = prepared
            .prepared
            .request
            .locations
            .iter()
            .map(|l| (l.clone(), [ms::AbstractValue("unknown".into())].into()))
            .collect::<std::collections::BTreeMap<_, _>>();
        let valuations = domain.clone();
        let edges: ariadne::EdgeSet = recovery
            .state()
            .edges
            .iter()
            .filter(|e| e.kind.is_local())
            .copied()
            .collect();
        let semantics = ms::SemanticInputs {
            snapshot_id: prepared.prepared.request.snapshot_id.clone(),
            value_domain: domain,
            catalogue: [
                (
                    ms::StateId("live".into()),
                    ms::AbstractState {
                        status: ms::Status::Running,
                        valuation: valuations.clone(),
                    },
                ),
                (
                    ms::StateId("returned".into()),
                    ms::AbstractState {
                        status: ms::Status::Returned,
                        valuation: valuations,
                    },
                ),
            ]
            .into(),
            entry_states: [(entry, [ms::StateId("live".into())].into())].into(),
            steps: edges
                .iter()
                .map(|&edge| ms::StateStep {
                    edge,
                    before: ms::StateId("live".into()),
                    after: ms::StateId("live".into()),
                })
                .collect(),
            terminal_transitions: [ms::TerminalTransition {
                site: entry + 12,
                before: ms::StateId("live".into()),
                after: ms::StateId("returned".into()),
                outcome: ms::TerminalOutcome::Returned,
            }]
            .into(),
            complete_sites: Default::default(),
            adapter_obligations: Default::default(),
        };
        let handoff = ms::prepare_from_recovery(&recovery, semantics).unwrap();
        let input = ariadne::reports::encode_semantics(&handoff.request).unwrap();
        let input_path = tmp.join("semantics.json");
        std::fs::write(&input_path, serde_json::to_vec(&input).unwrap()).unwrap();
        let output_path = tmp.join("reports");
        let run = |output: &Path| {
            Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
                .arg(&dump)
                .arg("--decoder")
                .arg(&decoder)
                .arg("--entry")
                .arg(format!("0x{entry:x}"))
                .arg("--seed")
                .arg(format!("0x{:x}", entry + 6))
                .arg("--seed")
                .arg(format!("0x{:x}", entry + 0x100))
                .arg("--stateflow-input")
                .arg(&input_path)
                .arg("--output-dir")
                .arg(output)
                .output()
                .unwrap()
        };
        let result = run(&output_path);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let dot_binary =
            std::env::var_os("ARIADNE_DOT").expect("completion gate supplies Graphviz");
        let parsed = Command::new(&dot_binary)
            .arg("-Tdot")
            .arg(output_path.join("report.dot"))
            .output()
            .unwrap();
        assert!(
            parsed.status.success(),
            "{}",
            String::from_utf8_lossy(&parsed.stderr)
        );
        let parsed = Command::new(&dot_binary)
            .arg("-Tdot")
            .arg(output_path.join("machine-state.dot"))
            .output()
            .unwrap();
        assert!(
            parsed.status.success(),
            "{}",
            String::from_utf8_lossy(&parsed.stderr)
        );
        let report: serde_json::Value =
            serde_json::from_slice(&std::fs::read(output_path.join("machine-state.json")).unwrap())
                .unwrap();
        assert_eq!(
            report["identity"]["snapshot_id"],
            handoff.request.snapshot_id
        );
        assert_eq!(report["schema"], "ariadne.machine-state-report/v1");
        assert_eq!(
            report["minidump_report"]["schema"],
            "ariadne-minidump-report-v1"
        );
        assert!(
            !report["minidump_report"]["preparation"]["gaps"]
                .as_array()
                .unwrap()
                .is_empty()
        );
        assert_eq!(
            report["recovery"]["full_edges"].as_array().unwrap().len(),
            recovery.state().edges.len()
        );
        assert_eq!(
            report["obligations"].as_array().unwrap().len(),
            handoff.request.nodes.len()
        );
        assert_eq!(
            report["recovery"]["missing_slice_seeds"],
            serde_json::json!([format!("0x{:016x}", entry + 0x100)])
        );
        assert_eq!(report["terminals"].as_array().unwrap().len(), 1);
        for file in [
            "report.txt",
            "report.dot",
            "report.json",
            "machine-state.txt",
            "machine-state.dot",
            "machine-state.json",
        ] {
            assert!(output_path.join(file).is_file());
        }
        let text = std::fs::read_to_string(output_path.join("machine-state.txt")).unwrap();
        let dot = std::fs::read_to_string(output_path.join("machine-state.dot")).unwrap();
        assert!(text.contains("incomplete-semantics") && dot.contains("incomplete-semantics"));
        let mut wrong = input.clone();
        wrong["snapshot_id"] = "wrong".into();
        std::fs::write(&input_path, serde_json::to_vec(&wrong).unwrap()).unwrap();
        let bad = tmp.join("bad");
        assert!(!run(&bad).status.success());
        assert!(!bad.exists());
        std::fs::write(&input_path, b"{\"schema\":\"x\",\"schema\":\"y\"}").unwrap();
        assert!(!run(&bad).status.success());
        assert!(!bad.exists());
        std::fs::remove_dir_all(tmp).unwrap();
    }
}
