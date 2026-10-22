//! Windows metadata v2 fixtures authored independently of the runtime parser.
//! The descriptor length includes only the terminal's first byte and excludes
//! preceding ADD/LEA cleanup. These conventions follow Microsoft's copied OS
//! unwinder and LLVM's MCWin64EH v2 producer; Windows comparison is independent.
use super::{
    Capture, IMAGE, SAVED, STACK, assert_return, legacy_prefix_order, rehash, stream, u32_at,
};
use ariadne::investigation::CapturedFrameChain;

fn rbp_free_capture(descriptors: &[u8], pc: u64, sp: u64) -> Capture {
    let mut capture = Capture::new();
    capture.image_bytes(0x200, &[0x53, 0x48, 0x83, 0xec, 0x20]);
    capture.image_bytes(0x23a, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0xc3]);
    let mut codes = descriptors.to_vec();
    codes.extend([5, 0x32, 1, 0x30]);
    capture.unwind(5, 0, &codes);
    capture.image_bytes(0xa00, &[2]);
    capture.pc(IMAGE + pc);
    capture.register(4, sp);
    capture.register(3, if sp >= 0x1028 { SAVED } else { 0x5555 });
    capture.stack_word(0x20, SAVED);
    capture.returns(0x28);
    capture
}

fn tail(pc: u64, sp: u64) -> Capture {
    // Common size2; implicit final epilog plus required second padding slot.
    rbp_free_capture(&[2, 0x16, 0, 6], pc, sp)
}

fn r12_tail(pc: u64, sp: u64) -> Capture {
    let mut capture = Capture::new();
    capture.image_bytes(0x200, &[0x41, 0x54, 0x48, 0x83, 0xec, 0x20]);
    capture.image_bytes(0x239, &[0x48, 0x83, 0xc4, 0x20, 0x41, 0x5c, 0xc3]);
    capture.unwind(6, 0, &[3, 0x16, 0, 6, 6, 0x32, 2, 0xc0]);
    capture.image_bytes(0xa00, &[2]);
    capture.pc(IMAGE + pc);
    capture.register(4, sp);
    capture.register(12, if sp >= 0x1028 { SAVED } else { 0x5555 });
    capture.stack_word(0x20, SAVED);
    capture.returns(0x28);
    capture
}

fn multiple(pc: u64, sp: u64) -> Capture {
    // The implicit final span may coexist with an earlier explicit distance.
    let mut capture = rbp_free_capture(&[2, 0x16, 0x20, 6], pc, sp);
    capture.image_bytes(0x21c, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0xc3]);
    capture
}

fn flags_pop(pc: u64, sp: u64) -> Capture {
    let mut capture = Capture::new();
    // PUSHFQ; PUSH RBX; SUB RSP,32, followed by POP RBX; POP RCX; RET.
    capture.image_bytes(0x200, &[0x9c, 0x53, 0x48, 0x83, 0xec, 0x20]);
    capture.image_bytes(0x239, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0x59, 0xc3]);
    capture.unwind(6, 0, &[3, 0x16, 0, 6, 6, 0x32, 2, 0x30, 1, 2]);
    capture.image_bytes(0xa00, &[2]);
    capture.pc(IMAGE + pc);
    capture.register(4, sp);
    capture.register(3, if sp >= 0x1028 { SAVED } else { 0x5555 });
    capture.stack_word(0x20, SAVED);
    capture.stack_word(0x28, 0x202);
    capture.returns(0x30);
    capture
}

fn machine_epilog(error_code: bool) -> Capture {
    let mut capture = Capture::new();
    // The descriptor counts the first byte of IRETQ only. Any hardware error
    // code has already been removed before entering this epilog span.
    capture.unwind(
        1,
        0,
        &[1, 6, 0x10, 6, 1, if error_code { 0x1a } else { 0x0a }],
    );
    capture.image_bytes(0xa00, &[2]);
    capture.image_bytes(0x230, &[0x48, 0xcf]);
    capture.stack_word(0, IMAGE + 0x340);
    capture.stack_word(8, 0x33);
    capture.stack_word(16, 0x202);
    capture.stack_word(24, 0x1040);
    capture.stack_word(32, 0x2b);
    capture.stack_word(0x40, 0);
    capture
}

