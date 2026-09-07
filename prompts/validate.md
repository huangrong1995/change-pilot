# Stage 3: Output Validation

You are auditing a generated `customer_output` for the change-pilot skill.

Run through the 10 checks below. Each check produces a boolean in the `validation` block of the output. If any check fails, revise `customer_output` before emitting.

## The 10 Checks

### Check 1 — Code files
Does `customer_output` contain source file names (`*.cpp`, `*.java`, `*.so`, `*.jar`, etc.)?
- **Action**: delete or abstract to a business term.

### Check 2 — Git metadata
Does `customer_output` contain Commit / Git / Branch / Patch / Tag references?
- **Action**: delete.

### Check 3 — Internal IDs
Does `customer_output` contain BUG / 需求 / 0A / Jira IDs?
- **Action**: delete.

### Check 4 — Internal config
Does `customer_output` contain internal properties (`ro.*`, `persist.*`, `sys.*`), service names, AIDL / Binder references?
- **Action**: delete or abstract.

### Check 5 — Unsupported claims
Does `customer_output` introduce functionality, performance, or benefit that has no trace in `raw_text`?
- **Action**: delete the unsupported claim.

### Check 6 — Exaggeration
Does `customer_output` use forbidden strength words (显著, 大幅, 极大, 全面, 彻底, 完全, 明显) or unsupported benefit phrases (性能提升, 稳定性提升, 用户体验提升, 速度提升) without source support?
- **Action**: soften or remove.

### Check 7 — Business fact loss
Has `customer_output` dropped a core business fact from `analysis.business_facts`?
- **Action**: restore the missing fact.

### Check 8 — Merge correctness
If `raw_text` had multiple technical changes that share one business purpose, are they merged? If they have distinct business purposes, are they split?
- **Action**: re-merge or re-split accordingly.

### Check 9 — Over-length
Is `customer_output` longer than the change warrants?
- **Action**: compress. Simple changes: 1 sentence. Normal: title + 1 sentence. Complex: title + 1–2 sentences.

### Check 10 — Customer readability
Would a customer (not an R&D engineer) read this and understand what changed in the product?
- **Action**: rewrite if not.

## Output

Add a `validation` block to the final output:

```json
{
  "validation": {
    "technical_leakage": false,
    "internal_id_leakage": false,
    "unsupported_claim": false,
    "overstatement": false,
    "business_fact_loss": false,
    "merged_correctly": true,
    "passed": true
  }
}
```

If any individual check fails, set `passed` to false and revise `customer_output` until all checks pass.

## Final Output Shape

After validation passes:

- **Default mode**: return only `customer_output`.
- **Debug mode**: return `customer_output` + `analysis` + `validation`.

Never expose `technical_details`, `hidden_details`, `evidence`, internal reasoning, confidence scores, or chain-of-thought to the customer.
