//! Property-generated synthetic captures; no hardware or real-dump qualification.
use ariadne::input::{FileSnapshot, OpenLimits};
use ariadne::investigation::{Classification, FrameRecoveryLimits};
use proptest::prelude::*;
use proptest::test_runner::{Config, FileFailurePersistence, RngSeed};

fn config() -> Config {
    Config {
        cases: 128,
        max_shrink_iters: 4096,
        rng_seed: RngSeed::Fixed(0x1d82_769b_0af4_33c5),
        failure_persistence: Some(Box::new(FileFailurePersistence::Direct(
            "tests/input/frame_unwind.proptest-regressions",
        ))),
        ..Config::default()
    }
}
fn u32_at(b: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(b[at..at + 4].try_into().unwrap())
}
/// Independent on-disk layout lookup, not FileSnapshot or the unwind reader.
fn stream(b: &[u8], kind: u32) -> usize {
    let count = u32_at(b, 8) as usize;
    let directory = u32_at(b, 12) as usize;
    (0..count)
        .map(|i| directory + i * 12)
        .find(|at| u32_at(b, *at) == kind)
        .map(|at| u32_at(b, at + 8) as usize)
        .unwrap()
}
fn generated_capture(
    units: u16,
    encoding: u8,
    integer_valid: bool,
    rax: u64,
    rcx: u64,
    rbx: u64,
) -> Vec<u8> {
    let mut b = include_bytes!("fixtures/frame_paths/diamond.dmp").to_vec();
    let image = u32_at(&b, stream(&b, 5) + 16) as usize;
    let stack = u32_at(&b, stream(&b, 3) + 4 + 36) as usize;
    let ex = stream(&b, 6);
    let context = u32_at(&b, ex + 164) as usize;
    let allocation = u64::from(units) * 8;
    b[image + 0x200..image + 0x240].fill(0x90);
    let prologue = if allocation <= 120 {
        b[image + 0x200..image + 0x204].copy_from_slice(&[0x48, 0x83, 0xec, allocation as u8]);
        4
    } else {
        b[image + 0x200..image + 0x203].copy_from_slice(&[0x48, 0x81, 0xec]);
        b[image + 0x203..image + 0x207].copy_from_slice(&(allocation as u32).to_le_bytes());
        7
    };
    b[image + 0x20c..image + 0x20f].copy_from_slice(&[0x48, 0x8b, 0x00]);
    let codes = match encoding {
        0 => vec![prologue, ((units - 1) as u8) << 4 | 2],
        1 => {
            let mut c = vec![prologue, 1];
            c.extend(units.to_le_bytes());
            c
        }
        _ => {
            let mut c = vec![prologue, 0x11];
            c.extend((allocation as u32).to_le_bytes());
            c
        }
    };
    b[image + 0x900..image + 0x910].fill(0);
    b[image + 0x900..image + 0x904].copy_from_slice(&[1, prologue, (codes.len() / 2) as u8, 0]);
    b[image + 0x904..image + 0x904 + codes.len()].copy_from_slice(&codes);
    b[stack..stack + 256].fill(0);
    // Algebraic oracle: undo the allocation, then pop an eight-byte return PC.
    for (offset, pc) in [
        (allocation, 0x400315u64),
        (allocation + 40, 0x400415),
        (allocation + 80, 0),
    ] {
        let at = stack + offset as usize;
        b[at..at + 8].copy_from_slice(&pc.to_le_bytes());
    }
    b[context + 48..context + 52]
        .copy_from_slice(&(if integer_valid { 0x100003u32 } else { 0x100001 }).to_le_bytes());
    for (offset, value) in [(120, rax), (128, rcx), (144, rbx), (248, 0x40020c)] {
        b[context + offset..context + offset + 8].copy_from_slice(&value.to_le_bytes());
    }
    b[ex + 24..ex + 32].copy_from_slice(&0x40020cu64.to_le_bytes());
    b
}

proptest! {
    #![proptest_config(config())]

    #[test]
    fn prop_unwind_matches_stack_arithmetic_and_register_validity(units in 1u16..=16,encoding in 0u8..3,integer in any::<bool>(),rax in any::<u64>(),rcx in any::<u64>(),rbx in any::<u64>()){
        let snapshot=FileSnapshot::from_minidump_bytes(generated_capture(units,encoding,integer,rax,rcx,rbx),OpenLimits::default()).unwrap();
        let chain=snapshot.recover_thread_frames(17,FrameRecoveryLimits::default()).unwrap();
        prop_assert_eq!(chain.frames.len(),3);
        prop_assert_eq!(&chain.stop_reason,"zero-return-boundary");
        let allocation=u64::from(units)*8;
        prop_assert_eq!(chain.frames[0].return_slot,Some(0x1000+allocation));
        prop_assert_eq!(chain.frames[1].sp,0x1000+allocation+8);
        prop_assert_eq!(chain.frames[2].sp,0x1000+allocation+48);
        prop_assert_eq!(chain.frames[1].pc,0x400315);
        for frame in &chain.frames[1..]{
            prop_assert!(!frame.registers.contains_key("rax"));prop_assert!(!frame.registers.contains_key("rcx"));
            prop_assert_eq!(frame.registers.get("rbx"),integer.then_some(&rbx));
            prop_assert_eq!(frame.register_evidence["rip"].classification,Classification::DerivedUnderPremises);
        }
        prop_assert_eq!(chain.frames[0].registers.get("rax"),integer.then_some(&rax));
        chain.validate().unwrap();snapshot.validate_thread_frames(&chain).unwrap();
    }

    #[test]
    fn prop_unwind_limits_bound_reads_and_preserve_a_valid_prefix(units in 1u16..=16,encoding in 0u8..3,frames in 0usize..=4,read_bytes in 0usize..=768){
        let snapshot=FileSnapshot::from_minidump_bytes(generated_capture(units,encoding,true,0,0,0),OpenLimits::default()).unwrap();
        let limits=FrameRecoveryLimits{max_frames:frames,max_read_bytes:read_bytes,..FrameRecoveryLimits::default()};
        let limited=snapshot.recover_thread_frames(17,limits).unwrap();
        let full=snapshot.recover_thread_frames(17,FrameRecoveryLimits::default()).unwrap();
        prop_assert!(limited.frames.len()<=frames);
        prop_assert!(limited.read_bytes<=read_bytes);
        for (a,b) in limited.frames.iter().zip(&full.frames){
            prop_assert_eq!((a.index,a.pc,a.sp), (b.index,b.pc,b.sp));
            prop_assert_eq!(&a.registers,&b.registers);
        }
        limited.validate().unwrap();snapshot.validate_thread_frames(&limited).unwrap();
    }

    #[test]
    fn prop_generated_unwind_receipt_tampering_is_rejected(units in 1u16..=16,encoding in 0u8..3,receipt in 0usize..32,byte in 0usize..1024,bit in 0u8..8){
        let snapshot=FileSnapshot::from_minidump_bytes(generated_capture(units,encoding,true,1,2,3),OpenLimits::default()).unwrap();
        let mut chain=snapshot.recover_thread_frames(17,FrameRecoveryLimits::default()).unwrap();
        let at=receipt%chain.reads.len();let data=&mut chain.reads[at].bytes_hex;
        // All ordinary successful recipe reads here are nonempty.
        let index=(byte%(data.len()/2))*2;
        let old=u8::from_str_radix(&data[index..index+2],16).unwrap();
        data.replace_range(index..index+2,&format!("{:02x}",old^(1<<bit)));
        prop_assert!(chain.validate().is_err());
        prop_assert!(snapshot.validate_thread_frames(&chain).is_err());
    }
}
