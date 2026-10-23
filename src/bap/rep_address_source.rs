//! Identity-pinned AMD BAP producer for 28 address-32 REP forms and four LODS forms.
//! This transport accepts actual typed BIL and constructs no instruction effects.
use super::ast::{Expr, Lift, Stmt, Var};
use super::{Error, invalid};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

const MAX_RESPONSE: usize = 64 * 1024;
const MAX_EXECUTABLE: u64 = 256 * 1024 * 1024;
const CASES: [&str; 32] = [
    "66f3ad", "6766f2a7", "6766f2af", "6766f3a5", "6766f3a7", "6766f3ab", "6766f3ad", "6766f3af",
    "67f248a7", "67f248af", "67f2a6", "67f2a7", "67f2ae", "67f2af", "67f348a5", "67f348a7",
    "67f348ab", "67f348ad", "67f348af", "67f3a4", "67f3a5", "67f3a6", "67f3a7", "67f3aa", "67f3ab",
    "67f3ac", "67f3ad", "67f3ae", "67f3af", "f348ad", "f3ac", "f3ad",
];
pub(crate) const LOCK: &[u8] =
    include_bytes!("../../native/bap/source-coverage/rep-address.runtime.lock.json");

fn bounded_file(path: &Path, maximum: usize) -> Result<Vec<u8>, Error> {
    let file = std::fs::File::open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.len() > maximum as u64 {
        return Err(invalid("REP address source file size/type"));
    }
    let mut bytes = Vec::new();
    file.take(maximum as u64 + 1).read_to_end(&mut bytes)?;
    if bytes.len() > maximum {
        return Err(invalid("REP address source streamed file size"));
    }
    Ok(bytes)
}