fn high_offset() -> Capture {
    let mut capture = rbp_free_capture(&[2, 6, 0x20, 0x16], 0x1d0, 0x1020);
    // The explicit end-relative distance is 0x2f0-0x1d0 = 0x120.
    capture.image_bytes(0x800, &0x1c0u32.to_le_bytes());
    capture.image_bytes(0x804, &0x2f0u32.to_le_bytes());
    capture.image_bytes(0x1c0, &[0x53, 0x48, 0x83, 0xec, 0x20]);
    capture.image_bytes(0x1cc, &[0x48, 0x83, 0xc4, 0x20, 0x5b, 0xc3]);
    capture
}

fn ret_imm() -> Capture {
    let mut capture = rbp_free_capture(&[2, 6, 0x10, 6], 0x231, 0x1028);
    capture.image_bytes(0x230, &[0x5b, 0xc2, 0x10, 0]);
    capture
}

fn direct_tail_jump() -> Capture {
    let mut capture = rbp_free_capture(&[2, 6, 0x10, 6], 0x231, 0x1028);
    let mut code = vec![0x5b, 0xe9];
    code.extend((0x500i32 - 0x236).to_le_bytes());
    capture.image_bytes(0x230, &code);
    capture
}

/// Retain explicit image fragments instead of a whole-image memory descriptor.
/// The omitted bytes still exist in the file but have no captured VA mapping.
fn omit_code(capture: &mut Capture, holes: &[(usize, usize)]) {
    let mut ranges = Vec::new();
    let mut begin = 0;
    for &(lo, hi) in holes {
        assert!(begin <= lo && lo < hi && hi <= 4096);
        if begin < lo {
            ranges.push((begin, lo));
        }
        begin = hi;
    }
    if begin < 4096 {
        ranges.push((begin, 4096));
    }
    let mut memory = ((ranges.len() + 1) as u32).to_le_bytes().to_vec();
    for (begin, end) in ranges {
        memory.extend((IMAGE + begin as u64).to_le_bytes());
        memory.extend(((end - begin) as u32).to_le_bytes());
        memory.extend(((capture.image + begin) as u32).to_le_bytes());
    }
    memory.extend(STACK.to_le_bytes());
    memory.extend(256u32.to_le_bytes());
    memory.extend((capture.stack as u32).to_le_bytes());
    let offset = capture.bytes.len();
    let directory = u32_at(&capture.bytes, 12);
    let count = u32_at(&capture.bytes, 8);
    let record = (0..count)
        .map(|i| directory + i * 12)
        .find(|at| u32_at(&capture.bytes, *at) == 5)
        .unwrap();
    capture.bytes[record + 4..record + 8].copy_from_slice(&(memory.len() as u32).to_le_bytes());
    capture.bytes[record + 8..record + 12].copy_from_slice(&(offset as u32).to_le_bytes());
    capture.bytes.extend(memory);
}

fn assert_avoids_holes(chain: &CapturedFrameChain, holes: &[(usize, usize)]) {
    for read in &chain.reads {
        for &(lo, hi) in holes {
            assert!(
                read.address >= IMAGE + hi as u64
                    || read.address + read.requested as u64 <= IMAGE + lo as u64,
                "read {:x}+{} crosses absent captured bytes {lo:x}..{hi:x}",
                read.address,
                read.requested
            );
        }
    }
}

