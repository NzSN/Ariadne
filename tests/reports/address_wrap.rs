//! Strict I5c codec/render controls from public-bound supplied capture fixtures.
#[path = "../common/address_wrap.rs"]
mod address_wrap_fixture;
use address_wrap_fixture::{assert_oracle, limits, oracle, pipeline, prepare, question};
use ariadne::investigation::{
    AddressWrapAssertion, AddressWrapAssessment, AddressWrapKind, Classification,
    ZeroAddressConclusion,
};
use ariadne::reports::{
    Format, decode_address_wrap, encode_address_wrap, render_address_wrap, sha256,
};
use serde_json::{Value, json};
use std::collections::BTreeSet;

const REJECTIONS: [&str; 24] = [
    "duplicate-json-member",
    "unknown-top-level-field",
    "unknown-arithmetic-field",
    "sum-json-number",
    "sum-plus-sign",
    "sum-leading-zero",
    "sum-negative-zero",
    "sum-empty",
    "sum-whitespace",
    "sum-over-21-chars",
    "sum-below-domain",
    "sum-above-domain",
    "sum-not-B-plus-D",
    "wrong-wrap-kind",
    "wrong-effective-address",
    "wrong-signed-displacement",
    "arithmetic-through-early-gap",
    "definite-through-late-gap",
    "definite-through-budget-gap",
    "scope-digest",
    "content-digest",
    "dangling-evidence-ref",
    "cross-scope-claim-ref",
    "forged-observed-arithmetic",
];

fn sample(name: &str) -> AddressWrapAssessment {
    let row = oracle(name);
    let (prepared, completed) = prepare(name, |_| {});
    let value = pipeline(&prepared, &completed, question(), limits(&row)).unwrap();
    assert_oracle(&value, &row);
    value
}

fn arithmetic_claim(assertion: &AddressWrapAssertion) -> bool {
    matches!(
        assertion,
        AddressWrapAssertion::DecodedBase { .. }
            | AddressWrapAssertion::CapturedBase { .. }
            | AddressWrapAssertion::WideSum { .. }
            | AddressWrapAssertion::WrapKind { .. }
            | AddressWrapAssertion::ComputedAddress { .. }
    )
}

// Typed corruptions are re-signed with the compact typed field ordering.
// Dependent claims remain unchanged so reconstruction, rather than a stale
// content digest alone, rejects the forged semantic/source/claim fields.
fn refresh_content_id(value: &mut AddressWrapAssessment) {
    value.content_id.clear();
    value.content_id = sha256(&serde_json::to_vec(value).unwrap());
}

enum Corruption {
    Json(Vec<u8>),
    Typed(Box<AddressWrapAssessment>),
}

