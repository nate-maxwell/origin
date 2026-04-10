"""
# Environment Resolver

Responsible for resolving packages and building environments.
Unlike other environment abstraction frameworks, Origin is very simplistic and
is meant for use by very small teams.
"""

import os
import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Optional

# -----Exceptions--------------------------------------------------------------


class PackageNotFoundError(Exception):
    """Raised when a package directory or config cannot be located on disk."""


class VersionNotSpecifiedError(Exception):
    """
    Raised when a required package has no specified version in the Environment
    config.
    """


# -----Package-----------------------------------------------------------------


@dataclass
class Package(object):
    """
    A fully resolved package.

    Produced by the resolver after reading a PackageConfig from disk and
    expanding all token references in its env values. Represents the package's
    identity, its location on disk, and its concrete contribution to the
    environment being built.

    Attributes:
        name (str): The package name.
        version (str): The version string, as specified in the EnvironmentConfig.
        root (Path): Absolute path to the versioned package directory on disk.
        env (dict[str, str]): Environment variables this package contributes,
            with all {root} and $VAR tokens fully expanded.
    """

    name: str
    version: str
    root: Path
    env: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Package({self.name!r}, version={self.version!r})"


# -----Config dataclasses------------------------------------------------------


@dataclass
class PackageConfig(object):
    """
    Raw contents of a Package.json file, as read from disk.

    Represents the package's own declaration of what it needs: which
    subdirectories to add to PYTHONPATH, and which environment variables to
    set. Values in env are raw strings and may contain {root} or $VAR tokens
    that have not yet been expanded.

    Attributes:
        name (str): Package name.
        version (str): Package version.
        env (dict[str, str]): Raw environment variable declarations. Values
            may use {root} to reference the package root directory, and
            $VAR or ${VAR} to reference variables set by previously resolved
            packages.
    """

    name: str
    version: str
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "PackageConfig":
        """
        Read and parse a Package.json file from disk.

        Args:
            path (Path): Path to the Package.json file.
        Returns:
            PackageConfig: The parsed config with raw, unexpanded values.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        _name = str(data["name"])
        _version = data["version"]
        _env = data.get("env", {})
        _env[f"{_name.upper()}_VERSION"] = _version

        return cls(
            name=_name,
            version=_version,
            env=_env,
        )


@dataclass
class EnvironmentConfig(object):
    """
    Parsed contents of an Environment.json file.

    Defines the package versions available to a program and which additional
    packages the resolver should include when a given package is requested.

    Attributes:
        name (str): The name of the show or environment this config represents.
        packages_root (str): Root directory containing all versioned package
            folders, structured as packages_root/name/version/.
        versions (dict[str, str]): Maps each package name to its version string.
        loadouts (dict[str, list[str]]): Maps a package name to a list of
            additional package names the resolver should include when that
            package is requested.
    """

    name: str
    packages_root: str
    versions: dict[str, str] = field(default_factory=dict)
    loadouts: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "EnvironmentConfig":
        """
        Read and parse an Environment.json file from disk.

        Args:
            path (Path): Path to the Environment.json file.
        Returns:
            EnvironmentConfig: The parsed config.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            packages_root=data["packages_root"],
            versions=data.get("versions", {}),
            loadouts=data.get("loadouts", {}),
        )


# -----Environment Resolver----------------------------------------------------


@dataclass
class ResolvedEnvironment(object):
    """
    The result of a single EnvironmentResolver.resolve() call.

    Attributes:
        env (dict[str, str]): The fully built environment dict, ready to pass
            to subprocess.Popen(env=...).
        packages (list[Package]): One Package per resolved package, in the
            order they were resolved.
    """

    env: dict[str, str]
    packages: list[Package]


class EnvironmentResolver(object):

    def __init__(self, cfg: EnvironmentConfig) -> None:
        self._cfg = cfg
        self._env: dict[str, str] = {}

    def resolve(
        self, loadouts: list[str], base_env: Optional[dict[str, str]] = None
    ) -> ResolvedEnvironment:
        env: dict[str, str] = base_env if base_env is not None else dict(os.environ)
        packages: list[Package] = []
        seen: set[str] = set()

        for loadout in loadouts:
            packages_to_resolve = self._cfg.loadouts[loadout]
            for name in packages_to_resolve:
                if name in seen:
                    continue
                seen.add(name)

                pkg = self._resolve_package(name, env)
                packages.append(pkg)

                # Merge this package's root into PYTHONPATH in the current
                # env dict.
                existing = env.get("PYTHONPATH", "")
                new_paths = os.pathsep.join([pkg.root.as_posix()])
                env["PYTHONPATH"] = (
                    os.pathsep.join([new_paths, existing]) if existing else new_paths
                )

                # Merge env vars into the accumulating env so later packages can
                # expand $VAR references against them.
                env.update(pkg.env)

        return ResolvedEnvironment(env=env, packages=packages)

    def _resolve_version(self, name: str) -> str:
        """
        Look up the version for a package in the environment config.

        Args:
            name (str): Package name.
        Returns:
            str: Package version string.
        Raises:
            VersionNotSpecifiedError: If the package has no version in the environment config.
        """
        try:
            return self._cfg.versions[name]
        except KeyError:
            raise VersionNotSpecifiedError(
                f"Package '{name}' has no version in environment config '{self._cfg.name}'."
            )

    def _find_package_dir(self, name: str, version: str) -> Path:
        """
        Locate the versioned package directory on disk.

        Searches show.packages_root first, then any extra_search_paths.

        Args:
            name (str): Package name.
            version (str): Version string.
        Returns:
            Path: Absolute path to the package version directory.
        Raises:
            PackageNotFoundError: If no matching directory is found.
        """
        root = Path(self._cfg.packages_root)
        candidate = root / name / version
        if candidate.is_dir():
            return candidate

        raise PackageNotFoundError(
            f"Package '{name}' version '{version}' not found. Searched: {root.as_posix()}"
        )

    def _resolve_package(self, name: str, env: dict[str, str]) -> Package:
        version = self._resolve_version(name)
        pkg_dir = self._find_package_dir(name, version)
        pkg_config = PackageConfig.from_file(pkg_dir / "Package.json")

        return Package(
            name=name,
            version=version,
            root=pkg_dir,
            env=pkg_config.env,
        )
