//! Sealed candidate control and independently replayed paired proof binding.
use super::{Error, guard_admission as guard, invalid, target_resolution as target};
use crate::{Address, AnalysisRequest, InstructionKind};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeMap;

mod legacy;

pub const LEGACY_PROFILE: &str = "captured-guarded-targets/v1";
pub const LEGACY_SCHEMA: &str = "ariadne.guarded-target-resolution/v1";
pub const LEGACY_V2_PROFILE: &str = "captured-guarded-targets/v2";
pub const LEGACY_V2_SCHEMA: &str = "ariadne.guarded-target-resolution/v2";
pub const PROFILE: &str = "captured-guarded-targets/v3";
pub const SCHEMA: &str = "ariadne.guarded-target-resolution/v3";
pub const ADVANCED_PROFILE: &str = "captured-guarded-targets/v4";
pub const ADVANCED_SCHEMA: &str = "ariadne.guarded-target-resolution/v4";
pub const PRE_ADVANCED_CHECKER: &str =
    "6f8a96e415998dbc9ea69f701ef72c76697746e1b1549fb117dd1ccee1cf82bc";
pub const MODEL_VERSION: &str = "ariadne.guarded-target-resolution/v3";
pub const LEGACY_V2_MODEL_SHA256: &str =
    "605fb57d42e755b7fee75511f66e6ad864a16c303bbf5ffb5bad8855c7d05675";
pub const LEGACY_V2_CHECKER_SHA256: &str =
    "dd277b844376234cce199ecae9e7bc9eee04dfa69390d2320c2349b4f11b6cb4";
pub const LEGACY_MODEL_SHA256: &str =
    "e142a6fd22d78044c444c26211b7c659a56fedb5f9e555aa20e3aa1be23e8b10";
pub const LEGACY_CHECKER_SHA256: &str =
    "c36c8876810e35ed10b7e366e650d7854958b0ad7b07d33084039d39b68e9580";

