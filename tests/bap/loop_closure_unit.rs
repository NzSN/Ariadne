use super::*;

fn fixture(
    name: &str,
) -> (
    BTreeMap<u64, Instruction>,
    BTreeMap<u64, Transfer>,
    serde_json::Value,
) {
    let source = match name {
        "da09" => include_str!("fixtures/loop-closure/dump-da09.json"),
        "dadd" => include_str!("fixtures/loop-closure/dump-dadd.json"),
        _ => panic!("unknown loop fixture"),
    };
    let fixture: serde_json::Value = serde_json::from_str(source).unwrap();
    let mut graph = BTreeMap::new();
    let mut transfers = BTreeMap::new();
    for s in fixture["sources"].as_array().unwrap() {
        let site = address(s["site"].as_str().unwrap()).unwrap();
        let i = &s["candidate_instruction"];
        let kind = match i["kind"].as_str().unwrap() {
            "ordinary" => InstructionKind::Ordinary,
            "conditional" => InstructionKind::Conditional,
            "jump" => InstructionKind::Jump,
            "indirect" => InstructionKind::Indirect,
            other => panic!("unexpected {other}"),
        };
        let addresses = |field: &str| {
            i[field]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| address(v.as_str().unwrap()).unwrap())
                .collect()
        };
        let locations = |field: &str| {
            i[field]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap().to_owned())
                .collect()
        };
        graph.insert(
            site,
            Instruction {
                kind,
                complete: i["targets_complete"].as_bool().unwrap(),
                fall: addresses("fall"),
                targets: addresses("targets"),
                uses: locations("uses"),
                may_defs: locations("may_defs"),
                must_defs: locations("must_defs"),
            },
        );
        let bil: Vec<Stmt> = serde_json::from_str(s["ast"].as_str().unwrap()).unwrap();
        transfers.insert(
            site,
            extract(
                &bil,
                site,
                &decode_bytes(s["bytes_hex"].as_str().unwrap()).unwrap(),
            )
            .unwrap(),
        );
    }
    (graph, transfers, fixture)
}
fn limits() -> Limits {
    Limits {
        max_steps: 2_000_000,
        max_path_steps: 512,
        max_elapsed_ms: 30_000,
        max_rounds: 64,
        ..Limits::default()
    }
}
fn report(
    name: &str,
) -> (
    Report,
    BTreeMap<u64, Instruction>,
    BTreeMap<u64, Transfer>,
    serde_json::Value,
) {
    let (graph, transfers, fixture) = fixture(name);
    let reads: Vec<DataRead> = serde_json::from_value(fixture["table_reads"].clone()).unwrap();
    let report = resolve_candidate(
        "loop-fixture-snapshot",
        "loop-fixture-artifact",
        &graph,
        &AddressSet::new(),
        &transfers,
        &limits(),
        |a, n| {
            Ok(reads
                .iter()
                .find(|r| r.address == hex(a) && r.requested == n)
                .unwrap()
                .clone())
        },
    )
    .unwrap();
    (report, graph, transfers, fixture)
}
fn induction(report: &Report) -> &LoopClosureReceipt {
    match report.resolutions[0].coverage.as_ref().unwrap() {
        CoverageEvidence::InductiveDispatch { receipt } => receipt,
        _ => panic!(
            "expected loop induction: {:?}",
            report.resolutions[0].unresolved
        ),
    }
}
#[test]
fn captured_pointer_changing_phase_regions_close_with_independent_edge_replay() {
    for name in ["da09", "dadd"] {
        let (report, graph, _, fixture) = report(name);
        let row = &report.resolutions[0];
        assert!(row.complete, "{} {:?}", name, row.unresolved);
        assert_eq!(row.targets.len(), 4);
        let receipt = induction(&report);
        assert_eq!(receipt.region.len(), 9);
        assert_eq!(receipt.internal_edges.len(), 10);
        assert_eq!(receipt.entrances.len(), 1);
        assert_eq!(receipt.exits.len(), 4);
        assert_eq!(receipt.table.indices, (0..10).collect::<Vec<_>>());
        assert_eq!(
            receipt.region,
            serde_json::from_value::<Vec<String>>(fixture["region_sites"].clone()).unwrap()
        );
        validate(&report, &graph, &AddressSet::new()).unwrap();
        if let Some(directory) = std::env::var_os("ARIADNE_LOOP_RECEIPT_DIR") {
            let directory = std::path::PathBuf::from(directory);
            std::fs::create_dir_all(&directory).unwrap();
            std::fs::write(
                directory.join(format!("{name}-target-report.json")),
                serde_json::to_vec_pretty(&report).unwrap(),
            )
            .unwrap();
            let instructions=graph.iter().map(|(&site,i)|serde_json::json!({"address":hex(site),"kind":format!("{:?}",i.kind).to_lowercase(),"fall":i.fall.iter().copied().map(hex).collect::<Vec<_>>(),"targets":i.targets.iter().copied().map(hex).collect::<Vec<_>>(),"targets_complete":i.complete,"uses":i.uses,"may_defs":i.may_defs,"must_defs":i.must_defs})).collect::<Vec<_>>();
            std::fs::write(
                directory.join(format!("{name}-instructions.json")),
                serde_json::to_vec_pretty(&instructions).unwrap(),
            )
            .unwrap();
        }
        let dispatch = address(&row.site).unwrap();
        let mut complete_graph = graph.clone();
        complete_graph.get_mut(&dispatch).unwrap().complete = true;
        assert!(
            validate(&report, &complete_graph, &AddressSet::new()).is_err(),
            "complete-only graph changes invalidate proof"
        );
    }
}
#[test]
fn loop_receipt_tampering_cannot_hide_entrance_edges_domains_or_original_sources() {
    let (original, graph, _, _) = report("da09");
    induction(&original);
    for variant in [
        "entrance", "internal", "exit", "corridor", "base", "selector", "flags", "bytes", "table",
        "snapshot", "model", "engine", "graph",
    ] {
        let mut forged = original.clone();
        let CoverageEvidence::InductiveDispatch { receipt } =
            forged.resolutions[0].coverage.as_mut().unwrap()
        else {
            unreachable!()
        };
        match variant {
            "entrance" => receipt.entrances.clear(),
            "internal" => {
                receipt.internal_edges.pop();
            }
            "exit" => {
                receipt.exits.pop();
            }
            "corridor" => {
                receipt.corridors[0].sites.remove(0);
            }
            "base" => receipt.table.base = hex(address(&receipt.table.base).unwrap() + 4),
            "selector" => {
                let a = receipt
                    .assertions
                    .iter_mut()
                    .find(|a| a.site == receipt.table.load_site)
                    .unwrap();
                a.domains.insert(
                    receipt.table.selector_bank.clone(),
                    loop_closure::WordDomain {
                        width: 64,
                        kind: loop_closure::WordDomainKind::Constant { value: hex(3) },
                    },
                );
            }
            "flags" => {
                for a in &mut receipt.assertions {
                    a.flags.clear();
                }
            }
            "bytes" => receipt.source_refs[0].bytes_hex = "90".into(),
            "table" => {
                receipt.table.entries.pop();
            }
            "snapshot" => receipt.snapshot.push('x'),
            "model" => receipt.model_sha256 = "0".repeat(64),
            "engine" => receipt.engine_sha256 = "0".repeat(64),
            "graph" => receipt.graph_sha256 = "0".repeat(64),
            _ => unreachable!(),
        }
        assert!(
            validate(&forged, &graph, &AddressSet::new()).is_err(),
            "{variant}"
        );
    }
}
#[test]
fn loop_closure_keeps_legacy_path_prohibition_and_retains_candidates_after_invalidation() {
    let (mut report, graph, _, _) = report("da09");
    let expected = report.resolutions[0].targets.clone();
    let path = report.resolutions[0].paths[0].clone();
    invalidate_loop_coverage(&mut report, "candidate-epoch-changed");
    assert!(!report.resolutions[0].complete);
    assert_eq!(report.resolutions[0].targets, expected);
    assert_eq!(report.resolutions[0].paths[0], path);
    validate(&report, &graph, &AddressSet::new()).unwrap();
    let mut forged = report.clone();
    let repeated_site = forged.resolutions[0].site.clone();
    forged.resolutions[0].paths[0]
        .reverse_path
        .push(repeated_site);
    forged.resolutions[0].paths[0].reverse_edges.push(true);
    assert!(validate(&forged, &graph, &AddressSet::new()).is_err());
    report.schema = "ariadne.indirect-target-resolution/v2".into();
    report.profile = LEGACY_LOCAL_PROFILE.into();
    report.graph_sha256 = legacy_graph_digest(&graph, &AddressSet::new()).unwrap();
    assert!(
        validate(&report, &graph, &AddressSet::new()).is_err(),
        "new coverage cannot be downgraded"
    );
    report.resolutions[0].coverage = None;
    validate(&report, &graph, &AddressSet::new()).unwrap();
    let encoded = serde_json::to_value(&report.resolutions[0]).unwrap();
    assert!(encoded.get("coverage").is_none());
}
#[test]
fn loop_closure_rejects_root_bypass_clobbers_and_missing_preexisting_witnesses() {
    let (original, graph, transfers, _) = report("da09");
    let receipt = induction(&original).clone();
    let site = address(&receipt.dispatch).unwrap();
    let mut roots = AddressSet::new();
    roots.insert(address(&receipt.region[0]).unwrap());
    assert!(validate(&original, &graph, &roots).is_err());
    let reads = original
        .data_reads
        .iter()
        .cloned()
        .map(|r| ((address(&r.address).unwrap(), r.requested), r))
        .collect();
    let mut missing = original.resolutions[0].clone();
    for p in &mut missing.paths {
        p.entries.retain(|e| e.index != 3);
    }
    assert!(
        loop_closure::validate(
            &receipt,
            &original,
            &graph,
            &AddressSet::new(),
            &transfers,
            &reads,
            &missing
        )
        .is_err()
    );
    let mut bad_graph = graph.clone();
    let first = address(&receipt.region[0]).unwrap();
    bad_graph
        .get_mut(&first)
        .unwrap()
        .may_defs
        .insert("memory:any".into());
    let mut bad_report = original.clone();
    bad_report.graph_sha256 = graph_digest(&bad_graph, &AddressSet::new()).unwrap();
    let CoverageEvidence::InductiveDispatch { receipt: bad } =
        bad_report.resolutions[0].coverage.as_mut().unwrap()
    else {
        unreachable!()
    };
    bad.graph_sha256 = bad_report.graph_sha256.clone();
    assert!(validate(&bad_report, &bad_graph, &AddressSet::new()).is_err());
    assert_eq!(site, address(&original.resolutions[0].site).unwrap());
}