fn file_hash(path: &Path, maximum: u64) -> Result<String, Error> {
    let mut file = std::fs::File::open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.len() > maximum {
        return Err(invalid("REP address source file size/type"));
    }
    let mut hash = Sha256::new();
    let mut buffer = [0; 64 * 1024];
    let mut total = 0u64;
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        total = total
            .checked_add(n as u64)
            .filter(|n| *n <= maximum)
            .ok_or_else(|| invalid("REP address source streamed file size"))?;
        hash.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

fn digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Lock {
    schema: String,
    manifest_sha256: String,
    executable_sha256: String,
}

pub(crate) struct RepAddressSource {
    directory: PathBuf,
    manifest_hash: String,
    executable_hash: String,
    build_id: String,
}

impl RepAddressSource {
    /// `lock_bytes` comes only from the repository's reviewed compile-time pin.
    /// Configuration selects a directory; it cannot supply a source certificate.
    pub(crate) fn load(directory: &Path, lock_bytes: &[u8]) -> Result<Self, Error> {
        let lock: Lock = serde_json::from_value(crate::reports::strict_json_with_limit(
            lock_bytes,
            MAX_RESPONSE,
        )?)?;
        if lock.schema != "ariadne.bap-source-rep-address-lock/v1"
            || !digest(&lock.manifest_sha256)
            || !digest(&lock.executable_sha256)
        {
            return Err(invalid("REP address source dependency lock schema/digest"));
        }
        let directory = directory.canonicalize()?;
        let bytes = bounded_file(&directory.join("manifest.json"), MAX_RESPONSE)?;
        let manifest_hash = crate::reports::sha256(&bytes);
        if manifest_hash != lock.manifest_sha256 {
            return Err(invalid(
                "REP address source manifest differs from dependency lock",
            ));
        }
        let manifest = crate::reports::strict_json_with_limit(&bytes, MAX_RESPONSE)?;
        if manifest["schema"] != "ariadne.bap-source-rep-address-build/v1"
            || manifest["profiles"] != serde_json::json!(["bap-bit-provenance-v15"])
            || manifest["runtime_role"] != "rep-address-source"
            || manifest["vendor"] != "AMD"
            || manifest["semantic_premises"]
                != serde_json::json!([
                    "amd-long-mode-memory-rep",
                    "address32-zero-count-preserves-upper-lanes"
                ])
            || manifest["executable"] != "rep-address-lift"
            || manifest["executable_sha256"] != lock.executable_sha256
            || manifest["max_response_bytes"] != MAX_RESPONSE
            || manifest["cases"] != serde_json::json!(CASES)
        {
            return Err(invalid("REP address source manifest scope"));
        }
        let sources = manifest["binding"]["sources"]
            .as_object()
            .ok_or_else(|| invalid("REP address source binding sources"))?;
        let expected = [
            (
                "rep_address_build.py",
                include_bytes!("../../native/bap/source-coverage/rep_address_build.py").as_slice(),
            ),
            (
                "rep_address_lift.ml",
                include_bytes!("../../native/bap/source-coverage/rep_address_lift.ml").as_slice(),
            ),
            (
                "rep_address_probe.ml",
                include_bytes!("../../native/bap/source-coverage/rep_address_probe.ml").as_slice(),
            ),
            (
                "rep_address.patch",
                include_bytes!("../../native/bap/source-coverage/rep_address.patch").as_slice(),
            ),
            (
                "lods.patch",
                include_bytes!("../../native/bap/source-coverage/lods.patch").as_slice(),
            ),
            (
                "build.py",
                include_bytes!("../../native/bap/source-coverage/build.py").as_slice(),
            ),
        ];
        if sources.len() != expected.len()
            || expected.iter().any(|(name, source)| {
                sources.get(*name) != Some(&crate::reports::sha256(source).into())
            })
        {
            return Err(invalid("REP address source/patch binding differs"));
        }
        let sdk_lock_bytes = include_bytes!("../../native/bap-core/sdk.lock.json");
        let sdk_lock = crate::reports::strict_json(sdk_lock_bytes)?;
        if manifest["binding"]["sdk_lock_sha256"] != crate::reports::sha256(sdk_lock_bytes)
            || manifest["binding"]["base_revision"] != sdk_lock["bapSourceRevision"]
            || manifest["binding"]["source_archive_sha256"]
                != sdk_lock["bapSourceArchive"]["sha256"]
        {
            return Err(invalid("REP address source SDK/archive binding differs"));
        }
        for name in ["sdk_manifest_sha256", "compiler_sha256"] {
            if !manifest["binding"][name].as_str().is_some_and(digest) {
                return Err(invalid("REP address source SDK/compiler identity"));
            }
        }
        for name in ["upstream_modules", "patched_modules"] {
            let modules = manifest["binding"][name]
                .as_object()
                .ok_or_else(|| invalid("REP address source module binding"))?;
            let expected_modules = [
                "lib/x86_cpu/x86_types.ml",
                "lib/x86_cpu/x86_env.ml",
                "lib/x86_cpu/x86_cpu.ml",
                "plugins/x86/x86_utils.ml",
                "plugins/x86/x86_disasm.ml",
                "plugins/x86/x86_lifter.ml",
            ];
            if modules.len() != expected_modules.len()
                || expected_modules.iter().any(|name| {
                    !modules
                        .get(*name)
                        .and_then(serde_json::Value::as_str)
                        .is_some_and(digest)
                })
            {
                return Err(invalid("REP address source module identity"));
            }
        }
        let build_id = manifest["build_id"]
            .as_str()
            .filter(|value| digest(value))
            .ok_or_else(|| invalid("REP address source build ID"))?
            .to_owned();
        if build_id != crate::reports::sha256(&serde_json::to_vec(&manifest["binding"])?) {
            return Err(invalid("REP address source build ID differs"));
        }
        let source = Self {
            directory,
            manifest_hash,
            executable_hash: lock.executable_sha256,
            build_id,
        };
        source.validate()?;
        Ok(source)
    }

    pub(crate) fn validate(&self) -> Result<(), Error> {
        if file_hash(&self.directory.join("manifest.json"), MAX_RESPONSE as u64)?
            != self.manifest_hash
            || file_hash(&self.directory.join("rep-address-lift"), MAX_EXECUTABLE)?
                != self.executable_hash
        {
            return Err(invalid("REP address source artifact changed"));
        }
        Ok(())
    }

    pub(crate) fn runtime_identity(&self, base_runtime: &str) -> String {
        crate::reports::sha256(
            format!(
                "ariadne.bap-source-rep-address-runtime/v1\n{base_runtime}\n{}\n{}\n{}\n",
                self.manifest_hash, self.executable_hash, self.build_id
            )
            .as_bytes(),
        )
    }

    pub(crate) fn supports(bytes: &[u8]) -> bool {
        let code: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
        CASES.contains(&code.as_str())
    }

    pub(crate) fn lift(
        &self,
        target: &str,
        snapshot: &str,
        va: u64,
        bytes: &[u8],
        timeout: Duration,
    ) -> Result<Vec<Stmt>, Error> {
        if !Self::supports(bytes)
            || va.checked_add(bytes.len() as u64).is_none()
            || !["windows-amd64", "linux-amd64"].contains(&target)
            || timeout.is_zero()
        {
            return Err(invalid("REP address source outside exact query scope"));
        }
        self.validate()?;
        let snapshot = crate::reports::sha256(snapshot.as_bytes());
        let va = format!("0x{va:016x}");
        let code: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
        let start = Instant::now();
        let mut child = ManagedChild(
            Command::new(self.directory.join("rep-address-lift"))
                .args([target, &snapshot, &va, &code])
                .env_clear()
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()?,
        );
        let output = child
            .0
            .stdout
            .take()
            .ok_or_else(|| invalid("REP address source stdout"))?;
        let (sender, receiver) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut bytes = Vec::new();
            let result = output
                .take(MAX_RESPONSE as u64 + 1)
                .read_to_end(&mut bytes)
                .map(|_| bytes)
                .map_err(|e| e.to_string());
            let _ = sender.send(result);
        });
        let output = receiver
            .recv_timeout(timeout.saturating_sub(start.elapsed()))
            .map_err(|_| invalid("REP address source response timeout"))?
            .map_err(invalid)?;
        if output.len() > MAX_RESPONSE {
            return Err(invalid("REP address source response limit"));
        }
        loop {
            if let Some(status) = child.0.try_wait()? {
                if !status.success() {
                    return Err(invalid("REP address source process failed"));
                }
                break;
            }
            if start.elapsed() >= timeout {
                return Err(invalid("REP address source exit timeout"));
            }
            std::thread::sleep(Duration::from_millis(2));
        }
        let response: Response = serde_json::from_value(crate::reports::strict_json_with_limit(
            &output,
            MAX_RESPONSE,
        )?)?;
        let bil = self.bind_response(response, target, &snapshot, &va, &code)?;
        self.validate()?;
        Ok(bil)
    }

    fn bind_response(
        &self,
        response: Response,
        target: &str,
        snapshot: &str,
        va: &str,
        code: &str,
    ) -> Result<Vec<Stmt>, Error> {
        if response.schema != "ariadne.bap-source-rep-address/v1"
            || response.build_id != self.build_id
            || response.target != target
            || response.snapshot != snapshot
            || response.va != va
            || response.bytes != code
            || !CASES.contains(&code)
            || response.length as usize != code.len() / 2
        {
            return Err(invalid(
                "REP address source response identity/extent differs",
            ));
        }
        Lift {
            schema: String::new(),
            batch: 0,
            snapshot: String::new(),
            va: String::new(),
            status: String::new(),
            length: response.length,
            bytes: String::new(),
            opcode: None,
            properties: None,
            bil: response.bil.clone(),
        }
        .validate_ast()?;
        validate_rep_address_bil(&response.bil, code)?;
        Ok(response.bil)
    }
}

