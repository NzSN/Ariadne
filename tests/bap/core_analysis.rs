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
