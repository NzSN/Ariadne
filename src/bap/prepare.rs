//! BAP is the sole semantic producer. LLVM supplies decoded facts only.
use crate::bap::{Config, Error, Session, invalid};
use crate::{
    Address, InstructionKind,
    effects::{
        EffectQuality, GapReason, Operand, PreparationGap, PreparationOptions, SemanticEvidence,
    },
    llvm_mc::{DecoderTarget, PreparedBatch, PreparedSite, decode_with_session},
};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
const PROJECTION: &str = "bap-bit-provenance-v3";
#[derive(Clone, Copy, Debug, Default)]
pub struct Metrics {
    pub reference_processes: u64,
    pub runtime_validation: Duration,
    pub reference_decode: Duration,
    pub helper_startup: Duration,
    pub lift_and_protocol: Duration,
    pub projection: Duration,
}
pub struct Backend {
    config: Config,
    decoder: PathBuf,
    decoder_hash: String,
    decoder_session: Option<crate::llvm_mc::protocol::ReferenceSession>,
    session: Option<Session>,
    snapshot: Option<String>,
    target: Option<DecoderTarget>,
    runtime_hash: String,
    helper_hash: String,
    metrics: Metrics,
}
fn stop(site: &mut PreparedSite, options: &PreparationOptions, va: Address) {
    site.instruction.uses = options.catalogue.locations();
    site.instruction.may_defs = options.catalogue.locations();
    site.instruction.must_defs.clear();
    site.instruction.kind = InstructionKind::Stop;
    site.instruction.fall.clear();
    site.instruction.targets.clear();
    site.instruction.complete = false;
    site.decodable = false;
    site.evidence.quality = EffectQuality::Opaque;
    site.evidence.control = Some(InstructionKind::Stop);
    site.evidence.rule = None;
    if !site
        .gaps
        .iter()
        .any(|g| g.reason == GapReason::UnsupportedControl)
    {
        site.gaps.push(PreparationGap {
            address: va,
            reason: GapReason::UnsupportedControl,
        });
    }
}
impl Backend {
    pub fn metrics(&self) -> Metrics {
        self.metrics
    }
    pub fn finish(mut self) -> Result<(), Error> {
        if crate::reports::sha256(&std::fs::read(&self.decoder)?) != self.decoder_hash {
            return Err(invalid(
                "decode reference changed during snapshot preparation",
            ));
        }
        if let Some(s) = self.session.take() {
            s.finish()?;
        }
        if let Some(s) = self.decoder_session.take() {
            s.finish()?;
        }
        Ok(())
    }
    pub fn new(config: Config, decoder: &Path) -> Result<Self, Error> {
        let start = Instant::now();
        let runtime_hash = config.validate_runtime()?;
        let helper_hash = crate::bap::helper_identity(&config.helper)?;
        Ok(Self {
            config,
            decoder_hash: crate::reports::sha256(&std::fs::read(decoder)?),
            decoder: decoder.into(),
            decoder_session: None,
            session: None,
            snapshot: None,
            target: None,
            runtime_hash,
            helper_hash,
            metrics: Metrics {
                runtime_validation: start.elapsed(),
                ..Metrics::default()
            },
        })
    }
    pub fn prepare(
        &mut self,
        snapshot: &str,
        candidates: &BTreeMap<Address, Option<Vec<u8>>>,
        options: &PreparationOptions,
        target: DecoderTarget,
    ) -> Result<PreparedBatch, Error> {
        if self.snapshot.as_deref().is_some_and(|id| id != snapshot)
            || self.target.is_some_and(|t| t != target)
        {
            return Err(invalid(
                "BAP session cannot cross snapshot/target identities",
            ));
        }
        self.snapshot = Some(snapshot.into());
        self.target = Some(target);
        let start = Instant::now();
        if self.decoder_session.is_none() && candidates.values().any(Option::is_some) {
            self.metrics.reference_processes += 1;
        }
        let mut batch = decode_with_session(
            snapshot,
            candidates,
            &self.decoder,
            options,
            target,
            &mut self.decoder_session,
        )?;
        if crate::reports::sha256(&std::fs::read(&self.decoder)?) != self.decoder_hash {
            return Err(invalid("decode reference changed between snapshot batches"));
        }
        self.metrics.reference_decode += start.elapsed();
        batch.identity.ruleset = PROJECTION.into();
        let available: BTreeMap<_, _> = candidates
            .iter()
            .filter_map(|(&a, b)| b.as_ref().map(|b| (a, b.clone())))
            .collect();
        if available.is_empty() {
            return Ok(batch);
        }
        if self.session.is_none() {
            let start = Instant::now();
            self.session = Some(Session::start(
                &self.config,
                snapshot,
                match target {
                    DecoderTarget::WindowsAmd64 => "windows-amd64",
                    DecoderTarget::LinuxAmd64 => "linux-amd64",
                },
            )?);
            self.metrics.helper_startup += start.elapsed();
        }
        let start = Instant::now();
        let lifts = self.session.as_mut().unwrap().lift(&available)?;
        if self.session.as_ref().unwrap().helper_hash != self.helper_hash {
            return Err(invalid("BAP helper changed during query initialization"));
        }
        self.metrics.lift_and_protocol += start.elapsed();
        let start = Instant::now();
        for (va, lift) in lifts {
            let site = batch
                .sites
                .get_mut(&va)
                .ok_or_else(|| invalid("BAP returned unsolicited site"))?;
            let ast = serde_json::to_vec(&lift.bil)?;
            let mut semantic = SemanticEvidence {
                backend: "bap-x86-legacy".into(),
                helper_sha256: self.helper_hash.clone(),
                runtime_sha256: self.runtime_hash.clone(),
                projection: PROJECTION.into(),
                status: "opaque-unsupported".into(),
                ast_sha256: Some(crate::reports::sha256(&ast)),
                fallback: None,
                gaps: Vec::new(),
                memory_accesses: Vec::new(),
            };
            if lift.status == "invalid" && site.evidence.length == 0 {
                semantic.status = "invalid-decode".into();
                semantic
                    .gaps
                    .push("invalid-or-short-captured-prefix".into());
                site.evidence.semantic = Some(semantic);
                continue;
            }
            if lift.status != "decoded"
                || lift.length != site.evidence.length
                || lift.bytes
                    != site
                        .evidence
                        .bytes
                        .iter()
                        .map(|b| format!("{b:02x}"))
                        .collect::<String>()
            {
                semantic.status = "decode-disagreement".into();
                semantic.gaps.push("decode-disagreement".into());
                stop(site, options, va);
                site.evidence.semantic = Some(semantic);
                continue;
            }
            let p = lift
                .properties
                .as_ref()
                .ok_or_else(|| invalid("missing decoded BAP control facts"))?;
            let kind = site.instruction.kind;
            let compatible = match kind {
                InstructionKind::Ordinary => {
                    !p.jump && !p.conditional && !p.indirect && !p.control && !p.call && !p.return_
                }
                InstructionKind::Conditional => {
                    p.jump && p.conditional && !p.indirect && p.control && !p.call && !p.return_
                }
                InstructionKind::Jump => {
                    p.jump && !p.conditional && !p.indirect && p.control && !p.call && !p.return_
                }
                InstructionKind::Indirect => {
                    p.jump && !p.conditional && p.indirect && p.control && !p.call && !p.return_
                }
                InstructionKind::Call => p.call && !p.return_ && !p.conditional && p.control,
                InstructionKind::Return => p.return_ && !p.call && !p.conditional && p.control,
                InstructionKind::Stop => false,
            };
            if !compatible {
                semantic.status = "control-disagreement".into();
                semantic.gaps.push("control-disagreement".into());
                stop(site, options, va);
            } else if matches!(kind, InstructionKind::Call | InstructionKind::Return) {
                semantic.status = "opaque-call-return".into();
                semantic
                    .gaps
                    .push("callee/return-semantics-not-projected".into());
                site.instruction.uses = options.catalogue.locations();
                site.instruction.may_defs = options.catalogue.locations();
                site.instruction.must_defs.clear();
                site.evidence.quality = EffectQuality::Opaque;
                site.evidence.rule = Some("bap-opaque-call-return-v1".into());
                site.gaps.push(PreparationGap {
                    address: va,
                    reason: GapReason::OpaqueEffects,
                });
            } else {
                let opcode = site.evidence.opcode.as_deref().unwrap_or("");
                let registers: Vec<_> = site
                    .evidence
                    .operands
                    .iter()
                    .filter_map(|o| {
                        if let Operand::Register(r) = o {
                            Some(r)
                        } else {
                            None
                        }
                    })
                    .collect();
                let destination = crate::bap::admission::decoded_destination(&site.evidence);
                match crate::bap::projection::project_with_destination(
                    &lift.bil,
                    opcode,
                    &site.evidence.bytes,
                    va,
                    destination,
                ) {
                    Ok(projection) => {
                        let actual: Vec<u64> =
                            projection.targets.iter().flatten().copied().collect();
                        let allowed: std::collections::BTreeSet<_> = site
                            .instruction
                            .targets
                            .union(&site.instruction.fall)
                            .copied()
                            .collect();
                        let move_binding = !["MOV8rr", "MOV16rr", "MOV32rr", "MOV64rr"]
                            .contains(&opcode)
                            || (registers.len() == 2
                                && projection.uses.is_superset(&registers[1].reads())
                                && projection.may_defs == registers[0].replacements());
                        if actual.iter().any(|a| !allowed.contains(a))
                            || (kind == InstructionKind::Ordinary && !projection.targets.is_empty())
                            || (matches!(
                                kind,
                                InstructionKind::Conditional | InstructionKind::Jump
                            ) && (projection.targets.is_empty()
                                || projection.targets.iter().any(Option::is_none)))
                        {
                            semantic.status = "control-disagreement".into();
                            semantic.gaps.push("control-disagreement".into());
                            stop(site, options, va);
                        } else if !move_binding {
                            semantic.status = "operand-binding-disagreement".into();
                            semantic
                                .gaps
                                .push("decoded-move-operand-binding-disagreement".into());
                            stop(site, options, va);
                        } else {
                            site.instruction.uses = projection.uses;
                            site.instruction.may_defs = projection.may_defs;
                            site.instruction.must_defs = projection.must_defs;
                            if ["TEST64rr", "TEST8rr", "XOR64rr"].contains(&opcode) {
                                // Separately reviewed logical-instruction AF undefinedness;
                                // the generic BIL Unknown alone establishes no ISA label.
                                site.evidence.undefined_flags.insert("flag:af".into());
                                site.instruction.must_defs.remove("flag:af");
                                site.gaps.push(PreparationGap {
                                    address: va,
                                    reason: GapReason::UndefinedFlags,
                                });
                            }
                            site.evidence.quality = EffectQuality::ExternalLifted;
                            site.evidence.rule = Some(PROJECTION.into());
                            semantic.status = "projected".into();
                            semantic.memory_accesses = crate::bap::address::extract(&lift.bil, va);
                            semantic.gaps.extend(projection.gaps);
                        }
                    }
                    Err(e) => {
                        if crate::bap::admission::fatal(&e) {
                            return Err(e);
                        }
                        semantic.gaps.push(e.to_string());
                        if kind == InstructionKind::Ordinary
                            && crate::bap::admission::ordinary_unknown(
                                &lift.bil,
                                &site.evidence.bytes,
                                &e,
                            )
                        {
                            semantic.status = "opaque-ordinary".into();
                            semantic.gaps.push("unsupported-data-effects".into());
                            site.instruction.uses = options.catalogue.locations();
                            site.instruction.may_defs = options.catalogue.locations();
                            site.instruction.must_defs.clear();
                            site.evidence.quality = EffectQuality::Opaque;
                            site.evidence.rule = Some("bap-opaque-ordinary-v3".into());
                            site.gaps.push(PreparationGap {
                                address: va,
                                reason: GapReason::OpaqueEffects,
                            });
                        } else {
                            stop(site, options, va);
                        }
                    }
                }
            }
            site.evidence.semantic = Some(semantic);
        }
        self.metrics.projection += start.elapsed();
        Ok(batch)
    }
}
