"""Tests of the run lookup used by the QC window (runner/job_store.py): load_exam_jobs and latest_ready_job.
Run files are written in a temporary JOBS_DIR."""

import pytest

from runner import job_store
from runner.job import Job, JobState


def make_job(job_id, segment="thighs", method="dixon3pt", state=JobState.RESULTS_READY):
    exam_id = job_id.split("-")[0]
    return Job(exam_id=exam_id, source_dir="src", segment=segment, method_name=method, series=[1],
               state=state, job_id=job_id)


@pytest.fixture
def jobs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "JOBS_DIR", tmp_path)
    return tmp_path


# --- load_exam_jobs

def test_exam_never_run_has_no_job(jobs_dir):
    assert job_store.load_exam_jobs("EX") == []


def test_load_exam_jobs_keeps_only_this_exam(jobs_dir):
    for job_id in ("EX-20261101-100000-aaaa", "EX-20261102-100000-bbbb", "EY-20261101-100000-cccc",
                   "EX2-20261101-100000-dddd"):
        job_store.save(make_job(job_id))
    assert [job.job_id for job in job_store.load_exam_jobs("EX")] == [
        "EX-20261101-100000-aaaa", "EX-20261102-100000-bbbb"]


# --- latest_ready_job

def test_no_run_for_the_block_is_none():
    assert job_store.latest_ready_job([make_job("EX-20261101-100000-aaaa", segment="legs")], "thighs", "dixon3pt") is None


def test_latest_ready_job_is_the_most_recent_ready_run_of_the_block():
    jobs = [
        make_job("EX-20261101-100000-aaaa"),
        make_job("EX-20261103-100000-bbbb"),
        make_job("EX-20261102-100000-cccc"),
        make_job("EX-20261104-100000-dddd", state=JobState.FAILED),        # more recent but failed
        make_job("EX-20261105-100000-eeee", method="t2map_3exp"),          # other block
        make_job("EX-20261106-100000-ffff", segment="legs"),               # other block
    ]
    assert job_store.latest_ready_job(jobs, "thighs", "dixon3pt").job_id == "EX-20261103-100000-bbbb"


@pytest.mark.parametrize("state", [JobState.PENDING, JobState.IN_PROGRESS, JobState.SUSPENDED, JobState.FAILED])
def test_runs_without_results_never_count(state):
    assert job_store.latest_ready_job([make_job("EX-20261101-100000-aaaa", state=state)], "thighs", "dixon3pt") is None
