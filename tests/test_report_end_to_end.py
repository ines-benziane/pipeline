"""End-to-end: result JSON files -> medical report (HTML rendered into the PDF).

Input: tests/fixtures/report, built from a real run (CL2PA260910, legs and thighs, FF and T2),
anonymised (exam id E2E001, dates shifted) and lightened (1 Dixon slice out of 8). A synthetic
antecedent one year earlier (FF -8 points, T2 -3 ms) exercises the evolution display.
Note: the legs Dixon of this exam has a known right-side water/fat swap (FF ~96 %); the test checks
that the report shows exactly what the JSON contains, not that the value is clinically right (RES-001).

The section config is the one the GUI builds (gui/sections.py, config_entry).
Values are checked in the HTML that weasyprint converts into the PDF (Medical_report.html).
"""

import json
import re
from pathlib import Path

import pytest

from adapters.medical_report_generator import MedicalReportGenerator
from medical_report.comment_generator import select_comment

FIXTURES = Path(__file__).parent / "fixtures" / "report"
EXAM_ID, EXAM_DATE = "E2E001", "2020-01-01"
SECTIONS = [("FF", "legs", "dixon3pt"), ("T2", "legs", "t2map_3exp"),
            ("FF", "thighs", "dixon3pt"), ("T2", "thighs", "t2map_3exp")]
# muscles listed in the report value tables (templates/*/1slice/<segment>/section_design.html)
TABLE_MUSCLES = {"legs": ["TA", "ED", "PER", "DLPC", "POP", "SOL", "GAS_MED", "GAS_LAT"],
                 "thighs": ["VL", "VI", "VM", "RF", "SAR", "GRA", "SM", "ST", "BF", "AM", "AL"]}
SIDE_LABELS = {"L": "Gauche (L)", "R": "Droite (R)"}


def _gui_config():
    return {"section": [{"biomarker": bio, "section_name": "1slice", "segment": seg,
                         "method": {method: "1.0"}, "version": None, "generate": False,
                         "date": None, "acquisition": "1.0"} for bio, seg, method in SECTIONS]}


def _exam(segment, method, date=EXAM_DATE):
    return json.loads((FIXTURES / f"{EXAM_ID}_{date}_{segment}_{method}_1.0_1.0.json").read_text(encoding="utf-8"))


def _text(html):
    html = re.sub(r'src="data:[^"]+"', "", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    out = tmp_path_factory.mktemp("report")
    pdf = MedicalReportGenerator().generate([EXAM_ID], FIXTURES, out, lang="fr", config=_gui_config())
    html = (out / "Medical_report.html").read_text(encoding="utf-8")
    return pdf, html


def _side_tables(html, side):
    """Text of every per-side value table ('Gauche (L)' / 'Droite (R)' header + table)."""
    label = re.escape(SIDE_LABELS[side])
    blocks = re.findall(rf"<h5[^>]*>\s*{label}\s*</h5>\s*<table.*?</table>", html, flags=re.S)
    return [_text(b) for b in blocks]


def _displayed(biomarker, value):
    return f"{value * 100:.1f}%" if biomarker == "FF" else f"{value:.1f} ms"


def test_pdf_is_produced(report):
    pdf, _ = report
    assert pdf.read_bytes()[:5] == b"%PDF-"
    assert pdf.stat().st_size > 100_000


def test_exam_date_printed(report):
    assert f"Date d'examen : {EXAM_DATE}" in _text(report[1])


@pytest.mark.parametrize("biomarker, segment, method", SECTIONS)
@pytest.mark.parametrize("side", ["L", "R"])
def test_every_muscle_value_lands_on_the_right_muscle_and_side(report, biomarker, segment, method, side):
    """RES-004 (automated part): each value in the report tables is the JSON value of that muscle and side."""
    values = {m["name"]: m["volume"]["stats"][biomarker] for m in _exam(segment, method)["muscles"]
              if m["side"] == side and biomarker in m["volume"]["stats"]}
    expected = [f"{name}: {_displayed(biomarker, values[name])}" for name in TABLE_MUSCLES[segment]]

    tables = _side_tables(report[1], side)
    assert any(all(e in t for e in expected) for t in tables), expected


def test_t2_comment_printed(report):
    for segment in ("legs", "thighs"):
        comment = select_comment(_exam(segment, "t2map_3exp")["muscles"], lang="fr")["comment"]
        assert comment and comment in _text(report[1]), segment


def test_evolution_against_antecedent_printed(report):
    """FF legs right side: +8 points vs the antecedent -> 'aggravé' arrow with the value."""
    current = {m["name"]: m["volume"]["stats"]["FF"] for m in _exam("legs", "dixon3pt")["muscles"] if m["side"] == "R"}
    before = {m["name"]: m["volume"]["stats"]["FF"] for m in _exam("legs", "dixon3pt", "2019-01-01")["muscles"]
              if m["side"] == "R"}
    pct = round((current["TA"] - before["TA"]) * 100)

    assert f"TA: ↑ {pct}%" in _text(report[1])


@pytest.mark.xfail(strict=True, reason="Re-identification not implemented yet (planned): the header shows no "
                                       "patient name nor exam identifier. FONC-005 cannot pass until then.")
def test_exam_identifier_printed(report):
    assert EXAM_ID in _text(report[1])


@pytest.mark.xfail(strict=True, reason="AB and BF_SH (thighs) are segmented but absent from the 1slice value tables "
                                       "(template list of 11 muscles). Report layout change, to arbitrate with a physician.")
def test_every_segmented_thigh_muscle_has_a_value_in_the_tables(report):
    segmented = {m["name"] for m in _exam("thighs", "dixon3pt")["muscles"]}
    tables = " ".join(_side_tables(report[1], "L"))
    assert all(f"{name}:" in tables for name in segmented)
