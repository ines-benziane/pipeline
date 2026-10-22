"""resume_pipeline: continue a job suspended for QC, with the user's decision."""

from pathlib import Path

import pytest

from runner import job_store, methods_registry
from runner.errors import JobNotFoundError
from runner.job import Job, JobState
from runner.resume import resume_pipeline
from tests.test_job_runner import RecordingMethod


@pytest.fixture(autouse=True)
def _fresh_method(monkeypatch):
    monkeypatch.setattr(RecordingMethod, "behaviour", "ok")
    monkeypatch.setattr(RecordingMethod, "calls", [])
    methods_registry.register(RecordingMethod)


@pytest.fixture
def suspended_job(isolated_store, tmp_path):
    job = Job(exam_id="EXAM001", source_dir="src", segment="legs", method_name="recording",
              series=[17, 18], state=JobState.SUSPENDED, qc="checkpoint", checkpoint="stage1",
              qc_dir=tmp_path / "qc")
    job_store.save(job)
    return job


def test_resume_continues_from_recorded_checkpoint(suspended_job, tmp_path):
    job = resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=False)

    assert [c[0] for c in RecordingMethod.calls] == ["handle_checkpoint"]
    assert RecordingMethod.calls[0][1]["name"] == "stage1"
    assert job.state is JobState.RESULTS_READY


def test_resume_keeps_the_same_job_id(suspended_job, tmp_path):
    job = resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=False)

    assert job.job_id == suspended_job.job_id


def test_resume_passes_user_decision(suspended_job, tmp_path):
    resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=False,
                    tag="swap", comment="ok after check")

    decision = RecordingMethod.calls[0][1]["decision"]
    assert (decision.decision_status, decision.tag, decision.comment) == ("yes", "swap", "ok after check")


@pytest.mark.parametrize("qc, expected", [(True, "checkpoint"), (False, "off")])
def test_resume_qc_flag(suspended_job, tmp_path, qc, expected):
    resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=qc)

    assert RecordingMethod.calls[0][1]["qc"] == expected


def test_resume_with_action_reruns_from_scratch(suspended_job, tmp_path):
    job = resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=False, action="global-swap")

    assert [c[0] for c in RecordingMethod.calls] == ["run"]
    assert job.checkpoint is None


def test_resume_keeps_the_original_qc_dir(suspended_job, tmp_path):
    """QC artifacts of the first run and of the resume must land in the same bundle."""
    job = resume_pipeline(suspended_job.job_id, tmp_path / "out", "yes", qc=True)

    assert Path(job.qc_dir) == tmp_path / "qc"


@pytest.mark.xfail(strict=True, reason="QC decision moves to a dedicated `qc` command (QC redesign, phase 2)")
def test_qc_refused_produces_no_result(suspended_job, tmp_path, isolated_store):
    """FONC-004: an exam refused at QC ("no") must not produce a result file."""
    resume_pipeline(suspended_job.job_id, tmp_path / "out", "no", qc=False)

    assert not isolated_store.exists() or not any(isolated_store.iterdir())


def test_resume_unknown_job_raises(isolated_store, tmp_path):
    with pytest.raises(JobNotFoundError):
        resume_pipeline("no-such-job", tmp_path / "out", "yes", qc=False)
