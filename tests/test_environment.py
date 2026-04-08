"""Unit tests for environment.py."""

import json
import os
import pytest
from pathlib import Path

from envereal.environment import (
    EnvironmentConfig,
    EnvironmentResolver,
    Package,
    PackageConfig,
    PackageNotFoundError,
    ResolvedEnvironment,
    VersionNotSpecifiedError,
)

# -----Helpers-----------------------------------------------------------------


def make_package(
    root: Path,
    name: str,
    version: str,
    python_paths: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Write a Package.json into root/name/version/ and return the package dir."""
    pkg_dir = root / name / version
    pkg_dir.mkdir(parents=True, exist_ok=True)
    for rel in python_paths or []:
        (pkg_dir / rel).mkdir(parents=True, exist_ok=True)
    (pkg_dir / "Package.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": version,
                "python_paths": python_paths or [],
                "env": env or {},
            }
        ),
        encoding="utf-8",
    )
    return pkg_dir


def make_config(
    root: Path,
    versions: dict[str, str],
    loadouts: dict[str, list[str]] | None = None,
    name: str = "TESTSHOW",
) -> EnvironmentConfig:
    return EnvironmentConfig(
        name=name,
        packages_root=str(root),
        versions=versions,
        loadouts=loadouts or {},
    )


# -----PackageConfig-----------------------------------------------------------


class TestPackageConfig:

    def test_from_file_reads_all_fields(self, tmp_path: Path) -> None:
        make_package(
            tmp_path,
            "pipelinecore",
            "1.2.0",
            python_paths=["python"],
            env={"CORE_ROOT": "{root}"},
        )
        cfg = PackageConfig.from_file(
            tmp_path / "pipelinecore" / "1.2.0" / "Package.json"
        )

        assert cfg.name == "pipelinecore"
        assert cfg.version == "1.2.0"
        assert cfg.python_paths == ["python"]
        assert cfg.env == {"CORE_ROOT": "{root}"}

    def test_from_file_optional_fields_default_to_empty(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pipelinecore" / "1.2.0"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "Package.json").write_text(
            json.dumps({"name": "pipelinecore", "version": "1.2.0"}),
            encoding="utf-8",
        )
        cfg = PackageConfig.from_file(pkg_dir / "Package.json")

        assert cfg.python_paths == []
        assert cfg.env == {}

    def test_from_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PackageConfig.from_file(
                tmp_path / "pipelinecore" / "1.2.0" / "Package.json"
            )


# -----EnvironmentConfig-------------------------------------------------------


class TestEnvironmentConfig:

    def test_from_file_reads_all_fields(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "Environment.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "name": "MYSHOW",
                    "packages_root": "/studio/packages",
                    "versions": {
                        "pipelinecore": "1.2.0",
                        "colour": "0.4.2",
                        "service": "15.0.1",
                        "mytool": "2.3.0",
                    },
                    "loadouts": {
                        "nuke": ["pipelinecore", "colour"],
                        "mytool": ["pipelinecore"],
                    },
                }
            ),
            encoding="utf-8",
        )

        cfg = EnvironmentConfig.from_file(cfg_path)

        assert cfg.name == "MYSHOW"
        assert cfg.packages_root == "/studio/packages"
        assert cfg.versions == {
            "pipelinecore": "1.2.0",
            "colour": "0.4.2",
            "service": "15.0.1",
            "mytool": "2.3.0",
        }
        assert cfg.loadouts == {
            "nuke": ["pipelinecore", "colour"],
            "mytool": ["pipelinecore"],
        }

    def test_from_file_optional_fields_default_to_empty(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "Environment.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "name": "MYSHOW",
                    "packages_root": "/studio/packages",
                }
            ),
            encoding="utf-8",
        )

        cfg = EnvironmentConfig.from_file(cfg_path)

        assert cfg.versions == {}
        assert cfg.loadouts == {}

    def test_from_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            EnvironmentConfig.from_file(tmp_path / "Environment.json")


# -----EnvironmentResolver.resolve---------------------------------------------


class TestResolve:

    def test_single_loadout_resolves_its_packages(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0", env={"CORE_ROOT": "{root}"})
        make_package(tmp_path, "colour", "0.4.2", env={"COLOUR_ROOT": "{root}"})
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0", "colour": "0.4.2"},
            loadouts={"nuke": ["pipelinecore", "colour"]},
        )
        result = EnvironmentResolver(config).resolve(["nuke"], base_env={})

        assert "CORE_ROOT" in result.env
        assert "COLOUR_ROOT" in result.env
        assert [p.name for p in result.packages] == ["pipelinecore", "colour"]

    def test_multiple_loadouts_combined(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0")
        make_package(tmp_path, "colour", "0.4.2")
        make_package(tmp_path, "mytool", "2.3.0")
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0", "colour": "0.4.2", "mytool": "2.3.0"},
            loadouts={
                "nuke": ["pipelinecore", "colour"],
                "mytool": ["pipelinecore", "mytool"],
            },
        )
        result = EnvironmentResolver(config).resolve(["nuke", "mytool"], base_env={})

        names = [p.name for p in result.packages]
        assert "pipelinecore" in names
        assert "colour" in names
        assert "mytool" in names

    def test_package_shared_across_loadouts_resolved_once(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0")
        make_package(tmp_path, "colour", "0.4.2")
        make_package(tmp_path, "mytool", "2.3.0")
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0", "colour": "0.4.2", "mytool": "2.3.0"},
            loadouts={
                "nuke": ["pipelinecore", "colour"],
                "mytool": ["pipelinecore", "mytool"],
            },
        )
        result = EnvironmentResolver(config).resolve(["nuke", "mytool"], base_env={})

        assert [p.name for p in result.packages].count("pipelinecore") == 1

    def test_pythonpath_not_duplicated_across_loadouts(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0", python_paths=["python"])
        make_package(tmp_path, "colour", "0.4.2")
        make_package(tmp_path, "mytool", "2.3.0")
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0", "colour": "0.4.2", "mytool": "2.3.0"},
            loadouts={
                "nuke": ["pipelinecore", "colour"],
                "mytool": ["pipelinecore", "mytool"],
            },
        )
        result = EnvironmentResolver(config).resolve(["nuke", "mytool"], base_env={})

        core_path = str((tmp_path / "pipelinecore" / "1.2.0" / "python").resolve())
        paths = result.env["PYTHONPATH"].split(os.pathsep)
        assert paths.count(core_path) == 1

    def test_root_token_expanded_in_env(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0", env={"CORE_ROOT": "{root}"})
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0"},
            loadouts={"nuke": ["pipelinecore"]},
        )
        result = EnvironmentResolver(config).resolve(["nuke"], base_env={})

        assert (
            result.env["CORE_ROOT"] == (tmp_path / "pipelinecore" / "1.2.0").as_posix()
        )

    def test_var_token_expanded_against_accumulated_env(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0", env={"CORE_ROOT": "{root}"})
        make_package(
            tmp_path, "colour", "0.4.2", env={"COLOUR_CONFIG": "$CORE_ROOT/config"}
        )
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0", "colour": "0.4.2"},
            loadouts={"nuke": ["pipelinecore", "colour"]},
        )
        result = EnvironmentResolver(config).resolve(["nuke"], base_env={})

        core_root = (tmp_path / "pipelinecore" / "1.2.0").as_posix()
        assert result.env["COLOUR_CONFIG"] == core_root + "/config"

    def test_base_env_inherited(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0")
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0"},
            loadouts={"nuke": ["pipelinecore"]},
        )
        result = EnvironmentResolver(config).resolve(
            ["nuke"], base_env={"STUDIO": "myshow"}
        )

        assert result.env["STUDIO"] == "myshow"

    def test_os_environ_not_mutated(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0", env={"CORE_ROOT": "{root}"})
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0"},
            loadouts={"nuke": ["pipelinecore"]},
        )
        before = os.environ.copy()

        EnvironmentResolver(config).resolve(["nuke"], base_env={})

        assert os.environ == before

    def test_returns_resolved_environment_type(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.2.0")
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0"},
            loadouts={"nuke": ["pipelinecore"]},
        )
        result = EnvironmentResolver(config).resolve(["nuke"], base_env={})

        assert isinstance(result, ResolvedEnvironment)
        assert isinstance(result.env, dict)
        assert isinstance(result.packages, list)
        assert all(isinstance(p, Package) for p in result.packages)

    def test_version_not_specified_raises(self, tmp_path: Path) -> None:
        config = make_config(
            tmp_path,
            versions={},
            loadouts={"nuke": ["pipelinecore"]},
        )
        with pytest.raises(VersionNotSpecifiedError):
            EnvironmentResolver(config).resolve(["nuke"], base_env={})

    def test_package_dir_not_found_raises(self, tmp_path: Path) -> None:
        config = make_config(
            tmp_path,
            versions={"pipelinecore": "1.2.0"},
            loadouts={"nuke": ["pipelinecore"]},
        )
        with pytest.raises(PackageNotFoundError):
            EnvironmentResolver(config).resolve(["nuke"], base_env={})
