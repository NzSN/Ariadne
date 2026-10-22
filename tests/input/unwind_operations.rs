//! Independent synthetic Windows metadata/stack encodings, not hardware captures.
use ariadne::input::{FileSnapshot, OpenLimits};
use ariadne::investigation::{CapturedFrameChain, FrameRecoveryLimits};
use sha2::{Digest, Sha256};

#[path = "unwind_v2.rs"]
mod metadata_v2;

const IMAGE: u64 = 0x400000;
const STACK: u64 = 0x1000;
const SAVED: u64 = 0x1234_5678_9abc_def0;

fn u32_at(bytes: &[u8], at: usize) -> usize {
    u32::from_le_bytes(bytes[at..at + 4].try_into().unwrap()) as usize
}

/// Parse only the documented minidump directory, independently of FileSnapshot.
fn stream(bytes: &[u8], kind: usize) -> usize {
    let count = u32_at(bytes, 8);
    let directory = u32_at(bytes, 12);
    (0..count)
        .map(|index| directory + index * 12)
        .find(|at| u32_at(bytes, *at) == kind)
        .map(|at| u32_at(bytes, at + 8))
        .unwrap()
}

struct Capture {
    bytes: Vec<u8>,
    image: usize,
    stack: usize,
    context: usize,
    exception: usize,
}

impl Capture {
    fn new() -> Self {
        let bytes = include_bytes!("fixtures/frame_paths/diamond.dmp").to_vec();
        let memory = stream(&bytes, 5);
        let image = u32_at(&bytes, memory + 16);
        let stack = u32_at(&bytes, memory + 32);
        let exception = stream(&bytes, 6);
        let context = u32_at(&bytes, exception + 164);
        let mut value = Self {
            bytes,
            image,
            stack,
            context,
            exception,
        };
        value.image_bytes(0x200, &[0x90; 64]);
        value.image_bytes(0x230, &[0x48, 0x8b, 0x00]);
        // Keep this record independent of the two caller unwind records.
        value.image_bytes(0x808, &0xa00u32.to_le_bytes());
        value.pc(IMAGE + 0x230);
        value.bytes[stack..stack + 256].fill(0);
        value.returns(0x20);
        value
    }

    fn image_bytes(&mut self, rva: usize, bytes: &[u8]) {
        self.bytes[self.image + rva..self.image + rva + bytes.len()].copy_from_slice(bytes);
    }

