use super::{AdapterError, ByteSnapshot, hex, protocol};
use crate::effects::*;
use crate::{AnalysisRequest, ByteSource, InputKind, Instruction, InstructionKind, LocationSet};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

impl ByteSnapshot {
    /// Prepare reviewed normal-continuation effects in a fixed disjoint location
    /// catalogue. Keep the returned evidence/gaps alongside the analyzer result.
    /// `scope_closed()` alone does not imply effect or instruction-step coverage.
    pub fn prepare(
        &self,
        decoder: &Path,
        options: &PreparationOptions,
    ) -> Result<PreparedAnalysis, AdapterError> {
        if self.locations != options.catalogue.locations() {
            return Err(AdapterError::InvalidInput(
                "locations must exactly match the effects catalogue".into(),
            ));
        }
        if self.snapshot_id.is_empty()
            || self.entry_points.is_empty()
            || !self
                .trusted_fallback
                .iter()
                .all(|a| self.file_backed.contains_key(a))
        {
            return Err(AdapterError::InvalidInput(
                "invalid snapshot identity, entries or fallback domain".into(),
            ));
        }
        let mut request = AnalysisRequest {
            snapshot_id: self.snapshot_id.clone(),
            locations: self.locations.clone(),
            entry_points: self.entry_points.clone(),
            slice_seeds: self.slice_seeds.clone(),
            input_kind: self.input_kind,
            ..AnalysisRequest::default()
        };
        request.addresses.extend(
            self.entry_points
                .iter()
                .chain(self.slice_seeds.iter())
                .copied(),
        );
        request
            .addresses
            .extend(self.captured.keys().chain(self.file_backed.keys()).copied());
        let mut selected = BTreeMap::new();
        for &a in &request.addresses {
            let bytes = match self.input_kind {
                InputKind::Binary => self.file_backed.get(&a).map(|b| (b, ByteSource::File)),
                InputKind::Dump => self
                    .captured
                    .get(&a)
                    .map(|b| (b, ByteSource::Captured))
                    .or_else(|| {
                        self.trusted_fallback
                            .contains(&a)
                            .then(|| self.file_backed.get(&a).map(|b| (b, ByteSource::File)))
                            .flatten()
                    }),
            };
            if let Some((bytes, source)) = bytes {
                if bytes.is_empty() {
                    return Err(AdapterError::InvalidInput(
                        "available byte spans must be nonempty".into(),
                    ));
                }
                selected.insert(a, (&bytes[..bytes.len().min(15)], source));
            }
        }
        let input = selected
            .iter()
            .map(|(a, (bytes, _))| format!("{a} {}\n", hex(bytes)))
            .collect();
        let rows = protocol::invoke(decoder, input, selected.len())?;
        let mut instructions = BTreeMap::new();
        let mut gaps = Vec::new();
        let mut seen = BTreeSet::new();
        for raw in rows {
            let a = raw.decoded.address;
            let Some(&(bytes, source)) = selected.get(&a) else {
                return Err(AdapterError::DecoderProtocol("unexpected VA".into()));
            };
            if !seen.insert(a) {
                return Err(AdapterError::DecoderProtocol("duplicate VA".into()));
            }
            let d = &raw.decoded;
            if d.length > bytes.len() as u64 {
                return Err(AdapterError::DecoderProtocol(
                    "length exceeds supplied bytes".into(),
                ));
            }
            if d.status == "ok" {
                let kind = d.kind.expect("parser checked");
                if (matches!(kind, InstructionKind::Conditional | InstructionKind::Jump)
                    && d.target.is_none())
                    || (!matches!(
                        kind,
                        InstructionKind::Conditional
                            | InstructionKind::Jump
                            | InstructionKind::Call
                    ) && d.target.is_some())
                {
                    return Err(AdapterError::DecoderProtocol(
                        "target contradicts control kind".into(),
                    ));
                }
            }
            let truncated = d.status == "invalid" && bytes.len() < 15;
            if !truncated {
                match source {
                    ByteSource::Captured => {
                        request.captured.insert(a);
                    }
                    ByteSource::File => {
                        request.file_backed.insert(a);
                        if self.input_kind == InputKind::Dump {
                            request.trusted_fallback.insert(a);
                        }
                    }
                    ByteSource::Unavailable => unreachable!(),
                }
            }
            let mut evidence = InstructionEvidence {
                bytes: bytes[..if d.length == 0 {
                    bytes.len()
                } else {
                    d.length as usize
                }]
                    .to_vec(),
                source,
                opcode: (raw.opcode != "-").then(|| raw.opcode.clone()),
                length: d.length as u8,
                operands: Vec::new(),
                rule: None,
                control: None,
                quality: EffectQuality::Unavailable,
                undefined_flags: LocationSet::new(),
                decoder_record: Some(raw.record.clone()),
            };
            if d.status == "invalid" {
                gaps.push(PreparationGap {
                    address: a,
                    reason: if truncated {
                        GapReason::MissingBytes
                    } else {
                        GapReason::InvalidEncoding
                    },
                });
            } else if let Some(s) = crate::effects::summarize(&raw, &evidence.bytes)
                .filter(|s| d.status == "ok" && d.kind == Some(s.kind))
            {
                let next = a
                    .checked_add(d.length)
                    .ok_or_else(|| AdapterError::DecoderProtocol("next VA overflow".into()))?;
                let fall = if matches!(
                    s.kind,
                    InstructionKind::Ordinary
                        | InstructionKind::Conditional
                        | InstructionKind::Call
                ) {
                    [next].into()
                } else {
                    BTreeSet::new()
                };
                let targets: BTreeSet<_> = d.target.into_iter().collect();
                request
                    .addresses
                    .extend(fall.iter().chain(targets.iter()).copied());
                request.decodable.insert(a);
                evidence.operands = s.operands;
                evidence.rule = Some(s.rule);
                evidence.control = Some(s.kind);
                evidence.quality = s.quality.clone();
                evidence.undefined_flags = s.undefined;
                if s.quality == EffectQuality::Opaque {
                    gaps.push(PreparationGap {
                        address: a,
                        reason: GapReason::OpaqueEffects,
                    });
                }
                if !evidence.undefined_flags.is_empty() {
                    gaps.push(PreparationGap {
                        address: a,
                        reason: GapReason::UndefinedFlags,
                    });
                }
                request.instructions.insert(
                    a,
                    Instruction {
                        kind: s.kind,
                        fall,
                        targets,
                        complete: s.kind != InstructionKind::Indirect
                            && (s.kind != InstructionKind::Call || d.target.is_some()),
                        uses: s.uses,
                        may_defs: s.may_defs,
                        must_defs: s.must_defs,
                    },
                );
            } else {
                gaps.push(PreparationGap {
                    address: a,
                    reason: GapReason::UnsupportedControl,
                });
            }
            instructions.insert(a, evidence);
        }
        for &a in &request.addresses {
            request.instructions.entry(a).or_default();
            instructions.entry(a).or_insert_with(|| {
                gaps.push(PreparationGap {
                    address: a,
                    reason: GapReason::MissingBytes,
                });
                InstructionEvidence {
                    bytes: Vec::new(),
                    source: ByteSource::Unavailable,
                    opcode: None,
                    length: 0,
                    operands: Vec::new(),
                    rule: None,
                    control: None,
                    quality: EffectQuality::Unavailable,
                    undefined_flags: LocationSet::new(),
                    decoder_record: None,
                }
            });
        }
        gaps.sort_by_key(|g| g.address);
        request.validate().map_err(AdapterError::InvalidRequest)?;
        Ok(PreparedAnalysis {
            request,
            instructions,
            gaps,
            identity: PreparationIdentity {
                decoder: "LLVM MC 20.1.2".into(),
                protocol: 2,
                ruleset: RULESET.into(),
                catalogue: options.catalogue.identity().into(),
            },
        })
    }
}
