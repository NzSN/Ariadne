use super::*;
use crate::bap::ast::Lift;
use crate::effects::{PreparationIdentity, SemanticEvidence};
use crate::llvm_mc::{PreparedBatch, PreparedSite};
#[path = "common/mod.rs"]
mod common;

fn case(linux: bool) -> FileSnapshot {
    case_with_ranges(linux, Vec::new())
}

fn case_with_ranges(linux: bool, extra: Vec<(u64, Vec<u8>)>) -> FileSnapshot {
    case_capture(linux, extra, true)
}

fn case_capture(linux: bool, extra: Vec<(u64, Vec<u8>)>, target_code: bool) -> FileSnapshot {
    let corpus: serde_json::Value =
        serde_json::from_str(include_str!("../bap/fixtures/target-resolution-bil.json")).unwrap();
    let mut ranges: Vec<(u64, Vec<u8>)> = Vec::new();
    for row in corpus["rows"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|r| r["schema"] == "ariadne.bap-site/v1")
    {
        let va =
            u64::from_str_radix(row["va"].as_str().unwrap().trim_start_matches("0x"), 16).unwrap();
        let text = row["bytes"].as_str().unwrap();
        let bytes = (0..text.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&text[i..i + 2], 16).unwrap())
            .collect();
        ranges.push((va, bytes));
    }
    let record: serde_json::Value =
        serde_json::from_str(include_str!("../bap/fixtures/target-resolution-table.json")).unwrap();
    if target_code {
        for target in record["unique_targets"].as_array().unwrap() {
            ranges.push((
                u64::from_str_radix(target.as_str().unwrap().trim_start_matches("0x"), 16).unwrap(),
                vec![0xc3],
            ));
        }
    }
    ranges.push((
        0x7ff64791ef58,
        include_bytes!("../bap/fixtures/target-resolution-table.bin").to_vec(),
    ));
    ranges.extend(extra);
    let mut dump = common::Dump::new(linux);
    dump.memory64(
        &ranges
            .iter()
            .map(|(a, b)| (*a, b.as_slice()))
            .collect::<Vec<_>>(),
    );
    FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap()
}
fn batch(
    candidates: &BTreeMap<u64, Option<Vec<u8>>>,
) -> (
    PreparedBatch,
    BTreeMap<u64, crate::bap::target_resolution::Transfer>,
) {
    let corpus: serde_json::Value =
        serde_json::from_str(include_str!("../bap/fixtures/target-resolution-bil.json")).unwrap();
    let mut sites = BTreeMap::new();
    let mut transfers = BTreeMap::new();
    for (&va, prefix) in candidates {
        let lift = corpus["rows"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| {
                r["schema"] == "ariadne.bap-site/v1"
                    && u64::from_str_radix(r["va"].as_str().unwrap().trim_start_matches("0x"), 16)
                        .unwrap()
                        == va
            })
            .map(|v| serde_json::from_value::<Lift>(v.clone()).unwrap());
        let mut instruction = Instruction {
            kind: InstructionKind::Return,
            complete: true,
            ..Instruction::default()
        };
        let mut evidence = placeholder();
        let available = prefix.is_some();
        if let Some(lift) = lift {
            let bytes = prefix.as_ref().unwrap()[..usize::from(lift.length)].to_vec();
            let projection =
                crate::bap::test_project(&lift.bil, lift.opcode.as_deref().unwrap(), &bytes, va)
                    .unwrap();
            let t = crate::bap::target_resolution::extract(&lift.bil, va, &bytes).unwrap();
            let p = lift.properties.as_ref().unwrap();
            let kind = if p.indirect {
                InstructionKind::Indirect
            } else if p.conditional {
                InstructionKind::Conditional
            } else {
                InstructionKind::Ordinary
            };
            instruction = Instruction {
                kind,
                complete: kind != InstructionKind::Indirect,
                fall: if kind == InstructionKind::Indirect {
                    AddressSet::new()
                } else {
                    [va + u64::from(lift.length)].into()
                },
                targets: projection.targets.into_iter().flatten().collect(),
                uses: projection.uses,
                may_defs: projection.may_defs,
                must_defs: projection.must_defs,
            };
            evidence.bytes = bytes;
            evidence.length = lift.length;
            evidence.opcode = lift.opcode;
            evidence.quality = EffectQuality::ExternalLifted;
            evidence.semantic = Some(SemanticEvidence {
                backend: "bap-x86-legacy".into(),
                helper_sha256: "a".repeat(64),
                runtime_sha256: "b".repeat(64),
                projection: "bap-bit-provenance-v3".into(),
                status: "projected".into(),
                ast_sha256: Some(t.ast_sha256.clone()),
                fallback: None,
                gaps: Vec::new(),
                memory_accesses: Vec::new(),
            });
            transfers.insert(va, t);
        } else if let Some(prefix) = prefix {
            evidence.bytes = prefix[..1].to_vec();
            evidence.length = 1;
        }
        evidence.source = if available {
            ByteSource::Captured
        } else {
            ByteSource::Unavailable
        };
        evidence.control = Some(instruction.kind);
        sites.insert(
            va,
            PreparedSite {
                instruction,
                evidence,
                gaps: Vec::new(),
                decodable: available,
                complete_capture: available,
            },
        );
    }
    (
        PreparedBatch {
            sites,
            identity: PreparationIdentity {
                target: "mock AMD64".into(),
                decoder: "independent frozen fixture".into(),
                protocol: 2,
                ruleset: "bap-bit-provenance-v3".into(),
                catalogue: "gpr-bytes-status-df-memory-other-v1".into(),
            },
        },
        transfers,
    )
}
#[test]
fn both_platforms_expand_targets_without_promoting_seeds_to_roots() {
    for linux in [false, true] {
        let snapshot = case(linux);
        let query = AnalysisQuery {
            entry_points: [0x7ff640079640].into(),
            slice_seeds: [0x7ff640079670, 0xdead0000].into(),
        };
        let prepared = snapshot
            .prepare_materialization(
                &query,
                &PreparationOptions::default(),
                PrepareLimits::default(),
                Some(&crate::bap::target_resolution::Limits::default()),
                |_, c, _, _| Ok(batch(c)),
            )
            .unwrap();
        prepared.validate_target_resolution().unwrap();
        let row = &prepared.target_resolution().unwrap().resolutions[0];
        assert!(row.complete);
        assert_eq!(row.targets.len(), 45);
        assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
        assert!(!prepared.materialization.attempted.contains(&0xdead0000));
        for t in &row.targets {
            assert!(
                prepared
                    .materialization
                    .attempted
                    .contains(&u64::from_str_radix(t.trim_start_matches("0x"), 16).unwrap())
            );
        }
        let analyzed = crate::analyze(prepared.prepared.request.clone()).unwrap();
        assert_eq!(
            analyzed
                .state
                .edges
                .iter()
                .filter(|e| e.src == 0x7ff64007968b && e.kind == EdgeKind::Indirect)
                .count(),
            45
        );
        assert!(
            !analyzed
                .state
                .obligations
                .iter()
                .any(|o| o.site == 0x7ff64007968b)
        );
        let json = crate::input::report::render(
            &prepared,
            &analyzed,
            crate::input::report::ReportFormat::Json,
            false,
        )
        .unwrap();
        let value: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(value["schema"], "ariadne-minidump-report-v2");
        assert_eq!(
            value["target_resolution"]["memory_premise"],
            "FrozenCapturedControlData"
        );
    }
}
#[test]
fn disabled_mode_keeps_the_original_query_and_unresolved_jump() {
    let snapshot = case(false);
    let query = AnalysisQuery {
        entry_points: [0x7ff640079640].into(),
        slice_seeds: [0x7ff640079670].into(),
    };
    let p = snapshot
        .prepare_with_preparer(
            &query,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            |_, c, _, _| Ok(batch(c).0),
        )
        .unwrap();
    assert!(p.target_resolution().is_none());
    assert!(
        p.prepared.request.instructions[&0x7ff64007968b]
            .targets
            .is_empty()
    );
    let a = crate::analyze(p.prepared.request.clone()).unwrap();
    let report =
        crate::input::report::render(&p, &a, crate::input::report::ReportFormat::Json, false)
            .unwrap();
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&report).unwrap()["schema"],
        "ariadne-minidump-report-v1"
    );
}

