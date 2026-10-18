use super::*;
#[test]
fn independent_four_bit_projection_oracle() {
    let oracle: serde_json::Value = serde_json::from_str(include_str!(
        "../investigation/fixtures/frame_question_oracle.json"
    ))
    .unwrap();
    for row in oracle["masks"].as_array().unwrap() {
        let bits = Bits {
            width: 4,
            known: row["mask"].as_u64().unwrap(),
            value: row["bits"].as_u64().unwrap(),
        };
        let constant = row["constant"].as_u64().unwrap();
        let input = Term {
            width: 4,
            kind: TermKind::Input {
                key: "RAX:0:false".into(),
            },
        };
        let env = Environment::from([("RAX".into(), bits)]);
        for (op, field) in [(8, "and_values"), (18, "add_values")] {
            let mut work = 100;
            let result = eval(
                &Term::binary(op, input.clone(), Term::constant(constant, 4)),
                &env,
                &mut work,
                0,
                64,
            )
            .unwrap();
            for value in row[field].as_array().unwrap() {
                assert!(
                    result.meet(15, value.as_u64().unwrap()).is_some(),
                    "{row} {field}"
                );
            }
            if field == "and_values" {
                let represented: Vec<_> =
                    (0..16).filter(|n| result.meet(15, *n).is_some()).collect();
                let expected: Vec<_> = row[field]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|n| n.as_u64().unwrap())
                    .collect();
                assert_eq!(represented, expected);
            }
        }
        for value in 0..16 {
            assert_eq!(
                bits.meet(15, value).is_some(),
                value & bits.known == bits.value
            );
        }
    }
}
#[test]
fn zero_work_and_unknown_memory_cannot_supply_concrete_values() {
    let input = Term {
        width: 64,
        kind: TermKind::Input {
            key: "RAX:0:false".into(),
        },
    };
    assert_eq!(eval(&input, &Environment::new(), &mut 0, 0, 64), None);
    assert_eq!(
        eval(&Term::unknown(64), &Environment::new(), &mut 10, 0, 64)
            .unwrap()
            .number(),
        None
    );
    for width in 1..=64 {
        let a = Bits::exact(width, 0);
        let b = Bits::exact(width, u64::MAX);
        assert_eq!(a.join(b).number(), None);
    }
}
