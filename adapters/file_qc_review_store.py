"""QC reviews kept inside the results JSON they check, in a "qc_reviews" list:
the original in the run folder (workdirs/<job_id>/) and the copy read by the report (workdirs/results/)."""
import json
from pathlib import Path
from datetime import datetime
from enum import Enum
from dataclasses import asdict
from runner.job_runner import  RESULT_DIR, WORKDIR_ROOT
from runner.qc_review import (QCReview, ReviewStatus, MapCheck, MapDecision, SegmentationCheck, ErrorCounts,
                              MuscleError, Side, Grade, SegmentationDecision)
from runner.qc_review_store import QCReviewStore, QCReviewStoreError


class FileQCReviewStore(QCReviewStore):
    def __init__(self, result_dir: Path = RESULT_DIR, working_dir : Path = WORKDIR_ROOT):
        self.result_dir = Path(result_dir)
        self.working_dir = Path(working_dir)

    def save(self, qc: QCReview) -> None:
        """Write the QC in the results it checks: the original in the run folder, and the copy read by the
        report if that copy still comes from the same run (after a rerun it doesn't: the QC isn't about it)."""
        pattern = f"{qc.exam_id}_*_{qc.segment}_{qc.method}_*.json"
        run_paths = sorted((self.working_dir / qc.job_id).glob(pattern))
        if not run_paths:
            raise QCReviewStoreError(f"no results of run {qc.job_id} to attach the QC {qc.qc_id} to")
        original = run_paths[0]
        current = self.result_dir / original.name
        try:
            _write_qc(original, qc)
            if current.exists() and _job_id_of(current) == qc.job_id:
                _write_qc(current, qc)
        except OSError as e:
            raise QCReviewStoreError(f"cannot write QC review {qc.qc_id}: {e}") from e

    def list_for_block(self, exam_id: str, segment: str, method: str) -> list[QCReview]:
        pattern = f"{exam_id}_*_{segment}_{method}_*.json"
        paths = sorted(self.result_dir.glob(pattern))
        qcs = []
        for path in paths:
            text = path.read_text(encoding="utf-8") #file -> text
            data = json.loads(text)                 # text -> dict
            for qc_data in data.get("qc_reviews", []):   # no key: never checked
                qcs.append(_qc_from_dict(qc_data))       # dict -> QCReview
        return qcs

def _job_id_of(path: Path) -> str | None:
    """The run that produced these results (None in results written before the job_id was recorded)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["metadata"].get("job_id")


def _write_qc(path: Path, qc: QCReview) -> None:
    """Add the QC to the "qc_reviews" list of the results JSON `path`.
    A QC done in two sittings (saved as a draft, finished later) keeps its qc_id: its draft is replaced,
    so the list holds each QC once. A QC with a new qc_id is just added."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    others = [r for r in data.get("qc_reviews", []) if r["qc_id"] != qc.qc_id]     # drop this QC's draft, if any
    others.append(asdict(qc))
    data["qc_reviews"] = others
    text = json.dumps(data, default=_to_json_value, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")                                        

def _to_json_value(value):
    """json.dumps cannot read Enum or datetime, this fun does it"""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot write {type(value).__name__} to JSON")

def _map_check_from_dict(data: dict) -> MapCheck:
    decision = data["decision"]
    return MapCheck(
        decision=MapDecision(decision) if decision else None,
        reason=data["reason"],
        comment=data["comment"],
    )


def _segmentation_check_from_dict(data: dict) -> SegmentationCheck:
    grade = data["grade"]
    decision = data["decision"]
    errors = []
    for error in data["errors"]:                      # list of dict -> list of MuscleError
        errors.append(MuscleError(error["muscle"], error["other"], Side(error["side"])))
    return SegmentationCheck(
        counts=ErrorCounts(**data["counts"]),         # {"large": 0, ...} -> ErrorCounts
        grade=Grade(grade) if grade else None,
        decision=SegmentationDecision(decision) if decision else None,
        reason=data["reason"],
        comment=data["comment"],
        errors=tuple(errors),                         # JSON gives a list, the QC wants a tuple
    )



def _qc_from_dict(data: dict) -> QCReview:
    validated_at = data["validated_at"]
    return QCReview(
        qc_id=data["qc_id"],
        exam_id=data["exam_id"],
        segment=data["segment"],
        method=data["method"],
        biomarker=data["biomarker"],
        job_id=data["job_id"],
        status=ReviewStatus(data["status"]),                    # texte → Enum
        author=data["author"],
        started_at=datetime.fromisoformat(data["started_at"]),  # texte → date
        rules_version=data["rules_version"],
        map=_map_check_from_dict(data["map"]),                        
        segmentation=_segmentation_check_from_dict(data["segmentation"]), 
        validated_at=datetime.fromisoformat(validated_at) if validated_at else None,
        duration_s=data["duration_s"],
        copied_from=data["copied_from"],
    )