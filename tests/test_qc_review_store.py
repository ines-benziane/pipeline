"""Tests of FileQCReviewStore (adapters/file_qc_review_store.py), in a temporary folder:
a QC saved then listed comes back identical, and each block only lists its own QCs."""

from dataclasses import replace
from datetime import datetime

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


def test_saved_qc_comes_back_identical(tmp_path):
    store = FileQCReviewStore(tmp_path)
    store.save(full_qc())
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [full_qc()]


def test_draft_with_empty_fields_comes_back_identical(tmp_path):
    store = FileQCReviewStore(tmp_path)
    store.save(empty_draft())
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [empty_draft()]


def test_file_is_written_in_the_block_folder(tmp_path):
    FileQCReviewStore(tmp_path).save(full_qc())
    assert (tmp_path / "EX" / "thighs_dixon3pt" / "EX-20261125-1000-abcd.json").is_file()


def test_block_never_checked_lists_nothing(tmp_path):
    assert FileQCReviewStore(tmp_path).list_for_block("EX", "legs", "t2map_3exp") == []


def test_saving_the_same_qc_again_replaces_it(tmp_path):
    store = FileQCReviewStore(tmp_path)
    store.save(empty_draft())
    finished = replace(empty_draft(), map=MapCheck(MapDecision.COMPLETE, None, ""))
    store.save(finished)
    assert store.list_for_block("EX", "thighs", "dixon3pt") == [finished]


def test_each_block_lists_only_its_own_qcs(tmp_path):
    store = FileQCReviewStore(tmp_path)
    store.save(full_qc())
    store.save(empty_draft())
    t2 = replace(full_qc(), qc_id="EX-20261125-1000-t2t2", method="t2map_3exp", biomarker="T2")
    other_exam = replace(full_qc(), qc_id="EY-20261125-1000-abcd", exam_id="EY")
    store.save(t2)
    store.save(other_exam)

    listed = store.list_for_block("EX", "thighs", "dixon3pt")

    assert sorted(qc.qc_id for qc in listed) == ["EX-20261125-1000-abcd", "EX-20261125-1100-draf"]
    assert store.list_for_block("EX", "thighs", "t2map_3exp") == [t2]
