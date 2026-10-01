//! Bounded address-use facts from an admitted instruction lift.
use super::RegisterView;
use crate::LocationSet;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MemoryAccessRole {
    Load,
    Store,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AddressTerm {
    pub bank: u8,
    pub coefficient: u64,
}
/// Modular affine expression over before-instruction 64-bit GPR values.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AddressExpression {
    pub width: u16,
    pub terms: Vec<AddressTerm>,
    pub constant: u64,
}
impl AddressExpression {
    pub fn validate(&self) -> bool {
        self.width == 64
            && self.terms.len() <= 16
            && self.terms.iter().all(|t| t.bank < 16 && t.coefficient != 0)
            && self.terms.windows(2).all(|w| w[0].bank < w[1].bank)
    }
    pub fn locations(&self) -> LocationSet {
        self.terms
            .iter()
            .flat_map(|t| RegisterView::new(t.bank, 0, 64).unwrap().reads())
            .collect()
    }
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MemoryAccessEvidence {
    pub index: usize,
    pub role: MemoryAccessRole,
    pub access_width: u16,
    pub address_width: u16,
    pub expression: Option<AddressExpression>,
    pub address_inputs: LocationSet,
    pub attribution: String,
    pub gaps: Vec<String>,
}
