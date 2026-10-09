//! Typed producer admission; opcode spelling is not a generic permission gate.
use super::Error;
use super::ast::{Expr, Stmt, Var};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum FailureKind {
    Malformed,
    UnsupportedData,
    UnsupportedControl,
    Resource,
}
#[derive(Debug)]
pub(crate) struct Failure {
    pub kind: FailureKind,
    pub reason: String,
}
impl std::fmt::Display for Failure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.reason)
    }
}
impl std::error::Error for Failure {}
pub(crate) fn failure(kind: FailureKind, reason: impl Into<String>) -> Error {
    Box::new(Failure {
        kind,
        reason: reason.into(),
    })
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Type {
    Bits(usize),
    Memory,
    Unknown,
}
#[derive(Default)]
struct Check {
    env: BTreeMap<String, Type>,
    unsupported_data: bool,
    control: bool,
    nodes: usize,
}
pub(crate) struct Capabilities {
    pub ordinary_data_only: bool,
    pub unsupported_data: bool,
}
fn malformed(reason: &str) -> Error {
    failure(FailureKind::Malformed, reason)
}
fn scalar(t: Type) -> Result<Option<usize>, Error> {
    match t {
        Type::Bits(w) => Ok(Some(w)),
        Type::Unknown => Ok(None),
        Type::Memory => Err(malformed("memory used as scalar")),
    }
}
fn same(lhs: Type, rhs: Type) -> Result<Type, Error> {
    if lhs == Type::Unknown {
        return Ok(rhs);
    }
    if rhs == Type::Unknown {
        return Ok(lhs);
    }
    if lhs != rhs {
        return Err(malformed("BIL operand type/width mismatch"));
    }
    Ok(lhs)
}
fn var_type(v: &Var) -> Result<Type, Error> {
    if v.name.is_empty() || v.name.len() > 128 || v.index < 0 {
        return Err(malformed("invalid BIL variable identity"));
    }
    let ty = match v.type_.as_str() {
        "imm" if (1..=256).contains(&v.width) => Type::Bits(v.width),
        "mem" if v.width == 0 => Type::Memory,
        _ => return Err(malformed("invalid BIL variable type/width")),
    };
    if !v.virtual_ {
        let bank = [
            "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11",
            "R12", "R13", "R14", "R15", "RIP",
        ]
        .contains(&v.name.as_str());
        let flag = ["CF", "PF", "AF", "ZF", "SF", "OF", "DF"].contains(&v.name.as_str());
        if v.index != 0
            || !(bank && ty == Type::Bits(64)
                || flag && ty == Type::Bits(1)
                || v.name == "mem" && ty == Type::Memory)
        {
            return Err(failure(
                FailureKind::UnsupportedControl,
                format!("unmodeled architectural namespace/type: {}", v.name),
            ));
        }
    }
    Ok(ty)
}
fn integer_type(value: &str) -> Result<Type, Error> {
    let (number, width) = value
        .split_once(':')
        .ok_or_else(|| malformed("BIL integer missing width"))?;
    let width = width
        .strip_suffix('u')
        .or_else(|| width.strip_suffix('s'))
        .unwrap_or(width)
        .parse::<usize>()
        .map_err(|_| malformed("BIL integer width"))?;
    if !(1..=256).contains(&width) || number.is_empty() {
        return Err(malformed("BIL integer width/value"));
    }
    if let Some(hex) = number.strip_prefix("0x") {
        if hex.is_empty() || !hex.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(malformed("BIL integer hex"));
        }
        for (i, c) in hex.chars().rev().enumerate() {
            let n = c.to_digit(16).unwrap();
            for bit in 0..4 {
                if i * 4 + bit >= width && n & (1 << bit) != 0 {
                    return Err(malformed("BIL integer overflow"));
                }
            }
        }
    } else {
        let n = number
            .parse::<i128>()
            .map_err(|_| malformed("BIL integer value"))?;
        if width < 128
            && (n >= 0 && (n as u128) >= (1u128 << width) || n < 0 && n < -(1i128 << (width - 1)))
        {
            return Err(malformed("BIL integer overflow"));
        }
    }
    Ok(Type::Bits(width))
}
fn unknown_value(e: &Expr) -> bool {
    match e {
        Expr::Unknown { .. } | Expr::Unsupported => true,
        Expr::Load { mem, addr, .. } => unknown_value(mem) || unknown_value(addr),
        Expr::Store {
            mem, addr, value, ..
        } => unknown_value(mem) || unknown_value(addr) || unknown_value(value),
        Expr::Binop { lhs, rhs, .. } | Expr::Concat { lhs, rhs } => {
            unknown_value(lhs) || unknown_value(rhs)
        }
        Expr::Unop { arg, .. } | Expr::Cast { arg, .. } | Expr::Extract { arg, .. } => {
            unknown_value(arg)
        }
        Expr::Ite { condition, yes, no } => {
            unknown_value(condition) || unknown_value(yes) || unknown_value(no)
        }
        Expr::Let { value, body, .. } => unknown_value(value) || unknown_value(body),
        _ => false,
    }
}
impl Check {
    fn budget(&mut self, depth: usize) -> Result<(), Error> {
        self.nodes += 1;
        if depth > 64 || self.nodes > 8192 {
            return Err(failure(
                FailureKind::Resource,
                "BIL admission budget exceeded",
            ));
        }
        Ok(())
    }
    fn expr(&mut self, e: &Expr, depth: usize) -> Result<Type, Error> {
        self.budget(depth)?;
        Ok(match e {
            Expr::Var { var } => {
                let ty = var_type(var)?;
                if var.virtual_ {
                    let bound = *self
                        .env
                        .get(&var.key())
                        .ok_or_else(|| malformed("read before virtual definition"))?;
                    same(ty, bound)?;
                    bound
                } else {
                    ty
                }
            }
            Expr::Int { value } => integer_type(value)?,
            Expr::Unknown { .. } => Type::Unknown,
            Expr::Unsupported => {
                self.unsupported_data = true;
                Type::Unknown
            }
            Expr::Load { width, mem, addr } => {
                if !(1..=256).contains(width) {
                    return Err(malformed("BIL load width"));
                }
                if self.expr(mem, depth + 1)? != Type::Memory
                    || scalar(self.expr(addr, depth + 1)?)? != Some(64)
                {
                    return Err(malformed("BIL load memory/address type"));
                }
                if ![8, 16, 32, 64].contains(width) {
                    self.unsupported_data = true;
                }
                Type::Bits(*width)
            }
            Expr::Store {
                width,
                mem,
                addr,
                value,
            } => {
                if !(1..=256).contains(width) {
                    return Err(malformed("BIL store width"));
                }
                if self.expr(mem, depth + 1)? != Type::Memory
                    || scalar(self.expr(addr, depth + 1)?)? != Some(64)
                {
                    return Err(malformed("BIL store memory/address type"));
                }
                same(Type::Bits(*width), self.expr(value, depth + 1)?)?;
                if ![8, 16, 32, 64].contains(width) {
                    self.unsupported_data = true;
                }
                Type::Memory
            }
            Expr::Binop { op, lhs, rhs } => {
                let l = self.expr(lhs, depth + 1)?;
                let r = self.expr(rhs, depth + 1)?;
                scalar(l)?;
                scalar(r)?;
                let ty = same(l, r)?;
                if *op < 0 {
                    return Err(malformed("negative BIL operator"));
                }
                if *op > 18 {
                    self.unsupported_data = true;
                    Type::Unknown
                } else if *op <= 5 {
                    Type::Bits(1)
                } else {
                    ty
                }
            }
            Expr::Unop { op, arg } => {
                let t = self.expr(arg, depth + 1)?;
                scalar(t)?;
                if *op < 0 {
                    return Err(malformed("negative BIL unary operator"));
                }
                if *op > 1 {
                    self.unsupported_data = true;
                    Type::Unknown
                } else {
                    t
                }
            }
            Expr::Cast { op, width, arg } => {
                if !(1..=256).contains(width) {
                    return Err(malformed("BIL cast width"));
                }
                let source = scalar(self.expr(arg, depth + 1)?)?;
                if *op < 0 {
                    return Err(malformed("negative BIL cast operator"));
                }
                if *op > 3 {
                    self.unsupported_data = true;
                } else if let Some(source) = source {
                    if (*op < 2 && *width > source) || (*op >= 2 && *width < source) {
                        return Err(malformed("BIL cast mode/width mismatch"));
                    }
                }
                Type::Bits(*width)
            }
            Expr::Extract { hi, lo, arg } => {
                let width = scalar(self.expr(arg, depth + 1)?)?;
                if lo > hi || *hi >= 256 || width.is_some_and(|w| *hi >= w) {
                    return Err(malformed("BIL extraction range"));
                }
                Type::Bits(hi - lo + 1)
            }
            Expr::Concat { lhs, rhs } => {
                let l = scalar(self.expr(lhs, depth + 1)?)?;
                let r = scalar(self.expr(rhs, depth + 1)?)?;
                match (l, r) {
                    (Some(l), Some(r)) if l + r <= 256 => Type::Bits(l + r),
                    (Some(_), Some(_)) => return Err(malformed("BIL concatenation width")),
                    _ => {
                        self.unsupported_data = true;
                        Type::Unknown
                    }
                }
            }
            Expr::Ite { condition, yes, no } => {
                if scalar(self.expr(condition, depth + 1)?)?.is_some_and(|w| w != 1) {
                    return Err(malformed("BIL condition width"));
                }
                let y = self.expr(yes, depth + 1)?;
                let n = self.expr(no, depth + 1)?;
                same(y, n)?
            }
            Expr::Let { var, value, body } => {
                if !var.virtual_ {
                    return Err(malformed("architectural let binder"));
                }
                let ty = var_type(var)?;
                same(ty, self.expr(value, depth + 1)?)?;
                let key = var.key();
                let previous = self.env.insert(key.clone(), ty);
                let result = self.expr(body, depth + 1)?;
                if let Some(old) = previous {
                    self.env.insert(key, old);
                } else {
                    self.env.remove(&key);
                }
                result
            }
        })
    }
    fn statements(&mut self, statements: &[Stmt], depth: usize) -> Result<(), Error> {
        for s in statements {
            self.budget(depth)?;
            match s {
                Stmt::Move { var, value } => {
                    let ty = var_type(var)?;
                    if matches!(ty, Type::Bits(w) if w>1) && unknown_value(value) {
                        self.unsupported_data = true;
                    }
                    let value = self.expr(value, depth + 1)?;
                    same(ty, value)?;
                    if !var.virtual_ && var.name == "RIP" {
                        return Err(failure(
                            FailureKind::UnsupportedControl,
                            "architectural RIP assignment",
                        ));
                    }
                    // Unknown flags have the reviewed weak-output contract. Unknown
                    // scalar state has no reviewed footprint: retain all effects.
                    if value == Type::Unknown && ty != Type::Bits(1) {
                        self.unsupported_data = true;
                    }
                    self.env.insert(var.key(), ty);
                }
                Stmt::Jump { target } => {
                    if scalar(self.expr(target, depth + 1)?)? != Some(64) {
                        return Err(failure(
                            FailureKind::UnsupportedControl,
                            "unresolved BIL jump type",
                        ));
                    }
                    self.control = true;
                }
                Stmt::If { condition, yes, no } => {
                    if scalar(self.expr(condition, depth + 1)?)?.is_some_and(|w| w != 1) {
                        return Err(malformed("BIL condition width"));
                    }
                    let before = self.env.clone();
                    self.statements(yes, depth + 1)?;
                    let after_yes = self.env.clone();
                    self.env = before;
                    self.statements(no, depth + 1)?;
                    self.env.retain(|key, ty| after_yes.get(key) == Some(ty));
                }
                Stmt::While { .. } | Stmt::Exception { .. } | Stmt::Special | Stmt::Unsupported => {
                    return Err(failure(
                        FailureKind::UnsupportedControl,
                        "unmodeled BIL control/special/loop semantics",
                    ));
                }
            }
        }
        Ok(())
    }
}
pub(crate) fn guarded_prefix(bytes: &[u8]) -> bool {
    for byte in bytes {
        if [0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65, 0x67].contains(byte) {
            return true;
        }
        if *byte == 0x66 || (0x40..=0x4f).contains(byte) {
            continue;
        }
        break;
    }
    false
}
pub(crate) fn capabilities(statements: &[Stmt]) -> Result<Capabilities, Error> {
    let mut check = Check::default();
    check.statements(statements, 0)?;
    Ok(Capabilities {
        ordinary_data_only: !check.control,
        unsupported_data: check.unsupported_data,
    })
}
pub(crate) fn admit(statements: &[Stmt], opcode: &str, bytes: &[u8]) -> Result<(), Error> {
    if guarded_prefix(bytes) {
        return Err(failure(
            FailureKind::UnsupportedControl,
            "unmodeled instruction prefix",
        ));
    }
    if statements.is_empty() {
        if opcode == "NOOP" && bytes == [0x90] {
            return Ok(());
        }
        return Err(failure(
            FailureKind::UnsupportedControl,
            "empty lift is not an admitted no-op",
        ));
    }
    let capabilities = capabilities(statements)?;
    if capabilities.unsupported_data {
        return Err(failure(
            FailureKind::UnsupportedData,
            "unsupported typed BIL data capability",
        ));
    }
    Ok(())
}
pub(crate) fn ordinary_unknown(statements: &[Stmt], bytes: &[u8], error: &Error) -> bool {
    if guarded_prefix(bytes) || statements.is_empty() {
        return false;
    }
    error
        .downcast_ref::<Failure>()
        .is_some_and(|e| e.kind == FailureKind::UnsupportedData)
        && capabilities(statements).is_ok_and(|c| c.ordinary_data_only)
}
pub(crate) fn fatal(error: &Error) -> bool {
    error
        .downcast_ref::<Failure>()
        .is_none_or(|e| matches!(e.kind, FailureKind::Malformed | FailureKind::Resource))
}

