#[allow(dead_code)]
mod common;
#[path = "support/scanning_engine.rs"]
mod scanning_engine;
use ariadne::*;
use common::*;
use std::time::Duration;

fn reverse_chain(n: u64) -> AnalysisRequest {
    let mut r = request(&(0..n).collect::<Vec<_>>(), &["memory"]);
    r.entry_points = [n - 1].into();
    r.slice_seeds.clear();
    for a in 0..n {
        r.instructions.insert(
            a,
            instruction(
                if a == 0 {
                    InstructionKind::Stop
                } else {
                    InstructionKind::Ordinary
                },
                &if a == 0 { vec![] } else { vec![a - 1] },
                &[],
                true,
                &[],
                &[],
                &["memory"],
            ),
        );
    }
    r
}
#[test]
fn bounded_completion_avoids_repeated_address_order_waves() {
    for n in [1, 2, 3, 4, 8, 16, 32, 64, 128] {
        let r = reverse_chain(n);
        let limits = CompletionLimits {
            max_actions: 4 * n + 8,
            ..CompletionLimits::default()
        };
        let (result, metrics) = Analyzer::new(r.clone())
            .unwrap()
            .finish_bounded(limits)
            .unwrap();
        assert!(metrics.actions < 4 * n + 8);
        for a in 0..n {
            let mut expected: DefinitionSet = ((a + 1)..n)
                .map(|site| definition("memory", site, DefinitionOrigin::Instruction))
                .collect();
            expected.insert(definition("memory", n - 1, DefinitionOrigin::Entry));
            assert_eq!(result.state.reaching[&a], expected);
        }
        assert_eq!(result, scanning_engine::Analyzer::new(r).unwrap().finish());
    }
}
#[test]
fn compact_completion_resumes_each_legacy_prefix_without_changing_results() {
    let mut r = reverse_chain(12);
    r.entry_points.insert(4);
    r.slice_seeds = [0].into();
    r.instructions.get_mut(&5).unwrap().must_defs = ["memory".into()].into();
    r.instructions.get_mut(&3).unwrap().kind = InstructionKind::Conditional;
    r.instructions.get_mut(&3).unwrap().targets = [7].into();
    let expected = scanning_engine::Analyzer::new(r.clone()).unwrap().finish();
    for prefix in 0..80 {
        let mut analyzer = Analyzer::new(r.clone()).unwrap();
        for _ in 0..prefix {
            analyzer.step();
        }
        let (actual, _) = analyzer
            .finish_bounded(CompletionLimits::default())
            .unwrap();
        assert_eq!(actual, expected, "prefix {prefix}");
    }
}
#[test]
fn completion_limits_refuse_publication_instead_of_returning_partial_state() {
    for limits in [
        CompletionLimits {
            max_actions: 0,
            ..CompletionLimits::default()
        },
        CompletionLimits {
            max_bitmap_words: 0,
            ..CompletionLimits::default()
        },
        CompletionLimits {
            max_definitions: 0,
            ..CompletionLimits::default()
        },
        CompletionLimits {
            max_definition_bytes: 0,
            ..CompletionLimits::default()
        },
        CompletionLimits {
            max_elapsed: Duration::ZERO,
            ..CompletionLimits::default()
        },
    ] {
        assert!(
            Analyzer::new(reverse_chain(8))
                .unwrap()
                .finish_bounded(limits)
                .is_err()
        );
    }
}

#[test]
fn a_completed_prefix_still_respects_the_total_action_budget() {
    let mut analyzer = Analyzer::new(reverse_chain(4)).unwrap();
    while analyzer.step() {}
    let actions = analyzer.metrics().actions;
    assert!(
        analyzer
            .finish_bounded(CompletionLimits {
                max_actions: actions - 1,
                ..CompletionLimits::default()
            })
            .is_err()
    );
    let mut analyzer = Analyzer::new(reverse_chain(4)).unwrap();
    while analyzer.step() {}
    assert!(
        analyzer
            .finish_bounded(CompletionLimits {
                max_actions: actions,
                ..CompletionLimits::default()
            })
            .is_ok()
    );
}

#[test]
fn completion_preserves_cycle_origins_and_excludes_call_only_flow() {
    let mut r = request(&[0, 1, 2, 3], &["memory"]);
    r.entry_points = [0, 3].into();
    r.slice_seeds = [2].into();
    r.instructions.insert(
        0,
        instruction(
            InstructionKind::Call,
            &[1],
            &[3],
            true,
            &["memory"],
            &[],
            &["memory"],
        ),
    );
    r.instructions.insert(
        1,
        instruction(
            InstructionKind::Ordinary,
            &[2],
            &[],
            true,
            &["memory"],
            &[],
            &["memory"],
        ),
    );
    r.instructions.insert(
        2,
        instruction(
            InstructionKind::Jump,
            &[],
            &[0],
            true,
            &["memory"],
            &[],
            &["memory"],
        ),
    );
    r.instructions.insert(
        3,
        instruction(InstructionKind::Stop, &[], &[], true, &["memory"], &[], &[]),
    );
    let expected = scanning_engine::Analyzer::new(r.clone()).unwrap().finish();
    let (actual, _) = Analyzer::new(r)
        .unwrap()
        .finish_bounded(CompletionLimits::default())
        .unwrap();
    assert_eq!(actual, expected);
    assert_eq!(
        actual.state.reaching[&3],
        [definition("memory", 3, DefinitionOrigin::Entry)].into()
    );
    assert_eq!(actual.state.reaching[&1].len(), 4);
}

#[test]
fn completion_matches_independent_reference_on_all_three_node_graphs() {
    let nodes = [0, 7, u64::MAX];
    for mask in 0..512u16 {
        for extra_root in [false, true] {
            for definite in [false, true] {
                let mut r = request(&nodes, &["memory", "x"]);
                if extra_root {
                    r.entry_points.insert(7);
                }
                for (n, &a) in nodes.iter().enumerate() {
                    let targets = nodes
                        .iter()
                        .enumerate()
                        .filter_map(|(m, &b)| (mask & (1 << (n * 3 + m)) != 0).then_some(b))
                        .collect();
                    r.instructions.insert(
                        a,
                        Instruction {
                            kind: InstructionKind::Indirect,
                            targets,
                            complete: mask & 1 != 0,
                            uses: ["memory".into(), "x".into()].into(),
                            may_defs: if n == 1 {
                                ["memory".into(), "x".into()].into()
                            } else {
                                ["memory".into()].into()
                            },
                            must_defs: if definite && n == 1 {
                                ["x".into()].into()
                            } else {
                                LocationSet::new()
                            },
                            ..Instruction::default()
                        },
                    );
                }
                let expected = scanning_engine::Analyzer::new(r.clone()).unwrap().finish();
                let (actual, _) = Analyzer::new(r)
                    .unwrap()
                    .finish_bounded(CompletionLimits::default())
                    .unwrap();
                assert_eq!(
                    actual, expected,
                    "graph {mask} root {extra_root} kill {definite}"
                );
            }
        }
    }
}
