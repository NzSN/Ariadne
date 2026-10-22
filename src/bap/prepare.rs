//! BAP is the sole semantic producer. LLVM supplies decoded facts only.
use super::{OPAQUE_ORDINARY_RULE, PROJECTION};
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
#[derive(Clone, Copy, Debug, Default)]
pub struct Metrics {
    pub reference_processes: u64,
    pub helper_processes: u64,
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
    source_extension: Option<super::source_extension::SourceExtension>,
    source_extension_failed: bool,
    metrics: Metrics,
    retain_refinement: bool,
    refinement: BTreeMap<Address, super::refinement::TransferReceipt>,
    refinement_bytes: usize,
    retain_targets: bool,
    target_transfers: BTreeMap<Address, super::target_resolution::Transfer>,
    retain_guards: bool,
    guard_sites: BTreeMap<Address, super::guard_admission::CandidateSite>,
    terminal_receipts: BTreeMap<Address, super::guard_admission::TerminalReceipt>,
    query_total: usize,
    query_limit: usize,
}
pub(crate) struct GuardNormalProjection {
    pub instruction: crate::Instruction,
    pub memory_accesses: Vec<crate::effects::MemoryAccessEvidence>,
    pub gaps: Vec<String>,
}
pub(crate) fn stop(site: &mut PreparedSite, options: &PreparationOptions, va: Address) {
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
    pub(crate) fn guard_normal_projection(
        ast: &str,
        opcode: &str,
        bytes: &[u8],
        va: Address,
    ) -> Result<GuardNormalProjection, Error> {
        let bil: Vec<super::ast::Stmt> = serde_json::from_str(ast)?;
        let projection =
            super::projection::project_with_destination(&bil, opcode, bytes, va, None)?;
        if !projection.targets.is_empty() {
            return Err(invalid("guard normal selection changes control"));
        }
        Ok(GuardNormalProjection {
            instruction: crate::Instruction {
                kind: InstructionKind::Ordinary,
                fall: [va
                    .checked_add(bytes.len() as u64)
                    .ok_or_else(|| invalid("guard next address overflow"))?]
                .into(),
                targets: Default::default(),
                complete: true,
                uses: projection.uses,
                may_defs: projection.may_defs,
                must_defs: projection.must_defs,
            },
            memory_accesses: super::address::extract(&bil, va),
            gaps: projection.gaps,
        })
    }
    pub(crate) fn guard_producer(&self) -> super::guard_admission::Producer {
        super::guard_admission::Producer {
            helper_sha256: self.helper_hash.clone(),
            runtime_sha256: self.runtime_hash.clone(),
            decoder_sha256: self.decoder_hash.clone(),
            projection: super::guard_admission::PRODUCER_PROFILE.into(),
        }
    }
    /// Apply only a selection replayed over the frozen candidate graph.
    pub(crate) fn finalize_guard(
        site: &mut PreparedSite,
        va: Address,
        normal_ast: Option<&str>,
        residual: &str,
        options: &PreparationOptions,
    ) -> Result<(), Error> {
        let semantic = site
            .evidence
            .semantic
            .as_mut()
            .ok_or_else(|| invalid("guard semantic source absent"))?;
        semantic
            .gaps
            .retain(|g| g != "normal-or-alignment-fault-pending");
        if let Some(ast) = normal_ast {
            let projection = Self::guard_normal_projection(
                ast,
                site.evidence.opcode.as_deref().unwrap_or(""),
                &site.evidence.bytes,
                va,
            )?;
            site.instruction = projection.instruction;
            site.evidence.quality = EffectQuality::ExternalLifted;
            site.evidence.rule = Some(super::guard_admission::PRODUCER_PROFILE.into());
            let semantic = site.evidence.semantic.as_mut().expect("checked semantic");
            semantic.status = "projected".into();
            semantic.memory_accesses = projection.memory_accesses;
            semantic.gaps.extend(projection.gaps);
            semantic
                .gaps
                .push("alignment-normal-under-recorded-premises".into());
        } else {
            semantic.status = "guard-not-admitted".into();
            semantic.gaps.push(residual.into());
            stop(site, options, va);
        }
        Ok(())
    }
    pub(crate) fn enable_guard_admission(&mut self) {
        self.retain_guards = true;
    }
    pub(crate) fn take_guard_sites(
        &mut self,
    ) -> BTreeMap<Address, super::guard_admission::CandidateSite> {
        std::mem::take(&mut self.guard_sites)
    }
    pub(crate) fn take_terminal_receipts(
        &mut self,
    ) -> BTreeMap<Address, super::guard_admission::TerminalReceipt> {
        std::mem::take(&mut self.terminal_receipts)
    }
    pub(crate) fn enable_target_resolution(&mut self) {
        self.retain_targets = true;
    }
    pub(crate) fn take_target_transfers(
        &mut self,
    ) -> BTreeMap<Address, super::target_resolution::Transfer> {
        std::mem::take(&mut self.target_transfers)
    }
    pub(crate) fn enable_refinement(&mut self) {
        self.retain_refinement = true;
    }
    pub(crate) fn take_refinement(
        &mut self,
    ) -> BTreeMap<Address, super::refinement::TransferReceipt> {
        std::mem::take(&mut self.refinement)
    }
    pub fn metrics(&self) -> Metrics {
        self.metrics
    }
    /// Immutable aggregate bound selected by the owning captured-query builder.
    /// A child process keeps its independent fixed protocol capacity.
    pub(crate) fn set_query_site_limit(&mut self, limit: usize) -> Result<(), Error> {
        if self.snapshot.is_some() || self.query_total != 0 {
            return Err(invalid(
                "BAP query site limit cannot change after preparation starts",
            ));
        }
        self.query_limit = limit;
        Ok(())
    }
    pub fn finish(mut self) -> Result<(), Error> {
        if self.source_extension_failed {
            return Err(invalid(
                "source extension query failed; start a fresh backend",
            ));
        }
        if let Some(extension) = &self.source_extension {
            extension.validate()?;
        }
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
        if let Some(extension) = &self.source_extension {
            extension.validate()?;
        }
        Ok(())
    }
    pub fn new(config: Config, decoder: &Path) -> Result<Self, Error> {
        let start = Instant::now();
        let packaged_runtime_hash = config.validate_runtime()?;
        let source_extension = config
            .source_extension
            .as_deref()
            .map(super::source_extension::SourceExtension::load)
            .transpose()?;
        let runtime_hash = source_extension.as_ref().map_or_else(
            || packaged_runtime_hash.clone(),
            |extension| extension.runtime_identity(&packaged_runtime_hash),
        );
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
            source_extension,
            source_extension_failed: false,
            metrics: Metrics {
                runtime_validation: start.elapsed(),
                ..Metrics::default()
            },
            retain_refinement: false,
            refinement: BTreeMap::new(),
            refinement_bytes: 0,
            retain_targets: false,
            target_transfers: BTreeMap::new(),
            retain_guards: false,
            guard_sites: BTreeMap::new(),
            terminal_receipts: BTreeMap::new(),
            query_total: 0,
            query_limit: super::session::MAX_SESSION_SITES,
        })
    }
    pub fn prepare(
        &mut self,
        snapshot: &str,
        candidates: &BTreeMap<Address, Option<Vec<u8>>>,
        options: &PreparationOptions,
        target: DecoderTarget,
    ) -> Result<PreparedBatch, Error> {
        if self.source_extension_failed {
            return Err(invalid(
                "source extension query failed; start a fresh backend",
            ));
        }
        let result = self.prepare_inner(snapshot, candidates, options, target);
        if self.source_extension.is_some() && result.is_err() {
            self.source_extension_failed = true;
            self.session.take();
            self.decoder_session.take();
        }
        result
    }
    fn prepare_inner(
        &mut self,
        snapshot: &str,
        candidates: &BTreeMap<Address, Option<Vec<u8>>>,
        options: &PreparationOptions,
        target: DecoderTarget,
    ) -> Result<PreparedBatch, Error> {
        if self.source_extension.is_some()
            && (self.retain_guards || self.retain_targets || self.retain_refinement)
        {
            return Err(invalid(
                "source flag extension does not admit guards, target resolution or refinement",
            ));
        }
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
        let profile = if self.retain_guards {
            super::guard_admission::PRODUCER_PROFILE
        } else if self.source_extension.is_some() {
            super::source_extension::PROFILE
        } else {
            PROJECTION
        };
        batch.identity.ruleset = profile.into();
        let available: BTreeMap<_, _> = candidates
            .iter()
            .filter_map(|(&a, b)| b.as_ref().map(|b| (a, b.clone())))
            .collect();
        if available.is_empty() {
            return Ok(batch);
        }
        if available.len() > 256 {
            return Err(invalid("invalid BAP batch size"));
        }
        let query_total = self
            .query_total
            .checked_add(available.len())
            .filter(|n| *n <= self.query_limit)
            .ok_or_else(|| invalid("BAP query site budget exceeded"))?;
        if self
            .session
            .as_ref()
            .is_some_and(|s| s.remaining_sites() < available.len())
        {
            // Rotation changes transport lifetime only. Aggregate evidence,
            // query identity, source hashes and selected budgets remain owned
            // by this backend; no child may exceed its fixed protocol cap.
            self.session
                .take()
                .expect("capacity checked session")
                .finish()?;
        }
        if self.session.is_none() {
            let start = Instant::now();
            let session = Session::start(
                &self.config,
                snapshot,
                match target {
                    DecoderTarget::WindowsAmd64 => "windows-amd64",
                    DecoderTarget::LinuxAmd64 => "linux-amd64",
                },
            )?;
            if session.helper_hash != self.helper_hash {
                return Err(invalid("BAP helper changed during query initialization"));
            }
            self.session = Some(session);
            self.metrics.helper_processes += 1;
            self.metrics.helper_startup += start.elapsed();
        }
        let start = Instant::now();
        let lifts = self.session.as_mut().unwrap().lift(&available)?;
        self.query_total = query_total;
        if self.session.as_ref().unwrap().helper_hash != self.helper_hash {
            return Err(invalid("BAP helper changed during query initialization"));
        }
        self.metrics.lift_and_protocol += start.elapsed();
        let start = Instant::now();
        for (va, mut lift) in lifts {
            let site = batch
                .sites
                .get_mut(&va)
                .ok_or_else(|| invalid("BAP returned unsolicited site"))?;
            if let Some(extension) = &self.source_extension
                && lift.status == "decoded"
                && lift.bil.is_empty()
                && lift.length == 1
                && site.evidence.length == 1
                && super::source_extension::SourceExtension::supports(&site.evidence.bytes)
                && lift.bytes == format!("{:02x}", site.evidence.bytes[0])
                && site.instruction.kind == InstructionKind::Ordinary
                && lift.properties.as_ref().is_some_and(|p| {
                    !p.jump && !p.conditional && !p.indirect && !p.call && !p.return_ && !p.control
                })
            {
                lift.bil = extension.lift(
                    match target {
                        DecoderTarget::WindowsAmd64 => "windows-amd64",
                        DecoderTarget::LinuxAmd64 => "linux-amd64",
                    },
                    snapshot,
                    va,
                    &site.evidence.bytes,
                    self.config.timeout,
                )?;
                lift.validate_ast()?;
            }
            let ast = serde_json::to_vec(&lift.bil)?;
            let mut semantic = SemanticEvidence {
                backend: "bap-x86-legacy".into(),
                helper_sha256: self.helper_hash.clone(),
                runtime_sha256: self.runtime_hash.clone(),
                projection: profile.into(),
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
                if self.retain_guards {
                    self.guard_sites
                        .insert(va, guard_source(site, va, &ast, true)?);
                }
                site.evidence.semantic = Some(semantic);
                continue;
            }
            if self.retain_guards {
                let terminal = if let Some(record) = site.evidence.decoder_record.as_deref() {
                    super::terminal_control::recognize(
                        va,
                        &site.evidence.bytes,
                        std::str::from_utf8(&ast)?,
                        &lift,
                        record,
                    )?
                } else {
                    None
                };
                if let Some(receipt) = terminal {
                    site.instruction.kind = InstructionKind::Stop;
                    site.instruction.fall.clear();
                    site.instruction.targets.clear();
                    site.instruction.complete = true;
                    site.instruction.uses = options.catalogue.locations();
                    site.instruction.may_defs = options.catalogue.locations();
                    site.instruction.must_defs.clear();
                    site.decodable = true;
                    site.evidence.quality = EffectQuality::Opaque;
                    site.evidence.control = Some(InstructionKind::Stop);
                    site.evidence.rule = Some(super::terminal_control::RULE.into());
                    semantic.status = super::terminal_control::STATUS.into();
                    semantic.gaps.extend([
                        super::terminal_control::EXIT.into(),
                        super::terminal_control::RESUMPTION.into(),
                        "unsupported-exception-effects".into(),
                    ]);
                    if receipt.rule == "ud1-pinned-extent/v1" {
                        semantic.gaps.push("pinned-bap-extent-disagreement".into());
                    }
                    site.gaps
                        .retain(|g| g.reason != GapReason::UnsupportedControl);
                    if !site
                        .gaps
                        .iter()
                        .any(|g| g.reason == GapReason::OpaqueEffects)
                    {
                        site.gaps.push(PreparationGap {
                            address: va,
                            reason: GapReason::OpaqueEffects,
                        });
                    }
                    self.guard_sites
                        .insert(va, guard_source(site, va, &ast, true)?);
                    self.terminal_receipts.insert(va, receipt);
                    site.evidence.semantic = Some(semantic);
                    continue;
                }
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
                if self.retain_guards {
                    self.guard_sites
                        .insert(va, guard_source(site, va, &ast, true)?);
                }
                site.evidence.semantic = Some(semantic);
                continue;
            }
            let p = lift
                .properties
                .as_ref()
                .ok_or_else(|| invalid("missing decoded BAP control facts"))?;
            let kind = site.instruction.kind;
            let raw_control = site.instruction.clone();
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
            } else if self.retain_guards
                && super::guard_admission::recognize_pending(
                    &super::guard_admission::CandidateSite {
                        site: format!("0x{va:016x}"),
                        bytes_hex: lift.bytes.clone(),
                        ast: String::from_utf8(ast.clone())?,
                        control: super::guard_admission::CandidateControl::from_instruction(
                            &raw_control,
                        ),
                        opaque: true,
                    },
                )?
                .is_some()
            {
                // This graph-only continuation commits no normal effects. Its
                // independent residue relation is checked again after closure.
                site.instruction.uses.clear();
                site.instruction.may_defs.clear();
                site.instruction.must_defs.clear();
                site.evidence.quality = EffectQuality::Opaque;
                site.evidence.rule = None;
                semantic.status = "guard-pending".into();
                semantic
                    .gaps
                    .push("normal-or-alignment-fault-pending".into());
                if self.retain_targets {
                    // Recognition above constrains this to a reviewed
                    // vector-only load or memory store. Extract scalar flow on
                    // its candidate normal continuation, without selecting the
                    // normal AST or committing the store to final effects.
                    let transfer =
                        super::target_resolution::extract(&lift.bil, va, &site.evidence.bytes)?;
                    if !transfer.is_scalar_identity() {
                        return Err(invalid("pending guard scalar transfer changed"));
                    }
                    self.target_transfers.insert(va, transfer);
                }
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
                            site.evidence.rule = Some(profile.into());
                            semantic.status = "projected".into();
                            if self.retain_targets {
                                self.target_transfers.insert(
                                    va,
                                    super::target_resolution::extract(
                                        &lift.bil,
                                        va,
                                        &site.evidence.bytes,
                                    )?,
                                );
                            }
                            if self.retain_refinement {
                                let receipt =
                                    super::refinement::extract(&lift.bil, va, lift.bytes.clone())?;
                                self.refinement_bytes = self
                                    .refinement_bytes
                                    .checked_add(receipt.ast.len())
                                    .filter(|n| *n <= 64 * 1024 * 1024)
                                    .ok_or_else(|| invalid("refinement sidecar byte budget"))?;
                                self.refinement.insert(va, receipt);
                            }
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
                            site.evidence.rule = Some(OPAQUE_ORDINARY_RULE.into());
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
            if self.retain_guards {
                self.guard_sites.insert(
                    va,
                    guard_source(site, va, &ast, semantic.status != "projected")?,
                );
            }
            site.evidence.semantic = Some(semantic);
        }
        self.metrics.projection += start.elapsed();
        Ok(batch)
    }
}

fn guard_source(
    site: &PreparedSite,
    va: Address,
    ast: &[u8],
    opaque: bool,
) -> Result<super::guard_admission::CandidateSite, Error> {
    Ok(super::guard_admission::CandidateSite {
        site: format!("0x{va:016x}"),
        bytes_hex: site
            .evidence
            .bytes
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
        ast: std::str::from_utf8(ast)?.into(),
        control: super::guard_admission::CandidateControl::from_instruction(&site.instruction),
        opaque,
    })
}