    fn register(&mut self, bank: usize, value: u64) {
        let at = self.context + 120 + bank * 8;
        self.bytes[at..at + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn pc(&mut self, pc: u64) {
        self.bytes[self.context + 248..self.context + 256].copy_from_slice(&pc.to_le_bytes());
        self.bytes[self.exception + 24..self.exception + 32].copy_from_slice(&pc.to_le_bytes());
    }

    fn stack_word(&mut self, offset: usize, value: u64) {
        self.bytes[self.stack + offset..self.stack + offset + 8]
            .copy_from_slice(&value.to_le_bytes());
    }

    fn returns(&mut self, first: usize) {
        // Caller frame layouts each allocate 32 bytes and pop an eight-byte PC.
        self.stack_word(first, IMAGE + 0x315);
        self.stack_word(first + 40, IMAGE + 0x415);
        self.stack_word(first + 80, 0);
    }

    fn unwind(&mut self, prologue: u8, frame: u8, codes: &[u8]) {
        assert_eq!(codes.len() % 2, 0);
        self.image_bytes(0xa00, &[0; 128]);
        self.image_bytes(0xa00, &[1, prologue, (codes.len() / 2) as u8, frame]);
        self.image_bytes(0xa04, codes);
    }

    fn xmm(&mut self, offset: usize) -> Vec<u8> {
        let value: Vec<_> = (0..16).map(|i| 0x91 + i).collect();
        self.bytes[self.stack + offset..self.stack + offset + 16].copy_from_slice(&value);
        value
    }

    fn snapshot(&self) -> FileSnapshot {
        FileSnapshot::from_minidump_bytes(self.bytes.clone(), OpenLimits::default()).unwrap()
    }

    fn recover(&self) -> CapturedFrameChain {
        self.snapshot()
            .recover_thread_frames(17, FrameRecoveryLimits::default())
            .unwrap()
    }
}

fn assert_return(capture: &Capture, chain: &CapturedFrameChain, slot: u64, sp: u64) {
    assert_eq!(chain.frames.len(), 3, "{}", chain.stop_reason);
    assert_eq!(chain.stop_reason, "zero-return-boundary");
    assert_eq!(chain.frames[0].return_slot, Some(slot));
    assert_eq!(chain.frames[0].return_pc, Some(IMAGE + 0x315));
    assert_eq!(chain.frames[1].pc, IMAGE + 0x315);
    assert_eq!(chain.frames[1].sp, sp);
    assert!(!chain.frames[1].registers.contains_key("rax"));
    chain.validate().unwrap();
    capture.snapshot().validate_thread_frames(chain).unwrap();
}

fn assert_stop(capture: &Capture, reason: &str) {
    let chain = capture.recover();
    assert_eq!(chain.frames.len(), 1, "{}", chain.stop_reason);
    assert!(chain.stop_reason.contains(reason), "{}", chain.stop_reason);
    assert_eq!(chain.frames[0].return_pc, None);
    chain.validate().unwrap();
    capture.snapshot().validate_thread_frames(&chain).unwrap();
}

#[test]
fn saved_xmm_near_slots_preserve_all_bytes_without_inventing_vector_context() {
    for bank in 6..=15 {
        let mut capture = Capture::new();
        capture.unwind(8, 0, &[8, bank << 4 | 8, 1, 0, 4, 0x32]);
        let expected = capture.xmm(0x10);
        let chain = capture.recover();
        assert_return(&capture, &chain, STACK + 0x20, STACK + 0x28);
        let reads: Vec<_> = chain
            .reads
            .iter()
            .filter(|read| read.address == STACK + 0x10 && read.requested == 16)
            .collect();
        assert_eq!(reads.len(), 1);
        let expected_hex: String = expected.iter().map(|byte| format!("{byte:02x}")).collect();
        assert_eq!(reads[0].bytes_hex, expected_hex);
        assert!(
            chain.frames[1]
                .registers
                .keys()
                .all(|name| !name.starts_with("xmm"))
        );
        assert_eq!(
            reads[0].spans.iter().map(|span| span.length).sum::<usize>(),
            16
        );
    }
}

#[test]
fn saved_xmm_uses_fixed_frame_base_when_rsp_has_dynamic_allocation() {
    let mut capture = Capture::new();
    // RBP=0x1030 and the encoded 16-byte bias establish base 0x1020,
    // independently of the lower captured RSP=0x1000.
    capture.register(5, 0x1030);
    capture.unwind(12, 0x15, &[12, 0x68, 1, 0, 10, 3, 4, 0x32]);
    capture.xmm(0x30);
    capture.returns(0x40);
    let chain = capture.recover();
    assert_return(&capture, &chain, 0x1040, 0x1048);
    assert!(
        chain
            .reads
            .iter()
            .any(|read| read.address == 0x1030 && read.requested == 16)
    );
    assert!(
        !chain
            .reads
            .iter()
            .any(|read| read.address == 0x1010 && read.requested == 16)
    );
}

#[test]
fn saved_xmm_rejects_volatile_registers_incomplete_slots_and_bad_frame_order() {
    for bank in 0..6 {
        let mut capture = Capture::new();
        capture.unwind(8, 0, &[8, bank << 4 | 8, 1, 0, 4, 0x32]);
        assert_stop(&capture, "invalid-saved-xmm-register");
    }
    let mut truncated = Capture::new();
    truncated.unwind(8, 0, &[8, 0x68]);
    assert_stop(&truncated, "truncated-unwind-operation");

    let mut order = Capture::new();
    order.register(5, 0x1010);
    order.unwind(12, 0x15, &[12, 3, 10, 0x68, 1, 0, 4, 0x32]);
    assert_stop(&order, "save-before-frame-establishment");
}

#[test]
fn saved_xmm_rejects_unaligned_or_outside_stack_slots() {
    let mut unaligned = Capture::new();
    unaligned.register(4, 0x1008);
    unaligned.unwind(8, 0, &[8, 0x68, 1, 0, 4, 0x32]);
    assert_stop(&unaligned, "unaligned-saved-xmm-slot");

    let mut outside = Capture::new();
    outside.unwind(8, 0, &[8, 0x68, 16, 0, 4, 0x32]);
    assert_stop(&outside, "return-or-save-outside-thread-stack");
}

#[test]
fn saved_xmm_read_budget_stops_before_a_partial_saved_register_receipt() {
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x68, 1, 0, 4, 0x32]);
    capture.xmm(0x10);
    let complete = capture.recover();
    let before_xmm: usize = complete
        .reads
        .iter()
        .take_while(|read| !(read.address == 0x1010 && read.requested == 16))
        .map(|read| read.requested)
        .sum();
    let snapshot = capture.snapshot();
    let limited = snapshot
        .recover_thread_frames(
            17,
            FrameRecoveryLimits {
                max_read_bytes: before_xmm + 15,
                ..FrameRecoveryLimits::default()
            },
        )
        .unwrap();
    assert_eq!(limited.frames.len(), 1);
    assert!(limited.truncated);
    assert!(limited.stop_reason.contains("unwind-read-budget"));
    assert!(!limited.reads.iter().any(|read| read.address == 0x1010));
    limited.validate().unwrap();
    snapshot.validate_thread_frames(&limited).unwrap();
}

#[test]
fn all_gpr_save_encodings_restore_the_independent_stack_value() {
    for bank in [3u8, 5, 6, 7, 12, 13, 14, 15] {
        for far in [false, true] {
            let mut capture = Capture::new();
            let mut codes = vec![8, bank << 4 | if far { 5 } else { 4 }];
            if far {
                codes.extend(16u32.to_le_bytes());
            } else {
                codes.extend(2u16.to_le_bytes());
            }
            codes.extend([4, 0x32]);
            capture.unwind(8, 0, &codes);
            capture.stack_word(0x10, SAVED);
            let chain = capture.recover();
            assert_return(&capture, &chain, 0x1020, 0x1028);
            let name = [
                "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11",
                "r12", "r13", "r14", "r15",
            ][usize::from(bank)];
            assert_eq!(chain.frames[1].registers[name], SAVED);
            assert_eq!(
                chain.frames[1].register_evidence[name].stack_slot,
                Some(0x1010)
            );
        }
    }
}

fn rehash(chain: &mut CapturedFrameChain) {
    chain.chain_id.clear();
    chain.chain_id = format!("{:x}", Sha256::digest(serde_json::to_vec(&chain).unwrap()));
}

