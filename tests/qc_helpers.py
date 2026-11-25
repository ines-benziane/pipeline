"""Helpers for the tests that generate a report: the report only shows sections with a validated QC,
so these tests first save validated QCs in a temporary FileQCReviewStore."""

from datetime import datetime

from adapters.file_qc_review_store import FileQCReviewStore
from runner.qc_review import (
    ErrorCounts,
    Grade,
    MapCheck,
    MapDecision,
    QCReview,
    ReviewStatus,
    SegmentationCheck,
    SegmentationDecision,
)


def validated_qc(exam_id, segment, method, map_decision=MapDecision.COMPLETE, map_reason=None,
                 seg_decision=SegmentationDecision.ACCEPTED, seg_reason=None):
    """A validated QC of one block; by default everything passes (the section appears)."""
    return QCReview(
        qc_id=f"{exam_id}-{segment}-{method}", exam_id=exam_id, segment=segment, method=method,
        biomarker="FF" if method == "dixon3pt" else "T2", job_id=f"{exam_id}-job", status=ReviewStatus.VALIDATED,
        author="test", started_at=datetime(2026, 11, 26, 9), rules_version="v1",
        map=MapCheck(map_decision, map_reason, ""),
        segmentation=SegmentationCheck(ErrorCounts(0, 0, 0), Grade.GOOD, seg_decision, seg_reason, "", ()),
        validated_at=datetime(2026, 11, 26, 9, 5), duration_s=300, copied_from=None,
    )


def store_with_validated(root, exam_id, blocks):
    """A FileQCReviewStore in `root` where each (segment, method) block of the exam has a passing validated QC."""
    store = FileQCReviewStore(root)
    for segment, method in blocks:
        store.save(validated_qc(exam_id, segment, method))
    return store