#[test]
fn loop_rule_declines_changed_original_guard_effects_and_explicit_zero_budgets() {
    let (graph, original, fixture) = fixture("da09");
    let reads: Vec<DataRead> = serde_json::from_value(fixture["table_reads"].clone()).unwrap();
    let read = |a, n| {
        Ok(reads
            .iter()
            .find(|r| r.address == hex(a) && r.requested == n)
            .cloned()
            .unwrap_or_else(|| DataRead {
                address: hex(a),
                requested: n,
                bytes_hex: String::new(),
                spans: Vec::new(),
                conflict_sources: Vec::new(),
                stop: "not_captured".into(),
            }))
    };
    for variant in [
        "base-clobber",
        "signed-compare",
        "memory-store",
        "selector-overwrite",
    ] {
        let mut transfers = original.clone();
        let compare = address("0x00007ff77440d9fc").unwrap();
        let pointer = address("0x00007ff77440d9eb").unwrap();
        let load = address("0x00007ff77440da02").unwrap();
        let site = match variant {
            "base-clobber" | "memory-store" => pointer,
            "signed-compare" => compare,
            _ => load,
        };
        let current = &transfers[&site];
        let mut bil: Vec<Stmt> = serde_json::from_str(&current.ast).unwrap();
        let register = |name: &str| crate::bap::ast::Var {
            name: name.into(),
            index: 0,
            virtual_: false,
            width: 64,
            type_: "imm".into(),
        };
        match variant {
            "base-clobber" => bil.push(Stmt::Move {
                var: register("RDX"),
                value: Expr::Int {
                    value: "0:64u".into(),
                },
            }),
            "signed-compare" => {
                fn change(e: &mut Expr) {
                    match e {
                        Expr::Binop { op, lhs, rhs } => {
                            if *op == 3 {
                                *op = 1;
                            }
                            change(lhs);
                            change(rhs);
                        }
                        Expr::Cast { arg, .. }
                        | Expr::Unop { arg, .. }
                        | Expr::Extract { arg, .. } => change(arg),
                        _ => {}
                    }
                }
                for s in &mut bil {
                    if let Stmt::Move { value, .. } = s {
                        change(value);
                    }
                }
            }
            "memory-store" => bil.push(Stmt::Move {
                var: crate::bap::ast::Var {
                    name: "mem".into(),
                    index: 0,
                    virtual_: false,
                    width: 0,
                    type_: "mem".into(),
                },
                value: Expr::Unsupported,
            }),
            "selector-overwrite" => bil.insert(
                0,
                Stmt::Move {
                    var: register("R8"),
                    value: Expr::Int {
                        value: "255:64u".into(),
                    },
                },
            ),
            _ => unreachable!(),
        }
        transfers.insert(
            site,
            extract(&bil, site, &decode_bytes(&current.bytes_hex).unwrap()).unwrap(),
        );
        let result = resolve_candidate(
            "snapshot",
            "artifact",
            &graph,
            &AddressSet::new(),
            &transfers,
            &limits(),
            read,
        )
        .unwrap();
        assert!(!result.resolutions[0].complete, "{variant}");
        assert!(
            !matches!(
                result.resolutions[0].coverage,
                Some(CoverageEvidence::InductiveDispatch { .. })
            ),
            "{variant}"
        );
        validate(&result, &graph, &AddressSet::new()).unwrap();
    }
    for limits in [
        Limits {
            max_steps: 0,
            ..limits()
        },
        Limits {
            max_elapsed_ms: 0,
            ..limits()
        },
        Limits {
            max_values: 0,
            ..limits()
        },
        Limits {
            max_rounds: 0,
            ..limits()
        },
        Limits {
            max_entries: 0,
            ..limits()
        },
    ] {
        let result = resolve_candidate(
            "snapshot",
            "artifact",
            &graph,
            &AddressSet::new(),
            &original,
            &limits,
            read,
        )
        .unwrap();
        assert!(result.resolutions.iter().all(|r| !r.complete));
        validate(&result, &graph, &AddressSet::new()).unwrap();
    }
}

