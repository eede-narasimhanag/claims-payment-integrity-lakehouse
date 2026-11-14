"""Payment-integrity rules over a canonical claim-line DataFrame.

Each rule is a pure function: DataFrame in, DataFrame out with one boolean
``flag_*`` column added. Nothing is dropped; flagged lines go to review, which is
how pre-/post-payment review works in practice.

Canonical claim-line columns
----------------------------
claim_id, line_id, member_id, provider_id, service_date (date), procedure_code,
diagnosis_code, units (int), billed_amount, allowed_amount, paid_amount
(``line_id`` must be unique per line).
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

# (flag column, human-readable reason code)
RULE_FLAGS = [
    ("flag_duplicate", "DUPLICATE_LINE"),
    ("flag_overbilled", "OVERBILLED"),
    ("flag_code_mismatch", "PROC_DX_MISMATCH"),
    ("flag_outside_coverage", "OUTSIDE_COVERAGE"),
    ("flag_invalid_amount", "INVALID_AMOUNT"),
]


def flag_duplicate_lines(df: DataFrame) -> DataFrame:
    """Flag every repeat of the same member/provider/date/procedure/billed amount.

    The first occurrence (ordered by claim_id, line_id) is kept clean; later
    copies are flagged.
    """
    w = Window.partitionBy(
        "member_id", "provider_id", "service_date", "procedure_code", "billed_amount"
    ).orderBy("claim_id", "line_id")
    return (
        df.withColumn("_dup_rank", F.row_number().over(w))
        .withColumn("flag_duplicate", F.col("_dup_rank") > 1)
        .drop("_dup_rank")
    )


def build_reference_unit_prices(df: DataFrame) -> DataFrame:
    """Median allowed amount per unit, per procedure code (data-derived reference)."""
    return (
        df.where(F.col("units") > 0)
        .groupBy("procedure_code")
        .agg(
            F.percentile_approx(F.col("allowed_amount") / F.col("units"), 0.5).alias(
                "reference_unit_amount"
            )
        )
    )


def flag_overbilled(
    df: DataFrame, reference_prices: DataFrame | None = None, multiplier: float = 3.0
) -> DataFrame:
    """Flag lines whose billed amount per unit exceeds ``multiplier`` x the reference.

    ``reference_prices``: columns procedure_code, reference_unit_amount. If omitted,
    the per-procedure median allowed amount per unit is derived from ``df`` itself.
    """
    if reference_prices is None:
        reference_prices = build_reference_unit_prices(df)
    ref = F.broadcast(reference_prices.select("procedure_code", "reference_unit_amount"))
    billed_per_unit = F.col("billed_amount") / F.col("units")
    cond = (
        (F.col("units") > 0)
        & F.col("reference_unit_amount").isNotNull()
        & (F.col("reference_unit_amount") > 0)
        & (billed_per_unit > F.lit(multiplier) * F.col("reference_unit_amount"))
    )
    return (
        df.join(ref, "procedure_code", "left")
        .withColumn("flag_overbilled", F.coalesce(cond, F.lit(False)))
        .drop("reference_unit_amount")
    )


def flag_code_mismatch(df: DataFrame, procedure_dx_rules: DataFrame) -> DataFrame:
    """Flag lines whose diagnosis does not support the billed procedure.

    ``procedure_dx_rules``: columns procedure_code, dx_prefix (one row per allowed
    diagnosis prefix). Procedures absent from the table are not governed and never
    flagged. A governed procedure with a missing diagnosis is flagged.
    """
    k = df.select("claim_id", "line_id", "procedure_code", "diagnosis_code").alias("k")
    r = procedure_dx_rules.select("procedure_code", "dx_prefix").alias("r")

    matched = (
        k.join(
            r,
            (F.col("k.procedure_code") == F.col("r.procedure_code"))
            & F.col("k.diagnosis_code").startswith(F.col("r.dx_prefix")),
            "inner",
        )
        .select(F.col("k.claim_id").alias("claim_id"), F.col("k.line_id").alias("line_id"))
        .distinct()
        .withColumn("_matched", F.lit(True))
    )
    governed = (
        k.join(
            r.select("procedure_code").distinct().alias("g"),
            F.col("k.procedure_code") == F.col("g.procedure_code"),
            "inner",
        )
        .select(F.col("k.claim_id").alias("claim_id"), F.col("k.line_id").alias("line_id"))
        .distinct()
        .withColumn("_governed", F.lit(True))
    )
    keys = ["claim_id", "line_id"]
    return (
        df.join(governed, keys, "left")
        .join(matched, keys, "left")
        .withColumn(
            "flag_code_mismatch",
            F.coalesce(F.col("_governed"), F.lit(False))
            & ~F.coalesce(F.col("_matched"), F.lit(False)),
        )
        .drop("_governed", "_matched")
    )


def flag_outside_coverage(df: DataFrame, eligibility: DataFrame) -> DataFrame:
    """Flag lines whose service date is not inside any coverage span for the member.

    ``eligibility``: member_id, coverage_start (date), coverage_end (date, null =
    open-ended). Members with no eligibility row are flagged.
    """
    k = df.select("claim_id", "line_id", "member_id", "service_date").alias("k")
    e = eligibility.select("member_id", "coverage_start", "coverage_end").alias("e")
    covered = (
        k.join(
            e,
            (F.col("k.member_id") == F.col("e.member_id"))
            & (F.col("k.service_date") >= F.col("e.coverage_start"))
            & (F.col("e.coverage_end").isNull() | (F.col("k.service_date") <= F.col("e.coverage_end"))),
            "inner",
        )
        .select(F.col("k.claim_id").alias("claim_id"), F.col("k.line_id").alias("line_id"))
        .distinct()
        .withColumn("_covered", F.lit(True))
    )
    return (
        df.join(covered, ["claim_id", "line_id"], "left")
        .withColumn("flag_outside_coverage", ~F.coalesce(F.col("_covered"), F.lit(False)))
        .drop("_covered")
    )


def flag_invalid_amounts(df: DataFrame) -> DataFrame:
    """Flag non-positive units/billed, negative paid, or paid greater than billed."""
    cond = (
        (F.col("units") <= 0)
        | (F.col("billed_amount") <= 0)
        | (F.col("paid_amount") < 0)
        | (F.col("paid_amount") > F.col("billed_amount"))
    )
    return df.withColumn("flag_invalid_amount", F.coalesce(cond, F.lit(False)))


def apply_all_rules(
    claims: DataFrame,
    eligibility: DataFrame,
    procedure_dx_rules: DataFrame,
    reference_prices: DataFrame | None = None,
    overbill_multiplier: float = 3.0,
) -> DataFrame:
    """Run every rule and add ``flag_count``, ``is_flagged`` and ``flag_reasons``."""
    out = flag_duplicate_lines(claims)
    out = flag_overbilled(out, reference_prices, overbill_multiplier)
    out = flag_code_mismatch(out, procedure_dx_rules)
    out = flag_outside_coverage(out, eligibility)
    out = flag_invalid_amounts(out)

    flag_count = sum((F.col(c).cast("int") for c, _ in RULE_FLAGS), F.lit(0))
    reasons = F.concat_ws(",", *[F.when(F.col(c), F.lit(name)) for c, name in RULE_FLAGS])
    return (
        out.withColumn("flag_count", flag_count)
        .withColumn("is_flagged", F.col("flag_count") > 0)
        .withColumn("flag_reasons", F.when(F.col("flag_count") > 0, reasons))
    )
