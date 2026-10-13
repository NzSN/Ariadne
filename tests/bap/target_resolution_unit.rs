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
            "requested_length"
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
        stop: "requested_length".into(),
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
