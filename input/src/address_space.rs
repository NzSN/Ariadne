use crate::{FileSnapshot, InputError, malformed};
use ariadne::Address;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CaptureSource {
    pub stream: u32,
    pub entry: usize,
    pub file_offset: u64,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReadSpan {
    pub address: Address,
    pub length: usize,
    pub contributors: Vec<CaptureSource>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ReadStop {
    RequestedLength,
    NotCaptured(Address),
    ConflictingCapture(Address),
    AddressOverflow,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ByteRead {
    /// Contributors at the first conflicting byte, separate from the usable prefix.
    pub conflict_sources: Vec<CaptureSource>,
    pub bytes: Vec<u8>,
    pub spans: Vec<ReadSpan>,
    pub stop: ReadStop,
}
#[derive(Clone, Debug)]
pub(crate) struct Capture {
    pub start: u64,
    pub end: u128,
    pub offset: usize,
    pub source: CaptureSource,
}
#[derive(Debug)]
pub(crate) struct Node {
    index: usize,
    end: u128,
    left: Option<Box<Node>>,
    right: Option<Box<Node>>,
}
impl Node {
    pub(crate) fn build(captures: &[Capture], lo: usize, hi: usize) -> Option<Box<Self>> {
        if lo == hi {
            return None;
        }
        let mid = lo + (hi - lo) / 2;
        let left = Self::build(captures, lo, mid);
        let right = Self::build(captures, mid + 1, hi);
        let end = captures[mid]
            .end
            .max(left.as_ref().map_or(0, |n| n.end))
            .max(right.as_ref().map_or(0, |n| n.end));
        Some(Box::new(Self {
            index: mid,
            end,
            left,
            right,
        }))
    }
    fn contributors(&self, va: u64, captures: &[Capture], found: &mut Vec<usize>) {
        if self.end <= u128::from(va) {
            return;
        }
        if let Some(left) = &self.left {
            left.contributors(va, captures, found);
        }
        let c = &captures[self.index];
        if c.start <= va {
            if u128::from(va) < c.end {
                found.push(self.index);
            }
            if let Some(right) = &self.right {
                right.contributors(va, captures, found);
            }
        }
    }
}

pub(crate) fn index(
    captures: &mut [Capture],
    max_overlap: usize,
) -> Result<Option<Box<Node>>, InputError> {
    captures.sort_by_key(|c| (c.start, c.source.stream, c.source.entry));
    let mut events = Vec::with_capacity(captures.len() * 2);
    for c in captures.iter() {
        events.push((u128::from(c.start), 1i64));
        events.push((c.end, -1));
    }
    events.sort_unstable(); // end events precede start events at adjacent boundaries
    let mut active = 0i64;
    for (_, delta) in events {
        active += delta;
        if active as usize > max_overlap {
            return Err(InputError::Limit("overlapping capture ranges"));
        }
    }
    Ok(Node::build(captures, 0, captures.len()))
}

impl FileSnapshot {
    /// Longest contiguous unambiguous prefix. Missing/conflicting bytes stop the
    /// read; they never become zeros. Identical overlaps retain every contributor.
    pub fn read_prefix(&self, va: Address, max_len: usize) -> Result<ByteRead, InputError> {
        if max_len > self.limits.max_read_bytes {
            return Err(InputError::Limit("read bytes"));
        }
        let mut result = ByteRead {
            conflict_sources: Vec::new(),
            bytes: Vec::new(),
            spans: Vec::new(),
            stop: ReadStop::RequestedLength,
        };
        for i in 0..max_len {
            let Some(at) = va.checked_add(i as u64) else {
                result.stop = ReadStop::AddressOverflow;
                break;
            };
            let mut found = Vec::new();
            if let Some(tree) = &self.tree {
                tree.contributors(at, &self.captures, &mut found);
            }
            if found.is_empty() {
                result.stop = ReadStop::NotCaptured(at);
                break;
            }
            let mut sources = Vec::with_capacity(found.len());
            let mut value = None;
            let mut conflict = false;
            for n in found {
                let c = &self.captures[n];
                let off = c.offset
                    + usize::try_from(at - c.start).map_err(|_| malformed("capture offset"))?;
                let byte = self.bytes[off];
                if value.is_some_and(|v| v != byte) {
                    conflict = true;
                }
                value = Some(byte);
                let mut source = c.source.clone();
                source.file_offset = off as u64;
                sources.push(source);
            }
            if conflict {
                result.conflict_sources = sources;
                result.stop = ReadStop::ConflictingCapture(at);
                break;
            }
            result.bytes.push(value.expect("contributors"));
            let extend = result.spans.last().is_some_and(|span| {
                span.contributors.len() == sources.len()
                    && span.contributors.iter().zip(&sources).all(|(a, b)| {
                        a.stream == b.stream
                            && a.entry == b.entry
                            && a.file_offset + span.length as u64 == b.file_offset
                    })
            });
            if extend {
                result.spans.last_mut().expect("span").length += 1;
            } else {
                result.spans.push(ReadSpan {
                    address: at,
                    length: 1,
                    contributors: sources,
                });
            }
        }
        Ok(result)
    }
}
