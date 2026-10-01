use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Var {
    pub name: String,
    pub index: i32,
    #[serde(rename = "virtual")]
    pub virtual_: bool,
    pub width: usize,
    #[serde(rename = "type")]
    pub type_: String,
}
impl Var {
    pub fn key(&self) -> String {
        format!("{}:{}:{}", self.name, self.index, self.virtual_)
    }
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum Expr {
    Var {
        var: Var,
    },
    Int {
        value: String,
    },
    Unknown {
        reason: String,
    },
    Load {
        width: usize,
        mem: Box<Expr>,
        addr: Box<Expr>,
    },
    Store {
        width: usize,
        mem: Box<Expr>,
        addr: Box<Expr>,
        value: Box<Expr>,
    },
    Binop {
        op: i32,
        lhs: Box<Expr>,
        rhs: Box<Expr>,
    },
    Unop {
        op: i32,
        arg: Box<Expr>,
    },
    Cast {
        op: i32,
        width: usize,
        arg: Box<Expr>,
    },
    Extract {
        hi: usize,
        lo: usize,
        arg: Box<Expr>,
    },
    Concat {
        lhs: Box<Expr>,
        rhs: Box<Expr>,
    },
    Ite {
        condition: Box<Expr>,
        yes: Box<Expr>,
        no: Box<Expr>,
    },
    Let {
        var: Var,
        value: Box<Expr>,
        body: Box<Expr>,
    },
    Unsupported,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum Stmt {
    Move {
        var: Var,
        value: Expr,
    },
    Jump {
        target: Expr,
    },
    If {
        condition: Expr,
        yes: Vec<Stmt>,
        no: Vec<Stmt>,
    },
    While {
        condition: Expr,
        body: Vec<Stmt>,
    },
    Exception {
        number: i32,
    },
    Special,
    Unsupported,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Properties {
    pub jump: bool,
    pub conditional: bool,
    pub indirect: bool,
    pub call: bool,
    #[serde(rename = "return")]
    pub return_: bool,
    pub control: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Lift {
    pub schema: String,
    pub batch: usize,
    pub snapshot: String,
    pub va: String,
    pub status: String,
    pub length: u8,
    pub bytes: String,
    pub opcode: Option<String>,
    pub properties: Option<Properties>,
    pub bil: Vec<Stmt>,
}

impl Lift {
    pub fn validate_ast(&self) -> Result<(), crate::Error> {
        fn var(v: &Var) -> Result<(), crate::Error> {
            if v.name.is_empty()
                || v.name.len() > 128
                || v.index < 0
                || !matches!(v.type_.as_str(), "imm" | "mem")
                || (v.type_ == "imm" && !(1..=256).contains(&v.width))
                || (v.type_ == "mem" && v.width != 0)
            {
                return Err(crate::invalid("invalid BIL variable"));
            }
            Ok(())
        }
        fn budget(depth: usize, nodes: &mut usize) -> Result<(), crate::Error> {
            *nodes += 1;
            if depth > 64 || *nodes > 8192 {
                return Err(crate::invalid("BIL AST budget exceeded"));
            }
            Ok(())
        }
        fn expr(e: &Expr, d: usize, n: &mut usize) -> Result<(), crate::Error> {
            budget(d, n)?;
            match e {
                Expr::Var { var: v } => var(v)?,
                Expr::Int { value } if value.len() > 128 => {
                    return Err(crate::invalid("BIL integer too long"));
                }
                Expr::Unknown { reason } if reason.len() > 1024 => {
                    return Err(crate::invalid("BIL unknown too long"));
                }
                Expr::Load { width, mem, addr } => {
                    if !(1..=256).contains(width) {
                        return Err(crate::invalid("BIL load width"));
                    }
                    expr(mem, d + 1, n)?;
                    expr(addr, d + 1, n)?;
                }
                Expr::Store {
                    width,
                    mem,
                    addr,
                    value,
                } => {
                    if !(1..=256).contains(width) {
                        return Err(crate::invalid("BIL store width"));
                    }
                    expr(mem, d + 1, n)?;
                    expr(addr, d + 1, n)?;
                    expr(value, d + 1, n)?;
                }
                Expr::Binop { lhs, rhs, .. } | Expr::Concat { lhs, rhs } => {
                    expr(lhs, d + 1, n)?;
                    expr(rhs, d + 1, n)?;
                }
                Expr::Unop { arg, .. } => expr(arg, d + 1, n)?,
                Expr::Cast { width, arg, .. } => {
                    if !(1..=256).contains(width) {
                        return Err(crate::invalid("BIL cast width"));
                    }
                    expr(arg, d + 1, n)?;
                }
                Expr::Extract { hi, lo, arg } => {
                    if lo > hi || *hi >= 256 {
                        return Err(crate::invalid("BIL extraction bounds"));
                    }
                    expr(arg, d + 1, n)?;
                }
                Expr::Ite { condition, yes, no } => {
                    expr(condition, d + 1, n)?;
                    expr(yes, d + 1, n)?;
                    expr(no, d + 1, n)?;
                }
                Expr::Let {
                    var: v,
                    value,
                    body,
                } => {
                    var(v)?;
                    expr(value, d + 1, n)?;
                    expr(body, d + 1, n)?;
                }
                _ => {}
            }
            Ok(())
        }
        fn stmts(s: &[Stmt], d: usize, n: &mut usize) -> Result<(), crate::Error> {
            for s in s {
                budget(d, n)?;
                match s {
                    Stmt::Move { var: v, value } => {
                        var(v)?;
                        expr(value, d + 1, n)?;
                    }
                    Stmt::Jump { target } => expr(target, d + 1, n)?,
                    Stmt::If { condition, yes, no } => {
                        expr(condition, d + 1, n)?;
                        stmts(yes, d + 1, n)?;
                        stmts(no, d + 1, n)?;
                    }
                    Stmt::While { condition, body } => {
                        expr(condition, d + 1, n)?;
                        stmts(body, d + 1, n)?;
                    }
                    _ => {}
                }
            }
            Ok(())
        }
        stmts(&self.bil, 0, &mut 0)
    }
}
