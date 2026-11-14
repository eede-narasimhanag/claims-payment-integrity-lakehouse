"""Helpers to summarise rule output and score it against injected ground truth."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from claims_integrity.rules import RULE_FLAGS

# ground-truth anomaly label -> flag column that should catch it
ANOMALY_TO_FLAG = {
    "duplicate": "flag_duplicate",
    "overbilled": "flag_overbilled",
    "code_mismatch": "flag_code_mismatch",
    "outside_coverage": "flag_outside_coverage",
    "invalid_amount": "flag_invalid_amount",
}


def summarize_flags(flagged: DataFrame) -> DataFrame:
    """One row per rule: flagged line count and total paid amount on flagged lines."""
    parts = [
        flagged.where(F.col(col))
        .agg(
            F.lit(name).alias("rule"),
            F.count("*").alias("flagged_lines"),
            F.coalesce(F.sum("paid_amount"), F.lit(0)).alias("flagged_paid_amount"),
        )
        for col, name in RULE_FLAGS
    ]
    out = parts[0]
    for p in parts[1:]:
        out = out.unionByName(p)
    return out


def score_against_truth(
    spark: SparkSession, flagged: DataFrame, ground_truth: DataFrame
) -> list[dict]:
    """Precision / recall per rule using ground_truth(line_id, anomaly_type).

    Lines labelled with a different anomaly but caught by this rule count as false
    positives for this rule, so scores are conservative.
    """
    results = []
    for anomaly, col in ANOMALY_TO_FLAG.items():
        truth = ground_truth.where(F.col("anomaly_type") == anomaly).select("line_id").distinct()
        pred = flagged.where(F.col(col)).select("line_id").distinct()
        n_truth = truth.count()
        n_pred = pred.count()
        tp = truth.join(pred, "line_id", "inner").count()
        precision = tp / n_pred if n_pred else None
        recall = tp / n_truth if n_truth else None
        results.append(
            {
                "rule": col,
                "injected": n_truth,
                "flagged": n_pred,
                "true_positives": tp,
                "precision": None if precision is None else round(precision, 4),
                "recall": None if recall is None else round(recall, 4),
            }
        )
    return results
