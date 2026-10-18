//! Question-only finite bit projection of the existing normalized target terms.
//! Memory reads and unsupported expressions stay unknown; this is not stateflow.
use super::{Term, TermKind, Transfer, mask};
use std::collections::BTreeMap;
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) struct Bits {
    pub width: u8,
    pub known: u64,
    pub value: u64,
}
impl Bits {
    pub(crate) fn top(width: u8) -> Self {
        Self {
            width,
            known: 0,
            value: 0,
        }
    }
    pub(crate) fn exact(width: u8, value: u64) -> Self {
        Self {
            width,
            known: mask(width),
            value: value & mask(width),
        }
    }
    pub(crate) fn number(self) -> Option<u64> {
        (self.known == mask(self.width)).then_some(self.value)
    }
    pub(crate) fn meet(self, known: u64, value: u64) -> Option<Self> {
        if (self.value ^ value) & self.known & known != 0 {
            return None;
        }
        Some(Self {
            width: self.width,
            known: (self.known | known) & mask(self.width),
            value: (self.value | value) & mask(self.width),
        })
    }
    pub(crate) fn join(self, other: Self) -> Self {
        if self.width != other.width {
            return Self::top(self.width.max(other.width));
        }
        let known = self.known & other.known & !(self.value ^ other.value);
        Self {
            width: self.width,
            known,
            value: self.value & known,
        }
    }
}
pub(crate) type Environment = BTreeMap<String, Bits>;
pub(crate) fn bank_name(bank: u8) -> String {
    super::BANKS[bank as usize].to_owned()
}
fn physical(key: &str) -> Option<&str> {
    let name = key.split(':').next()?;
    (key.ends_with(":false") && (super::BANKS.contains(&name) || ["CF", "ZF"].contains(&name)))
        .then_some(name)
}
fn eval(
    t: &Term,
    env: &Environment,
    left: &mut u64,
    depth: usize,
    depth_limit: usize,
) -> Option<Bits> {
    if !(1..=64).contains(&t.width) {
        return Some(Bits::top(64));
    }
    if *left == 0 || depth >= depth_limit {
        return None;
    }
    *left -= 1;
    let next = |x: &Term, left: &mut u64| eval(x, env, left, depth + 1, depth_limit);
    let result = match &t.kind {
        TermKind::Constant { .. } => Bits::exact(t.width, t.number()?),
        TermKind::Input { key } => physical(key)
            .and_then(|n| env.get(n).copied())
            .filter(|v| v.width == t.width)
            .unwrap_or(Bits::top(t.width)),
        TermKind::Unknown | TermKind::Load { .. } => Bits::top(t.width),
        TermKind::Unary { op, arg } => {
            let a = next(arg, left)?;
            if *op == 0 {
                Bits {
                    width: t.width,
                    known: a.known,
                    value: !a.value & a.known,
                }
            } else if let Some(n) = a.number() {
                Bits::exact(
                    t.width,
                    Term::unary(*op, Term::constant(n, arg.width)).number()?,
                )
            } else {
                Bits::top(t.width)
            }
        }
        TermKind::Binary {
            op,
            left: a,
            right: b,
        } => {
            let a = next(a, left)?;
            let b = next(b, left)?;
            if let (Some(x), Some(y)) = (a.number(), b.number()) {
                Bits::exact(
                    t.width,
                    Term::binary(*op, Term::constant(x, a.width), Term::constant(y, b.width))
                        .number()?,
                )
            } else {
                match *op {
                    6 => {
                        let known = a.known & b.known;
                        Bits {
                            width: t.width,
                            known,
                            value: (a.value ^ b.value) & known,
                        }
                    }
                    7 => {
                        let ones = (a.value & a.known) | (b.value & b.known);
                        let zeros = (a.known & !a.value) & (b.known & !b.value);
                        Bits {
                            width: t.width,
                            known: ones | zeros,
                            value: ones,
                        }
                    }
                    8 => {
                        let zeros = (a.known & !a.value) | (b.known & !b.value);
                        let ones = a.known & a.value & b.known & b.value;
                        Bits {
                            width: t.width,
                            known: zeros | ones,
                            value: ones,
                        }
                    }
                    4 | 5 if (a.value ^ b.value) & a.known & b.known != 0 => {
                        Bits::exact(1, u64::from(*op == 4))
                    }
                    _ => Bits::top(t.width),
                }
            }
        }
        TermKind::Cast { op, arg } => {
            let a = next(arg, left)?;
            if let Some(v) = a.number() {
                Bits::exact(
                    t.width,
                    Term::cast(*op, t.width, Term::constant(v, arg.width)).number()?,
                )
            } else {
                match *op {
                    0 => Bits {
                        width: t.width,
                        known: a.known & mask(t.width),
                        value: a.value & mask(t.width),
                    },
                    1 if t.width <= a.width => Bits {
                        width: t.width,
                        known: a.known >> (a.width - t.width),
                        value: a.value >> (a.width - t.width),
                    },
                    3 if t.width >= a.width => Bits {
                        width: t.width,
                        known: a.known | (mask(t.width) & !mask(a.width)),
                        value: a.value,
                    },
                    _ => Bits::top(t.width),
                }
            }
        }
    };
    Some(result)
}
impl Transfer {
    pub(crate) fn question_target(
        &self,
        env: &Environment,
        work: &mut u64,
        depth_limit: usize,
    ) -> Option<Bits> {
        self.jump
            .as_ref()
            .and_then(|t| eval(t, env, work, 0, depth_limit))
    }
    pub(crate) fn question_condition(
        &self,
        env: &Environment,
        work: &mut u64,
        depth_limit: usize,
    ) -> Option<Bits> {
        self.condition
            .as_ref()
            .and_then(|t| eval(t, env, work, 0, depth_limit))
    }
    pub(crate) fn question_outputs(
        &self,
        env: &Environment,
        work: &mut u64,
        depth_limit: usize,
    ) -> Option<Environment> {
        let mut out = Environment::new();
        for (key, term) in &self.outputs {
            if let Some(name) = physical(key) {
                out.insert(name.to_owned(), eval(term, env, work, 0, depth_limit)?);
            }
        }
        Some(out)
    }
}

#[cfg(test)]
#[path = "../../../tests/bap/frame_question_bits.rs"]
mod tests;
