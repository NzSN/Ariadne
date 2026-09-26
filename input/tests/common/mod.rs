#![allow(dead_code)]
// Deliberately hand-encoded, independent of the minidump parser/serializer.
pub fn w32(b: &mut [u8], o: usize, n: u32) {
    b[o..o + 4].copy_from_slice(&n.to_le_bytes());
}
pub fn w64(b: &mut [u8], o: usize, n: u64) {
    b[o..o + 8].copy_from_slice(&n.to_le_bytes());
}
#[derive(Default)]
pub struct Dump {
    pub bytes: Vec<u8>,
    pub streams: Vec<(u32, u32, u32)>,
}
impl Dump {
    pub fn new(linux: bool) -> Self {
        let mut d = Self {
            bytes: vec![0; 32],
            streams: Vec::new(),
        };
        let mut sys = vec![0; 56];
        sys[0] = 9;
        sys[6] = 1;
        w32(&mut sys, 20, if linux { 0x8201 } else { 2 });
        d.stream(7, sys);
        d
    }
    pub fn data(&mut self, b: &[u8]) -> u32 {
        let off = self.bytes.len() as u32;
        self.bytes.extend_from_slice(b);
        off
    }
    pub fn stream(&mut self, kind: u32, b: Vec<u8>) {
        let off = self.data(&b);
        self.streams.push((kind, off, b.len() as u32));
    }
    pub fn memory(&mut self, ranges: &[(u64, &[u8])]) {
        let mut list = vec![0; 4 + ranges.len() * 16];
        w32(&mut list, 0, ranges.len() as u32);
        for (i, (va, b)) in ranges.iter().enumerate() {
            let off = self.data(b);
            w64(&mut list, 4 + i * 16, *va);
            w32(&mut list, 12 + i * 16, b.len() as u32);
            w32(&mut list, 16 + i * 16, off);
        }
        self.stream(5, list);
    }
    pub fn memory64(&mut self, ranges: &[(u64, &[u8])]) {
        let mut list = vec![0; 16 + ranges.len() * 16];
        w64(&mut list, 0, ranges.len() as u64);
        w64(&mut list, 8, self.bytes.len() as u64);
        for (i, (va, b)) in ranges.iter().enumerate() {
            self.data(b);
            w64(&mut list, 16 + i * 16, *va);
            w64(&mut list, 24 + i * 16, b.len() as u64);
        }
        self.stream(9, list);
    }
    pub fn thread(&mut self, id: u32, va: u64, stack: &[u8], rip: u64, flags: u32) {
        let stack_off = self.data(stack);
        let context = self.context(rip, flags);
        let mut list = vec![0; 52];
        w32(&mut list, 0, 1);
        w32(&mut list, 4, id);
        w64(&mut list, 28, va);
        w32(&mut list, 36, stack.len() as u32);
        w32(&mut list, 40, stack_off);
        w32(&mut list, 44, 1232);
        w32(&mut list, 48, context);
        self.stream(3, list);
    }
    pub fn context(&mut self, rip: u64, flags: u32) -> u32 {
        let mut c = vec![0; 1232];
        w32(&mut c, 48, 0x100000 | flags);
        w64(&mut c, 248, rip);
        w64(&mut c, 120, 0x1234);
        self.data(&c)
    }
    pub fn exception(&mut self, thread: u32, address: u64, rip: u64) {
        let ctx = self.context(rip, 1);
        let mut ex = vec![0; 168];
        w32(&mut ex, 0, thread);
        w32(&mut ex, 8, 0xc0000005);
        w64(&mut ex, 24, address);
        w32(&mut ex, 160, 1232);
        w32(&mut ex, 164, ctx);
        self.stream(6, ex);
    }
    pub fn module(&mut self, va: u64, size: u32, name: &str) {
        let text: Vec<_> = name.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let mut string = vec![0; 4];
        w32(&mut string, 0, text.len() as u32);
        string.extend(text);
        let off = self.data(&string);
        let mut list = vec![0; 112];
        w32(&mut list, 0, 1);
        w64(&mut list, 4, va);
        w32(&mut list, 12, size);
        w32(&mut list, 24, off);
        self.stream(4, list);
    }
    pub fn finish(mut self) -> Vec<u8> {
        let dir = self.bytes.len() as u32;
        self.bytes[..4].copy_from_slice(b"MDMP");
        w32(&mut self.bytes, 4, 0xa793);
        w32(&mut self.bytes, 8, self.streams.len() as u32);
        w32(&mut self.bytes, 12, dir);
        for (kind, off, len) in self.streams {
            self.bytes.extend(kind.to_le_bytes());
            self.bytes.extend(len.to_le_bytes());
            self.bytes.extend(off.to_le_bytes());
        }
        self.bytes
    }
}
