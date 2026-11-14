# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Silver: typed tables with data-quality expectations (declarative pipeline)
# MAGIC Add this notebook as the source of a pipeline whose target schema is `silver`
# MAGIC (see `databricks.yml`). Databricks has been renaming Delta Live Tables to
# MAGIC "Lakeflow Spark Declarative Pipelines"; if your workspace expects
# MAGIC `from pyspark import pipelines as dp`, swap `import dlt` / `dlt.` accordingly. Verify in the current docs.
# MAGIC
# MAGIC Structurally invalid rows are **dropped into a quarantine table**; business-rule
# MAGIC violations (duplicates, overbilling...) are NOT dropped here, they are flagged in gold.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

CATALOG = spark.conf.get("catalog", "workspace")

CLAIM_RULES = {
    "claim_id_present": "claim_id IS NOT NULL",
    "line_id_present": "line_id IS NOT NULL",
    "member_id_present": "member_id IS NOT NULL",
    "service_date_valid": "service_date IS NOT NULL",
    "billed_amount_present": "billed_amount IS NOT NULL",
}
QUARANTINE_FILTER = "NOT (" + " AND ".join(f"({r})" for r in CLAIM_RULES.values()) + ")"

# COMMAND ----------

@dlt.view(name="claim_lines_typed")
def claim_lines_typed():
    return (
        spark.read.table(f"{CATALOG}.bronze.claim_lines")
        .select(
            "claim_id", "line_id", "member_id", "provider_id",
            F.to_date("service_date").alias("service_date"),
            "procedure_code", "diagnosis_code",
            F.col("units").cast("int").alias("units"),
            F.col("billed_amount").cast("decimal(12,2)").alias("billed_amount"),
            F.col("allowed_amount").cast("decimal(12,2)").alias("allowed_amount"),
            F.col("paid_amount").cast("decimal(12,2)").alias("paid_amount"),
            "place_of_service", "claim_status",
            F.to_date("load_date").alias("load_date"),
            "_source_file", "_ingest_ts",
        )
        .dropDuplicates(["line_id"])
    )


@dlt.table(name="silver_claim_line", comment="Typed claim lines that pass structural checks")
@dlt.expect_all_or_drop(CLAIM_RULES)
@dlt.expect("units_positive", "units > 0")          # logged only
@dlt.expect("paid_not_negative", "paid_amount >= 0")  # logged only
def silver_claim_line():
    return dlt.read("claim_lines_typed")


@dlt.table(name="silver_claim_line_quarantine", comment="Rows that failed structural checks, kept for review")
def silver_claim_line_quarantine():
    return dlt.read("claim_lines_typed").filter(QUARANTINE_FILTER)

# COMMAND ----------

@dlt.table(name="silver_eligibility", comment="Member coverage spans")
@dlt.expect_or_drop("member_id_present", "member_id IS NOT NULL")
@dlt.expect_or_drop("coverage_start_present", "coverage_start IS NOT NULL")
@dlt.expect("end_after_start", "coverage_end IS NULL OR coverage_end >= coverage_start")
def silver_eligibility():
    return spark.read.table(f"{CATALOG}.bronze.eligibility").select(
        "member_id",
        F.to_date("coverage_start").alias("coverage_start"),
        F.to_date(F.nullif(F.col("coverage_end"), F.lit(""))).alias("coverage_end"),
    )