/// Reconstruct the older profiles' declared top-PC read before their metadata
/// read. V4 can classify metadata v2 without fetching unrelated body bytes.
fn legacy_prefix_order(capture: &Capture, chain: &mut CapturedFrameChain) {
    let pc = chain.frames[0].pc;
    let prefix = if let Some(index) = chain
        .reads
        .iter()
        .position(|read| read.address == pc && read.requested == 15)
    {
        chain.reads.remove(index)
    } else {
        let read = capture.snapshot().read_prefix(pc, 15).unwrap();
        ariadne::investigation::FrameMemoryEvidence {
            address: pc,
            requested: 15,
            bytes_hex: read
                .bytes
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect(),
            spans: read
                .spans
                .iter()
                .map(|span| ariadne::investigation::Span {
                    va: span.address,
                    length: span.length,
                    contributors: span
                        .contributors
                        .iter()
                        .map(|contributor| ariadne::investigation::Contributor {
                            stream: contributor.stream,
                            entry: contributor.entry,
                            file_offset: contributor.file_offset,
                        })
                        .collect(),
                })
                .collect(),
        }
    };
    let header = chain
        .reads
        .iter()
        .position(|read| read.address == IMAGE + 0xa00 && read.requested == 4)
        .unwrap();
    chain.reads.insert(header, prefix);
    chain.read_bytes = chain.reads.iter().map(|read| read.requested).sum();
}

#[test]
fn saved_v1_xmm_stop_replays_without_consuming_newly_supported_stack_bytes() {
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x68, 1, 0, 4, 0x32]);
    capture.xmm(0x10);
    let fresh = capture.recover();
    let mut legacy_json = serde_json::to_value(&fresh).unwrap();
    for frame in legacy_json["frames"].as_array_mut().unwrap() {
        frame.as_object_mut().unwrap().remove("transition");
    }
    let mut legacy: CapturedFrameChain = serde_json::from_value(legacy_json).unwrap();
    legacy_prefix_order(&capture, &mut legacy);
    legacy.profile = "captured-windows-amd64-unwind-v1".into();
    legacy.frames.truncate(1);
    legacy.frames[0].return_pc = None;
    legacy.frames[0].return_slot = None;
    let stop = legacy
        .reads
        .iter()
        .position(|read| read.address == 0x1010 && read.requested == 16)
        .unwrap();
    legacy.reads.truncate(stop);
    legacy.read_bytes = legacy.reads.iter().map(|read| read.requested).sum();
    legacy.stop_reason = "unsupported-unwind-operation".into();
    rehash(&mut legacy);
    legacy.validate().unwrap();
    capture.snapshot().validate_thread_frames(&legacy).unwrap();
    assert_ne!(legacy.chain_id, fresh.chain_id);
    let mut forged = legacy;
    forged.profile = "captured-windows-amd64-unwind-v999".into();
    rehash(&mut forged);
    assert!(forged.validate().is_err());
}

#[test]
fn all_stack_allocation_encodings_follow_independent_return_slot_arithmetic() {
    for size in [8u32, 16, 32, 64, 128] {
        for encoding in 0..3 {
            let codes = match encoding {
                0 => vec![4, (((size / 8 - 1) as u8) << 4) | 2],
                1 => {
                    let mut codes = vec![4, 1];
                    codes.extend(((size / 8) as u16).to_le_bytes());
                    codes
                }
                _ => {
                    let mut codes = vec![4, 0x11];
                    codes.extend(size.to_le_bytes());
                    codes
                }
            };
            let mut capture = Capture::new();
            capture.unwind(4, 0, &codes);
            capture.returns(size as usize);
            let chain = capture.recover();
            assert_return(
                &capture,
                &chain,
                STACK + u64::from(size),
                STACK + u64::from(size) + 8,
            );
        }
    }
}

#[test]
fn push_nonvolatile_restores_each_bank_and_pops_exactly_one_slot() {
    let names = [
        (3u8, "rbx"),
        (5, "rbp"),
        (6, "rsi"),
        (7, "rdi"),
        (12, "r12"),
        (13, "r13"),
        (14, "r14"),
        (15, "r15"),
    ];
    for (bank, name) in names {
        let mut capture = Capture::new();
        capture.unwind(5, 0, &[5, 0x32, 1, bank << 4]);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1028, 0x1030);
        assert_eq!(chain.frames[1].registers[name], SAVED);
        assert_eq!(
            chain.frames[1].register_evidence[name].stack_slot,
            Some(0x1020)
        );
    }
}

#[test]
fn frame_register_bias_restores_rsp_for_each_nonvolatile_frame_register() {
    for bank in [3u8, 5, 6, 7, 12, 13, 14, 15] {
        let mut capture = Capture::new();
        capture.register(usize::from(bank), 0x1030);
        capture.unwind(10, 0x10 | bank, &[10, 3, 4, 0x32]);
        capture.returns(0x40);
        assert_return(&capture, &capture.recover(), 0x1040, 0x1048);
    }
    for (frame, codes) in [
        (0u8, vec![4, 3]),
        (0x14, vec![4, 3]),
        (0x15, vec![4, 0x13]),
        (0x15, vec![4, 3, 3, 3]),
        (0x15, vec![4, 0x32]),
    ] {
        let mut capture = Capture::new();
        capture.register(5, 0x1010);
        capture.unwind(4, frame, &codes);
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 1);
        assert_eq!(chain.frames[0].return_slot, None);
        assert!(chain.stop_reason.contains("frame"), "{}", chain.stop_reason);
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

#[test]
fn cumulative_stack_adjustment_includes_the_return_pop() {
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x12, 4, 0x12]);
    let snapshot = capture.snapshot();
    for budget in [16, 32, 39] {
        let chain = snapshot
            .recover_thread_frames(
                17,
                FrameRecoveryLimits {
                    max_stack_adjustment: budget,
                    ..FrameRecoveryLimits::default()
                },
            )
            .unwrap();
        assert_eq!(chain.frames.len(), 1);
        assert!(chain.truncated);
        assert!(chain.stop_reason.contains("unwind-stack-adjustment-budget"));
        assert_eq!(chain.frames[0].return_pc, None);
        chain.validate().unwrap();
        snapshot.validate_thread_frames(&chain).unwrap();
    }
}

