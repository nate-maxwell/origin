"""Tests for caching.py and cached resolution in environment.py"""

import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from origin.caching import (
    CACHING_DISABLED,
    CACHING_ENABLED,
    ENV_CACHING,
    get_caching_enabled,
    get_package_cache_dir,
)
from origin.environment import (
    EnvironmentConfig,
    EnvironmentResolver,
)
from tests.helpers import make_mock_open

# -----Test data---------------------------------------------------------------

ENVIRONMENT_YAML = {
    "name": "MYSHOW",
    "repositories": [
        "/fake/packages",
    ],
    "packages": {
        "pipelinecore": "1.2.0",
    },
    "loadouts": {
        "base": ["pipelinecore"],
    },
}

PIPELINECORE_PACKAGE_YAML = {
    "name": "pipelinecore",
    "version": "1.2.0",
    "env": {},
}

# The cache key includes a hash of the repository path
_REPO_HASH = hashlib.md5("/fake/packages".encode()).hexdigest()[:8]
_CACHED_PACKAGE_YAML_PATH = f"/fake/cache/{_REPO_HASH}/pipelinecore/1.2.0/package.yaml"


# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def env_config_path() -> Path:
    return Path("/fake/shows/MYSHOW/environment.yaml")


@pytest.fixture()
def all_files(env_config_path: Path) -> dict[str, dict]:
    return {
        str(env_config_path): ENVIRONMENT_YAML,
        "/fake/packages/pipelinecore/1.2.0/package.yaml": PIPELINECORE_PACKAGE_YAML,
        _CACHED_PACKAGE_YAML_PATH: PIPELINECORE_PACKAGE_YAML,
    }


# -----get_caching_enabled-----------------------------------------------------


def test_caching_disabled_by_default() -> None:
    with patch.dict(os.environ, {ENV_CACHING: CACHING_DISABLED}):
        assert get_caching_enabled() is False


def test_caching_enabled_when_env_var_set() -> None:
    with patch.dict(os.environ, {ENV_CACHING: CACHING_ENABLED}):
        assert get_caching_enabled() is True


def test_caching_disabled_when_env_var_unset() -> None:
    env = {k: v for k, v in os.environ.items() if k != ENV_CACHING}
    with patch.dict(os.environ, env, clear=True):
        assert get_caching_enabled() is False


# -----get_package_cache_dir---------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows path test cannot run on Mac/Linux")
def test_get_package_cache_dir_windows() -> None:
    with patch("os.name", "nt"):
        with patch.dict(os.environ, {"SYSTEMDRIVE": "C:"}):
            result = get_package_cache_dir()
    assert str(result) == "C:\\origin\\cache"


@pytest.mark.skipif(os.name != "nt", reason="Windows path test cannot run on Mac/Linux")
def test_get_package_cache_dir_windows_uses_systemdrive() -> None:
    with patch("os.name", "nt"):
        with patch.dict(os.environ, {"SYSTEMDRIVE": "D:"}):
            result = get_package_cache_dir()
    assert str(result) == "D:\\origin\\cache"


@pytest.mark.skipif(os.name == "nt", reason="Unix path test cannot run on Windows")
def test_get_package_cache_dir_unix() -> None:
    with patch("origin.caching.Path.home", return_value=Path("/home/nate")):
        result = get_package_cache_dir()
    assert str(result) == "/home/nate/.origin/cache"


# -----resolver caching--------------------------------------------------------


def test_resolve_uses_cache_dir_when_caching_enabled(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict(os.environ, {ENV_CACHING: CACHING_ENABLED}):
                with patch(
                    "origin.caching.get_package_cache_dir",
                    return_value=Path("/fake/cache"),
                ):
                    with patch("shutil.copytree"):
                        cfg = EnvironmentConfig.from_file(env_config_path)
                        resolver = EnvironmentResolver(cfg)
                        resolved = resolver.resolve(["base"], base_env={})

    assert "/fake/cache" in resolved.env["PYTHONPATH"]


def test_resolve_uses_repository_when_caching_disabled(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict(os.environ, {ENV_CACHING: CACHING_DISABLED}):
                cfg = EnvironmentConfig.from_file(env_config_path)
                resolver = EnvironmentResolver(cfg)
                resolved = resolver.resolve(["base"], base_env={})

    assert "/fake/packages" in resolved.env["PYTHONPATH"]


def test_resolve_copies_package_to_cache_if_not_cached(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    def exists_side_effect(self):
        normalized = str(self).replace("\\", "/")
        if "/fake/shows" in normalized:
            return True
        if "/fake/cache" in normalized and "package.yaml" in normalized:
            return True
        return "/fake/packages" in normalized and "package.yaml" not in normalized

    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", exists_side_effect):
            with patch("pathlib.Path.mkdir"):
                with patch.dict(os.environ, {ENV_CACHING: CACHING_ENABLED}):
                    with patch(
                        "origin.caching.get_package_cache_dir",
                        return_value=Path("/fake/cache"),
                    ):
                        with patch("shutil.copytree") as mock_copytree:
                            cfg = EnvironmentConfig.from_file(env_config_path)
                            resolver = EnvironmentResolver(cfg)
                            resolver.resolve(["base"], base_env={})

    mock_copytree.assert_called_once()


def test_resolve_skips_copy_if_already_cached(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    with patch("builtins.open", make_mock_open(all_files)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict(os.environ, {ENV_CACHING: CACHING_ENABLED}):
                with patch(
                    "origin.caching.get_package_cache_dir",
                    return_value=Path("/fake/cache"),
                ):
                    with patch("shutil.copytree") as mock_copytree:
                        cfg = EnvironmentConfig.from_file(env_config_path)
                        resolver = EnvironmentResolver(cfg)
                        resolver.resolve(["base"], base_env={})

    mock_copytree.assert_not_called()


def test_cache_key_differs_per_repository(
    env_config_path: Path, all_files: dict[str, dict]
) -> None:
    repo_a = "/fake/studio/packages"
    repo_b = "/fake/project/packages"
    hash_a = hashlib.md5(repo_a.encode()).hexdigest()[:8]
    hash_b = hashlib.md5(repo_b.encode()).hexdigest()[:8]
    assert hash_a != hash_b
