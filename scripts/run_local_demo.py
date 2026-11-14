#!/usr/bin/env python3
"""Run the rules locally on generated CSVs and score them against ground truth.

    python scripts/generate_claim_lines.py --out data/generated
    python scripts/run_local_demo.py --data data/generated

Needs Java + pyspark (see requirements-dev.txt). No Databricks required.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from claims_integrity.evaluate import score_against_truth, summarize_flags  # noqa: E402
from claims_integrity.rules import apply_all_rules  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--load", choices=["1", "2", "all"], default="all")
    a = ap.parse_args()
    d = Path(a.data)

    spark = (
        SparkSession.builder.master("local[2]").appName("claims-demo")
        .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false").getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    def read(entity, pattern="*.csv"):
        return spark.read.option("header", "true").csv(str(d / entity / pattern))

    pat = "*.csv" if a.load == "all" else f"*load{a.load}.csv"
    claims = (
        read("claim_lines", pat)
        .withColumn("service_date", F.to_date("service_date"))
        .withColumn("units", F.col("units").cast("int"))
        .withColumn("billed_amount", F.col("billed_amount").cast("decimal(12,2)"))
        .withColumn("allowed_amount", F.col("allowed_amount").cast("decimal(12,2)"))
        .withColumn("paid_amount", F.col("paid_amount").cast("decimal(12,2)"))
    )
    elig = (
        read("eligibility")
        .withColumn("coverage_start", F.to_date("coverage_start"))
        .withColumn("coverage_end", F.to_date("coverage_end"))
    )
    rules_ref = read("procedure_dx_rules")
    truth = read("ground_truth", pat)

    flagged = apply_all_rules(claims, elig, rules_ref).cache()
    print(f"\nlines: {flagged.count()}  flagged: {flagged.where('is_flagged').count()}\n")
    summarize_flags(flagged).show(truncate=False)
    print("Scored against injected ground truth:")
    for row in score_against_truth(spark, flagged, truth):
        print(row)
    spark.stop()


if __name__ == "__main__":
    main()