fn corrupt(name: &str, positive: &AddressWrapAssessment) -> Corruption {
    if [
        "duplicate-json-member",
        "unknown-top-level-field",
        "unknown-arithmetic-field",
        "sum-json-number",
    ]
    .contains(&name)
    {
        let mut wire = encode_address_wrap(positive).unwrap();
        match name {
            "duplicate-json-member" => {
                let compact = serde_json::to_string(&wire).unwrap();
                return Corruption::Json(
                    format!(
                        "{{\"schema\":{},{}",
                        serde_json::to_string(&positive.schema).unwrap(),
                        &compact[1..]
                    )
                    .into_bytes(),
                );
            }
            "unknown-top-level-field" => wire["extra"] = json!(true),
            "unknown-arithmetic-field" => wire["arithmetic"]["extra"] = json!(true),
            "sum-json-number" => wire["arithmetic"]["sum_before_reduction"] = json!(0),
            _ => unreachable!(),
        }
        return Corruption::Json(serde_json::to_vec(&wire).unwrap());
    }
    let mut value = match name {
        "arithmetic-through-early-gap" => sample("missing-integer"),
        "definite-through-late-gap" => sample("reported-before"),
        "definite-through-budget-gap" => sample("budget-e64-c35"),
        _ => positive.clone(),
    };
    if name == "arithmetic-through-early-gap" {
        value.arithmetic = positive.arithmetic.clone();
    }
    let bad_sum = match name {
        "sum-plus-sign" => Some("+18446744073709551624".to_string()),
        "sum-leading-zero" => Some("018446744073709551624".to_string()),
        "sum-negative-zero" => Some("-0".to_string()),
        "sum-empty" => Some(String::new()),
        "sum-whitespace" => Some(" 18446744073709551624".to_string()),
        "sum-over-21-chars" => Some("1".repeat(22)),
        "sum-below-domain" => Some("-2147483649".to_string()),
        "sum-above-domain" => Some("18446744075857035263".to_string()),
        "sum-not-B-plus-D" => Some("18446744073709551625".to_string()),
        _ => None,
    };
    if let Some(sum) = bad_sum {
        value.arithmetic.as_mut().unwrap().sum_before_reduction = sum;
        if name == "sum-not-B-plus-D" {
            value.arithmetic.as_mut().unwrap().effective_address.value = 9;
        }
    }
    match name {
        "wrong-wrap-kind" => value.arithmetic.as_mut().unwrap().wrap_kind = AddressWrapKind::None,
        "wrong-effective-address" => value.arithmetic.as_mut().unwrap().effective_address.value = 9,
        "wrong-signed-displacement" => {
            let arithmetic = value.arithmetic.as_mut().unwrap();
            arithmetic.signed_displacement = 15;
            arithmetic.displacement_bits.value = 15;
            arithmetic.sum_before_reduction = "18446744073709551623".into();
            arithmetic.effective_address.value = 7;
        }
        "definite-through-late-gap" | "definite-through-budget-gap" => {
            value.conclusion = ZeroAddressConclusion::ConsistentWithEvidence;
        }
        "scope-digest" => value.scope_id = "0".repeat(64),
        _ => {}
    }
    match name {
        "dangling-evidence-ref" => {
            let claim = value
                .claims
                .iter_mut()
                .find(|claim| arithmetic_claim(&claim.assertion))
                .unwrap();
            claim.evidence_refs = vec![format!("i5c-evidence:{}", "0".repeat(64))];
        }
        "cross-scope-claim-ref" => {
            value.claims[0] = sample("mov32mi-ordinary-positive").claims[0].clone();
        }
        "forged-observed-arithmetic" => {
            let claim = value
                .claims
                .iter_mut()
                .find(|claim| matches!(claim.assertion, AddressWrapAssertion::WideSum { .. }))
                .unwrap();
            claim.classification = Classification::Observed;
            claim.premises.clear();
        }
        _ => {}
    }
    refresh_content_id(&mut value);
    if name == "content-digest" {
        value.content_id = "0".repeat(64);
    }
    Corruption::Typed(Box::new(value))
}

#[test]
fn all_formats_roundtrip_the_typed_result_and_frozen_publication_limits() {
    for name in [
        "mov32mi-upper",
        "mov32mi-ordinary-positive",
        "mov32mi-negative-zero",
        "mov32mi-underflow",
        "missing-integer",
        "budget-e32-c64",
        "budget-e64-c35",
        "budget-e0-c0",
    ] {
        let value = sample(name);
        let wire = encode_address_wrap(&value).unwrap();
        assert_eq!(
            decode_address_wrap(&serde_json::to_vec(&wire).unwrap()).unwrap(),
            value
        );
        let json = render_address_wrap(&value, Format::Json).unwrap();
        assert_eq!(decode_address_wrap(json.as_bytes()).unwrap(), value);
        let dot = render_address_wrap(&value, Format::Dot).unwrap();
        let retained = dot
            .lines()
            .next()
            .unwrap()
            .strip_prefix("// address_wrap_assessment: ")
            .unwrap();
        assert_eq!(decode_address_wrap(retained.as_bytes()).unwrap(), value);
        assert!(dot.contains("digraph AddressWrap"));
        for evidence in &value.evidence {
            assert!(dot.contains(&serde_json::to_string(&evidence.id).unwrap()));
        }
        for claim in &value.claims {
            for reference in &claim.evidence_refs {
                assert!(dot.contains(&format!(
                    "{} -> {};",
                    serde_json::to_string(reference).unwrap(),
                    serde_json::to_string(&claim.id).unwrap()
                )));
            }
        }
    }
}

