"""RES-004 (values displayed in the report): every value of the report tables is the muReport value of that muscle and side.

For each exam of a RES-003 run (resultats_tests/RES003_<date>/<exam>/): read the JSON results used for the report
(json/) and the HTML rendered into the PDF (Medical_report.html), then check, per biomarker, segment, side and muscle
of the report tables, that "<MUSCLE>: <value>" is printed on that side (FF in % with 1 decimal, T2 in ms with 1 decimal,
as in the templates). Same rule as tests/test_report_end_to_end.py, on the whole lot.

Usage: python scripts/check_res004.py resultats_tests/RES003_<date>
Output: <run>/RES004_values.csv (one row per checked value) + a summary per exam.
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# muscles listed in the report value tables (templates/*/1slice/<segment>/section_design.html)
TABLE_MUSCLES = {"legs": ["TA", "ED", "PER", "DLPC", "POP", "SOL", "GAS_MED", "GAS_LAT"],
                 "thighs": ["VL", "VI", "VM", "RF", "SAR", "GRA", "SM", "ST", "BF", "AM", "AL"]}
SIDE_LABELS = {"L": "Gauche (L)", "R": "Droite (R)"}


def text(html):
    html = re.sub(r'src="data:[^"]+"', "", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def side_tables(html, side):
    """Text of every per-side value table of the report ('Gauche (L)' / 'Droite (R)' header + table)."""
    label = re.escape(SIDE_LABELS[side])
    return [text(b) for b in re.findall(rf"<h5[^>]*>\s*{label}\s*</h5>\s*<table.*?</table>", html, flags=re.S)]


def displayed(biomarker, value):
    return f"{value * 100:.1f}%" if biomarker == "FF" else f"{value:.1f} ms"


def check_exam(exam_dir):
    """One row per value expected in the report tables of this exam."""
    html_file = exam_dir / "Medical_report.html"
    if not html_file.exists():
        return [dict(exam=exam_dir.name, biomarker="", segment="", side="", muscle="", expected="",
                     found="NON", remark="pas de Medical_report.html")]
    html = html_file.read_text(encoding="utf-8")
    tables = {side: " ".join(side_tables(html, side)) for side in SIDE_LABELS}
    rows = []
    for json_file in sorted((exam_dir / "json").glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        biomarker, segment = data["metadata"]["biomarker"], data["metadata"]["segment"]
        for side in SIDE_LABELS:
            values = {m["name"]: m["volume"]["stats"][biomarker] for m in data["muscles"]
                      if m["side"] == side and isinstance(m["volume"]["stats"].get(biomarker), (int, float))}
            for muscle in TABLE_MUSCLES[segment]:
                if muscle not in values:
                    expected, found = f"{muscle}: --", f"{muscle}: --" in tables[side]
                    remark = "pas de valeur dans le JSON"
                else:
                    expected, found = f"{muscle}: {displayed(biomarker, values[muscle])}", None
                    found = expected in tables[side]
                    remark = ""
                rows.append(dict(exam=exam_dir.name, biomarker=biomarker, segment=segment, side=side, muscle=muscle,
                                 expected=expected, found="oui" if found else "NON", remark=remark))
    date = None
    for json_file in (exam_dir / "json").glob("*.json"):
        date = json.loads(json_file.read_text(encoding="utf-8"))["metadata"]["exam_date"]
    rows.append(dict(exam=exam_dir.name, biomarker="", segment="", side="", muscle="date d'examen",
                     expected=f"Date d'examen : {date}", found="oui" if f"Date d'examen : {date}" in text(html) else "NON",
                     remark=""))
    return rows


def main():
    run_dir = Path(sys.argv[1])
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    rows = []
    for exam_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("CL")):
        rows += check_exam(exam_dir)

    out = run_dir / "RES004_values.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    bad = [r for r in rows if r["found"] != "oui"]
    exams = sorted({r["exam"] for r in rows})
    print(f"{out}: {len(rows)} values checked on {len(exams)} exams, {len(rows) - len(bad)} found, {len(bad)} NOT found")
    for r in bad:
        print(f"  NON  {r['exam']} {r['biomarker']} {r['segment']} {r['side']}: {r['expected']} {r['remark']}")


if __name__ == "__main__":
    main()