#[test]
fn legacy_coverage_omission_is_distinct_from_explicit_json_null() {
    let (mut report, graph, _, fixture) = report("da09");
    invalidate_loop_coverage(&mut report, "legacy-fixture");
    report.resolutions[0].coverage = None;
    for (schema, profile) in [
        ("ariadne.indirect-target-resolution/v1", PROFILE),
        (
            "ariadne.indirect-target-resolution/v2",
            LEGACY_LOCAL_PROFILE,
        ),
    ] {
        report.schema = schema.into();
        report.profile = profile.into();
        report.graph_sha256 = legacy_graph_digest(&graph, &AddressSet::new()).unwrap();
        let mut encoded = serde_json::to_value(&report).unwrap();
        assert!(encoded["resolutions"][0].get("coverage").is_none());
        let decoded: Report = serde_json::from_value(encoded.clone()).unwrap();
        assert!(decoded.resolutions[0].coverage.is_none());
        encoded["resolutions"][0]["coverage"] = serde_json::Value::Null;
        assert!(
            serde_json::from_value::<Report>(encoded).is_err(),
            "{schema} must reject an explicit null coverage field"
        );
    }
    let legacy = fixture["legacy_resolution"].clone();
    let decoded: Resolution = serde_json::from_value(legacy.clone()).unwrap();
    assert!(decoded.coverage.is_none());
    assert_eq!(
        serde_json::to_value(decoded).unwrap(),
        legacy,
        "legacy row serialization preserves all fields and omits coverage"
    );
}

