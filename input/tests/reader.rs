mod common;
use ariadne_input::{FileSnapshot, InputError, OpenLimits, Platform, ReadStop};
use common::*;
fn open(d: Dump) -> FileSnapshot {
    FileSnapshot::from_minidump_bytes(d.finish(), OpenLimits::default()).unwrap()
}
#[test]
fn memory_lists_and_packed_memory64_preserve_virtual_addresses_and_file_offsets() {
    for linux in [false, true] {
        let mut a = Dump::new(linux);
        a.memory(&[(0x4000, &[1, 2, 3]), (0x7000, &[4, 5, 6, 7, 8])]);
        let mut b = Dump::new(linux);
        b.memory64(&[(0x4000, &[1, 2, 3]), (0x7000, &[4, 5, 6, 7, 8])]);
        let a = open(a);
        let b = open(b);
        for (va, expected) in [(0x4000, vec![1, 2, 3]), (0x7000, vec![4, 5, 6, 7, 8])] {
            let x = a.read_prefix(va, 15).unwrap();
            let y = b.read_prefix(va, 15).unwrap();
            assert_eq!(x.bytes, expected);
            assert_eq!(y.bytes, expected);
            assert_eq!(x.spans[0].contributors[0].stream, 5);
            assert_eq!(y.spans[0].contributors[0].stream, 9);
        }
        assert_eq!(
            a.metadata().platform,
            if linux {
                Platform::Linux
            } else {
                Platform::Windows
            }
        );
        assert_ne!(a.metadata().snapshot_id, b.metadata().snapshot_id);
    }
}
#[test]
fn adjacent_and_identical_overlaps_compose_but_conflicts_are_localized() {
    let mut d = Dump::new(false);
    d.memory(&[
        (100, &[0x90, 0x48]),
        (102, &[0x89, 0xd8]),
        (101, &[0x48, 0x89]),
    ]);
    d.memory64(&[(103, &[0xff])]);
    let s = open(d);
    let r = s.read_prefix(100, 15).unwrap();
    assert_eq!(r.bytes, vec![0x90, 0x48, 0x89]);
    assert_eq!(r.stop, ReadStop::ConflictingCapture(103));
    assert_eq!(
        s.read_prefix(101, 1).unwrap().spans[0].contributors.len(),
        2
    );
    assert!(s.read_prefix(103, 1).unwrap().bytes.is_empty());
    assert_eq!(
        s.read_prefix(104, 1).unwrap().stop,
        ReadStop::NotCaptured(104)
    );
}
#[test]
fn thread_capture_and_valid_register_groups_are_retained_without_using_crash_values() {
    let mut d = Dump::new(true);
    d.thread(17, 0x8000, &[0xc3], 0x1234, 1);
    d.exception(17, 0xdead, 0x5678);
    let s = open(d);
    assert_eq!(s.read_prefix(0x8000, 15).unwrap().bytes, vec![0xc3]);
    assert_eq!(s.metadata().threads[0].registers.get("rip"), Some(&0x1234));
    assert!(!s.metadata().threads[0].registers.contains_key("rax"));
    let e = s.metadata().exception.as_ref().unwrap();
    assert_eq!(e.reported_address, 0xdead);
    assert_eq!(e.registers.get("rip"), Some(&0x5678));
    let mut d = Dump::new(false);
    d.thread(1, 0, &[], 99, 2);
    let s = open(d);
    assert!(!s.metadata().threads[0].registers.contains_key("rip"));
    assert_eq!(s.metadata().threads[0].registers.get("rax"), Some(&0x1234));
}
#[test]
fn metadata_and_unknown_streams_never_supply_memory() {
    let mut d = Dump::new(false);
    d.module(0x1000, 4096, "not-opened.exe");
    d.stream(0x12345678, vec![0xc3]);
    let s = open(d);
    assert_eq!(s.metadata().modules[0].name, "not-opened.exe");
    assert_eq!(
        s.read_prefix(0x1000, 1).unwrap().stop,
        ReadStop::NotCaptured(0x1000)
    );
    assert!(s.metadata().gaps.iter().any(|g| g.stream == 0x12345678));
}
#[test]
fn malformed_ranges_duplicates_counts_and_architecture_are_rejected() {
    let mut cases = Vec::new();
    let mut d = Dump::new(false);
    d.memory(&[(u64::MAX, &[1, 2])]);
    cases.push(d.finish());
    let mut d = Dump::new(false);
    d.memory(&[(1, &[1])]);
    d.memory(&[(2, &[2])]);
    cases.push(d.finish());
    let mut d = Dump::new(false);
    let mut bad = vec![0; 20];
    w32(&mut bad, 0, 1);
    w64(&mut bad, 4, 1);
    w32(&mut bad, 12, 2);
    w32(&mut bad, 16, u32::MAX);
    d.stream(5, bad);
    cases.push(d.finish());
    let mut d = Dump::new(false);
    let mut bad = vec![0; 16];
    w64(&mut bad, 0, u64::MAX);
    d.stream(9, bad);
    cases.push(d.finish());
    let mut d = Dump::new(false);
    d.bytes[32] = 0;
    cases.push(d.finish());
    let mut d = Dump::new(false);
    w32(&mut d.bytes, 52, 1);
    cases.push(d.finish());
    for b in cases {
        assert!(FileSnapshot::from_minidump_bytes(b, OpenLimits::default()).is_err());
    }
}
#[test]
fn immutable_identity_limits_empty_reads_and_last_virtual_byte() {
    let mut d = Dump::new(true);
    d.memory(&[(u64::MAX, &[0xc3])]);
    let bytes = d.finish();
    let s = FileSnapshot::from_minidump_bytes(bytes.clone(), OpenLimits::default()).unwrap();
    let t = FileSnapshot::from_minidump_bytes(bytes.clone(), OpenLimits::default()).unwrap();
    assert_eq!(s.metadata().snapshot_id, t.metadata().snapshot_id);
    let r = s.read_prefix(u64::MAX, 2).unwrap();
    assert_eq!(r.bytes, vec![0xc3]);
    assert_eq!(r.stop, ReadStop::AddressOverflow);
    assert_eq!(s.read_prefix(0, 0).unwrap().stop, ReadStop::RequestedLength);
    assert!(matches!(s.read_prefix(0, 65537), Err(InputError::Limit(_))));
    assert!(
        FileSnapshot::from_minidump_bytes(
            bytes,
            OpenLimits {
                max_file_bytes: 10,
                ..OpenLimits::default()
            }
        )
        .is_err()
    );
    let mut d = Dump::new(false);
    d.memory(&[(1, &[1]), (1, &[1])]);
    assert!(
        FileSnapshot::from_minidump_bytes(
            d.finish(),
            OpenLimits {
                max_overlap: 1,
                ..OpenLimits::default()
            }
        )
        .is_err()
    );
}

