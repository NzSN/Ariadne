use super::model::*;
use crate::bap::{ast::Stmt, refinement::TransferReceipt, target_resolution::Transfer};
use crate::investigation::{BoundFrameStructure, Error, invalid};
use std::collections::BTreeMap;
pub(crate) struct Semantics {
    pub transfers: BTreeMap<u64, Transfer>,
    pub receipts: BTreeMap<u64, TransferReceipt>,
    pub unavailable: Vec<u64>,
}
pub(crate) fn materialize(
    source: &BoundFrameStructure,
    frame: usize,
    limits: &FrameQuestionLimits,
) -> Result<Semantics, Error> {
    let recovery = source
        .recoveries()
        .iter()
        .find(|(i, _)| *i == frame)
        .map(|(_, r)| r)
        .ok_or_else(|| invalid("question frame has no recovery"))?;
    let mut result = Semantics {
        transfers: BTreeMap::new(),
        receipts: BTreeMap::new(),
        unavailable: Vec::new(),
    };
    let mut bytes = 0usize;
    let sites: BTreeMap<_, _> = recovery
        .proofs()
        .guard
        .as_ref()
        .map(|g| g.input.sites.iter().map(|s| (s.site.as_str(), s)).collect())
        .unwrap_or_default();
    for site in &recovery.context().sites {
        let key = format!("0x{:016x}", site.va);
        let raw = sites.get(key.as_str()).copied();
        let Some(raw) = raw else {
            result.unavailable.push(site.va);
            continue;
        };
        let selected = recovery
            .alignment_hypotheses()
            .and_then(|r| r.normal_selection(site.va))
            .or_else(|| {
                recovery
                    .proofs()
                    .guard
                    .as_ref()
                    .and_then(|r| r.normal_selection(site.va))
            });
        let ast = selected.unwrap_or(&raw.ast);
        if site.semantic_status.as_deref() != Some("projected")
            || crate::reports::sha256(ast.as_bytes()) != site.ast_sha256.clone().unwrap_or_default()
        {
            result.unavailable.push(site.va);
            continue;
        }

        bytes = bytes
            .checked_add(ast.len())
            .ok_or_else(|| invalid("question AST byte overflow"))?;
        if bytes > limits.max_proof_bytes {
            return Err(invalid("question semantic evidence byte cap"));
        }
        let bil: Vec<Stmt> = serde_json::from_str(ast)?;
        let receipt = crate::bap::refinement::extract(&bil, site.va, site.bytes_hex.clone())?;
        receipt.validate(site)?;
        let bytes = (0..site.bytes_hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&site.bytes_hex[i..i + 2], 16))
            .collect::<Result<Vec<_>, _>>()?;
        let transfer = crate::bap::target_resolution::extract(&bil, site.va, &bytes)?;
        result.transfers.insert(site.va, transfer);
        result.receipts.insert(site.va, receipt);
    }
    Ok(result)
}
