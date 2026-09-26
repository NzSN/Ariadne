use crate::LocationSet;

const BANKS: [&str; 16] = [
    "rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12", "r13",
    "r14", "r15",
];
pub(crate) const FLAGS: [&str; 7] = ["cf", "pf", "af", "zf", "sf", "of", "df"];

/// A fixed disjoint catalogue; callers cannot add overlapping string aliases.
/// `state:other` groups FP/vector/opmask application data and their status.
/// RIP and system/debug/control state (including RF/TF/IF) are outside this
/// provenance vocabulary, not implicitly preserved architectural facts.
#[derive(Clone, Debug, Default)]
pub struct Catalogue;
impl Catalogue {
    pub fn identity(&self) -> &'static str {
        "gpr-bytes-status-df-memory-other-v1"
    }
    pub fn locations(&self) -> LocationSet {
        let mut result: LocationSet = BANKS
            .iter()
            .flat_map(|b| (0..8).map(move |i| format!("gpr:{b}:{i}")))
            .collect();
        result.extend(FLAGS.map(|f| format!("flag:{f}")));
        result.extend(["memory:any".into(), "state:other".into()]);
        result
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RegisterView {
    bank: u8,
    offset: u8,
    width: u8,
}
impl RegisterView {
    pub fn new(bank: u8, bit_offset: u8, width: u8) -> Option<Self> {
        (bank < 16
            && ((bit_offset == 0 && [8, 16, 32, 64].contains(&width))
                || (bank < 4 && bit_offset == 8 && width == 8)))
            .then_some(Self {
                bank,
                offset: bit_offset,
                width,
            })
    }
    pub fn bank(&self) -> u8 {
        self.bank
    }
    pub fn bit_offset(&self) -> u8 {
        self.offset
    }
    pub fn width(&self) -> u8 {
        self.width
    }
    pub fn reads(&self) -> LocationSet {
        self.cells(self.offset / 8, self.width / 8)
    }
    pub fn replacements(&self) -> LocationSet {
        if self.width == 32 {
            self.cells(0, 8)
        } else {
            self.reads()
        }
    }
    fn cells(&self, start: u8, len: u8) -> LocationSet {
        (start..start + len)
            .map(|i| format!("gpr:{}:{i}", BANKS[self.bank as usize]))
            .collect()
    }
    pub(crate) fn parse(name: &str) -> Option<Self> {
        let names = [
            ["AL", "AX", "EAX", "RAX"],
            ["CL", "CX", "ECX", "RCX"],
            ["DL", "DX", "EDX", "RDX"],
            ["BL", "BX", "EBX", "RBX"],
            ["SPL", "SP", "ESP", "RSP"],
            ["BPL", "BP", "EBP", "RBP"],
            ["SIL", "SI", "ESI", "RSI"],
            ["DIL", "DI", "EDI", "RDI"],
        ];
        for (bank, row) in names.iter().enumerate() {
            if let Some(i) = row.iter().position(|n| *n == name) {
                return Self::new(bank as u8, 0, [8, 16, 32, 64][i]);
            }
        }
        if let Some(i) = ["AH", "CH", "DH", "BH"].iter().position(|n| *n == name) {
            return Self::new(i as u8, 8, 8);
        }
        for bank in 8..16 {
            for (suffix, width) in [("B", 8), ("W", 16), ("D", 32), ("", 64)] {
                if name == format!("R{bank}{suffix}") {
                    return Self::new(bank, 0, width);
                }
            }
        }
        None
    }
}
