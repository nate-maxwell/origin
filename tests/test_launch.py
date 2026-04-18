"""Tests for launch.py"""

from pathlib import Path
from unittest.mock import patch

import pytest

from origin.application import Application
from origin.launch import launch
from tests.helpers import make_mock_open

# -----Test data---------------------------------------------------------------

ENVIRONMENT_YAML = {
    "name": "MYSHOW",
    "repositories": [
        "/fake/packages",
    ],
    "packages": {
        "mytool": "2.3.0",
    },
    "loadouts": {
        "nuke": ["mytool"],
    },
}

MYTOOL_PACKAGE_YAML = {
    "name": "mytool",
    "version": "2.3.0",
    "env": {
        "MYTOOL_ROOT": "/fake/packages/mytool/2.3.0",
    },
}


# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def env_config_path() -> Path:
    return Path("/fake/shows/MYSHOW/environment.yaml")


@pytest.fixture()
def all_files(env_config_path: Path) -> dict[str, dict]:
    return {
        str(env_config_path): ENVIRONMENT_YAML,
        "/fake/packages/mytool/2.3.0/package.yaml": MYTOOL_PACKAGE_YAML,
    }


# -----launch------------------------------------------------------------------


def test_launch_returns_application(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen"):
                app = launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    assert isinstance(app, Application)


def test_launch_calls_popen(env_config_path: Path, all_files: dict[str, dict]) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    mock_popen.assert_called_once()


def test_launch_passes_executable_to_popen(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "/fake/nuke"


def test_launch_passes_args_to_popen(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                    args=["--nukex"],
                )
    cmd = mock_popen.call_args[0][0]
    assert "--nukex" in cmd


def test_launch_passes_resolved_env_to_popen(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    env = mock_popen.call_args[1]["env"]
    assert "MYTOOL_ROOT" in env


def test_launch_stores_loadout_on_application(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen"):
                app = launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    assert app.loadout == "nuke"


def test_launch_stores_resolved_env_on_application(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("subprocess.Popen"):
                app = launch(
                    executable=Path("/fake/nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                    base_env={},
                )
    assert "MYTOOL_ROOT" in app.resolved.env
