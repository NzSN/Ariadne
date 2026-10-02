use crate::bap::ast::{Expr, Stmt, Var};
use crate::bap::{Error, invalid};
use crate::{LocationSet, effects::Catalogue};
use std::collections::BTreeMap;

const BANKS: [&str; 16] = [
    "RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI", "R8", "R9", "R10", "R11", "R12", "R13",
    "R14", "R15",
];
#[derive(Clone, Debug, PartialEq, Eq)]
struct Bit {
    value: Option<bool>,
    original: Option<(String, usize)>,
    deps: LocationSet,
    uncertain: bool,
}
impl Bit {
    fn constant(value: bool) -> Self {
        Self {
            value: Some(value),
            original: None,
            deps: LocationSet::new(),
            uncertain: false,
        }
    }
    fn calculated(deps: LocationSet, uncertain: bool) -> Self {
        Self {
            value: None,
            original: None,
            deps,
            uncertain,
        }
    }
}
#[derive(Clone, Debug)]
enum Value {
    Bits(Vec<Bit>),
    Memory,
}
impl Value {
    fn bits(&self) -> Result<&[Bit], Error> {
        match self {
            Self::Bits(bits) => Ok(bits),
            Self::Memory => Err(invalid("memory used as scalar")),
        }
    }
    fn deps(&self) -> LocationSet {
        match self {
            Self::Bits(bits) => bits.iter().flat_map(|b| b.deps.iter().cloned()).collect(),
            Self::Memory => LocationSet::new(),
        }
    }
    fn constant(&self) -> Option<u64> {
        let bits = self.bits().ok()?;
        if bits.len() > 64 {
            return None;
        }
        let mut n = 0;
        for (i, b) in bits.iter().enumerate() {
            if b.value? {
                n |= 1u64 << i;
            }
        }
        Some(n)
    }
}
#[derive(Clone, Default)]
struct State {
    env: BTreeMap<String, Value>,
    arch: BTreeMap<String, Var>,
    forced_uses: LocationSet,
    memory_write: bool,
    gaps: Vec<String>,
    jumps: Vec<Option<u64>>,
}
fn location(var: &Var, bit: usize) -> Result<String, Error> {
    if let Some(bank) = BANKS.iter().position(|name| *name == var.name) {
        if var.width != 64 || bit >= 64 {
            return Err(invalid("unreviewed architectural register width"));
        }
        return Ok(format!(
            "gpr:{}:{}",
            BANKS[bank].to_ascii_lowercase(),
            bit / 8
        ));
    }
    let flag = var.name.to_ascii_lowercase();
    if ["cf", "pf", "af", "zf", "sf", "of", "df"].contains(&flag.as_str())
        && var.width == 1
        && bit == 0
    {
        return Ok(format!("flag:{flag}"));
    }
    Err(invalid(format!(
        "unmodeled architectural variable {}",
        var.name
    )))
}
fn initial(var: &Var, va: u64) -> Result<Value, Error> {
    if var.type_ == "mem" && var.name == "mem" {
        return Ok(Value::Memory);
    }
    if var.type_ != "imm" || var.width == 0 || var.width > 256 {
        return Err(invalid("unreviewed BIL variable type/width"));
    }
    if var.name == "RIP" && !var.virtual_ && var.width == 64 {
        return Ok(Value::Bits(
            (0..64)
                .map(|i| Bit::constant(va & (1u64 << i) != 0))
                .collect(),
        ));
    }
    if var.virtual_ {
        return Err(invalid("read before virtual definition"));
    }
    Ok(Value::Bits(
        (0..var.width)
            .map(|i| {
                Ok(Bit {
                    value: None,
                    original: Some((var.key(), i)),
                    deps: [location(var, i)?].into(),
                    uncertain: false,
                })
            })
            .collect::<Result<_, Error>>()?,
    ))
}
fn get(state: &mut State, var: &Var, va: u64) -> Result<Value, Error> {
    if let Some(v) = state.env.get(&var.key()) {
        return Ok(v.clone());
    }
    let value = initial(var, va)?;
    state.env.insert(var.key(), value.clone());
    if !var.virtual_ && var.type_ == "imm" && var.name != "RIP" {
        state.arch.insert(var.key(), var.clone());
    }
    Ok(value)
}
fn union(lhs: &Value, rhs: &Value) -> LocationSet {
    lhs.deps().union(&rhs.deps()).cloned().collect()
}
fn integer(text: &str) -> Result<Value, Error> {
    let (value, width) = text
        .split_once(':')
        .ok_or_else(|| invalid("BIL integer missing width"))?;
    let digits = width
        .strip_suffix('u')
        .or_else(|| width.strip_suffix('s'))
        .unwrap_or(width);
    let width: usize = digits.parse()?;
    if width == 0 || width > 256 {
        return Err(invalid("BIL integer width limit"));
    }
    let mut bits = vec![Bit::constant(false); width];
    if let Some(hex) = value.strip_prefix("0x") {
        for (digit, c) in hex.chars().rev().enumerate() {
            let nibble = c.to_digit(16).ok_or_else(|| invalid("BIL integer hex"))?;
            for b in 0..4 {
                let i = digit * 4 + b;
                if i < width {
                    bits[i] = Bit::constant(nibble & (1 << b) != 0);
                } else if nibble & (1 << b) != 0 {
                    return Err(invalid("BIL integer overflow"));
                }
            }
        }
    } else {
        let n: i128 = value.parse()?;
        for (i, bit) in bits.iter_mut().enumerate() {
            *bit = Bit::constant(if i < 128 {
                (n as u128) & (1u128 << i) != 0
            } else {
                n < 0
            });
        }
    }
    Ok(Value::Bits(bits))
}
fn join(condition: &Value, yes: Value, no: Value) -> Result<Value, Error> {
    let y = yes.bits()?;
    let n = no.bits()?;
    if y.len() != n.len() {
        return Err(invalid("BIL choice width mismatch"));
    }
    Ok(Value::Bits(
        y.iter()
            .zip(n)
            .map(|(y, n)| {
                if y == n {
                    y.clone()
                } else {
                    Bit::calculated(
                        y.deps
                            .union(&n.deps)
                            .cloned()
                            .chain(condition.deps())
                            .collect(),
                        true, // conditional choice may preserve the destination; never infer a kill
                    )
                }
            })
            .collect(),
    ))
}
fn eval(expr: &Expr, state: &mut State, va: u64, depth: usize) -> Result<Value, Error> {
    if depth > 64 {
        return Err(invalid("BIL expression depth exceeded"));
    }
    let mut child = |e: &Expr| eval(e, state, va, depth + 1);
    Ok(match expr {
        Expr::Var { var } => get(state, var, va)?,
        Expr::Int { value } => integer(value)?,
        Expr::Unknown { reason } => {
            state.gaps.push(format!("unknown-output:{reason}"));
            Value::Bits(vec![Bit::calculated(Catalogue.locations(), true)])
        }
        Expr::Load { width, mem, addr } => {
            if *width == 0 || *width > 256 || !matches!(child(mem)?, Value::Memory) {
                return Err(invalid("invalid load type/width"));
            }
            let address = child(addr)?;
            let deps = address
                .deps()
                .into_iter()
                .chain(["memory:any".into()])
                .collect();
            Value::Bits(vec![Bit::calculated(deps, false); *width])
        }
        Expr::Store {
            width,
            mem,
            addr,
            value,
        } => {
            if !matches!(child(mem)?, Value::Memory) || ![8, 16, 32, 64].contains(width) {
                return Err(invalid("invalid store type/width"));
            }
            let address = child(addr)?;
            let stored = child(value)?;
            if stored.bits()?.len() != *width {
                return Err(invalid("store payload width"));
            }
            state.forced_uses.extend(address.deps());
            state.forced_uses.extend(stored.deps());
            state.memory_write = true;
            Value::Memory
        }
        Expr::Extract { hi, lo, arg } => {
            let value = child(arg)?;
            let bits = value.bits()?;
            if lo > hi || *hi >= bits.len() {
                return Err(invalid("BIL extraction range"));
            }
            Value::Bits(bits[*lo..=*hi].to_vec())
        }
        Expr::Concat { lhs, rhs } => {
            let lhs = child(lhs)?;
            let rhs = child(rhs)?;
            let mut bits = rhs.bits()?.to_vec();
            bits.extend_from_slice(lhs.bits()?);
            if bits.len() > 256 {
                return Err(invalid("concatenation width limit"));
            }
            Value::Bits(bits)
        }
        Expr::Cast { op, width, arg } => {
            if *width == 0 || *width > 256 {
                return Err(invalid("cast width limit"));
            }
            let value = child(arg)?;
            let source = value.bits()?;
            let bits = match *op {
                0 if *width <= source.len() => source[..*width].to_vec(),
                1 if *width <= source.len() => source[source.len() - width..].to_vec(),
                2 | 3 if *width >= source.len() => {
                    let mut bits = source.to_vec();
                    let extension = if *op == 2 {
                        source
                            .last()
                            .ok_or_else(|| invalid("empty signed source"))?
                            .clone()
                    } else {
                        Bit::constant(false)
                    };
                    bits.resize(*width, extension);
                    bits
                }
                _ => return Err(invalid("cast mode/width mismatch")),
            };
            Value::Bits(bits)
        }
        Expr::Let { var, value, body } => {
            let value = child(value)?;
            let key = var.key();
            let previous = state.env.insert(key.clone(), value);
            let result = eval(body, state, va, depth + 1)?;
            if let Some(previous) = previous {
                state.env.insert(key, previous);
            } else {
                state.env.remove(&key);
            }
            result
        }
        Expr::Ite { condition, yes, no } => {
            let condition = child(condition)?;
            if let Some(c) = condition.constant() {
                if c == 0 { child(no)? } else { child(yes)? }
            } else {
                let y = child(yes)?;
                let n = child(no)?;
                join(&condition, y, n)?
            }
        }
        Expr::Unop { op, arg } => {
            let value = child(arg)?;
            if *op == 0 {
                Value::Bits(
                    value
                        .bits()?
                        .iter()
                        .map(|b| {
                            if let Some(v) = b.value {
                                Bit::constant(!v)
                            } else {
                                Bit::calculated(b.deps.clone(), b.uncertain)
                            }
                        })
                        .collect(),
                )
            } else if *op == 1 {
                Value::Bits(vec![
                    Bit::calculated(
                        value.deps(),
                        value.bits()?.iter().any(|b| b.uncertain)
                    );
                    value.bits()?.len()
                ])
            } else {
                return Err(invalid("unsupported unary operator"));
            }
        }
        Expr::Binop { op, lhs, rhs } => {
            let left = child(lhs)?;
            let right = child(rhs)?;
            let l = left.bits()?;
            let r = right.bits()?;
            if l.len() != r.len() {
                return Err(invalid("binary width mismatch"));
            }
            if *op == 6 && l == r {
                Value::Bits(vec![Bit::constant(false); l.len()])
            } else if [6, 7, 8].contains(op) {
                Value::Bits(
                    l.iter()
                        .zip(r)
                        .map(|(a, b)| {
                            if let (Some(a), Some(b)) = (a.value, b.value) {
                                return Bit::constant(match op {
                                    6 => a ^ b,
                                    7 => a | b,
                                    _ => a & b,
                                });
                            }
                            if *op == 8 && (a.value == Some(false) || b.value == Some(false)) {
                                return Bit::constant(false);
                            }
                            if *op == 7 && (a.value == Some(true) || b.value == Some(true)) {
                                return Bit::constant(true);
                            }
                            if (*op == 8 && b.value == Some(true))
                                || (*op == 7 && b.value == Some(false))
                                || (*op == 6 && b.value == Some(false))
                            {
                                return a.clone();
                            }
                            if (*op == 8 && a.value == Some(true))
                                || (*op == 7 && a.value == Some(false))
                                || (*op == 6 && a.value == Some(false))
                            {
                                return b.clone();
                            }
                            Bit::calculated(
                                a.deps.union(&b.deps).cloned().collect(),
                                a.uncertain || b.uncertain,
                            )
                        })
                        .collect(),
                )
            } else if [9, 10, 11].contains(op) && right.constant().is_some() {
                let shift = right.constant().unwrap() as usize;
                let mut bits = vec![Bit::constant(false); l.len()];
                for (i, bit) in bits.iter_mut().enumerate() {
                    *bit = if *op == 11 {
                        if i >= shift {
                            l[i - shift].clone()
                        } else {
                            Bit::constant(false)
                        }
                    } else if i.checked_add(shift).is_some_and(|n| n < l.len()) {
                        l[i + shift].clone()
                    } else if *op == 9 {
                        l.last().unwrap().clone()
                    } else {
                        Bit::constant(false)
                    };
                }
                Value::Bits(bits)
            } else if (0..=18).contains(op) {
                let width = if *op <= 5 { 1 } else { l.len() };
                Value::Bits(vec![
                    Bit::calculated(
                        union(&left, &right),
                        l.iter().chain(r).any(|b| b.uncertain)
                    );
                    width
                ])
            } else {
                return Err(invalid("unsupported binary operator"));
            }
        }
        Expr::Unsupported => return Err(invalid("unsupported BIL expression")),
    })
}
fn run(
    statements: &[Stmt],
    states: Vec<State>,
    va: u64,
    depth: usize,
) -> Result<Vec<State>, Error> {
    if depth > 32 {
        return Err(invalid("BIL statement nesting limit"));
    }
    let mut states = states;
    for stmt in statements {
        let mut next = Vec::new();
        for mut state in states {
            match stmt {
                Stmt::Move { var, value } => {
                    if !var.virtual_ && var.type_ == "imm" && var.name != "RIP" {
                        get(&mut state, var, va)?;
                    }
                    let frame_expression = matches!(value, Expr::Concat { .. } | Expr::Ite { .. });
                    let mut value = eval(value, &mut state, va, 0)?;
                    if !var.virtual_ && var.type_ == "imm" && !frame_expression {
                        // A scalar assignment is an architectural definition even
                        // when an input bit equals its old value. Concat frames
                        // and conditional preservation remain separately tracked.
                        if let Value::Bits(bits) = &mut value {
                            for bit in bits {
                                bit.original = None;
                            }
                        }
                    }
                    if var.type_ == "imm" && value.bits()?.len() != var.width {
                        // Generic Unknown lacks a type in the packaged accessor.
                        if matches!(value,Value::Bits(ref b) if b.len()==1&&b[0].uncertain) {
                            state.env.insert(
                                var.key(),
                                Value::Bits(vec![value.bits()?[0].clone(); var.width]),
                            );
                        } else {
                            return Err(invalid("assignment width mismatch"));
                        }
                    } else {
                        state.env.insert(var.key(), value);
                    }
                    next.push(state);
                }
                Stmt::Jump { target } => {
                    let value = eval(target, &mut state, va, 0)?;
                    state.forced_uses.extend(value.deps());
                    state.jumps.push(value.constant());
                    next.push(state);
                }
                Stmt::If { condition, yes, no } => {
                    let value = eval(condition, &mut state, va, 0)?;
                    state.forced_uses.extend(value.deps());
                    if let Some(c) = value.constant() {
                        next.extend(run(
                            if c == 0 { no } else { yes },
                            vec![state],
                            va,
                            depth + 1,
                        )?);
                    } else {
                        next.extend(run(yes, vec![state.clone()], va, depth + 1)?);
                        next.extend(run(no, vec![state], va, depth + 1)?);
                    }
                }
                Stmt::While { condition, body } => {
                    let _ = (condition, body);
                    return Err(invalid("unreviewed loop semantics"));
                }
                Stmt::Exception { number } => {
                    return Err(invalid(format!("unreviewed exception semantics {number}")));
                }
                Stmt::Special | Stmt::Unsupported => {
                    return Err(invalid("unreviewed special semantics"));
                }
            }
        }
        if next.len() > 32 {
            return Err(invalid("BIL path limit"));
        }
        states = next;
    }
    Ok(states)
}
#[derive(Clone, Debug)]
pub(crate) struct Projection {
    pub uses: LocationSet,
    pub may_defs: LocationSet,
    pub must_defs: LocationSet,
    pub gaps: Vec<String>,
    pub targets: Vec<Option<u64>>,
}
fn supported(opcode: &str) -> bool {
    matches!(
        opcode,
        "MOV64rr"
            | "MOV8rr"
            | "MOV16rr"
            | "MOV32rr"
            | "MOV32ri"
            | "MOV64rm"
            | "MOV32rm"
            | "MOV64mr"
            | "MOV32mr"
            | "MOV32mi"
            | "MOV64mi32"
            | "CMOV64rr"
            | "NOT64r"
            | "MOVSX64rr8"
            | "MOVZX32rr8"
            | "LEA64r"
            | "ADD64rr"
            | "ADC64rr"
            | "CMP64rr"
            | "TEST64rr"
            | "TEST8rr"
            | "INC64r"
            | "PUSH64r"
            | "POP64r"
            | "JCC_1"
            | "JMP_1"
            | "JMP64r"
            | "SHL64ri"
            | "SHL64rCL"
    )
}
#[cfg(test)]
pub(crate) fn project(
    statements: &[Stmt],
    opcode: &str,
    bytes: &[u8],
    va: u64,
) -> Result<Projection, Error> {
    project_with_destination(statements, opcode, bytes, va, None)
}
pub(crate) fn project_with_destination(
    statements: &[Stmt],
    opcode: &str,
    bytes: &[u8],
    va: u64,
    destination: Option<&crate::effects::RegisterView>,
) -> Result<Projection, Error> {
    let mut guarded_prefix = false;
    for byte in bytes {
        if [0xf0, 0xf2, 0xf3, 0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65, 0x67].contains(byte) {
            guarded_prefix = true;
            break;
        }
        if *byte == 0x66 || *byte == 0x67 || (0x40..=0x4f).contains(byte) {
            continue;
        }
        break;
    }
    if statements.is_empty() && opcode == "NOOP" && bytes == [0x90] {
        return Ok(Projection {
            uses: LocationSet::new(),
            may_defs: LocationSet::new(),
            must_defs: LocationSet::new(),
            gaps: Vec::new(),
            targets: Vec::new(),
        });
    }
    if statements.is_empty() || !supported(opcode) || guarded_prefix {
        return Err(invalid("unsupported lift/form/prefix"));
    }
    let states = run(statements, vec![State::default()], va, 0)?;
    let mut uses = LocationSet::new();
    let mut may_defs = LocationSet::new();
    let mut must_defs: Option<LocationSet> = None;
    let mut gaps = Vec::new();
    let mut targets = Vec::new();
    let partial_destination = if ["MOV8rr", "MOV16rr"].contains(&opcode) {
        destination.map(|d| d.replacements()).unwrap_or_default()
    } else {
        LocationSet::new()
    };
    for state in states {
        uses.extend(state.forced_uses);
        let mut definite = LocationSet::new();
        for (key, var) in &state.arch {
            let value = state
                .env
                .get(key)
                .ok_or_else(|| invalid("missing architectural output"))?;
            let bits = value.bits()?;
            if bits.len() != var.width {
                return Err(invalid("architectural width mismatch"));
            }
            let mut cells: BTreeMap<String, Vec<(usize, &Bit)>> = BTreeMap::new();
            for (i, bit) in bits.iter().enumerate() {
                cells.entry(location(var, i)?).or_default().push((i, bit));
            }
            for (cell, parts) in cells {
                let changed = partial_destination.contains(&cell)
                    || parts
                        .iter()
                        .any(|(i, b)| b.original.as_ref() != Some(&(key.clone(), *i)));
                if changed {
                    may_defs.insert(cell.clone());
                    for (_, bit) in &parts {
                        uses.extend(bit.deps.clone());
                    }
                    if parts.iter().all(|(i, b)| {
                        !b.uncertain
                            && (partial_destination.contains(&cell)
                                || b.original.as_ref() != Some(&(key.clone(), *i)))
                    }) {
                        definite.insert(cell);
                    }
                }
            }
        }
        if state.memory_write {
            may_defs.insert("memory:any".into());
        }
        must_defs = Some(if let Some(old) = must_defs {
            old.intersection(&definite).cloned().collect()
        } else {
            definite
        });
        gaps.extend(state.gaps);
        targets.extend(state.jumps);
    }
    gaps.sort();
    gaps.dedup();
    Ok(Projection {
        uses,
        may_defs,
        must_defs: must_defs.unwrap_or_default(),
        gaps,
        targets,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn generic_unknown_keeps_old_origins_and_is_not_an_undefined_isa_claim() {
        let statements = [Stmt::Move {
            var: Var {
                name: "AF".into(),
                index: 0,
                virtual_: false,
                width: 1,
                type_: "imm".into(),
            },
            value: Expr::Unknown {
                reason: "generic-output".into(),
            },
        }];
        let p = project(&statements, "ADD64rr", &[0x48, 0x01, 0xd8], 0x1000).unwrap();
        assert_eq!(p.may_defs, ["flag:af".into()].into());
        assert!(p.must_defs.is_empty());
        assert_eq!(p.uses, Catalogue.locations());
        assert_eq!(p.gaps, ["unknown-output:generic-output"]);
        assert!(project(&[], "MOV64rr", &[0x48, 0x89, 0xd8], 0x1000).is_err());
    }
    #[test]
    fn captured_bil_matches_independent_alias_flag_address_and_memory_expectations() {
        let corpus: serde_json::Value =
            serde_json::from_str(include_str!("../../tests/bap/fixtures/corpus.json")).unwrap();
        for row in corpus["rows"].as_array().unwrap() {
            let lift: crate::bap::ast::Lift = serde_json::from_value(row["lift"].clone()).unwrap();
            lift.validate_ast().unwrap();
            let hex = row["prefix"].as_str().unwrap();
            let bytes: Vec<u8> = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                .collect();
            let projected = project(
                &lift.bil,
                lift.opcode.as_deref().unwrap(),
                &bytes,
                u64::from_str_radix(&lift.va[2..], 16).unwrap(),
            );
            if row["expect"]["reject"] == true {
                assert!(projected.is_err(), "{}", row["name"]);
                continue;
            }
            let p = projected.unwrap_or_else(|e| panic!("{}: {e}", row["name"]));
            for (key, actual) in [
                ("uses", &p.uses),
                ("may_defs", &p.may_defs),
                ("must_defs", &p.must_defs),
            ] {
                if let Some(expected) = row["expect"][key].as_array() {
                    let expected: LocationSet = expected
                        .iter()
                        .map(|s| s.as_str().unwrap().into())
                        .collect();
                    assert_eq!(*actual, expected, "{} {key}", row["name"]);
                }
            }
            for (key, actual) in [("uses", &p.uses), ("must", &p.must_defs)] {
                for (suffix, want) in [("includes", true), ("excludes", false)] {
                    if let Some(cells) = row["expect"][format!("{key}_{suffix}")].as_array() {
                        for c in cells {
                            assert_eq!(
                                actual.contains(c.as_str().unwrap()),
                                want,
                                "{} {key} {c}",
                                row["name"]
                            );
                        }
                    }
                }
            }
        }
    }
}
