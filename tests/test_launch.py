"""Tests for launch.py"""

import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch
from typing import Any
from typing import Generator

import pytest

from origin.environment import EnvironmentConfig
from origin.environment import EnvironmentResolver
from origin.launch import launch

ENVIRONMENT_JSON = {
    "name": "MYSHOW",
    "packages_root": "T:/packages",
    "packages": {
        "pipelinecore": "1.2.0",
        "mytool": "2.3.0",
    },
    "loadouts": {
        "nuke": ["pipelinecore", "mytool"],
    },
}

PIPELINECORE_PACKAGE_JSON = {
    "name": "pipelinecore",
    "version": "1.2.0",
    "python_paths": ["python"],
    "env": {
        "PIPELINECORE_ROOT": "{root}",
    },
}

MYTOOL_PACKAGE_JSON = {
    "name": "mytool",
    "version": "2.3.0",
    "python_paths": ["python"],
    "env": {
        "MYTOOL_ROOT": "{root}",
        "MYTOOL_PLUGINS": "{root}/plugins",
    },
}


def make_mock_open(files: dict[str, dict]) -> MagicMock:
    """
    Return a mock for builtins.open that serves different JSON content per path.

    Args:
        files (dict[str, dict]): Maps file path strings to the dict that
            should be returned when that path is opened and JSON-decoded.
    Returns:
        MagicMock: A mock suitable for patching builtins.open.
    """
    normalized = {str(Path(k)): v for k, v in files.items()}

    def _open(path, *args, **kwargs):
        content = json.dumps(normalized[str(Path(path))])
        return mock_open(read_data=content)()

    return MagicMock(side_effect=_open)


@pytest.fixture()
def env_config_path() -> Path:
    return Path("T:/shows/MYSHOW/Environment.json")


@pytest.fixture()
def resolver(env_config_path: Path) -> Generator[EnvironmentResolver, Any, None]:
    files = {
        str(env_config_path): ENVIRONMENT_JSON,
        "T:/packages/pipelinecore/1.2.0/Package.json": PIPELINECORE_PACKAGE_JSON,
        "T:/packages/mytool/2.3.0/Package.json": MYTOOL_PACKAGE_JSON,
    }
    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.is_dir", return_value=True):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            yield resolver


def test_resolve_sets_pythonpath(resolver: EnvironmentResolver) -> None:
    resolved = resolver.resolve(["nuke"])
    assert "PYTHONPATH" in resolved.env


def test_resolve_sets_package_env_vars(resolver: EnvironmentResolver) -> None:
    resolved = resolver.resolve(["nuke"])
    assert "MYTOOL_ROOT" in resolved.env
    assert "MYTOOL_PLUGINS" in resolved.env


def test_resolve_returns_correct_packages(resolver: EnvironmentResolver) -> None:
    resolved = resolver.resolve(["nuke"])
    names = [p.name for p in resolved.packages]
    assert names == ["pipelinecore", "mytool"]


def test_launch_calls_popen(env_config_path: Path) -> None:
    files = {
        str(env_config_path): ENVIRONMENT_JSON,
        "T:/packages/pipelinecore/1.2.0/Package.json": PIPELINECORE_PACKAGE_JSON,
        "T:/packages/mytool/2.3.0/Package.json": MYTOOL_PACKAGE_JSON,
    }
    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("subprocess.Popen") as mock_popen:
                launch(
                    executable=Path("nuke"),
                    environment_config=env_config_path,
                    loadout="nuke",
                )
    mock_popen.assert_called_once()
    assert mock_popen.call_args[0][0][0] == "nuke"
