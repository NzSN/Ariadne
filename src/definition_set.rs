//! Value-semantic definition sets. Completed analyses can share a sorted
//! definition universe and retain membership as bits instead of cloned strings.
use crate::model::Definition;
use std::cmp::Ordering;
use std::collections::BTreeSet;
use std::fmt;
use std::sync::Arc;

#[derive(Clone)]
enum Storage {
    Tree(BTreeSet<Definition>),
    Dense {
        universe: Arc<[Definition]>,
        words: Arc<[u64]>,
        len: usize,
    },
}

#[derive(Clone)]
pub struct DefinitionSet(Storage);

impl Default for DefinitionSet {
    fn default() -> Self {
        Self::new()
    }
}

impl DefinitionSet {
    pub fn new() -> Self {
        Self(Storage::Tree(BTreeSet::new()))
    }
    pub(crate) fn from_dense(universe: Arc<[Definition]>, words: Vec<u64>) -> Self {
        assert_eq!(words.len(), universe.len().div_ceil(64));
        #[allow(clippy::manual_is_multiple_of)]
        if universe.len() % 64 != 0 {
            assert_eq!(
                words.last().copied().unwrap_or(0) >> (universe.len() % 64),
                0
            );
        }
        let len = words.iter().map(|w| w.count_ones() as usize).sum();
        Self(Storage::Dense {
            universe,
            words: words.into(),
            len,
        })
    }
    fn tree(&mut self) -> &mut BTreeSet<Definition> {
        if matches!(self.0, Storage::Dense { .. }) {
            self.0 = Storage::Tree(self.iter().cloned().collect());
        }
        match &mut self.0 {
            Storage::Tree(tree) => tree,
            Storage::Dense { .. } => unreachable!(),
        }
    }
    pub fn len(&self) -> usize {
        match &self.0 {
            Storage::Tree(tree) => tree.len(),
            Storage::Dense { len, .. } => *len,
        }
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    /// Shared sorted universe and low-to-high 64-bit membership words, when
    /// retained compactly. These immutable slices expose every member exactly.
    pub fn compact_membership(&self) -> Option<(&[Definition], &[u64])> {
        match &self.0 {
            Storage::Tree(_) => None,
            Storage::Dense {
                universe, words, ..
            } => Some((universe, words)),
        }
    }
    pub fn contains(&self, value: &Definition) -> bool {
        match &self.0 {
            Storage::Tree(tree) => tree.contains(value),
            Storage::Dense {
                universe, words, ..
            } => universe
                .binary_search(value)
                .is_ok_and(|n| words[n / 64] & (1 << (n % 64)) != 0),
        }
    }
    pub fn insert(&mut self, value: Definition) -> bool {
        self.tree().insert(value)
    }
    pub fn remove(&mut self, value: &Definition) -> bool {
        self.tree().remove(value)
    }
    pub fn clear(&mut self) {
        self.0 = Storage::Tree(BTreeSet::new());
    }
    pub fn retain(&mut self, predicate: impl FnMut(&Definition) -> bool) {
        self.tree().retain(predicate);
    }
    pub fn iter(&self) -> DefinitionIter<'_> {
        match &self.0 {
            Storage::Tree(tree) => DefinitionIter::Tree(tree.iter()),
            Storage::Dense {
                universe,
                words,
                len,
            } => DefinitionIter::Dense {
                universe,
                words,
                front: 0,
                back: universe.len(),
                remaining: *len,
            },
        }
    }
    pub fn range<'a, R: std::ops::RangeBounds<Definition> + 'a>(
        &'a self,
        range: R,
    ) -> Box<dyn DoubleEndedIterator<Item = &'a Definition> + 'a> {
        match &self.0 {
            Storage::Tree(tree) => Box::new(tree.range(range)),
            Storage::Dense { .. } => Box::new(self.iter().filter(move |d| range.contains(*d))),
        }
    }
    pub fn is_subset(&self, other: &Self) -> bool {
        if let (
            Storage::Dense {
                universe: a,
                words: x,
                ..
            },
            Storage::Dense {
                universe: b,
                words: y,
                ..
            },
        ) = (&self.0, &other.0)
        {
            if Arc::ptr_eq(a, b) {
                return x.iter().zip(y.iter()).all(|(x, y)| x & !y == 0);
            }
        }
        self.iter().all(|d| other.contains(d))
    }
    pub fn is_disjoint(&self, other: &Self) -> bool {
        self.iter().all(|d| !other.contains(d))
    }
    pub fn difference<'a>(&'a self, other: &'a Self) -> impl Iterator<Item = &'a Definition> {
        self.iter().filter(|d| !other.contains(d))
    }
    pub fn intersection<'a>(&'a self, other: &'a Self) -> impl Iterator<Item = &'a Definition> {
        self.iter().filter(|d| other.contains(d))
    }
    pub fn union<'a>(&'a self, other: &'a Self) -> impl Iterator<Item = &'a Definition> {
        self.iter()
            .chain(other.difference(self))
            .collect::<BTreeSet<_>>()
            .into_iter()
    }
}