#[test]
fn saved_xmm_far_uses_unscaled_u32_offset_and_all_nonvolatile_banks() {
    for bank in 6..=15 {
        let mut capture = Capture::new();
        capture.unwind(8, 0, &[8, bank << 4 | 9, 16, 0, 0, 0, 4, 0x32]);
        capture.xmm(0x10);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1020, 0x1028);
        assert!(
            chain
                .reads
                .iter()
                .any(|read| read.address == 0x1010 && read.requested == 16)
        );
        assert!(!chain.reads.iter().any(|read| read.address == 0x1100));
    }
}

#[test]
fn saved_xmm_far_rejects_truncation_unaligned_offsets_and_outside_stack() {
    for codes in [&[8, 0x69][..], &[8, 0x69, 16, 0][..]] {
        let mut capture = Capture::new();
        capture.unwind(8, 0, codes);
        assert_stop(&capture, "truncated-unwind-operation");
    }
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x69, 8, 0, 0, 0, 4, 0x32]);
    assert_stop(&capture, "unaligned-saved-xmm-slot");
    capture.unwind(8, 0, &[8, 0x69, 0, 1, 0, 0, 4, 0x32]);
    assert_stop(&capture, "return-or-save-outside-thread-stack");
}

#[test]
fn saved_v2_xmm_reads_replay_and_v1_v2_far_saves_still_stop() {
    for operation in [8u8, 9] {
        let mut capture = Capture::new();
        let codes = if operation == 8 {
            vec![8, 0x68, 1, 0, 4, 0x32]
        } else {
            vec![8, 0x69, 16, 0, 0, 0, 4, 0x32]
        };
        capture.unwind(8, 0, &codes);
        capture.xmm(0x10);
        let fresh = capture.recover();
        for version in [1, 2] {
            if version == 1 && operation == 8 {
                continue; // The dedicated v1 early-stop control above covers it.
            }
            let mut value = serde_json::to_value(&fresh).unwrap();
            for frame in value["frames"].as_array_mut().unwrap() {
                frame.as_object_mut().unwrap().remove("transition");
            }
            let mut old: CapturedFrameChain = serde_json::from_value(value).unwrap();
            legacy_prefix_order(&capture, &mut old);
            old.profile = format!("captured-windows-amd64-unwind-v{version}");
            if operation == 9 {
                old.frames.truncate(1);
                old.frames[0].return_slot = None;
                old.frames[0].return_pc = None;
                let count = old
                    .reads
                    .iter()
                    .position(|read| read.address == 0x1010 && read.requested == 16)
                    .unwrap();
                old.reads.truncate(count);
                old.read_bytes = old.reads.iter().map(|read| read.requested).sum();
                old.stop_reason = "unsupported-unwind-operation".into();
            }
            rehash(&mut old);
            old.validate().unwrap();
            capture.snapshot().validate_thread_frames(&old).unwrap();
        }
    }
}

