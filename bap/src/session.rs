use crate::ast::Lift;
use crate::{Error, invalid};
use ariadne::Address;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::time::Duration;

#[derive(Clone, Debug)]
pub struct Config {
    pub helper: PathBuf,
    pub runtime: PathBuf,
    pub timeout: Duration,
}
impl Config {
    pub fn from_env() -> Self {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        Self::new(
            std::env::var_os("ARIADNE_BAP_HELPER")
                .map(PathBuf::from)
                .unwrap_or_else(|| root.join("target/ariadne-bap-lift")),
            std::env::var_os("BAP_RUNTIME_ROOT")
                .map(PathBuf::from)
                .unwrap_or_else(|| root.join("tmp/bap-setup/stable")),
        )
    }
    pub fn new(helper: PathBuf, runtime: PathBuf) -> Self {
        Self {
            helper,
            runtime,
            timeout: Duration::from_secs(10),
        }
    }
    pub fn validate(&self) -> Result<(), Error> {
        let helper = std::fs::metadata(&self.helper)?;
        if !helper.is_file() {
            return Err(invalid("BAP helper must be a file"));
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if helper.permissions().mode() & 0o111 == 0 {
                return Err(invalid("BAP helper is not executable"));
            }
        }
        let lock: serde_json::Value =
            serde_json::from_str(include_str!("../../native/bap/toolchain.lock.json"))?;
        for (relative, digest) in lock["files"]
            .as_object()
            .ok_or_else(|| invalid("invalid BAP lock"))?
        {
            let bytes = std::fs::read(self.runtime.join(relative))?;
            if ariadne_reports::sha256(&bytes) != digest.as_str().unwrap_or("") {
                return Err(invalid(format!(
                    "BAP runtime identity mismatch: {relative}"
                )));
            }
        }
        Ok(())
    }
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Ready {
    schema: String,
    snapshot: String,
    target: String,
    version: String,
    lifter: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Done {
    schema: String,
    batch: usize,
    count: usize,
}
pub struct Session {
    child: Child,
    input: Option<ChildStdin>,
    lines: Receiver<Result<Vec<u8>, String>>,
    snapshot: String,
    target: String,
    next: usize,
    total: usize,
    poisoned: bool,
    timeout: Duration,
    pub(crate) helper_hash: String,
}
fn command(config: &Config) -> Command {
    let mut command = Command::new(&config.helper);
    let local = config.runtime.join("usr/local/lib");
    let ffi = config.runtime.join("usr/lib/x86_64-linux-gnu");
    // This environment is confined to the BAP child; LLVM MC keeps its own ABI.
    command
        .arg(config.runtime.join("usr/local/lib/bap"))
        .env(
            "LD_LIBRARY_PATH",
            format!("{}:{}", local.display(), ffi.display()),
        )
        .env("XDG_STATE_HOME", config.runtime.join("state"))
        .env("XDG_CACHE_HOME", config.runtime.join("cache"));
    command
}
impl Session {
    pub fn start(config: &Config, snapshot_id: &str, target: &str) -> Result<Self, Error> {
        config.validate()?;
        if snapshot_id.is_empty() || !["windows-amd64", "linux-amd64"].contains(&target) {
            return Err(invalid("invalid BAP query identity/target"));
        }
        let helper_hash = ariadne_reports::sha256(&std::fs::read(&config.helper)?);
        let snapshot = ariadne_reports::sha256(snapshot_id.as_bytes());
        let mut child = command(config)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let input = child
            .stdin
            .take()
            .ok_or_else(|| invalid("missing BAP stdin"))?;
        let output = child
            .stdout
            .take()
            .ok_or_else(|| invalid("missing BAP stdout"))?;
        let (sender, lines) = mpsc::sync_channel(256);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(output);
            loop {
                let mut bytes = Vec::new();
                let result = reader
                    .by_ref()
                    .take(4 * 1024 * 1024 + 1)
                    .read_until(b'\n', &mut bytes);
                match result {
                    Ok(0) => break,
                    Ok(_) if bytes.len() > 4 * 1024 * 1024 => {
                        let _ = sender.send(Err("BAP response too large".into()));
                        break;
                    }
                    Ok(_) => {
                        if sender.send(Ok(bytes)).is_err() {
                            break;
                        }
                    }
                    Err(error) => {
                        let _ = sender.send(Err(error.to_string()));
                        break;
                    }
                }
            }
        });
        let mut session = Self {
            child,
            input: Some(input),
            lines,
            snapshot,
            target: target.into(),
            next: 0,
            total: 0,
            poisoned: false,
            timeout: config.timeout,
            helper_hash,
        };
        writeln!(
            session.input.as_mut().unwrap(),
            "ARIADNE-BAP-LIFT 1 {target} {}",
            session.snapshot
        )?;
        session.input.as_mut().unwrap().flush()?;
        let ready: Ready = serde_json::from_value(session.read()?)?;
        if ready.schema != "ariadne.bap-ready/v1"
            || ready.snapshot != session.snapshot
            || ready.target != target
            || ready.version != "2.5.0-alpha"
            || ready.lifter != "legacy"
        {
            return Err(invalid("BAP initialization identity/version mismatch"));
        }
        Ok(session)
    }
    fn read(&self) -> Result<serde_json::Value, Error> {
        let bytes = self
            .lines
            .recv_timeout(self.timeout)
            .map_err(|e| invalid(format!("BAP transport timeout/closed: {e}")))?
            .map_err(invalid)?;
        ariadne_reports::strict_json(&bytes)
    }
    pub(crate) fn lift(
        &mut self,
        candidates: &BTreeMap<Address, Vec<u8>>,
    ) -> Result<BTreeMap<Address, Lift>, Error> {
        if self.poisoned {
            return Err(invalid("BAP session failed; start a fresh query"));
        }
        let result = self.lift_batch(candidates);
        if result.is_err() {
            self.poisoned = true;
            let _ = self.child.kill();
        }
        result
    }
    fn lift_batch(
        &mut self,
        candidates: &BTreeMap<Address, Vec<u8>>,
    ) -> Result<BTreeMap<Address, Lift>, Error> {
        if candidates.is_empty() || candidates.len() > 256 {
            return Err(invalid("invalid BAP batch size"));
        }
        if self.total + candidates.len() > 8192 {
            return Err(invalid("BAP query site budget exceeded"));
        }
        for (&va, bytes) in candidates {
            if bytes.is_empty() || bytes.len() > 15 || va.checked_add(bytes.len() as u64).is_none()
            {
                return Err(invalid("invalid BAP prefix/address"));
            }
        }
        let id = self.next;
        self.next += 1;
        self.total += candidates.len();
        let input = self
            .input
            .as_mut()
            .ok_or_else(|| invalid("closed BAP input"))?;
        writeln!(input, "batch {id} {}", candidates.len())?;
        for (&va, bytes) in candidates {
            if bytes.is_empty() || bytes.len() > 15 || va.checked_add(bytes.len() as u64).is_none()
            {
                return Err(invalid("invalid BAP prefix/address"));
            }
            writeln!(
                input,
                "0x{va:016x} {}",
                bytes.iter().map(|b| format!("{b:02x}")).collect::<String>()
            )?;
        }
        input.flush()?;
        let mut result = BTreeMap::new();
        for (&va, prefix) in candidates {
            let lift: Lift = serde_json::from_value(self.read()?)?;
            lift.validate_ast()?;
            if lift.schema != "ariadne.bap-site/v1"
                || lift.snapshot != self.snapshot
                || lift.batch != id
                || lift.va != format!("0x{va:016x}")
            {
                return Err(invalid("BAP site identity/count/order mismatch"));
            }
            if lift.status == "decoded" {
                if lift.length == 0
                    || lift.length as usize > prefix.len()
                    || lift.bytes
                        != prefix[..lift.length as usize]
                            .iter()
                            .map(|b| format!("{b:02x}"))
                            .collect::<String>()
                    || lift.opcode.is_none()
                    || lift.properties.is_none()
                {
                    return Err(invalid("invalid BAP decoded response"));
                }
            } else if lift.status != "invalid"
                || lift.length != 0
                || !lift.bytes.is_empty()
                || !lift.bil.is_empty()
                || lift.opcode.is_some()
                || lift.properties.is_some()
            {
                return Err(invalid("invalid BAP failure response"));
            }
            result.insert(va, lift);
        }
        let done: Done = serde_json::from_value(self.read()?)?;
        if done.schema != "ariadne.bap-batch/v1"
            || done.batch != id
            || done.count != candidates.len()
        {
            return Err(invalid("BAP batch cardinality mismatch"));
        }
        Ok(result)
    }
    /// Close the request stream and require a clean native exit before publication.
    pub fn finish(mut self) -> Result<(), Error> {
        if self.poisoned {
            return Err(invalid("BAP session failed"));
        }
        self.input.take();
        let start = std::time::Instant::now();
        loop {
            if let Some(status) = self.child.try_wait()? {
                if !status.success() {
                    return Err(invalid(format!("BAP helper failed: {status}")));
                }
                // A completed query must not leave unsolicited output behind.
                match self.lines.recv_timeout(self.timeout) {
                    Err(mpsc::RecvTimeoutError::Disconnected) => return Ok(()),
                    _ => {
                        return Err(invalid(
                            "BAP helper emitted trailing output or failed to close stdout",
                        ));
                    }
                }
            }
            if start.elapsed() >= self.timeout {
                return Err(invalid("BAP helper exit timeout"));
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    pub fn target(&self) -> &str {
        &self.target
    }
}
impl Drop for Session {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
pub fn helper_identity(path: &Path) -> Result<String, Error> {
    Ok(ariadne_reports::sha256(&std::fs::read(path)?))
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    #[test]
    #[ignore = "requires hash-pinned runtime; invokes adversarial helper fixtures"]
    fn malformed_batches_bind_every_site_and_poison_failed_sessions() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .to_path_buf();
        let runtime = std::env::var_os("BAP_RUNTIME_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join("tmp/bap-setup/stable"));
        let folder =
            std::env::temp_dir().join(format!("ariadne-bap-transport-{}", std::process::id()));
        std::fs::create_dir_all(&folder).unwrap();
        let corpus: serde_json::Value =
            serde_json::from_str(include_str!("../tests/fixtures/corpus.json")).unwrap();
        let fixture = folder.join("lift.json");
        std::fs::write(
            &fixture,
            serde_json::to_vec(&corpus["rows"][0]["lift"]).unwrap(),
        )
        .unwrap();
        for mode in [
            "healthy",
            "schema",
            "snapshot",
            "batch",
            "va",
            "bytes",
            "zero-length",
            "long-length",
            "opcode",
            "properties",
            "width",
            "extract",
            "extra-field",
            "duplicate-field",
            "missing-row",
            "wrong-count",
            "duplicate-row",
            "oversized",
            "timeout",
            "trailer",
            "exit",
        ] {
            let path = folder.join(format!("{mode}.py"));
            let program = r#"#!/usr/bin/env python3
import sys,json,time
mode='MODE'
lift=json.load(open('FIXTURE'))
header=sys.stdin.readline().split()
ready=dict(schema='ariadne.bap-ready/v1',target=header[2],snapshot=header[3],version='2.5.0-alpha',lifter='legacy')
print(json.dumps(ready),flush=True)
batch=sys.stdin.readline().split();rows=[sys.stdin.readline().split() for _ in range(int(batch[2]))]
if mode=='missing-row':sys.exit(0)
if mode=='timeout':time.sleep(2);sys.exit(0)
if mode=='oversized':print('x'*4194305,flush=True);sys.exit(0)
for i,row in enumerate(rows):
 value=dict(lift,snapshot=header[3],batch=int(batch[1]),va=row[0],bytes=row[1])
 if mode in ('schema','snapshot','va','bytes'):value[mode]='wrong'
 if mode=='batch':value['batch']=99
 if mode=='zero-length':value['length']=0
 if mode=='long-length':value['length']=16
 if mode in ('opcode','properties'):value[mode]=None
 if mode=='width':value['bil'][0]['var']['width']=99999999
 if mode=='extract':value['bil'][0]['value']=dict(kind='extract',hi=0,lo=63,arg=lift['bil'][0]['value'])
 if mode=='extra-field':value['extra']=True
 if mode=='duplicate-row' and i==1:value['va']=rows[0][0]
 text=json.dumps(value)
 if mode=='duplicate-field':text=text[:-1]+',"va":"duplicate"}'
 print(text,flush=True)
print(json.dumps(dict(schema='ariadne.bap-batch/v1',batch=int(batch[1]),count=999 if mode=='wrong-count' else len(rows))),flush=True)
if mode=='trailer':print('{}',flush=True)
if mode=='exit':sys.exit(3)
for _ in sys.stdin:pass
"#;
            let program = program
                .replace("MODE", mode)
                .replace("FIXTURE", fixture.to_str().unwrap());
            std::fs::write(&path, program).unwrap();
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
            let mut config = Config::new(path, runtime.clone());
            config.timeout = Duration::from_millis(500);
            let mut session = Session::start(&config, "fixture", "linux-amd64").unwrap();
            let mut candidates: BTreeMap<_, _> = [(0x1000, vec![0x48, 0x89, 0xd8])].into();
            if mode == "duplicate-row" {
                candidates.insert(0x1020, vec![0x48, 0x89, 0xd8]);
            }
            let response = session.lift(&candidates);
            if ["healthy", "trailer", "exit"].contains(&mode) {
                assert!(response.is_ok(), "{mode}: {response:?}");
                assert_eq!(session.finish().is_ok(), mode == "healthy", "{mode}");
            } else {
                assert!(response.is_err(), "{mode}: invalid batch was accepted");
                assert!(
                    session.lift(&candidates).is_err(),
                    "failed session was reused"
                );
            }
        }
        std::fs::remove_dir_all(folder).unwrap();
    }
}