#[test]
fn sparse_memory_info_is_metadata_and_does_not_become_capture() {
    let mut d = Dump::new(true);
    let mut info = vec![0; 64];
    w32(&mut info, 0, 16);
    w32(&mut info, 4, 48);
    w64(&mut info, 8, 1);
    w64(&mut info, 16, 0x5000);
    w64(&mut info, 40, 0x1000);
    w32(&mut info, 48, 0x1000);
    w32(&mut info, 52, 0x20);
    d.stream(16, info);
    let s = open(d);
    assert_eq!(s.metadata().memory_info[0].base, 0x5000);
    assert!(s.read_prefix(0x5000, 15).unwrap().bytes.is_empty());
}
#[test]
fn bounded_corruptions_do_not_panic_or_publish_out_of_bounds_ranges() {
    let mut d = Dump::new(false);
    d.memory(&[(1, &[1, 2, 3]), (200, &[4, 5])]);
    d.module(1, 200, "test.dll");
    d.thread(1, 400, &[0xc3], 1, 3);
    let bytes = d.finish();
    let mut random = 0x712abc_u64;
    for _ in 0..512 {
        random ^= random << 13;
        random ^= random >> 7;
        random ^= random << 17;
        let mut altered = bytes.clone();
        let i = (random as usize) % altered.len();
        altered[i] ^= (random >> 32) as u8 | 1;
        if let Ok(s) = FileSnapshot::from_minidump_bytes(
            altered,
            OpenLimits {
                max_records: 1024,
                max_capture_ranges: 1024,
                ..OpenLimits::default()
            },
        ) {
            for a in [0, 1, 199, 200, 400, u64::MAX] {
                let r = s.read_prefix(a, 15).unwrap();
                assert!(r.bytes.len() <= 15);
            }
        }
    }
}
