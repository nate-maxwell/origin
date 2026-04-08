"""
# Environment Resolver

Responsible for package resolution and environment building.

Packages are resolved first as PackageConfig objects that represent the raw
config data and then are converted to Context objects, a resolved package
representation including all the paths necessary to run the package.
"""

import json
import os
import re
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


# -----Context-----------------------------------------------------------------


@dataclass
class Context(object):
    """
    A resolved package: its identity, disk location, and environment contribution.

    Attributes:
        name (str): The package name.
        version (str): The resolved version string.
        root (Path): Absolute path to the package directory on disk.
        python_paths (list[str]): Absolute paths contributed to PYTHONPATH.
        env (dict[str, str]): Environment variables contributed by this package,
            after all token expansion has been applied.
    """

    name: str
    version: str
    root: Path
    python_paths: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Context({self.name!r}, version={self.version!r})"


# -----Config dataclasses------------------------------------------------------


@dataclass
class PackageConfig(object):
    """
    Parsed contents of a Package.json file.

    Attributes:
        name (str): Package name.
        version (str): Package version.
        python_paths (list[str]): Paths relative to the package root to add to
            PYTHONPATH.
        env (dict[str, str]): Environment variables to contribute. Values may use
            {root} (expands to the package root) and $VAR / ${VAR} (expands
            against the environment being built, so earlier packages' vars are
            available to later ones).
    """

    name: str
    version: str
    python_paths: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "PackageConfig":
        """
        Load and parse a Package.json file.

        Args:
            path (Path): Path to the Package.json file.
        Returns:
            PackageConfig: The parsed config.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            name=data["name"],
            version=data["version"],
            python_paths=data.get("python_paths", []),
            env=data.get("env", {}),
        )


@dataclass
class EnvironmentConfig(object):
    """
    Parsed contents of an Environment.json file.

    Attributes:
        name (str): Show name.
        packages_root (str): Root directory containing all versioned package folders.
        versions (dict[str, str]): Maps package name to its version string.
        loadout (dict[str, list[str]]): Maps package name to a list of
            additional package names that are auto-resolved alongside it.
    """

    name: str
    packages_root: str
    versions: dict[str, str] = field(default_factory=dict)
    loadout: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "EnvironmentConfig":
        """
        Load and parse an Environment.json file.

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
            loadout=data.get("loadout", {}),
        )


# -----Environment Resolver----------------------------------------------------


@dataclass
class ResolvedEnvironment(object):
    """
    The result of an EnvironmentResolver.resolve() call.
    Contains the full environment for all necessary tools related to a program
    and a list of Context objects that represent each of those packages.

    Attributes:
        env (dict[str, str]): The fully built environment, ready to pass to
            subprocess.Popen(env=...). Keys and values are all strings.
        contexts (list[Context]): One Context per resolved package, in load order.
    """

    env: dict[str, str]
    contexts: list[Context]


