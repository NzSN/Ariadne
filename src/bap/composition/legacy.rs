//! Frozen v1 semantic replay. Original identities refer to hash-verified fixtures.
use super::Report;
use crate::bap::{Error, guard_admission as guard, invalid, target_resolution as target};
use crate::{AnalysisRequest, InstructionKind};
use std::collections::BTreeMap;
const PROFILE: &str = super::LEGACY_PROFILE;
const SCHEMA: &str = super::LEGACY_SCHEMA;
const MODEL_VERSION: &str = super::LEGACY_SCHEMA;
fn model_identity() -> String {
    super::legacy_model_identity()
}
fn checker_identity() -> String {
    super::legacy_checker_identity()
}
use super::{binding_digest, candidate_request, typed_digest, value_digest};

pub fn validate(
    report: &Report,
    targets: &target::Report,
    guards: &guard::Report,
    final_request: &AnalysisRequest,
) -> Result<(), Error> {
    if report.schema != SCHEMA
        || report.profile != PROFILE
        || report.model_version != MODEL_VERSION
        || report.model_sha256 != model_identity()
        || report.checker_sha256 != checker_identity()
        || report.snapshot != guards.input.snapshot
        || report.snapshot != targets.snapshot
        || report.artifact_sha256 != guards.input.artifact_sha256
        || report.artifact_sha256 != targets.artifact_sha256
        || report.query_scope_sha256 != guards.input.query_scope_sha256
        || report.candidate_epoch != guards.input.candidate_epoch
        || targets.memory_premise != target::MEMORY_PREMISE
        || targets.profile != target::LEGACY_LOCAL_PROFILE
        || targets.schema != "ariadne.indirect-target-resolution/v2"
        || report.candidate_sha256 != value_digest(&report.candidate)?
        || report.target_report_sha256 != typed_digest(targets)?
        || report.guard_report_sha256 != typed_digest(guards)?
        || report.final_request_sha256
            != value_digest(&crate::bap::core_adapter::encode_request(final_request)?)?
        || report.binding_sha256 != binding_digest(report)?
    {
        return Err(invalid("composition identity, proof or graph digest"));
    }
    let candidate = candidate_request(report)?;
    if report.candidate != crate::bap::core_adapter::encode_request(&candidate)?
        || candidate.snapshot_id != report.snapshot
        || final_request.snapshot_id != report.snapshot
        || candidate.addresses != final_request.addresses
        || candidate.locations != final_request.locations
        || candidate.entry_points != final_request.entry_points
        || candidate.slice_seeds != final_request.slice_seeds
        || candidate.input_kind != final_request.input_kind
        || candidate.captured != final_request.captured
        || candidate.file_backed != final_request.file_backed
        || candidate.trusted_fallback != final_request.trusted_fallback
        || candidate.input_kind != crate::InputKind::Dump
        || !candidate.file_backed.is_empty()
        || !candidate.trusted_fallback.is_empty()
    {
        return Err(invalid("composition immutable scope or candidate encoding"));
    }
    target::validate(targets, &candidate.instructions, &candidate.entry_points)?;
    for (&site, instruction) in &candidate.instructions {
        if instruction.kind != InstructionKind::Indirect {
            continue;
        }
        let name = crate::bap::core_adapter::hex(site);
        if let Some(row) = targets.resolutions.iter().find(|r| r.site == name) {
            if row.targets
                != instruction
                    .targets
                    .iter()
                    .map(|a| crate::bap::core_adapter::hex(*a))
                    .collect::<Vec<_>>()
                || row.complete != instruction.complete
            {
                return Err(invalid(
                    "composition target receipt/candidate control mismatch",
                ));
            }
        } else if targets.stop.is_none() || instruction.complete || !instruction.targets.is_empty()
        {
            return Err(invalid("composition candidate indirect receipt absent"));
        }
    }
    for transfer in &targets.transfers {
        let source = guards
            .input
            .sites
            .iter()
            .find(|s| s.site == transfer.site)
            .ok_or_else(|| invalid("composition target source absent"))?;
        if transfer.ast != source.ast
            || transfer.bytes_hex != source.bytes_hex
            || transfer.ast_sha256 != crate::reports::sha256(source.ast.as_bytes())
        {
            return Err(invalid("composition paired semantic source mismatch"));
        }
    }
    guard::replay_report(&guards.input, guards)?;
    guard::validate_final_request(&guards.input, guards, &report.final_request_sha256)?;
    let originals: BTreeMap<_, _> = report
        .original_controls
        .iter()
        .map(|r| Ok((crate::bap::core_adapter::address(&r.site)?, &r.control)))
        .collect::<Result<_, Error>>()?;
    if originals.len() != report.original_controls.len()
        || report
            .original_controls
            .windows(2)
            .any(|w| w[0].site >= w[1].site)
        || originals.len() != guards.input.sites.len()
    {
        return Err(invalid("composition original control domain/order"));
    }
    for source in &guards.input.sites {
        let site = crate::bap::core_adapter::address(&source.site)?;
        let original = originals
            .get(&site)
            .ok_or_else(|| invalid("composition original source absent"))?;
        let instruction = candidate
            .instructions
            .get(&site)
            .ok_or_else(|| invalid("composition candidate source absent"))?;
        validate_original_control(source, original, &guards.input)?;
        let mut augmented = (*original).clone();
        if original.kind == guard::ControlKind::Indirect {
            if let Some(row) = targets.resolutions.iter().find(|r| r.site == source.site) {
                augmented.targets.extend(row.targets.iter().cloned());
                augmented.targets.sort();
                augmented.targets.dedup();
                augmented.complete = row.complete;
            } else if targets.stop.is_some() {
                augmented.complete = false;
            } else {
                return Err(invalid("composition missing indirect receipt"));
            }
        }
        if augmented != source.control
            || source.control != guard::CandidateControl::from_instruction(instruction)
        {
            return Err(invalid("composition unproved source control augmentation"));
        }
    }
    let sources: BTreeMap<_, _> = guards
        .input
        .sites
        .iter()
        .map(|s| (s.site.as_str(), s))
        .collect();
    for (&site, old) in &candidate.instructions {
        let actual = final_request
            .instructions
            .get(&site)
            .ok_or_else(|| invalid("composition final instruction absent"))?;
        let name = crate::bap::core_adapter::hex(site);
        let pending = sources
            .get(name.as_str())
            .map(|s| guard::recognize_pending_for_input(&guards.input, s))
            .transpose()?
            .flatten();
        if pending.is_some() {
            let source = sources[name.as_str()];
            if old.kind != InstructionKind::Ordinary
                || !old.uses.is_empty()
                || !old.may_defs.is_empty()
                || !old.must_defs.is_empty()
                || !candidate.decodable.contains(&site)
            {
                return Err(invalid("composition pending candidate committed effects"));
            }
            let decision = guards.guards.iter().find(|g| g.site == name);
            if let Some(ast) = decision.and_then(|d| d.normal_ast.as_deref()) {
                let bytes: Vec<_> = (0..source.bytes_hex.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&source.bytes_hex[i..i + 2], 16))
                    .collect::<Result<_, _>>()?;
                let expected = crate::bap::Backend::guard_normal_projection(
                    ast,
                    "MOVAPS-reviewed-store",
                    &bytes,
                    site,
                )?;
                if expected.instruction != *actual || !final_request.decodable.contains(&site) {
                    return Err(invalid("composition selected normal effects changed"));
                }
            } else if actual.kind != InstructionKind::Stop
                || !actual.fall.is_empty()
                || !actual.targets.is_empty()
                || actual.complete
                || actual.uses != candidate.locations
                || actual.may_defs != candidate.locations
                || !actual.must_defs.is_empty()
                || final_request.decodable.contains(&site)
            {
                return Err(invalid("composition unproved normal guard continuation"));
            }
        } else if old != actual
            || candidate.decodable.contains(&site) != final_request.decodable.contains(&site)
        {
            return Err(invalid(
                "composition final control/effects outside checked transform",
            ));
        }
    }
    Ok(())
}

