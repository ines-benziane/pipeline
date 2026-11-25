"""save: from QC to dict."""
import json
from pathlib import Path
from datetime import datetime
from enum import Enum
from dataclasses import asdict
from runner.qc_review import (QCReview, ReviewStatus, MapCheck, MapDecision, SegmentationCheck, ErrorCounts,
                              MuscleError, Side, Grade, SegmentationDecision)
from runner.qc_review_store import QCReviewStore, QCReviewStoreError

QC_REVIEWS_DIR = Path("workdirs") / "qc_reviews"

class FileQCReviewStore(QCReviewStore):
    def __init__(self, root: Path = QC_REVIEWS_DIR):
        self.root = Path(root)

    def save(self, qc: QCReview) ->None:
        """qc -> dict -> json -> saved in Path"""
        data = asdict(qc)
        text = json.dumps(data, default=_to_json_value, indent=2, ensure_ascii=False)
        folder = self.root / qc.exam_id / f"{qc.segment}_{qc.method}"
        path = folder / f"{qc.qc_id}.json"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            raise QCReviewStoreError(f"cannot write QC review {path}: {e}") from e

    def list_for_block(self, exam_id: str, segment: str, method: str) -> list[QCReview]:
        folder = self.root / exam_id / f"{segment}_{method}"
        paths = sorted(folder.glob("*.json"))
        qcs = []
        for path in paths:
            text = path.read_text(encoding="utf-8") #file -> text
            data = json.loads(text)                 # text -> dict
            qc = _qc_from_dict(data)                # dict -> QCReview 
            qcs.append(qc)
        return qcs

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