fn validate_rep_address_bil(statements: &[Stmt], code: &str) -> Result<(), Error> {
    let writes: &[&str] = match &code[code.len() - 2..] {
        "a4" | "a5" => &["RCX", "RSI", "RDI", "mem"],
        "aa" | "ab" => &["RCX", "RDI", "mem"],
        "ac" | "ad" => &["RAX", "RCX", "RSI"],
        "a6" | "a7" => &["RCX", "RSI", "RDI", "CF", "PF", "AF", "ZF", "SF", "OF"],
        "ae" | "af" => &["RCX", "RDI", "CF", "PF", "AF", "ZF", "SF", "OF"],
        _ => return Err(invalid("REP address source instruction family")),
    };
    fn variable(var: &Var, writes: Option<&[&str]>) -> Result<(), Error> {
        if !var.virtual_
            && !(if let Some(writes) = writes {
                writes.contains(&var.name.as_str())
            } else {
                [
                    "RAX", "RCX", "RSI", "RDI", "CF", "PF", "AF", "ZF", "SF", "OF", "DF", "mem",
                ]
                .contains(&var.name.as_str())
            })
        {
            return Err(invalid(
                "REP address source outside architectural register scope",
            ));
        }
        Ok(())
    }
    fn expression(expr: &Expr) -> Result<(), Error> {
        match expr {
            Expr::Var { var } => variable(var, None)?,
            Expr::Int { .. } => {}
            Expr::Load { mem, addr, .. } => {
                expression(mem)?;
                expression(addr)?;
            }
            Expr::Store {
                mem, addr, value, ..
            } => {
                expression(mem)?;
                expression(addr)?;
                expression(value)?;
            }
            Expr::Binop {
                op: 0..=18,
                lhs,
                rhs,
            } => {
                expression(lhs)?;
                expression(rhs)?;
            }
            Expr::Unop { op: 0, arg } => expression(arg)?,
            Expr::Cast { op: 0..=3, arg, .. } | Expr::Extract { arg, .. } => expression(arg)?,
            Expr::Concat { lhs, rhs } => {
                expression(lhs)?;
                expression(rhs)?;
            }
            Expr::Ite { condition, yes, no } => {
                expression(condition)?;
                expression(yes)?;
                expression(no)?;
            }
            Expr::Let { var, value, body } => {
                if !var.virtual_ {
                    return Err(invalid("REP address source architectural let binder"));
                }
                expression(value)?;
                expression(body)?;
            }
            _ => return Err(invalid("REP address source unmodeled expression")),
        }
        Ok(())
    }
    fn body(statements: &[Stmt], writes: &[&str]) -> Result<(), Error> {
        for statement in statements {
            match statement {
                Stmt::Move { var, value } => {
                    variable(var, Some(writes))?;
                    expression(value)?;
                }
                Stmt::If { condition, yes, no } => {
                    expression(condition)?;
                    body(yes, writes)?;
                    body(no, writes)?;
                }
                _ => return Err(invalid("REP address source unmodeled control/nested loop")),
            }
        }
        Ok(())
    }
    let [
        Stmt::Move {
            var: loop_flag,
            value: Expr::Int { value: initial },
        },
        Stmt::While {
            condition,
            body: loop_body,
        },
    ] = statements
    else {
        return Err(invalid(
            "REP address source requires loop-flag seed and one top-level loop",
        ));
    };
    if !loop_flag.virtual_
        || loop_flag.width != 1
        || loop_flag.type_ != "imm"
        || initial != "1:1u"
        || loop_body.is_empty()
    {
        return Err(invalid(
            "REP address source requires virtual flag seed and nonempty loop body",
        ));
    }
    expression(condition)?;
    body(loop_body, writes)?;
    // The existing repeated-string checker provides width/type and temporary
    // binding validation without granting this bundle any instruction admission.
    let capabilities = super::admission::capabilities_with_profile(
        statements,
        super::repeated_strings::PROFILE15,
    )?;
    if !capabilities.ordinary_data_only || capabilities.unsupported_data {
        return Err(invalid("REP address source unsupported data/control"));
    }
    Ok(())
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Response {
    schema: String,
    build_id: String,
    target: String,
    snapshot: String,
    va: String,
    bytes: String,
    length: u8,
    bil: Vec<Stmt>,
}

struct ManagedChild(Child);
impl Drop for ManagedChild {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[cfg(test)]
#[path = "../../tests/bap/rep_address_source_unit.rs"]
mod tests;
