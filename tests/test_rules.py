from datetime import date

from claims_integrity import rules

CLAIM_SCHEMA = (
    "claim_id string, line_id string, member_id string, provider_id string, "
    "service_date date, procedure_code string, diagnosis_code string, units int, "
    "billed_amount double, allowed_amount double, paid_amount double"
)


def claim(cid, lid, member="M1", prov="P1", sdate=date(2024, 3, 1), proc="PR100",
          dx="E11.9", units=1, billed=150.0, allowed=120.0, paid=96.0):
    return (cid, lid, member, prov, sdate, proc, dx, units, billed, allowed, paid)


def make(spark, rows):
    return spark.createDataFrame(rows, CLAIM_SCHEMA)


def flags(df, col):
    return {r["line_id"]: r[col] for r in df.select("line_id", col).collect()}


def test_duplicate_flags_only_later_copy(spark):
    df = make(spark, [
        claim("C1", "C1-L1"),
        claim("C2", "C2-L1"),                      # same member/provider/date/proc/billed
        claim("C3", "C3-L1", billed=151.0),         # different billed amount: not a duplicate
    ])
    got = flags(rules.flag_duplicate_lines(df), "flag_duplicate")
    assert got == {"C1-L1": False, "C2-L1": True, "C3-L1": False}


def test_overbilled_uses_per_unit_reference(spark):
    ref = spark.createDataFrame([("PR100", 120.0)], "procedure_code string, reference_unit_amount double")
    df = make(spark, [
        claim("C1", "ok", units=2, billed=300.0),   # 150 per unit vs 120 -> fine
        claim("C2", "over", units=1, billed=500.0), # 500 > 3 x 120
        claim("C3", "unknown", proc="PRXXX", billed=9999.0),  # no reference -> never flagged
        claim("C4", "zero_units", units=0, billed=500.0),     # guarded
    ])
    got = flags(rules.flag_overbilled(df, ref, multiplier=3.0), "flag_overbilled")
    assert got == {"ok": False, "over": True, "unknown": False, "zero_units": False}


def test_overbilled_derives_reference_when_missing(spark):
    rows = [claim(f"C{i}", f"L{i}", member=f"M{i}", allowed=100.0, billed=110.0) for i in range(5)]
    rows.append(claim("C9", "outlier", member="M9", allowed=100.0, billed=900.0))
    got = flags(rules.flag_overbilled(make(spark, rows)), "flag_overbilled")
    assert got["outlier"] is True
    assert not any(v for k, v in got.items() if k != "outlier")


def test_code_mismatch(spark):
    dx_rules = spark.createDataFrame(
        [("PR100", "E11"), ("PR100", "I10")], "procedure_code string, dx_prefix string"
    )
    df = make(spark, [
        claim("C1", "match", dx="E11.9"),
        claim("C2", "match2", dx="I10.0"),
        claim("C3", "mismatch", dx="J45.1"),
        claim("C4", "missing_dx", dx=None),
        claim("C5", "ungoverned", proc="PR999", dx="J45.1"),
    ])
    got = flags(rules.flag_code_mismatch(df, dx_rules), "flag_code_mismatch")
    assert got == {"match": False, "match2": False, "mismatch": True,
                   "missing_dx": True, "ungoverned": False}


def test_outside_coverage(spark):
    elig = spark.createDataFrame(
        [("M1", date(2023, 1, 1), date(2024, 12, 31)), ("M2", date(2023, 1, 1), None)],
        "member_id string, coverage_start date, coverage_end date",
    )
    df = make(spark, [
        claim("C1", "in_range", member="M1", sdate=date(2024, 6, 1)),
        claim("C2", "after_end", member="M1", sdate=date(2025, 2, 1)),
        claim("C3", "open_ended", member="M2", sdate=date(2030, 1, 1)),
        claim("C4", "before_start", member="M2", sdate=date(2022, 6, 1)),
        claim("C5", "no_eligibility", member="M3"),
    ])
    got = flags(rules.flag_outside_coverage(df, elig), "flag_outside_coverage")
    assert got == {"in_range": False, "after_end": True, "open_ended": False,
                   "before_start": True, "no_eligibility": True}


def test_invalid_amounts(spark):
    df = make(spark, [
        claim("C1", "ok"),
        claim("C2", "paid_gt_billed", billed=100.0, paid=150.0),
        claim("C3", "neg_paid", paid=-5.0),
        claim("C4", "zero_units", units=0),
        claim("C5", "null_paid", paid=None),        # null is not treated as invalid
    ])
    got = flags(rules.flag_invalid_amounts(df), "flag_invalid_amount")
    assert got == {"ok": False, "paid_gt_billed": True, "neg_paid": True,
                   "zero_units": True, "null_paid": False}


def test_apply_all_rules_adds_summary_columns(spark):
    dx_rules = spark.createDataFrame([("PR100", "E11")], "procedure_code string, dx_prefix string")
    elig = spark.createDataFrame(
        [("M1", date(2023, 1, 1), None)], "member_id string, coverage_start date, coverage_end date"
    )
    ref = spark.createDataFrame([("PR100", 120.0)], "procedure_code string, reference_unit_amount double")
    df = make(spark, [
        claim("C1", "clean"),
        claim("C2", "dup_and_mismatch"),            # duplicate of C1 ...
        claim("C3", "mismatch_only", dx="J45.1", billed=151.0),
    ])
    # make C2 a duplicate of C1 and a diagnosis mismatch at once
    df = df.withColumn(
        "diagnosis_code",
        rules.F.when(rules.F.col("line_id") == "dup_and_mismatch", rules.F.lit("J45.1"))
        .otherwise(rules.F.col("diagnosis_code")),
    )
    out = rules.apply_all_rules(df, elig, dx_rules, reference_prices=ref)
    rows = {r["line_id"]: r for r in out.collect()}
    assert rows["clean"]["is_flagged"] is False and rows["clean"]["flag_reasons"] is None
    assert rows["dup_and_mismatch"]["flag_count"] == 2
    assert set(rows["dup_and_mismatch"]["flag_reasons"].split(",")) == {"DUPLICATE_LINE", "PROC_DX_MISMATCH"}
    assert rows["mismatch_only"]["flag_reasons"] == "PROC_DX_MISMATCH"
