"""Shared names so notebooks, SQL and tests agree. Override with environment variables."""

import os

CATALOG = os.getenv("CATALOG", "workspace")  # default catalog in Databricks Free Edition
BRONZE_SCHEMA = "bronze"
SILVER_SCHEMA = "silver"
GOLD_SCHEMA = "gold"
LANDING_VOLUME = os.getenv("LANDING_VOLUME", f"/Volumes/{CATALOG}/{BRONZE_SCHEMA}/raw_landing")

ENTITIES = ["claim_lines", "eligibility", "members", "providers", "procedure_dx_rules"]
