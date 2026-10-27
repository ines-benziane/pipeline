from pathlib import Path

import pytest

from methods.dummy import DummyMethod
from runner import job_runner, job_store, methods_registry
from runner.errors import MethodNotFoundError
from runner.job import Job, JobState
from runner.method import Method, Result
from runner.job_runner import run_job


class NotAutoValidMethod(Method):
    name = "not_auto_valid"
    version = "0"
    comparability_criteria = []

    def run(self, ctx):
        output = Path(ctx.workdir) / "not_auto_valid.json"
        output.write_text("{}", encoding="utf-8")
        return Result(
            results=output,
            auto_valid=False,
            provenance={"name": self.name},
        )

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None,
                          decision=None, debug=False, multicenter=False, seg_series=None):
        raise NotImplementedError


@pytest.fixture
def isolated_workdirs(tmp_path, monkeypatch):
    monkeypatch.setattr(job_runner, "WORKDIR_ROOT", tmp_path / "workdirs")
    monkeypatch.setattr(job_runner, "RESULT_DIR", tmp_path / "workdirs" / "results")
    monkeypatch.setattr(job_store, "JOBS_DIR", tmp_path / "workdirs" / "jobs")
    return tmp_path


def test_registry_raises_on_unknown_method():
    with pytest.raises(MethodNotFoundError):
        methods_registry.get("no_such_method")


def test_registry_returns_an_instance():
    methods_registry.register(DummyMethod)
    method = methods_registry.get("dummy")
    assert isinstance(method, DummyMethod)


def test_method_without_run_is_rejected():
    class IncompleteMethod(Method):
        name = "incomplete"
        version = "0"
        comparability_criteria = []

    with pytest.raises(TypeError):
        IncompleteMethod()


def test_job_reaches_results_ready(isolated_workdirs):
    methods_registry.register(DummyMethod)
    job = Job(job_id="test001", exam_id="exam_test", segment="legs", method_name="dummy",
              series="13, 14", source_dir="testeuh")
    run_job(job, output_dir=isolated_workdirs / "out")
    assert job.state is JobState.RESULTS_READY


def test_job_reaches_suspended(isolated_workdirs):
    methods_registry.register(NotAutoValidMethod)
    job = Job(job_id="test002", exam_id="exam_test", segment="legs", method_name="not_auto_valid", series="13,14", source_dir="test_00")
    run_job(job, output_dir=isolated_workdirs / "out")
    assert job.state is JobState.SUSPENDED
