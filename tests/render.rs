mod common;
use ariadne::render::{Format, render};
use ariadne::*;
use common::{definition, instruction, request, run_checked};
fn pipeline() -> AnalysisResult {
    let mut r = request(&[4096, 4100], &["x"]);
    r.snapshot_id = "pipeline-snapshot".into();
    r.instructions.insert(
        4096,
        instruction(
            InstructionKind::Ordinary,
            &[4100],
            &[],
            true,
            &[],
            &["x"],
            &["x"],
        ),
    );
    r.instructions.insert(
        4100,
        instruction(InstructionKind::Return, &[], &[], true, &["x"], &[], &[]),
    );
    run_checked(r)
}
#[test]
fn complete_result_is_readable_deterministic_and_unchanged() {
    let result = pipeline();
    let before = result.clone();
    assert!(result.state.reaching[&4096].contains(&definition("x", 4096, DefinitionOrigin::Entry)));
    let text = render(&result, Format::Text);
    for expected in [
        "snapshot: \"pipeline-snapshot\"",
        "phase: done",
        "scope_closed: true (recovery only; relative to supplied inputs)",
        "pending: []",
        "visited: [0x0000000000001000, 0x0000000000001004]",
        "decoded: [0x0000000000001000, 0x0000000000001004]",
        "data_slice: [0x0000000000001000, 0x0000000000001004]",
        "missing_slice_seeds: []",
        "0x0000000000001000 --next--> 0x0000000000001004",
        "\"x\" <- entry@0x0000000000001000",
        "\"x\" <- instruction@0x0000000000001000",
        "Unresolved recovery obligations:\n  (none)",
    ] {
        assert!(text.contains(expected), "missing {expected}");
    }
    for format in [Format::Text, Format::Dot] {
        assert_eq!(render(&result, format), render(&result, format));
    }
    assert_eq!(result, before);
}
#[test]
fn unvisited_callee_and_failed_continuation_are_distinguished() {
    let mut r = request(&[1, 2, 9], &["x"]);
    r.slice_seeds = [1, 9].into();
    r.file_backed.remove(&2);
    r.instructions.insert(
        1,
        instruction(
            InstructionKind::Call,
            &[2],
            &[9],
            false,
            &["x"],
            &[],
            &["x"],
        ),
    );
    let result = analyze(r).unwrap();
    let text = render(&result, Format::Text);
    let dot = render(&result, Format::Dot);
    assert!(text.contains("0x0000000000000009: unvisited; source=no successful decode"));
    assert!(text.contains("0x0000000000000002: visited, not decoded"));
    assert!(text.contains("0x0000000000000001: call-targets"));
    assert!(text.contains("0x0000000000000002: unavailable"));
    assert!(text.contains("--call--> 0x0000000000000009 [excluded from local discovery/dataflow]"));
    assert!(dot.contains("label=\"call\", style=\"dashed\""));
    assert!(dot.contains("label=\"summary\", style=\"solid\""));
    assert!(dot.contains("missing slice seed"));
    assert_eq!(dot.matches(" -> ").count(), result.state.edges.len());
}
#[test]
fn missing_seed_does_not_become_a_recovery_failure_or_disappear() {
    let mut r = request(&[1, 9], &[]);
    r.slice_seeds = [9].into();
    let result = analyze(r).unwrap();
    assert!(result.scope_closed());
    assert_eq!(result.missing_slice_seeds, [9].into());
    let text = render(&result, Format::Text);
    assert!(text.contains("scope_closed: true (recovery only"));
    assert!(text.contains("missing_slice_seeds: [0x0000000000000009]"));
    assert!(render(&result, Format::Dot).contains("missing slice seeds: 1"));
}
#[test]
fn parallel_control_labels_survive_and_reaching_facts_do_not_invent_edges() {
    let mut r = request(&[0, u64::MAX], &["x"]);
    r.instructions.insert(
        0,
        instruction(
            InstructionKind::Conditional,
            &[u64::MAX],
            &[u64::MAX],
            true,
            &[],
            &["x"],
            &["x"],
        ),
    );
    r.instructions.insert(
        u64::MAX,
        instruction(InstructionKind::Return, &[], &[], true, &[], &[], &[]),
    );
    let result = analyze(r).unwrap();
    let dot = render(&result, Format::Dot);
    assert!(dot.starts_with("digraph Ariadne {"));
    assert!(!dot.starts_with("strict"));
    assert_eq!(
        dot.matches("n_0000000000000000 -> n_ffffffffffffffff")
            .count(),
        2
    );
    assert!(dot.contains("label=\"taken\""));
    assert!(dot.contains("label=\"fallthrough\""));
    assert!(dot.contains("instruction@0x0000000000000000"));
    assert_eq!(dot.matches(" -> ").count(), 2);
}
fn hostile() -> AnalysisResult {
    let mut r = request(&[0, u64::MAX], &["name\"\\N\n\t\0<&>"]);
    r.snapshot_id = "snapshot\"; evil -> target; //\n\\G\r\u{1b}<b>".into();
    r.instructions.insert(
        0,
        instruction(
            InstructionKind::Ordinary,
            &[u64::MAX],
            &[],
            true,
            &[],
            &["name\"\\N\n\t\0<&>"],
            &["name\"\\N\n\t\0<&>"],
        ),
    );
    analyze(r).unwrap()
}
#[test]
fn metadata_is_quoted_and_cannot_create_output_records() {
    let result = hostile();
    let text = render(&result, Format::Text);
    let dot = render(&result, Format::Dot);
    assert!(!text.contains('\0'));
    assert!(!text.contains('\u{1b}'));
    assert!(text.contains("\\u{0}"));
    assert!(!dot.contains('\0'));
    assert!(!dot.contains('\u{1b}'));
    assert!(dot.contains("\\\\N"));
    assert!(dot.contains("0xffffffffffffffff"));
    assert_eq!(dot.lines().filter(|l| l.starts_with("  n_")).count(), 3);
}
#[test]
fn initial_and_intermediate_state_fields_are_not_labeled_done() {
    let r = request(&[1], &[]);
    let analyzer = Analyzer::new(r).unwrap();
    let result = AnalysisResult {
        snapshot_id: "live-state".into(),
        state: analyzer.state().clone(),
        missing_slice_seeds: AddressSet::new(),
    };
    let text = render(&result, Format::Text);
    assert!(text.contains("phase: recover"));
    assert!(text.contains("pending: [0x0000000000000001]"));
    assert!(text.contains("0x0000000000000001: pending; source=no successful decode"));
    assert!(text.contains("scope_closed: false"));
}

