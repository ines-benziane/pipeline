"""Helpers for the tests that generate a report: the report only shows sections with a validated QC,
so these tests first give the report a store holding validated QCs (in memory: the report only talks to the port)."""

from datetime import datetime

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
from runner.qc_review_store import QCReviewStore


class MemoryQCReviewStore(QCReviewStore):
    """QCReviewStore kept in a dict: same behaviour as the file store, no files."""

    def __init__(self):
        self.qcs = {}

    def save(self, qc):
        self.qcs[qc.qc_id] = qc

    def list_for_block(self, exam_id, segment, method):
        return [qc for qc in self.qcs.values() if (qc.exam_id, qc.segment, qc.method) == (exam_id, segment, method)]


def validated_qc(exam_id, segment, method, map_decision=MapDecision.COMPLETE, map_reason=None,
                 seg_decision=SegmentationDecision.ACCEPTED, seg_reason=None, job_id=None):
    """A validated QC of one block; by default everything passes (the section appears).
    By default it checks the run "<exam_id>-job", the job_id the test results carry."""
    return QCReview(
        qc_id=f"{exam_id}-{segment}-{method}", exam_id=exam_id, segment=segment, method=method,
        biomarker="FF" if method == "dixon3pt" else "T2", job_id=job_id or f"{exam_id}-job",
        status=ReviewStatus.VALIDATED,
        author="test", started_at=datetime(2026, 11, 26, 9), rules_version="v1",
        map=MapCheck(map_decision, map_reason, ""),
        segmentation=SegmentationCheck(ErrorCounts(0, 0, 0), Grade.GOOD, seg_decision, seg_reason, "", ()),
        validated_at=datetime(2026, 11, 26, 9, 5), duration_s=300, copied_from=None,
    )


def store_with_validated(exam_id, blocks):
    """A store where each (segment, method) block of the exam has a passing validated QC."""
    store = MemoryQCReviewStore()
    for segment, method in blocks:
        store.save(validated_qc(exam_id, segment, method))
    return store
