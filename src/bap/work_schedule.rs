//! Private shared scheduling, with a reserved turn for every runnable band.
use std::collections::VecDeque;
pub(crate) struct FairQueue<T> {
    queues: [VecDeque<T>; 3],
    turn: usize,
    len: usize,
}
impl<T> Default for FairQueue<T> {
    fn default() -> Self {
        Self {
            queues: std::array::from_fn(|_| VecDeque::new()),
            turn: 0,
            len: 0,
        }
    }
}
impl<T> FairQueue<T> {
    pub(crate) fn push(&mut self, band: usize, value: T) {
        self.queues[band].push_back(value);
        self.len += 1;
    }
    pub(crate) fn len(&self) -> usize {
        self.len
    }
    pub(crate) fn pop(&mut self) -> Option<(usize, T)> {
        let preferred = [0, 1, 0, 2][self.turn];
        self.turn = (self.turn + 1) % 4;
        let band = if !self.queues[preferred].is_empty() {
            preferred
        } else {
            (0..3).find(|i| !self.queues[*i].is_empty())?
        };
        self.len -= 1;
        Some((
            band,
            self.queues[band]
                .pop_front()
                .expect("nonempty selected band"),
        ))
    }
}

#[cfg(test)]
#[path = "../../tests/bap/frame_question_schedule.rs"]
mod tests;