#[test]
fn machine_frames_restore_saved_rsp_and_exact_rip_without_an_extra_return_pop() {
    for error_code in [false, true] {
        let mut capture = Capture::new();
        capture.unwind(1, 0, &[1, if error_code { 0x1a } else { 0x0a }]);
        let offset = if error_code { 8 } else { 0 };
        // This RIP is immediately outside the second RUNTIME_FUNCTION.
        // Treating it as a CALL return address (RIP-1) would choose that function.
        capture.stack_word(offset, IMAGE + 0x340);
        capture.stack_word(offset + 8, 0x33); // CS
        capture.stack_word(offset + 16, 0x202); // EFLAGS
        capture.stack_word(offset + 24, 0x1040); // interrupted RSP
        capture.stack_word(offset + 32, 0x2b); // SS
        if error_code {
            capture.stack_word(0, 0xbad);
        }
        capture.stack_word(0x40, 0); // interrupted leaf's return boundary
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 2, "{}", chain.stop_reason);
        assert_eq!(chain.stop_reason, "zero-return-boundary");
        assert_eq!(chain.frames[0].return_slot, Some(STACK + offset as u64));
        assert_eq!(chain.frames[0].return_pc, Some(IMAGE + 0x340));
        assert_eq!(chain.frames[1].pc, IMAGE + 0x340);
        assert_eq!(chain.frames[1].sp, 0x1040);
        assert_eq!(chain.frames[1].function_begin, None);
        assert_eq!(chain.frames[1].return_slot, Some(0x1040));
        assert_eq!(
            chain.frames[1].register_evidence["rip"].source,
            "machine-frame-rip"
        );
        assert_eq!(
            chain.frames[1].register_evidence["rsp"].source,
            "machine-frame-rsp"
        );
        assert_eq!(
            chain.frames[1].register_evidence["rsp"].stack_slot,
            Some(STACK + offset as u64 + 24)
        );
        assert_eq!(
            serde_json::to_value(&chain.frames[0]).unwrap()["transition"],
            "machine_frame"
        );
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

#[test]
fn machine_frames_require_complete_stack_layout_and_supported_saved_rsp() {
    for error_code in [false, true] {
        let mut capture = Capture::new();
        capture.unwind(1, 0, &[1, if error_code { 0x1a } else { 0x0a }]);
        capture.register(4, 0x10e0);
        assert_stop(&capture, "return-or-save-outside-thread-stack");
    }
    for saved_sp in [0x0ff8u64, 0x1000, 0x1110] {
        let mut capture = Capture::new();
        capture.unwind(1, 0, &[1, 0x0a]);
        capture.stack_word(0, IMAGE + 0x340);
        capture.stack_word(8, 0x33);
        capture.stack_word(16, 0x202);
        capture.stack_word(24, saved_sp);
        capture.stack_word(32, 0x2b);
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 1, "{saved_sp:x}: {}", chain.stop_reason);
        assert_eq!(chain.frames[0].return_pc, None);
        assert!(!chain.truncated);
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

#[test]
fn interrupted_machine_frame_rip_zero_is_not_a_normal_return_boundary() {
    let mut capture = Capture::new();
    capture.unwind(1, 0, &[1, 0x0a]);
    capture.stack_word(0, 0);
    capture.stack_word(8, 0x33);
    capture.stack_word(16, 0x202);
    capture.stack_word(24, 0x1040);
    capture.stack_word(32, 0x2b);
    let chain = capture.recover();
    assert_eq!(chain.frames.len(), 2, "{}", chain.stop_reason);
    assert_eq!(chain.frames[1].pc, 0);
    assert_eq!(chain.frames[1].sp, 0x1040);
    assert_eq!(chain.stop_reason, "missing-or-ambiguous-frame-module");
    assert_eq!(chain.frames[1].method, "unresolved-frame");
    assert_eq!(
        serde_json::to_value(&chain.frames[0]).unwrap()["transition"],
        "machine_frame"
    );
    chain.validate().unwrap();
    capture.snapshot().validate_thread_frames(&chain).unwrap();
}

#[test]
fn partial_prologue_undoes_only_completed_operations_at_each_boundary() {
    // Prologue: PUSH RBX finishes at +1, SUB RSP,32 finishes at +5.
    // Each capture supplies its actual intermediate RSP and observed stack.
    for (offset, sp, saved_slot, return_slot) in [
        (0u64, 0x1028, None, 0x1028),
        (1, 0x1020, Some(0x1020), 0x1028),
        (4, 0x1020, Some(0x1020), 0x1028),
        (5, 0x1000, Some(0x1020), 0x1028),
    ] {
        let mut capture = Capture::new();
        capture.image_bytes(0x200, &[0x53, 0x48, 0x83, 0xec, 0x20]);
        capture.unwind(5, 0, &[5, 0x32, 1, 0x30]);
        capture.register(4, sp);
        capture.register(3, 0x5555);
        capture.pc(IMAGE + 0x200 + offset);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        let chain = capture.recover();
        assert_return(&capture, &chain, return_slot, 0x1030);
        assert_eq!(
            chain.frames[1].registers["rbx"],
            if saved_slot.is_some() { SAVED } else { 0x5555 }
        );
        assert_eq!(
            chain.frames[1].register_evidence["rbx"].stack_slot,
            saved_slot
        );
    }
}

#[test]
fn ordinary_handler_metadata_preserves_return_arithmetic_without_running_handlers() {
    for flags in [1u8, 2] {
        let mut capture = Capture::new();
        capture.unwind(4, 0, &[4, 0x32]);
        capture.image_bytes(0xa00, &[1 | flags << 3]);
        // CountOfCodes=1 is rounded to an even slot count before the handler RVA.
        capture.image_bytes(0xa08, &0x500u32.to_le_bytes());
        capture.image_bytes(0x500, &[0xcc]);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1020, 0x1028);
        assert!(
            chain
                .reads
                .iter()
                .any(|read| read.address == IMAGE + 0xa08 && read.requested == 4)
        );
        assert!(!chain.reads.iter().any(|read| read.address == IMAGE + 0x500));
    }
}

#[test]
fn chained_unwind_applies_secondary_then_primary_codes_and_rejects_cycles() {
    let mut capture = Capture::new();
    // Shrink-wrapped secondary saves RBX in the primary's 32-byte frame.
    // Secondary records cannot introduce an additional fixed allocation.
    capture.unwind(8, 0, &[8, 0x34, 2, 0]);
    capture.image_bytes(0xa00, &[0x21]);
    let mut chained = Vec::new();
    for word in [0x200u32, 0x240, 0xb00] {
        chained.extend(word.to_le_bytes());
    }
    capture.image_bytes(0xa08, &chained);
    capture.image_bytes(0xb00, &[1, 4, 1, 0, 4, 0x32]);
    capture.stack_word(0x10, SAVED);
    let chain = capture.recover();
    assert_return(&capture, &chain, 0x1020, 0x1028);
    assert_eq!(chain.frames[1].registers["rbx"], SAVED);
    assert!(
        chain
            .reads
            .iter()
            .any(|read| read.address == IMAGE + 0xa08 && read.requested == 12)
    );
    assert!(chain.reads.iter().any(|read| read.address == IMAGE + 0xb00));

    capture.image_bytes(0xa10, &0xa00u32.to_le_bytes());
    let cycle = capture.recover();
    assert_eq!(cycle.frames.len(), 1);
    assert!(cycle.stop_reason.contains("chain"), "{}", cycle.stop_reason);
    assert_eq!(cycle.frames[0].return_pc, None);
    cycle.validate().unwrap();
    capture.snapshot().validate_thread_frames(&cycle).unwrap();
}

#[test]
fn chained_secondary_cannot_add_fixed_allocation_or_push_nonvolatile() {
    for codes in [vec![4, 0x12], vec![1, 0x30]] {
        let mut capture = Capture::new();
        capture.unwind(4, 0, &codes);
        capture.image_bytes(0xa00, &[0x21]);
        let mut chained = Vec::new();
        for word in [0x200u32, 0x240, 0xb00] {
            chained.extend(word.to_le_bytes());
        }
        capture.image_bytes(0xa08, &chained);
        capture.image_bytes(0xb00, &[1, 4, 1, 0, 4, 0x32]);
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 1);
        assert_eq!(chain.frames[0].return_slot, None);
        assert!(chain.stop_reason.contains("chain"), "{}", chain.stop_reason);
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

#[test]
fn epilogue_suffixes_restore_only_work_not_already_executed() {
    // Legal suffix ADD RSP,32; POP RBX; RET, examined before each instruction.
    for (pc, sp, restore) in [
        (0x220u64, 0x1000, true),
        (0x224, 0x1020, true),
        (0x225, 0x1028, false),
    ] {
        let mut capture = Capture::new();
        capture.unwind(5, 0, &[5, 0x32, 1, 0x30]);
        capture.image_bytes(0x220, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0xc3]);
        capture.pc(IMAGE + pc);
        capture.register(4, sp);
        capture.register(3, 0x5555);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1028, 0x1030);
        assert_eq!(
            chain.frames[1].registers["rbx"],
            if restore { SAVED } else { 0x5555 }
        );
    }
}