/// Explicit destination role from already validated protocol-2 metadata.
/// This is operand binding, never an LLVM effect-rule fallback.
pub(crate) fn decoded_destination(
    e: &crate::effects::InstructionEvidence,
) -> Option<&crate::effects::RegisterView> {
    let fields: Vec<_> = e.decoder_record.as_deref()?.split_whitespace().collect();
    let operands = fields.get(2)?.parse::<usize>().ok()?;
    let definitions = fields.get(3 + operands)?.parse::<usize>().ok()?;
    if definitions == 0 {
        return None;
    }
    match e.operands.first()? {
        crate::effects::Operand::Register(r) => Some(r),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn v(name: &str, width: usize, virtual_: bool) -> Var {
        Var {
            name: name.into(),
            index: 0,
            virtual_,
            width,
            type_: "imm".into(),
        }
    }
    fn constant(width: usize) -> Expr {
        Expr::Int {
            value: format!("1:{width}u"),
        }
    }
    fn move_to(var: Var, value: Expr) -> Stmt {
        Stmt::Move { var, value }
    }
    #[test]
    fn capabilities_validate_composed_scalar_widths_and_virtual_bindings() {
        for width in [1, 8, 16, 32, 64, 128, 256] {
            let temp = v("temporary", width, true);
            let statements = vec![
                move_to(temp.clone(), constant(width)),
                move_to(
                    v("ZF", 1, false),
                    Expr::Binop {
                        op: 0,
                        lhs: Box::new(Expr::Var { var: temp }),
                        rhs: Box::new(constant(width)),
                    },
                ),
            ];
            let c = capabilities(&statements).unwrap();
            assert!(c.ordinary_data_only);
            assert!(!c.unsupported_data);
        }
        let memory = Var {
            name: "mem".into(),
            index: 0,
            virtual_: false,
            width: 0,
            type_: "mem".into(),
        };
        let load = Expr::Load {
            width: 8,
            mem: Box::new(Expr::Var {
                var: memory.clone(),
            }),
            addr: Box::new(Expr::Var {
                var: v("RBX", 64, false),
            }),
        };
        let store = Expr::Store {
            width: 8,
            mem: Box::new(Expr::Var {
                var: memory.clone(),
            }),
            addr: Box::new(Expr::Var {
                var: v("RCX", 64, false),
            }),
            value: Box::new(load),
        };
        assert!(
            !capabilities(&[move_to(memory, store)])
                .unwrap()
                .unsupported_data
        );
    }
    #[test]
    fn malformed_alternatives_cannot_hide_behind_unsupported_data_or_constant_conditions() {
        let wrong = move_to(v("RAX", 64, false), constant(32));
        let unsupported = move_to(v("RBX", 64, false), Expr::Unsupported);
        let inputs = [
            vec![wrong.clone()],
            vec![unsupported, wrong.clone()],
            vec![Stmt::If {
                condition: constant(1),
                yes: vec![],
                no: vec![wrong],
            }],
            vec![move_to(
                v("RAX", 64, false),
                Expr::Var {
                    var: v("unbound", 64, true),
                },
            )],
            vec![move_to(
                v("RAX", 64, false),
                Expr::Extract {
                    hi: 64,
                    lo: 0,
                    arg: Box::new(constant(64)),
                },
            )],
        ];
        for statements in inputs {
            let e = capabilities(&statements).err().unwrap();
            assert_eq!(
                e.downcast_ref::<Failure>().unwrap().kind,
                FailureKind::Malformed
            );
        }
    }
    #[test]
    fn ordinary_opaque_requires_known_namespace_and_no_control_construct() {
        let ordinary = [move_to(v("RAX", 64, false), Expr::Unsupported)];
        let e = admit(&ordinary, "descriptive-metadata", &[0x48, 0x89, 0xd8]).unwrap_err();
        assert!(ordinary_unknown(&ordinary, &[0x48, 0x89, 0xd8], &e));
        for special in [
            Stmt::Special,
            Stmt::Unsupported,
            Stmt::Exception { number: 0 },
            Stmt::While {
                condition: constant(1),
                body: vec![],
            },
            move_to(v("RIP", 64, false), constant(64)),
            move_to(v("YMM0", 256, false), constant(256)),
        ] {
            let statements = [special];
            let e = capabilities(&statements).err().unwrap();
            assert!(!ordinary_unknown(&statements, &[0x90], &e));
        }
        assert!(!ordinary_unknown(&ordinary, &[0x67, 0x90], &e));
        assert!(!ordinary_unknown(&[], &[0x90], &e));
        let jump = [
            ordinary[0].clone(),
            Stmt::Jump {
                target: constant(64),
            },
        ];
        assert!(!ordinary_unknown(&jump, &[0x90], &e));
    }
    #[test]
    fn admission_has_no_generic_opcode_membership_gate_but_preserves_prefix_and_empty_controls() {
        let statements = [move_to(v("CF", 1, false), constant(1))];
        assert!(admit(&statements, "new-instruction-description", &[0xf9]).is_ok());
        assert!(admit(&statements, "CALLER_DESCRIPTION_IS_NOT_CONTROL", &[0xf9]).is_ok());
        for prefix in [0xf0, 0xf2, 0xf3, 0x64, 0x65, 0x67] {
            assert!(admit(&statements, "new-instruction-description", &[prefix, 0xf9]).is_err());
        }
        assert!(admit(&[], "NOOP", &[0x90]).is_ok());
        assert!(admit(&[], "NOOP", &[0x0f, 0x1f, 0x00]).is_err());
        assert!(admit(&[], "MOV64rr", &[0x48, 0x89, 0xd8]).is_err());
    }
}
