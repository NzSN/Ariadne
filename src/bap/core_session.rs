//! Process-per-query transport for the experimental OCaml recovery bootstrap.
use super::core_protocol::{
    CAPTURED_PROFILE, FamilyObservation, FamilyResponse, MAX_FRAME, Observation, PROFILE,
    StateflowObservation, profile_query_digest,
};
use super::{Error, invalid};
use serde_json::{Value, json};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, SyncSender};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

#[derive(Clone)]
pub struct CoreConfig {
    pub helper: PathBuf,
    pub manifest: PathBuf,
    pub timeout: Duration,
}
impl CoreConfig {
    pub fn from_directory(directory: PathBuf) -> Self {
        Self {
            helper: directory.join("ariadne-bap-core"),
            manifest: directory.join("manifest.json"),
            timeout: Duration::from_secs(10),
        }
    }
}
pub type CoreSession = FamilySession<Observation>;
pub type StateflowSession = FamilySession<StateflowObservation>;
pub struct FamilySession<O: FamilyObservation> {
    observation_type: std::marker::PhantomData<O>,
    child: Child,
    writes: Option<SyncSender<Vec<u8>>>,
    written: Receiver<Result<(), String>>,
    lines: Receiver<Result<Vec<u8>, String>>,
    workers: Vec<JoinHandle<()>>,
    snapshot: String,
    query: String,
    session: String,
    sequence: u64,
    action_index: u64,
    timeout: Duration,
    closed: bool,
    identity: Value,
    last_observation: Option<Vec<u8>>,
}
impl<O: FamilyObservation> FamilySession<O> {
    pub fn identity(&self) -> &Value {
        &self.identity
    }
    pub fn start(
        config: &CoreConfig,
        session: &str,
        snapshot: &str,
        input: &Value,
    ) -> Result<(Self, FamilyResponse<O>), Error> {
        Self::start_profile(config, session, snapshot, PROFILE, input)
    }
    pub fn start_profile(
        config: &CoreConfig,
        session: &str,
        snapshot: &str,
        profile: &str,
        input: &Value,
    ) -> Result<(Self, FamilyResponse<O>), Error> {
        if ![PROFILE, CAPTURED_PROFILE].contains(&profile)
            || (O::FAMILY != "recovery" && profile != PROFILE)
        {
            return Err(invalid("unsupported core input profile"));
        }
        if session.is_empty() || snapshot.is_empty() {
            return Err(invalid("empty core identity"));
        }
        let manifest: Value = serde_json::from_slice(&std::fs::read(&config.manifest)?)?;
        if manifest["schema"] != "ariadne.bap-core-build/v1"
            || manifest["helper_sha256"] != crate::reports::sha256(&std::fs::read(&config.helper)?)
        {
            return Err(invalid("core helper manifest mismatch"));
        }
        let handshake = &manifest["handshake"];
        if handshake["schema"] != "ariadne.bap-core-ready/v1"
            || handshake["abi"] != 2
            || handshake["families"] != json!(["recovery", "stateflow"])
            || handshake["profiles"] != json!([PROFILE, CAPTURED_PROFILE])
            || handshake["operations"] != json!(super::core_protocol::RECOVERY_OPERATIONS)
            || handshake["max_frame_bytes"] != MAX_FRAME
        {
            return Err(invalid("unsupported core handshake capabilities"));
        }
        let query = profile_query_digest(snapshot, O::FAMILY, profile, input)?;
        let mut command = Command::new(&config.helper);
        for key in [
            "OPAMROOT",
            "OPAMSWITCH",
            "OPAM_SWITCH_PREFIX",
            "OCAMLPATH",
            "OCAMLLIB",
            "CAML_LD_LIBRARY_PATH",
            "OCAML_TOPLEVEL_PATH",
            "OCAMLTOP_INCLUDE_PATH",
            "LD_LIBRARY_PATH",
            "LD_PRELOAD",
        ] {
            command.env_remove(key);
        }
        let mut child = command
            .args([session, snapshot, &query, O::FAMILY])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| invalid("missing core stdin"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| invalid("missing core stdout"))?;
        let (writes, write_requests) = mpsc::sync_channel::<Vec<u8>>(1);
        let (write_results, written) = mpsc::sync_channel(1);
        let writer = std::thread::spawn(move || {
            while let Ok(bytes) = write_requests.recv() {
                let result = stdin
                    .write_all(&bytes)
                    .and_then(|_| stdin.flush())
                    .map_err(|e| e.to_string());
                let failed = result.is_err();
                if write_results.try_send(result).is_err() || failed {
                    break;
                }
            }
        });
        let (sender, lines) = mpsc::sync_channel(2);
        let reader = std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut bytes = Vec::new();
                let result = match reader
                    .by_ref()
                    .take((MAX_FRAME + 1) as u64)
                    .read_until(b'\n', &mut bytes)
                {
                    Ok(_) if bytes.len() > MAX_FRAME => Err("core frame oversized".into()),
                    Ok(_) if bytes.last() != Some(&b'\n') => Err("core partial frame/EOF".into()),
                    Ok(_) => Ok(bytes),
                    Err(e) => Err(e.to_string()),
                };
                let failed = result.is_err();
                if sender.try_send(result).is_err() || failed {
                    break;
                }
            }
        });
        let mut this = Self {
            observation_type: std::marker::PhantomData,
            child,
            writes: Some(writes),
            written,
            lines,
            workers: vec![writer, reader],
            snapshot: snapshot.into(),
            query: query.clone(),
            session: session.into(),
            sequence: 0,
            action_index: 0,
            timeout: config.timeout,
            closed: false,
            last_observation: None,
            identity: json!({"schema":"ariadne.analysis-backend/v1","backend":"bap",
                "snapshot":snapshot,"query":query,"family":O::FAMILY,"profile":profile,
                "build":manifest}),
        };
        let ready: Value = serde_json::from_slice(&this.read()?)?;
        if &ready != handshake {
            return Err(invalid("core handshake identity mismatch"));
        }
        let response = this.request("initialize", json!({"profile":profile,"input":input}))?;
        Ok((this, response))
    }
    pub fn process_id(&self) -> u32 {
        self.child.id()
    }
    fn read(&self) -> Result<Vec<u8>, Error> {
        self.lines
            .recv_timeout(self.timeout)
            .map_err(|e| invalid(format!("core response: {e}")))?
            .map_err(invalid)
    }
    /// Semantic rejections are returned with unchanged state. Protocol failures
    /// kill/reap the process and permanently close this session.
    pub fn request(&mut self, operation: &str, payload: Value) -> Result<FamilyResponse<O>, Error> {
        if self.closed {
            return Err(invalid("core session closed/poisoned"));
        }
        let result = self.exchange(operation, payload);
        if result.is_err() {
            self.terminate();
        }
        result
    }
    fn exchange_frame(&self, operation: &str, payload: Value) -> Result<Vec<u8>, Error> {
        let request = json!({"schema":"ariadne.bap-core/v1", "session":self.session,
            "snapshot":self.snapshot,"query":self.query,"family":O::FAMILY,
            "sequence":self.sequence,"operation":operation,"payload":payload});
        let mut bytes = serde_json::to_vec(&request)?;
        bytes.push(b'\n');
        if bytes.len() > MAX_FRAME {
            return Err(invalid("core request oversized"));
        }
        self.writes
            .as_ref()
            .ok_or_else(|| invalid("core closed"))?
            .try_send(bytes)
            .map_err(|e| invalid(e.to_string()))?;
        self.written
            .recv_timeout(self.timeout)
            .map_err(|e| invalid(format!("core write: {e}")))?
            .map_err(invalid)?;
        self.read()
    }
    fn exchange(&mut self, operation: &str, payload: Value) -> Result<FamilyResponse<O>, Error> {
        let raw = self.exchange_frame(operation, payload)?;
        let response: FamilyResponse<O> = serde_json::from_slice(&raw)?;
        if response.schema != "ariadne.bap-core/v1"
            || response.session != self.session
            || response.snapshot != self.snapshot
            || response.query != self.query
            || response.family != O::FAMILY
            || response.sequence != self.sequence
            || response.generation != 1
        {
            return Err(invalid("core response identity/sequence mismatch"));
        }
        let changed = matches!(operation, "advance" | "step") && response.error.is_none();
        let expected_index = self.action_index + u64::from(changed);
        if response.changed != changed || response.action_index != expected_index {
            return Err(invalid("core action index/change mismatch"));
        }
        let state = &response.observation;
        state.validate_shape()?;
        // Retain the exact previously validated frame, avoiding a deep clone of
        // every definition string after every action. Read-only responses still
        // undergo the same complete semantic equality check.
        if !changed {
            if let Some(old) = &self.last_observation {
                let old: FamilyResponse<O> = serde_json::from_slice(old)?;
                if &old.observation != state {
                    return Err(invalid(
                        "read-only or rejected operation mutated native state",
                    ));
                }
            }
        }
        if O::FAMILY == "stateflow" && !response.attribution.is_empty() {
            return Err(invalid("stateflow cannot invent machine term attribution"));
        }
        if operation == "reset" && response.error.is_some() {
            return Err(invalid(
                "native reset rejected; completion cannot be published",
            ));
        }
        if operation == "finish" && response.error.is_none() {
            if state.phase() != "done"
                || response
                    .result
                    .as_ref()
                    .is_none_or(|r| r.snapshot != self.snapshot)
            {
                return Err(invalid("core unfinished/unbound result"));
            }
        } else if response.result.is_some() {
            return Err(invalid("unsolicited core result"));
        }
        self.last_observation = Some(raw);
        self.sequence += 1;
        self.action_index = expected_index;
        if operation == "reset" && response.error.is_none() {
            self.wait_clean()?;
        }
        Ok(response)
    }
    fn wait_clean(&mut self) -> Result<(), Error> {
        self.writes.take();
        let start = Instant::now();
        loop {
            if let Some(status) = self.child.try_wait()? {
                if !status.success() {
                    return Err(invalid(format!("core exit: {status}")));
                }
                self.closed = true;
                for worker in self.workers.drain(..) {
                    let _ = worker.join();
                }
                return Ok(());
            }
            if start.elapsed() >= self.timeout {
                return Err(invalid("core shutdown timeout"));
            }
            std::thread::sleep(Duration::from_millis(2));
        }
    }
    fn terminate(&mut self) {
        self.writes.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
        self.closed = true;
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
    }
}
impl FamilySession<Observation> {
    fn completion_request(
        &mut self,
        operation: &str,
        payload: Value,
    ) -> Result<super::core_protocol::CompletionResponse, Error> {
        if self.closed {
            return Err(invalid("core session closed/poisoned"));
        }
        let raw = self.exchange_frame(operation, payload)?;
        let response: super::core_protocol::CompletionResponse = serde_json::from_slice(&raw)?;
        if response.schema != "ariadne.bap-core-completion/v1"
            || response.session != self.session
            || response.snapshot != self.snapshot
            || response.query != self.query
            || response.family != "recovery"
            || response.sequence != self.sequence
            || response.generation != 1
            || response.advanced > 64
            || (operation != "run-batch" && response.advanced != 0)
            || response.action_index != self.action_index + response.advanced
            || response.action_index > 1_000_000
            || response.closed != (operation == "result-close")
            || response.total_bytes > super::core_protocol::MAX_COMPLETED_BYTES
        {
            return Err(invalid("completion identity/counter/budget mismatch"));
        }
        if let Some(error) = &response.error {
            return Err(invalid(error.message.clone()));
        }
        self.sequence += 1;
        self.action_index = response.action_index;
        Ok(response)
    }
    /// Executes the same scheduled actions natively and retrieves one immutable
    /// final envelope through bounded pages. No partial observation is exposed.
    pub fn finish_paged(&mut self) -> Result<FamilyResponse<Observation>, Error> {
        let result = self.finish_paged_inner();
        if result.is_err() {
            self.terminate();
        }
        result
    }
    fn finish_paged_inner(&mut self) -> Result<FamilyResponse<Observation>, Error> {
        use super::core_protocol::{COMPLETION_PAGE_BYTES, completion_checksum};
        let metadata = loop {
            let response = self.completion_request("run-batch", json!({"steps":64}))?;
            if !response.data_hex.is_empty() || response.offset != 0 {
                return Err(invalid("unsolicited completion data"));
            }
            if response.done {
                if response.total_bytes == 0
                    || response.checksum.len() != 16
                    || response.result_sequence.checked_add(1) != Some(self.sequence)
                {
                    return Err(invalid("invalid completed result metadata"));
                }
                break response;
            }
            if response.advanced == 0
                || response.total_bytes != 0
                || response.result_sequence != 0
                || !response.checksum.is_empty()
            {
                return Err(invalid("invalid completion progress"));
            }
        };
        let mut bytes = Vec::with_capacity(metadata.total_bytes);
        while bytes.len() < metadata.total_bytes {
            let page = self.completion_request("result-page", json!({"offset":bytes.len()}))?;
            if !page.done
                || page.offset != bytes.len()
                || page.total_bytes != metadata.total_bytes
                || page.checksum != metadata.checksum
                || page.result_sequence != metadata.result_sequence
                || page.action_index != metadata.action_index
                || page.data_hex.is_empty()
                || page.data_hex.len() % 2 != 0
                || page.data_hex.len() > COMPLETION_PAGE_BYTES * 2
                || page.data_hex.len() / 2 > metadata.total_bytes - bytes.len()
            {
                return Err(invalid("completion page order/size/binding mismatch"));
            }
            for pair in page.data_hex.as_bytes().chunks_exact(2) {
                let nibble = |byte| match byte {
                    b'0'..=b'9' => Ok(byte - b'0'),
                    b'a'..=b'f' => Ok(byte - b'a' + 10),
                    _ => Err(invalid("noncanonical completion hex")),
                };
                bytes.push(nibble(pair[0])? * 16 + nibble(pair[1])?);
            }
        }
        if completion_checksum(&bytes) != metadata.checksum {
            return Err(invalid("completed result checksum mismatch"));
        }
        let response: FamilyResponse<Observation> = serde_json::from_slice(&bytes)?;
        if response.schema != "ariadne.bap-core/v1"
            || response.session != self.session
            || response.snapshot != self.snapshot
            || response.query != self.query
            || response.family != "recovery"
            || response.sequence != metadata.result_sequence
            || response.generation != 1
            || response.action_index != metadata.action_index
            || response.changed
            || response.error.is_some()
            || response.observation.phase != "done"
            || response
                .result
                .as_ref()
                .is_none_or(|result| result.snapshot != self.snapshot)
        {
            return Err(invalid("completed envelope identity/state mismatch"));
        }
        response.observation.validate_shape()?;
        let closed = self.completion_request("result-close", json!({}))?;
        if !closed.done
            || closed.offset != 0
            || closed.total_bytes != metadata.total_bytes
            || closed.checksum != metadata.checksum
            || closed.result_sequence != metadata.result_sequence
            || !closed.data_hex.is_empty()
            || closed.action_index != metadata.action_index
        {
            return Err(invalid("completion close binding mismatch"));
        }
        self.wait_clean()?;
        Ok(response)
    }
}
impl<O: FamilyObservation> Drop for FamilySession<O> {
    fn drop(&mut self) {
        if !self.closed {
            self.terminate();
        }
    }
}
