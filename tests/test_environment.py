"""Unit tests for environment.py."""

import json
import os
import pytest
from pathlib import Path

from envereal.environment import (
    EnvironmentConfig,
    EnvironmentResolver,
    PackageConfig,
    PackageNotFoundError,
    ResolvedEnvironment,
    VersionNotPinnedError,
)

# -----Helpers-----------------------------------------------------------------


def make_package(
    root: Path,
    name: str,
    version: str,
    python_paths: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Write a Package.json into root/name/version/ and return the envereal dir."""
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


def make_show(
    pins: dict[str, str],
    with_packages: dict[str, list[str]] | None = None,
    packages_root: str = "/studio/packages",
    name: str = "TESTSHOW",
) -> EnvironmentConfig:
    return EnvironmentConfig(
        name=name,
        packages_root=packages_root,
        pins=pins,
        with_packages=with_packages or {},
    )


# -----PackageConfig-----------------------------------------------------------


class TestPackageConfig:

    def test_from_file_reads_all_fields(self, tmp_path: Path) -> None:
        pkg_dir = make_package(
            tmp_path,
            "mytool",
            "1.0.0",
            python_paths=["python"],
            env={"MYTOOL_ROOT": "{root}"},
        )
        cfg = PackageConfig.from_file(pkg_dir / "Package.json")

        assert cfg.name == "mytool"
        assert cfg.version == "1.0.0"
        assert cfg.python_paths == ["python"]
        assert cfg.env == {"MYTOOL_ROOT": "{root}"}

    def test_from_file_optional_fields_default_to_empty(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "bare" / "0.1.0"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "Package.json").write_text(
            json.dumps({"name": "bare", "version": "0.1.0"}),
            encoding="utf-8",
        )
        cfg = PackageConfig.from_file(pkg_dir / "Package.json")

        assert cfg.python_paths == []
        assert cfg.env == {}

    def test_from_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PackageConfig.from_file(tmp_path / "nonexistent" / "Package.json")


# -----EnvironmentConfig-------------------------------------------------------


class TestEnvironmentConfig:

    def test_from_file_reads_all_fields(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "env.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "name": "MYSHOW",
                    "packages_root": "/studio/packages",
                    "pins": {"mytool": "2.0.0"},
                    "with_packages": {"mytool": ["pipelinecore"]},
                }
            ),
            encoding="utf-8",
        )

        cfg = EnvironmentConfig.from_file(cfg_path)

        assert cfg.name == "MYSHOW"
        assert cfg.packages_root == "/studio/packages"
        assert cfg.pins == {"mytool": "2.0.0"}
        assert cfg.with_packages == {"mytool": ["pipelinecore"]}

    def test_from_file_optional_fields_default_to_empty(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "env.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "name": "BARE",
                    "packages_root": "/packages",
                }
            ),
            encoding="utf-8",
        )

        cfg = EnvironmentConfig.from_file(cfg_path)

        assert cfg.pins == {}
        assert cfg.with_packages == {}

    def test_from_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            EnvironmentConfig.from_file(tmp_path / "missing.json")


# -----EnvironmentResolver._resolve_load_order---------------------------------


class TestResolveLoadOrder:

    def test_single_package_no_deps(self, tmp_path: Path) -> None:
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        assert resolver._resolve_load_order(["mytool"]) == ["mytool"]

    def test_with_packages_resolved_before_dependent(self, tmp_path: Path) -> None:
        show = make_show(
            pins={"nuke": "15.0.0", "pipelinecore": "1.0.0"},
            with_packages={"nuke": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)
        order = resolver._resolve_load_order(["nuke"])

        assert order.index("pipelinecore") < order.index("nuke")

    def test_shared_dep_deduplicated(self, tmp_path: Path) -> None:
        show = make_show(
            pins={"nuke": "15.0.0", "mytool": "1.0.0", "pipelinecore": "1.0.0"},
            with_packages={"nuke": ["pipelinecore"], "mytool": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)
        order = resolver._resolve_load_order(["nuke", "mytool"])

        assert order.count("pipelinecore") == 1

    def test_explicit_packages_preserved_in_order(self, tmp_path: Path) -> None:
        show = make_show(
            pins={"a": "1.0.0", "b": "1.0.0", "c": "1.0.0"},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)
        order = resolver._resolve_load_order(["a", "b", "c"])

        assert order == ["a", "b", "c"]

    def test_deep_with_packages_chain(self, tmp_path: Path) -> None:
        # c depends on b depends on a -- a should come first
        show = make_show(
            pins={"a": "1.0.0", "b": "1.0.0", "c": "1.0.0"},
            with_packages={"b": ["a"], "c": ["b"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)
        order = resolver._resolve_load_order(["c"])

        assert order == ["a", "b", "c"]


# -----EnvironmentResolver._expand_value---------------------------------------


class TestExpandValue:

    def test_root_token_substituted(self, tmp_path: Path) -> None:
        result = EnvironmentResolver._expand_value("{root}/lib", tmp_path, {})
        assert result == tmp_path.as_posix() + "/lib"

    def test_dollar_var_expanded_from_env(self, tmp_path: Path) -> None:
        env = {"STUDIO_ROOT": "/studio"}
        result = EnvironmentResolver._expand_value("$STUDIO_ROOT/lib", tmp_path, env)
        assert result == "/studio/lib"

    def test_braced_dollar_var_expanded(self, tmp_path: Path) -> None:
        env = {"STUDIO_ROOT": "/studio"}
        result = EnvironmentResolver._expand_value("${STUDIO_ROOT}/lib", tmp_path, env)
        assert result == "/studio/lib"

    def test_unknown_var_left_unexpanded(self, tmp_path: Path) -> None:
        result = EnvironmentResolver._expand_value("$UNKNOWN/lib", tmp_path, {})
        assert result == "$UNKNOWN/lib"

    def test_root_and_var_combined(self, tmp_path: Path) -> None:
        env = {"SUFFIX": "python"}
        result = EnvironmentResolver._expand_value("{root}/$SUFFIX", tmp_path, env)
        assert result == tmp_path.as_posix() + "/python"


# -----EnvironmentResolver.resolve---------------------------------------------


class TestResolve:

    def test_basic_resolve_sets_env_vars(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0", env={"MYTOOL_ROOT": "{root}"})
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        assert "MYTOOL_ROOT" in result.env
        assert result.env["MYTOOL_ROOT"] == (tmp_path / "mytool" / "1.0.0").as_posix()

    def test_python_paths_added_to_pythonpath(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0", python_paths=["python"])
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        expected = str((tmp_path / "mytool" / "1.0.0" / "python").resolve())
        assert expected in result.env["PYTHONPATH"]

    def test_with_packages_auto_included(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.0.0", env={"CORE_ROOT": "{root}"})
        make_package(tmp_path, "mytool", "1.0.0", env={"MYTOOL_ROOT": "{root}"})
        show = make_show(
            pins={"mytool": "1.0.0", "pipelinecore": "1.0.0"},
            with_packages={"mytool": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        assert "CORE_ROOT" in result.env
        assert "MYTOOL_ROOT" in result.env

    def test_cross_package_var_expansion(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.0.0", env={"CORE_ROOT": "{root}"})
        make_package(
            tmp_path, "mytool", "1.0.0", env={"MYTOOL_CONFIG": "$CORE_ROOT/config"}
        )
        show = make_show(
            pins={"mytool": "1.0.0", "pipelinecore": "1.0.0"},
            with_packages={"mytool": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        core_root = (tmp_path / "pipelinecore" / "1.0.0").as_posix()
        assert result.env["MYTOOL_CONFIG"] == core_root + "/config"

    def test_shared_dep_resolved_once(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.0.0", env={"CORE_ROOT": "{root}"})
        make_package(tmp_path, "nuke", "15.0.0", env={"NUKE_ROOT": "{root}"})
        make_package(tmp_path, "mytool", "1.0.0", env={"MYTOOL_ROOT": "{root}"})
        show = make_show(
            pins={"nuke": "15.0.0", "mytool": "1.0.0", "pipelinecore": "1.0.0"},
            with_packages={"nuke": ["pipelinecore"], "mytool": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["nuke", "mytool"], base_env={})

        assert [ctx.name for ctx in result.contexts].count("pipelinecore") == 1

    def test_base_env_inherited(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0")
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={"INHERITED": "yes"})

        assert result.env["INHERITED"] == "yes"

    def test_os_environ_not_mutated(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0", env={"MYTOOL_ROOT": "{root}"})
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)
        before = os.environ.copy()

        resolver.resolve(["mytool"], base_env={})

        assert os.environ == before

    def test_multiple_python_paths_all_present(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0", python_paths=["python", "vendor"])
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        pythonpath = result.env["PYTHONPATH"]
        assert str((tmp_path / "mytool" / "1.0.0" / "python").resolve()) in pythonpath
        assert str((tmp_path / "mytool" / "1.0.0" / "vendor").resolve()) in pythonpath

    def test_contexts_returned_in_load_order(self, tmp_path: Path) -> None:
        make_package(tmp_path, "pipelinecore", "1.0.0")
        make_package(tmp_path, "nuke", "15.0.0")
        show = make_show(
            pins={"nuke": "15.0.0", "pipelinecore": "1.0.0"},
            with_packages={"nuke": ["pipelinecore"]},
            packages_root=str(tmp_path),
        )
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["nuke"], base_env={})

        names = [ctx.name for ctx in result.contexts]
        assert names.index("pipelinecore") < names.index("nuke")

    def test_returns_resolved_environment_type(self, tmp_path: Path) -> None:
        make_package(tmp_path, "mytool", "1.0.0")
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        result = resolver.resolve(["mytool"], base_env={})

        assert isinstance(result, ResolvedEnvironment)
        assert isinstance(result.env, dict)
        assert isinstance(result.contexts, list)

    def test_version_not_pinned_raises(self, tmp_path: Path) -> None:
        show = make_show(pins={}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        with pytest.raises(VersionNotPinnedError):
            resolver.resolve(["unpinned"], base_env={})

    def test_package_not_found_raises(self, tmp_path: Path) -> None:
        show = make_show(pins={"ghost": "9.9.9"}, packages_root=str(tmp_path))
        resolver = EnvironmentResolver(show)

        with pytest.raises(PackageNotFoundError):
            resolver.resolve(["ghost"], base_env={})

    def test_extra_search_paths_used_as_fallback(self, tmp_path: Path) -> None:
        primary = tmp_path / "primary"
        secondary = tmp_path / "secondary"
        primary.mkdir()
        make_package(secondary, "mytool", "1.0.0", env={"MYTOOL_ROOT": "{root}"})
        show = make_show(pins={"mytool": "1.0.0"}, packages_root=str(primary))
        resolver = EnvironmentResolver(show, extra_search_paths=[secondary])

        result = resolver.resolve(["mytool"], base_env={})

        assert "MYTOOL_ROOT" in result.env
