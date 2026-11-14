# Architecture

## Layers

| Layer | Where | What happens | Why |
|---|---|---|---|
| Landing | UC Volume (Databricks) / ADLS `raw` (Azure) | Files exactly as delivered, one folder per entity | Immutable source of truth, reprocessable |
| Bronze | `workspace.bronze.*` | Auto Loader, all columns as strings, `_source_file`, `_ingest_ts` | Audit and replay without re-fetching |
| Silver | `workspace.silver.*` | Types cast, structural expectations, quarantine table | Trusted, queryable claims |
| Gold | `workspace.gold.*` | SCD2 `dim_member`/`dim_provider`, `fact_claim_line` with integrity flags, `rule_summary` | Analytics and review queues |

## Design decisions

1. **Flag, don't drop, business-rule violations.** Duplicates and overbilled lines still exist and may be legitimate on review; silver only drops rows that are structurally unusable (null keys, no date) and keeps them in quarantine.
2. **Rules live in a tested Python package**, not inside notebooks, so they run in CI and in Databricks unchanged.
3. **Bronze is strings.** Schema drift or a bad value never fails ingestion; typing and validation happen in silver where failures are visible and counted.
4. **SCD2 on member/provider.** A claim should be analysed against the member/provider attributes valid at the time (state, specialty).
5. **Idempotent loads.** Auto Loader checkpoints files; ADF upserts by `line_id`, and watermarks advance only after a successful copy.
6. **Orchestration.** Databricks Workflow: bronze -> (silver pipeline || SCD2 dims) -> rules/gold. ADF handles the Azure-side ingestion and audit log.

## Free-tier constraints that shape the design

- Databricks Free Edition: serverless only, restricted outbound internet (so data is uploaded to a Volume instead of pulled from APIs), limited concurrent tasks, one active pipeline.
- ADF is not verified to trigger a Free Edition workspace. Treat ADF -> Databricks as a documented handoff (files copied to the Volume) unless you confirm otherwise.

## Security and privacy (synthetic-data practice, not a compliance claim)

- Member IDs masked for non-auditor roles (`sql/06_governance.sql`).
- Least-privilege grants; no analyst access to bronze/silver.
- No secrets in the repo (`.env.example` only); use Azure Key Vault / Databricks secrets for real credentials.
- Tags classify tables (`synthetic`, `contains_identifiers`).
