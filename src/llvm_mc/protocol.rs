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

pub(crate) fn invoke(path: &Path, input: String, count: usize) -> Result<Vec<Raw>, AdapterError> {
    if exchange(path, "--protocol-version", String::new(), 128)?
        != "ariadne-llvm-mc 20.1.2 protocol 2\n"
    {
        return Err(error("expected LLVM 20.1.2 protocol 2"));
    }
    let cap = count
        .checked_mul(MAX_RECORD)
        .ok_or_else(|| error("batch too large"))?;
    let output = exchange(path, "--protocol=2", input, cap)?;
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
