"""Tests for environment.py"""

from pathlib import Path
from typing import Any
from typing import Generator
from unittest.mock import patch

import pytest

from origin.environment import (
    EnvironmentConfig,
    EnvironmentResolver,
    PackageConfig,
    PackageNotFoundError,
    VersionNotSpecifiedError,
)
from tests.helpers import make_mock_open

# -----Test data---------------------------------------------------------------

ENVIRONMENT_JSON = {
    "name": "MYSHOW",
    "repositories": [
        "/fake/project/packages",
        "/fake/studio/packages",
    ],
    "packages": {
        "pipelinecore": "1.2.0",
        "mytool": "2.3.0",
    },
    "loadouts": {
        "base": ["pipelinecore"],
        "nuke": ["base", "mytool"],
    },
}

PIPELINECORE_PACKAGE_JSON = {
    "name": "pipelinecore",
    "version": "1.2.0",
    "env": {
        "PIPELINECORE_ROOT": "/fake/studio/packages/pipelinecore/1.2.0",
    },
}

MYTOOL_PACKAGE_JSON = {
    "name": "mytool",
    "version": "2.3.0",
    "env": {},
}


# -----Helpers-----------------------------------------------------------------


def make_exists_in(*roots: str):
    """
    Return a side effect function that returns True only for paths under
    the given roots.

    Args:
        roots (str): Root path prefixes to match against.
    Returns:
        Callable: A side effect function for patching pathlib.Path.exists.
    """

    def _exists(self) -> bool:
        normalized = str(self).replace("\\", "/")
        return any(root in normalized for root in roots)

    return _exists


# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def env_config_path() -> Path:
    return Path("/fake/shows/MYSHOW/Environment.json")


@pytest.fixture()
def all_files(env_config_path: Path) -> dict[str, dict]:
    return {
        str(env_config_path): ENVIRONMENT_JSON,
        "/fake/project/packages/pipelinecore/1.2.0/Package.json": PIPELINECORE_PACKAGE_JSON,
        "/fake/project/packages/mytool/2.3.0/Package.json": MYTOOL_PACKAGE_JSON,
        "/fake/studio/packages/pipelinecore/1.2.0/Package.json": PIPELINECORE_PACKAGE_JSON,
        "/fake/studio/packages/mytool/2.3.0/Package.json": MYTOOL_PACKAGE_JSON,
    }


@pytest.fixture()
def resolver(
    env_config_path: Path, all_files: dict[str, dict]
) -> Generator[EnvironmentResolver, Any, None]:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            cfg = EnvironmentConfig.from_file(env_config_path)
            yield EnvironmentResolver(cfg)


# -----PackageConfig.from_file-------------------------------------------------


