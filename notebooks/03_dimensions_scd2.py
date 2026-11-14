# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Gold dimensions with SCD Type 2 (members, providers)
# MAGIC Replays bronze snapshots in `load_date` order. A changed tracked attribute closes the
# MAGIC current row (`is_current = false`, `effective_end`) and inserts a new current row.
# MAGIC
# MAGIC Pattern: stage every incoming row twice, once keyed (to close the old version) and once
# MAGIC with a NULL key (to insert the new version). Written for Delta `MERGE`; not run against a
# MAGIC live workspace by the author of this scaffold, so check the row counts in section 4.

# COMMAND ----------

CATALOG = "workspace"

DIMS = {
    "dim_member": {
        "bronze": f"{CATALOG}.bronze.members",
        "key": "member_id",
        "attrs": ["birth_date", "gender", "state"],     # tracked attributes
    },
    "dim_provider": {
        "bronze": f"{CATALOG}.bronze.providers",
        "key": "provider_id",
        "attrs": ["name", "specialty", "state"],
    },
}

# COMMAND ----------

def create_dim(name: str, key: str, attrs: list[str]):
    cols = ", ".join(f"{a} STRING" for a in attrs)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {CATALOG}.gold.{name} (
            {key} STRING, {cols}, attr_hash STRING,
            effective_start DATE, effective_end DATE, is_current BOOLEAN
        ) USING DELTA
    """)


def scd2_merge(name: str, bronze: str, key: str, attrs: list[str], load_date: str):
    attr_list = ", ".join(attrs)
    u_attrs = ", ".join("u." + a for a in attrs)
    coalesced = ", ".join("coalesce({}, '')".format(a) for a in attrs)
    hash_expr = "sha2(concat_ws('||', " + coalesced + "), 256)"
    target = f"{CATALOG}.gold.{name}"

    spark.sql(f"""
        CREATE OR REPLACE TEMP VIEW stg AS
        SELECT {key}, {attr_list}, {hash_expr} AS attr_hash, to_date(load_date) AS effective_start
        FROM {bronze}
        WHERE load_date = '{load_date}'
    """)

    spark.sql(f"""
        MERGE INTO {target} AS t
        USING (
            SELECT {key} AS merge_key, * FROM stg
            UNION ALL
            SELECT NULL AS merge_key, s.*
            FROM stg s JOIN {target} d
              ON s.{key} = d.{key} AND d.is_current AND s.attr_hash <> d.attr_hash
        ) AS u
        ON t.{key} = u.merge_key AND t.is_current = true
        WHEN MATCHED AND t.attr_hash <> u.attr_hash THEN
            UPDATE SET t.is_current = false, t.effective_end = u.effective_start
        WHEN NOT MATCHED THEN
            INSERT ({key}, {attr_list}, attr_hash, effective_start, effective_end, is_current)
            VALUES (u.{key}, {u_attrs}, u.attr_hash, u.effective_start, NULL, true)
    """)

# COMMAND ----------

for name, cfg in DIMS.items():
    create_dim(name, cfg["key"], cfg["attrs"])
    loads = [r[0] for r in spark.sql(f"SELECT DISTINCT load_date FROM {cfg['bronze']} ORDER BY 1").collect()]
    for ld in loads:
        scd2_merge(name, cfg["bronze"], cfg["key"], cfg["attrs"], ld)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Sanity checks (expect: exactly one current row per key; history rows = number of changes)

# COMMAND ----------

spark.sql(f"""
    SELECT 'dim_member' AS dim, count(*) AS rows, sum(CAST(is_current AS INT)) AS current_rows,
           count(DISTINCT member_id) AS keys FROM {CATALOG}.gold.dim_member
    UNION ALL
    SELECT 'dim_provider', count(*), sum(CAST(is_current AS INT)), count(DISTINCT provider_id)
    FROM {CATALOG}.gold.dim_provider
""").show()