/// Bind the immutable decoder control to the original typed BIL. Conservative
/// stopped and call/return summaries retain their producer trust boundary.
fn validate_original_control(
    source: &guard::CandidateSite,
    control: &guard::CandidateControl,
    input: &guard::GuardInput,
) -> Result<(), Error> {
    use guard::ControlKind as K;
    let bytes: Vec<_> = (0..source.bytes_hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&source.bytes_hex[i..i + 2], 16))
        .collect::<Result<_, _>>()?;
    let site = crate::bap::core_adapter::address(&source.site)?;
    let next = crate::bap::core_adapter::hex(
        site.checked_add(bytes.len() as u64)
            .ok_or_else(|| invalid("composition next address overflow"))?,
    );
    let expected_fall = if matches!(control.kind, K::Ordinary | K::Conditional | K::Call) {
        vec![next]
    } else {
        Vec::new()
    };
    if control.fall != expected_fall
        || (control.kind == K::Indirect && (!control.targets.is_empty() || control.complete))
        || (matches!(control.kind, K::Ordinary | K::Return | K::Stop)
            && !control.targets.is_empty())
    {
        return Err(invalid("composition original structural control"));
    }
    if guard::recognize_pending_for_input(input, source)?.is_some()
        || matches!(control.kind, K::Call | K::Return | K::Stop)
    {
        return Ok(());
    }
    let bil: Vec<crate::bap::ast::Stmt> = serde_json::from_str(&source.ast)?;
    if source.opaque {
        fn data_only(stmts: &[crate::bap::ast::Stmt]) -> bool {
            stmts.iter().all(|stmt| match stmt {
                crate::bap::ast::Stmt::Move { .. } => true,
                crate::bap::ast::Stmt::If { yes, no, .. } => data_only(yes) && data_only(no),
                _ => false,
            })
        }
        if control.kind != K::Ordinary || !data_only(&bil) {
            return Err(invalid("composition opaque original control"));
        }
        return Ok(());
    }
    let opcode = if bytes == [0x90] { "NOOP" } else { "" };
    let projected =
        crate::bap::projection::project_with_destination(&bil, opcode, &bytes, site, None)?;
    let allowed: std::collections::BTreeSet<_> = control
        .targets
        .iter()
        .chain(&control.fall)
        .map(|a| crate::bap::core_adapter::address(a))
        .collect::<Result<_, _>>()?;
    let valid = match control.kind {
        K::Ordinary => projected.targets.is_empty(),
        K::Jump | K::Conditional => {
            !projected.targets.is_empty()
                && projected
                    .targets
                    .iter()
                    .all(|a| a.is_some_and(|a| allowed.contains(&a)))
                && control.targets.iter().all(|a| {
                    crate::bap::core_adapter::address(a)
                        .is_ok_and(|a| projected.targets.contains(&Some(a)))
                })
        }
        K::Indirect => {
            !projected.targets.is_empty() && projected.targets.iter().any(Option::is_none)
        }
        _ => false,
    };
    if !valid {
        return Err(invalid("composition original BIL control disagreement"));
    }
    Ok(())
}
