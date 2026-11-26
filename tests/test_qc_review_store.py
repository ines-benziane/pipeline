"""Tests of FileQCReviewStore (adapters/file_qc_review_store.py): the QCs live in the "qc_reviews" list of the
results JSON they check, in the run folder (workdirs/<job_id>/) and in the copy read by the report (workdirs/results/).
Results are written in a temporary folder the way job_runner leaves them."""

import json
from dataclasses import replace
from datetime import datetime

import pytest

from adapters.file_qc_review_store import FileQCReviewStore
from runner.qc_review import (
    ErrorCounts,
    Grade,
    MapCheck,
    MapDecision,
    MuscleError,
    QCReview,
    ReviewStatus,
    SegmentationCheck,
    SegmentationDecision,
    Side,
)
from runner.qc_review_store import QCReviewStoreError


def full_qc():
    """A validated QC where every field is filled, accents and muscle errors included."""
    return QCReview(
        qc_id="EX-20261125-1000-abcd", exam_id="EX", segment="thighs", method="dixon3pt", biomarker="FF",
        job_id="job_ff", status=ReviewStatus.VALIDATED, author="tech", started_at=datetime(2026, 11, 25, 10),
        rules_version="v1",
        map=MapCheck(MapDecision.LEFT_ONLY, "Artefact de mouvement", "jambe droite floue"),
        segmentation=SegmentationCheck(ErrorCounts(0, 2, 4), Grade.AVERAGE, SegmentationDecision.ACCEPTED, None, "",
                                       (MuscleError("VL", "VI", Side.LEFT), MuscleError("SAR", "background", Side.BOTH))),
        validated_at=datetime(2026, 11, 25, 10, 5), duration_s=300, copied_from="EX-20261125-1000-t2t2",
    )


def empty_draft():
    """A draft just opened: no decision, no grade, no date of validation."""
    return replace(full_qc(), qc_id="EX-20261125-1100-draf", status=ReviewStatus.DRAFT,
                   map=MapCheck(None, None, ""),
                   segmentation=SegmentationCheck(ErrorCounts(0, 0, 0), None, None, None, "", ()),
                   validated_at=None, duration_s=None, copied_from=None)


def _name(exam_id="EX", segment="thighs", method="dixon3pt"):
    return f"{exam_id}_2026-11-25_{segment}_{method}_1.0_1.0.json"


def _write_run(tmp_path, job_id, current=True, **block):
    """Results of one run, as job_runner leaves them: in the run folder and, if `current`, copied for the report."""
    name = _name(**block)
    text = json.dumps({"muscles": [{"name": "VL"}], "metadata": {"exam_id": "EX", "job_id": job_id}})
    (tmp_path / "workdirs" / job_id).mkdir(parents=True, exist_ok=True)
    (tmp_path / "workdirs" / job_id / name).write_text(text, encoding="utf-8")
    if current:
        (tmp_path / "results").mkdir(exist_ok=True)
        (tmp_path / "results" / name).write_text(text, encoding="utf-8")


@pytest.fixture
def store(tmp_path):
    _write_run(tmp_path, "job_ff")
    return FileQCReviewStore(result_dir=tmp_path / "results", working_dir=tmp_path / "workdirs")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_saved_qc_comes_back_identical(store):
    store.save(full_qc())
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [full_qc()]


def test_draft_with_empty_fields_comes_back_identical(store):
    store.save(empty_draft())
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [empty_draft()]


def test_qc_is_written_in_both_copies_of_the_results_which_are_kept(store, tmp_path):
    store.save(full_qc())
    original = _read(tmp_path / "workdirs" / "job_ff" / _name())
    current = _read(tmp_path / "results" / _name())

    assert original == current
    assert [qc["qc_id"] for qc in original["qc_reviews"]] == ["EX-20261125-1000-abcd"]
    assert original["muscles"] == [{"name": "VL"}] and original["metadata"]["job_id"] == "job_ff"


def test_block_never_checked_lists_nothing(store):
    assert store.list_for_block("EX", "thighs", "dixon3pt") == []
    assert store.list_for_block("EX", "legs", "t2map_3exp") == []   # no results at all


def test_qc_done_in_two_sittings_replaces_its_draft(store):
    store.save(empty_draft())
    finished = replace(empty_draft(), map=MapCheck(MapDecision.COMPLETE, None, ""))
    store.save(finished)
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [finished]


def test_each_block_lists_only_its_own_qcs(store, tmp_path):
    _write_run(tmp_path, "job_t2", method="t2map_3exp")
    _write_run(tmp_path, "job_ey", exam_id="EY")
    t2 = replace(full_qc(), qc_id="EX-20261125-1000-t2t2", method="t2map_3exp", biomarker="T2", job_id="job_t2")
    other_exam = replace(full_qc(), qc_id="EY-20261125-1000-abcd", exam_id="EY", job_id="job_ey")
    for qc in (full_qc(), empty_draft(), t2, other_exam):
        store.save(qc)

    listed = store.list_for_block("EX", "thighs", "dixon3pt")

    assert sorted(qc.qc_id for qc in listed) == ["EX-20261125-1000-abcd", "EX-20261125-1100-draf"]
    assert store.list_for_block("EX", "thighs", "t2map_3exp") == [t2]


def test_qc_of_an_earlier_run_stays_with_that_run_only(store, tmp_path):
    """The block was run again: the report's copy is the new run's, the QC of the earlier run doesn't go in it."""
    _write_run(tmp_path, "job_ff_rerun")   # same results name: replaces the report's copy

    store.save(full_qc())   # QC of job_ff

    assert store.list_for_block("EX", "thighs", "dixon3pt") == []
    assert len(_read(tmp_path / "workdirs" / "job_ff" / _name())["qc_reviews"]) == 1


def test_qc_of_a_run_without_results_is_an_error(store):
    with pytest.raises(QCReviewStoreError):
        store.save(replace(full_qc(), job_id="job_unknown"))
