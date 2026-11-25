"""Tests of the pure core of the QC review (runner/qc_review.py): grade, check_complete,
latest_validated, section_plan, copy_entries. No file, no window: QCs are built by hand."""

from dataclasses import replace
from datetime import datetime

import pytest

from runner.qc_review import (
    GRADE_RULES,
    ErrorCounts,
    Grade,
    GradeRules,
    MapCheck,
    MapDecision,
    Mention,
    MuscleError,
    QCReview,
    ReviewStatus,
    SectionFate,
    SegmentationCheck,
    SegmentationDecision,
    Side,
    check_complete,
    copy_entries,
    grade,
    latest_validated,
    section_plan,
)


def make_qc(map_decision=MapDecision.COMPLETE, map_reason=None, seg_decision=SegmentationDecision.ACCEPTED,
            seg_reason=None, counts=(0, 0, 0), **fields):
    """A QC of the thighs FF block; every entry can be overridden."""
    qc = QCReview(
        qc_id="E-20261125-1000-abcd", exam_id="E", segment="thighs", method="dixon3pt", biomarker="FF",
        job_id="job_ff", status=ReviewStatus.DRAFT, author="tech", started_at=datetime(2026, 11, 25, 10),
        rules_version=GRADE_RULES.version,
        map=MapCheck(map_decision, map_reason, ""),
        segmentation=SegmentationCheck(ErrorCounts(*counts), None, seg_decision, seg_reason, "", ()),
        validated_at=None, duration_s=None, copied_from=None,
    )
    return replace(qc, **fields)


def validated(qc_id, day):
    return make_qc(qc_id=qc_id, status=ReviewStatus.VALIDATED, validated_at=datetime(2026, 11, day))


# --- grade: edge cases of the Excel thresholds (design doc §6.1)

@pytest.mark.parametrize("counts, expected", [
    ((0, 0, 0), Grade.GOOD),
    ((0, 0, 4), Grade.GOOD),
    ((0, 0, 5), Grade.AVERAGE),
    ((0, 4, 0), Grade.AVERAGE),
    ((0, 4, 99), Grade.AVERAGE),
    ((0, 5, 0), Grade.POOR),
    ((1, 0, 0), Grade.POOR),
])
def test_grade_edge_cases(counts, expected):
    assert grade(ErrorCounts(*counts), GRADE_RULES) is expected


def test_grade_uses_the_rules_it_receives():
    strict = GradeRules(version="test", max_small_for_good=0, max_medium_for_average=0)
    assert grade(ErrorCounts(0, 0, 1), strict) is Grade.AVERAGE
    assert grade(ErrorCounts(0, 1, 0), strict) is Grade.POOR


# --- check_complete

def test_complete_qc_has_nothing_missing():
    assert check_complete(make_qc(), GRADE_RULES) == []


def test_missing_decisions_are_both_reported():
    assert len(check_complete(make_qc(map_decision=None, seg_decision=None), GRADE_RULES)) == 2


@pytest.mark.parametrize("map_decision", [MapDecision.LEFT_ONLY, MapDecision.RIGHT_ONLY, MapDecision.REJECTED])
@pytest.mark.parametrize("empty_reason", [None, ""])
def test_map_reason_required_unless_complete(map_decision, empty_reason):
    assert len(check_complete(make_qc(map_decision=map_decision, map_reason=empty_reason), GRADE_RULES)) == 1
    assert check_complete(make_qc(map_decision=map_decision, map_reason="Artefact de mouvement"), GRADE_RULES) == []


def test_rejected_segmentation_requires_a_reason():
    qc = make_qc(seg_decision=SegmentationDecision.REJECTED)
    assert len(check_complete(qc, GRADE_RULES)) == 1
    assert check_complete(replace(qc, segmentation=replace(qc.segmentation, reason="Trop d'erreurs")),
                          GRADE_RULES) == []


