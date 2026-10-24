//! Independent native consumer of the bounded memory-MOV8 domain.
//! Raw encoding fields define expectations; production register/address parsers
//! and the projection are never used to manufacture expected byte origins.
use super::{bank_cells, cell, common, core, decoder, entry_origins, locations, producer, target};
use crate::bap::core_adapter::NativeAnalyzer;
use crate::effects::{EffectQuality, PreparationOptions};
use crate::input::{AnalysisQuery, FilePreparedAnalysis, FileSnapshot, OpenLimits, PrepareLimits};
use crate::{
    Address, AddressSet, AnalysisView, Analyzer, ByteSource, CompletedAnalysis, Definition,
    DefinitionOrigin, Edge, EdgeKind, InstructionKind, LocationSet, Obligation, ObligationReason,
    Phase,
};
use std::collections::BTreeSet;

#[derive(Clone, Debug)]
struct Case {
    index: usize,
    bytes: Vec<u8>,
    load: bool,
    data: (usize, usize),
    address_reads: LocationSet,
}

fn cases(address32: bool) -> Vec<Case> {
    let mut cases = Vec::new();
    for rex in [
        None,
        Some(0x40),
        Some(0x41),
        Some(0x42),
        Some(0x43),
        Some(0x44),
        Some(0x45),
        Some(0x46),
        Some(0x47),
    ] {
        for opcode in [0x88, 0x8a] {
            for register in [0_u8, 4] {
                for mode in 0_u8..3 {
                    for rm in [0_u8, 4, 5] {
                        let sibs: Vec<Option<u8>> = if rm == 4 {
                            [0x00, 0x05, 0x20, 0x25, 0xc0, 0xc5, 0xe0, 0xe5]
                                .into_iter()
                                .map(Some)
                                .collect()
                        } else {
                            vec![None]
                        };
                        for sib in sibs {
                            let width = if mode == 1 {
                                1
                            } else if mode == 2
                                || mode == 0 && (rm == 5 || sib.is_some_and(|b| b & 7 == 5))
                            {
                                4
                            } else {
                                0
                            };
                            let values: &[i32] = match width {
                                1 => &[-128, 0, 127],
                                4 => &[i32::MIN, 0, i32::MAX],
                                _ => &[0],
                            };
                            for displacement in values {
                                let mut bytes = if address32 { vec![0x67] } else { Vec::new() };
                                bytes.extend(rex);
                                bytes.extend([opcode, mode << 6 | register << 3 | rm]);
                                bytes.extend(sib);
                                bytes.extend(&displacement.to_le_bytes()[..width]);
                                let bits = rex.unwrap_or(0);
                                let data = if rex.is_none() && register == 4 {
                                    (0, 1)
                                } else {
                                    (usize::from(register + if bits & 4 == 0 { 0 } else { 8 }), 0)
                                };
                                let mut address_reads = LocationSet::new();
                                if !(mode == 0 && (rm == 5 || sib.is_some_and(|b| b & 7 == 5))) {
                                    let base = sib.map_or(rm, |b| b & 7)
                                        + if bits & 1 == 0 { 0 } else { 8 };
                                    address_reads.extend(bank_cells(usize::from(base)));
                                }
                                if let Some(sib) = sib {
                                    let index = (sib >> 3) & 7;
                                    if index != 4 || bits & 2 != 0 {
                                        address_reads.extend(bank_cells(usize::from(
                                            index + if bits & 2 == 0 { 0 } else { 8 },
                                        )));
                                    }
                                }
                                cases.push(Case {
                                    index: cases.len(),
                                    bytes,
                                    load: opcode == 0x8a,
                                    data,
                                    address_reads,
                                });
                            }
                        }
                    }
                }
            }
        }
    }
    cases
}

#[derive(Clone, Debug)]
struct Block {
    entry: Address,
    consumer: Address,
    terminal: Address,
    bytes: Vec<u8>,
}

