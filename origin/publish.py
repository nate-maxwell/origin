"""
# Package Publisher

Provides tooling for publishing a package from a source directory to the
packages root defined in an Environment.json file.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from distlib.database import DistributionPath

import origin.git_utils
from origin.environment import PackageConfig


class PackageVersionExistsError(Exception):
    """
    Raised when attempting to publish a package with a version that has
    already been published.
    """


class PackageVersionNotExistsError(Exception):
    """
    Raised when attempting to publish a package with a Package.json that cannot
    be found.
    """


_ignore_list = [
    ".vscode",
    ".idea",
    "*.pyc",
    "__pycache__",
    ".git",
    ".gitignore",
    "*.egg-info",
    ".github",
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenvironment",
    "virtual_environment",
    ".virtualenvironment",
    ".virtual_environment",
]


def _publish_package(environment_config: Path, source_dir: Path) -> PackageConfig:
    # Environment json
    env_str = environment_config.read_text()
    env_data = json.loads(env_str)
    packages_root = Path(env_data["packages_root"])

    # Package json
    package_json = Path(source_dir, "Package.json")
    if not package_json.exists():
        err_msg = f"No Package.json file located in {source_dir.as_posix()}"
        raise PackageVersionNotExistsError(err_msg)

    pkg_cfg = PackageConfig.from_file(package_json)
    package_version_path = Path(packages_root, pkg_cfg.name, pkg_cfg.version)

    if Path(package_version_path, "Package.json").exists():
        err_msg = f"Package {pkg_cfg.name} version {pkg_cfg.version} already exists!"
        raise PackageVersionExistsError(err_msg)

    # Publish package to disk
    shutil.copytree(
        source_dir,
        package_version_path,
        ignore=shutil.ignore_patterns(*_ignore_list),
        dirs_exist_ok=True,
    )

    return pkg_cfg


def _update_environment_config(
    environment_config: Path,
    distributions: list,
) -> None:
    """
    Add the published pip package to the Environment.json packages section.

    Args:
        environment_config (Path): Path to the Environment.json file to update.
        distributions (list): Distlib Distribution objects that were published.
    Returns:
        None
    """
    data = json.loads(environment_config.read_text(encoding="utf-8"))

    for distribution in distributions:
        data["packages"][distribution.name] = distribution.version

    environment_config.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )


def publish_package(environment_config: Path, source_dir: Path) -> None:
    """
    Publish a package from a source directory to the packages root.

    A publish operation does the following:
    1. Reads the Environment.json to determine the packages root.
    2. Reads the Package.json in the source directory to determine the
       package name and version.
    3. Copies the source directory to the packages root, excluding
       development artifacts such as virtual environments, caches, and
       editor configs.
    4. Creates a version branch in the source repository and pushes it
       to the remote, ensuring the deployed artifact is traceable to an
       exact point in source history.

    Args:
        environment_config (Path): Path to the Environment.json file that
            defines the packages root to publish into.
        source_dir (Path): Path to the root of the package source directory.
            Must contain a Package.json file.
    Raises:
        PackageVersionNotExistsError: If no Package.json is found in source_dir.
        PackageVersionExistsError: If the package version has already been
            published to the packages root.
        git.GitCommandError: If the version branch push fails.
        ValueError: If the version branch already exists locally.
        UncommittedChangesError: If the source repository has uncommitted changes.
        UnpushedCommitsError: If the source repository has unpushed commits.
    """
    pkg_cfg = _publish_package(environment_config, source_dir)

    # Make git branch for package version
    origin.git_utils.check_git_available()
    origin.git_utils.check_repo_is_clean(source_dir)
    origin.git_utils.create_and_push_branch(source_dir, pkg_cfg.version)


def pip_publish(environment_config: Path, package_name: str) -> None:
    """
    Download a package from PyPI using pip, merge all installed distributions
    into a single Origin package, and publish it to the packages root.

    All distributions installed as dependencies (e.g. PySide6_Essentials,
    PySide6_Addons, shiboken6) are merged into a single package directory
    alongside the top-level package, mirroring how pip installs them into
    a flat site-packages directory. This avoids path resolution issues that
    arise when distributions expect their dependencies to be co-located.

    Args:
        environment_config (Path): Path to the Environment.json file that
            defines the packages root to publish into.
        package_name (str): The PyPI package name to install, e.g. "requests"
            or "numpy==1.26.0".
    Raises:
        PackageVersionExistsError: If the package version has already been
            published to the packages root.
        subprocess.CalledProcessError: If the pip install fails.
        RuntimeError: If no distributions are found after installation, or if
            the top-level package cannot be identified in the installed distributions.
    """
    loadout_name = re.split(r"[=<>!]", package_name)[0].strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        subprocess.run(
            ["pip", "install", package_name, "--target", str(tmp_path)],
            check=True,
        )

        distributions = list(DistributionPath([str(tmp_path)]).get_distributions())
        if not distributions:
            raise RuntimeError(
                f"Could not find any distributions after installing '{package_name}'."
            )

        # Find the top-level distribution to get the canonical version
        top_dist = next(
            (d for d in distributions if d.name.lower() == loadout_name.lower()),
            None,
        )
        if top_dist is None:
            raise RuntimeError(
                f"Could not identify top-level distribution '{loadout_name}' "
                f"in installed distributions: {[d.name for d in distributions]}"
            )

        # Merge all distributions into a single staging directory
        staging_dir = tmp_path / f"_staging_{loadout_name}"
        staging_dir.mkdir()

        for distribution in distributions:
            for installed_file, _, _ in distribution.list_installed_files():
                src = tmp_path / installed_file
                dst = staging_dir / installed_file
                if not src.exists():
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        # Generate a single Package.json for the merged package
        (staging_dir / "Package.json").write_text(
            json.dumps(
                {
                    "name": loadout_name,
                    "version": top_dist.version,
                    "env": {},
                },
                indent=4,
            ),
            encoding="utf-8",
        )

        _publish_package(environment_config, staging_dir)
        _update_environment_config(environment_config, [top_dist], loadout_name)