def test_poor_grade_cannot_be_accepted():
    assert len(check_complete(make_qc(counts=(1, 0, 0)), GRADE_RULES)) == 1
    rejected = make_qc(counts=(1, 0, 0), seg_decision=SegmentationDecision.REJECTED, seg_reason="Trop d'erreurs")
    assert check_complete(rejected, GRADE_RULES) == []


# --- latest_validated

def test_latest_validated_without_qc_is_none():
    assert latest_validated([]) is None


def test_drafts_never_count():
    assert latest_validated([make_qc()]) is None


def test_latest_validated_is_the_most_recent_one_whatever_the_order():
    qcs = [validated("new", 24), make_qc(qc_id="draft"), validated("old", 20)]
    assert latest_validated(qcs).qc_id == "new"


# --- section_plan

def test_section_without_qc_is_removed_as_not_checked():
    plan = section_plan(None)
    assert (plan.fate, plan.mention) == (SectionFate.REMOVED, Mention.NOT_CHECKED)


def test_section_shown_when_all_is_fine():
    plan = section_plan(make_qc())
    assert (plan.fate, plan.kept_side, plan.mention, plan.reason) == (SectionFate.SHOWN, None, None, None)


@pytest.mark.parametrize("map_decision, kept", [(MapDecision.LEFT_ONLY, Side.LEFT), (MapDecision.RIGHT_ONLY, Side.RIGHT)])
def test_one_side_keeps_that_side_with_the_reason(map_decision, kept):
    plan = section_plan(make_qc(map_decision=map_decision, map_reason="Artefact de mouvement"))
    assert (plan.fate, plan.kept_side, plan.mention, plan.reason) == (
        SectionFate.ONE_SIDE, kept, Mention.SIDE_REMOVED, "Artefact de mouvement")


def test_rejected_map_removes_the_section():
    plan = section_plan(make_qc(map_decision=MapDecision.REJECTED, map_reason="Inversion eau/graisse"))
    assert (plan.fate, plan.mention, plan.reason) == (SectionFate.REMOVED, Mention.MAP_UNUSABLE, "Inversion eau/graisse")


def test_rejected_segmentation_removes_the_section_even_with_one_side_map():
    plan = section_plan(make_qc(map_decision=MapDecision.LEFT_ONLY, map_reason="Artefact de mouvement",
                                seg_decision=SegmentationDecision.REJECTED, seg_reason="Trop d'erreurs"))
    assert (plan.fate, plan.mention, plan.reason) == (SectionFate.REMOVED, Mention.SEGMENTATION_TO_REDO, "Trop d'erreurs")


def test_both_rejected_shows_the_map_mention():
    plan = section_plan(make_qc(map_decision=MapDecision.REJECTED, map_reason="Inversion eau/graisse",
                                seg_decision=SegmentationDecision.REJECTED, seg_reason="Trop d'erreurs"))
    assert plan.mention is Mention.MAP_UNUSABLE


# --- copy_entries

def test_copy_entries_copies_the_entries_and_keeps_the_target_identity():
    source = make_qc(map_decision=MapDecision.LEFT_ONLY, map_reason="Artefact de mouvement", counts=(0, 2, 4),
                     status=ReviewStatus.VALIDATED, validated_at=datetime(2026, 11, 25, 11))
    source = replace(source, segmentation=replace(source.segmentation, errors=(MuscleError("VL", "VI", Side.LEFT),)))
    target = make_qc(qc_id="E-20261125-1000-t2t2", method="t2map_3exp", biomarker="T2", job_id="job_t2",
                     map_decision=None, seg_decision=None)

    copied = copy_entries(source, target)

    assert copied.map == source.map
    assert copied.segmentation == source.segmentation
    assert (copied.qc_id, copied.method, copied.biomarker, copied.job_id) == (
        target.qc_id, "t2map_3exp", "T2", "job_t2")
    assert copied.copied_from == source.qc_id
    assert copied.status is ReviewStatus.DRAFT
    assert copied.validated_at is None


def test_copy_entries_leaves_the_target_unchanged():
    target = make_qc(map_decision=None)
    copy_entries(make_qc(), target)
    assert target.map.decision is None and target.copied_from is None
