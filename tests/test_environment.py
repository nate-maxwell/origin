"""Tests for environment.py"""

import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch
from typing import Any
from typing import Generator

import pytest

from origin.environment import (
    EnvironmentConfig,
    EnvironmentResolver,
    PackageConfig,
    PackageNotFoundError,
    VersionNotSpecifiedError,
)

# -----Test data---------------------------------------------------------------

ENVIRONMENT_JSON = {
    "name": "MYSHOW",
    "packages_root": "T:/packages",
    "versions": {
        "pipelinecore": "1.2.0",
        "mytool": "2.3.0",
    },
    "loadouts": {
        "nuke": ["pipelinecore", "mytool"],
        "myapp": ["pipelinecore"],
    },
}

PIPELINECORE_PACKAGE_JSON = {
    "name": "pipelinecore",
    "version": "1.2.0",
    "env": {
        "PIPELINECORE_ROOT": "{root}",
    },
}

MYTOOL_PACKAGE_JSON = {
    "name": "mytool",
    "version": "2.3.0",
    "env": {},
}


# -----Helpers-----------------------------------------------------------------


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


# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def env_config_path() -> Path:
    return Path("T:/shows/MYSHOW/Environment.json")


@pytest.fixture()
def all_files(env_config_path: Path) -> dict[str, dict]:
    return {
        str(env_config_path): ENVIRONMENT_JSON,
        "T:/packages/pipelinecore/1.2.0/Package.json": PIPELINECORE_PACKAGE_JSON,
        "T:/packages/mytool/2.3.0/Package.json": MYTOOL_PACKAGE_JSON,
    }


@pytest.fixture()
def resolver(
    env_config_path: Path, all_files: dict[str, dict]
) -> Generator[EnvironmentResolver, Any, None]:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.is_dir", return_value=True):
            cfg = EnvironmentConfig.from_file(env_config_path)
            yield EnvironmentResolver(cfg)


# -----PackageConfig.from_file-------------------------------------------------


def test_package_config_parses_name(all_files: dict[str, dict]) -> None:
    path = Path("T:/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.name == "mytool"


def test_package_config_parses_version(all_files: dict[str, dict]) -> None:
    path = Path("T:/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.version == "2.3.0"


def test_package_config_injects_version_env_var(all_files: dict[str, dict]) -> None:
    path = Path("T:/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["MYTOOL_VERSION"] == "2.3.0"


# -----EnvironmentConfig.from_file---------------------------------------------


def test_environment_config_parses_name(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.name == "MYSHOW"


def test_environment_config_parses_versions(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.versions["mytool"] == "2.3.0"
    assert cfg.versions["pipelinecore"] == "1.2.0"


def test_environment_config_parses_loadouts(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.loadouts["nuke"] == ["pipelinecore", "mytool"]


# -----EnvironmentResolver.resolve---------------------------------------------


def test_resolve_returns_correct_package_names(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert [p.name for p in resolved.packages] == ["pipelinecore", "mytool"]


def test_resolve_returns_correct_package_versions(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    versions = {p.name: p.version for p in resolved.packages}
    assert versions["mytool"] == "2.3.0"
    assert versions["pipelinecore"] == "1.2.0"


def test_resolve_sets_pythonpath(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert "PYTHONPATH" in resolved.env


def test_resolve_pythonpath_contains_package_roots(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert "T:/packages/pipelinecore/1.2.0" in resolved.env["PYTHONPATH"]
    assert "T:/packages/mytool/2.3.0" in resolved.env["PYTHONPATH"]


def test_resolve_sets_version_env_var(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert resolved.env["MYTOOL_VERSION"] == "2.3.0"


def test_resolve_deduplicates_packages_across_loadouts(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        resolved = resolver.resolve(["nuke", "myapp"], base_env={})
    names = [p.name for p in resolved.packages]
    assert names.count("pipelinecore") == 1


def test_resolve_raises_on_unknown_loadout(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.is_dir", return_value=True):
        with pytest.raises(KeyError):
            resolver.resolve(["nonexistent"], base_env={})


# -----EnvironmentResolver error handling--------------------------------------


def test_resolve_raises_version_not_specified(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    data = {**ENVIRONMENT_JSON, "versions": {}}
    files = {**all_files, str(env_config_path): data}
    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.is_dir", return_value=True):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            with pytest.raises(VersionNotSpecifiedError):
                resolver.resolve(["nuke"], base_env={})


def test_resolve_raises_package_not_found(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.is_dir", return_value=False):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            with pytest.raises(PackageNotFoundError):
                resolver.resolve(["nuke"], base_env={})
