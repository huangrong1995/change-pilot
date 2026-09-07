# Stage 1: Change Analysis

You are analyzing a raw R&D change-point description. **Do not generate customer-facing copy in this stage.**

Your job is to extract the structured analysis that the next stage will consume.

## Inputs

- `raw_text` (required): the R&D change-point description.
- `context` (optional): `{product, version, module}` — used only to disambiguate. Never invent.

## Output Structure

Produce a structured analysis:

```yaml
business_intent: <one-sentence business purpose>
change_types:
  - <one or more of: new_feature | optimization | bug_fix | compatibility | security_compliance | version_component>
business_facts:
  - <fact that should pass to customer output>
technical_details:
  - <implementation detail that should be hidden or abstracted>
hidden_details:
  - <internal identifier / file path / ID that must be hidden>
abstractions:
  - source: <technical source>
    target: <business-language replacement>
multiple_changes: <true | false>
merge_grouping: <if multiple_changes, describe which facts share a business purpose and should merge>
```

## Rules

- **Only judge what the source explicitly says.** No inference of benefits, performance, or UX impact.
- **Do not convert technical implementation into business value.** A "fix in scan_service.cpp" is a technical detail, not a customer benefit.
- **Recognize multiple independent changes.** If the source contains multiple distinct business purposes, list each one and decide merge/split.
- **Identify every internal identifier** in the source: BUG IDs, requirement IDs, 0A IDs, commit hashes, branches, file paths, internal component versions. Add them to `hidden_details`.
- **Use `rules/terminology.yaml` to decide retain/abstract/hide for each technical term.**
- **Use `rules/sensitive-patterns.yaml` to spot internal identifiers you may have missed.**

## Self-Check Before Producing Output

1. Does every claim in `business_facts` have explicit source support?
2. Have I scanned for BUG/需求/0A/Commit/Branch/file path patterns?
3. If there are multiple technical changes, have I decided merge vs split based on business purpose (not edit count)?
4. Are `change_types` from the controlled vocabulary?

If you cannot answer yes to all four, revise the analysis before emitting it.
