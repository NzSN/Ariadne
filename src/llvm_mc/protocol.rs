use super::{AdapterError, Decoded, decode_row};
use std::io::{Read, Write};
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::time::Duration;

pub(crate) const MAX_RECORD: usize = 4096;
#[derive(Clone, Debug)]
pub(crate) enum RawOperand {
    Register(String),
    Immediate(i64),
    Unsupported,
}
pub(crate) struct Raw {
    pub opcode: String,
    pub operands: Vec<RawOperand>,
    pub decoded: Decoded,
    pub record: String,
}
fn error(message: &str) -> AdapterError {
    AdapterError::DecoderProtocol(message.into())
}

#[cfg(feature = "bap")]
pub(crate) struct ReferenceSession {
    child: std::process::Child,
    writes: Option<std::sync::mpsc::SyncSender<Vec<u8>>>,
    written: std::sync::mpsc::Receiver<Result<(), String>>,
    lines: Option<std::sync::mpsc::Receiver<Result<Vec<u8>, String>>>,
    workers: Vec<std::thread::JoinHandle<()>>,
    closed: bool,
    timeout: Duration,
}
#[cfg(feature = "bap")]
impl ReferenceSession {
    pub(crate) fn start(path: &Path, target: super::DecoderTarget) -> Result<Self, AdapterError> {
        Self::start_with_timeout(path, target, Duration::from_secs(30))
    }
    fn start_with_timeout(
        path: &Path,
        target: super::DecoderTarget,
        timeout: Duration,
    ) -> Result<Self, AdapterError> {
        use std::io::{BufRead, BufReader};
        use std::sync::mpsc;
        let (arg, header) = match target {
            super::DecoderTarget::WindowsAmd64 => (
                "--protocol=2-checked",
                "ariadne-llvm-mc 20.1.2 protocol 2\n",
            ),
            super::DecoderTarget::LinuxAmd64 => (
                "--protocol=2-checked-linux",
                "ariadne-llvm-mc 20.1.2 protocol 2 target x86_64-unknown-linux-gnu\n",
            ),
        };
        let mut child = Command::new(path)
            .arg(arg)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        let mut stdin = child.stdin.take().expect("piped");
        let stdout = child.stdout.take().expect("piped");
        let (writes, requests) = mpsc::sync_channel::<Vec<u8>>(1);
        let (result_tx, written) = mpsc::sync_channel(1);
        let writer = std::thread::spawn(move || {
            while let Ok(bytes) = requests.recv() {
                let result = stdin
                    .write_all(&bytes)
                    .and_then(|_| stdin.flush())
                    .map_err(|e| e.to_string());
                let failed = result.is_err();
                if result_tx.try_send(result).is_err() || failed {
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
                    .take((MAX_RECORD + 1) as u64)
                    .read_until(b'\n', &mut bytes)
                {
                    Ok(0) => Err("decoder EOF".into()),
                    Ok(_) if bytes.len() > MAX_RECORD => Err("decoder row oversized".into()),
                    Ok(_) if bytes.last() != Some(&b'\n') => Err("decoder partial row".into()),
                    Ok(_) => Ok(bytes),
                    Err(e) => Err(e.to_string()),
                };
                let failed = result.is_err();
                if sender.send(result).is_err() || failed {
                    break;
                }
            }
        });
        let session = Self {
            child,
            writes: Some(writes),
            written,
            lines: Some(lines),
            workers: vec![writer, reader],
            closed: false,
            timeout,
        };
        let ready = session.read_line()?;
        if ready != header.as_bytes() {
            return Err(error("expected LLVM 20.1.2 checked streaming header"));
        }
        Ok(session)
    }
    fn read_line(&self) -> Result<Vec<u8>, AdapterError> {
        self.lines
            .as_ref()
            .ok_or_else(|| error("decoder session closed"))?
            .recv_timeout(self.timeout)
            .map_err(|_| error("decoder stream timeout/disconnect"))?
            .map_err(AdapterError::DecoderProtocol)
    }
    pub(crate) fn batch(&mut self, input: String, count: usize) -> Result<Vec<Raw>, AdapterError> {
        if self.closed {
            return Err(error("decoder session closed/poisoned"));
        }
        let result = self.exchange(input, count);
        if result.is_err() {
            self.terminate();
        }
        result
    }
    fn exchange(&mut self, input: String, count: usize) -> Result<Vec<Raw>, AdapterError> {
        self.writes
            .as_ref()
            .ok_or_else(|| error("decoder session closed"))?
            .try_send(input.into_bytes())
            .map_err(|_| error("decoder write queue unavailable"))?;
        let mut rows = Vec::new();
        for _ in 0..count {
            let bytes = self.read_line()?;
            let row = std::str::from_utf8(&bytes).map_err(|_| error("non-UTF-8 decoder output"))?;
            rows.push(parse(
                row.strip_suffix('\n')
                    .ok_or_else(|| error("unterminated decoder row"))?,
            )?);
        }
        self.written
            .recv_timeout(self.timeout)
            .map_err(|_| error("decoder write timeout/disconnect"))?
            .map_err(AdapterError::DecoderProtocol)?;
        Ok(rows)
    }
    pub(crate) fn finish(mut self) -> Result<(), AdapterError> {
        self.writes.take();
        let start = std::time::Instant::now();
        let mut eof = false;
        loop {
            while let Ok(row) = self.lines.as_ref().expect("open decoder").try_recv() {
                match row {
                    Err(s) if s == "decoder EOF" => eof = true,
                    _ => return Err(error("decoder unsolicited/partial trailing output")),
                }
            }
            if let Some(status) = self.child.try_wait()? {
                if !status.success() {
                    return Err(error("decoder did not exit cleanly"));
                }
                break;
            }
            if start.elapsed() >= self.timeout {
                return Err(error("decoder exit timeout"));
            }
            std::thread::sleep(Duration::from_millis(1));
        }
        if !eof {
            match self
                .lines
                .as_ref()
                .expect("open decoder")
                .recv_timeout(self.timeout)
            {
                Ok(Err(s)) if s == "decoder EOF" => {}
                _ => return Err(error("decoder unsolicited/partial trailing output")),
            }
        }
        self.lines.take();
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
        self.closed = true;
        Ok(())
    }
    fn terminate(&mut self) {
        self.closed = true;
        self.writes.take();
        self.lines.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
        for worker in self.workers.drain(..) {
            let _ = worker.join();
        }
    }
}
#[cfg(feature = "bap")]
impl Drop for ReferenceSession {
    fn drop(&mut self) {
        if !self.closed {
            self.terminate();
        }
    }
}

// All streams are drained concurrently. Any limit/error kills and reaps the
// child; stdout and stderr cannot block each other after one reader exits.
fn exchange(path: &Path, arg: &str, input: String, cap: usize) -> Result<String, AdapterError> {
    let mut child = Command::new(path)
        .arg(arg)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let mut stdin = child.stdin.take().expect("piped");
    let stdout = child.stdout.take().expect("piped");
    let stderr = child.stderr.take().expect("piped");
    let (tx, rx) = mpsc::channel();
    let mut handles = Vec::new();
    for (id, reader, limit) in [
        (0, Box::new(stdout) as Box<dyn Read + Send>, cap),
        (1, Box::new(stderr) as Box<dyn Read + Send>, 4096),
    ] {
        let tx = tx.clone();
        handles.push(std::thread::spawn(move || {
            let mut bytes = Vec::new();
            let result = reader
                .take(limit as u64 + 1)
                .read_to_end(&mut bytes)
                .map_err(AdapterError::DecoderIo)
                .and_then(|_| {
                    if bytes.len() > limit {
                        Err(error("decoder output limit exceeded"))
                    } else {
                        Ok(bytes)
                    }
                });
            let _ = tx.send((id, result));
        }));
    }
    handles.push(std::thread::spawn(move || {
        let result = stdin
            .write_all(input.as_bytes())
            .map(|_| Vec::new())
            .map_err(AdapterError::DecoderIo);
        drop(stdin);
        let _ = tx.send((2, result));
    }));
    let mut output = Vec::new();
    let mut diagnostic = Vec::new();
    let mut failure = None;
    let deadline = std::time::Instant::now() + Duration::from_secs(30);
    for _ in 0..3 {
        match rx.recv_timeout(deadline.saturating_duration_since(std::time::Instant::now())) {
            Ok((id, Ok(bytes))) => match id {
                0 => output = bytes,
                1 => diagnostic = bytes,
                _ => {}
            },
            Ok((_, Err(err))) => {
                failure = Some(err);
                break;
            }
            Err(_) => {
                failure = Some(error("decoder stream timeout"));
                break;
            }
        }
    }
    if failure.is_some() {
        let _ = child.kill();
    }
    // A process can close all streams without exiting. Bound that wait too.
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if std::time::Instant::now() >= deadline {
            let _ = child.kill();
            failure.get_or_insert(error("decoder exit timeout"));
            break child.wait()?;
        }
        std::thread::sleep(Duration::from_millis(5));
    };
    for handle in handles {
        let _ = handle.join();
    }
    if let Some(err) = failure {
        return Err(err);
    }
    if !status.success() {
        return Err(AdapterError::DecoderFailure(
            String::from_utf8_lossy(&diagnostic).into_owned(),
        ));
    }
    String::from_utf8(output).map_err(|_| error("non-UTF-8 decoder output"))
}