/// Two separately relocated LEA/JMP corridors enter the same local phase.
/// The generated instruction bytes agree with their semantic VAs and original
/// absolute BIL targets. This is a synthetic graph, not additional dump capture.
#[test]
fn independently_initialized_entrances_both_establish_the_loop_invariant() {
    let (mut graph, mut transfers, fixture) = fixture("da09");
    let old_reset = address("0x00007ff77440d9e2").unwrap();
    let old_jump = address("0x00007ff77440d9e9").unwrap();
    let header = address("0x00007ff77440d9f7").unwrap();
    let base = address("0x00007ff77ba909a8").unwrap();
    let reset = old_reset + 0x100000;
    let jump = reset + 7;
    let mut lea_bytes = vec![0x48, 0x8d, 0x15];
    let lea_displacement = i32::try_from(i128::from(base) - i128::from(jump)).unwrap();
    lea_bytes.extend(lea_displacement.to_le_bytes());
    assert_eq!(jump.wrapping_add(lea_displacement as i64 as u64), base);
    let mut jump_bytes = vec![0xe9];
    let jump_displacement = i32::try_from(i128::from(header) - i128::from(jump + 5)).unwrap();
    jump_bytes.extend(jump_displacement.to_le_bytes());
    assert_eq!(
        (jump + 5).wrapping_add(jump_displacement as i64 as u64),
        header
    );
    let reset_bil: Vec<Stmt> = serde_json::from_str(&transfers[&old_reset].ast).unwrap();
    let jump_bil: Vec<Stmt> = serde_json::from_str(&transfers[&old_jump].ast).unwrap();
    transfers.insert(reset, extract(&reset_bil, reset, &lea_bytes).unwrap());
    transfers.insert(jump, extract(&jump_bil, jump, &jump_bytes).unwrap());
    let mut reset_instruction = graph[&old_reset].clone();
    reset_instruction.fall = [jump].into();
    let jump_instruction = graph[&old_jump].clone();
    graph.insert(reset, reset_instruction);
    graph.insert(jump, jump_instruction);
    let reads: Vec<DataRead> = serde_json::from_value(fixture["table_reads"].clone()).unwrap();
    let report = resolve_candidate(
        "loop-multiple-entrance-snapshot",
        "loop-synthetic-artifact",
        &graph,
        &AddressSet::new(),
        &transfers,
        &limits(),
        |a, n| {
            Ok(reads
                .iter()
                .find(|r| r.address == hex(a) && r.requested == n)
                .unwrap()
                .clone())
        },
    )
    .unwrap();
    assert!(
        report.resolutions[0].complete,
        "{:?}",
        report.resolutions[0].unresolved
    );
    assert_eq!(report.resolutions[0].targets.len(), 4);
    let proof = induction(&report);
    assert_eq!(proof.region.len(), 9);
    assert_eq!(proof.entrances.len(), 2);
    assert_eq!(proof.corridors.len(), 2);
    assert_eq!(
        proof
            .corridors
            .iter()
            .map(|c| c.sites.clone())
            .collect::<Vec<_>>(),
        vec![
            vec![hex(old_reset), hex(old_jump)],
            vec![hex(reset), hex(jump)]
        ]
    );
    assert!(proof.entrances.iter().all(|e| e.to == hex(header)));
    assert_eq!(proof.table.indices, (0..10).collect::<Vec<_>>());
    validate(&report, &graph, &AddressSet::new()).unwrap();
    let mut missing = report.clone();
    let Some(CoverageEvidence::InductiveDispatch { receipt }) =
        missing.resolutions[0].coverage.as_mut()
    else {
        unreachable!()
    };
    receipt.corridors.pop();
    assert!(
        validate(&missing, &graph, &AddressSet::new()).is_err(),
        "each initialized entrance needs its own checked corridor"
    );
    if let Some(directory) = std::env::var_os("ARIADNE_LOOP_RECEIPT_DIR") {
        let directory = std::path::PathBuf::from(directory);
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(
            directory.join("da09-multi-target-report.json"),
            serde_json::to_vec_pretty(&report).unwrap(),
        )
        .unwrap();
        let instructions=graph.iter().map(|(&site,i)|serde_json::json!({"address":hex(site),"kind":format!("{:?}",i.kind).to_lowercase(),"fall":i.fall.iter().copied().map(hex).collect::<Vec<_>>(),"targets":i.targets.iter().copied().map(hex).collect::<Vec<_>>(),"targets_complete":i.complete,"uses":i.uses,"may_defs":i.may_defs,"must_defs":i.must_defs})).collect::<Vec<_>>();
        std::fs::write(
            directory.join("da09-multi-instructions.json"),
            serde_json::to_vec_pretty(&instructions).unwrap(),
        )
        .unwrap();
    }
}
