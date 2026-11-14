# Databricks notebook source
# MAGIC %md
# MAGIC # 04 - Apply payment-integrity rules and build the gold fact
# MAGIC Uses the tested rule library in `src/claims_integrity/rules.py`.
# MAGIC Run this notebook from a Databricks Git folder so `../src` exists.

# COMMAND ----------

import os
import sys

# Repo root is one level above notebooks/ when run from a Git folder. Verify with print(os.getcwd()).
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

from claims_integrity.evaluate import summarize_flags
from claims_integrity.rules import apply_all_rules

CATALOG = "workspace"

# COMMAND ----------

claims = spark.table(f"{CATALOG}.silver.silver_claim_line")
eligibility = spark.table(f"{CATALOG}.silver.silver_eligibility")
dx_rules = spark.table(f"{CATALOG}.bronze.procedure_dx_rules")

flagged = apply_all_rules(claims, eligibility, dx_rules)

(
    flagged.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.gold.fact_claim_line")
)

# COMMAND ----------

summary = summarize_flags(spark.table(f"{CATALOG}.gold.fact_claim_line"))
summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{CATALOG}.gold.rule_summary"
)
display(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC Optional scoring against the generator's ground truth: upload `ground_truth/*.csv` to a
# MAGIC separate volume, read it, and call `score_against_truth(spark, flagged, truth)` from
# MAGIC `claims_integrity.evaluate`. Keep that file out of the landing volume.