pub(super) fn positive_cases() -> Vec<(String, Capture)> {
    let mut cases = Vec::new();
    for (name, pc, sp) in [
        ("body", 0x230, 0x1000),
        ("cleanup", 0x23a, 0x1000),
        ("pop", 0x23e, 0x1020),
        ("ret", 0x23f, 0x1028),
        ("prolog-before-push", 0x200, 0x1028),
        ("prolog-after-push", 0x201, 0x1020),
    ] {
        cases.push((format!("v2-tail-{name}"), tail(pc, sp)));
    }
    for (name, pc, sp) in [("pop-r12", 0x23d, 0x1020), ("ret-after-r12", 0x23f, 0x1028)] {
        cases.push((format!("v2-{name}"), r12_tail(pc, sp)));
    }
    for (pc, sp) in [
        (0x220, 0x1020),
        (0x221, 0x1028),
        (0x23e, 0x1020),
        (0x23f, 0x1028),
    ] {
        cases.push((format!("v2-multiple-{pc:x}"), multiple(pc, sp)));
    }
    for (pc, sp) in [(0x23d, 0x1020), (0x23e, 0x1028), (0x23f, 0x1030)] {
        cases.push((format!("v2-flags-pop-{pc:x}"), flags_pop(pc, sp)));
    }
    for error_code in [false, true] {
        cases.push((
            format!("v2-machine-epilog-error-{error_code}"),
            machine_epilog(error_code),
        ));
    }
    cases.push(("v2-high-explicit-offset".into(), high_offset()));
    cases.push(("v2-ret-imm16".into(), ret_imm()));
    cases.push(("v2-direct-tail-jump".into(), direct_tail_jump()));
    let mut no_markers = rbp_free_capture(&[], 0x230, 0x1000);
    no_markers.image_bytes(0x230, &[0xc3]);
    cases.push(("v2-body-without-epilog-descriptors".into(), no_markers));
    for flags in [1u8, 2, 3] {
        let mut capture = tail(0x230, 0x1000);
        capture.image_bytes(0xa00, &[2 | flags << 3]);
        capture.image_bytes(0xa0c, &0x500u32.to_le_bytes());
        capture.image_bytes(0x500, &[0xcc]);
        cases.push((format!("v2-handler-{flags}"), capture));
    }
    cases
}

#[test]
fn descriptors_select_pop_suffixes_without_reapplying_stack_cleanup() {
    for (pc, sp) in [
        (0x230, 0x1000),
        (0x23a, 0x1000),
        (0x23e, 0x1020),
        (0x23f, 0x1028),
    ] {
        let capture = tail(pc, sp);
        let chain = capture.recover();
        assert_eq!(chain.profile, "captured-windows-amd64-unwind-v4");
        assert_return(&capture, &chain, 0x1028, 0x1030);
        assert_eq!(chain.frames[1].registers["rbx"], SAVED);
    }
    for (pc, sp) in [(0x23d, 0x1020), (0x23f, 0x1028)] {
        let capture = r12_tail(pc, sp);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1028, 0x1030);
        assert_eq!(chain.frames[1].registers["r12"], SAVED);
    }
}

#[test]
fn explicit_offsets_multiple_spans_and_multibyte_terminals_use_exact_geometry() {
    for capture in [
        multiple(0x220, 0x1020),
        multiple(0x221, 0x1028),
        multiple(0x23e, 0x1020),
        high_offset(),
        ret_imm(),
    ] {
        assert_return(&capture, &capture.recover(), 0x1028, 0x1030);
    }
}

#[test]
fn v2_without_descriptors_uses_body_unwind_even_at_a_ret_byte() {
    let mut capture = rbp_free_capture(&[], 0x230, 0x1000);
    capture.image_bytes(0x230, &[0xc3]);
    assert_return(&capture, &capture.recover(), 0x1028, 0x1030);
}

#[test]
fn partial_prologues_and_flags_cleanup_have_distinct_metadata_paths() {
    for (pc, sp) in [(0x200, 0x1028), (0x201, 0x1020), (0x205, 0x1000)] {
        let capture = tail(pc, sp);
        assert_return(&capture, &capture.recover(), 0x1028, 0x1030);
    }
    for (pc, sp) in [(0x23d, 0x1020), (0x23e, 0x1028), (0x23f, 0x1030)] {
        let capture = flags_pop(pc, sp);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1030, 0x1038);
        assert_eq!(chain.frames[1].registers["rbx"], SAVED);
        assert!(!chain.frames[1].registers.contains_key("rcx"));
    }
}