#[test]
fn ret_imm16_recovers_the_windows_virtual_unwind_context() {
    let mut capture = Capture::new();
    capture.unwind(4, 0, &[4, 0x32]);
    capture.image_bytes(0x230, &[0xc2, 0x10, 0x00]);
    capture.register(4, 0x1020);
    let chain = capture.recover();
    // Independent RtlVirtualUnwind observation: the recovered context pops the
    // saved PC, while RET's immediate argument cleanup is not part of its SP.
    // This is virtual unwinding, not simulation of executing RET imm16.
    assert_return(&capture, &chain, 0x1020, 0x1028);
}

#[test]
fn reserved_operations_and_invalid_allocations_never_become_completed_frames() {
    for codes in [
        vec![4, 6],
        vec![4, 7],
        vec![4, 11],
        vec![4, 0x21, 1, 0],
        vec![4, 1, 0, 0],
        vec![4, 0x11, 7, 0, 0, 0],
        vec![4, 0x2a],
    ] {
        let mut capture = Capture::new();
        capture.unwind(4, 0, &codes);
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 1, "{codes:?}: {}", chain.stop_reason);
        assert_eq!(chain.frames[0].return_slot, None, "{codes:?}");
        assert!(!chain.truncated, "{codes:?}");
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

fn relocate_image_to_last_address_page(capture: &mut Capture) -> u64 {
    let base = u64::MAX - 0xfff;
    let module = stream(&capture.bytes, 4);
    let memory = stream(&capture.bytes, 5);
    capture.bytes[module + 4..module + 12].copy_from_slice(&base.to_le_bytes());
    capture.bytes[memory + 4..memory + 12].copy_from_slice(&base.to_le_bytes());
    capture.image_bytes(0x98 + 24, &base.to_le_bytes());
    capture.pc(base + 0x230);
    base
}

fn high_address_replay(capture: &Capture, base: u64) -> CapturedFrameChain {
    // The module's half-open extent legitimately ends at mathematical 2^64.
    // A Runtime.end represented by u64 cannot silently turn that end into zero.
    let snapshot = capture.snapshot();
    let chain = snapshot
        .recover_thread_frames(17, FrameRecoveryLimits::default())
        .unwrap();
    assert_eq!(chain.frames.len(), 1);
    assert_eq!(chain.frames[0].pc, base + 0x230);
    assert_eq!(chain.frames[0].return_pc, None);
    assert_eq!(chain.frames[0].function_end, None);
    // The pinned minidump reader omits this module before the adapter sees it.
    assert!(snapshot.metadata().modules.is_empty());
    assert_eq!(chain.stop_reason, "missing-or-ambiguous-frame-module");
    assert!(!chain.truncated);
    chain.validate().unwrap();
    snapshot.validate_thread_frames(&chain).unwrap();
    let mut saved = serde_json::to_value(chain).unwrap();
    saved["seed"]["modules"] = serde_json::json!([{
        "base": format!("0x{base:016x}"), "size": 4096,
        "timestamp": 1, "checksum": 0,
    }]);
    serde_json::from_value(saved).unwrap()
}

fn assert_overflow_replay(
    capture: &Capture,
    mut chain: CapturedFrameChain,
    reads: &[(u64, usize)],
    reason: &str,
) {
    chain.reads = reads
        .iter()
        .map(|&(address, requested)| {
            let read = capture.snapshot().read_prefix(address, requested).unwrap();
            ariadne::investigation::FrameMemoryEvidence {
                address,
                requested,
                bytes_hex: read
                    .bytes
                    .iter()
                    .map(|byte| format!("{byte:02x}"))
                    .collect(),
                spans: read
                    .spans
                    .iter()
                    .map(|span| ariadne::investigation::Span {
                        va: span.address,
                        length: span.length,
                        contributors: span
                            .contributors
                            .iter()
                            .map(|c| ariadne::investigation::Contributor {
                                stream: c.stream,
                                entry: c.entry,
                                file_offset: c.file_offset,
                            })
                            .collect(),
                    })
                    .collect(),
            }
        })
        .collect();
    chain.read_bytes = chain.reads.iter().map(|read| read.requested).sum();
    chain.stop_reason = reason.into();
    rehash(&mut chain);
    chain.validate().unwrap();
    // Standalone replay cannot bypass the live adapter's missing-module result.
    assert!(capture.snapshot().validate_thread_frames(&chain).is_err());
}

#[test]
fn runtime_table_end_at_two_to_64_is_an_explicit_gap_not_wrapped_leaf() {
    let mut capture = Capture::new();
    capture.unwind(4, 0, &[4, 0x32]);
    capture.image_bytes(0x98 + 140, &12u32.to_le_bytes());
    capture.image_bytes(0x804, &0x1000u32.to_le_bytes());
    let base = relocate_image_to_last_address_page(&mut capture);
    let chain = high_address_replay(&capture, base);
    assert_overflow_replay(
        &capture,
        chain,
        &[
            (base, 64),
            (base + 0x80, 24),
            (base + 0x98, 240),
            (base + 0x800, 12),
        ],
        "runtime-function-address-overflow",
    );
}

#[test]
fn chained_runtime_end_at_two_to_64_is_an_explicit_gap_not_wrapped_range() {
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x34, 2, 0]);
    capture.image_bytes(0xa00, &[0x21]);
    let mut primary = Vec::new();
    for word in [0x200u32, 0x1000, 0xb00] {
        primary.extend(word.to_le_bytes());
    }
    capture.image_bytes(0xa08, &primary);
    capture.image_bytes(0xb00, &[1, 4, 1, 0, 4, 0x32]);
    let base = relocate_image_to_last_address_page(&mut capture);
    let mut chain = high_address_replay(&capture, base);
    chain.frames[0].method = "runtime-v1".into();
    assert_overflow_replay(
        &capture,
        chain,
        &[
            (base, 64),
            (base + 0x80, 24),
            (base + 0x98, 240),
            (base + 0x800, 36),
            (base + 0xa00, 4),
            (base + 0xa04, 4),
            (base + 0xa08, 12),
        ],
        "runtime-function-address-overflow",
    );
}

