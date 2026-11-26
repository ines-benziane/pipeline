"""Code of the qc review module.
Declares dataclasses needed for the qc review, and main classes."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

class MapDecision(Enum):
    COMPLETE = "complete"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"
    REJECTED = "rejected"

class SegmentationDecision(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class Grade(Enum):
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"

class Side(Enum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"

class ReviewStatus(Enum):
    DRAFT = "draft"
    VALIDATED = "validated"

@dataclass(frozen=True)
class ErrorCounts:
    large: int
    medium: int
    small: int

@dataclass(frozen=True)
class MuscleError:
    muscle: str
    other: str
    side: Side

@dataclass(frozen=True)
class MapCheck:
    decision: MapDecision | None
    reason: str | None
    comment: str

@dataclass(frozen=True)
class SegmentationCheck:
    counts: ErrorCounts
    grade: Grade | None
    decision: SegmentationDecision | None
    reason: str | None
    comment: str
    errors: tuple[MuscleError, ...]

@dataclass(frozen=True)
class QCReview:
    qc_id: str
    exam_id: str
    segment: str
    method: str
    biomarker: str
    job_id: str
    status: ReviewStatus
    author: str
    started_at: datetime
    rules_version: str
    map: MapCheck
    segmentation: SegmentationCheck
    validated_at: datetime | None
    duration_s: int | None
    copied_from: str | None 


@dataclass(frozen=True)
class GradeRules:
    """Thresholds of the segmentation grade."""
    version: str
    max_small_for_good: int      # good: no large, no medium, at most this many small
    max_medium_for_average: int  # average: no large, at most this many medium


GRADE_RULES = GradeRules(version="v1", max_small_for_good=4, max_medium_for_average=4)


def grade(error_counts: ErrorCounts, rules: GradeRules) -> Grade:
    """Grade of a segmentation from its error counts: any large error is poor."""
    if error_counts.large > 0:
        return Grade.POOR
    if error_counts.medium == 0 and error_counts.small <= rules.max_small_for_good:
        return Grade.GOOD
    if error_counts.medium <= rules.max_medium_for_average:
        return Grade.AVERAGE
    return Grade.POOR

def check_complete(qc: QCReview, rules: GradeRules) -> list[str]:
    """What is missing before the QC can be validated. Empty list: the QC is complete."""
    missing = []
    map_check = qc.map
    seg_check = qc.segmentation

    if map_check.decision is None:
        missing.append("Mapping : no decision.")
    elif map_check.decision is not MapDecision.COMPLETE and not map_check.reason:
        missing.append("Mapping : reason is mandatory for this decision.")

    if seg_check.decision is None:
        missing.append("Segmentation : no decision.")
    elif seg_check.decision is SegmentationDecision.REJECTED and not seg_check.reason:
        missing.append("Segmentation : reason is mandatory for this decision.")

    if grade(seg_check.counts, rules) is Grade.POOR and seg_check.decision is SegmentationDecision.ACCEPTED:
        missing.append("Segmentation : 'poor' grade can't be accepted.")

    return missing

def latest_validated(qcs: list[QCReview]) -> QCReview | None:
    """The QC that counts for the block: the most recently validated one. None if no QC is validated."""
    validated = [qc for qc in qcs if qc.status is ReviewStatus.VALIDATED]
    if not validated:
        return None
    return max(validated, key=lambda qc: qc.validated_at)

class SectionFate(Enum):
    SHOWN = "shown"
    ONE_SIDE = "one_side"
    REMOVED = "removed"


class Mention(Enum):
    """Kind of note shown in the report; the text itself is in medical_report's fr.json / en.json."""
    NOT_CHECKED = "not_checked"
    MAP_UNUSABLE = "map_unusable"
    SEGMENTATION_TO_REDO = "segmentation_to_redo"
    SIDE_REMOVED = "side_removed"


@dataclass(frozen=True)
class SectionPlan:
    """What the report does with the section of one block."""
    fate: SectionFate
    kept_side: Side | None   # LEFT or RIGHT when fate is ONE_SIDE, None otherwise
    mention: Mention | None
    reason: str | None


def section_plan(qc: QCReview | None) -> SectionPlan:
    """Turn the QC that counts for a block into what its report section becomes."""
    if qc is None:
        return SectionPlan(SectionFate.REMOVED, None, Mention.NOT_CHECKED, None)

    map_check = qc.map
    seg_check = qc.segmentation

    if map_check.decision is MapDecision.REJECTED:
        return SectionPlan(SectionFate.REMOVED, None, Mention.MAP_UNUSABLE, map_check.reason)
    if seg_check.decision is SegmentationDecision.REJECTED:
        return SectionPlan(SectionFate.REMOVED, None, Mention.SEGMENTATION_TO_REDO, seg_check.reason)
    if map_check.decision is MapDecision.LEFT_ONLY:
        return SectionPlan(SectionFate.ONE_SIDE, Side.LEFT, Mention.SIDE_REMOVED, map_check.reason)
    if map_check.decision is MapDecision.RIGHT_ONLY:
        return SectionPlan(SectionFate.ONE_SIDE, Side.RIGHT, Mention.SIDE_REMOVED, map_check.reason)
    return SectionPlan(SectionFate.SHOWN, None, None, None)


def copy_entries(source: QCReview, target: QCReview) -> QCReview:
    """The target QC filled with the entries of the source QC (map and segmentation parts), marked as copied.
    What identifies the target (block, run, id, author, start time) is kept; it stays a draft to be checked."""
    return replace(
        target,
        map=source.map,
        segmentation=source.segmentation,
        status=ReviewStatus.DRAFT,
        copied_from=source.qc_id,
    )
