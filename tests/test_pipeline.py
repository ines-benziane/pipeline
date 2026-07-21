from pathlib import Path

import pytest

from methods.dummy import DummyMethod
from runner import methods_registry
from runner.job import Job, JobState
from runner.method import Method, Result
from runner.runner import run_pipeline


class NotAutoValidMethod(Method):
    name = "not_auto_valid"
    version = "0"
    comparability_criteria = []

    def run(self, exam_dir, workdir, segment):
        output = Path(workdir) / "not_auto_valid.json"
        output.write_text("{}", encoding="utf-8")
        return Result(
            results=output,
            auto_valid=False,
            provenance={"name": self.name},
        )


def test_registry_raises_on_unknown_method():
    with pytest.raises(KeyError):
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


def test_job_reaches_completed():
    methods_registry.register(DummyMethod)
    job = Job(job_id="test001", exam_id="exam_test", segment="legs", method_id="dummy")
    run_pipeline(job)
    assert job.state is JobState.COMPLETED


def test_job_reaches_suspended():
    methods_registry.register(NotAutoValidMethod)
    job = Job(job_id="test002", exam_id="exam_test", segment="legs", method_id="not_auto_valid")
    run_pipeline(job)
    assert job.state is JobState.SUSPENDED