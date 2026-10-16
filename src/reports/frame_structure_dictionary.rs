//! Content-addressed JSON trees for self-contained structural evidence.
use super::{Error, invalid};
use crate::investigation::FrameStructureLimits;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub(super) enum Node {
    Scalar { value: Value },
    Array { items: Vec<String> },
    Object { members: BTreeMap<String, String> },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Entry {
    pub id: String,
    pub node: Node,
}

fn identity(node: &Node) -> Result<String, Error> {
    use sha2::{Digest, Sha256};
    struct HashWriter(Sha256);
    impl Write for HashWriter {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            self.0.update(bytes);
            Ok(bytes.len())
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut writer = HashWriter(Sha256::new());
    writer.write_all(b"ariadne.frame-structure-evidence/v1\n")?;
    serde_json::to_writer(&mut writer, node)?;
    Ok(format!("{:x}", writer.0.finalize()))
}

pub(super) struct Dictionary {
    nodes: BTreeMap<String, Node>,
    used: BTreeSet<String>,
    work: usize,
    expanded_bytes: usize,
    wire_bytes: usize,
}

impl Dictionary {
    pub fn new() -> Self {
        Self {
            nodes: BTreeMap::new(),
            used: BTreeSet::new(),
            work: 0,
            expanded_bytes: 0,
            wire_bytes: 0,
        }
    }

    pub fn from_entries(entries: Vec<Entry>, limits: &FrameStructureLimits) -> Result<Self, Error> {
        if entries.len() > limits.max_dictionary_entries {
            return Err(invalid("structural evidence dictionary entry limit"));
        }
        let mut dictionary = Self::new();
        for entry in entries {
            if let Node::Scalar { value } = &entry.node {
                if value.is_array() || value.is_object() {
                    return Err(invalid("structural scalar contains a hidden evidence tree"));
                }
            }
            if identity(&entry.node)? != entry.id
                || dictionary.nodes.insert(entry.id, entry.node).is_some()
            {
                return Err(invalid(
                    "conflicting, duplicate or changed structural evidence dictionary entry",
                ));
            }
        }
        Ok(dictionary)
    }

    fn tick(&mut self, limits: &FrameStructureLimits) -> Result<(), Error> {
        self.work = self
            .work
            .checked_add(1)
            .ok_or_else(|| invalid("structural replay work overflow"))?;
        if self.work > limits.max_replay_work {
            return Err(invalid("structural evidence replay work limit"));
        }
        Ok(())
    }

    pub fn intern(&mut self, value: Value, limits: &FrameStructureLimits) -> Result<String, Error> {
        self.intern_at(value, 0, limits)
    }

    fn intern_at(
        &mut self,
        value: Value,
        depth: usize,
        limits: &FrameStructureLimits,
    ) -> Result<String, Error> {
        self.tick(limits)?;
        if depth > limits.max_dictionary_depth {
            return Err(invalid("structural evidence depth limit"));
        }
        let node = match value {
            Value::Array(values) => Node::Array {
                items: values
                    .into_iter()
                    .map(|v| self.intern_at(v, depth + 1, limits))
                    .collect::<Result<_, _>>()?,
            },
            Value::Object(values) => Node::Object {
                members: values
                    .into_iter()
                    .map(|(k, v)| Ok((k, self.intern_at(v, depth + 1, limits)?)))
                    .collect::<Result<_, Error>>()?,
            },
            value => Node::Scalar { value },
        };
        let id = identity(&node)?;
        if let Some(old) = self.nodes.get(&id) {
            if old != &node {
                return Err(invalid("structural evidence hash collision"));
            }
        } else {
            if self.nodes.len() >= limits.max_dictionary_entries {
                return Err(invalid("structural evidence dictionary entry limit"));
            }
            #[derive(Serialize)]
            struct BorrowedEntry<'a> {
                id: &'a str,
                node: &'a Node,
            }
            struct Counter {
                used: usize,
                limit: usize,
            }
            impl Write for Counter {
                fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
                    if bytes.len() > self.limit.saturating_sub(self.used) {
                        return Err(std::io::Error::other(
                            "structural dictionary publication byte limit",
                        ));
                    }
                    self.used += bytes.len();
                    Ok(bytes.len())
                }
                fn flush(&mut self) -> std::io::Result<()> {
                    Ok(())
                }
            }
            let mut counter = Counter {
                used: usize::from(!self.nodes.is_empty()),
                limit: limits.max_output_bytes.saturating_sub(self.wire_bytes),
            };
            serde_json::to_writer(
                &mut counter,
                &BorrowedEntry {
                    id: &id,
                    node: &node,
                },
            )?;
            self.wire_bytes = self
                .wire_bytes
                .checked_add(counter.used)
                .ok_or_else(|| invalid("structural dictionary publication byte overflow"))?;
            self.nodes.insert(id.clone(), node);
        }
        Ok(id)
    }

    pub fn entries(self) -> Vec<Entry> {
        self.nodes
            .into_iter()
            .map(|(id, node)| Entry { id, node })
            .collect()
    }

    /// Charge the entire expanded tree before allocating it. Shared subtrees
    /// count once per reference: deduplication must not enable expansion bombs.
    pub fn resolve(&mut self, id: &str, limits: &FrameStructureLimits) -> Result<Value, Error> {
        self.preflight(id, 0, &mut BTreeSet::new(), limits)?;
        self.expand(id, 0, limits)
    }

    fn charge_bytes(&mut self, bytes: usize, limits: &FrameStructureLimits) -> Result<(), Error> {
        self.expanded_bytes = self
            .expanded_bytes
            .checked_add(bytes)
            .ok_or_else(|| invalid("structural evidence byte overflow"))?;
        if self.expanded_bytes > limits.max_owned_bytes {
            return Err(invalid("structural expanded evidence byte limit"));
        }
        Ok(())
    }

    fn preflight(
        &mut self,
        id: &str,
        depth: usize,
        _active: &mut BTreeSet<String>,
        limits: &FrameStructureLimits,
    ) -> Result<(), Error> {
        enum Event {
            Enter(String, usize),
            Exit(String),
        }
        let mut stack = vec![Event::Enter(id.to_string(), depth)];
        let mut active = BTreeSet::new();
        while let Some(event) = stack.pop() {
            let (id, depth) = match event {
                Event::Exit(id) => {
                    active.remove(&id);
                    continue;
                }
                Event::Enter(id, depth) => (id, depth),
            };
            self.tick(limits)?;
            if depth > limits.max_dictionary_depth || !active.insert(id.clone()) {
                return Err(invalid("cyclic or too deep structural evidence dictionary"));
            }
            let node = self
                .nodes
                .get(&id)
                .ok_or_else(|| invalid("missing structural evidence reference"))?
                .clone();
            self.used.insert(id.clone());
            self.charge_bytes(2, limits)?;
            stack.push(Event::Exit(id));
            match node {
                Node::Scalar { value } => {
                    self.charge_bytes(serde_json::to_vec(&value)?.len(), limits)?
                }
                Node::Array { items } => {
                    if items.len() > limits.max_replay_work.saturating_sub(self.work) {
                        return Err(invalid("structural evidence replay work limit"));
                    }
                    self.charge_bytes(items.len(), limits)?;
                    stack.extend(
                        items
                            .into_iter()
                            .rev()
                            .map(|child| Event::Enter(child, depth + 1)),
                    );
                }
                Node::Object { members } => {
                    if members.len() > limits.max_replay_work.saturating_sub(self.work) {
                        return Err(invalid("structural evidence replay work limit"));
                    }
                    self.charge_bytes(members.len(), limits)?;
                    for (key, child) in members.into_iter().rev() {
                        self.charge_bytes(
                            serde_json::to_vec(&key)?
                                .len()
                                .checked_add(1)
                                .ok_or_else(|| invalid("structural key byte overflow"))?,
                            limits,
                        )?;
                        stack.push(Event::Enter(child, depth + 1));
                    }
                }
            }
        }
        Ok(())
    }

    fn expand(
        &mut self,
        id: &str,
        _depth: usize,
        limits: &FrameStructureLimits,
    ) -> Result<Value, Error> {
        // A flat malicious DAG can be arbitrarily deeper than its wire JSON.
        // Expand iteratively into bounded JSON, then use the normal strict
        // parser's nesting checks before constructing any nested Value tree.
        enum Event {
            Node(String),
            Bytes(Vec<u8>),
        }
        let mut stack = vec![Event::Node(id.to_string())];
        let mut bytes = Vec::new();
        while let Some(event) = stack.pop() {
            match event {
                Event::Bytes(token) => {
                    if token.len() > limits.max_owned_bytes.saturating_sub(bytes.len()) {
                        return Err(invalid("structural expanded evidence byte limit"));
                    }
                    bytes.extend(token);
                }
                Event::Node(id) => {
                    self.tick(limits)?;
                    let node = self
                        .nodes
                        .get(&id)
                        .ok_or_else(|| invalid("missing structural evidence reference"))?
                        .clone();
                    match node {
                        Node::Scalar { value } => {
                            stack.push(Event::Bytes(serde_json::to_vec(&value)?))
                        }
                        Node::Array { items } => {
                            stack.push(Event::Bytes(b"]".to_vec()));
                            for (index, child) in items.into_iter().enumerate().rev() {
                                stack.push(Event::Node(child));
                                if index > 0 {
                                    stack.push(Event::Bytes(b",".to_vec()));
                                }
                            }
                            stack.push(Event::Bytes(b"[".to_vec()));
                        }
                        Node::Object { members } => {
                            stack.push(Event::Bytes(b"}".to_vec()));
                            for (index, (key, child)) in members.into_iter().enumerate().rev() {
                                stack.push(Event::Node(child));
                                stack.push(Event::Bytes(b":".to_vec()));
                                stack.push(Event::Bytes(serde_json::to_vec(&key)?));
                                if index > 0 {
                                    stack.push(Event::Bytes(b",".to_vec()));
                                }
                            }
                            stack.push(Event::Bytes(b"{".to_vec()));
                        }
                    }
                }
            }
        }
        super::strict_json_with_limit(&bytes, limits.max_owned_bytes)
    }

    pub fn finish(&self) -> Result<(), Error> {
        if self.used.len() != self.nodes.len() {
            return Err(invalid(
                "unreferenced structural evidence dictionary entries",
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "../../tests/reports/frame_structure_dictionary.rs"]
mod tests;
