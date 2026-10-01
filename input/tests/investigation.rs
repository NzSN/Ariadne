mod common;
use ariadne::{Analyzer, effects::PreparationOptions};
use ariadne_input::{
    AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits, investigation::bind_investigation,
};
use ariadne_investigation::{
    AnswerStatus, Assertion, ExplainLimits, FaultAddressQuestion, OriginKind,
};
use std::{path::PathBuf, process::Command};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}
fn prepare(
    snapshot: &FileSnapshot,
    entries: &[u64],
    seeds: &[u64],
) -> (ariadne_input::FilePreparedAnalysis, Analyzer) {
    let p = snapshot
        .prepare(
            &AnalysisQuery {
                entry_points: entries.iter().copied().collect(),
                slice_seeds: seeds.iter().copied().collect(),
            },
            &std::env::var_os("ARIADNE_LLVM_MC")
                .map(PathBuf::from)
                .unwrap_or_else(|| root().join("target/ariadne-llvm-mc")),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    let mut a = Analyzer::new(p.prepared.request.clone()).unwrap();
    while a.step() {}
    (p, a)
}
fn explain(
    p: &ariadne_input::FilePreparedAnalysis,
    a: &Analyzer,
    site: u64,
) -> ariadne_investigation::Explanation {
    let b = bind_investigation(p, a).unwrap();
    ariadne_investigation::explain_fault_address(
        &b,
        FaultAddressQuestion {
            site,
            memory_access: 0,
        },
        ExplainLimits::default(),
    )
    .unwrap()
}
#[test]
#[ignore = "requires pinned BAP/MC helpers"]
fn both_platforms_explain_address_producer_and_preserve_dump_offsets() {
    for (name, entry) in [
        ("stage_b_linux.dmp", 0x401000),
        ("stage_b_windows.dmp", 0x7ff700001000),
    ] {
        let s = FileSnapshot::open_minidump(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("tests/fixtures")
                .join(name),
            OpenLimits::default(),
        )
        .unwrap();
        let (p, a) = prepare(&s, &[entry], &[entry + 6]);
        let e = explain(&p, &a, entry + 6);
        assert_eq!(e.status, AnswerStatus::Partial);
        assert_eq!(e.origins.len(), 8);
        assert!(
            e.origins
                .iter()
                .all(|g| g.producers.len() == 1 && g.producers[0].site == entry)
        );
        assert!(
            e.origins
                .iter()
                .all(|g| !g.producers.iter().any(|p| p.site == entry + 3))
        );
        assert!(e.evidence.iter().any(|v| v.instruction.va == entry
            && v.instruction.spans[0].contributors[0].file_offset
                == p.reads[&entry].spans[0].contributors[0].file_offset));
        assert!(
            e.evidence_requirements
                .iter()
                .any(|r| r.code == "entry-origin"
                    && r.locations.iter().any(|l| l.starts_with("gpr:rbx:")))
        );
    }
}
#[test]
#[ignore = "requires pinned native helpers"]
fn aliases_joins_calls_and_weak_memory_keep_alternatives() {
    let cases: Vec<(Vec<u8>, u64)> = vec![
        (
            vec![0x48, 0x89, 0xd8, 0x88, 0xd4, 0xc7, 0x00, 5, 0, 0, 0, 0xc3],
            0x1005,
        ),
        (
            vec![
                0x75, 5, 0x48, 0x89, 0xd8, 0xeb, 3, 0x48, 0x89, 0xd0, 0xc7, 0x00, 5, 0, 0, 0, 0xc3,
            ],
            0x100a,
        ),
        (
            vec![
                0x48, 0x89, 0xd8, 0xe8, 0, 0, 0, 0, 0xc7, 0, 5, 0, 0, 0, 0xc3,
            ],
            0x1008,
        ),
        (vec![0x48, 0x8b, 0x03, 0xc7, 0, 5, 0, 0, 0, 0xc3], 0x1003),
    ];
    for (i, (code, seed)) in cases.into_iter().enumerate() {
        let mut d = common::Dump::new(true);
        d.memory(&[(0x1000, &code)]);
        let s = FileSnapshot::from_minidump_bytes(d.finish(), OpenLimits::default()).unwrap();
        let (p, a) = prepare(&s, &[0x1000], &[seed]);
        let e = explain(&p, &a, seed);
        match i {
            0 => {
                let high = e
                    .origins
                    .iter()
                    .find(|g| g.location == "gpr:rax:1")
                    .unwrap();
                assert_eq!(high.producers[0].site, 0x1003);
                let low = e
                    .origins
                    .iter()
                    .find(|g| g.location == "gpr:rax:0")
                    .unwrap();
                assert_eq!(low.producers[0].site, 0x1000);
            }
            1 => {
                assert!(e.origins.iter().all(|g| {
                    g.producers
                        .iter()
                        .map(|p| p.site)
                        .collect::<std::collections::BTreeSet<_>>()
                        == [0x1002, 0x1007].into()
                }));
            }
            2 => {
                assert!(
                    e.origins
                        .iter()
                        .all(|g| g.producers.iter().any(|p| p.site == 0x1000)
                            && g.producers.iter().any(|p| p.site == 0x1003))
                );
                assert!(e.gaps.iter().any(|g| g.code == "opaque-call"));
            }
            _ => assert!(e.gaps.iter().any(|g| g.code == "unknown-memory-alias")),
        }
        assert!(
            e.claims
                .iter()
                .filter(|c| matches!(c.assertion, Assertion::PossibleOrigin { .. }))
                .all(|c| c.classification
                    == ariadne_investigation::Classification::DerivedUnderPremises)
        );
    }
}
#[test]
#[ignore = "requires pinned native helpers"]
fn exact_query_binding_and_unavailable_conflict_are_retained() {
    let mut d = common::Dump::new(true);
    d.memory(&[
        (0x1000, &[0x48, 0x89, 0xd8, 0xc7, 0, 5, 0, 0, 0, 0xc3]),
        (0x3000, &[0x48, 0x89, 0xd8]),
        (0x3001, &[0xff]),
    ]);
    let s = FileSnapshot::from_minidump_bytes(d.finish(), OpenLimits::default()).unwrap();
    let (p, a) = prepare(&s, &[0x1000, 0x3000, 0x4000], &[0x1003, 0x3000, 0x4000]);
    let (_, other) = prepare(&s, &[0x1000], &[0x1000]);
    assert!(bind_investigation(&p, &other).is_err());
    let mut bad = p.clone();
    bad.materialization.query_identity = "0".repeat(64);
    assert!(bind_investigation(&bad, &a).is_err());
    for site in [0x3000, 0x4000] {
        let e = explain(&p, &a, site);
        assert_eq!(e.status, AnswerStatus::Unavailable);
        assert!(e.gaps.iter().any(|g| g.code == "not-reached"));
    }
    assert!(p.reads[&0x3000].conflict_sources.len() > 1);
}
#[test]
#[ignore = "requires pinned native helpers"]
fn not_chain_reports_are_versioned_strict_and_transactionally_published() {
    let out =
        std::env::temp_dir().join(format!("ariadne-investigation-cli-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&out);
    let r = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .arg(
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("tests/fixtures/bap_precision_linux.dmp"),
        )
        .arg("--decoder-reference")
        .arg(root().join("target/ariadne-llvm-mc"))
        .args([
            "--entry",
            "0x401000",
            "--explain-fault-address",
            "0x401006",
            "--memory-access",
            "0",
            "--output-dir",
        ])
        .arg(&out)
        .output()
        .unwrap();
    assert!(r.status.success(), "{}", String::from_utf8_lossy(&r.stderr));
    let bytes = std::fs::read(out.join("explanation.json")).unwrap();
    let e = ariadne_reports::decode_explanation(&bytes).unwrap();
    assert!(e.origins.iter().all(|g| g.producers[0].site == 0x401003));
    assert!(e.claims.iter().any(|c| matches!(
        c.assertion,
        Assertion::Dependency {
            producer: ariadne_investigation::Producer {
                site: 0x401000,
                origin: OriginKind::Instruction,
                ..
            },
            ..
        }
    )));
    let text = std::fs::read_to_string(out.join("explanation.txt")).unwrap();
    assert!(
        text.contains("Possible origins")
            && text.contains("Required evidence")
            && text.contains("not an execution witness")
    );
    let dot = std::fs::read_to_string(out.join("explanation.dot")).unwrap();
    assert!(dot.contains(&e.identity.query_id));
    assert!(out.join("report.json").is_file());
    let duplicate = b"{\"schema\":\"x\",\"schema\":\"y\"}";
    assert!(ariadne_reports::decode_explanation(duplicate).is_err());
    std::fs::remove_dir_all(out).unwrap();
}
#[test]
fn malformed_question_flags_do_not_publish() {
    let r = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"))
        .args([
            "/unused",
            "--decoder-reference",
            "/unused",
            "--entry",
            "0x1000",
            "--explain-fault-address",
            "0x1000",
            "--format",
            "json",
        ])
        .output()
        .unwrap();
    assert!(!r.status.success());
    assert!(r.stdout.is_empty());
}