#[test]
fn machine_epilog_iretq_uses_the_already_removed_error_code_layout() {
    for error_code in [false, true] {
        let capture = machine_epilog(error_code);
        let chain = capture.recover();
        assert_eq!(chain.frames.len(), 2, "{}", chain.stop_reason);
        assert_eq!(chain.frames[0].return_slot, Some(STACK));
        assert_eq!(chain.frames[1].pc, IMAGE + 0x340);
        assert_eq!(chain.frames[1].sp, 0x1040);
        assert_eq!(chain.frames[1].function_begin, None);
        assert_eq!(
            chain.frames[1].register_evidence["rsp"].stack_slot,
            Some(0x1018)
        );
        assert_eq!(
            serde_json::to_value(&chain.frames[0]).unwrap()["transition"],
            "machine_frame"
        );
        chain.validate().unwrap();
        capture.snapshot().validate_thread_frames(&chain).unwrap();
    }
}

fn rejected(capture: &Capture) -> CapturedFrameChain {
    let chain = capture.recover();
    assert_eq!(chain.frames.len(), 1, "{}", chain.stop_reason);
    assert_eq!(chain.frames[0].return_pc, None);
    assert!(!chain.truncated);
    chain.validate().unwrap();
    capture.snapshot().validate_thread_frames(&chain).unwrap();
    chain
}

#[test]
fn malformed_descriptor_size_flags_padding_and_positions_are_rejected() {
    let descriptors = [
        vec![0, 0x16, 0, 6],                // zero common size
        vec![2, 0x26, 0, 6],                // first OpInfo is flags, not an offset high nibble
        vec![2, 0x16],                      // odd prefix without padding
        vec![2, 6, 0, 6],                   // no implicit or explicit epilog
        vec![2, 0x16, 0, 6, 0x20, 6, 0, 6], // interior padding
        vec![2, 0x16, 0, 7],                // reserved operation is not descriptor padding
    ];
    for descriptor in descriptors {
        rejected(&rbp_free_capture(&descriptor, 0x23e, 0x1020));
    }
    for flags in 2u8..=15 {
        rejected(&rbp_free_capture(&[2, flags << 4 | 6, 0, 6], 0x23e, 0x1020));
    }
    let mut late = tail(0x23e, 0x1020);
    late.unwind(5, 0, &[5, 0x32, 2, 0x16, 0, 6, 1, 0x30]);
    late.image_bytes(0xa00, &[2]);
    rejected(&late);
}

#[test]
fn descriptor_ranges_reject_underflow_overlap_duplicates_and_function_escape() {
    for descriptor in [
        vec![2, 6, 0xff, 0xf6],             // offset exceeds whole function extent
        vec![2, 6, 1, 6],                   // common size extends beyond function end
        vec![2, 0x16, 2, 6],                // duplicate implicit tail
        vec![2, 0x16, 3, 6],                // overlapping tail spans
        vec![2, 6, 0x20, 6, 0x20, 6, 0, 6], // duplicate explicit distance
    ] {
        rejected(&rbp_free_capture(&descriptor, 0x23e, 0x1020));
    }
}

#[test]
fn descriptor_claims_require_matching_pop_terminal_and_instruction_boundary() {
    let mut wrong_register = tail(0x23e, 0x1020);
    wrong_register.image_bytes(0x23e, &[0x5e, 0xc3]);
    rejected(&wrong_register);
    let mut wrong_terminal = tail(0x23e, 0x1020);
    wrong_terminal.image_bytes(0x23f, &[0x90]);
    rejected(&wrong_terminal);
    rejected(&r12_tail(0x23e, 0x1020));
}

#[test]
fn v2_flags_and_truncated_captured_code_arrays_remain_explicit_failures() {
    for flags in [5u8, 6, 7, 8, 16, 31] {
        let mut capture = tail(0x230, 0x1000);
        capture.image_bytes(0xa00, &[2 | flags << 3]);
        rejected(&capture);
    }
    let mut capture = tail(0x230, 0x1000);
    let memory = stream(&capture.bytes, 5);
    // File bytes remain present, but the captured VA interval ends midway
    // through the first descriptor. No image fallback may fill this hole.
    capture.bytes[memory + 12..memory + 16].copy_from_slice(&0xa05u32.to_le_bytes());
    let chain = rejected(&capture);
    assert!(
        chain
            .stop_reason
            .contains("missing-or-conflicting-unwind-bytes"),
        "{}",
        chain.stop_reason
    );
}

