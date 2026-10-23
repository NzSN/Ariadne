//! Optional normalized transfer evidence from the already admitted BIL.
use super::ast::{Expr, Lift, Stmt, Var};
use crate::investigation::{ScalarTransfer, SiteEvidence};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub(crate) const PROFILE: &str = "bap-memory-refinement-v1";
pub(crate) const ADVANCED_PROFILE: &str = "bap-memory-refinement-v2";
const BANKS: [&str; 16] = [
    "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12", "R13",
    "R14", "R15",
];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum TransferExpression {
    Input {
        bank: u8,
    },
    Constant {
        #[serde(with = "crate::investigation::model::va")]
        value: u64,
    },
    Apply {
        operation: ScalarTransfer,
        input: Box<TransferExpression>,
    },
    Unsupported {
        reason: String,
    },
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct TransferReceipt {
    pub profile: String,
    #[serde(with = "crate::investigation::model::va")]
    pub site: u64,
    pub bytes_hex: String,
    pub ast_sha256: String,
    pub ast: String,
    pub outputs: BTreeMap<u8, TransferExpression>,
    pub memory_footprint_complete: bool,
}
#[derive(Clone)]
struct Term {
    width: usize,
    value: TransferExpression,
}
fn unknown(reason: &str) -> Term {
    Term {
        width: 64,
        value: TransferExpression::Unsupported {
            reason: reason.into(),
        },
    }
}
fn bank(v: &Var) -> Option<u8> {
    if !v.virtual_ && v.width == 64 && v.type_ == "imm" {
        BANKS.iter().position(|n| *n == v.name).map(|n| n as u8)
    } else {
        None
    }
}
fn constant(t: &Term) -> Option<u64> {
    match &t.value {
        TransferExpression::Constant { value } => Some(*value),
        _ => None,
    }
}
fn mask(w: usize) -> u64 {
    if w == 64 { u64::MAX } else { (1u64 << w) - 1 }
}
fn eval(e: &Expr, env: &mut BTreeMap<String, Term>, va: u64, depth: usize) -> Term {
    if depth > 64 {
        return unknown("transfer-expression-budget");
    }
    match e {
        Expr::Var { var } => env.get(&var.key()).cloned().unwrap_or_else(|| {
            if let Some(bank) = bank(var) {
                Term {
                    width: 64,
                    value: TransferExpression::Input { bank },
                }
            } else if !var.virtual_ && var.name == "RIP" && var.width == 64 {
                Term {
                    width: 64,
                    value: TransferExpression::Constant { value: va },
                }
            } else {
                unknown("unavailable-transfer-input")
            }
        }),
        Expr::Int { value } => {
            let parsed = value.split_once(':').and_then(|(n, w)| {
                let width = w.trim_end_matches(['u', 's']).parse::<usize>().ok()?;
                if !(1..=64).contains(&width) {
                    return None;
                }
                let value = if let Some(h) = n.strip_prefix("0x") {
                    u64::from_str_radix(h, 16).ok()?
                } else {
                    n.parse::<i64>().ok()? as u64
                };
                Some(Term {
                    width,
                    value: TransferExpression::Constant {
                        value: value & mask(width),
                    },
                })
            });
            parsed.unwrap_or_else(|| unknown("unsupported-transfer-integer"))
        }
        Expr::Cast { op, width, arg } => {
            let input = eval(arg, env, va, depth + 1);
            if !(1..=64).contains(width) {
                return unknown("unsupported-transfer-width");
            }
            if let Some(value) = constant(&input) {
                let result = match op {
                    0 if *width <= input.width => value & mask(*width),
                    1 if *width <= input.width => value >> (input.width - width),
                    2 if *width >= input.width => {
                        if value & (1u64 << (input.width - 1)) != 0 {
                            value | !mask(input.width)
                        } else {
                            value
                        }
                    }
                    3 if *width >= input.width => value,
                    _ => return unknown("unsupported-transfer-cast"),
                };
                Term {
                    width: *width,
                    value: TransferExpression::Constant {
                        value: result & mask(*width),
                    },
                }
            } else if input.width == *width {
                input
            } else {
                unknown("partial-register-transfer")
            }
        }
        Expr::Binop { op, lhs, rhs } => {
            let left = eval(lhs, env, va, depth + 1);
            let right = eval(rhs, env, va, depth + 1);
            if left.width != right.width || left.width != 64 {
                return unknown("unsupported-transfer-width");
            }
            if *op == 6
                && left.value == right.value
                && !matches!(left.value, TransferExpression::Unsupported { .. })
            {
                return Term {
                    width: 64,
                    value: TransferExpression::Constant { value: 0 },
                };
            }
            if let (Some(a), Some(b)) = (constant(&left), constant(&right)) {
                let value = match op {
                    18 => a.wrapping_add(b),
                    17 => a.wrapping_sub(b),
                    8 => a & b,
                    6 => a ^ b,
                    _ => return unknown("unsupported-transfer-operation"),
                };
                return Term {
                    width: 64,
                    value: TransferExpression::Constant { value },
                };
            }
            let (input, operation) = match (*op, constant(&left), constant(&right)) {
                (18, _, Some(value)) => (left, ScalarTransfer::Add { value }),
                (18, Some(value), _) => (right, ScalarTransfer::Add { value }),
                (17, _, Some(value)) => (left, ScalarTransfer::Sub { value }),
                (8, _, Some(mask)) => (left, ScalarTransfer::And { mask }),
                (8, Some(mask), _) => (right, ScalarTransfer::And { mask }),
                _ => return unknown("unsupported-transfer-operation"),
            };
            Term {
                width: 64,
                value: TransferExpression::Apply {
                    operation,
                    input: Box::new(input.value),
                },
            }
        }
        Expr::Let { var, value, body } => {
            let value = eval(value, env, va, depth + 1);
            let prior = env.insert(var.key(), value);
            let result = eval(body, env, va, depth + 1);
            if let Some(v) = prior {
                env.insert(var.key(), v);
            } else {
                env.remove(&var.key());
            }
            result
        }
        Expr::Load { .. } => unknown("memory-history-unavailable"),
        Expr::Unknown { .. } => unknown("unknown-output"),
        _ => unknown("unsupported-transfer-expression"),
    }
}

pub(crate) fn extract(
    bil: &[Stmt],
    site: u64,
    bytes_hex: String,
) -> Result<TransferReceipt, super::Error> {
    extract_with_profile(bil, site, bytes_hex, super::PROJECTION)
}
pub(crate) fn extract_with_profile(
    bil: &[Stmt],
    site: u64,
    bytes_hex: String,
    producer: &str,
) -> Result<TransferReceipt, super::Error> {
    let ast = serde_json::to_string(bil)?;
    if ast.len() > 1024 * 1024 {
        return Err(super::invalid("refinement AST byte limit"));
    }
    let mut env = BTreeMap::new();
    let mut outputs = BTreeMap::new();
    let straight = bil.iter().all(|s| matches!(s, Stmt::Move { .. }));
    if straight {
        for stmt in bil {
            if let Stmt::Move { var, value } = stmt {
                let mut term = eval(value, &mut env, site, 0);
                let mut depth = 0;
                let mut expression = &term.value;
                while let TransferExpression::Apply { input, .. } = expression {
                    depth += 1;
                    expression = input;
                }
                if depth > 64 {
                    term = unknown("transfer-expression-budget");
                }
                if let Some(bank) = bank(var) {
                    outputs.insert(
                        bank,
                        if term.width == 64 {
                            term.value.clone()
                        } else {
                            unknown("partial-register-transfer").value
                        },
                    );
                }
                env.insert(var.key(), term);
            }
        }
    }
    let accesses = super::address::extract(bil, site);
    let memory_footprint_complete = straight
        && accesses
            .iter()
            .all(|a| a.gaps.is_empty() && a.expression.is_some());
    Ok(TransferReceipt {
        profile: if super::advanced_projection(producer) {
            ADVANCED_PROFILE
        } else {
            PROFILE
        }
        .into(),
        site,
        bytes_hex,
        ast_sha256: crate::reports::sha256(ast.as_bytes()),
        ast,
        outputs,
        memory_footprint_complete,
    })
}
impl TransferReceipt {
    pub(crate) fn validate(&self, site: &SiteEvidence) -> Result<(), super::Error> {
        if self.profile
            != if site
                .projection
                .as_deref()
                .is_some_and(super::advanced_projection)
            {
                ADVANCED_PROFILE
            } else {
                PROFILE
            }
            || site
                .projection
                .as_deref()
                .is_some_and(super::ordinary_only_projection)
            || self.site != site.va
            || self.bytes_hex != site.bytes_hex
            || site.semantic_status.as_deref() != Some("projected")
            || site.quality != "external_lift"
            || !site
                .projection
                .as_deref()
                .is_some_and(super::known_projection)
            || !site.captured
            || site.ast_sha256.as_deref() != Some(self.ast_sha256.as_str())
            || crate::reports::sha256(self.ast.as_bytes()) != self.ast_sha256
            || self.ast.len() > 1024 * 1024
        {
            return Err(super::invalid("refinement receipt identity mismatch"));
        }
        let bil: Vec<Stmt> = serde_json::from_str(&self.ast)?;
        let fake = Lift {
            schema: String::new(),
            batch: 0,
            snapshot: String::new(),
            va: format!("0x{:016x}", self.site),
            status: "decoded".into(),
            length: 0,
            bytes: self.bytes_hex.clone(),
            opcode: site.opcode.clone(),
            properties: None,
            bil: bil.clone(),
        };
        fake.validate_ast()?;
        let bytes = (0..self.bytes_hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&self.bytes_hex[i..i + 2], 16))
            .collect::<Result<Vec<_>, _>>()?;
        let producer = site.projection.as_deref().unwrap_or("");
        super::admission::admit_with_profile(
            &bil,
            site.opcode.as_deref().unwrap_or(""),
            &bytes,
            producer,
        )?;
        if extract_with_profile(&bil, self.site, self.bytes_hex.clone(), producer)? != *self {
            return Err(super::invalid("refinement receipt recomputation mismatch"));
        }
        let accesses: Vec<_> = super::address::extract(&bil, self.site)
            .iter()
            .map(crate::investigation::AddressUse::from)
            .collect();
        if accesses != site.accesses {
            return Err(super::invalid("refinement receipt access mismatch"));
        }
        Ok(())
    }
}
