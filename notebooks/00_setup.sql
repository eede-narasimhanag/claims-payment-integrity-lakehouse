-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 00 - Setup: schemas and landing volume
-- MAGIC Run once. `workspace` is the default catalog in Databricks Free Edition; change it if yours differs.

-- COMMAND ----------

CREATE SCHEMA IF NOT EXISTS workspace.bronze COMMENT 'Raw landed claims data (strings, as received)';
CREATE SCHEMA IF NOT EXISTS workspace.silver COMMENT 'Typed, validated claims data';
CREATE SCHEMA IF NOT EXISTS workspace.gold   COMMENT 'Curated dimensional model and integrity flags';

-- COMMAND ----------

CREATE VOLUME IF NOT EXISTS workspace.bronze.raw_landing;
CREATE VOLUME IF NOT EXISTS workspace.bronze.checkpoints;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Upload each generated entity folder into the landing volume so the layout is:
-- MAGIC `/Volumes/workspace/bronze/raw_landing/<entity>/<file>.csv`
-- MAGIC (entities: claim_lines, eligibility, members, providers, procedure_dx_rules).
-- MAGIC Do **not** upload `ground_truth/` into the landing volume.
