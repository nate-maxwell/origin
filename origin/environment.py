"""
# Environment Resolver

Responsible for resolving packages and building environments.
Unlike other environment abstraction frameworks, Origin is very simplistic and
is meant for use by very small teams.
"""

import hashlib
import os
import shutil
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Optional
from typing import Union

import origin.caching
import origin.config

# -----Exceptions--------------------------------------------------------------


class PackageNotFoundError(Exception):
    """Raised when a package directory or config could not be located."""


class PackageConfigError(Exception):
    """Raised when a package directory or config cannot be loaded from disk."""


class EnvironmentConfigError(Exception):
    """
    Raised when an environment directory or config cannot be located or loaded
    from disk.
    """


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
    build_command: Optional[str] = None

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike]) -> "PackageConfig":
        """
        Read and parse a Package.json file from disk.

        Args:
            path (Union[str, os.PathLike]): Path to the Package.json file.
        Returns:
            PackageConfig: The parsed config with raw, unexpanded values.
        Raises:
            PackageConfigError: If the package.yaml file could not be found or
                loaded.
        """
        data = origin.config.import_data_from_yaml(path)
        if data is None:
            msg = f"Could not import package data for {str(path)}!"
            raise PackageConfigError(msg)

        _name = str(data["name"])

        _version = data["version"]
        _version_parts = _version.split(".")
        _major = _version_parts[0] if len(_version_parts) > 0 else "x"
        _minor = _version_parts[1] if len(_version_parts) > 1 else "x"
        _patch = _version_parts[2] if len(_version_parts) > 2 else "x"

        _env = data.get("env", {})
        _env[f"ORIGIN_{_name.upper()}_VERSION"] = _version
        _env[f"ORIGIN_{_name.upper()}_MAJOR_VERSION"] = _major
        _env[f"ORIGIN_{_name.upper()}_MINOR_VERSION"] = _minor
        _env[f"ORIGIN_{_name.upper()}_PATCH_VERSION"] = _patch

        return cls(
            name=_name,
            version=_version,
            env=_env,
            build_command=data.get("build_command"),
        )