#[test]
fn saved_profile_v3_keeps_its_original_windows_v2_header_stop() {
    let capture = tail(0x230, 0x1000);
    let mut old = capture.recover();
    legacy_prefix_order(&capture, &mut old);
    old.profile = "captured-windows-amd64-unwind-v3".into();
    old.frames.truncate(1);
    old.frames[0].return_pc = None;
    old.frames[0].return_slot = None;
    old.frames[0].transition = None;
    old.frames[0].function_begin = None;
    old.frames[0].function_end = None;
    old.frames[0].method = "runtime-v1".into();
    let header = old
        .reads
        .iter()
        .position(|read| read.address == IMAGE + 0xa00 && read.requested == 4)
        .unwrap();
    old.reads.truncate(header + 1);
    old.read_bytes = old.reads.iter().map(|read| read.requested).sum();
    old.stop_reason = "unsupported-windows-unwind-version".into();
    old.truncated = false;
    rehash(&mut old);
    old.validate().unwrap();
    capture.snapshot().validate_thread_frames(&old).unwrap();
}

#[test]
fn v2_body_and_prologue_need_metadata_not_unrelated_instruction_bytes() {
    for (pc, sp, holes) in [
        (0x230, 0x1000, vec![(0x230, 0x240)]),
        (0x230, 0x1000, vec![(0x231, 0x240)]),
        (0x200, 0x1028, vec![(0x200, 0x240)]),
        (0x201, 0x1020, vec![(0x200, 0x240)]),
    ] {
        let mut capture = tail(pc, sp);
        omit_code(&mut capture, &holes);
        let chain = capture.recover();
        assert_return(&capture, &chain, 0x1028, 0x1030);
        assert_avoids_holes(&chain, &holes);
        assert!(
            !chain
                .reads
                .iter()
                .any(|read| read.address >= IMAGE + 0x200 && read.address < IMAGE + 0x240)
        );
    }
}

#[test]
fn selected_epilogue_reads_only_its_real_pop_and_terminal_bytes() {
    let mut tail = tail(0x23e, 0x1020);
    omit_code(&mut tail, &[(0x200, 0x23e), (0x240, 0x300)]);
    let chain = tail.recover();
    assert_return(&tail, &chain, 0x1028, 0x1030);
    assert_avoids_holes(&chain, &[(0x200, 0x23e), (0x240, 0x300)]);
    let mut immediate = ret_imm();
    omit_code(&mut immediate, &[(0x234, 0x300)]);
    let chain = immediate.recover();
    assert_return(&immediate, &chain, 0x1028, 0x1030);
    assert_avoids_holes(&chain, &[(0x234, 0x300)]);
    let mut machine = machine_epilog(false);
    omit_code(&mut machine, &[(0x232, 0x300)]);
    let chain = machine.recover();
    assert_eq!(chain.frames[1].pc, IMAGE + 0x340);
    assert_eq!(chain.frames[1].sp, 0x1040);
    assert_avoids_holes(&chain, &[(0x232, 0x300)]);
    chain.validate().unwrap();
    machine.snapshot().validate_thread_frames(&chain).unwrap();
}

#[test]
fn pc_in_terminal_bytes_outside_common_size_is_not_reclassified_as_body() {
    let mut machine = machine_epilog(false);
    machine.pc(IMAGE + 0x231);
    rejected(&machine);
    for pc in [0x232, 0x233] {
        let mut immediate = ret_imm();
        immediate.pc(IMAGE + pc);
        rejected(&immediate);
    }
    for pc in 0x232..=0x235 {
        let mut jump = direct_tail_jump();
        jump.pc(IMAGE + pc);
        rejected(&jump);
    }
}
