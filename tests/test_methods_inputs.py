"""Real methods (dixon3pt, t2map_3exp): contract with the runner and input guards.
No DICOM data needed: every case fails before any computation."""

import dataclasses
import inspect

import numpy as np
import pytest

from methods.dixon3pt import Dixon3ptMethod, MODEL_BY_SEGMENT
from methods.t2map_3exp import T2Map3ExpMethod
from mutools.io.volume import asvolume
from runner.errors import DicomSelectionError, UnknownSegmentError
from runner.method import RunContext

METHODS = [Dixon3ptMethod, T2Map3ExpMethod]


def _ctx(tmp_path, **overrides):
    kwargs = dict(source_dir=str(tmp_path), exam_id="E", workdir=tmp_path / "wd", segment="legs", series=[17, 18])
    kwargs.update(overrides)
    return RunContext(**kwargs)


@pytest.mark.parametrize("method_class", METHODS)
def test_run_accepts_the_runner_call(method_class):
    """job_runner calls run(ctx) with a single RunContext."""
    inspect.signature(method_class().run).bind(RunContext(source_dir="s", exam_id="E", workdir="w",
                                                          segment="legs", series=[17, 18]))


def test_run_context_is_frozen(tmp_path):
    """A method cannot change the caller's context; it must copy it (dataclasses.replace)."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        _ctx(tmp_path).qc = "global"


@pytest.mark.parametrize("method_class", METHODS)
def test_handle_checkpoint_accepts_the_runner_call(method_class):
    """job_runner calls handle_checkpoint(...) with these keywords, seg_series included."""
    inspect.signature(method_class().handle_checkpoint).bind(
        name="x", workdir="w", segment="legs", exam_id="E", qc="off", qc_dir=None,
        decision=None, debug=False, multicenter=False, seg_series=None,
    )


@pytest.mark.parametrize("method_class", METHODS)
def test_unknown_action_rejected(method_class, tmp_path):
    with pytest.raises(ValueError):
        method_class().run(_ctx(tmp_path, action="no-such-action"))


@pytest.mark.parametrize("method_class", METHODS)
def test_missing_series_raise_dicom_selection_error(method_class, tmp_path):
    """FONC-003: a folder without the requested series fails with an explicit error."""
    with pytest.raises(DicomSelectionError):
        method_class().run(_ctx(tmp_path))


def test_dixon_unknown_checkpoint_rejected(tmp_path):
    with pytest.raises(ValueError):
        Dixon3ptMethod().handle_checkpoint(name="no-such-stage", workdir=tmp_path, segment="legs",
                                           exam_id="E", qc="off")


def test_dixon_unknown_segment_rejected(tmp_path):
    vol = asvolume(np.ones((4, 4, 4)))
    with pytest.raises(UnknownSegmentError):
        Dixon3ptMethod().segmentation([vol, vol, vol], "arms", "E", "off", "20260112", tmp_path)


def test_every_segment_has_a_model():
    assert set(MODEL_BY_SEGMENT) == {"legs", "thighs"}