def test_package_config_parses_name(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.name == "mytool"


def test_package_config_parses_version(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.version == "2.3.0"


def test_package_config_injects_version_env_var(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["ORIGIN_MYTOOL_VERSION"] == "2.3.0"


def test_package_config_injects_major_version(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["ORIGIN_MYTOOL_MAJOR_VERSION"] == "2"


def test_package_config_injects_minor_version(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["ORIGIN_MYTOOL_MINOR_VERSION"] == "3"


def test_package_config_injects_patch_version(all_files: dict[str, dict]) -> None:
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["ORIGIN_MYTOOL_PATCH_VERSION"] == "0"


def test_package_config_partial_version_defaults_to_x(
    all_files: dict[str, dict],
) -> None:
    files = {
        **all_files,
        "/fake/studio/packages/mytool/2.3.0/Package.json": {
            "name": "mytool",
            "version": "2",
            "env": {},
        },
    }
    path = Path("/fake/studio/packages/mytool/2.3.0/Package.json")
    with patch("builtins.open", make_mock_open(files)):
        cfg = PackageConfig.from_file(path)
    assert cfg.env["ORIGIN_MYTOOL_MINOR_VERSION"] == "x"
    assert cfg.env["ORIGIN_MYTOOL_PATCH_VERSION"] == "x"


# -----EnvironmentConfig.from_file---------------------------------------------


def test_environment_config_parses_name(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.name == "MYSHOW"


def test_environment_config_parses_repositories(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.repositories == ["/fake/project/packages", "/fake/studio/packages"]


def test_environment_config_parses_packages(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.packages["mytool"] == "2.3.0"
    assert cfg.packages["pipelinecore"] == "1.2.0"


def test_environment_config_parses_loadouts(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
    assert cfg.loadouts["nuke"] == ["base", "mytool"]


# -----EnvironmentResolver.resolve---------------------------------------------


def test_resolve_returns_correct_package_names(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert [p.name for p in resolved.packages] == ["pipelinecore", "mytool"]


def test_resolve_returns_correct_package_versions(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    versions = {p.name: p.version for p in resolved.packages}
    assert versions["pipelinecore"] == "1.2.0"
    assert versions["mytool"] == "2.3.0"


def test_resolve_sets_pythonpath(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert "PYTHONPATH" in resolved.env


def test_resolve_pythonpath_contains_package_roots(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert "pipelinecore/1.2.0" in resolved.env["PYTHONPATH"]
    assert "mytool/2.3.0" in resolved.env["PYTHONPATH"]


def test_resolve_sets_version_env_var(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["nuke"], base_env={})
    assert resolved.env["ORIGIN_MYTOOL_VERSION"] == "2.3.0"


def test_resolve_deduplicates_packages_across_loadouts(
    resolver: EnvironmentResolver,
) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        resolved = resolver.resolve(["base", "nuke"], base_env={})
    names = [p.name for p in resolved.packages]
    assert names.count("pipelinecore") == 1


def test_resolve_raises_on_unknown_loadout(resolver: EnvironmentResolver) -> None:
    with patch("pathlib.Path.exists", return_value=True):
        with pytest.raises(KeyError):
            resolver.resolve(["nonexistent"], base_env={})


def test_resolve_uses_project_repository_before_studio(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch(
            "pathlib.Path.exists",
            make_exists_in("/fake/project/packages"),
        ):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            resolved = resolver.resolve(["nuke"], base_env={})

    mytool_pkg = next(p for p in resolved.packages if p.name == "mytool")
    assert "/fake/project/packages" in mytool_pkg.root.as_posix()


def test_resolve_falls_back_to_studio_repository(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch(
            "pathlib.Path.exists",
            make_exists_in("/fake/studio/packages"),
        ):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            resolved = resolver.resolve(["base"], base_env={})

    pipelinecore_pkg = next(p for p in resolved.packages if p.name == "pipelinecore")
    assert "/fake/studio/packages" in pipelinecore_pkg.root.as_posix()


# -----EnvironmentResolver._expand_loadouts------------------------------------


def test_expand_loadouts_resolves_nested_loadout(
    resolver: EnvironmentResolver,
) -> None:
    result = resolver._expand_loadouts(["nuke"])
    assert result == ["pipelinecore", "mytool"]


def test_expand_loadouts_deduplicates_packages(
    resolver: EnvironmentResolver,
) -> None:
    result = resolver._expand_loadouts(["base", "nuke"])
    assert result.count("pipelinecore") == 1


def test_expand_loadouts_raises_on_circular_reference(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    circular_env = {
        **ENVIRONMENT_JSON,
        "loadouts": {
            "a": ["b"],
            "b": ["a"],
        },
    }
    files = {**all_files, str(env_config_path): circular_env}
    with patch("builtins.open", make_mock_open(files)):
        cfg = EnvironmentConfig.from_file(env_config_path)
        resolver = EnvironmentResolver(cfg)
        with pytest.raises(RecursionError):
            resolver._expand_loadouts(["a"])


# -----EnvironmentResolver error handling--------------------------------------


def test_resolve_raises_version_not_specified(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    data = {**ENVIRONMENT_JSON, "packages": {}}
    files = {**all_files, str(env_config_path): data}
    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.exists", return_value=True):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            with pytest.raises(VersionNotSpecifiedError):
                resolver.resolve(["base"], base_env={})


def test_resolve_raises_package_not_found(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=False):
            cfg = EnvironmentConfig.from_file(env_config_path)
            resolver = EnvironmentResolver(cfg)
            with pytest.raises(PackageNotFoundError):
                resolver.resolve(["base"], base_env={})