#[test]
fn unknown_and_all_gaps_precede_conditional_arithmetic_in_text() {
    for name in [
        "mov32mi-underflow",
        "reported-before",
        "missing-integer",
        "budget-e32-c64",
    ] {
        let value = sample(name);
        let text = render_address_wrap(&value, Format::Text).unwrap();
        let conclusion = text.find("conclusion: Unknown").unwrap();
        let arithmetic = text
            .find("conditional arithmetic under the declared premises:")
            .unwrap_or(text.len());
        assert!(conclusion < arithmetic);
        for gap in &value.gaps {
            let at = text.find(&format!("gap: {gap}\n")).unwrap();
            assert!(conclusion < at && at < arithmetic);
        }
        for requirement in &value.evidence_requirements {
            let at = text.find(&format!("requires: {requirement}\n")).unwrap();
            assert!(conclusion < at && at < arithmetic);
        }
        assert_eq!(arithmetic < text.len(), value.arithmetic.is_some());
    }
}

#[test]
fn all_24_frozen_serialized_rejections_are_checked_without_stale_digest_shortcuts() {
    let matrix: Value = serde_json::from_slice(include_bytes!(
        "../input/fixtures/i5c/qualification-matrix.json"
    ))
    .unwrap();
    let declared: BTreeSet<_> = matrix["serialized_rejections"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| row["name"].as_str().unwrap())
        .collect();
    assert_eq!(declared.len(), 24);
    assert_eq!(declared, REJECTIONS.into_iter().collect::<BTreeSet<_>>());
    let positive = sample("mov32mi-upper");
    let mut parse_only = 0;
    let mut typed = 0;
    for name in REJECTIONS {
        match corrupt(name, &positive) {
            Corruption::Json(bytes) => {
                assert!(decode_address_wrap(&bytes).is_err(), "{name}");
                parse_only += 1;
            }
            Corruption::Typed(value) => {
                let bytes = serde_json::to_vec(&value).unwrap();
                assert!(decode_address_wrap(&bytes).is_err(), "{name}: decode");
                assert!(value.validate().is_err(), "{name}: validate");
                assert!(encode_address_wrap(&value).is_err(), "{name}: encode");
                for format in [Format::Text, Format::Json, Format::Dot] {
                    assert!(
                        render_address_wrap(&value, format).is_err(),
                        "{name}: render {format:?}"
                    );
                }
                typed += 1;
            }
        }
    }
    assert_eq!((parse_only, typed), (4, 20));
}

#[test]
#[ignore = "requires an explicit frozen I5c serialized mutation observer case"]
fn w5_selected_frozen_serialized_mutation_case() {
    let name = std::env::var("ARIADNE_I5C_MUTATION_CASE").unwrap();
    let rejection = name.strip_prefix("serialization:").unwrap();
    assert!(REJECTIONS.contains(&rejection));
    println!("I5C_W5_OBSERVER {}", json!({"case": name}));
    match corrupt(rejection, &sample("mov32mi-upper")) {
        Corruption::Json(bytes) => assert!(decode_address_wrap(&bytes).is_err()),
        Corruption::Typed(value) => {
            assert!(decode_address_wrap(&serde_json::to_vec(&value).unwrap()).is_err());
            assert!(value.validate().is_err());
            assert!(encode_address_wrap(&value).is_err());
            for format in [Format::Text, Format::Json, Format::Dot] {
                assert!(render_address_wrap(&value, format).is_err());
            }
        }
    }
}
