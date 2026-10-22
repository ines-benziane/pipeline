import pytest


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Redirect workdirs, results and the job store to tmp_path; returns the results dir."""
    results_dir = tmp_path / "results"
    monkeypatch.setattr("runner.job_runner.WORKDIR_ROOT", tmp_path / "workdirs")
    monkeypatch.setattr("runner.job_runner.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.pipeline.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.job_store.JOBS_DIR", tmp_path / "jobs")
    return results_dir
