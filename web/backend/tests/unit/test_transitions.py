import pytest

from ssscreen_web.domain.enums import RunStatus, TaskStatus
from ssscreen_web.domain.errors import InvalidTransition
from ssscreen_web.domain.transitions import ensure_run_transition, ensure_task_transition


def test_valid_transitions() -> None:
    ensure_run_transition(RunStatus.DRAFT, RunStatus.QUEUED)
    ensure_task_transition(TaskStatus.FAILED, TaskStatus.READY)
    ensure_task_transition(TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED)


def test_invalid_transition_has_stable_error() -> None:
    with pytest.raises(InvalidTransition, match="cannot transition") as caught:
        ensure_task_transition(TaskStatus.RUNNING, TaskStatus.READY)
    assert caught.value.code == "task.invalid_transition"
