"""External segmentation: use a Matlab ROI folder (roi.hdr / roi.img + labels_*.txt, ITK-SNAP labels)
in place of the automatic segmentation (MuSeg-AI), e.g. to compare muReport and Matlab on identical inputs."""

from pathlib import Path

import numpy as np

from mutools import io
from mutools.io import volume

from runner.errors import ExternalSegmentationError, UnknownSegmentError

LABELS_FILE_BY_SEGMENT = {"legs": "labels_leg.txt", "thighs": "labels_thigh.txt"}
NOT_MUSCLES = {"TIBIA", "FIBULA", "FEMUR"}


def read_external_segmentation(folder: Path, reference, segment: str):
    """Read and check a Matlab ROI folder; return ([roi], {index: "NAME_R"}) like the automatic segmentation.

    `reference` is an image of the run (e.g. first Dixon echo): the ROI must be on its grid.
    """
    labels_file = _check_files(folder, segment)
    roi = volume.read(folder / "roi.hdr")
    _check_same_grid(roi, reference, folder)
    labels = _muscle_labels(roi, _read_labels(labels_file), folder)
    return [roi], labels


def _check_files(folder: Path, segment: str) -> Path:
    """The folder holds the ROI and the labels file of the requested segment; return the labels file."""
    labels_name = LABELS_FILE_BY_SEGMENT.get(segment)
    if labels_name is None:
        raise UnknownSegmentError(segment, LABELS_FILE_BY_SEGMENT)
    for name in ("roi.hdr", "roi.img", labels_name):
        if not (folder / name).exists():
            raise ExternalSegmentationError(
                f"{name} not found in {folder}",
                hint=f"for {segment}, give the Matlab folder containing roi.hdr, roi.img and {labels_name}",
            )
    return folder / labels_name


def _read_labels(path: Path) -> dict:
    """ITK-SNAP labels file -> {index: description}."""
    labels = io.read_labels(path)
    return dict(zip(labels.indices, labels.descriptions))


def _check_same_grid(roi, reference, folder: Path):
    """Same number of voxels, voxel size, origin and orientation (mm, small float tolerance)."""
    same_grid = (
        roi.shape == reference.shape
        and np.allclose(roi.spacing, reference.spacing, atol=1e-3)
        and np.allclose(roi.origin, reference.origin, atol=1e-2)
        and np.allclose(roi.transform, reference.transform, atol=1e-3)
    )
    if not same_grid:
        raise ExternalSegmentationError(
            f"segmentation grid {roi.shape} does not match the images {reference.shape} ({folder})",
            hint="check that the folder belongs to this exam, segment and sequence (ROI_DIXON_* for Dixon)",
        )


def _muscle_labels(roi, labels: dict, folder: Path) -> dict:
    """Keep the labels actually drawn in the ROI that name a muscle side (NAME_R / NAME_L), bones excluded."""
    present = set(np.unique(np.asarray(roi)).tolist())
    muscles = {
        index: name for index, name in labels.items()
        if index in present
        and name.endswith(("_R", "_L"))
        and name.rsplit("_", 1)[0] not in NOT_MUSCLES
    }
    if not muscles:
        raise ExternalSegmentationError(
            f"no muscle label found in the segmentation of {folder}",
            hint="the folder must contain a Matlab muscle ROI (e.g. ROI_DIXON_LEG)",
        )
    return muscles