#[test]
fn legacy_header_ending_at_two_to_64_rejects_overflow_before_zero_code_read() {
    let mut capture = Capture::new();
    capture.image_bytes(0x98 + 140, &12u32.to_le_bytes());
    capture.image_bytes(0x808, &0xffcu32.to_le_bytes());
    capture.image_bytes(0xffc, &[1, 4, 0, 0]);
    let base = relocate_image_to_last_address_page(&mut capture);
    for version in [1, 2] {
        let mut chain = high_address_replay(&capture, base);
        chain.profile = format!("captured-windows-amd64-unwind-v{version}");
        chain.frames[0].function_begin = Some(base + 0x200);
        chain.frames[0].function_end = Some(base + 0x240);
        chain.frames[0].method = "runtime-v1".into();
        assert_overflow_replay(
            &capture,
            chain,
            &[
                (base, 64),
                (base + 0x80, 24),
                (base + 0x98, 240),
                (base + 0x800, 12),
                (base + 0x230, 15),
                (base + 0xffc, 4),
            ],
            "unwind-info-overflow",
        );
    }
}

/// Actual synthetic inputs for an independent Windows RtlVirtualUnwind observer.
/// The observer receives Ariadne's result only as the value to compare, never as
/// input to the native unwind operation.
#[test]
#[ignore = "explicit fresh target export for the Windows RtlVirtualUnwind reference"]
fn export_positive_unwind_inputs_for_windows_reference() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let requested = std::path::PathBuf::from(
        std::env::var_os("ARIADNE_UNWIND_EXPORT").expect("ARIADNE_UNWIND_EXPORT is required"),
    );
    let directory = root.join(requested);
    let parent = directory.parent().unwrap().canonicalize().unwrap();
    let target = root.join("target").canonicalize().unwrap();
    assert!(
        parent.starts_with(&target),
        "export must remain under target/"
    );
    assert!(!directory.exists(), "export directory must be fresh");
    std::fs::create_dir(&directory).unwrap();

    let mut cases = Vec::new();
    for bank in [3u8, 5, 6, 7, 12, 13, 14, 15] {
        for far in [false, true] {
            let mut capture = Capture::new();
            let mut codes = vec![8, bank << 4 | if far { 5 } else { 4 }];
            if far {
                codes.extend(16u32.to_le_bytes());
            } else {
                codes.extend(2u16.to_le_bytes());
            }
            codes.extend([4, 0x32]);
            capture.unwind(8, 0, &codes);
            capture.stack_word(0x10, SAVED);
            cases.push((
                format!("save-gpr-{bank}-{}", if far { "far" } else { "near" }),
                capture,
            ));
        }
        let mut capture = Capture::new();
        capture.unwind(5, 0, &[5, 0x32, 1, bank << 4]);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        cases.push((format!("push-gpr-{bank}"), capture));

        let mut capture = Capture::new();
        capture.register(usize::from(bank), 0x1030);
        capture.unwind(10, 0x10 | bank, &[10, 3, 4, 0x32]);
        capture.returns(0x40);
        cases.push((format!("frame-register-{bank}"), capture));
    }
    for size in [8u32, 16, 32, 64, 128] {
        for encoding in 0..3 {
            let mut codes = vec![
                4,
                match encoding {
                    0 => (((size / 8 - 1) as u8) << 4) | 2,
                    1 => 1,
                    _ => 0x11,
                },
            ];
            if encoding == 1 {
                codes.extend(((size / 8) as u16).to_le_bytes());
            }
            if encoding == 2 {
                codes.extend(size.to_le_bytes());
            }
            let mut capture = Capture::new();
            capture.unwind(4, 0, &codes);
            capture.returns(size as usize);
            cases.push((format!("allocation-{size}-{encoding}"), capture));
        }
    }
    for bank in 6..=15 {
        for far in [false, true] {
            let mut capture = Capture::new();
            let codes = if far {
                vec![8, bank << 4 | 9, 16, 0, 0, 0, 4, 0x32]
            } else {
                vec![8, bank << 4 | 8, 1, 0, 4, 0x32]
            };
            capture.unwind(8, 0, &codes);
            capture.xmm(0x10);
            cases.push((
                format!("save-xmm-{bank}-{}", if far { "far" } else { "near" }),
                capture,
            ));
        }
    }
    for error_code in [false, true] {
        let mut capture = Capture::new();
        capture.unwind(1, 0, &[1, if error_code { 0x1a } else { 0x0a }]);
        let offset = if error_code { 8 } else { 0 };
        capture.stack_word(offset, IMAGE + 0x340);
        capture.stack_word(offset + 8, 0x33);
        capture.stack_word(offset + 16, 0x202);
        capture.stack_word(offset + 24, 0x1040);
        capture.stack_word(offset + 32, 0x2b);
        if error_code {
            capture.stack_word(0, 0xbad);
        }
        capture.stack_word(0x40, 0);
        cases.push((format!("machine-frame-error-{error_code}"), capture));
    }
    for (offset, sp) in [(0u64, 0x1028), (1, 0x1020), (5, 0x1000)] {
        let mut capture = Capture::new();
        capture.image_bytes(0x200, &[0x53, 0x48, 0x83, 0xec, 0x20]);
        capture.unwind(5, 0, &[5, 0x32, 1, 0x30]);
        capture.register(4, sp);
        capture.register(3, 0x5555);
        capture.pc(IMAGE + 0x200 + offset);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        cases.push((format!("partial-prologue-{offset}"), capture));
    }
    for (pc, sp) in [(0x220u64, 0x1000), (0x224, 0x1020), (0x225, 0x1028)] {
        let mut capture = Capture::new();
        capture.unwind(5, 0, &[5, 0x32, 1, 0x30]);
        capture.image_bytes(0x220, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0xc3]);
        capture.pc(IMAGE + pc);
        capture.register(4, sp);
        capture.register(3, 0x5555);
        capture.stack_word(0x20, SAVED);
        capture.returns(0x28);
        cases.push((format!("epilogue-{pc:x}"), capture));
    }
    for flags in [1u8, 2] {
        let mut capture = Capture::new();
        capture.unwind(4, 0, &[4, 0x32]);
        capture.image_bytes(0xa00, &[1 | flags << 3]);
        capture.image_bytes(0xa08, &0x500u32.to_le_bytes());
        capture.image_bytes(0x500, &[0xcc]);
        cases.push((format!("handler-{flags}"), capture));
    }
    let mut capture = Capture::new();
    capture.unwind(4, 0, &[4, 0x32]);
    capture.image_bytes(0x230, &[0xc2, 0x10, 0x00]);
    capture.register(4, 0x1020);
    cases.push(("epilogue-ret-imm16".into(), capture));
    let mut capture = Capture::new();
    capture.unwind(8, 0, &[8, 0x34, 2, 0]);
    capture.image_bytes(0xa00, &[0x21]);
    let mut trailer = Vec::new();
    for word in [0x200u32, 0x240, 0xb00] {
        trailer.extend(word.to_le_bytes());
    }
    capture.image_bytes(0xa08, &trailer);
    capture.image_bytes(0xb00, &[1, 4, 1, 0, 4, 0x32]);
    capture.stack_word(0x10, SAVED);
    cases.push(("chained-save-gpr".into(), capture));
    cases.extend(metadata_v2::positive_cases());

    if let Ok(selected) = std::env::var("ARIADNE_UNWIND_EXPORT_CASE") {
        cases.retain(|(name, _)| name == &selected);
        assert_eq!(cases.len(), 1, "unknown native reference case: {selected}");
    }

    let mut rows = Vec::new();
    for (name, capture) in cases {
        let chain = capture.recover();
        chain.validate().unwrap();
        let caller = chain
            .frames
            .get(1)
            .unwrap_or_else(|| panic!("{name}: {}", chain.stop_reason));
        let file = format!("{name}.dmp");
        let digest = format!("{:x}", Sha256::digest(&capture.bytes));
        std::fs::write(directory.join(&file), capture.bytes).unwrap();
        rows.push(serde_json::json!({
            "name": name, "file": file, "sha256": digest,
            "ariadne": {"pc": caller.pc, "sp": caller.sp, "registers": caller.registers},
        }));
    }
    let manifest = serde_json::json!({
        "cases": rows,
        "sources": {
            "src/investigation/frame_unwind.rs": format!("{:x}", Sha256::digest(include_bytes!("../../src/investigation/frame_unwind.rs"))),
            "src/input/frame_paths.rs": format!("{:x}", Sha256::digest(include_bytes!("../../src/input/frame_paths.rs"))),
            "tests/input/unwind_operations.rs": format!("{:x}", Sha256::digest(include_bytes!("unwind_operations.rs"))),
            "tests/input/unwind_v2.rs": format!("{:x}", Sha256::digest(include_bytes!("unwind_v2.rs"))),
        },
        "skipped": [
            "Malformed metadata and out-of-bounds cases are Rust rejection tests; they are unsafe native unwinder inputs.",
            "SAVE_XMM128/FAR saved bytes are validated by Rust tests; this reference compares PC/SP/GPR state only.",
            "Sparse captured-code inputs are exercised by Rust tests only; native reference inputs have complete synthetic images.",
            "Address ranges ending at 2^64 are exercised by Rust reader/replay tests only; native reference inputs use the bounded synthetic image domain.",
            "Windows unwind metadata version 3/APX and arbitrary exception dispatch are outside this finite v1/v2 reference corpus.",
        ],
    });
    std::fs::write(
        directory.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
    println!(
        "Windows unwind reference inputs: {} cases at {}",
        manifest["cases"].as_array().unwrap().len(),
        directory.display()
    );
}
