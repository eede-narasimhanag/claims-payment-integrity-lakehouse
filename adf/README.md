# ADF: metadata-driven ingestion (design)

Not built or run by the scaffold author: this is the design to implement in the ADF Studio, then commit through Git integration.

## Resources

- Storage account (ADLS Gen2): containers `landing` (where files arrive) and `raw` (partitioned by source/date).
- Azure SQL Database: `ctl.*` control tables and `curated.claim_line` (`adf/sql/01_control_tables.sql`).
- Data Factory with Git integration to this repo, root folder `adf/`.

## Pipelines

**`pl_ingest_all` (parent)**
1. Lookup: `SELECT * FROM ctl.ingestion_config WHERE is_active = 1`
2. ForEach (batch count small to stay inside free limits) -> Execute Pipeline `pl_ingest_source` with parameters from the row.

**`pl_ingest_source` (child, parameterised)**
1. Stored Procedure: `ctl.usp_log_run` (`STARTED`, `@pipeline().RunId`).
2. If `watermark_column` is set: Lookup max watermark from the source; filter the copy to `> last_watermark`.
3. Copy: `landing/<source_path>` -> `raw/<target_folder>/load_date=@{utcNow('yyyy-MM-dd')}` (dataset parameterised by folder and format).
4. For `claim_lines` only: second Copy into `curated.claim_line_stg` (auto-create table) then Stored Procedure `curated.usp_upsert_claim_line`.
5. On success: Stored Procedure `ctl.usp_update_watermark`, then `ctl.usp_log_run` (`SUCCEEDED`, rows read/written from the Copy output).
6. On failure path: `ctl.usp_log_run` (`FAILED`, `@activity('Copy').error.message`), then fail the pipeline.

## Triggers

Schedule trigger (daily) for `pl_ingest_all`. Add a storage-event trigger as an extension.

## Things to show in the portfolio

- Screenshot of `pl_ingest_all` and `pl_ingest_source` canvases.
- Query of `ctl.pipeline_run_log` showing SUCCEEDED and one deliberate FAILED run (rename a file) followed by a clean re-run.
- Evidence the upsert is idempotent: run twice, row count unchanged.
- Cost view in Cost Management, then delete the resource group.

## Handoff to Databricks

Not verified: whether ADF can trigger a Free Edition workspace. If it can't, copy the `raw/` files into the Databricks landing volume (upload or CLI)
and say so in the README. If you have a paid Azure Databricks workspace, use an ADF Databricks linked service instead.
