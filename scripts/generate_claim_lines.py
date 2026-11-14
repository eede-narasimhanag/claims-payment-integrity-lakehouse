#!/usr/bin/env python3
"""Generate synthetic claim lines with labelled, injected anomalies (stdlib only).

Members and providers can come from Synthea (patients.csv / providers.csv). Synthea's
claim files are not reshaped here; claim lines are generated so every injected
anomaly has a known label and the rules can be scored (precision / recall).

All procedure codes are invented demo codes (PR100...), not CPT/HCPCS. Diagnosis
prefixes are real ICD-10-CM category prefixes, but the procedure-to-diagnosis
pairings are made up for demonstration and carry no clinical meaning.

Output layout (one folder per entity, ready for Auto Loader / ADF landing):
  <out>/claim_lines/claim_lines_load{1,2}.csv
  <out>/members/members_load{1,2}.csv        (load2 = changed rows, for SCD2)
  <out>/providers/providers_load{1,2}.csv
  <out>/eligibility/eligibility_load1.csv
  <out>/procedure_dx_rules/procedure_dx_rules.csv
  <out>/ground_truth/ground_truth_load{1,2}.csv   (keep OUT of the pipeline)
"""

from __future__ import annotations

import argparse
import csv
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

PROCEDURES = [  # code, reference price per unit, valid dx prefixes (demo only)
    ("PR100", 120.0, ["E11", "I10"]),
    ("PR200", 85.0, ["J45", "J44"]),
    ("PR300", 250.0, ["M54", "M51"]),
    ("PR400", 60.0, ["Z00"]),
    ("PR500", 410.0, ["N18", "E11"]),
    ("PR600", 175.0, ["I10", "I25"]),
]
ALL_DX = ["E11", "I10", "J45", "J44", "M54", "M51", "Z00", "N18", "I25", "K21"]
POS = ["11", "21", "22", "23"]
STATES = ["MN", "TX", "CA", "NY", "FL", "AZ", "WA", "IL"]
SPECIALTIES = ["GENERAL PRACTICE", "CARDIOLOGY", "ORTHOPEDICS", "PULMONOLOGY", "NEPHROLOGY"]

RATES = {  # share of base lines receiving each anomaly
    "duplicate": 0.02,
    "overbilled": 0.015,
    "code_mismatch": 0.015,
    "outside_coverage": 0.01,
    "invalid_amount": 0.005,
}

LINE_FIELDS = [
    "claim_id", "line_id", "member_id", "provider_id", "service_date", "procedure_code",
    "diagnosis_code", "units", "billed_amount", "allowed_amount", "paid_amount",
    "place_of_service", "claim_status", "load_date",
]


def new_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128)))


def load_people(path, n, rng, kind):
    rows = []
    if path:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if kind == "member":
                    rows.append({
                        "member_id": r["Id"], "birth_date": r.get("BIRTHDATE", ""),
                        "gender": r.get("GENDER", ""), "state": r.get("STATE", "") or rng.choice(STATES),
                    })
                else:
                    rows.append({
                        "provider_id": r["Id"], "name": r.get("NAME", ""),
                        "specialty": r.get("SPECIALITY") or rng.choice(SPECIALTIES),
                        "state": r.get("STATE", "") or rng.choice(STATES),
                    })
                if len(rows) >= n:
                    break
    while len(rows) < n:
        if kind == "member":
            by = rng.randint(1940, 2015)
            rows.append({
                "member_id": new_id(rng), "birth_date": f"{by}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "gender": rng.choice(["F", "M"]), "state": rng.choice(STATES),
            })
        else:
            rows.append({
                "provider_id": new_id(rng), "name": f"Provider {len(rows) + 1}",
                "specialty": rng.choice(SPECIALTIES), "state": rng.choice(STATES),
            })
    return rows


def money(x: float) -> str:
    return f"{x:.2f}"


def make_lines(rng, members, providers, elig, claim_no, n_lines, d_from, d_to, load_date):
    """Create ~n_lines clean lines. Returns (lines, next_claim_no)."""
    lines = []
    span = (d_to - d_from).days
    while len(lines) < n_lines:
        claim_no += 1
        claim_id = f"CLM{claim_no:08d}"
        m = rng.choice(members)["member_id"]
        p = rng.choice(providers)["provider_id"]
        sdate = d_from + timedelta(days=rng.randint(0, span))
        pos = rng.choice(POS)
        for k in range(1, rng.randint(1, 3) + 1):
            code, ref, prefixes = rng.choice(PROCEDURES)
            units = rng.randint(1, 3)
            allowed = ref * units * rng.uniform(0.9, 1.1)
            billed = allowed * rng.uniform(1.0, 1.8)
            paid = allowed * 0.8
            lines.append({
                "claim_id": claim_id, "line_id": f"{claim_id}-L{k}", "member_id": m, "provider_id": p,
                "service_date": sdate.isoformat(), "procedure_code": code,
                "diagnosis_code": f"{rng.choice(prefixes)}.{rng.randint(0, 9)}", "units": units,
                "billed_amount": money(billed), "allowed_amount": money(allowed), "paid_amount": money(paid),
                "place_of_service": pos, "claim_status": "PAID", "load_date": load_date,
            })
    return lines, claim_no


