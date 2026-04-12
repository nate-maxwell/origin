"""
# Package Publisher

Provides tooling for publishing a package from a source directory to the
packages root defined in an Environment.json file.

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
"""

import json
import shutil
from pathlib import Path

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


def publish_package(environment_config: Path, source_dir: Path) -> None:
    """
    Publish a package from a source directory to the packages root.

    Copies the source directory to packages_root/name/version/ as defined
    by the Package.json found in source_dir, then creates and pushes a
    version branch in the source repository.

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

    # Make git branch for package version
    origin.git_utils.check_git_available()
    origin.git_utils.check_repo_is_clean(source_dir)
    origin.git_utils.create_and_push_branch(source_dir, pkg_cfg.version)
