//! Bounded mathematical preimages. Machine admission is a separate obligation.
use super::{Error, invalid};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ScalarTransfer {
    Copy,
    Add {
        #[serde(with = "super::model::va")]
        value: u64,
    },
    Sub {
        #[serde(with = "super::model::va")]
        value: u64,
    },
    And {
        #[serde(with = "super::model::va")]
        mask: u64,
    },
    Constant {
        #[serde(with = "super::model::va")]
        value: u64,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum BackwardValue {
    Exact {
        width: u16,
        #[serde(with = "super::model::va")]
        value: u64,
    },
    Constrained {
        width: u16,
        /// Apply these bijections to a candidate before checking known bits.
        operations: Vec<ScalarTransfer>,
        #[serde(with = "super::model::va")]
        mask: u64,
        #[serde(with = "super::model::va")]
        value: u64,
    },
    Unknown {
        width: u16,
        reason: String,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BackwardStep {
    /// The later fact is retained even if its predecessor cannot be represented.
    pub after: BackwardValue,
    pub before: Option<BackwardValue>,
    pub boundary: Option<String>,
    pub conflict: bool,
}

fn word_mask(width: u16) -> Result<u64, Error> {
    if !(1..=64).contains(&width) {
        return Err(invalid("invalid scalar width"));
    }
    Ok(if width == 64 {
        u64::MAX
    } else {
        (1u64 << width) - 1
    })
}

impl ScalarTransfer {
    pub(crate) fn apply(&self, input: u64, width: u16) -> Result<u64, Error> {
        let bits = word_mask(width)?;
        let output = match self {
            Self::Copy => input,
            Self::Add { value } => input.wrapping_add(*value),
            Self::Sub { value } => input.wrapping_sub(*value),
            Self::And { mask } => input & mask,
            Self::Constant { value } => *value,
        };
        Ok(output & bits)
    }
}

impl BackwardValue {
    pub fn width(&self) -> u16 {
        match self {
            Self::Exact { width, .. }
            | Self::Constrained { width, .. }
            | Self::Unknown { width, .. } => *width,
        }
    }
    pub fn validate(&self) -> Result<(), Error> {
        let bits = word_mask(self.width())?;
        match self {
            Self::Exact { value, .. } if value & !bits != 0 => {
                Err(invalid("scalar value exceeds width"))
            }
            Self::Constrained {
                mask,
                value,
                operations,
                ..
            } => {
                if *mask == 0
                    || *mask == bits
                    || value & !mask != 0
                    || mask & !bits != 0
                    || operations.len() > 64
                    || operations.iter().any(|op| {
                        !matches!(op, ScalarTransfer::Add { .. } | ScalarTransfer::Sub { .. })
                    })
                {
                    return Err(invalid("invalid or noncanonical scalar constraint"));
                }
                Ok(())
            }
            Self::Unknown { reason, .. } if reason.is_empty() || reason.len() > 128 => {
                Err(invalid("invalid scalar unknown reason"))
            }
            _ => Ok(()),
        }
    }
    /// Predicate membership, useful to compare against an independent oracle.
    pub fn permits(&self, input: u64) -> Result<bool, Error> {
        self.validate()?;
        if input & !word_mask(self.width())? != 0 {
            return Ok(false);
        }
        match self {
            Self::Exact { value, .. } => Ok(input == *value),
            Self::Unknown { .. } => Ok(true),
            Self::Constrained {
                width,
                operations,
                mask,
                value,
            } => {
                let mut current = input;
                for op in operations {
                    current = op.apply(current, *width)?;
                }
                Ok(current & mask == *value)
            }
        }
    }
}

/// Compute a conservative preimage with explicit conflict/information barriers.
pub fn backward_preimage(
    after: &BackwardValue,
    transfer: &ScalarTransfer,
) -> Result<BackwardStep, Error> {
    after.validate()?;
    let width = after.width();
    let bits = word_mask(width)?;
    let mut result = BackwardStep {
        after: after.clone(),
        before: None,
        boundary: None,
        conflict: false,
    };
    if matches!(after, BackwardValue::Unknown { .. }) {
        result.before = Some(after.clone());
        result.boundary = Some("no-useful-numerical-constraint".into());
        return Ok(result);
    }
    match transfer {
        ScalarTransfer::Copy => result.before = Some(after.clone()),
        ScalarTransfer::Constant { value } => {
            if !after.permits(value & bits)? {
                result.conflict = true;
                result.boundary = Some("inconsistent-predecessor-constraints".into());
            } else {
                result.before = Some(BackwardValue::Unknown {
                    width,
                    reason: "information-erasure".into(),
                });
                result.boundary = Some("information-erasure".into());
            }
        }
        ScalarTransfer::Add { value } | ScalarTransfer::Sub { value } => {
            if let BackwardValue::Exact { value: known, .. } = after {
                let value = if matches!(transfer, ScalarTransfer::Add { .. }) {
                    known.wrapping_sub(*value)
                } else {
                    known.wrapping_add(*value)
                } & bits;
                result.before = Some(BackwardValue::Exact { width, value });
            } else if let BackwardValue::Constrained {
                operations,
                mask,
                value: known,
                ..
            } = after
            {
                if operations.len() == 64 {
                    result.boundary = Some("constraint-expression-budget".into());
                } else {
                    let mut next = vec![transfer.clone()];
                    next.extend(operations.clone());
                    result.before = Some(BackwardValue::Constrained {
                        width,
                        operations: next,
                        mask: *mask,
                        value: *known,
                    });
                }
            }
        }
        ScalarTransfer::And { mask: operand } => {
            let operand = operand & bits;
            if operand == bits {
                result.before = Some(after.clone());
            } else {
                let known = match after {
                    BackwardValue::Exact { value, .. } => Some((bits, *value)),
                    BackwardValue::Constrained {
                        operations,
                        mask,
                        value,
                        ..
                    } if operations.is_empty() => Some((*mask, *value)),
                    _ => None,
                };
                if let Some((known_mask, value)) = known {
                    let mask = known_mask & operand;
                    if value & !mask != 0 {
                        result.conflict = true;
                        result.boundary = Some("inconsistent-predecessor-constraints".into());
                    } else if mask == 0 {
                        result.before = Some(BackwardValue::Unknown {
                            width,
                            reason: "information-erasure".into(),
                        });
                        result.boundary = Some("information-erasure".into());
                    } else {
                        result.before = Some(BackwardValue::Constrained {
                            width,
                            operations: Vec::new(),
                            mask,
                            value,
                        });
                    }
                } else {
                    result.boundary = Some("unsupported-constraint-composition".into());
                }
            }
        }
    }
    if let Some(value) = &result.before {
        value.validate()?;
    }
    Ok(result)
}