pub enum DefinitionIter<'a> {
    Tree(std::collections::btree_set::Iter<'a, Definition>),
    Dense {
        universe: &'a [Definition],
        words: &'a [u64],
        front: usize,
        back: usize,
        remaining: usize,
    },
}
impl<'a> Iterator for DefinitionIter<'a> {
    type Item = &'a Definition;
    fn next(&mut self) -> Option<Self::Item> {
        match self {
            Self::Tree(tree) => tree.next(),
            Self::Dense {
                universe,
                words,
                front,
                back,
                remaining,
            } => {
                while *front < *back {
                    let bits = words[*front / 64] & (u64::MAX << (*front % 64));
                    if bits != 0 {
                        let n = *front / 64 * 64 + bits.trailing_zeros() as usize;
                        if n >= *back {
                            break;
                        }
                        *front = n + 1;
                        *remaining -= 1;
                        return Some(&universe[n]);
                    }
                    *front = (*front / 64 + 1) * 64;
                }
                *remaining = 0;
                None
            }
        }
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        let n = match self {
            Self::Tree(tree) => tree.len(),
            Self::Dense { remaining, .. } => *remaining,
        };
        (n, Some(n))
    }
}
impl DoubleEndedIterator for DefinitionIter<'_> {
    fn next_back(&mut self) -> Option<Self::Item> {
        match self {
            Self::Tree(tree) => tree.next_back(),
            Self::Dense {
                universe,
                words,
                front,
                back,
                remaining,
            } => {
                while *front < *back {
                    let last = *back - 1;
                    let bits = words[last / 64] & (u64::MAX >> (63 - last % 64));
                    if bits != 0 {
                        let n = last / 64 * 64 + 63 - bits.leading_zeros() as usize;
                        if n < *front {
                            break;
                        }
                        *back = n;
                        *remaining -= 1;
                        return Some(&universe[n]);
                    }
                    *back = last / 64 * 64;
                }
                *remaining = 0;
                None
            }
        }
    }
}
impl ExactSizeIterator for DefinitionIter<'_> {}
impl std::iter::FusedIterator for DefinitionIter<'_> {}
impl Extend<Definition> for DefinitionSet {
    fn extend<I: IntoIterator<Item = Definition>>(&mut self, values: I) {
        self.tree().extend(values);
    }
}
impl FromIterator<Definition> for DefinitionSet {
    fn from_iter<I: IntoIterator<Item = Definition>>(values: I) -> Self {
        Self(Storage::Tree(values.into_iter().collect()))
    }
}
impl<const N: usize> From<[Definition; N]> for DefinitionSet {
    fn from(values: [Definition; N]) -> Self {
        values.into_iter().collect()
    }
}
impl<'a> IntoIterator for &'a DefinitionSet {
    type Item = &'a Definition;
    type IntoIter = DefinitionIter<'a>;
    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}
impl IntoIterator for DefinitionSet {
    type Item = Definition;
    type IntoIter = std::collections::btree_set::IntoIter<Definition>;
    fn into_iter(self) -> Self::IntoIter {
        match self.0 {
            Storage::Tree(tree) => tree.into_iter(),
            Storage::Dense { .. } => self.iter().cloned().collect::<BTreeSet<_>>().into_iter(),
        }
    }
}
impl PartialEq for DefinitionSet {
    fn eq(&self, other: &Self) -> bool {
        if self.len() != other.len() {
            return false;
        }
        if let (
            Storage::Dense {
                universe: a,
                words: x,
                ..
            },
            Storage::Dense {
                universe: b,
                words: y,
                ..
            },
        ) = (&self.0, &other.0)
        {
            if Arc::ptr_eq(a, b) {
                return x == y;
            }
        }
        self.iter().eq(other.iter())
    }
}
impl Eq for DefinitionSet {}
impl Ord for DefinitionSet {
    fn cmp(&self, other: &Self) -> Ordering {
        self.iter().cmp(other.iter())
    }
}
impl PartialOrd for DefinitionSet {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl fmt::Debug for DefinitionSet {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_set().entries(self.iter()).finish()
    }
}

#[cfg(test)]
#[path = "../tests/core/definition_set.rs"]
mod tests;
