//! Retain address expressions from typed BIL, independently of effect transfer.
use crate::ast::{Expr, Stmt, Var};
use ariadne::{
    LocationSet,
    effects::{AddressExpression, AddressTerm, MemoryAccessEvidence, MemoryAccessRole},
};
use std::collections::BTreeMap;
const BANKS: [&str; 16] = [
    "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12", "R13",
    "R14", "R15",
];
#[derive(Clone)]
struct Value {
    affine: Option<AddressExpression>,
    width: usize,
    inputs: LocationSet,
    gaps: Vec<String>,
}
impl Value {
    fn unknown(width: usize, reason: &str) -> Self {
        Self {
            affine: None,
            width,
            inputs: Default::default(),
            gaps: vec![reason.into()],
        }
    }
    fn affine(expression: AddressExpression, width: usize) -> Self {
        let inputs = expression.locations();
        Self {
            affine: Some(expression),
            width,
            inputs,
            gaps: Vec::new(),
        }
    }
}
struct Walker {
    env: BTreeMap<String, Value>,
    accesses: Vec<MemoryAccessEvidence>,
    va: u64,
    nodes: usize,
}
impl Walker {
    fn initial(&self, v: &Var) -> Value {
        if v.name == "RIP" && !v.virtual_ && v.width == 64 {
            return Value::affine(
                AddressExpression {
                    width: 64,
                    terms: Vec::new(),
                    constant: self.va,
                },
                64,
            );
        }
        if !v.virtual_
            && v.width == 64
            && let Some(bank) = BANKS.iter().position(|n| *n == v.name)
        {
            return Value::affine(
                AddressExpression {
                    width: 64,
                    terms: vec![AddressTerm {
                        bank: bank as u8,
                        coefficient: 1,
                    }],
                    constant: 0,
                },
                64,
            );
        }
        Value::unknown(v.width, "unsupported-address-variable")
    }
    fn access(&mut self, role: MemoryAccessRole, width: usize, v: &Value, path: &str) {
        let expression = v
            .affine
            .as_ref()
            .filter(|e| v.width == 64 && e.validate())
            .cloned();
        let mut gaps = v.gaps.clone();
        if expression.is_none() && gaps.is_empty() {
            gaps.push("unsupported-address-expression".into());
        }
        self.accesses.push(MemoryAccessEvidence {
            index: self.accesses.len(),
            role,
            access_width: width as u16,
            address_width: v.width as u16,
            expression,
            address_inputs: v.inputs.clone(),
            attribution: path.into(),
            gaps,
        });
    }
    fn eval(&mut self, e: &Expr, path: &str, depth: usize) -> Value {
        self.nodes += 1;
        if depth > 64 || self.nodes > 8192 {
            return Value::unknown(0, "address-expression-budget");
        }
        match e {
            Expr::Var { var } => self
                .env
                .get(&var.key())
                .cloned()
                .unwrap_or_else(|| self.initial(var)),
            Expr::Int { value } => {
                let parsed = value.split_once(':').and_then(|(n, w)| {
                    let width = w.trim_end_matches(['u', 's']).parse::<usize>().ok()?;
                    let value = if let Some(h) = n.strip_prefix("0x") {
                        u64::from_str_radix(h, 16).ok()?
                    } else {
                        n.parse::<i64>().ok()? as u64
                    };
                    Some((value, width))
                });
                if let Some((n, width)) = parsed.filter(|(_, w)| *w > 0 && *w <= 64) {
                    Value::affine(
                        AddressExpression {
                            width: 64,
                            terms: Vec::new(),
                            constant: n,
                        },
                        width,
                    )
                } else {
                    Value::unknown(0, "unsupported-address-integer")
                }
            }
            Expr::Binop { op, lhs, rhs } => {
                let l = self.eval(lhs, &format!("{path}.lhs"), depth + 1);
                let r = self.eval(rhs, &format!("{path}.rhs"), depth + 1);
                let inputs = l.inputs.union(&r.inputs).cloned().collect();
                let mut gaps = l.gaps.clone();
                gaps.extend(r.gaps.clone());
                if l.width != r.width {
                    return Value {
                        affine: None,
                        width: l.width,
                        inputs,
                        gaps: vec!["address-width-mismatch".into()],
                    };
                }
                let affine = match (&l.affine, &r.affine, *op) {
                    (Some(a), Some(b), 18 | 17) => {
                        let minus = *op == 17;
                        let mut terms: BTreeMap<u8, u64> =
                            a.terms.iter().map(|t| (t.bank, t.coefficient)).collect();
                        for t in &b.terms {
                            let coefficient = if minus {
                                t.coefficient.wrapping_neg()
                            } else {
                                t.coefficient
                            };
                            terms
                                .entry(t.bank)
                                .and_modify(|c| *c = c.wrapping_add(coefficient))
                                .or_insert(coefficient);
                        }
                        Some(AddressExpression {
                            width: 64,
                            terms: terms
                                .into_iter()
                                .filter(|(_, c)| *c != 0)
                                .map(|(bank, coefficient)| AddressTerm { bank, coefficient })
                                .collect(),
                            constant: if minus {
                                a.constant.wrapping_sub(b.constant)
                            } else {
                                a.constant.wrapping_add(b.constant)
                            },
                        })
                    }
                    (Some(a), Some(b), 16) if a.terms.is_empty() || b.terms.is_empty() => {
                        let (source, n) = if a.terms.is_empty() {
                            (b, a.constant)
                        } else {
                            (a, b.constant)
                        };
                        Some(AddressExpression {
                            width: 64,
                            terms: source
                                .terms
                                .iter()
                                .filter_map(|t| {
                                    let coefficient = t.coefficient.wrapping_mul(n);
                                    (coefficient != 0).then_some(AddressTerm {
                                        bank: t.bank,
                                        coefficient,
                                    })
                                })
                                .collect(),
                            constant: source.constant.wrapping_mul(n),
                        })
                    }
                    (Some(a), Some(b), 11) if b.terms.is_empty() && b.constant < 64 => {
                        let n = 1u64 << b.constant;
                        Some(AddressExpression {
                            width: 64,
                            terms: a
                                .terms
                                .iter()
                                .map(|t| AddressTerm {
                                    bank: t.bank,
                                    coefficient: t.coefficient.wrapping_mul(n),
                                })
                                .filter(|t| t.coefficient != 0)
                                .collect(),
                            constant: a.constant.wrapping_mul(n),
                        })
                    }
                    _ => None,
                };
                if affine.is_none() {
                    gaps.push("non-affine-address-operation".into());
                }
                Value {
                    affine,
                    width: l.width,
                    inputs,
                    gaps,
                }
            }
            Expr::Load { width, mem, addr } => {
                self.eval(mem, &format!("{path}.memory"), depth + 1);
                let address = self.eval(addr, &format!("{path}.address"), depth + 1);
                self.access(MemoryAccessRole::Load, *width, &address, path);
                let mut v = Value::unknown(*width, "address-depends-on-loaded-value");
                v.inputs = address.inputs;
                v.inputs.insert("memory:any".into());
                v
            }
            Expr::Store {
                width,
                mem,
                addr,
                value,
            } => {
                self.eval(mem, &format!("{path}.memory"), depth + 1);
                let address = self.eval(addr, &format!("{path}.address"), depth + 1);
                self.eval(value, &format!("{path}.payload"), depth + 1);
                self.access(MemoryAccessRole::Store, *width, &address, path);
                Value::unknown(0, "memory-value")
            }
            Expr::Let { var, value, body } => {
                let v = self.eval(value, &format!("{path}.binding"), depth + 1);
                let old = self.env.insert(var.key(), v);
                let result = self.eval(body, &format!("{path}.body"), depth + 1);
                if let Some(old) = old {
                    self.env.insert(var.key(), old);
                } else {
                    self.env.remove(&var.key());
                }
                result
            }
            Expr::Cast { op, width, arg } => {
                let mut v = self.eval(arg, &format!("{path}.cast"), depth + 1);
                if v.width != *width || ![0, 3].contains(op) {
                    v.affine = None;
                    v.gaps.push("unsupported-address-cast".into());
                }
                v.width = *width;
                v
            }
            Expr::Extract { hi, lo, arg } => {
                let mut v = self.eval(arg, &format!("{path}.extract"), depth + 1);
                if *lo != 0 || *hi + 1 != v.width {
                    v.affine = None;
                    v.gaps.push("unsupported-address-extraction".into());
                }
                v.width = hi - lo + 1;
                v
            }
            Expr::Ite { condition, yes, no } => {
                self.eval(condition, &format!("{path}.condition"), depth + 1);
                let a = self.eval(yes, &format!("{path}.yes"), depth + 1);
                let b = self.eval(no, &format!("{path}.no"), depth + 1);
                Value {
                    affine: None,
                    width: a.width,
                    inputs: a.inputs.union(&b.inputs).cloned().collect(),
                    gaps: vec!["conditional-address-expression".into()],
                }
            }
            Expr::Concat { lhs, rhs } => {
                let a = self.eval(lhs, &format!("{path}.high"), depth + 1);
                let b = self.eval(rhs, &format!("{path}.low"), depth + 1);
                Value {
                    affine: None,
                    width: a.width + b.width,
                    inputs: a.inputs.union(&b.inputs).cloned().collect(),
                    gaps: vec!["concatenated-address-expression".into()],
                }
            }
            Expr::Unop { arg, .. } => {
                let mut v = self.eval(arg, &format!("{path}.unary"), depth + 1);
                v.affine = None;
                v.gaps.push("unsupported-address-unary".into());
                v
            }
            _ => Value::unknown(0, "unknown-address-expression"),
        }
    }
    fn statements(&mut self, s: &[Stmt], path: &str, depth: usize) {
        if depth > 32 {
            return;
        }
        for (n, stmt) in s.iter().enumerate() {
            let path = format!("{path}.{n}");
            match stmt {
                Stmt::Move { var, value } => {
                    let v = self.eval(value, &format!("{path}.value"), 0);
                    self.env.insert(var.key(), v);
                }
                Stmt::Jump { target } => {
                    self.eval(target, &format!("{path}.target"), 0);
                }
                Stmt::If { condition, yes, no } => {
                    self.eval(condition, &format!("{path}.condition"), 0);
                    let env = self.env.clone();
                    let start = self.accesses.len();
                    self.statements(yes, &format!("{path}.yes"), depth + 1);
                    self.env = env.clone();
                    self.statements(no, &format!("{path}.no"), depth + 1);
                    self.env = env;
                    for a in &mut self.accesses[start..] {
                        a.gaps.push("conditional-memory-access".into());
                    }
                }
                _ => {}
            }
        }
    }
}
pub(crate) fn extract(statements: &[Stmt], va: u64) -> Vec<MemoryAccessEvidence> {
    let mut w = Walker {
        env: BTreeMap::new(),
        accesses: Vec::new(),
        va,
        nodes: 0,
    };
    w.statements(statements, "bil", 0);
    w.accesses
}
