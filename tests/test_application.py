"""Tests for Application class."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from origin.environment import ResolvedEnvironment
from origin.launch import Application


@pytest.fixture()
def mock_resolved() -> ResolvedEnvironment:
    return ResolvedEnvironment(
        env={"MYTOOL_ROOT": "T:/packages/mytool/2.3.0"}, packages=[]
    )


@pytest.fixture()
def mock_process() -> MagicMock:
    return MagicMock(spec=subprocess.Popen)


@pytest.fixture()
def app(mock_process: MagicMock, mock_resolved: ResolvedEnvironment) -> Application:
    return Application(
        executable=Path("nuke"),
        loadout="nuke",
        process=mock_process,
        resolved=mock_resolved,
    )


def test_wait_returns_exit_code(app: Application, mock_process: MagicMock) -> None:
    mock_process.wait.return_value = 0
    assert app.wait() == 0


def test_poll_returns_none_while_running(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = None
    assert app.poll() is None


def test_poll_returns_exit_code_when_finished(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = 0
    assert app.poll() == 0


def test_has_crashed_false_while_running(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = None
    assert app.has_crashed is False


def test_has_crashed_false_on_clean_exit(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = 0
    assert app.has_crashed is False


def test_has_crashed_true_on_nonzero_exit(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = 1
    assert app.has_crashed is True


def test_resolved_environment_available_on_crash(
    app: Application, mock_process: MagicMock
) -> None:
    mock_process.poll.return_value = 1
    assert app.has_crashed is True
    assert "MYTOOL_ROOT" in app.resolved.env