class EnvironmentResolver(object):
    """
    Builds a resolved environment dict from a show config and a list of packages.

    Does not touch os.environ or sys.path. The returned environment dict can be
    passed directly to subprocess.Popen(env=...).

    Usage:
        resolver = EnvironmentResolver(show)
        result = resolver.resolve(["mytool", "nuke"], base_env=os.environ.copy())
        subprocess.Popen(["nuke", "-t", "script.nk"], env=result.env)
    Args:
        config (EnvironmentConfig): The environment configuration to resolve
            packages from.
        extra_search_paths (list[Path]): Additional directories to search for
            packages alongside show.packages_root.
    """

    def __init__(
        self,
        config: EnvironmentConfig,
        extra_search_paths: Optional[list[Path]] = None,
    ) -> None:
        self._config = config
        self._extra_search_paths = extra_search_paths or []

    def resolve(
        self,
        packages: list[str],
        base_env: Optional[dict[str, str]] = None,
    ) -> ResolvedEnvironment:
        """
        Resolve a list of packages and return the resulting environment.

        Loadouts declared in the environment config are automatically included.
        Duplicate packages are resolved only once, in first-seen order.

        $VAR expansion in package env values resolves against the environment
        as it accumulates, so a package can reference vars set by an earlier
        package in the same resolve call.

        Args:
            packages (list[str]): Package names to resolve.
            base_env (Optional[dict[str, str]]): The starting environment to
                layer package vars on top of. Defaults to None.
        Returns:
            ResolvedEnvironment: The built env dict and one Context per package.
        Raises:
            VersionNotSpecifiedError: If a package has no specified version.
            PackageNotFoundError: If a package directory does not exist on disk.
        """
        env: dict[str, str] = base_env if base_env is not None else {}
        contexts: list[Context] = []

        for name in self._resolve_load_order(packages):
            ctx = self._resolve_package(name, env)
            contexts.append(ctx)

            # Merge this package's python_paths into PYTHONPATH in the env dict.
            if ctx.python_paths:
                existing = env.get("PYTHONPATH", "")
                new_paths = os.pathsep.join(ctx.python_paths)
                env["PYTHONPATH"] = (
                    os.pathsep.join([new_paths, existing]) if existing else new_paths
                )

            # Merge env vars into the accumulating env so later packages can
            # expand $VAR references against them.
            env.update(ctx.env)

        return ResolvedEnvironment(env=env, contexts=contexts)

    def _resolve_load_order(self, packages: list[str]) -> list[str]:
        """
        Return a flat, deduplicated load order including all packages.

        With-packages are resolved before the package that declares them so
        that $VAR expansion in a package's env values can reference variables
        set by its dependencies.

        Args:
            packages (list[str]): Explicitly requested package names.
        Returns:
            list[str]: Ordered, deduplicated list of all package names to resolve.
        """
        seen: set[str] = set()
        order: list[str] = []

        def visit(name_: str) -> None:
            if name_ in seen:
                return
            seen.add(name_)
            for dep in self._config.loadout.get(name_, []):
                visit(dep)
            order.append(name_)

        for name in packages:
            visit(name)

        return order

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
            return self._config.versions[name]
        except KeyError:
            raise VersionNotSpecifiedError(
                f"Package '{name}' has no version in environment config '{self._config.name}'."
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
        search_roots = [Path(self._config.packages_root), *self._extra_search_paths]
        for root in search_roots:
            candidate = root / name / version
            if candidate.is_dir():
                return candidate

        searched = ", ".join(str(r) for r in search_roots)
        raise PackageNotFoundError(
            f"Package '{name}' version '{version}' not found. Searched: {searched}"
        )

    @staticmethod
    def _expand_value(value: str, root: Path, env: dict[str, str]) -> str:
        """
        Expand {root} and $VAR / ${VAR} tokens in an env var value.

        {root} is substituted first, then $VAR / ${VAR} references are expanded
        against env — the environment as accumulated so far during this resolve
        call, not os.environ.

        Args:
            value (str): Raw value string from Package.json.
            root (Path): Absolute path to the package directory.
            env (dict[str, str]): The environment accumulated so far.
        Returns:
            str: Fully expanded value.
        """
        value = value.replace("{root}", root.as_posix())

        def replace(match: re.Match) -> str:
            key = match.group(1) or match.group(2)
            return env.get(key, match.group(0))

        return re.sub(r"\$\{(\w+)}|\$(\w+)", replace, value)

    def _resolve_package(self, name: str, env: dict[str, str]) -> Context:
        """
        Read a package config from disk and build its Context.

        Does not mutate env. The caller is responsible for merging ctx.env
        back into the accumulating environment after this returns.

        Args:
            name (str): Package name to resolve.
            env (dict[str, str]): The environment accumulated so far, used for
                $VAR expansion in this package's env values.
        Returns:
            Context: The resolved context.
        Raises:
            VersionNotSpecifiedError: If the package version is not in the show config.
            PackageNotFoundError: If the package directory does not exist on disk.
        """
        version = self._resolve_version(name)
        pkg_dir = self._find_package_dir(name, version)
        config = PackageConfig.from_file(pkg_dir / "Package.json")

        abs_python_paths = [
            str((pkg_dir / rel).resolve()) for rel in config.python_paths
        ]

        resolved_env: dict[str, str] = {
            key: self._expand_value(raw, pkg_dir, env)
            for key, raw in config.env.items()
        }

        return Context(
            name=name,
            version=version,
            root=pkg_dir,
            python_paths=abs_python_paths,
            env=resolved_env,
        )
