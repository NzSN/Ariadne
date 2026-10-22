//! Explicitly selected, identity-pinned upstream BAP flag extension.
//! This module transports actual typed BIL; it constructs no instruction effects.
use super::ast::Stmt;
use super::{Error, invalid};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

pub(crate) const PROFILE: &str = "bap-bit-provenance-v9";
pub(crate) const ADVANCED_PROFILE: &str = "bap-bit-provenance-v10";
pub(crate) const ADVANCED_GUARDED_PROFILE: &str = "bap-bit-provenance-v11";
const MAX_RESPONSE: usize = 4096;
const LOCK: &[u8] = include_bytes!("../../native/bap/source-coverage/runtime.lock.json");
const ADVANCED_LOCK: &[u8] =
    include_bytes!("../../native/bap/source-coverage/advanced.runtime.lock.json");

fn file_hash(path: &Path, maximum: u64) -> Result<String, Error> {
    let mut file = std::fs::File::open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.len() > maximum {
        return Err(invalid("source extension file size/type"));
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
            .ok_or_else(|| invalid("source extension streamed file size"))?;
        hash.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Lock {
    schema: String,
    manifest_sha256: String,
    executable_sha256: String,
}

pub(crate) struct SourceExtension {
    directory: PathBuf,
    manifest_hash: String,
    executable_hash: String,
    build_id: String,
}

impl SourceExtension {
    #[cfg(test)]
    pub(crate) fn load(directory: &Path) -> Result<Self, Error> {
        Self::load_with_mode(directory, super::SourceExtensionMode::Basic)
    }
    pub(crate) fn load_with_mode(
        directory: &Path,
        mode: super::SourceExtensionMode,
    ) -> Result<Self, Error> {
        let advanced = mode == super::SourceExtensionMode::Advanced;
        if mode == super::SourceExtensionMode::Invalid {
            return Err(invalid("invalid source extension mode"));
        }
        let lock: Lock = serde_json::from_value(crate::reports::strict_json(if advanced {
            ADVANCED_LOCK
        } else {
            LOCK
        })?)?;
        if lock.schema
            != if advanced {
                "ariadne.bap-source-advanced-lock/v1"
            } else {
                "ariadne.bap-source-flags-lock/v1"
            }
        {
            return Err(invalid("source extension dependency lock schema"));
        }
        let manifest_path = directory.join("manifest.json");
        let manifest_hash = file_hash(&manifest_path, 64 * 1024)?;
        if manifest_hash != lock.manifest_sha256 {
            return Err(invalid(
                "source extension manifest differs from dependency lock",
            ));
        }
        let manifest = crate::reports::strict_json(&std::fs::read(manifest_path)?)?;
        let version_matches = if advanced {
            manifest["schema"] == "ariadne.bap-source-advanced-build/v1"
                && manifest["profiles"]
                    == serde_json::json!([ADVANCED_PROFILE, ADVANCED_GUARDED_PROFILE])
                && manifest["runtime_role"] == "advanced-source-flags"
        } else {
            manifest["schema"] == "ariadne.bap-source-flags-build/v1"
                && manifest["profile"] == PROFILE
                && manifest["runtime_role"] == "explicit-opt-in-four-flag-preparation"
        };
        if !version_matches
            || manifest["executable"] != "flag-lift"
            || manifest["executable_sha256"] != lock.executable_sha256
            || manifest["max_response_bytes"] != MAX_RESPONSE
            || manifest["cases"] != serde_json::json!(["f5", "f8", "f9", "fd"])
        {
            return Err(invalid("source extension manifest scope"));
        }
        for (name, source) in [
            (
                "build.py",
                include_bytes!("../../native/bap/source-coverage/build.py").as_slice(),
            ),
            (
                "flag_lift.ml",
                include_bytes!("../../native/bap/source-coverage/flag_lift.ml").as_slice(),
            ),
            (
                "flag_probe.ml",
                include_bytes!("../../native/bap/source-coverage/flag_probe.ml").as_slice(),
            ),
            (
                "flags.patch",
                include_bytes!("../../native/bap/source-coverage/flags.patch").as_slice(),
            ),
        ] {
            if advanced && name == "flag_lift.ml" {
                continue;
            }
            if manifest["binding"]["sources"][name] != crate::reports::sha256(source) {
                return Err(invalid("source extension source/patch binding differs"));
            }
        }
        if advanced {
            for (name, source) in [
                (
                    "advanced_build.py",
                    include_bytes!("../../native/bap/source-coverage/advanced_build.py").as_slice(),
                ),
                (
                    "advanced_flag_lift.ml",
                    include_bytes!("../../native/bap/source-coverage/advanced_flag_lift.ml")
                        .as_slice(),
                ),
            ] {
                if manifest["binding"]["sources"][name] != crate::reports::sha256(source) {
                    return Err(invalid("advanced source extension source binding differs"));
                }
            }
        }
        if manifest["binding"]["sdk_lock_sha256"]
            != crate::reports::sha256(include_bytes!("../../native/bap-core/sdk.lock.json"))
        {
            return Err(invalid("source extension SDK lock differs"));
        }
        let build_id = manifest["build_id"]
            .as_str()
            .ok_or_else(|| invalid("source build ID"))?
            .to_owned();
        let binding_id = crate::reports::sha256(&serde_json::to_vec(&manifest["binding"])?);
        if build_id != binding_id {
            return Err(invalid("source extension build ID differs"));
        }
        let extension = Self {
            directory: directory.to_owned(),
            manifest_hash,
            executable_hash: lock.executable_sha256,
            build_id,
        };
        extension.validate()?;
        Ok(extension)
    }

    pub(crate) fn validate(&self) -> Result<(), Error> {
        if file_hash(&self.directory.join("manifest.json"), 64 * 1024)? != self.manifest_hash
            || file_hash(&self.directory.join("flag-lift"), 256 * 1024 * 1024)?
                != self.executable_hash
        {
            return Err(invalid("source extension artifact changed"));
        }
        Ok(())
    }

    pub(crate) fn runtime_identity(&self, packaged_runtime: &str) -> String {
        crate::reports::sha256(
            format!(
                "ariadne.bap-source-flags-runtime/v1\n{packaged_runtime}\n{}\n{}\n{}\n",
                self.manifest_hash, self.executable_hash, self.build_id
            )
            .as_bytes(),
        )
    }

    pub(crate) fn supports(bytes: &[u8]) -> bool {
        matches!(bytes, [0xf5 | 0xf8 | 0xf9 | 0xfd])
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
            || va.checked_add(1).is_none()
            || !["windows-amd64", "linux-amd64"].contains(&target)
        {
            return Err(invalid("source extension outside exact flag scope"));
        }
        self.validate()?;
        let snapshot = crate::reports::sha256(snapshot.as_bytes());
        let va = format!("0x{va:016x}");
        let code = format!("{:02x}", bytes[0]);
        let mut child = ManagedChild(
            Command::new(self.directory.join("flag-lift"))
                .args([target, &snapshot, &va, &code])
                .env_remove("LD_LIBRARY_PATH")
                .env_remove("CAML_LD_LIBRARY_PATH")
                .env_remove("LD_PRELOAD")
                .env_remove("LD_AUDIT")
                .stdin(Stdio::null())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()?,
        );
        let output = child
            .0
            .stdout
            .take()
            .ok_or_else(|| invalid("source extension stdout"))?;
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
        let start = Instant::now();
        let output = receiver
            .recv_timeout(timeout)
            .map_err(|_| invalid("source extension response timeout"))?
            .map_err(invalid)?;
        if output.len() > MAX_RESPONSE {
            return Err(invalid("source extension response limit"));
        }
        loop {
            if let Some(status) = child.0.try_wait()? {
                if !status.success() {
                    return Err(invalid("source extension process failed"));
                }
                break;
            }
            if start.elapsed() >= timeout {
                return Err(invalid("source extension exit timeout"));
            }
            std::thread::sleep(Duration::from_millis(2));
        }
        let response: Response = serde_json::from_value(crate::reports::strict_json(&output)?)?;
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
        if response.schema != "ariadne.bap-source-flags/v1"
            || response.build_id != self.build_id
            || response.target != target
            || response.snapshot != snapshot
            || response.va != va
            || response.bytes != code
            || response.length != 1
            || response.bil.len() != 1
        {
            return Err(invalid("source extension response identity/extent differs"));
        }
        super::admission::admit(
            &response.bil,
            "source-flag",
            &[u8::from_str_radix(code, 16)?],
        )?;
        let [Stmt::Move { var, value }] = response.bil.as_slice() else {
            return Err(invalid("source extension must return one flag assignment"));
        };
        let flag = if code == "fd" { "DF" } else { "CF" };
        if var.name != flag
            || var.width != 1
            || var.index != 0
            || var.virtual_
            || var.type_ != "imm"
        {
            return Err(invalid("source extension architectural flag scope"));
        }
        let expression_matches = match (code, value) {
            ("f8", super::ast::Expr::Int { value }) => value == "0:1u",
            ("f9" | "fd", super::ast::Expr::Int { value }) => value == "1:1u",
            ("f5", super::ast::Expr::Unop { op: 0, arg }) => matches!(arg.as_ref(),
                super::ast::Expr::Var { var } if var.name == "CF" && var.width == 1
                    && var.index == 0 && !var.virtual_ && var.type_ == "imm"),
            _ => false,
        };
        if !expression_matches {
            return Err(invalid(
                "source extension BIL differs from qualified flag form",
            ));
        }
        Ok(response.bil)
    }
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
#[path = "../../tests/bap/source_extension.rs"]
mod tests;