def inject(rng, lines, elig, claim_no, load_date):
    """Mutate/append lines with anomalies. Returns (lines, truth, next_claim_no)."""
    truth = []
    idx = list(range(len(lines)))
    rng.shuffle(idx)
    pos = 0

    def take(rate):
        nonlocal pos
        n = max(1, int(len(lines) * rate))
        chunk, pos = idx[pos:pos + n], pos + n
        return chunk

    prefixes_by_code = {c: pre for c, _, pre in PROCEDURES}
    base_n = len(lines)

    for i in take(RATES["overbilled"]):
        ln = lines[i]
        ln["billed_amount"] = money(float(ln["allowed_amount"]) * rng.uniform(4.0, 8.0))
        truth.append((ln["line_id"], "overbilled"))
    for i in take(RATES["code_mismatch"]):
        ln = lines[i]
        bad = [d for d in ALL_DX if d not in prefixes_by_code[ln["procedure_code"]]]
        ln["diagnosis_code"] = f"{rng.choice(bad)}.{rng.randint(0, 9)}"
        truth.append((ln["line_id"], "code_mismatch"))
    for i in take(RATES["outside_coverage"]):
        ln = lines[i]
        e = elig[ln["member_id"]]
        if e["coverage_end"]:
            d = date.fromisoformat(e["coverage_end"]) + timedelta(days=rng.randint(30, 120))
        else:
            d = date.fromisoformat(e["coverage_start"]) - timedelta(days=rng.randint(30, 120))
        ln["service_date"] = d.isoformat()
        truth.append((ln["line_id"], "outside_coverage"))
    for i in take(RATES["invalid_amount"]):
        ln = lines[i]
        ln["paid_amount"] = money(float(ln["billed_amount"]) * 1.5)
        truth.append((ln["line_id"], "invalid_amount"))

    dup_sources = take(RATES["duplicate"])  # clean lines only
    extra = []
    for i in dup_sources:
        claim_no += 1
        src = dict(lines[i])
        cid = f"CLM{claim_no:08d}"
        src.update({"claim_id": cid, "line_id": f"{cid}-L1"})
        extra.append(src)
        truth.append((src["line_id"], "duplicate"))
    assert base_n == len(lines)
    return lines + extra, truth, claim_no


def write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--patients", help="Synthea patients.csv (optional)")
    ap.add_argument("--providers", help="Synthea providers.csv (optional)")
    ap.add_argument("--members", type=int, default=2000)
    ap.add_argument("--provider-count", type=int, default=150)
    ap.add_argument("--lines", type=int, default=50000, help="approx. clean lines in load 1")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)

    rng = random.Random(a.seed)
    out = Path(a.out)
    members = load_people(a.patients, a.members, rng, "member")
    providers = load_people(a.providers, a.provider_count, rng, "provider")

    # eligibility: start in 2022; end is open (blank) or 2024-12-31
    elig = {}
    for m in members:
        start = date(2022, 1, 1) + timedelta(days=rng.randint(0, 364))
        end = "" if rng.random() < 0.7 else "2024-12-31"
        elig[m["member_id"]] = {"member_id": m["member_id"], "coverage_start": start.isoformat(), "coverage_end": end}

    # ---- load 1 ----
    L1 = "2024-07-01"
    lines1, claim_no = make_lines(rng, members, providers, elig, 0, a.lines, date(2023, 1, 1), date(2024, 6, 30), L1)
    lines1, truth1, claim_no = inject(rng, lines1, elig, claim_no, L1)
    for m in members:
        m["load_date"] = L1
    for p in providers:
        p["load_date"] = L1

    write_csv(out / "claim_lines" / "claim_lines_load1.csv", LINE_FIELDS, lines1)
    write_csv(out / "members" / "members_load1.csv", ["member_id", "birth_date", "gender", "state", "load_date"], members)
    write_csv(out / "providers" / "providers_load1.csv", ["provider_id", "name", "specialty", "state", "load_date"], providers)
    write_csv(out / "eligibility" / "eligibility_load1.csv", ["member_id", "coverage_start", "coverage_end"], elig.values())
    write_csv(
        out / "procedure_dx_rules" / "procedure_dx_rules.csv", ["procedure_code", "dx_prefix"],
        [{"procedure_code": c, "dx_prefix": p} for c, _, pre in PROCEDURES for p in pre],
    )
    write_csv(out / "ground_truth" / "ground_truth_load1.csv", ["line_id", "anomaly_type"],
              [{"line_id": lid, "anomaly_type": t} for lid, t in truth1])

    # ---- load 2: changed members/providers (SCD2) + new claim lines ----
    L2 = "2025-01-01"
    changed_m = []
    for m in rng.sample(members, max(1, int(len(members) * 0.05))):
        c = dict(m)
        c["state"] = rng.choice([s for s in STATES if s != m["state"]])
        c["load_date"] = L2
        changed_m.append(c)
    changed_p = []
    for p in rng.sample(providers, max(1, int(len(providers) * 0.03))):
        c = dict(p)
        c["specialty"] = rng.choice([s for s in SPECIALTIES if s != p["specialty"]])
        c["load_date"] = L2
        changed_p.append(c)
    lines2, claim_no = make_lines(rng, members, providers, elig, claim_no, max(100, a.lines // 5), date(2024, 7, 1), date(2024, 12, 31), L2)
    lines2, truth2, claim_no = inject(rng, lines2, elig, claim_no, L2)

    write_csv(out / "claim_lines" / "claim_lines_load2.csv", LINE_FIELDS, lines2)
    write_csv(out / "members" / "members_load2.csv", ["member_id", "birth_date", "gender", "state", "load_date"], changed_m)
    write_csv(out / "providers" / "providers_load2.csv", ["provider_id", "name", "specialty", "state", "load_date"], changed_p)
    write_csv(out / "ground_truth" / "ground_truth_load2.csv", ["line_id", "anomaly_type"],
              [{"line_id": lid, "anomaly_type": t} for lid, t in truth2])

    print(f"load1: {len(lines1)} lines, {len(truth1)} labelled anomalies")
    print(f"load2: {len(lines2)} lines, {len(truth2)} labelled anomalies")
    print(f"members changed in load2: {len(changed_m)}, providers changed: {len(changed_p)}")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
