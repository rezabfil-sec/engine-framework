#![allow(dead_code)]
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Measurement {
    pub total: u128,
    pub per_round_computation: Vec<u128>,
    pub per_round_total: Vec<u128>,
}

impl Measurement {
    pub fn combine(&mut self, other: Self) {
        other
            .per_round_computation
            .into_iter()
            .for_each(|x| self.per_round_computation.push(x));

        other
            .per_round_total
            .into_iter()
            .for_each(|x| self.per_round_total.push(x));

        self.total += other.total;
    }

    pub fn empty() -> Self {
        Measurement {
            total: 0,
            per_round_computation: Vec::new(),
            per_round_total: Vec::new(),
        }
    }
}

impl PartialEq for Measurement {
    fn eq(&self, other: &Self) -> bool {
        let mut res = true;

        res = res && self.total == other.total;
        res = res && self.per_round_computation.len() == other.per_round_computation.len();
        res = res && self.per_round_total.len() == other.per_round_total.len();
        if !res {
            return false;
        }

        for i in 0..self.per_round_computation.len() {
            if !res {
                return false;
            }
            res = res && self.per_round_computation[i] == other.per_round_computation[i]
        }

        for i in 0..self.per_round_total.len() {
            if !res {
                return false;
            }
            res = res && self.per_round_total[i] == other.per_round_total[i]
        }

        res
    }
}

impl Eq for Measurement {}
