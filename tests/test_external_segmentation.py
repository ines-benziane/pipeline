"""External segmentation (methods/external_segmentation.py): a Matlab ROI folder replaces MuSeg-AI.
Synthetic folders with the Matlab layout: roi.hdr / roi.img (Analyze) + labels_<segment>.txt (ITK-SNAP)."""

import numpy as np
import pytest

from methods.dixon3pt import Dixon3ptMethod
from methods.external_segmentation import read_external_segmentation
from mutools import io
from mutools.io import volume
from runner.errors import ExternalSegmentationError, UnknownSegmentError
from runner.method import RunContext

SHAPE, SPACING, ORIGIN = (8, 6, 4), (1.0, 1.0, 5.0), (-10.0, -5.0, -20.0)
LABELS = {0: "Clear Label", 1: "NOISE", 2: "S_FAT", 6: "TIBIA_R", 8: "TA_R", 9: "TP_R",
          30: "EXT_R", 33: "EXT_L", 34: "FIB_L"}


def _reference(shape=SHAPE, spacing=SPACING, origin=ORIGIN):
    return volume.asvolume(np.zeros(shape), spacing=spacing, origin=origin)


def _roi_folder(tmp_path, drawn=(1, 6, 30, 33), labels_name="labels_leg.txt", **geometry):
    """Matlab-like ROI folder; `drawn` = label values actually painted in the ROI."""
    folder = tmp_path / "ROI_DIXON_LEG"
    folder.mkdir()
    arr = np.zeros(geometry.get("shape", SHAPE), dtype=np.uint16)
    for i, value in enumerate(drawn):
        arr[i, :, :] = value
    volume.write(folder / "roi.hdr", volume.asvolume(arr, spacing=geometry.get("spacing", SPACING),
                                                     origin=geometry.get("origin", ORIGIN)))
    io.write_labels(folder / labels_name, LABELS)
    return folder


def test_returns_roi_and_muscle_labels(tmp_path):
    rois, labels = read_external_segmentation(_roi_folder(tmp_path), _reference(), "legs")

    assert len(rois) == 1 and rois[0].shape == SHAPE
    assert labels == {30: "EXT_R", 33: "EXT_L"}


def test_only_labels_drawn_in_the_roi_are_kept(tmp_path):
    """TA_R, TP_R and FIB_L are listed in the labels file but absent from the ROI."""
    _, labels = read_external_segmentation(_roi_folder(tmp_path, drawn=(8, 34)), _reference(), "legs")

    assert labels == {8: "TA_R", 34: "FIB_L"}


def test_noise_fat_and_bones_are_not_muscles(tmp_path):
    _, labels = read_external_segmentation(_roi_folder(tmp_path, drawn=(1, 2, 6, 8)), _reference(), "legs")

    assert labels == {8: "TA_R"}


@pytest.mark.parametrize("missing", ["roi.hdr", "roi.img", "labels_leg.txt"])
def test_missing_file_is_named(tmp_path, missing):
    folder = _roi_folder(tmp_path)
    (folder / missing).unlink()

    with pytest.raises(ExternalSegmentationError, match=missing) as exc:
        read_external_segmentation(folder, _reference(), "legs")
    assert exc.value.hint


def test_labels_file_must_match_the_segment(tmp_path):
    """A legs folder given for thighs is refused (labels_thigh.txt expected)."""
    with pytest.raises(ExternalSegmentationError, match="labels_thigh.txt"):
        read_external_segmentation(_roi_folder(tmp_path), _reference(), "thighs")


def test_unknown_segment_rejected(tmp_path):
    with pytest.raises(UnknownSegmentError):
        read_external_segmentation(_roi_folder(tmp_path), _reference(), "arms")


@pytest.mark.parametrize("geometry", [
    {"shape": (8, 6, 5)},
    {"spacing": (1.0, 1.0, 3.0)},
    {"origin": (-10.0, -5.0, -25.0)},
])
def test_roi_on_another_grid_rejected(tmp_path, geometry):
    """E.g. the T2 ROI given to Dixon, or a ROI from another exam."""
    with pytest.raises(ExternalSegmentationError, match="does not match"):
        read_external_segmentation(_roi_folder(tmp_path, **geometry), _reference(), "legs")


def test_tiny_float_differences_tolerated(tmp_path):
    folder = _roi_folder(tmp_path)

    read_external_segmentation(folder, _reference(origin=(-10.001, -5.0, -20.0)), "legs")


def test_roi_without_any_muscle_rejected(tmp_path):
    with pytest.raises(ExternalSegmentationError, match="no muscle label"):
        read_external_segmentation(_roi_folder(tmp_path, drawn=(1, 2, 6)), _reference(), "legs")


def test_dixon_uses_the_external_roi_instead_of_museg(tmp_path, monkeypatch):
    """With ext_seg set, the automatic segmentation (MuSeg-AI) is never called."""
    method = Dixon3ptMethod()
    monkeypatch.setattr(method, "segmentation", lambda *a, **k: pytest.fail("MuSeg-AI called"))
    ctx = RunContext(source_dir="s", exam_id="E", workdir=tmp_path, segment="legs", series=[17, 18],
                     ext_seg=_roi_folder(tmp_path))

    rois, labels, exam_date = method._segment(ctx, [_reference()], "20260112")

    assert labels == {30: "EXT_R", 33: "EXT_L"} and exam_date == "20260112"
