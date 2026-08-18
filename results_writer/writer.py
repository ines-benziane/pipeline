"""
Results table Parser — reads a results table from "getresults" and builds domain objects.
"""

from typing import Optional

NON_STAT_COLUMNS = {"HOW", "INDEX", "LABEL", "X", "Y", "Z", "OUTLINE"}

from medical_report.models.domain import (
    Exam,
    ExamMetadata,
    MuscleData,
    SliceData,
    VolumeData,
)

def _parse_label(label: str) -> tuple[str, str]:
    """Split a label like 'VL_R' or 'BF_SH_L' into (muscle_name, side)."""
    parts = label.rsplit("_", 1)
    if len(parts) != 2 or parts[1] not in ("L", "R"):
        raise ValueError(f"Cannot parse label '{label}': expected format 'NAME_L' or 'NAME_R'")
    return parts[0], parts[1]


def _extract_stats(row: dict) -> dict[str, str]:
    """Extract all stat columns dynamically from a row."""
    stats = {}
    for col, value in row.items():
        value = str(value).strip()
        if col in NON_STAT_COLUMNS:
            continue
        if value != "":
            stats[col] = value
    return stats


def _build_volume_result(row: dict) -> Optional[VolumeData]:
    """Build VolumeData from a VOLUME row. Returns None if no stats found."""
    stats = _extract_stats(row)
    if not stats:
        return None
    return VolumeData(stats=stats)


def _build_slice_result(row: dict) -> SliceData:
    """Build SliceData from a SLICE row."""
    return SliceData(
        index=row["INDEX"],
        x=row["X"],
        y=row["Y"],
        z=row["Z"],
        stats=_extract_stats(row),
        outline= row.get("OUTLINE", ""),
    )

def get_slice_number(s):
    return int(''.join(filter(str.isdigit, s.index)) or '0')

def parse_table(table, metadata) -> Exam:
    """Parse a results table and return a muscle-centric Exam."""
    muscles_map: dict[tuple[str, str], MuscleData] = {}
    for row in table.to_dict('records'):
        how = row["HOW"].strip()
        label = row["LABEL"].strip()
        muscle_name, side = _parse_label(label)

        key = (muscle_name, side)
        if key not in muscles_map:
            muscles_map[key] = MuscleData(name=muscle_name, side=side)

        muscle = muscles_map[key]

        if how == "VOLUME":
            muscle.volume = _build_volume_result(row)

        elif how == "SLICE":
            slice_result = _build_slice_result(row)
            muscle.slices.append(slice_result)

    for muscle in muscles_map.values():
        muscle.slices.sort(key=get_slice_number)
    return Exam(
        muscles=list(muscles_map.values()),
        metadata=ExamMetadata(
            exam_id=metadata["exam_id"],
            exam_date=metadata["exam_date"],
            segment=metadata["segment"],
            method=metadata["method"],
            version=metadata["version"],
            acquisition=metadata["acquisition"],
            segmentation="seg",
            biomarker=metadata["biomarker"],
            patient_name=metadata.get("patient_name"),
            birth_date=metadata.get("birth_date"),
            referring_doctor=metadata.get("referring_doctor"),
        )
    )
