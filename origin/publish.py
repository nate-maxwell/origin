"""
# Package Publisher

Provides tooling for publishing a package from a source directory to the
packages root defined in an Environment.json file.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Union

from distlib.database import DistributionPath

import origin.git_utils
import origin.config
from origin.environment import PackageConfig


class PackageVersionExistsError(Exception):
    """
    Raised when attempting to publish a package with a version that has
    already been published.
    """


class PackageVersionNotExistsError(Exception):
    """
    Raised when attempting to publish a package with a package.yaml that cannot
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
    "test",
    "tests",
    "unittests",
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    ".virtualenv",
    "virtualenvironment",
    ".virtualenvironment",
    "virtual_environment",
    ".virtual_environment",
]


def publish_package(
    repository: Union[str, os.PathLike], source_dir: Union[str, os.PathLike]
) -> None:
    """
    Publish a package from a source directory to a repository.

    A publish operation does the following:
    1. Reads the package.yaml in the source directory to determine the
       package name and version.
    2. Copies the source directory to a temporary location in the repository,
       excluding development artifacts such as virtual environments, caches,
       and editor configs.
    3. Renames the temporary directory into its final location, minimising
       the window in which a partial publish could be observed.
    4. Creates and pushes a version tag in the source git repository,
       ensuring the deployed artifact is traceable to an exact point in
       source history.

    If any step fails, the temporary directory is cleaned up automatically
    and the repository is left in a clean state. The publish can be retried
    without manual intervention.

    Args:
        repository (str | os.PathLike): Path to the repository to publish into.
        source_dir (str | os.PathLike): Path to the root of the package source
            directory. Must contain a package.yaml file.
    Raises:
        PackageVersionNotExistsError: If no package.yaml is found in source_dir.
        PackageVersionExistsError: If the package version has already been
            published to the repository.
        git.GitCommandError: If the version tag push fails.
        ValueError: If the version tag already exists locally.
        UncommittedChangesError: If the source repository has uncommitted changes.
    """
    repo_path = Path(repository)
    package_json = Path(source_dir, "package.yaml")

    if not package_json.exists():
        err_msg = f"No package.yaml file located in {Path(source_dir).as_posix()}"
        raise PackageVersionNotExistsError(err_msg)

    pkg_cfg = PackageConfig.from_file(package_json)
    package_version_path = repo_path / pkg_cfg.name / pkg_cfg.version

    if Path(package_version_path, "package.yaml").exists():
        err_msg = f"Package {pkg_cfg.name} version {pkg_cfg.version} already exists!"
        raise PackageVersionExistsError(err_msg)

    # Atomically copy - Copy to a temp directory alongside the destination first
    tmp_path = repo_path / pkg_cfg.name / f"_tmp_{pkg_cfg.version}"
    try:
        shutil.copytree(
            source_dir,
            tmp_path,
            ignore=shutil.ignore_patterns(*_ignore_list),
            dirs_exist_ok=True,
        )

        # Git checks happen after the copy succeeds but before we commit
        origin.git_utils.check_git_available()
        origin.git_utils.check_repo_is_clean(source_dir)

        # Rename into place — this is as close to atomic as the filesystem allows
        tmp_path.rename(package_version_path)

        # Tag only after the directory is in its final location
        origin.git_utils.create_and_push_tag(source_dir, pkg_cfg.version)

    except Exception:
        # Clean up the temp directory if anything went wrong
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        raise


def pip_publish(repository: Union[str, os.PathLike], package_name: str) -> None:
    """
    Download a package from PyPI using pip, merge all installed distributions
    into a single Origin package, and publish it to the repository.

    All distributions installed as dependencies (e.g. PySide6_Essentials,
    PySide6_Addons, shiboken6) are merged into a single package directory
    alongside the top-level package, mirroring how pip installs them into
    a flat site-packages directory. This avoids path resolution issues that
    arise when distributions expect their dependencies to be co-located.

    Args:
        repository (str | os.PathLike): Path to the repository to publish into.
        package_name (str): The PyPI package name to install, e.g. "requests"
            or "numpy==1.26.0".
    Raises:
        PackageVersionExistsError: If the package version has already been
            published to the repository.
        subprocess.CalledProcessError: If the pip install fails.
        RuntimeError: If no distributions are found after installation, or if
            the top-level package cannot be identified in the installed distributions.
    """
    repo_path = Path(repository)
    loadout_name = re.split(r"[=<>!]", package_name)[0].strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        subprocess.run(
            ["pip", "install", package_name, "--target", str(tmp_path)],
            check=True,
        )

        distributions = list(DistributionPath([str(tmp_path)]).get_distributions())
        if not distributions:
            err_msg = (
                f"Could not find any distributions after installing '{package_name}'."
            )
            raise RuntimeError(err_msg)

        top_dist = next(
            (d for d in distributions if d.name.lower() == loadout_name.lower()),
            None,
        )
        if top_dist is None:
            err_msg = f"Could not identify top-level distribution '{loadout_name}' "
            err_msg += f"in installed distributions: {[d.name for d in distributions]}"
            raise RuntimeError(err_msg)

        package_version_path = repo_path / loadout_name / top_dist.version
        if Path(package_version_path, "package.yaml").exists():
            err = f"Package {loadout_name} version {top_dist.version} already exists!"
            raise PackageVersionExistsError(err)

        # Merge all distributions into a staging directory then rename into place
        staging_dir = tmp_path / f"_staging_{loadout_name}"
        staging_dir.mkdir()
        tmp_dest = None

        try:
            for distribution in distributions:
                for installed_file, _, _ in distribution.list_installed_files():
                    src = tmp_path / installed_file
                    dst = staging_dir / installed_file
                    if not src.exists():
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

            data = {"name": loadout_name, "version": top_dist.version, "env": {}}
            origin.config.export_data_to_yaml(Path(staging_dir, "package.yaml"), data)

            tmp_dest = repo_path / loadout_name / f"_tmp_{top_dist.version}"
            tmp_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging_dir, tmp_dest)
            tmp_dest.rename(package_version_path)

        except Exception:
            if tmp_dest is not None and tmp_dest.exists():
                shutil.rmtree(tmp_dest)
            raise
