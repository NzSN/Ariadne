use super::*;
use crate::bap::ast::Lift;

fn dispatch() -> (BTreeMap<u64, Instruction>, BTreeMap<u64, Transfer>) {
    let corpus: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/target-resolution-bil.json")).unwrap();
    let mut instructions = BTreeMap::new();
    let mut transfers = BTreeMap::new();
    for row in corpus["rows"].as_array().unwrap() {
        if row["schema"] != "ariadne.bap-site/v1" {
            continue;
        }
        let lift: Lift = serde_json::from_value(row.clone()).unwrap();
        lift.validate_ast().unwrap();
        let va = u64::from_str_radix(lift.va.trim_start_matches("0x"), 16).unwrap();
        let bytes = decode_bytes(&lift.bytes).unwrap();
        let p =
            crate::bap::projection::project(&lift.bil, lift.opcode.as_deref().unwrap(), &bytes, va)
                .unwrap();
        let props = lift.properties.as_ref().unwrap();
        let kind = if props.indirect {
            InstructionKind::Indirect
        } else if props.conditional {
            InstructionKind::Conditional
        } else {
            InstructionKind::Ordinary
        };
        instructions.insert(
            va,
            Instruction {
                kind,
                fall: if kind == InstructionKind::Indirect {
                    AddressSet::new()
                } else {
                    [va + u64::from(lift.length)].into()
                },
                targets: p.targets.into_iter().flatten().collect(),
                complete: kind != InstructionKind::Indirect,
                uses: p.uses,
                may_defs: p.may_defs,
                must_defs: p.must_defs,
            },
        );
        transfers.insert(va, extract(&lift.bil, va, &bytes).unwrap());
    }
    (instructions, transfers)
}
fn table_read(slot: u64, width: usize) -> Result<DataRead, Error> {
    let table = include_bytes!("fixtures/target-resolution-table.bin");
    let base = 0x7ff64791ef58;
    let offset = slot.checked_sub(base).and_then(|v| usize::try_from(v).ok());
    let data = offset.and_then(|n| table.get(n..n + width)).unwrap_or(&[]);
    Ok(DataRead {
        address: hex(slot),
        requested: width,
        bytes_hex: data.iter().map(|b| format!("{b:02x}")).collect(),
        spans: if data.is_empty() {
            Vec::new()
        } else {
            vec![Span {
                address: hex(slot),
                length: data.len(),
                contributors: vec![Contributor {
                    stream: 9,
                    entry: 2678,
                    file_offset: 1201054376 + offset.unwrap() as u64,
                }],
            }]
        },
        conflict_sources: Vec::new(),
        stop: if data.len() == width {
            "RequestedLength"
        } else {
            "not_captured"
        }
        .into(),
    })
}
#[test]
fn admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage() {
    let (instructions, transfers) = dispatch();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &[0x7ff640079640].into(),
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    assert_eq!(report.resolutions.len(), 1);
    let r = &report.resolutions[0];
    assert_eq!(r.targets.len(), 45);
    assert!(r.complete, "{:?}", r.unresolved);
    assert_eq!(r.paths[0].indices.len(), 58);
    assert_eq!(r.paths[0].entries[0].target, "0x00007ff64007a34d");
    assert_eq!(report.data_reads.len(), 58);
    validate(&report, &instructions, &[0x7ff640079640].into()).unwrap();
    let mut forged = report.clone();
    forged.resolutions[0].targets.pop();
    assert!(validate(&forged, &instructions, &[0x7ff640079640].into()).is_err());
}
#[test]
fn newly_admitted_guard_bypass_downgrades_coverage_but_preserves_candidates() {
    let (instructions, transfers) = dispatch();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &[0x7ff640079640, 0x7ff640079684].into(),
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    assert_eq!(report.resolutions[0].targets.len(), 45);
    assert!(!report.resolutions[0].complete);
    assert!(
        report.resolutions[0]
            .unresolved
            .contains("unsupported-or-unknown-target")
    );
}
#[test]
fn missing_entry_keeps_other_destinations_and_unresolved_alternative() {
    let (instructions, transfers) = dispatch();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &[0x7ff640079640].into(),
        &transfers,
        &Limits::default(),
        |a, n| {
            let mut r = table_read(a, n)?;
            if a == 0x7ff64791ef58 {
                r.bytes_hex.clear();
                r.spans.clear();
                r.stop = "not_captured".into();
            }
            Ok(r)
        },
    )
    .unwrap();
    assert!(!report.resolutions[0].complete);
    assert!(!report.resolutions[0].targets.is_empty());
    assert!(
        report.resolutions[0]
            .unresolved
            .contains("unavailable-control-data")
    );
}
#[test]
fn zero_budgets_never_create_a_complete_target_certificate() {
    let (instructions, transfers) = dispatch();
    for limits in [
        Limits {
            max_steps: 0,
            ..Limits::default()
        },
        Limits {
            max_elapsed_ms: 0,
            ..Limits::default()
        },
        Limits {
            max_read_bytes: 0,
            ..Limits::default()
        },
        Limits {
            max_entries: 0,
            ..Limits::default()
        },
        Limits {
            max_targets: 0,
            ..Limits::default()
        },
        Limits {
            max_evidence_bytes: 0,
            ..Limits::default()
        },
        Limits {
            max_path_steps: 0,
            ..Limits::default()
        },
        Limits {
            max_values: 0,
            ..Limits::default()
        },
        Limits {
            max_rounds: 0,
            ..Limits::default()
        },
    ] {
        let r = resolve(
            "snapshot",
            "artifact",
            &instructions,
            &[0x7ff640079640].into(),
            &transfers,
            &limits,
            table_read,
        )
        .unwrap();
        assert!(r.resolutions.iter().all(|v| !v.complete));
        validate(&r, &instructions, &[0x7ff640079640].into()).unwrap();
    }
}
#[test]
fn independent_oracle_covers_signed_offsets_duplicates_lower_bounds_and_wrap() {
    let data: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/target-resolution-oracle.json")).unwrap();
    for case in data["cases"].as_array().unwrap() {
        let base = address(case["base"].as_str().unwrap()).unwrap();
        let mut got = BTreeSet::new();
        for i in case["lower"].as_u64().unwrap()..=case["upper"].as_u64().unwrap() {
            if case["missing"]
                .as_array()
                .unwrap()
                .contains(&serde_json::json!(i))
            {
                continue;
            }
            let bytes = decode_bytes(case["words"][i as usize].as_str().unwrap()).unwrap();
            got.insert(hex(base.wrapping_add(
                i32::from_le_bytes(bytes.try_into().unwrap()) as i64 as u64,
            )));
        }
        assert_eq!(
            got.into_iter().collect::<Vec<_>>(),
            case["expected"]
                .as_array()
                .unwrap()
                .iter()
                .map(|s| s.as_str().unwrap().to_owned())
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn unknown_outputs_do_not_alias_an_unrelated_guarded_value() {
    let a = Term::unknown(32);
    let index = Term::binary(8, a.clone(), Term::constant(63, 32));
    let t = Term::binary(
        18,
        Term::constant(4096, 64),
        Term::cast(
            2,
            64,
            Term {
                width: 32,
                kind: TermKind::Load {
                    site: hex(20),
                    address: Box::new(Term::binary(
                        18,
                        Term::constant(4096, 64),
                        Term::binary(11, Term::cast(3, 64, index), Term::constant(2, 64)),
                    )),
                },
            },
        ),
    );
    assert!(relative(&t).is_none());
}

#[test]
fn forged_source_expression_premise_and_graph_are_rejected() {
    let (instructions, transfers) = dispatch();
    let roots = [0x7ff640079640].into();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &roots,
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    for mutation in 0..5 {
        let mut r = report.clone();
        match mutation {
            0 => r.memory_premise = "runtime-equals-capture-without-evidence".into(),
            1 => r.resolutions[0].paths[0].expression = Term::constant(0, 64),
            2 => r.resolutions[0].paths[0].indices.pop().map(|_| ()).unwrap(),
            3 => r.resolutions[0].paths[0].reverse_edges[0] = true,
            _ => r.graph_sha256 = "0".repeat(64),
        }
        assert!(
            validate(&r, &instructions, &roots).is_err(),
            "mutation {mutation}"
        );
    }
}

#[test]
fn opaque_call_clobber_does_not_inherit_an_earlier_register_value() {
    let (mut instructions, mut transfers) = dispatch();
    let i = instructions.get_mut(&0x7ff640079665).unwrap();
    i.kind = InstructionKind::Call;
    i.may_defs = crate::effects::Catalogue.locations();
    i.must_defs.clear();
    i.complete = false;
    transfers.remove(&0x7ff640079665);
    let r = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &[0x7ff640079640].into(),
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    assert!(!r.resolutions[0].complete);
    assert!(r.resolutions[0].targets.is_empty());
}

#[test]
fn distinct_target_and_read_caps_do_not_charge_duplicates_twice() {
    let (instructions, transfers) = dispatch();
    let limits = Limits {
        max_targets: 45,
        max_read_bytes: 232,
        ..Limits::default()
    };
    let r = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &[0x7ff640079640].into(),
        &transfers,
        &limits,
        table_read,
    )
    .unwrap();
    assert!(r.resolutions[0].complete);
    assert_eq!(r.resolutions[0].targets.len(), 45);
    assert_eq!(r.data_reads.len(), 58);
}

fn register(name: &str) -> crate::bap::ast::Var {
    crate::bap::ast::Var {
        name: name.into(),
        index: 0,
        virtual_: false,
        width: 64,
        type_: "imm".into(),
    }
}

fn pointer_jump(address: Expr, site: u64) -> Transfer {
    extract(
        &[Stmt::Jump {
            target: Expr::Load {
                width: 64,
                mem: Box::new(Expr::Unknown {
                    reason: "captured memory".into(),
                }),
                addr: Box::new(address),
            },
        }],
        site,
        &[0xff, 0x20],
    )
    .unwrap()
}

fn pointer_read(slot: u64, width: usize) -> Result<DataRead, Error> {
    assert_eq!(width, 8);
    Ok(DataRead {
        address: hex(slot),
        requested: width,
        bytes_hex: (slot + 0x4000)
            .to_le_bytes()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
        spans: vec![Span {
            address: hex(slot),
            length: width,
            contributors: vec![Contributor {
                stream: 9,
                entry: 0,
                file_offset: slot,
            }],
        }],
        conflict_sources: Vec::new(),
        stop: "RequestedLength".into(),
    })
}

#[test]
fn complete_coverage_requires_each_combination_of_successive_diamonds() {
    let mut graph = BTreeMap::new();
    for (site, kind, fall, targets) in [
        (1, InstructionKind::Conditional, vec![2], vec![3]),
        (2, InstructionKind::Ordinary, vec![4], vec![]),
        (3, InstructionKind::Ordinary, vec![4], vec![]),
        (4, InstructionKind::Conditional, vec![5], vec![6]),
        (5, InstructionKind::Ordinary, vec![7], vec![]),
        (6, InstructionKind::Ordinary, vec![7], vec![]),
        (7, InstructionKind::Indirect, vec![], vec![]),
    ] {
        graph.insert(
            site,
            Instruction {
                kind,
                fall: fall.into_iter().collect(),
                targets: targets.into_iter().collect(),
                complete: kind != InstructionKind::Indirect,
                ..Instruction::default()
            },
        );
    }
    let mut transfers = BTreeMap::new();
    for (site, name, value) in [
        (2, "RAX", 4096),
        (3, "RAX", 8192),
        (5, "RBX", 0),
        (6, "RBX", 8),
    ] {
        transfers.insert(
            site,
            extract(
                &[Stmt::Move {
                    var: register(name),
                    value: Expr::Int {
                        value: format!("{value}:64"),
                    },
                }],
                site,
                &[0x90],
            )
            .unwrap(),
        );
    }
    transfers.insert(
        7,
        pointer_jump(
            Expr::Binop {
                op: 18,
                lhs: Box::new(Expr::Var {
                    var: register("RAX"),
                }),
                rhs: Box::new(Expr::Var {
                    var: register("RBX"),
                }),
            },
            7,
        ),
    );
    let roots = [1].into();
    let mut report = resolve(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    assert!(report.resolutions[0].complete);
    assert_eq!(report.resolutions[0].paths.len(), 4);
    assert_eq!(report.resolutions[0].targets.len(), 4);
    validate(&report, &graph, &roots).unwrap();
    for max_values in [1, 2, 3] {
        let limits = Limits {
            max_values,
            ..Limits::default()
        };
        let generated = resolve(
            "snapshot",
            "artifact",
            &graph,
            &roots,
            &transfers,
            &limits,
            pointer_read,
        )
        .unwrap();
        assert_eq!(generated.resolutions[0].complete, max_values >= 3);
        let mut bounded = report.clone();
        bounded.limits = limits;
        assert_eq!(validate(&bounded, &graph, &roots).is_ok(), max_values >= 3);
    }
    // Partial receipts may retain witnesses from multiple bounded passes.
    let mut retained = report.clone();
    retained.limits.max_values = 2;
    retained.resolutions[0].complete = false;
    validate(&retained, &graph, &roots).unwrap();
    let row = &mut report.resolutions[0];
    row.paths
        .retain(|path| path.reverse_path.contains(&hex(2)) == path.reverse_path.contains(&hex(5)));
    row.targets = row
        .paths
        .iter()
        .flat_map(|path| path.entries.iter().map(|entry| entry.target.clone()))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    assert_eq!(row.paths.len(), 2);
    assert_eq!(row.targets.len(), 2);
    assert!(validate(&report, &graph, &roots).is_err());
    // The surviving paths still witness candidates, but cannot exclude the two
    // other combinations even though their union includes every original edge.
    report.resolutions[0].complete = false;
    validate(&report, &graph, &roots).unwrap();
}

#[test]
fn shared_destinations_count_once_across_indirect_sites() {
    for same_destination in [true, false] {
        let graph = [1, 2]
            .into_iter()
            .map(|site| {
                (
                    site,
                    Instruction {
                        kind: InstructionKind::Indirect,
                        ..Instruction::default()
                    },
                )
            })
            .collect();
        let transfers = [1, 2]
            .into_iter()
            .map(|site| {
                let slot = if same_destination || site == 1 {
                    4096
                } else {
                    8192
                };
                (
                    site,
                    pointer_jump(
                        Expr::Int {
                            value: format!("{slot}:64"),
                        },
                        site,
                    ),
                )
            })
            .collect();
        let roots = [1, 2].into();
        let report = resolve(
            "snapshot",
            "artifact",
            &graph,
            &roots,
            &transfers,
            &Limits {
                max_targets: 1,
                ..Limits::default()
            },
            pointer_read,
        )
        .unwrap();
        assert!(report.resolutions[0].complete);
        assert_eq!(report.resolutions[1].complete, same_destination);
        assert_eq!(
            report.resolutions[1].targets.len(),
            usize::from(same_destination)
        );
        assert_eq!(
            report.data_reads.len(),
            if same_destination { 1 } else { 2 }
        );
        validate(&report, &graph, &roots).unwrap();
    }
}

#[test]
fn receipt_admission_enforces_actual_resource_usage() {
    let (instructions, transfers) = dispatch();
    let roots = [0x7ff640079640].into();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &roots,
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    for limits in [
        Limits {
            max_targets: 44,
            ..Limits::default()
        },
        Limits {
            max_read_bytes: 231,
            ..Limits::default()
        },
        Limits {
            max_read_bytes: 0,
            ..Limits::default()
        },
        Limits {
            max_evidence_bytes: 0,
            ..Limits::default()
        },
        Limits {
            max_entries: 57,
            ..Limits::default()
        },
        Limits {
            max_path_steps: report.resolutions[0].paths[0].reverse_path.len(),
            ..Limits::default()
        },
        Limits {
            max_values: 0,
            ..Limits::default()
        },
        Limits {
            max_steps: 0,
            ..Limits::default()
        },
        Limits {
            max_rounds: 0,
            ..Limits::default()
        },
        Limits {
            max_elapsed_ms: 0,
            ..Limits::default()
        },
    ] {
        let mut forged = report.clone();
        forged.limits = limits;
        assert!(
            validate(&forged, &instructions, &roots).is_err(),
            "{:?}",
            forged.limits
        );
    }
    let mut exact = report;
    exact.limits.max_targets = 45;
    exact.limits.max_read_bytes = 232;
    exact.limits.max_entries = 58;
    exact.limits.max_path_steps = exact.resolutions[0].paths[0].reverse_path.len() + 1;
    // A guard-bounded index range is independent of the value-set/frontier cap.
    exact.limits.max_values = 1;
    validate(&exact, &instructions, &roots).unwrap();
}

#[test]
fn admitted_evidence_leaves_room_for_conservative_discovery_stop() {
    let (instructions, transfers) = dispatch();
    let roots = [0x7ff640079640].into();
    let report = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &roots,
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    let mut limits = Limits::default();
    // Converge the budget's own serialized decimal width before checking the
    // boundary at which the initial complete receipt alone would fit.
    for _ in 0..3 {
        let mut sized = report.clone();
        sized.limits = limits.clone();
        limits.max_evidence_bytes = serde_json::to_vec(&sized).unwrap().len();
    }
    let bounded = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &roots,
        &transfers,
        &limits,
        table_read,
    )
    .unwrap();
    assert_eq!(bounded.stop.as_deref(), Some("resolution-evidence-limit"));
    validate(&bounded, &instructions, &roots).unwrap();
    limits.max_evidence_bytes += 64;
    let mut retained = resolve(
        "snapshot",
        "artifact",
        &instructions,
        &roots,
        &transfers,
        &limits,
        table_read,
    )
    .unwrap();
    assert!(retained.stop.is_none());
    retained.resolutions[0].complete = false;
    retained.stop = Some("resolution-retention-limit".into());
    validate(&retained, &instructions, &roots).unwrap();
}

fn frontier_diamond(
    unknown_alternative: bool,
) -> (BTreeMap<u64, Instruction>, BTreeMap<u64, Transfer>) {
    let mut graph = BTreeMap::new();
    for (site, kind, fall, targets) in [
        (1, InstructionKind::Conditional, vec![2], vec![3]),
        (2, InstructionKind::Ordinary, vec![4], vec![]),
        (3, InstructionKind::Ordinary, vec![4], vec![]),
        (4, InstructionKind::Indirect, vec![], vec![]),
    ] {
        graph.insert(
            site,
            Instruction {
                kind,
                complete: kind != InstructionKind::Indirect,
                fall: fall.into_iter().collect(),
                targets: targets.into_iter().collect(),
                ..Instruction::default()
            },
        );
    }
    let mut transfers = BTreeMap::new();
    for (site, slot) in [(2, 4096), (3, 8192)] {
        if unknown_alternative && site == 3 {
            graph.get_mut(&site).unwrap().may_defs = crate::effects::Catalogue.locations();
            continue;
        }
        transfers.insert(
            site,
            extract(
                &[Stmt::Move {
                    var: register("RAX"),
                    value: Expr::Int {
                        value: format!("{slot}:64"),
                    },
                }],
                site,
                &[0x90],
            )
            .unwrap(),
        );
    }
    transfers.insert(
        4,
        pointer_jump(
            Expr::Var {
                var: register("RAX"),
            },
            4,
        ),
    );
    (graph, transfers)
}

#[test]
fn local_frontiers_require_every_incoming_alternative_and_preserve_partial_witnesses() {
    let (graph, transfers) = frontier_diamond(false);
    let roots = [1].into();
    let report = resolve_candidate(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    assert!(report.resolutions[0].complete);
    assert_eq!(
        report.resolutions[0].targets,
        vec![hex(0x5000), hex(0x6000)]
    );
    assert_eq!(report.resolutions[0].paths.len(), 2);
    assert!(
        report.resolutions[0]
            .paths
            .iter()
            .all(|p| p.frontier && p.reverse_path.len() == 1)
    );
    validate(&report, &graph, &roots).unwrap();
    let mut omitted = report;
    omitted.resolutions[0].paths.pop();
    omitted.resolutions[0].targets = omitted.resolutions[0].paths[0]
        .entries
        .iter()
        .map(|e| e.target.clone())
        .collect();
    assert!(
        validate(&omitted, &graph, &roots)
            .unwrap_err()
            .to_string()
            .contains("prefix receipt references"),
        "omitted paths also invalidate the v3 coverage references"
    );
    omitted.resolutions[0].coverage = Some(CoverageEvidence::ExistingPrefixTree {
        path_receipt_refs: (0..omitted.resolutions[0].paths.len()).collect(),
    });
    assert!(
        validate(&omitted, &graph, &roots)
            .unwrap_err()
            .to_string()
            .contains("uncovered incoming path")
    );
    omitted.resolutions[0].complete = false;
    validate(&omitted, &graph, &roots).unwrap();
}

#[test]
fn unknown_incoming_register_does_not_gain_a_local_frontier_certificate() {
    let (graph, transfers) = frontier_diamond(true);
    let roots = [1].into();
    let report = resolve_candidate(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    let row = &report.resolutions[0];
    assert!(!row.complete);
    assert_eq!(row.targets, vec![hex(0x5000)]);
    assert_eq!(row.paths.len(), 1);
    assert!(row.paths[0].frontier);
    assert!(row.unresolved.contains("unsupported-or-unknown-target"));
    validate(&report, &graph, &roots).unwrap();
    let mut forged = report;
    forged.resolutions[0].complete = true;
    forged.resolutions[0].unresolved.clear();
    assert!(validate(&forged, &graph, &roots).is_err());
}

#[test]
fn legacy_profile_retains_root_paths_and_rejects_local_frontier_receipts() {
    let (graph, transfers) = frontier_diamond(false);
    let roots = [1].into();
    let legacy = resolve(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    assert_eq!(legacy.profile, PROFILE);
    assert!(legacy.resolutions[0].complete);
    assert!(
        legacy.resolutions[0]
            .paths
            .iter()
            .all(|p| !p.frontier && p.root == hex(1) && p.reverse_path.len() == 2)
    );
    validate(&legacy, &graph, &roots).unwrap();
    let mut local = resolve_candidate(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    local.profile = PROFILE.into();
    local.schema = "ariadne.indirect-target-resolution/v1".into();
    assert!(validate(&local, &graph, &roots).is_err());
}

#[test]
fn root_receipt_with_incoming_edge_is_terminal_but_not_a_frontier_cut() {
    let graph = [
        (0, InstructionKind::Ordinary, vec![1]),
        (1, InstructionKind::Ordinary, vec![2]),
        (2, InstructionKind::Indirect, vec![]),
    ]
    .into_iter()
    .map(|(site, kind, fall)| {
        (
            site,
            Instruction {
                kind,
                complete: kind != InstructionKind::Indirect,
                fall: fall.into_iter().collect(),
                ..Instruction::default()
            },
        )
    })
    .collect();
    let transfers = [
        (
            1,
            extract(
                &[Stmt::Move {
                    var: register("RAX"),
                    value: Expr::Int {
                        value: "4096:64".into(),
                    },
                }],
                1,
                &[0x90],
            )
            .unwrap(),
        ),
        (
            2,
            pointer_jump(
                Expr::Var {
                    var: register("RAX"),
                },
                2,
            ),
        ),
    ]
    .into();
    let roots = [1].into();
    let report = resolve_candidate(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        pointer_read,
    )
    .unwrap();
    assert!(report.resolutions[0].complete);
    assert_eq!(report.resolutions[0].paths.len(), 2);
    assert!(
        report.resolutions[0]
            .paths
            .iter()
            .any(|p| p.root == hex(1) && !p.frontier)
    );
    assert!(
        report.resolutions[0]
            .paths
            .iter()
            .any(|p| p.root == hex(0) && p.frontier)
    );
    validate(&report, &graph, &roots).unwrap();
    let mut omitted = report.clone();
    omitted.resolutions[0].paths.retain(|p| !p.frontier);
    assert!(
        validate(&omitted, &graph, &roots)
            .unwrap_err()
            .to_string()
            .contains("prefix receipt references"),
        "omitted paths also invalidate the v3 coverage references"
    );
    omitted.resolutions[0].coverage = Some(CoverageEvidence::ExistingPrefixTree {
        path_receipt_refs: (0..omitted.resolutions[0].paths.len()).collect(),
    });
    assert!(
        validate(&omitted, &graph, &roots)
            .unwrap_err()
            .to_string()
            .contains("uncovered incoming path")
    );
    let mut forged = report;
    forged.resolutions[0]
        .paths
        .iter_mut()
        .find(|p| p.root == hex(1))
        .unwrap()
        .frontier = true;
    assert!(
        validate(&forged, &graph, &roots)
            .unwrap_err()
            .to_string()
            .contains("path/semantic proof")
    );
}

#[test]
fn contradictory_unbounded_index_ranges_do_not_create_early_frontiers() {
    let index = Term::input("RAX:0:false".into(), 32);
    let base = Term::constant(4096, 64);
    let term = Term::binary(
        18,
        base.clone(),
        Term::cast(
            2,
            64,
            Term {
                width: 32,
                kind: TermKind::Load {
                    site: hex(4),
                    address: Box::new(Term::binary(
                        18,
                        base,
                        Term::binary(11, Term::cast(3, 64, index.clone()), Term::constant(2, 64)),
                    )),
                },
            },
        ),
    );
    let guards = [
        Guard {
            expression: Term::binary(2, index.clone(), Term::constant(1, 32)),
            taken: true,
        },
        Guard {
            expression: Term::binary(2, index, Term::constant(1, 32)),
            taken: false,
        },
    ];
    assert!(relative(&term).is_some());
    assert!(!bounded_form(&term, &guards, &Limits::default()));
}

// Independent control: LOOP writes the counter once, then the subsequent
// unsigned bound admits post-write table indices 0..=3. Its taken branch
// excludes zero. Reapplying the move to the branch predicate wrongly excludes
// one and admits zero instead.
#[test]
fn conditional_write_predicate_is_not_rewritten_twice() {
    let var = |name: &str| Expr::Var {
        var: register(name),
    };
    let number = |value: u64| Expr::Int {
        value: format!("{value}:64u"),
    };
    let bin = |op, lhs, rhs| Expr::Binop {
        op,
        lhs: Box::new(lhs),
        rhs: Box::new(rhs),
    };
    let mem = Expr::Var {
        var: crate::bap::ast::Var {
            name: "mem".into(),
            index: 0,
            virtual_: false,
            width: 0,
            type_: "mem".into(),
        },
    };
    let programs = BTreeMap::from([
        (
            1,
            vec![Stmt::Move {
                var: register("RDX"),
                value: number(4096),
            }],
        ),
        (
            2,
            vec![
                Stmt::Move {
                    var: register("RCX"),
                    value: bin(17, var("RCX"), number(1)),
                },
                Stmt::If {
                    condition: bin(4, var("RCX"), number(0)),
                    yes: vec![Stmt::Jump { target: number(3) }],
                    no: vec![],
                },
            ],
        ),
        (
            3,
            vec![Stmt::If {
                condition: bin(2, var("RCX"), number(3)),
                yes: vec![Stmt::Jump { target: number(4) }],
                no: vec![],
            }],
        ),
        (
            4,
            vec![Stmt::Jump {
                target: bin(
                    18,
                    var("RDX"),
                    Expr::Cast {
                        op: 2,
                        width: 64,
                        arg: Box::new(Expr::Load {
                            width: 32,
                            mem: Box::new(mem),
                            addr: Box::new(bin(18, var("RDX"), bin(11, var("RCX"), number(2)))),
                        }),
                    },
                ),
            }],
        ),
    ]);
    let mut graph = BTreeMap::new();
    for (site, kind, fall, targets) in [
        (1, InstructionKind::Ordinary, vec![2], vec![]),
        (2, InstructionKind::Conditional, vec![8], vec![3]),
        (3, InstructionKind::Conditional, vec![8], vec![4]),
        (4, InstructionKind::Indirect, vec![], vec![]),
        (8, InstructionKind::Return, vec![], vec![]),
    ] {
        graph.insert(
            site,
            Instruction {
                kind,
                fall: fall.into_iter().collect(),
                targets: targets.into_iter().collect(),
                complete: kind != InstructionKind::Indirect,
                may_defs: if site == 2 {
                    (0..8).map(|n| format!("gpr:rcx:{n}")).collect()
                } else {
                    LocationSet::new()
                },
                ..Instruction::default()
            },
        );
    }
    let transfers = programs
        .iter()
        .map(|(&site, bil)| (site, extract(bil, site, &[0x90]).unwrap()))
        .collect();
    let read = |slot: u64, width: usize| -> Result<DataRead, Error> {
        assert_eq!(width, 4);
        let index = (slot - 4096) / 4;
        assert!(index <= 3);
        Ok(DataRead {
            address: hex(slot),
            requested: 4,
            bytes_hex: (256u32 + index as u32 * 16)
                .to_le_bytes()
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect(),
            spans: vec![Span {
                address: hex(slot),
                length: 4,
                contributors: vec![Contributor {
                    stream: 9,
                    entry: index as usize,
                    file_offset: slot,
                }],
            }],
            conflict_sources: vec![],
            stop: "RequestedLength".into(),
        })
    };
    let expected = vec![1, 2, 3];
    let double_applied = vec![0, 2, 3];
    assert_eq!((0u64..=3).filter(|i| *i != 0).collect::<Vec<_>>(), expected);
    assert_eq!(
        (0u64..=3)
            .filter(|i| i.wrapping_sub(1) != 0)
            .collect::<Vec<_>>(),
        double_applied
    );
    for local in [false, true] {
        let report = resolve_inner(
            "snapshot",
            "artifact",
            &graph,
            &[1].into(),
            &transfers,
            &Limits::default(),
            local,
            read,
        )
        .unwrap();
        let row = &report.resolutions[0];
        assert!(row.complete, "{:?}", row.unresolved);
        assert_eq!(
            row.paths[0].indices, expected,
            "conditional write applied twice"
        );
        validate(&report, &graph, &[1].into()).unwrap();
        let mut forged = report;
        let path = &mut forged.resolutions[0].paths[0];
        let index = relative(&path.expression).unwrap().1;
        path.guards[1].expression = Term::binary(
            4,
            Term::binary(17, index, Term::constant(1, 64)),
            Term::constant(0, 64),
        );
        assert!(
            validate(&forged, &graph, &[1].into())
                .unwrap_err()
                .to_string()
                .contains("path/semantic proof")
        );
    }
}

#[test]
fn full_captured_read_metadata_must_not_hide_conflicts_or_holes() {
    let (graph, transfers) = dispatch();
    let roots = [0x7ff640079640].into();
    let report = resolve(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        table_read,
    )
    .unwrap();
    validate(&report, &graph, &roots).unwrap();
    for case in [
        "conflict",
        "stop",
        "span-hole",
        "empty-contributor",
        "short-coverage",
        "wrong-width",
        "invalid-span-address",
    ] {
        let mut forged = report.clone();
        let record = &mut forged.data_reads[0];
        match case {
            "conflict" => record.conflict_sources.push(Contributor {
                stream: 5,
                entry: 1,
                file_offset: 0,
            }),
            "stop" => record.stop = "Conflict".into(),
            "span-hole" => record.spans[0].address = hex(address(&record.address).unwrap() + 1),
            "empty-contributor" => record.spans[0].contributors.clear(),
            "short-coverage" => record.spans[0].length = 3,
            "wrong-width" => record.requested = 3,
            "invalid-span-address" => record.spans[0].address = "0x0".into(),
            _ => unreachable!(),
        }
        assert!(
            validate(&forged, &graph, &roots).is_err(),
            "accepted {case}"
        );
    }
    // A partial/conflicting record remains an explicit residual and contributes
    // no entry. Its other entries remain possible under the captured premise.
    let partial = resolve(
        "snapshot",
        "artifact",
        &graph,
        &roots,
        &transfers,
        &Limits::default(),
        |slot, width| {
            let mut read = table_read(slot, width)?;
            if slot == address(&report.data_reads[0].address).unwrap() {
                read.bytes_hex.truncate(4);
                read.spans.clear();
                read.conflict_sources.push(Contributor {
                    stream: 5,
                    entry: 1,
                    file_offset: 0,
                });
                read.stop = "Conflict".into();
            }
            Ok(read)
        },
    )
    .unwrap();
    assert!(!partial.resolutions[0].complete);
    assert!(
        partial.resolutions[0]
            .unresolved
            .contains("unavailable-control-data")
    );
    validate(&partial, &graph, &roots).unwrap();
}

#[test]
fn malformed_full_read_callback_is_rejected_before_candidate_admission() {
    let (graph, transfers) = dispatch();
    for case in ["conflict", "stop", "span-hole", "empty-contributor"] {
        let error = resolve(
            "snapshot",
            "artifact",
            &graph,
            &[0x7ff640079640].into(),
            &transfers,
            &Limits::default(),
            |slot, width| {
                let mut read = table_read(slot, width)?;
                match case {
                    "conflict" => read.conflict_sources.push(Contributor {
                        stream: 5,
                        entry: 1,
                        file_offset: 0,
                    }),
                    "stop" => read.stop = "NotCaptured".into(),
                    "span-hole" => read.spans[0].address = hex(slot + 1),
                    "empty-contributor" => read.spans[0].contributors.clear(),
                    _ => unreachable!(),
                }
                Ok(read)
            },
        )
        .unwrap_err();
        assert!(
            error.to_string().contains("resolver"),
            "unexpected {case}: {error}"
        );
    }
}

fn stable_byte_reload_loop(mode: &str) -> (BTreeMap<u64, Instruction>, BTreeMap<u64, Transfer>) {
    let var = |name: &str| Expr::Var {
        var: register(name),
    };
    let int = |n: u64| Expr::Int {
        value: format!("{n}:64u"),
    };
    let bin = |op, lhs, rhs| Expr::Binop {
        op,
        lhs: Box::new(lhs),
        rhs: Box::new(rhs),
    };
    let memory_var = crate::bap::ast::Var {
        name: "mem".into(),
        index: 0,
        virtual_: false,
        width: 0,
        type_: "mem".into(),
    };
    let memory = Expr::Var {
        var: memory_var.clone(),
    };
    let cycle = match mode {
        "address-write" => vec![Stmt::Move {
            var: register("RCX"),
            value: bin(18, var("RCX"), int(1)),
        }],
        "memory-write" => vec![Stmt::Move {
            var: memory_var,
            value: Expr::Store {
                width: 8,
                mem: Box::new(memory.clone()),
                addr: Box::new(var("RCX")),
                value: Box::new(Expr::Int {
                    value: "0:8u".into(),
                }),
            },
        }],
        _ => vec![],
    };
    let programs = BTreeMap::from([
        (
            1,
            vec![Stmt::Move {
                var: register("RDX"),
                value: int(4096),
            }],
        ),
        (2, vec![Stmt::Jump { target: int(6) }]),
        (3, cycle),
        (
            6,
            vec![Stmt::Move {
                var: register("R8"),
                value: Expr::Cast {
                    op: 3,
                    width: 64,
                    arg: Box::new(Expr::Cast {
                        op: 3,
                        width: 32,
                        arg: Box::new(Expr::Load {
                            width: 8,
                            mem: Box::new(memory.clone()),
                            addr: Box::new(bin(18, var("RCX"), int(120))),
                        }),
                    }),
                },
            }],
        ),
        (7, vec![]),
        (
            8,
            vec![Stmt::If {
                condition: bin(2, var("R8"), int(9)),
                yes: vec![Stmt::Jump { target: int(10) }],
                no: vec![],
            }],
        ),
        (
            10,
            vec![Stmt::Jump {
                target: bin(
                    18,
                    var("RDX"),
                    Expr::Cast {
                        op: 2,
                        width: 64,
                        arg: Box::new(Expr::Load {
                            width: 32,
                            mem: Box::new(memory),
                            addr: Box::new(bin(18, var("RDX"), bin(11, var("R8"), int(2)))),
                        }),
                    },
                ),
            }],
        ),
    ]);
    let mut graph = BTreeMap::new();
    for (site, kind, fall, targets) in [
        (1, InstructionKind::Ordinary, vec![2], vec![]),
        (2, InstructionKind::Jump, vec![], vec![6]),
        (3, InstructionKind::Ordinary, vec![6], vec![]),
        (6, InstructionKind::Ordinary, vec![7], vec![]),
        (7, InstructionKind::Ordinary, vec![8], vec![]),
        (8, InstructionKind::Conditional, vec![3], vec![10]),
        (10, InstructionKind::Indirect, vec![], vec![]),
    ] {
        graph.insert(
            site,
            Instruction {
                kind,
                complete: kind != InstructionKind::Indirect,
                fall: fall.into_iter().collect(),
                targets: targets.into_iter().collect(),
                may_defs: if site == 3 && mode == "address-write" {
                    (0..8).map(|n| format!("gpr:rcx:{n}")).collect()
                } else {
                    LocationSet::new()
                },
                ..Instruction::default()
            },
        );
    }
    if mode == "bypass" {
        graph.insert(
            5,
            Instruction {
                kind: InstructionKind::Jump,
                targets: [6].into(),
                complete: true,
                ..Instruction::default()
            },
        );
    }
    if mode == "unknown-memory" {
        graph
            .get_mut(&3)
            .unwrap()
            .may_defs
            .insert("memory:any".into());
    }
    let transfers = programs
        .iter()
        .map(|(&site, bil)| (site, extract(bil, site, &[0x90]).unwrap()))
        .collect();
    (graph, transfers)
}
fn small_relative_read(slot: u64, width: usize) -> Result<DataRead, Error> {
    assert_eq!(width, 4);
    let index = (slot - 4096) / 4;
    assert!(index <= 9);
    Ok(DataRead {
        address: hex(slot),
        requested: 4,
        bytes_hex: (256u32 + index as u32 * 16)
            .to_le_bytes()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
        spans: vec![Span {
            address: hex(slot),
            length: 4,
            contributors: vec![Contributor {
                stream: 9,
                entry: index as usize,
                file_offset: slot,
            }],
        }],
        conflict_sources: vec![],
        stop: "RequestedLength".into(),
    })
}
#[test]
fn stable_byte_reload_loop_has_checked_infeasible_context_and_ten_entries() {
    let (graph, transfers) = stable_byte_reload_loop("stable");
    let report = resolve_candidate(
        "snapshot",
        "artifact",
        &graph,
        &[1].into(),
        &transfers,
        &Limits::default(),
        small_relative_read,
    )
    .unwrap();
    let row = &report.resolutions[0];
    assert!(row.complete, "{:?}", row.unresolved);
    assert_eq!(row.targets.len(), 10);
    assert!(
        row.paths
            .iter()
            .any(|p| p.form == "relative32" && p.indices == (0..10).collect::<Vec<_>>())
    );
    assert!(row.paths.iter().any(|p| p.form == "infeasible"
        && p.frontier
        && p.indices.is_empty()
        && p.entries.is_empty()));
    validate(&report, &graph, &[1].into()).unwrap();
    let mut omitted = report.clone();
    omitted.resolutions[0]
        .paths
        .retain(|p| p.form != "infeasible");
    assert!(validate(&omitted, &graph, &[1].into()).is_err());
}
#[test]
fn byte_reload_loop_bypass_or_writes_keep_unknown_alternatives() {
    for mode in ["memory-write", "unknown-memory", "address-write", "bypass"] {
        let (graph, transfers) = stable_byte_reload_loop(mode);
        let roots = if mode == "bypass" {
            [1, 5].into()
        } else {
            [1].into()
        };
        let report = resolve_candidate(
            "snapshot",
            "artifact",
            &graph,
            &roots,
            &transfers,
            &Limits::default(),
            small_relative_read,
        )
        .unwrap();
        assert!(!report.resolutions[0].complete, "incorrect complete {mode}");
        assert_eq!(
            report.resolutions[0].targets.len(),
            10,
            "lost entry candidates {mode}"
        );
        validate(&report, &graph, &roots).unwrap();
    }
}

#[test]
fn question_resolver_services_selected_late_dispatch_before_earlier_peers() {
    let (mut instructions, mut transfers) = dispatch();
    let (&site, first) = instructions
        .iter()
        .find(|(_, i)| i.kind == InstructionKind::Indirect)
        .unwrap();
    let first = first.clone();
    let transfer = transfers[&site].clone();
    let later = site + 0x100000;
    let bil: Vec<Stmt> = serde_json::from_str(&transfer.ast).unwrap();
    instructions.insert(later, first);
    transfers.insert(
        later,
        extract(&bil, later, &decode_bytes(&transfer.bytes_hex).unwrap()).unwrap(),
    );
    let schedule = QuestionTargetSchedule {
        priority: [later].into(),
        quantum: 1,
        deadline: None,
        work: std::cell::Cell::new(0),
        service: std::cell::RefCell::new(Vec::new()),
    };
    let roots = [*instructions.keys().next().unwrap(), later].into();
    let r = resolve_question(
        "question-fixture",
        &"1".repeat(64),
        &instructions,
        &roots,
        &transfers,
        &Limits::default(),
        &schedule,
        table_read,
    )
    .unwrap();
    validate(&r, &instructions, &roots).unwrap();
    let service = schedule.service.borrow();
    assert_eq!(service.first(), Some(&later));
    assert!(service.contains(&site));
    assert!(schedule.work.get() > 0);
}
