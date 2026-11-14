# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Bronze ingestion (Auto Loader)
# MAGIC Lands raw CSVs as Delta tables, everything as strings, plus lineage columns.
# MAGIC Incremental: re-running only picks up new files (checkpointed).

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = "workspace"
LANDING = f"/Volumes/{CATALOG}/bronze/raw_landing"
CHECKPOINTS = f"/Volumes/{CATALOG}/bronze/checkpoints"
ENTITIES = ["claim_lines", "eligibility", "members", "providers", "procedure_dx_rules"]

# COMMAND ----------

def ingest(entity: str):
    stream = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINTS}/{entity}/schema")
        .load(f"{LANDING}/{entity}/")
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingest_ts", F.current_timestamp())
    )
    return (
        stream.writeStream.option("checkpointLocation", f"{CHECKPOINTS}/{entity}/ckpt")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)
        .toTable(f"{CATALOG}.bronze.{entity}")
    )


for e in ENTITIES:
    q = ingest(e)
    q.awaitTermination()
    print(e, "->", spark.table(f"{CATALOG}.bronze.{e}").count(), "rows")
