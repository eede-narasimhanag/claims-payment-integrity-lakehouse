# Runbook

## Daily run (Databricks Workflow `claims-daily-run`)

bronze_ingest -> silver pipeline + dimensions_scd2 -> rules_gold

## Health checks

| Check | How | Expected |
|---|---|---|
| New files ingested | Row counts in `bronze.*` vs files in the landing volume | Increase after each upload |
| Silver drops | Pipeline event log / expectation metrics | Small, stable; spikes mean a source format change |
| Quarantine volume | `SELECT count(*) FROM silver.silver_claim_line_quarantine` | Near zero on clean data |
| SCD2 integrity | Notebook 03 section 4 | Exactly one current row per key |
| Flag rate | `gold.rule_summary` | Stable day to day; large jumps need investigation |

## Failure handling

- **Bronze fails on a bad file**: move the file out of the landing folder, re-run; Auto Loader resumes from its checkpoint.
- **Silver expectation failures spike**: inspect quarantine rows and `_source_file`, fix the source or the cast, re-run (silver tables are rebuilt from bronze).
- **Rules notebook fails**: tests in CI should have caught logic errors; check input schema changes in silver.
- **ADF copy fails**: the run is logged as FAILED in `ctl.pipeline_run_log`; the watermark is not advanced, so a re-run repeats the same window safely.

## Reprocessing

Delete the silver/gold tables and re-run; bronze and landing are the source of truth. To reload bronze, delete the entity's checkpoint folder and the bronze table.

## Deployment

Merge to `main` after CI passes; `databricks bundle deploy -t dev` (validate first). ADF changes flow through the Git-integrated `adf/` folder.