#[test]
#[ignore = "requires Graphviz; set ARIADNE_DOT to the dot executable"]
fn graphviz_parses_escaped_labels_without_extra_nodes_or_edges() {
    use std::io::Write;
    use std::process::{Command, Stdio};
    let executable = std::env::var_os("ARIADNE_DOT").expect("set ARIADNE_DOT");
    let result = hostile();
    let dot = render(&result, Format::Dot);
    let mut child = Command::new(executable)
        .arg("-Tplain")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(dot.as_bytes())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let parsed = String::from_utf8(out.stdout).unwrap();
    assert_eq!(parsed.lines().filter(|l| l.starts_with("node ")).count(), 2);
    assert_eq!(parsed.lines().filter(|l| l.starts_with("edge ")).count(), 1);
    assert!(parsed.contains("node n_ffffffffffffffff "));
}

#[test]
fn every_recovery_gap_and_captured_provenance_survives_rendering() {
    let mut r = request(&[1, 2, 3, 9, 10, 20], &["x"]);
    r.input_kind = InputKind::Dump;
    r.entry_points = [1, 9].into();
    r.captured = [1, 2, 9, 10].into();
    r.decodable = [1, 3, 9, 10].into();
    r.slice_seeds = [1, 9, 20].into();
    r.instructions.insert(
        1,
        instruction(
            InstructionKind::Indirect,
            &[],
            &[2, 3],
            false,
            &["x"],
            &[],
            &[],
        ),
    );
    r.instructions.insert(
        9,
        instruction(
            InstructionKind::Call,
            &[10],
            &[20],
            false,
            &["x"],
            &[],
            &["x"],
        ),
    );
    let result = analyze(r).unwrap();
    assert_eq!(result.state.obligations.len(), 4);
    for format in [Format::Text, Format::Dot] {
        let output = render(&result, format);
        for reason in [
            "indirect-targets",
            "decode-failed",
            "unavailable",
            "call-targets",
        ] {
            assert!(output.contains(reason), "{reason}");
        }
        assert!(output.contains("captured"));
        assert!(output.contains("missing slice seed"));
    }
}
