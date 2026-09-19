//! Public request setup only: no expected states or model-side result values.

use InstructionKind::*;
use ariadne::*;

fn locations(values: &[&str]) -> LocationSet {
    values.iter().map(|value| (*value).into()).collect()
}

fn instruction(
    kind: InstructionKind,
    fall: &[Address],
    targets: &[Address],
    complete: bool,
    uses: &[&str],
    must: &[&str],
    may: &[&str],
) -> Instruction {
    Instruction {
        kind,
        fall: fall.iter().copied().collect(),
        targets: targets.iter().copied().collect(),
        complete,
        uses: locations(uses),
        must_defs: locations(must),
        may_defs: locations(may),
    }
}

pub fn request(fixture: &str) -> Result<AnalysisRequest, String> {
    if !["Binary", "Dump", "Loop", "Closed", "Pipeline", "Calls"].contains(&fixture) {
        return Err(format!("unknown fixture {fixture}"));
    }
    let small = matches!(fixture, "Pipeline" | "Calls");
    let addresses: AddressSet = match fixture {
        "Pipeline" => [4096, 4100].into(),
        "Calls" => (1..=4).collect(),
        _ => (1..=7).collect(),
    };
    let mut r = AnalysisRequest {
        snapshot_id: match fixture {
            "Pipeline" => "pipeline-snapshot",
            "Calls" => "calls-snapshot",
            _ => "example-snapshot",
        }
        .into(),
        addresses: addresses.clone(),
        locations: if small {
            locations(&["x"])
        } else {
            locations(&["x", "target"])
        },
        entry_points: match fixture {
            "Pipeline" => [4096].into(),
            "Calls" => [1, 3].into(),
            _ => [1].into(),
        },
        slice_seeds: match fixture {
            "Pipeline" => [4100].into(),
            "Calls" => [2, 3].into(),
            "Loop" => [5].into(),
            _ => [4, 5].into(),
        },
        input_kind: if matches!(fixture, "Dump" | "Closed") {
            InputKind::Dump
        } else {
            InputKind::Binary
        },
        captured: if small {
            [].into()
        } else if matches!(fixture, "Binary" | "Dump") {
            [1, 3, 4].into()
        } else {
            [1, 3, 4, 5].into()
        },
        file_backed: if small {
            addresses.clone()
        } else {
            [1, 2, 3, 4, 5, 7].into()
        },
        trusted_fallback: if small { [].into() } else { [2, 7].into() },
        decodable: if small {
            addresses.clone()
        } else {
            (1..=6).collect()
        },
        ..AnalysisRequest::default()
    };
    for a in addresses {
        let i = match (fixture, a) {
            ("Pipeline", 4096) => instruction(Ordinary, &[4100], &[], true, &[], &["x"], &["x"]),
            ("Pipeline", _) => instruction(Return, &[], &[], true, &["x"], &[], &[]),
            ("Calls", 1) => instruction(Call, &[2], &[3, 4], true, &[], &[], &["x"]),
            ("Calls", _) => instruction(Return, &[], &[], true, &["x"], &[], &[]),
            ("Loop", 1) => instruction(Conditional, &[2], &[3], true, &[], &[], &[]),
            ("Loop", 2 | 3) => instruction(Ordinary, &[4], &[], true, &[], &["x"], &["x"]),
            ("Loop", 4) => instruction(Conditional, &[5], &[2], true, &["x"], &[], &[]),
            ("Loop", _) => instruction(Return, &[], &[], true, &["x"], &[], &[]),
            (_, 1) => instruction(Conditional, &[2], &[3], true, &[], &[], &[]),
            (_, 2) => instruction(Ordinary, &[4], &[], true, &[], &["x"], &["x"]),
            (_, 3) => instruction(
                Indirect,
                &[],
                if fixture == "Closed" {
                    &[4]
                } else {
                    &[4, 6, 7]
                },
                fixture == "Closed",
                &["target"],
                &[],
                &[],
            ),
            (_, 4) => instruction(
                Call,
                &[5],
                &[6],
                fixture == "Closed",
                &["x"],
                &[],
                &["x", "target"],
            ),
            _ => instruction(Return, &[], &[], true, &["x"], &[], &[]),
        };
        r.instructions.insert(a, i);
    }
    Ok(r)
}