pub fn legacy_model_identity() -> String {
    crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/loop-closure/legacy-v1/AriadneGuardedTargetResolution.tla.txt"
    ))
}
pub fn legacy_checker_identity() -> String {
    crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/loop-closure/legacy-v1/composition.rs.txt"
    ))
}
pub fn generation(report: &Report) -> u8 {
    match (report.schema.as_str(), report.profile.as_str()) {
        (LEGACY_SCHEMA, LEGACY_PROFILE) => 1,
        (LEGACY_V2_SCHEMA, LEGACY_V2_PROFILE) => 2,
        (SCHEMA, PROFILE) => 3,
        (ADVANCED_SCHEMA, ADVANCED_PROFILE) => 4,
        _ => 0,
    }
}
pub fn is_legacy(report: &Report) -> bool {
    matches!(generation(report), 1 | 2)
}
pub fn contains_profile(profile: &str) -> bool {
    [LEGACY_PROFILE, LEGACY_V2_PROFILE, PROFILE, ADVANCED_PROFILE]
        .iter()
        .any(|p| profile.contains(p))
}
pub fn capture_domain(report: &Report) -> &'static str {
    match generation(report) {
        1 => "ariadne-composed-capture/v1",
        2 => "ariadne-composed-capture/v2",
        4 => "ariadne-composed-capture/v4",
        _ => "ariadne-composed-capture/v3",
    }
}
fn legacy_v2_model_identity() -> String {
    let composition = crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/caller-coverage/legacy-v2/AriadneGuardedTargetResolution.tla.txt"
    ));
    let loops = crate::reports::sha256(include_bytes!("../../Specs/AriadneLoopTargetClosure.tla"));
    crate::reports::sha256(
        format!("ariadne.guarded-target-model/v2\n{composition}\n{loops}\n").as_bytes(),
    )
}
fn legacy_v2_checker_identity() -> String {
    let composition = crate::reports::sha256(include_bytes!(
        "../../tests/bap/fixtures/caller-coverage/legacy-v2/composition.rs.txt"
    ));
    let loops = target::LEGACY_QUESTION_LOOP_ENGINE.to_owned();
    crate::reports::sha256(
        format!("ariadne.guarded-target-checker/v2\n{composition}\n{loops}\n").as_bytes(),
    )
}
pub fn model_identity() -> String {
    let composition = crate::reports::sha256(include_bytes!(
        "../../Specs/AriadneGuardedTargetResolution.tla"
    ));
    let loops = crate::reports::sha256(include_bytes!("../../Specs/AriadneLoopTargetClosure.tla"));
    let guards = guard::model_identity();
    crate::reports::sha256(
        format!("ariadne.guarded-target-model/v3\n{composition}\n{loops}\n{guards}\n").as_bytes(),
    )
}
pub fn checker_identity() -> String {
    let composition = crate::reports::sha256(include_bytes!("composition.rs"));
    let loops = target::loop_engine_identity();
    let guards = guard::checker_identity();
    crate::reports::sha256(
        format!("ariadne.guarded-target-checker/v3\n{composition}\n{loops}\n{guards}\n").as_bytes(),
    )
}
pub fn advanced_checker_identity() -> String {
    crate::reports::sha256(
        format!(
            "ariadne.guarded-target-checker/v4\n{}\n{}\n{}\n",
            crate::reports::sha256(include_bytes!("composition.rs")),
            target::loop_engine_identity(),
            guard::advanced_checker_identity()
        )
        .as_bytes(),
    )
}
pub fn value_digest(value: &Value) -> Result<String, Error> {
    Ok(crate::reports::sha256(&serde_json::to_vec(value)?))
}
fn typed_digest<T: Serialize>(value: &T) -> Result<String, Error> {
    value_digest(&serde_json::to_value(value)?)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OriginalControl {
    pub site: String,
    pub control: guard::CandidateControl,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Report {
    pub schema: String,
    pub profile: String,
    pub model_version: String,
    pub model_sha256: String,
    pub checker_sha256: String,
    pub snapshot: String,
    pub artifact_sha256: String,
    pub query_scope_sha256: String,
    pub candidate_epoch: u64,
    pub candidate: Value,
    pub original_controls: Vec<OriginalControl>,
    pub candidate_sha256: String,
    pub target_report_sha256: String,
    pub guard_report_sha256: String,
    pub final_request_sha256: String,
    pub binding_sha256: String,
}
pub fn candidate_request(report: &Report) -> Result<AnalysisRequest, Error> {
    crate::investigation::frame_paths::decode_guard_request(&report.candidate)
}
fn binding_digest(report: &Report) -> Result<String, Error> {
    value_digest(&json!([
        match generation(report) {
            1 => "ariadne-guarded-target-binding/v1",
            2 => "ariadne-guarded-target-binding/v2",
            4 => "ariadne-guarded-target-binding/v4",
            _ => "ariadne-guarded-target-binding/v3",
        },
        report.snapshot,
        report.artifact_sha256,
        report.query_scope_sha256,
        report.candidate_epoch,
        report.model_version,
        report.model_sha256,
        report.checker_sha256,
        report.candidate_sha256,
        report.original_controls,
        report.target_report_sha256,
        report.guard_report_sha256,
        report.final_request_sha256
    ]))
}
pub fn analysis_id(report: &Report) -> Result<String, Error> {
    if report.binding_sha256 != binding_digest(report)? {
        return Err(invalid("composition binding digest"));
    }
    value_digest(&json!([
        match generation(report) {
            1 => "ariadne-guarded-target-analysis/v1",
            2 => "ariadne-guarded-target-analysis/v2",
            4 => "ariadne-guarded-target-analysis/v4",
            _ => "ariadne-guarded-target-analysis/v3",
        },
        report.binding_sha256
    ]))
}

pub fn seal(
    candidate: &AnalysisRequest,
    original: &BTreeMap<Address, guard::CandidateControl>,
    epoch: u64,
    targets: &target::Report,
    guards: &guard::Report,
    final_request: &AnalysisRequest,
) -> Result<Report, Error> {
    let encoded = super::core_adapter::encode_request(candidate)?;
    let advanced = guard::is_advanced(guards);
    let mut report = Report {
        schema: if advanced { ADVANCED_SCHEMA } else { SCHEMA }.into(),
        profile: if advanced { ADVANCED_PROFILE } else { PROFILE }.into(),
        model_version: MODEL_VERSION.into(),
        model_sha256: model_identity(),
        checker_sha256: if advanced {
            advanced_checker_identity()
        } else {
            checker_identity()
        },
        snapshot: guards.input.snapshot.clone(),
        artifact_sha256: guards.input.artifact_sha256.clone(),
        query_scope_sha256: guards.input.query_scope_sha256.clone(),
        candidate_epoch: epoch,
        candidate_sha256: value_digest(&encoded)?,
        candidate: encoded,
        original_controls: original
            .iter()
            .map(|(site, control)| OriginalControl {
                site: super::core_adapter::hex(*site),
                control: control.clone(),
            })
            .collect(),
        target_report_sha256: typed_digest(targets)?,
        guard_report_sha256: typed_digest(guards)?,
        final_request_sha256: value_digest(&super::core_adapter::encode_request(final_request)?)?,
        binding_sha256: String::new(),
    };
    report.binding_sha256 = binding_digest(&report)?;
    validate(&report, targets, guards, final_request)?;
    Ok(report)
}

/// Replays both proofs on their owning graphs before admitting a final view.
/// Captured byte/read comparisons against the immutable reader remain its job.
pub fn validate(
    report: &Report,
    targets: &target::Report,
    guards: &guard::Report,
    final_request: &AnalysisRequest,
) -> Result<(), Error> {
    if generation(report) == 1 {
        if !guard::is_legacy(guards) {
            return Err(invalid(
                "legacy composition cannot admit current guard evidence",
            ));
        }
        if legacy_model_identity() != LEGACY_MODEL_SHA256
            || legacy_checker_identity() != LEGACY_CHECKER_SHA256
        {
            return Err(invalid("legacy composition fixture identities changed"));
        }
        return legacy::validate(report, targets, guards, final_request);
    }
    let previous = generation(report) == 2;
    let advanced = generation(report) == 4;
    let (schema, profile, model, checker) = if previous {
        if legacy_v2_model_identity() != LEGACY_V2_MODEL_SHA256
            || legacy_v2_checker_identity() != LEGACY_V2_CHECKER_SHA256
        {
            return Err(invalid("legacy v2 composition fixture identities changed"));
        }
        (
            LEGACY_V2_SCHEMA,
            LEGACY_V2_PROFILE,
            LEGACY_V2_MODEL_SHA256.to_owned(),
            LEGACY_V2_CHECKER_SHA256.to_owned(),
        )
    } else if advanced {
        (
            ADVANCED_SCHEMA,
            ADVANCED_PROFILE,
            model_identity(),
            advanced_checker_identity(),
        )
    } else {
        (SCHEMA, PROFILE, model_identity(), checker_identity())
    };
    if report.schema != schema
        || report.profile != profile
        || report.model_version != if advanced { MODEL_VERSION } else { schema }
        || report.model_sha256 != model
        || (report.checker_sha256 != checker
            && (previous
                || advanced
                || ![
                    PRE_ADVANCED_CHECKER,
                    "a66b79f4a78330eda3dad00b64802498a3ab289404007c1fd62bb521a5a380ee",
                ]
                .contains(&report.checker_sha256.as_str())))
        || guard::is_legacy(guards) != previous
        || guard::is_advanced(guards) != advanced
        || report.snapshot != guards.input.snapshot
        || report.snapshot != targets.snapshot
        || report.artifact_sha256 != guards.input.artifact_sha256
        || report.artifact_sha256 != targets.artifact_sha256
        || report.query_scope_sha256 != guards.input.query_scope_sha256
        || report.candidate_epoch != guards.input.candidate_epoch
        || targets.memory_premise != target::MEMORY_PREMISE
        || targets.profile
            != if advanced {
                target::ADVANCED_LOCAL_PROFILE
            } else {
                target::LOCAL_PROFILE
            }
        || targets.schema
            != if advanced {
                target::ADVANCED_SCHEMA
            } else {
                "ariadne.indirect-target-resolution/v3"
            }
        || report.candidate_sha256 != value_digest(&report.candidate)?
        || report.target_report_sha256 != typed_digest(targets)?
        || report.guard_report_sha256 != typed_digest(guards)?
        || report.final_request_sha256
            != value_digest(&super::core_adapter::encode_request(final_request)?)?
        || report.binding_sha256 != binding_digest(report)?
    {
        return Err(invalid("composition identity, proof or graph digest"));
    }
    let candidate = candidate_request(report)?;
    if report.candidate != super::core_adapter::encode_request(&candidate)?
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
        let name = super::core_adapter::hex(site);
        if let Some(row) = targets.resolutions.iter().find(|r| r.site == name) {
            if row.targets
                != instruction
                    .targets
                    .iter()
                    .map(|a| super::core_adapter::hex(*a))
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
        .map(|r| Ok((super::core_adapter::address(&r.site)?, &r.control)))
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
        let site = super::core_adapter::address(&source.site)?;
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
    guard::validate_normal_flow_request(&guards.input, &candidate)?;
    guard::validate_normal_flow_request(&guards.input, final_request)?;
    for (&site, old) in &candidate.instructions {
        let actual = final_request
            .instructions
            .get(&site)
            .ok_or_else(|| invalid("composition final instruction absent"))?;
        let name = super::core_adapter::hex(site);
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
                let expected = super::Backend::guard_normal_projection(
                    ast,
                    if previous {
                        "MOVAPS-reviewed-store"
                    } else {
                        "MOVAPS-reviewed-memory"
                    },
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
    let site = super::core_adapter::address(&source.site)?;
    let next = super::core_adapter::hex(
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
    let bil: Vec<super::ast::Stmt> = serde_json::from_str(&source.ast)?;
    if source.opaque {
        fn data_only(stmts: &[super::ast::Stmt]) -> bool {
            stmts.iter().all(|stmt| match stmt {
                super::ast::Stmt::Move { .. } => true,
                super::ast::Stmt::If { yes, no, .. } => data_only(yes) && data_only(no),
                _ => false,
            })
        }
        if control.kind != K::Ordinary || !data_only(&bil) {
            return Err(invalid("composition opaque original control"));
        }
        return Ok(());
    }
    let opcode = if bytes == [0x90] { "NOOP" } else { "" };
    let projected = super::projection::project_with_destination(&bil, opcode, &bytes, site, None)?;
    let allowed: std::collections::BTreeSet<_> = control
        .targets
        .iter()
        .chain(&control.fall)
        .map(|a| super::core_adapter::address(a))
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
                    super::core_adapter::address(a)
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