pub(crate) fn invoke(
    path: &Path,
    input: String,
    count: usize,
    target: super::DecoderTarget,
) -> Result<Vec<Raw>, AdapterError> {
    let (decode_arg, expected) = match target {
        super::DecoderTarget::WindowsAmd64 => (
            "--protocol=2-checked",
            "ariadne-llvm-mc 20.1.2 protocol 2\n",
        ),
        super::DecoderTarget::LinuxAmd64 => (
            "--protocol=2-checked-linux",
            "ariadne-llvm-mc 20.1.2 protocol 2 target x86_64-unknown-linux-gnu\n",
        ),
    };
    let cap = count
        .checked_mul(MAX_RECORD)
        .and_then(|cap| cap.checked_add(128))
        .ok_or_else(|| error("batch too large"))?;
    let output = exchange(path, decode_arg, input, cap)?;
    let output = output
        .strip_prefix(expected)
        .ok_or_else(|| error("expected LLVM 20.1.2 protocol 2 checked header"))?;
    if !output.is_empty() && !output.ends_with('\n') {
        return Err(error("unterminated record"));
    }
    let rows: Vec<_> = output.lines().collect();
    if rows.len() != count {
        return Err(error("decoder record count mismatch"));
    }
    rows.into_iter().map(parse).collect()
}
fn token<'a>(tokens: &mut impl Iterator<Item = &'a str>) -> Result<&'a str, AdapterError> {
    tokens.next().ok_or_else(|| error("truncated v2 record"))
}
fn count<'a>(tokens: &mut impl Iterator<Item = &'a str>) -> Result<usize, AdapterError> {
    let n = token(tokens)?
        .parse::<usize>()
        .map_err(|_| error("invalid count"))?;
    if n > 32 {
        Err(error("count exceeds 32"))
    } else {
        Ok(n)
    }
}
fn name(s: &str) -> bool {
    !s.is_empty() && s.len() <= 96 && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
}
pub(crate) fn parse(row: &str) -> Result<Raw, AdapterError> {
    if row.len() >= MAX_RECORD {
        return Err(error("record too long"));
    }
    let mut t = row.split_ascii_whitespace();
    if token(&mut t)? != "v2" {
        return Err(error("wrong record schema"));
    }
    let opcode = token(&mut t)?.to_string();
    if opcode != "-" && !name(&opcode) {
        return Err(error("invalid opcode"));
    }
    let n = count(&mut t)?;
    let mut operands = Vec::new();
    for _ in 0..n {
        let s = token(&mut t)?;
        operands.push(if let Some(s) = s.strip_prefix("r:").filter(|s| name(s)) {
            RawOperand::Register(s.into())
        } else if let Some(s) = s.strip_prefix("i:") {
            RawOperand::Immediate(s.parse().map_err(|_| error("invalid immediate"))?)
        } else if s == "x:unsupported" {
            RawOperand::Unsupported
        } else {
            return Err(error("invalid operand tag"));
        });
    }
    let defs = count(&mut t)?;
    if defs > n {
        return Err(error("definition count exceeds operands"));
    }
    let flags = count(&mut t)?;
    if flags > 7 {
        return Err(error("invalid descriptor flags"));
    }
    let mut implicit_count = 0;
    for _ in 0..2 {
        let n = count(&mut t)?;
        implicit_count += n;
        for _ in 0..n {
            if !name(token(&mut t)?) {
                return Err(error("invalid implicit register"));
            }
        }
    }
    for i in 0..n {
        let tied = token(&mut t)?
            .parse::<i32>()
            .map_err(|_| error("invalid tie"))?;
        if tied < -1 || tied >= n as i32 || tied == i as i32 {
            return Err(error("invalid tied operand index"));
        }
    }
    let tail = t.collect::<Vec<_>>().join(" ");
    let decoded = decode_row(&tail)?;
    match decoded.status.as_str() {
        "invalid"
            if decoded.length == 0
                && decoded.kind.is_none()
                && decoded.target.is_none()
                && opcode == "-"
                && n == 0
                && defs == 0
                && flags == 0
                && implicit_count == 0 => {}
        "ok" if (1..=15).contains(&decoded.length) && opcode != "-" && decoded.kind.is_some() => {}
        "unsupported"
            if (1..=15).contains(&decoded.length)
                && opcode != "-"
                && decoded.kind.is_none()
                && decoded.target.is_none() => {}
        _ => return Err(error("contradictory decode status")),
    }
    Ok(Raw {
        opcode,
        operands,
        decoded,
        record: row.into(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_malformed_records() {
        let valid = "v2 MOV64rr 2 r:RAX r:RBX 1 0 0 0 -1 -1 4096 ok 3 ordinary -";
        assert!(parse(valid).is_ok());
        for broken in [
            valid.replace("v2", "v3"),
            valid.replace("r:RAX", "q:RAX"),
            valid.replace("2 r:", "33 r:"),
            valid.replace("-1 -1", "2 -1"),
            valid.replace("ok 3", "invalid 3"),
            format!("{valid} extra"),
            valid.replace("1 0 0 0", "3 0 0 0"),
            valid.replace("MOV64rr", "-"),
        ] {
            assert!(parse(&broken).is_err(), "{broken}");
        }
    }
}

#[cfg(all(test, feature = "bap", unix))]
mod streaming_tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    struct Helper(std::path::PathBuf);
    impl Helper {
        fn new(body: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "ariadne-reference-stream-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            std::fs::create_dir(&dir).unwrap();
            let file = dir.join("helper.py");
            std::fs::write(
                &file,
                format!("#!/usr/bin/env python3\nimport sys,time\n{body}\n"),
            )
            .unwrap();
            std::fs::set_permissions(&file, std::fs::Permissions::from_mode(0o700)).unwrap();
            Self(file)
        }
        fn start(&self) -> Result<ReferenceSession, AdapterError> {
            ReferenceSession::start_with_timeout(
                &self.0,
                super::super::DecoderTarget::WindowsAmd64,
                Duration::from_millis(500),
            )
        }
    }
    impl Drop for Helper {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(self.0.parent().unwrap());
        }
    }
    const HEADER: &str = "print('ariadne-llvm-mc 20.1.2 protocol 2',flush=True)";
    const ROW: &str = "v2 MOV64rr 2 r:RAX r:RBX 1 0 0 0 -1 -1 4096 ok 3 ordinary -";
    #[test]
    fn checked_stream_rejects_bad_header_and_bounded_failures() {
        for body in [
            "print('wrong',flush=True)",
            "print('ariadne-llvm-mc 20.1.2 protocol 2 target x86_64-unknown-linux-gnu',flush=True)",
            "time.sleep(5)",
        ] {
            let helper = Helper::new(body);
            assert!(helper.start().is_err());
        }
        for bad in [
            "print('malformed',flush=True)".to_string(),
            "print('x'*4097,flush=True)".into(),
            "sys.stdout.write('partial');sys.stdout.flush()".into(),
            "sys.exit(0)".into(),
            "time.sleep(5)".into(),
        ] {
            let helper = Helper::new(&format!("{HEADER}\nsys.stdin.readline()\n{bad}"));
            let mut session = helper.start().unwrap();
            assert!(session.batch("4096 4889d8\n".into(), 1).is_err());
            assert!(session.closed);
            assert!(session.child.try_wait().unwrap().is_some());
            assert!(session.batch("4096 4889d8\n".into(), 1).is_err());
        }
    }
    #[test]
    fn checked_stream_requires_clean_shutdown_without_trailing_rows() {
        for tail in [
            "print('extra',flush=True)",
            "sys.stdout.write('partial');sys.stdout.flush()",
            "sys.exit(7)",
            "time.sleep(5)",
        ] {
            let helper = Helper::new(&format!(
                "{HEADER}\nsys.stdin.readline()\nprint({ROW:?},flush=True)\nsys.stdin.read()\n{tail}"
            ));
            let mut session = helper.start().unwrap();
            assert_eq!(session.batch("4096 4889d8\n".into(), 1).unwrap().len(), 1);
            assert!(session.finish().is_err());
        }
        let helper = Helper::new(&format!(
            "{HEADER}\nfor line in sys.stdin:\n print({ROW:?},flush=True)"
        ));
        let mut session = helper.start().unwrap();
        for _ in 0..3 {
            assert_eq!(session.batch("4096 4889d8\n".into(), 1).unwrap().len(), 1);
        }
        session.finish().unwrap();
    }
}
