use super::*;
use crate::DefinitionOrigin;

#[test]
fn dense_sets_preserve_order_membership_and_copy_on_write() {
    let universe: Arc<[Definition]> = (0..139)
        .map(|site| Definition {
            loc: "memory".into(),
            site,
            origin: DefinitionOrigin::Instruction,
        })
        .collect();
    for seed in 0..129u64 {
        let mut words = vec![0; 3];
        let mut tree = DefinitionSet::new();
        for (n, d) in universe.iter().enumerate() {
            if (n as u64 * 17 + seed) % 11 < 5 {
                words[n / 64] |= 1 << (n % 64);
                tree.insert(d.clone());
            }
        }
        let dense = DefinitionSet::from_dense(universe.clone(), words);
        assert_eq!(dense, tree);
        assert_eq!(
            dense.iter().rev().collect::<Vec<_>>(),
            tree.iter().rev().collect::<Vec<_>>()
        );
        assert_eq!(dense.len(), dense.iter().count());
        assert_eq!(
            dense
                .range(universe[13].clone()..=universe[129].clone())
                .collect::<Vec<_>>(),
            tree.range(universe[13].clone()..=universe[129].clone())
                .collect::<Vec<_>>()
        );
        let mut iter = dense.iter();
        let mut expected = tree.iter();
        loop {
            assert_eq!(iter.len(), expected.len());
            if expected.len() == 0 {
                break;
            }
            assert_eq!(iter.next(), expected.next());
            assert_eq!(iter.next_back(), expected.next_back());
        }
        assert!(dense.is_subset(&tree) && tree.is_subset(&dense));
        for d in universe.iter() {
            assert_eq!(dense.contains(d), tree.contains(d));
        }
        let saved = dense.clone();
        let mut changed = dense;
        changed.insert(universe[0].clone());
        changed.remove(&universe[1]);
        assert_eq!(saved, tree);
        changed.retain(|d| d.site % 2 == 0);
        assert!(changed.iter().all(|d| d.site % 2 == 0));
        changed.clear();
        assert!(changed.is_empty());
    }
}