#[test]
fn prepared_target_resolution_rejects_changed_semantic_source() {
    let snapshot = case(false);
    let mut prepared = snapshot
        .prepare_materialization(
            &AnalysisQuery {
                entry_points: [0x7ff640079640].into(),
                slice_seeds: AddressSet::new(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&crate::bap::target_resolution::Limits::default()),
            |_, candidates, _, _| Ok(batch(candidates)),
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    let source =
        parse_target_address(&prepared.target_resolution().unwrap().transfers[0].site).unwrap();
    prepared
        .prepared
        .instructions
        .get_mut(&source)
        .unwrap()
        .bytes[0] ^= 1;
    assert!(prepared.validate_target_resolution().is_err());
}

#[test]
fn captured_table_targets_remain_edges_when_destination_code_is_missing() {
    let snapshot = case_capture(false, Vec::new(), false);
    let prepared = snapshot
        .prepare_materialization(
            &AnalysisQuery {
                entry_points: [0x7ff640079640].into(),
                slice_seeds: AddressSet::new(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&crate::bap::target_resolution::Limits::default()),
            |_, candidates, _, _| Ok(batch(candidates)),
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    let report = prepared.target_resolution().unwrap();
    assert_eq!(report.resolutions[0].targets.len(), 45);
    assert_eq!(
        prepared.prepared.request.instructions[&0x7ff64007968b]
            .targets
            .len(),
        45
    );
    let analyzed = crate::analyze(prepared.prepared.request.clone()).unwrap();
    for target in &report.resolutions[0].targets {
        let target = parse_target_address(target).unwrap();
        assert!(analyzed.state.edges.iter().any(|edge| {
            edge.src == 0x7ff64007968b && edge.dst == target && edge.kind == EdgeKind::Indirect
        }));
        assert!(
            analyzed
                .state
                .obligations
                .iter()
                .any(|o| { o.site == target && o.reason == crate::ObligationReason::Unavailable })
        );
    }
}
#[test]
fn zero_rounds_yields_a_valid_partial_report() {
    let snapshot = case(false);
    let query = AnalysisQuery {
        entry_points: [0x7ff640079640].into(),
        slice_seeds: AddressSet::new(),
    };
    let limits = crate::bap::target_resolution::Limits {
        max_rounds: 0,
        ..Default::default()
    };
    let p = snapshot
        .prepare_materialization(
            &query,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&limits),
            |_, c, _, _| Ok(batch(c)),
        )
        .unwrap();
    p.validate_target_resolution().unwrap();
    assert_eq!(
        p.target_resolution().unwrap().stop.as_deref(),
        Some("discovery-round-limit")
    );
    assert!(
        p.prepared.request.instructions[&0x7ff64007968b]
            .targets
            .is_empty()
    );
    assert!(!p.prepared.request.instructions[&0x7ff64007968b].complete);
}

fn first_table_target() -> u64 {
    let record: serde_json::Value =
        serde_json::from_str(include_str!("../bap/fixtures/target-resolution-table.json")).unwrap();
    parse_target_address(record["unique_targets"][0].as_str().unwrap()).unwrap()
}

#[test]
fn bounded_revalidation_retains_targets_when_new_predecessors_exhaust_work() {
    let incoming: Vec<_> = (0..200).map(|n| 0x7fff00000000 + n).collect();
    let snapshot = case_with_ranges(false, incoming.iter().map(|a| (*a, vec![0x90])).collect());
    let limits = crate::bap::target_resolution::Limits {
        // Enough for the original path; the target exposes 200 new branches
        // that consume this pass before it can revisit that original path.
        max_steps: 791,
        ..Default::default()
    };
    let query = AnalysisQuery {
        entry_points: [0x7ff640079640].into(),
        slice_seeds: [0x7ff640079670].into(),
    };
    let target = first_table_target();
    let prepared = snapshot
        .prepare_materialization(
            &query,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&limits),
            |_, candidates, _, _| {
                let (mut batch, transfers) = batch(candidates);
                if let Some(site) = batch.sites.get_mut(&target) {
                    site.instruction.kind = InstructionKind::Ordinary;
                    site.instruction.fall = [incoming[0]].into();
                }
                for (index, address) in incoming.iter().enumerate() {
                    if let Some(site) = batch.sites.get_mut(address) {
                        site.instruction.kind = InstructionKind::Conditional;
                        site.instruction.fall =
                            [incoming.get(index + 1).copied().unwrap_or(address + 1)].into();
                        site.instruction.targets = [0x7ff640079688].into();
                    }
                }
                Ok((batch, transfers))
            },
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    let report = prepared.target_resolution().unwrap();
    let row = &report.resolutions[0];
    assert_eq!(row.targets.len(), 45);
    assert!(!row.complete);
    assert!(!row.paths.is_empty());
    assert!(!report.data_reads.is_empty());
    assert!(
        incoming
            .iter()
            .all(|a| prepared.materialization.attempted.contains(a))
    );
    let analyzed = crate::analyze(prepared.prepared.request.clone()).unwrap();
    assert_eq!(
        analyzed
            .state
            .edges
            .iter()
            .filter(|edge| { edge.src == 0x7ff64007968b && edge.kind == EdgeKind::Indirect })
            .count(),
        45
    );
    assert!(
        analyzed
            .state
            .obligations
            .iter()
            .any(|o| o.site == 0x7ff64007968b)
    );
}

#[test]
fn discovery_round_stop_preserves_witnesses_and_downgrades_coverage() {
    let snapshot = case(false);
    let limits = crate::bap::target_resolution::Limits {
        max_rounds: 1,
        ..Default::default()
    };
    let prepared = snapshot
        .prepare_materialization(
            &AnalysisQuery {
                entry_points: [0x7ff640079640].into(),
                slice_seeds: AddressSet::new(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&limits),
            |_, candidates, _, _| Ok(batch(candidates)),
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    let report = prepared.target_resolution().unwrap();
    assert_eq!(report.stop.as_deref(), Some("discovery-round-limit"));
    assert_eq!(report.resolutions[0].targets.len(), 45);
    assert!(!report.resolutions[0].complete);
}

#[test]
fn fitting_retention_merge_rejects_invalid_evidence_instead_of_falling_back() {
    let snapshot = case(false);
    let prepared = snapshot
        .prepare_materialization(
            &AnalysisQuery {
                entry_points: [0x7ff640079640].into(),
                slice_seeds: AddressSet::new(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&crate::bap::target_resolution::Limits::default()),
            |_, candidates, _, _| Ok(batch(candidates)),
        )
        .unwrap();
    let previous = prepared.target_resolution().unwrap().clone();
    let mut current = previous.clone();
    let row = &mut current.resolutions[0];
    let removed = row.targets.pop().unwrap();
    for path in &mut row.paths {
        path.entries.retain(|entry| entry.target != removed);
    }
    row.complete = false;
    row.unresolved.insert("resolution-work-limit".into());
    current.transfers[0].ast_sha256 = "0".repeat(64);
    let result = TargetResolutionCoordinator::retain_witnesses(
        previous,
        current,
        &prepared.prepared.request.instructions,
        &prepared.prepared.request.entry_points,
    );
    assert!(
        result
            .unwrap_err()
            .to_string()
            .contains("resolver AST digest"),
        "invalid current evidence must not be hidden by a valid previous receipt"
    );
}

#[test]
fn evidence_stop_keeps_previously_admitted_targets_within_the_cap() {
    let snapshot = case(false);
    let query = AnalysisQuery {
        entry_points: [0x7ff640079640].into(),
        slice_seeds: AddressSet::new(),
    };
    let prepare = |limits: &crate::bap::target_resolution::Limits| {
        snapshot.prepare_materialization(
            &query,
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(limits),
            |_, candidates, _, _| {
                let (mut batch, transfers) = batch(candidates);
                // A discovered target introduces a new unsupported dispatch,
                // so its residual row increases the next pass's evidence.
                if let Some(site) = batch.sites.get_mut(&first_table_target()) {
                    site.instruction.kind = InstructionKind::Indirect;
                    site.instruction.complete = false;
                }
                Ok((batch, transfers))
            },
        )
    };
    let first = prepare(&crate::bap::target_resolution::Limits {
        max_rounds: 1,
        ..Default::default()
    })
    .unwrap();
    let evidence_cap = serde_json::to_vec(first.target_resolution().unwrap())
        .unwrap()
        .len()
        + 8;
    let limits = crate::bap::target_resolution::Limits {
        max_evidence_bytes: evidence_cap,
        ..Default::default()
    };
    let prepared = prepare(&limits).unwrap();
    prepared.validate_target_resolution().unwrap();
    let report = prepared.target_resolution().unwrap();
    assert_eq!(report.resolutions[0].targets.len(), 45);
    assert!(!report.resolutions[0].complete);
    assert_eq!(report.stop.as_deref(), Some("resolution-retention-limit"));
    assert!(serde_json::to_vec(report).unwrap().len() <= evidence_cap);
    assert!(!prepared.prepared.request.instructions[&first_table_target()].complete);
}

#[test]
#[ignore = "requires pinned BAP/LLVM and rebuilt native target-resolution helper"]
fn actual_bap_lifts_and_native_rust_results_agree_on_both_capture_platforms() {
    for linux in [false, true] {
        let snapshot = case(linux);
        let query = AnalysisQuery {
            entry_points: [0x7ff640079640].into(),
            slice_seeds: [0x7ff640079670].into(),
        };
        let p = snapshot
            .prepare_with_bap_target_resolution(
                &query,
                &std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("target/ariadne-llvm-mc"),
                &crate::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                crate::bap::target_resolution::Limits::default(),
            )
            .unwrap();
        p.validate_target_resolution().unwrap();
        assert_eq!(
            p.target_resolution().unwrap().resolutions[0].targets.len(),
            45
        );
        assert!(p.target_resolution().unwrap().resolutions[0].complete);
        let config = crate::bap::core_session::CoreConfig::from_directory(
            std::env::var_os("ARIADNE_BAP_CORE_DIR")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|| {
                    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                        .join("target/indirect-target-resolution-native")
                }),
        );
        let native = crate::bap::core_adapter::NativeAnalyzer::from_capture(
            &config,
            "target-resolution-fixture",
            &p,
        )
        .unwrap()
        .complete()
        .unwrap()
        .into_result();
        let rust = crate::analyze(p.prepared.request.clone()).unwrap();
        assert_eq!(native, rust);
        assert_eq!(
            native
                .state
                .edges
                .iter()
                .filter(|e| e.src == 0x7ff64007968b && e.kind == EdgeKind::Indirect)
                .count(),
            45
        );
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM and rebuilt native target-resolution helper"]
fn captured_pointer_slot_resolves_even_when_destination_code_is_missing() {
    for (slot_present, conflict, expected) in [
        (true, false, true),
        (false, false, false),
        (true, true, false),
    ] {
        let code = [0xff, 0x25, 0xfa, 0x01, 0x00, 0x00];
        let pointer = 0xffff_ffff_ffff_fff9u64.to_le_bytes();
        let other = 0x402000u64.to_le_bytes();
        let mut ranges = vec![(0x401000, code.as_slice())];
        if slot_present {
            ranges.push((0x401200, pointer.as_slice()));
        }
        if conflict {
            ranges.push((0x401200, other.as_slice()));
        }
        let mut dump = common::Dump::new(false);
        dump.memory64(&ranges);
        let snapshot =
            FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
        let q = AnalysisQuery {
            entry_points: [0x401000].into(),
            slice_seeds: [0x401000].into(),
        };
        let p = snapshot
            .prepare_with_bap_target_resolution(
                &q,
                &std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("target/ariadne-llvm-mc"),
                &crate::bap::Config::from_env(),
                &PreparationOptions::default(),
                PrepareLimits::default(),
                crate::bap::target_resolution::Limits::default(),
            )
            .unwrap();
        p.validate_target_resolution().unwrap();
        let row = &p.target_resolution().unwrap().resolutions[0];
        assert_eq!(row.complete, expected);
        assert_eq!(row.targets.len(), usize::from(expected));
        if conflict {
            assert!(
                !p.target_resolution().unwrap().data_reads[0]
                    .conflict_sources
                    .is_empty()
            );
        }
        let config = crate::bap::core_session::CoreConfig::from_directory(
            std::env::var_os("ARIADNE_BAP_CORE_DIR")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|| {
                    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                        .join("target/indirect-target-resolution-native")
                }),
        );
        let native = crate::bap::core_adapter::NativeAnalyzer::from_capture(
            &config,
            "target-pointer-fixture",
            &p,
        )
        .unwrap()
        .complete()
        .unwrap()
        .into_result();
        assert_eq!(native, crate::analyze(p.prepared.request.clone()).unwrap());
        if expected {
            assert!(native.state.edges.iter().any(|e| e.src == 0x401000
                && e.dst == 0xffff_ffff_ffff_fff9
                && e.kind == EdgeKind::Indirect));
            assert!(
                native
                    .state
                    .obligations
                    .iter()
                    .any(|o| o.site == 0xffff_ffff_ffff_fff9
                        && o.reason == crate::ObligationReason::Unavailable)
            );
        }
    }
}

fn native_capture_request(p: &FilePreparedAnalysis) -> serde_json::Value {
    use serde_json::json;
    let context = crate::input::investigation::capture_context(p).unwrap();
    let sites = context.sites.iter().map(|s| json!({
        "address":format!("0x{:016x}",s.va),"bytes":s.bytes_hex,"captured":s.captured,
        "quality":s.quality,"status":s.semantic_status,"helper_sha256":s.helper_sha256,
        "runtime_sha256":s.runtime_sha256,"ast_sha256":s.ast_sha256,"projection":s.projection,
        "spans":s.spans.iter().map(|span| json!({"address":format!("0x{:016x}",span.va),"length":span.length,
            "contributors":span.contributors.iter().map(|c| json!({"stream":c.stream,"entry":c.entry,"file_offset":c.file_offset.to_string()})).collect::<Vec<_>>()
        })).collect::<Vec<_>>()
    })).collect::<Vec<_>>();
    json!({"normalized":crate::bap::core_adapter::encode_request(&p.prepared.request).unwrap(),
        "capture":{"snapshot":context.snapshot_id,"artifact_sha256":context.artifact_sha256,
            "query_id":context.query_id,"semantic_profile":context.semantic_profile,"sites":sites},
        "target_resolution":p.target_resolution().unwrap()})
}

#[test]
#[ignore = "requires pinned helpers; bypasses Rust receipt prevalidation"]
fn native_rejects_resolver_receipt_tampering_directly() {
    use serde_json::{Value, json};
    let snapshot = case(false);
    let p = snapshot
        .prepare_with_bap_target_resolution(
            &AnalysisQuery {
                entry_points: [0x7ff640079640].into(),
                slice_seeds: [0x7ff640079670].into(),
            },
            &std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/ariadne-llvm-mc"),
            &crate::bap::Config::from_env(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
            crate::bap::target_resolution::Limits::default(),
        )
        .unwrap();
    let good = native_capture_request(&p);
    let config = crate::bap::core_session::CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| {
                std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
            }),
    );
    let run = |input: &Value| {
        crate::bap::core_session::CoreSession::start_profile(
            &config,
            "hostile-resolver-receipt",
            &p.prepared.request.snapshot_id,
            crate::bap::core_protocol::TARGET_PROFILE,
            input,
        )
    };
    let (_session, response) = run(&good).unwrap();
    assert!(response.error.is_none());
    for mutation in [
        "premise",
        "snapshot",
        "artifact",
        "source",
        "offset",
        "index",
        "missing-entry",
        "contributor",
        "guard-bypass",
        "targets",
        "target-budget",
        "read-budget",
        "evidence-budget",
        "evidence-budget-forged-stop",
        "entry-budget",
        "step-budget",
        "path-budget",
        "value-budget",
        "round-budget",
        "elapsed-budget",
    ] {
        let mut bad = good.clone();
        match mutation {
            "premise" => bad["target_resolution"]["memory_premise"] = json!("ObservedOnly"),
            "snapshot" => bad["target_resolution"]["snapshot"] = json!("another-snapshot"),
            "artifact" => bad["target_resolution"]["artifact_sha256"] = json!("0".repeat(64)),
            "source" => bad["target_resolution"]["transfers"][0]["bytes_hex"] = json!("90"),
            "offset" => {
                bad["target_resolution"]["resolutions"][0]["paths"][0]["entries"][0]["target"] =
                    json!("0x0000000000000000")
            }
            "index" => bad["target_resolution"]["resolutions"][0]["paths"][0]["indices"]
                .as_array_mut()
                .unwrap()
                .pop()
                .map(|_| ())
                .unwrap(),
            "missing-entry" => bad["target_resolution"]["resolutions"][0]["paths"][0]["entries"]
                .as_array_mut()
                .unwrap()
                .pop()
                .map(|_| ())
                .unwrap(),
            "contributor" => {
                bad["target_resolution"]["data_reads"][0]["spans"][0]["contributors"] = json!([])
            }
            "guard-bypass" => bad["normalized"]["entry_points"]
                .as_array_mut()
                .unwrap()
                .push(json!("0x00007ff640079684")),
            "targets" => bad["target_resolution"]["resolutions"][0]["targets"] = json!([]),
            "target-budget" => bad["target_resolution"]["limits"]["max_targets"] = json!(0),
            "read-budget" => bad["target_resolution"]["limits"]["max_read_bytes"] = json!(0),
            "evidence-budget" => {
                bad["target_resolution"]["limits"]["max_evidence_bytes"] = json!(0)
            }
            "evidence-budget-forged-stop" => {
                bad["target_resolution"]["limits"]["max_evidence_bytes"] = json!(0);
                bad["target_resolution"]["stop"] = json!("resolution-evidence-limit");
                for row in bad["target_resolution"]["resolutions"]
                    .as_array_mut()
                    .unwrap()
                {
                    row["complete"] = json!(false);
                }
                for instruction in bad["normalized"]["instructions"].as_array_mut().unwrap() {
                    if instruction["kind"] == "indirect" {
                        instruction["targets_complete"] = json!(false);
                    }
                }
            }
            "entry-budget" => bad["target_resolution"]["limits"]["max_entries"] = json!(0),
            "step-budget" => bad["target_resolution"]["limits"]["max_steps"] = json!(0),
            "path-budget" => bad["target_resolution"]["limits"]["max_path_steps"] = json!(0),
            "value-budget" => bad["target_resolution"]["limits"]["max_values"] = json!(0),
            "round-budget" => bad["target_resolution"]["limits"]["max_rounds"] = json!(0),
            "elapsed-budget" => bad["target_resolution"]["limits"]["max_elapsed_ms"] = json!(0),
            _ => unreachable!(),
        }
        let rejected = match run(&bad) {
            Err(_) => true,
            Ok((_session, response)) => response.error.is_some(),
        };
        assert!(rejected, "native admitted resolver {mutation} mutation");
    }
}

#[test]
#[ignore = "requires rebuilt native target-resolution helper"]
fn native_requires_all_combinations_of_successive_diamonds() {
    use crate::bap::ast::{Expr, Stmt, Var};
    use serde_json::json;
    let variable = |name: &str| Var {
        name: name.into(),
        index: 0,
        virtual_: false,
        width: 64,
        type_: "imm".into(),
    };
    let graph: BTreeMap<_, _> = [
        (1, InstructionKind::Conditional, vec![2], vec![3]),
        (2, InstructionKind::Ordinary, vec![4], vec![]),
        (3, InstructionKind::Ordinary, vec![4], vec![]),
        (4, InstructionKind::Conditional, vec![5], vec![6]),
        (5, InstructionKind::Ordinary, vec![7], vec![]),
        (6, InstructionKind::Ordinary, vec![7], vec![]),
        (7, InstructionKind::Indirect, vec![], vec![]),
    ]
    .into_iter()
    .map(|(a, kind, fall, targets)| {
        (
            a,
            Instruction {
                kind,
                fall: fall.into_iter().collect(),
                targets: targets.into_iter().collect(),
                complete: kind != InstructionKind::Indirect,
                ..Instruction::default()
            },
        )
    })
    .collect();
    let mut semantics = BTreeMap::new();
    for (site, bank, value) in [
        (2, "RAX", 4096),
        (3, "RAX", 8192),
        (5, "RBX", 0),
        (6, "RBX", 8),
    ] {
        semantics.insert(
            site,
            vec![Stmt::Move {
                var: variable(bank),
                value: Expr::Int {
                    value: format!("{value}:64"),
                },
            }],
        );
    }
    semantics.insert(
        7,
        vec![Stmt::Jump {
            target: Expr::Load {
                width: 64,
                mem: Box::new(Expr::Unknown {
                    reason: "captured".into(),
                }),
                addr: Box::new(Expr::Binop {
                    op: 18,
                    lhs: Box::new(Expr::Var {
                        var: variable("RAX"),
                    }),
                    rhs: Box::new(Expr::Var {
                        var: variable("RBX"),
                    }),
                }),
            },
        }],
    );
    let mut ranges = vec![(1, vec![0x90; 7])];
    for slot in [0x1000u64, 0x1008, 0x2000, 0x2008] {
        ranges.push((slot, (slot + 0x4000).to_le_bytes().to_vec()));
    }
    let mut dump = common::Dump::new(false);
    dump.memory64(
        &ranges
            .iter()
            .map(|(a, b)| (*a, b.as_slice()))
            .collect::<Vec<_>>(),
    );
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let prepared = snapshot
        .prepare_materialization(
            &AnalysisQuery {
                entry_points: [1].into(),
                slice_seeds: AddressSet::new(),
            },
            &PreparationOptions::default(),
            PrepareLimits::default(),
            Some(&crate::bap::target_resolution::Limits::default()),
            |_, candidates, _, _| {
                let (mut batch, mut transfers) = batch(candidates);
                for (&site, record) in &mut batch.sites {
                    let Some(instruction) = graph.get(&site) else {
                        continue;
                    };
                    record.instruction = instruction.clone();
                    let transfer = crate::bap::target_resolution::extract(
                        semantics.get(&site).map(Vec::as_slice).unwrap_or_default(),
                        site,
                        &[0x90],
                    )
                    .unwrap();
                    record.evidence.quality = EffectQuality::ExternalLifted;
                    record.evidence.semantic = Some(SemanticEvidence {
                        backend: "bap-x86-legacy".into(),
                        helper_sha256: "a".repeat(64),
                        runtime_sha256: "b".repeat(64),
                        projection: "bap-bit-provenance-v3".into(),
                        status: "projected".into(),
                        ast_sha256: Some(transfer.ast_sha256.clone()),
                        fallback: None,
                        gaps: Vec::new(),
                        memory_accesses: Vec::new(),
                    });
                    transfers.insert(site, transfer);
                }
                Ok((batch, transfers))
            },
        )
        .unwrap();
    prepared.validate_target_resolution().unwrap();
    let report = prepared.target_resolution().unwrap();
    assert!(report.resolutions[0].complete);
    assert_eq!(report.resolutions[0].paths.len(), 4);
    let config = crate::bap::core_session::CoreConfig::from_directory(
        std::env::var_os("ARIADNE_BAP_CORE_DIR")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| {
                std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/bap-core-native")
            }),
    );
    let run = |request: &serde_json::Value| {
        crate::bap::core_session::CoreSession::start_profile(
            &config,
            "diamond-target-receipt",
            &prepared.prepared.request.snapshot_id,
            crate::bap::core_protocol::TARGET_PROFILE,
            request,
        )
    };
    let mut request = native_capture_request(&prepared);
    assert!(run(&request).unwrap().1.error.is_none());
    for (max_values, accepted) in [(2, false), (3, true)] {
        let mut bounded = request.clone();
        bounded["target_resolution"]["limits"]["max_values"] = json!(max_values);
        let admitted = match run(&bounded) {
            Err(_) => false,
            Ok((_, response)) => response.error.is_none(),
        };
        assert_eq!(admitted, accepted, "frontier cap {max_values}");
    }
    let row = &mut request["target_resolution"]["resolutions"][0];
    row["paths"].as_array_mut().unwrap().retain(|path| {
        let addresses = path["reverse_path"].as_array().unwrap();
        addresses.contains(&json!("0x0000000000000002"))
            == addresses.contains(&json!("0x0000000000000005"))
    });
    let targets: BTreeSet<_> = row["paths"]
        .as_array()
        .unwrap()
        .iter()
        .flat_map(|path| path["entries"].as_array().unwrap())
        .map(|entry| entry["target"].as_str().unwrap().to_owned())
        .collect();
    row["targets"] = json!(targets);
    request["normalized"]["instructions"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|instruction| instruction["address"] == "0x0000000000000007")
        .unwrap()["targets"] = json!(targets);
    assert_eq!(
        request["target_resolution"]["resolutions"][0]["paths"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert!(match run(&request) {
        Err(_) => true,
        Ok((_, response)) => response.error.is_some(),
    });
    request["target_resolution"]["resolutions"][0]["complete"] = json!(false);
    request["normalized"]["instructions"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|instruction| instruction["address"] == "0x0000000000000007")
        .unwrap()["targets_complete"] = json!(false);
    assert!(run(&request).unwrap().1.error.is_none());
}
