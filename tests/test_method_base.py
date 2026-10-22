"""Method base class guards and the methods registry."""

import pytest

from runner import methods_registry
from runner.method import Method, QCCheckpoint


class StagedMethod(Method):
    name = "staged"
    version = "0"
    comparability_criteria = []
    CHECKPOINTS = ("stage1", "stage2")
    ACTIONS = ("global-swap",)

    def run(self, *args, **kwargs):
        ...

    def handle_checkpoint(self, **kwargs):
        ...


def test_known_checkpoint_accepted():
    StagedMethod()._check_checkpoint("stage2")


def test_unknown_checkpoint_rejected():
    with pytest.raises(ValueError):
        StagedMethod()._check_checkpoint("stage3")


@pytest.mark.parametrize("action", [None, "global-swap"])
def test_no_action_or_known_action_accepted(action):
    StagedMethod()._check_action(action)


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        StagedMethod()._check_action("local-swap")


def test_qc_checkpoint_carries_stage_name():
    assert QCCheckpoint("stage1").name == "stage1"


def test_registry_get_returns_a_new_instance_each_time():
    methods_registry.register(StagedMethod)
    assert methods_registry.get("staged") is not methods_registry.get("staged")


def test_list_methods_returns_a_copy():
    methods_registry.register(StagedMethod)
    listed = methods_registry.list_methods()
    listed.pop("staged")
    assert "staged" in methods_registry.list_methods()
