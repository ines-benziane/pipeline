"""Job (state carrier) and job_store (persistence used to resume after QC or a crash)."""

from pathlib import Path

import pytest

from runner import job_store
from runner.errors import JobNotFoundError
from runner.job import Job, JobState


def _job(**overrides):
    kwargs = dict(exam_id="EXAM001", source_dir="src", segment="legs",
                  method_name="dixon3pt", series=[17, 18])
    kwargs.update(overrides)
    return Job(**kwargs)


def test_job_id_is_generated_and_prefixed_by_exam_id():
    job = _job()
    assert job.job_id.startswith("EXAM001-")


def test_generated_job_ids_are_unique():
    assert _job().job_id != _job().job_id


def test_given_job_id_is_kept():
    assert _job(job_id="my-id").job_id == "my-id"


def test_new_job_is_pending():
    assert _job().state is JobState.PENDING


@pytest.mark.parametrize("qc", ["off", "checkpoint", "global"])
def test_valid_qc_modes_accepted(qc):
    assert _job(qc=qc).qc == qc


def test_invalid_qc_mode_rejected():
    with pytest.raises(ValueError):
        _job(qc="maybe")


def test_store_round_trip_keeps_every_field(isolated_store, tmp_path):
    """A resumed job must come back exactly as it was saved."""
    job = _job(
        state=JobState.SUSPENDED,
        workdir=tmp_path / "wd",
        method_params={"fixed_fat": "1"},
        exam_date="20260112",
        qc="checkpoint",
        checkpoint="mutools",
        qc_dir=tmp_path / "qc",
        multicenter=True,
        seg_series=[22, 23],
        ext_seg=tmp_path / "ROI_DIXON_LEG",
    )
    job_store.save(job)

    assert job_store.load(job.job_id) == job


def test_load_unknown_job_raises(isolated_store):
    with pytest.raises(JobNotFoundError):
        job_store.load("no-such-job")