fn prepare(
    batch: &[Case],
    linux: bool,
    refused: bool,
) -> (FilePreparedAnalysis, Vec<Block>, Address) {
    let base = if linux { 0x401000 } else { 0x7ff700001000 };
    let extra_seed = base + 0x8000_0000;
    let blocks: Vec<_> = batch
        .iter()
        .map(|case| {
            let entry = base + case.index as u64 * 0x1000;
            let consumer = entry + case.bytes.len() as u64;
            let mut bytes = case.bytes.clone();
            if case.load {
                // MOV r15, the complete data bank: observe the overwritten byte
                // together with all seven preserved bytes, without a self-copy.
                let bank = case.data.0 as u8;
                bytes.extend([
                    0x49 | if bank >= 8 { 4 } else { 0 },
                    0x89,
                    0xc7 | (bank & 7) << 3,
                ]);
            } else {
                // MOV r15,[r14]: this reads aggregate memory after a possible store.
                bytes.extend([0x4d, 0x8b, 0x3e]);
            }
            bytes.push(0xc3);
            Block {
                entry,
                consumer,
                terminal: consumer + 3,
                bytes,
            }
        })
        .collect();
    let mut ranges: Vec<_> = blocks
        .iter()
        .map(|b| (b.entry, b.bytes.as_slice()))
        .collect();
    ranges.push((extra_seed, &[0x90, 0xc3]));
    let mut dump = common::Dump::new(linux);
    dump.memory64(&ranges);
    let snapshot = FileSnapshot::from_minidump_bytes(dump.finish(), OpenLimits::default()).unwrap();
    let query = AnalysisQuery {
        entry_points: blocks.iter().map(|b| b.entry).collect(),
        slice_seeds: blocks
            .iter()
            .map(|b| b.consumer)
            .chain([extra_seed])
            .collect(),
    };
    let prepared = snapshot
        .prepare_with_bap(
            &query,
            &decoder(),
            &producer(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    assert_eq!(prepared.prepared.identity.ruleset, "bap-bit-provenance-v6");
    assert_eq!(
        prepared.prepared.identity.target,
        if linux {
            "x86_64-unknown-linux-gnu"
        } else {
            "x86_64-pc-windows-msvc"
        }
    );
    assert_eq!(prepared.prepared.request.locations, locations());
    assert_eq!(prepared.prepared.request.entry_points, query.entry_points);
    assert_eq!(prepared.prepared.request.slice_seeds, query.slice_seeds);
    assert_eq!(prepared.materialization.entry_points, query.entry_points);
    assert_eq!(prepared.materialization.slice_seeds, query.slice_seeds);
    assert!(!prepared.materialization.attempted.contains(&extra_seed));
    for block in &blocks {
        assert_eq!(
            prepared.materialization.attempted.contains(&block.consumer),
            !refused
        );
    }
    (prepared, blocks, extra_seed)
}

fn effects(case: &Case) -> (LocationSet, LocationSet, LocationSet) {
    let mut reads = case.address_reads.clone();
    if case.load {
        reads.insert("memory:any".into());
        (reads, [cell(case.data)].into(), [cell(case.data)].into())
    } else {
        reads.insert(cell(case.data));
        (reads, ["memory:any".into()].into(), LocationSet::new())
    }
}

#[test]
fn memory_domain_has_independent_address_and_alias_partitions() {
    let a = cases(false);
    let b = cases(true);
    assert_eq!((a.len(), b.len()), (2880, 2880));
    assert_eq!(
        a.iter().map(|c| &c.bytes).collect::<BTreeSet<_>>().len(),
        2880
    );
    assert_eq!(a.iter().filter(|c| c.load).count(), 1440);
    for (a, b) in a.iter().zip(&b) {
        assert_eq!(b.bytes[0], 0x67);
        assert_eq!(a.bytes, b.bytes[1..]);
    }
    for (encoded, data, reads) in [
        (vec![0x8a, 0x00], (0, 0), bank_cells(0)),
        (vec![0x8a, 0x20], (0, 1), bank_cells(0)),
        (vec![0x40, 0x8a, 0x20], (4, 0), bank_cells(0)),
        (vec![0x47, 0x8a, 0x24, 0x00], (12, 0), bank_cells(8)),
        (vec![0x8a, 0x05, 0, 0, 0, 0], (0, 0), LocationSet::new()),
        (
            vec![0x41, 0x8a, 0x04, 0x25, 0, 0, 0, 0],
            (0, 0),
            LocationSet::new(),
        ),
    ] {
        let case = a.iter().find(|c| c.bytes == encoded).unwrap();
        assert_eq!(case.data, data);
        assert_eq!(case.address_reads, reads);
    }
}

#[test]
#[ignore = "requires pinned BAP/LLVM and audited native core; run in release mode"]
fn native_memory_mov8_preserves_byte_and_weak_memory_origins() {
    let cases = cases(false);
    let mut seen = BTreeSet::new();
    let mut batches = 0;
    let mut loads = 0;
    let mut stores = 0;
    for linux in [false, true] {
        for batch in cases.chunks(64) {
            let (prepared, blocks, extra_seed) = prepare(batch, linux, false);
            let request = &prepared.prepared.request;
            let reference =
                CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
            let native = NativeAnalyzer::from_capture(&core(), "mov8-memory-native", &prepared)
                .unwrap()
                .complete()
                .unwrap();
            assert_eq!(native.request(), request);
            assert_eq!(native.state(), reference.state());
            assert_eq!(native.state().phase, Phase::Done);
            assert!(native.state().obligations.is_empty());
            let decoded: AddressSet = blocks
                .iter()
                .flat_map(|b| [b.entry, b.consumer, b.terminal])
                .collect();
            assert_eq!(native.state().decoded, decoded);
            assert_eq!(native.state().visited, decoded);
            let edges: BTreeSet<_> = blocks
                .iter()
                .flat_map(|b| {
                    [
                        Edge {
                            src: b.entry,
                            dst: b.consumer,
                            kind: EdgeKind::Next,
                        },
                        Edge {
                            src: b.consumer,
                            dst: b.terminal,
                            kind: EdgeKind::Next,
                        },
                    ]
                })
                .collect();
            assert_eq!(native.state().edges, edges);
            assert_eq!(
                native.state().slice,
                blocks.iter().flat_map(|b| [b.entry, b.consumer]).collect()
            );
            for (case, block) in batch.iter().zip(&blocks) {
                assert!(seen.insert((target(linux), case.bytes.clone())));
                let evidence = &prepared.prepared.instructions[&block.entry];
                assert_eq!(evidence.bytes, case.bytes);
                assert_eq!(evidence.source, ByteSource::Captured);
                assert_eq!(evidence.quality, EffectQuality::ExternalLifted);
                let semantic = evidence.semantic.as_ref().unwrap();
                assert_eq!(semantic.status, "projected");
                assert!(semantic.fallback.is_none());
                assert!(semantic.gaps.is_empty());
                let instruction = &request.instructions[&block.entry];
                let (reads, may, must) = effects(case);
                assert_eq!(
                    (
                        &instruction.uses,
                        &instruction.may_defs,
                        &instruction.must_defs
                    ),
                    (&reads, &may, &must)
                );
                assert_eq!(instruction.kind, InstructionKind::Ordinary);
                assert!(instruction.complete);
                assert_eq!(instruction.fall, [block.consumer].into());
                assert!(instruction.targets.is_empty());
                assert_eq!(
                    native.state().reaching[&block.entry]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    entry_origins(block.entry)
                );
                let mut expected = entry_origins(block.entry);
                expected.retain(|d| !must.contains(&d.loc));
                expected.extend(may.into_iter().map(|loc| Definition {
                    loc,
                    site: block.entry,
                    origin: DefinitionOrigin::Instruction,
                }));
                assert_eq!(
                    native.state().reaching[&block.consumer]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    expected,
                    "{:02x?}",
                    case.bytes
                );
                let consumer = &request.instructions[&block.consumer];
                let uses = if case.load {
                    bank_cells(case.data.0)
                } else {
                    let mut uses = bank_cells(14);
                    uses.insert("memory:any".into());
                    uses
                };
                assert_eq!(consumer.uses, uses);
                assert_eq!(consumer.must_defs, bank_cells(15));
                assert_eq!(consumer.may_defs, bank_cells(15));
                let sink = bank_cells(15);
                expected.retain(|d| !sink.contains(&d.loc));
                expected.extend(sink.into_iter().map(|loc| Definition {
                    loc,
                    site: block.consumer,
                    origin: DefinitionOrigin::Instruction,
                }));
                assert_eq!(
                    native.state().reaching[&block.terminal]
                        .iter()
                        .cloned()
                        .collect::<BTreeSet<_>>(),
                    expected
                );
                for source in prepared.reads[&block.entry]
                    .spans
                    .iter()
                    .flat_map(|s| &s.contributors)
                {
                    assert!(source.file_offset < prepared.snapshot.artifact_bytes as u64);
                    assert_ne!(source.file_offset, block.entry);
                }
                loads += usize::from(case.load);
                stores += usize::from(!case.load);
            }
            crate::input::investigation::bind_investigation(&prepared, &native).unwrap();
            let result = native.into_result();
            assert_eq!(result.missing_slice_seeds, [extra_seed].into());
            assert!(result.scope_closed());
            batches += 1;
        }
    }
    assert_eq!((seen.len(), batches, loads, stores), (5760, 90, 2880, 2880));
    eprintln!(
        "MOV8_MEMORY_NATIVE points=2880 targets=2 instances=5760 batches=90 loads=2880 stores=2880 weak_memory_updates=2880"
    );
}

#[test]
#[ignore = "requires pinned BAP/LLVM and audited native core; address32 stays refused"]
fn native_memory_mov8_address32_stops_before_consumers() {
    let cases = cases(true);
    let mut seen = BTreeSet::new();
    let mut batches = 0;
    for linux in [false, true] {
        for batch in cases.chunks(64) {
            let (prepared, blocks, _) = prepare(batch, linux, true);
            let request = &prepared.prepared.request;
            assert!(prepared.refinement.is_empty());
            assert!(request.decodable.is_empty());
            for (case, block) in batch.iter().zip(&blocks) {
                assert!(seen.insert((target(linux), case.bytes.clone())));
                let evidence = &prepared.prepared.instructions[&block.entry];
                assert_eq!(evidence.bytes, case.bytes);
                assert_eq!(evidence.quality, EffectQuality::Opaque);
                assert_eq!(evidence.decoder_control, Some(InstructionKind::Ordinary));
                assert_eq!(evidence.control, Some(InstructionKind::Stop));
                let semantic = evidence.semantic.as_ref().unwrap();
                assert_eq!(semantic.status, "opaque-unsupported");
                assert!(semantic.fallback.is_none());
                assert!(semantic.memory_accesses.is_empty());
                assert!(
                    semantic
                        .gaps
                        .iter()
                        .any(|g| g.contains("unmodeled instruction prefix"))
                );
                let instruction = &request.instructions[&block.entry];
                assert_eq!(instruction.kind, InstructionKind::Stop);
                assert!(instruction.fall.is_empty());
                assert!(instruction.targets.is_empty());
                assert!(instruction.must_defs.is_empty());
                assert_eq!(instruction.uses, locations());
                assert_eq!(instruction.may_defs, locations());
            }
            let reference =
                CompletedAnalysis::from_analyzer(Analyzer::new(request.clone()).unwrap());
            let native = NativeAnalyzer::from_capture(&core(), "mov8-memory-address32", &prepared)
                .unwrap()
                .complete()
                .unwrap();
            assert_eq!(native.state(), reference.state());
            assert_eq!(native.state().phase, Phase::Done);
            assert_eq!(native.state().visited, request.entry_points);
            assert!(native.state().decoded.is_empty());
            assert!(native.state().edges.is_empty());
            assert!(native.state().slice.is_empty());
            let obligations = request
                .entry_points
                .iter()
                .map(|site| Obligation {
                    site: *site,
                    reason: ObligationReason::DecodeFailed,
                })
                .collect();
            assert_eq!(native.state().obligations, obligations);
            let result = native.into_result();
            assert_eq!(result.missing_slice_seeds, request.slice_seeds);
            assert!(!result.scope_closed());
            batches += 1;
        }
    }
    assert_eq!((seen.len(), batches), (5760, 90));
    eprintln!(
        "MOV8_MEMORY_ADDRESS32 points=2880 targets=2 refused_instances=5760 batches=90 decoded=0 consumer_starts=0 known_addresses=0 definite_writes=0"
    );
}
