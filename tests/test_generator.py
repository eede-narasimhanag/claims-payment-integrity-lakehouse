import csv
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_claim_lines.py"
spec = importlib.util.spec_from_file_location("gen", SCRIPT)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_generator_outputs_are_consistent(tmp_path):
    gen.main(["--out", str(tmp_path), "--members", "50", "--provider-count", "10", "--lines", "400", "--seed", "7"])

    lines1 = rows(tmp_path / "claim_lines" / "claim_lines_load1.csv")
    truth1 = rows(tmp_path / "ground_truth" / "ground_truth_load1.csv")
    lines2 = rows(tmp_path / "claim_lines" / "claim_lines_load2.csv")

    ids = [r["line_id"] for r in lines1] + [r["line_id"] for r in lines2]
    assert len(ids) == len(set(ids)), "line_id must be unique across loads"
    assert {t["line_id"] for t in truth1} <= {r["line_id"] for r in lines1}
    assert {t["anomaly_type"] for t in truth1} == set(gen.RATES)
    assert len(rows(tmp_path / "members" / "members_load2.csv")) >= 1


def test_generator_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        gen.main(["--out", str(out), "--members", "20", "--provider-count", "5", "--lines", "100", "--seed", "3"])
    assert (a / "claim_lines" / "claim_lines_load1.csv").read_text() == (b / "claim_lines" / "claim_lines_load1.csv").read_text()
