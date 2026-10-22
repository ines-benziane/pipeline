"""QC images (methods/quality_check/qc.py) and per-muscle extraction config (methods/get_results).
Synthetic volumes: two square 'muscles' with constant FF (0.3 and 0.7), 6 slices."""

import numpy as np
import pytest
from PIL import Image

from methods.get_results.getresults import getresults
from methods.quality_check.qc import quality_check_seg, quality_check_volumes, save_gif
from mutools.io.orientation import set_orientation
from mutools.io.volume import asvolume

SHAPE, SPACING = (20, 20, 6), (1, 1, 5)
LABELS = {1: "VL_R", 2: "VI_R"}


def _roi_array():
    roi = np.zeros(SHAPE, dtype=int)
    roi[5:10, 5:10, :] = 1
    roi[12:18, 12:18, :] = 2
    return roi


@pytest.fixture
def ffmap():
    arr = np.zeros(SHAPE)
    arr[5:10, 5:10, :] = 0.3
    arr[12:18, 12:18, :] = 0.7
    return asvolume(arr, spacing=SPACING)


class MusegRoi:
    """Shape of the ROI object returned by MuSeg-AI (flat row-major transform)."""
    def __init__(self, array):
        self.array, self.spacing, self.origin = array, SPACING, (0, 0, 0)
        self.transform = [1, 0, 0, 0, 1, 0, 0, 0, 1]


# --- overview image (FF map) -----------------------------------------------------

def test_overview_is_an_image(ffmap):
    image = quality_check_volumes(ffmap)

    assert isinstance(image, Image.Image)
    assert image.size[0] > 0 and image.size[1] > 0


def test_overview_does_not_depend_on_stored_orientation(ffmap):
    """The same anatomy stored in another orientation must give the same QC picture (RAI display)."""
    reoriented = set_orientation(ffmap, "LPS")

    assert np.array_equal(np.asarray(quality_check_volumes(ffmap)), np.asarray(quality_check_volumes(reoriented)))


# --- segmentation GIF ----------------------------------------------------------------

def test_one_frame_per_slice(ffmap):
    frames = quality_check_seg(ffmap, MusegRoi(_roi_array()), LABELS)

    assert len(frames) == SHAPE[2]


def test_step_skips_slices(ffmap):
    assert len(quality_check_seg(ffmap, MusegRoi(_roi_array()), LABELS, step=2)) == 3


def test_roi_is_drawn_on_the_frames(ffmap):
    with_roi = quality_check_seg(ffmap, MusegRoi(_roi_array()), LABELS)[0]
    without_roi = quality_check_seg(ffmap, MusegRoi(np.zeros(SHAPE, dtype=int)), LABELS)[0]

    assert not np.array_equal(np.asarray(with_roi), np.asarray(without_roi))


def test_gif_written_with_all_frames(tmp_path):
    arr = np.zeros(SHAPE)
    for k in range(SHAPE[2]):
        arr[2 + k:8 + k, 5:10, k] = 0.5   # anatomy changes from slice to slice, as in real data
    frames = quality_check_seg(asvolume(arr, spacing=SPACING), MusegRoi(_roi_array()), LABELS)
    path = tmp_path / "segmentation.gif"

    save_gif(frames, path)

    with Image.open(path) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames == len(frames)


# --- per-muscle extraction (results_config.yml) -------------------------------------

def _volume_rows(table):
    rows = table[table.HOW == "VOLUME"].set_index("LABEL")
    return {label: (row.NPIX, row.FF) for label, row in rows.iterrows()}


def test_mean_ff_per_muscle(ffmap):
    rows = _volume_rows(getresults({"ffmap": ffmap}, "dixon3pt", asvolume(_roi_array(), spacing=SPACING), LABELS))

    assert rows["VL_R"][1] == pytest.approx(0.3)
    assert rows["VI_R"][1] == pytest.approx(0.7)


def test_roi_border_eroded_before_measuring(ffmap):
    """Config: in-plane erosion, so the counted pixels are fewer than the drawn ROI."""
    rows = _volume_rows(getresults({"ffmap": ffmap}, "dixon3pt", asvolume(_roi_array(), spacing=SPACING), LABELS))

    assert 0 < rows["VI_R"][0] < (_roi_array() == 2).sum()


def test_ff_outside_0_1_excluded_from_the_mean(ffmap):
    """Config filter (0 <= FF <= 1): aberrant voxels do not bias the muscle mean."""
    arr = np.asarray(ffmap).copy()
    arr[14, 14, :] = 5.0
    rows = _volume_rows(getresults({"ffmap": asvolume(arr, spacing=SPACING)}, "dixon3pt",
                                   asvolume(_roi_array(), spacing=SPACING), LABELS))

    assert rows["VI_R"][1] == pytest.approx(0.7)


def test_slice_rows_and_outlines_produced(ffmap):
    table = getresults({"ffmap": ffmap}, "dixon3pt", asvolume(_roi_array(), spacing=SPACING), LABELS)
    slices = table[table.HOW == "SLICE"]

    assert len(slices) == len(LABELS) * SHAPE[2]
    assert "OUTLINE" in table.columns


def _t2_volumes(ffmap, t2_outlier=None, cint_outlier=None):
    t2 = np.zeros(SHAPE)
    t2[5:10, 5:10, :], t2[12:18, 12:18, :] = 40.0, 50.0
    cint = np.full(SHAPE, 2.0)
    if t2_outlier is not None:
        t2[14, 14, :] = t2_outlier
    if cint_outlier is not None:
        cint[15, 15, :] = cint_outlier
    return {"t2map": asvolume(t2, spacing=SPACING), "t2cint": asvolume(cint, spacing=SPACING), "ffmap": ffmap}


def _t2_rows(volumes):
    table = getresults(volumes, "t2map_3exp", asvolume(_roi_array(), spacing=SPACING), LABELS)
    return table[table.HOW == "VOLUME"].set_index("LABEL")


def test_mean_t2_per_muscle(ffmap):
    rows = _t2_rows(_t2_volumes(ffmap))

    assert rows.loc["VL_R", "T2"] == pytest.approx(40.0)
    assert rows.loc["VI_R", "T2"] == pytest.approx(50.0)


@pytest.mark.parametrize("outlier", [{"t2_outlier": 90.0}, {"t2_outlier": 10.0}, {"cint_outlier": 15.0}])
def test_t2_voxels_outside_config_limits_excluded(ffmap, outlier):
    """Config filter: 15 < T2 < 70 ms and confidence interval <= 10; other voxels do not enter the mean."""
    assert _t2_rows(_t2_volumes(ffmap, **outlier)).loc["VI_R", "T2"] == pytest.approx(50.0)


def test_unknown_method_has_no_config(ffmap):
    with pytest.raises(KeyError):
        getresults({"ffmap": ffmap}, "no_such_method", asvolume(_roi_array(), spacing=SPACING), LABELS)
