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
from adapters.patient_identity import PatientIdentityError
from medical_report.comment_generator import select_comment
from medical_report.section_generator.src.domain.report_muscles import abbr, muscle_ids

FIXTURES = Path(__file__).parent / "fixtures" / "report"
EXAM_ID, EXAM_DATE = "E2E001", "2020-01-01"
SECTIONS = [("FF", "legs", "dixon3pt"), ("T2", "legs", "t2map_3exp"),
            ("FF", "thighs", "dixon3pt"), ("T2", "thighs", "t2map_3exp")]
# muscles of the value tables = every muscle of the report list (src/domain/report_muscles.py)
TABLE_MUSCLES = {segment: muscle_ids(segment) for segment in ("legs", "thighs")}
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


IDENTITY = {"patient_name": "TEST PATIENT", "birth_date": "01/01/1970"}   # fake PACS answer


def _fake_pacs(exam_id, exam_date):
    assert (exam_id, exam_date) == (EXAM_ID, EXAM_DATE)
    return IDENTITY


def _pacs_unreachable(exam_id, exam_date):
    raise PatientIdentityError(f"No study found on the PACS for {exam_id} on {exam_date}")


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    out = tmp_path_factory.mktemp("report")
    pdf = MedicalReportGenerator(identity_provider=_fake_pacs).generate(
        [EXAM_ID], FIXTURES, out, lang="fr", config=_gui_config())
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
    year, month, day = EXAM_DATE.split("-")
    assert f"Date d'examen : {day}/{month}/{year}" in _text(report[1])


@pytest.mark.parametrize("biomarker, segment, method", SECTIONS)
@pytest.mark.parametrize("side", ["L", "R"])
def test_every_muscle_value_lands_on_the_right_muscle_and_side(report, biomarker, segment, method, side):
    """RES-004 (automated part): each value in the report tables is the JSON value of that muscle and side."""
    values = {m["name"]: m["volume"]["stats"][biomarker] for m in _exam(segment, method)["muscles"]
              if m["side"] == side and biomarker in m["volume"]["stats"]}
    expected = [f"{abbr(name)}: {_displayed(biomarker, values[name])}" for name in TABLE_MUSCLES[segment]
                if name in values]

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

    text = _text(report[1])
    assert f"TA: ↑ {pct} pt" in text                                      # FF evolution in percentage points
    assert "Évolution depuis l'examen du 01/01/2019 (1 an)" in text       # date of the antecedent and time elapsed


def test_patient_identity_printed_in_the_header(report):
    """FONC-005: name and birth date from the PACS in the report header (they are in no JSON)."""
    text = _text(report[1])

    assert f"Patient(e) : {IDENTITY['patient_name']}" in text
    assert f"Date de naissance : {IDENTITY['birth_date']}" in text


def test_report_produced_with_blank_identity_when_pacs_fails(tmp_path, capsys):
    """PACS unreachable or exam not found: the report is still produced, the identity fields are left blank
    to be filled in by hand, and the user is warned."""
    pdf = MedicalReportGenerator(identity_provider=_pacs_unreachable).generate(
        [EXAM_ID], FIXTURES, tmp_path, lang="fr", config=_gui_config())
    text = _text((tmp_path / "Medical_report.html").read_text(encoding="utf-8"))

    assert pdf.exists()
    assert "Patient(e) : Date de naissance : Adressé" in text
    assert "Fill in the name and birth date by hand" in capsys.readouterr().out


@pytest.mark.xfail(strict=True, reason="The exam identifier is not printed in the header (only name, birth date "
                                       "and exam date). To decide with the physicians.")
def test_exam_identifier_printed(report):
    assert EXAM_ID in _text(report[1])


def test_every_segmented_thigh_muscle_has_a_value_in_the_tables(report):
    """No segmented muscle is lost: all of them in the tables, also those not drawn on the diagram
    (AB, BF_SH, AL), under their abbreviation ("*" when absent from the slice shown)."""
    tables = " ".join(_side_tables(report[1], "L"))
    for m in (m for m in _exam("thighs", "dixon3pt")["muscles"] if m["side"] == "L"):
        assert f"{abbr(m['name'])}: {_displayed('FF', m['volume']['stats']['FF'])}" in tables, m["name"]


def test_height_and_weight_printed_in_the_header_when_known(tmp_path):
    """Lot 5: height and weight from the DICOM headers (result JSON metadata) under the birth date."""
    data = tmp_path / "data"
    data.mkdir()
    for f in FIXTURES.glob(f"{EXAM_ID}_{EXAM_DATE}_*.json"):
        exam = json.loads(f.read_text(encoding="utf-8"))
        exam["metadata"].update(patient_size=1.68, patient_weight=61.0)
        (data / f.name).write_text(json.dumps(exam), encoding="utf-8")

    MedicalReportGenerator(identity_provider=_fake_pacs).generate(
        [EXAM_ID], data, tmp_path / "out", lang="fr", config=_gui_config())
    text = _text((tmp_path / "out" / "Medical_report.html").read_text(encoding="utf-8"))

    assert "Taille : 1.68 m · Poids : 61 kg" in text


def test_no_height_or_weight_line_when_unknown(report):
    """The fixtures have no height nor weight: nothing printed (no empty "Taille :")."""
    assert "Taille :" not in _text(report[1]) and "Poids :" not in _text(report[1])
