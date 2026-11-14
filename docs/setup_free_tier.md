# Setup on free tiers

Check current terms before you start; free-tier rules change.

## A. Local (no accounts)

1. Install Python 3.11+ and Java 17+.
2. `pip install -r requirements-dev.txt`, then `pytest -q`.
3. `python scripts/generate_claim_lines.py --out data/generated`
4. `python scripts/run_local_demo.py --data data/generated`

## B. Databricks Free Edition

1. Sign up for Databricks Free Edition (serverless only; non-commercial use; log in regularly so the account is not deleted).
2. Connect your GitHub repo as a Git folder (Workspace > Create > Git folder) so `src/` sits next to `notebooks/`.
3. Run `notebooks/00_setup.sql`.
4. Upload each entity folder from `data/generated/` (except `ground_truth/`) into
   `/Volumes/workspace/bronze/raw_landing/<entity>/`. Upload `*_load1.csv` first.
5. Run `01_bronze_ingest.py`.
6. Create a pipeline from `02_silver_pipeline.py` (target schema `silver`, serverless) or deploy `databricks.yml`; run it.
7. Run `03_dimensions_scd2.py`, then `04_rules_gold.py`.
8. Upload the `*_load2.csv` files, re-run the workflow, and confirm: new claims appear, changed members get a second SCD2 row.
9. Run `sql/05_gold_kpis.sql`; build a dashboard from queries 1, 2 and 4.
10. Try `sql/06_governance.sql` and keep screenshots (lineage, tags, masks) in `docs/img/`.

Free Edition limits to remember: no custom compute or Scala/R, restricted outbound internet, 5 concurrent job tasks and one
active pipeline of each type.

## C. Azure free account (ADF + ADLS + Azure SQL)

Do this in the final stretch: the $200 credit lasts 30 days and needs a phone number and card for verification.

1. Create a budget alert immediately.
2. Create a resource group, a storage account with hierarchical namespace (ADLS Gen2, containers `landing` and `raw`), an Azure SQL Database (use the free offer if shown), and a Data Factory.
3. Run `adf/sql/01_control_tables.sql`, then load `adf/config/ingestion_config_sample.csv` into `ctl.ingestion_config`.
4. Follow `adf/README.md` to build the pipelines. Connect ADF to this GitHub repo with root folder `adf/` so the pipeline JSON is committed automatically.
5. Capture screenshots of runs, the audit table and monitoring views.
6. **Delete the resource group** when finished.

## D. GitHub Actions

Push the repo; `.github/workflows/ci.yml` runs ruff and pytest. Fix action versions if GitHub reports deprecations.
