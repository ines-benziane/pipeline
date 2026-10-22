"""results_writer: mutools results table -> Exam -> JSON read by the report.
Ported from medical_report/tests/test_data_writer.py (the code moved here)."""

import io
import json

import pandas as pd
import pytest

from results_writer.json_writer import JsonWriter
from results_writer.writer import _parse_label, parse_table

TABLE_CSV = """HOW,INDEX,LABEL,X,Y,Z,NPIX,T2,T2STD,T2CINT,FF,OUTLINE
VOLUME,NA,VL_R,-0.22,8.53,414.34,7540.0,46.50,13.04,9.13,0.37,
VOLUME,NA,VL_L,-0.22,8.53,414.34,6354.0,45.90,10.58,9.16,0.37,
SLICE,Z10,VL_R,-0.22,8.53,594.34,,44.00,16.33,,,
SLICE,Z0,VL_R,-0.22,8.53,294.34,,50.89,21.05,,,"[[51.0, 60.5], [50.5, 61.0]]"
SLICE,Z0,VL_L,-0.22,8.53,294.34,,,,,,
SLICE,Z2,VL_R,-0.22,8.53,324.34,,42.48,16.33,,,"[[54.0, 66.5]]"
"""

METADATA = {"exam_id": "PAT001", "exam_date": "20250101", "segment": "thighs",
            "method": "t2map_3exp", "version": "1.0", "acquisition": "1.0",
            "segmentation": "museg-thighs:model3", "biomarker": "T2"}


@pytest.fixture
def exam():
    return parse_table(pd.read_csv(io.StringIO(TABLE_CSV)), METADATA)


def _muscle(exam, name, side):
    return next(m for m in exam.muscles if (m.name, m.side) == (name, side))


@pytest.mark.parametrize("label, expected", [("VL_R", ("VL", "R")), ("BF_SH_L", ("BF_SH", "L"))])
def test_parse_label(label, expected):
    assert _parse_label(label) == expected


@pytest.mark.parametrize("label", ["VL", "VL_X"])
def test_parse_label_rejects_missing_or_wrong_side(label):
    with pytest.raises(ValueError):
        _parse_label(label)


def test_one_muscle_per_name_and_side(exam):
    assert {(m.name, m.side) for m in exam.muscles} == {("VL", "R"), ("VL", "L")}


def test_volume_values_kept(exam):
    """RES-004 (code side): the value computed by mutools is the value written for the report."""
    stats = _muscle(exam, "VL", "R").volume.stats
    assert (stats["T2"], stats["NPIX"], stats["FF"]) == (46.50, 7540.0, 0.37)


def test_slices_sorted_numerically(exam):
    assert [s.index for s in _muscle(exam, "VL", "R").slices] == ["Z0", "Z2", "Z10"]


def test_slice_values_and_outline(exam):
    z0 = _muscle(exam, "VL", "R").slices[0]
    assert z0.stats["T2"] == 50.89
    assert z0.outline == [[51.0, 60.5], [50.5, 61.0]]


def test_empty_slice_has_no_stats_nor_outline(exam):
    z0 = _muscle(exam, "VL", "L").slices[0]
    assert "T2" not in z0.stats
    assert z0.outline is None


def test_metadata_and_qc_carried(exam):
    qc_exam = parse_table(pd.read_csv(io.StringIO(TABLE_CSV)),
                          {**METADATA, "qc_decision": "yes", "qc_comment": "ok"})
    assert exam.metadata.exam_id == "PAT001"
    assert (qc_exam.metadata.qc_decision, qc_exam.metadata.qc_comment) == ("yes", "ok")


def test_json_named_after_metadata_when_given_a_folder(exam, tmp_path):
    path = JsonWriter().write(exam, tmp_path)
    assert path.name == "PAT001_20250101_thighs_t2map_3exp_1.0_1.0.json"


def test_json_written_to_given_file_and_parents_created(exam, tmp_path):
    target = tmp_path / "deep" / "nested" / "out.json"
    assert JsonWriter().write(exam, target) == target
    assert target.exists()


def test_json_has_no_null_values(exam, tmp_path):
    path = JsonWriter().write(exam, tmp_path)
    assert "null" not in path.read_text(encoding="utf-8")


def test_json_round_trip_keeps_values(exam, tmp_path):
    data = json.loads(JsonWriter().write(exam, tmp_path).read_text(encoding="utf-8"))
    vl_r = next(m for m in data["muscles"] if (m["name"], m["side"]) == ("VL", "R"))
    assert vl_r["volume"]["stats"]["T2"] == 46.50