@dataclass
class EnvironmentConfig(object):
    """
    Parsed contents of an Environment.json file.

    Defines the package versions available to a program and which additional
    packages the resolver should include when a given package is requested.

    Attributes:
        name (str): The name of the show or environment this config represents.
        repositories (list[str]): Root directory containing all versioned package
            folders, structured as packages_root/name/version/.
        packages (dict[str, str]): Maps each package name to its version string.
        loadouts (dict[str, list[str]]): Maps a package name to a list of
            additional package names the resolver should include when that
            package is requested.
    """

    name: str
    repositories: list[str] = field(default_factory=list)
    packages: dict[str, str] = field(default_factory=dict)
    loadouts: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike]) -> "EnvironmentConfig":
        """
        Read and parse an Environment.json file from disk.

        Args:
            path (Union[str, os.PathLike]): Path to the Environment.json file.
        Returns:
            EnvironmentConfig: The parsed config.
        Raises:
            EnvironmentConfigError: If the environment.yaml file could not be
                found or loaded.
        """
        data = origin.config.import_data_from_yaml(path)
        if data is None:
            msg = f"Could not import environment data for {str(path)}!"
            raise EnvironmentConfigError(msg)

        return cls(
            name=data["name"],
            repositories=data["repositories"],
            packages=data.get("packages", {}),
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
        """
        Resolve one or more loadouts into a fully built environment.

        Iterates over each loadout in order, resolving its packages and
        accumulating their environment contributions. Each package's root
        directory is prepended to PYTHONPATH, and its env vars are merged
        into the environment. Packages that appear in multiple loadouts are
        resolved only once.

        Args:
            loadouts (list[str]): One or more loadout keys defined in the
                EnvironmentConfig. Packages are resolved in the order they
                appear in each loadout.
            base_env (Optional[dict[str, str]]): Environment to build on top of.
                When omitted, the current process environment is used as the base.
        Returns:
            ResolvedEnvironment: The fully built environment and the list of
                resolved packages in resolution order.
        Raises:
            KeyError: If a loadout key is not defined in the EnvironmentConfig.
            VersionNotSpecifiedError: If a package in the loadout has no version
                declared in the EnvironmentConfig.
            PackageNotFoundError: If a package directory cannot be found on disk.
        """
        env: dict[str, str] = base_env if base_env is not None else dict(os.environ)
        packages: list[Package] = []
        seen: set[str] = set()

        package_names = self._expand_loadouts(loadouts)

        for name in package_names:
            if name in seen:
                continue
            seen.add(name)

            pkg = self._resolve_package(name)
            packages.append(pkg)

            existing = env.get("PYTHONPATH", "")
            new_paths = os.pathsep.join([pkg.root.as_posix()])
            env["PYTHONPATH"] = (
                os.pathsep.join([new_paths, existing]) if existing else new_paths
            )

            env.update(pkg.env)

        return ResolvedEnvironment(env=env, packages=packages)

    def _expand_loadouts(
        self, loadouts: list[str], seen_loadouts: Optional[set[str]] = None
    ) -> list[str]:
        """
        Expand a list of loadout names into an ordered, deduplicated list of
        package names, recursively resolving any loadouts that reference other
        loadouts.

        Args:
            loadouts (list[str]): Loadout keys to expand.
            seen_loadouts (Optional[set[str]]): Tracks visited loadouts to
                detect circular references.
        Returns:
            list[str]: Ordered, deduplicated list of package names.
        Raises:
            KeyError: If a loadout key is not defined in the EnvironmentConfig.
            RecursionError: If a circular loadout reference is detected.
        """
        if seen_loadouts is None:
            seen_loadouts = set()

        package_names: list[str] = []
        seen_packages: set[str] = set()

        for loadout in loadouts:
            if loadout in seen_loadouts:
                err_msg = f"Circular loadout reference detected: '{loadout}'"
                raise RecursionError(err_msg)
            seen_loadouts.add(loadout)

            for entry in self._cfg.loadouts[loadout]:
                if entry in self._cfg.loadouts:  # Entry is another loadout — recurse
                    nested = self._expand_loadouts([entry], seen_loadouts.copy())
                    for name in nested:
                        if name in seen_packages:
                            continue
                        seen_packages.add(name)
                        package_names.append(name)

                else:  # Entry is a package name
                    if entry in seen_packages:
                        continue
                    seen_packages.add(entry)
                    package_names.append(entry)

            seen_loadouts.discard(loadout)

        return package_names

    def _find_uncached_package_dir(self, name: str, version: str) -> Path:
        """
        Locate the versioned package directory on disk, searching repositories
        in order. The first repository containing the package is used.

        Args:
            name (str): Package name.
            version (str): Version string.
        Returns:
            Path: Absolute path to the package version directory.
        Raises:
            PackageNotFoundError: If no matching directory is found.
        """
        searched = []
        for repository in self._cfg.repositories:
            candidate = Path(repository) / name / version
            if candidate.exists():
                return candidate
            searched.append(repository)

        err_msg = f"Package '{name}' version '{version}' not found. Searched: "
        err_msg += ", ".join(searched)
        raise PackageConfigError(err_msg)

    def _cache_and_find_package_dir(self, name: str, version: str) -> Path:
        """
        Locate a package directory, copying it to the local cache if not already
        cached. The cache key is derived from the source repository path, package
        name, and version, ensuring that the same package version from different
        repositories is cached separately.

        Args:
            name (str): Package name.
            version (str): Version string.
        Returns:
            Path: Absolute path to the cached package version directory.
        Raises:
            PackageNotFoundError: If the package cannot be found in any repository.
        """

        uncached_pkg_dir = self._find_uncached_package_dir(name, version)

        # Hash the source repository path to create a stable, unique cache key.
        repo_path = Path(uncached_pkg_dir.parent.parent).as_posix()
        repo_hash = hashlib.md5(repo_path.encode()).hexdigest()[:8]

        root = origin.caching.get_package_cache_dir()
        candidate = root / repo_hash / name / version

        if candidate.exists():
            return candidate

        candidate.mkdir(parents=True, exist_ok=True)
        shutil.copytree(uncached_pkg_dir, candidate, dirs_exist_ok=True)

        return candidate

    def _resolve_package(self, name: str) -> Package:
        """
        Resolve a package by name into a fully populated Package instance.

        Looks up the version from the environment config, locates the package
        directory on disk (using the cache if caching is enabled), reads the
        Package.json, and returns a Package with all version environment variables
        injected.

        Args:
            name (str): Package name.
        Returns:
            Package: The fully resolved package.
        Raises:
            VersionNotSpecifiedError: If the package has no version declared in
                the environment config.
            PackageNotFoundError: If the versioned package directory cannot be
                found in any repository.
        """

        try:
            version = self._cfg.packages[name]
        except KeyError:
            err_msg = f"Package '{name}' has no version in environment config '{self._cfg.name}'."
            raise VersionNotSpecifiedError(err_msg)

        if origin.caching.get_caching_enabled():
            pkg_dir = self._cache_and_find_package_dir(name, version)
        else:
            pkg_dir = self._find_uncached_package_dir(name, version)

        pkg_config = PackageConfig.from_file(pkg_dir / "package.yaml")

        return Package(
            name=name,
            version=version,
            root=pkg_dir,
            env=pkg_config.env,
        )
