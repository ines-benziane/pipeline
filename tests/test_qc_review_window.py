"""QC review window (gui/qc_review_window.py), driven without clicks: entries are set through the window's
variables, then "Valider" is called. Runs are written in a temporary JOBS_DIR, QCs in a temporary store.
Skipped where no display is available (e.g. over plain SSH on the station)."""

import tkinter as tk

import pytest

from adapters.file_qc_review_store import FileQCReviewStore
from gui import qc_review_window as qrw
from runner import job_store
from runner.job import Job, JobState
from runner.qc_review import Grade, MapDecision, MuscleError, ReviewStatus, SegmentationDecision, Side

EXAM = "EXQC"


@pytest.fixture(scope="module")
def root():
    """One Tk root for the whole module: creating many Tk() in one process randomly fails on Windows."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def dialogs(monkeypatch):
    """Record the message boxes instead of showing them."""
    shown = []
    for kind in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(qrw.messagebox, kind, lambda title, message, kind=kind, **kw: shown.append((kind, message)))
    return shown


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """Thighs FF and T2 have a finished run; legs were not acquired."""
    monkeypatch.setattr(job_store, "JOBS_DIR", tmp_path / "jobs")
    for job_id, method in [(f"{EXAM}-20261126-090000-aaaa", "dixon3pt"), (f"{EXAM}-20261126-090100-bbbb", "t2map_3exp")]:
        job_store.save(Job(exam_id=EXAM, source_dir="src", segment="thighs", method_name=method, series=[1],
                           state=JobState.RESULTS_READY, job_id=job_id))


@pytest.fixture
def window(root, runs, tmp_path, dialogs):
    return qrw.QCReviewWindow(root, EXAM, store=FileQCReviewStore(tmp_path / "qc"))


def _block(window, segment, method):
    return next(b for b in window.blocks if (b.segment, b.method) == (segment, method))


def _fill(block, map_decision=MapDecision.COMPLETE, seg_decision=SegmentationDecision.ACCEPTED, small=3):
    block.map_decision.set(map_decision.value)
    block.seg_decision.set(seg_decision.value)
    block.counts["small"].set(str(small))


def test_each_block_is_wired_to_its_current_run(window):
    assert _block(window, "thighs", "dixon3pt").job.job_id == f"{EXAM}-20261126-090000-aaaa"
    assert _block(window, "thighs", "t2map_3exp").job.job_id == f"{EXAM}-20261126-090100-bbbb"
    assert not _block(window, "legs", "dixon3pt").acquired
    assert not _block(window, "legs", "t2map_3exp").acquired


def test_validate_saves_one_validated_qc_per_filled_block(window, tmp_path, dialogs):
    _fill(_block(window, "thighs", "dixon3pt"))
    window._validate()

    store = FileQCReviewStore(tmp_path / "qc")
    [qc] = store.list_for_block(EXAM, "thighs", "dixon3pt")
    assert (qc.status, qc.job_id, qc.segmentation.grade) == (ReviewStatus.VALIDATED, f"{EXAM}-20261126-090000-aaaa", Grade.GOOD)
    assert qc.validated_at is not None and qc.duration_s is not None
    assert store.list_for_block(EXAM, "thighs", "t2map_3exp") == []   # block left empty: not saved
    assert dialogs[-1][0] == "showinfo"


def test_incomplete_block_blocks_the_whole_validation(window, tmp_path, dialogs):
    _fill(_block(window, "thighs", "dixon3pt"))
    _block(window, "thighs", "t2map_3exp").map_decision.set(MapDecision.REJECTED.value)   # no reason, no seg decision
    window._validate()

    assert FileQCReviewStore(tmp_path / "qc").list_for_block(EXAM, "thighs", "dixon3pt") == []
    assert dialogs[-1][0] == "showwarning"


def test_poor_grade_forces_rejected(window):
    block = _block(window, "thighs", "dixon3pt")
    block.seg_decision.set(SegmentationDecision.ACCEPTED.value)
    block.counts["large"].set("1")
    assert block.seg_decision.get() == SegmentationDecision.REJECTED.value


def test_copy_fills_the_other_block_of_the_segment(window):
    source = _block(window, "thighs", "dixon3pt")
    target = _block(window, "thighs", "t2map_3exp")
    _fill(source, map_decision=MapDecision.LEFT_ONLY, small=4)
    source.map_reason.set("Artefact de mouvement")

    window._copy_into(target)

    assert target.map_decision.get() == MapDecision.LEFT_ONLY.value
    assert target.map_reason.get() == "Artefact de mouvement"
    assert target.counts["small"].get() == "4"
    assert target.copied_from == source.qc_id


def test_muscle_errors_are_saved_with_the_qc(window, tmp_path):
    block = _block(window, "thighs", "dixon3pt")
    _fill(block)
    for muscle, other, side in [("VL", "VI", "gauche"), ("SAR", "fond", "les deux")]:
        block._error_muscle.set(muscle)
        block._error_other.set(other)
        block._error_side.set(side)
        block._add_error()
    window._validate()

    [qc] = FileQCReviewStore(tmp_path / "qc").list_for_block(EXAM, "thighs", "dixon3pt")
    assert qc.segmentation.errors == (MuscleError("VL", "VI", Side.LEFT), MuscleError("SAR", "background", Side.BOTH))


def test_draft_is_saved_then_resumed_then_replaced_by_the_validated_qc(root, runs, tmp_path, dialogs):
    store = FileQCReviewStore(tmp_path / "qc")
    first = qrw.QCReviewWindow(root, EXAM, store=store)
    _block(first, "thighs", "dixon3pt").map_decision.set(MapDecision.COMPLETE.value)
    first._save_drafts()
    [draft] = store.list_for_block(EXAM, "thighs", "dixon3pt")
    assert draft.status is ReviewStatus.DRAFT

    second = qrw.QCReviewWindow(root, EXAM, store=store)
    block = _block(second, "thighs", "dixon3pt")
    assert block.map_decision.get() == MapDecision.COMPLETE.value   # entries filled back in
    block.seg_decision.set(SegmentationDecision.ACCEPTED.value)
    second._validate()

    [qc] = store.list_for_block(EXAM, "thighs", "dixon3pt")         # same file: the draft became the validated QC
    assert (qc.qc_id, qc.status) == (draft.qc_id, ReviewStatus.VALIDATED)


def test_overview_is_always_shown_whole_when_the_window_is_resized(root, tmp_path):
    from PIL import Image
    path = tmp_path / "overview.png"
    Image.new("L", (448, 2240)).save(path)   # 10 slices in one column: taller than most screens
    viewer = qrw.OverviewViewer(root, path, "aperçu")
    root.update()

    for geometry in (None, "300x300", "900x400"):
        if geometry:
            viewer.top.geometry(geometry)
            root.update()
        shown_w, shown_h = viewer.photo.width(), viewer.photo.height()
        assert shown_w <= viewer.label.winfo_width() and shown_h <= viewer.label.winfo_height()
        assert abs(shown_w / shown_h - 448 / 2240) < 0.02   # proportions kept
    viewer.top.destroy()


def test_summary_says_what_the_report_will_contain(window):
    _fill(_block(window, "thighs", "dixon3pt"))
    window._refresh_summary()
    lines = [label.cget("text") for label in window._summary_lines]
    assert lines[0].startswith("✔") and "paraît" in lines[0]          # thighs FF filled and accepted
    assert "non contrôlé" in lines[1]                                   # thighs T2 not filled
    assert "non acquis" in lines[2] and "non acquis" in lines[3]       # legs
