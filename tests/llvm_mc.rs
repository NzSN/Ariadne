use ariadne::llvm_mc::ByteSnapshot;
use ariadne::{Edge, EdgeKind, InputKind, Obligation, ObligationReason, analyze};
use std::path::Path;

fn decoder() -> String {
    std::env::var("ARIADNE_LLVM_MC").expect("set ARIADNE_LLVM_MC to the pinned decoder path")
}

#[test]
#[ignore = "requires the pinned LLVM MC decoder; run native/llvm_mc/check.sh"]
fn binary_control_flow_and_unknown_effects() {
    let snapshot = ByteSnapshot {
        snapshot_id: "binary-fixture".into(),
        input_kind: InputKind::Binary,
        file_backed: [
            (0x1000, vec![0xb0, 0x01]),       // mov al, 1
            (0x1002, vec![0x75, 0x02]),       // jne 0x1006
            (0x1004, vec![0xc3]),             // ret
            (0x1006, vec![0xe8, 0, 0, 0, 0]), // call 0x100b
            (0x100b, vec![0xff, 0xe0]),       // jmp rax
        ]
        .into(),
        entry_points: [0x1000].into(),
        slice_seeds: [0x100b].into(),
        locations: ["rax".into(), "zf".into()].into(),
        ..ByteSnapshot::default()
    };
    let request = snapshot.to_request(Path::new(&decoder())).unwrap();
    assert_eq!(request.decodable.len(), 5);
    assert_eq!(request.instructions[&0x1000].may_defs, snapshot.locations);
    assert!(request.instructions[&0x1000].must_defs.is_empty());
    let result = analyze(request).unwrap();
    let edge = |src, dst, kind| Edge { src, dst, kind };
    assert!(
        result
            .state
            .edges
            .contains(&edge(0x1000, 0x1002, EdgeKind::Next))
    );
    assert!(
        result
            .state
            .edges
            .contains(&edge(0x1002, 0x1006, EdgeKind::Taken))
    );
    assert!(
        result
            .state
            .edges
            .contains(&edge(0x1002, 0x1004, EdgeKind::Fallthrough))
    );
    assert!(
        result
            .state
            .edges
            .contains(&edge(0x1006, 0x100b, EdgeKind::Call))
    );
    assert!(
        result
            .state
            .edges
            .contains(&edge(0x1006, 0x100b, EdgeKind::Summary))
    );
    assert!(result.state.obligations.contains(&Obligation {
        site: 0x100b,
        reason: ObligationReason::IndirectTargets,
    }));
    assert!(!result.scope_closed());
}

#[test]
#[ignore = "requires the pinned LLVM MC decoder; run native/llvm_mc/check.sh"]
fn dump_capture_wins_and_failed_capture_does_not_fall_back() {
    let snapshot = ByteSnapshot {
        snapshot_id: "dump-fixture".into(),
        input_kind: InputKind::Dump,
        captured: [
            (0x2000, vec![0xeb, 0x02]),
            (0x2004, vec![0x0f; 15]),
            (0x2008, vec![0x0f]),
        ]
        .into(),
        file_backed: [
            (0x2000, vec![0xc3]),
            (0x2004, vec![0xc3]),
            (0x2007, vec![0xc3]),
            (0x2008, vec![0xc3]),
        ]
        .into(),
        trusted_fallback: [0x2000, 0x2004, 0x2008].into(),
        entry_points: [0x2000, 0x2007, 0x2008].into(),
        ..ByteSnapshot::default()
    };
    let request = snapshot.to_request(Path::new(&decoder())).unwrap();
    assert!(request.decodable.contains(&0x2000));
    assert!(!request.decodable.contains(&0x2004));
    assert!(!request.decodable.contains(&0x2007));
    assert!(!request.captured.contains(&0x2008));
    assert!(!request.trusted_fallback.contains(&0x2008));
    let result = analyze(request).unwrap();
    assert!(result.state.edges.contains(&Edge {
        src: 0x2000,
        dst: 0x2004,
        kind: EdgeKind::Jump,
    }));
    assert!(result.state.obligations.contains(&Obligation {
        site: 0x2004,
        reason: ObligationReason::DecodeFailed,
    }));
    assert!(result.state.obligations.contains(&Obligation {
        site: 0x2007,
        reason: ObligationReason::Unavailable,
    }));
    assert!(result.state.obligations.contains(&Obligation {
        site: 0x2008,
        reason: ObligationReason::Unavailable,
    }));
}

#[test]
#[ignore = "requires the pinned LLVM MC decoder; run native/llvm_mc/check.sh"]
fn indirect_call_retains_summary_and_unknown_target() {
    let snapshot = ByteSnapshot {
        snapshot_id: "indirect-call".into(),
        file_backed: [(0x3000, vec![0xff, 0xd0]), (0x3002, vec![0xc3])].into(),
        entry_points: [0x3000].into(),
        ..ByteSnapshot::default()
    };
    let result = analyze(snapshot.to_request(Path::new(&decoder())).unwrap()).unwrap();
    assert!(result.state.edges.contains(&Edge {
        src: 0x3000,
        dst: 0x3002,
        kind: EdgeKind::Summary,
    }));
    assert!(result.state.obligations.contains(&Obligation {
        site: 0x3000,
        reason: ObligationReason::CallTargets,
    }));
}

#[test]
#[ignore = "requires the pinned LLVM MC decoder; run native/llvm_mc/check.sh"]
fn system_and_transactional_transfers_do_not_invent_fallthrough() {
    let snapshot = ByteSnapshot {
        snapshot_id: "opaque-control".into(),
        file_backed: [
            (0x4000, vec![0x0f, 0x05]),       // syscall
            (0x4002, vec![0xcd, 0x80]),       // int 0x80
            (0x4004, vec![0xc6, 0xf8, 0x00]), // xabort 0
            (0x4007, vec![0x0f, 0x0b]),       // ud2
        ]
        .into(),
        entry_points: [0x4000, 0x4002, 0x4004, 0x4007].into(),
        ..ByteSnapshot::default()
    };
    let request = snapshot.to_request(Path::new(&decoder())).unwrap();
    assert_eq!(request.decodable, [0x4007].into());
    let result = analyze(request).unwrap();
    assert!(result.state.edges.is_empty());
    for site in [0x4000, 0x4002, 0x4004] {
        assert!(result.state.obligations.contains(&Obligation {
            site,
            reason: ObligationReason::DecodeFailed,
        }));
    }
}

#[test]
#[ignore = "requires the pinned LLVM MC decoder; run native/llvm_mc/check.sh"]
fn identical_bytes_from_binary_and_trusted_dump_have_identical_summaries() {
    let bytes = [
        (0x5000, vec![0x75, 0x02]),
        (0x5002, vec![0xc3]),
        (0x5004, vec![0xc3]),
    ];
    let binary = ByteSnapshot {
        snapshot_id: "same-image".into(),
        file_backed: bytes.clone().into(),
        entry_points: [0x5000].into(),
        ..ByteSnapshot::default()
    };
    let dump = ByteSnapshot {
        input_kind: InputKind::Dump,
        file_backed: bytes.into(),
        trusted_fallback: [0x5000, 0x5002, 0x5004].into(),
        ..binary.clone()
    };
    let decoder = decoder();
    let binary_request = binary.to_request(Path::new(&decoder)).unwrap();
    let dump_request = dump.to_request(Path::new(&decoder)).unwrap();
    assert_eq!(binary_request.instructions, dump_request.instructions);
    assert_eq!(
        analyze(binary_request).unwrap().state.edges,
        analyze(dump_request).unwrap().state.edges
    );
}
