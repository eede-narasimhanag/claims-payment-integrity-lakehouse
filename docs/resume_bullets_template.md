# Resume bullet templates (fill with YOUR measured numbers only)

Put under "Projects", labelled personal / synthetic data. Delete any bullet you did not build or measure.

- Built a medallion (Bronze/Silver/Gold) claims lakehouse on Databricks processing **[N]** synthetic claim lines across
  claims, member, provider and eligibility data using Auto Loader, Delta Lake and declarative pipelines.
- Implemented **[N]** payment-integrity rules (duplicate, overbilling, diagnosis/procedure mismatch, out-of-coverage, invalid amount)
  as a PySpark package with **[N]** unit tests and GitHub Actions CI; flagged **[X]%** of lines in a labelled test set.
- Designed SCD Type 2 member and provider dimensions with Delta MERGE and validated one-current-row-per-key integrity.
- Reduced KPI query time from **[A]s to [B]s** on the fact table using [OPTIMIZE / liquid clustering / partitioning] (measured on [N] rows).
- Built a metadata-driven ADF ingestion framework (config table, parameterised pipelines, watermark incremental loads, audit log) loading **[N]** sources into ADLS Gen2 and Azure SQL.
- Applied Unity Catalog governance: column masking, row filters, least-privilege grants and lineage documentation.

Keep each bullet to the one metric you can defend in an interview.
