"""
# Git Utils

Reusable common git operations.
"""

import os
from typing import Optional
from typing import Union

import git


class UncommittedChangesError(Exception):
    """Raised when the repository has uncommitted changes."""


class UnpushedCommitsError(Exception):
    """Raised when the local branch has commits not pushed to the remote."""


def check_git_available() -> None:
    """
    Verify that git is available on the system PATH.

    Raises:
        EnvironmentError: If git is not found on the system PATH.
    """
    try:
        git.cmd.Git().version()
    except git.exc.GitCommandNotFound:
        raise EnvironmentError("git is not available on the system PATH.")


def check_repo_is_clean(repo_path: Union[str, os.PathLike]) -> None:
    repo = git.Repo(repo_path)
    if repo.is_dirty(untracked_files=True):
        err_msg = f"Repository at '{repo_path}' has uncommitted changes."
        raise UncommittedChangesError(err_msg)


def create_and_push_tag(repo_path: Union[str, os.PathLike], tag_name: str) -> None:
    """
    Create a tag in a git repository and push it to the remote.

    Args:
        repo_path (str | PathLike): Path to the root of the git repository.
        tag_name (str): Name of the tag to create and push.
    Raises:
        ValueError: If the tag already exists locally.
        git.GitCommandError: If the push fails.
    """
    repo = git.Repo(repo_path)
    check_repo_is_clean(repo_path)

    if tag_name in [t.name for t in repo.tags]:
        raise ValueError(
            f"Tag '{tag_name}' already exists locally. "
            f"If a previous publish attempt failed, delete it manually before retrying."
        )

    repo.create_tag(tag_name)
    repo.remote("origin").push(refspec=f"refs/tags/{tag_name}:refs/tags/{tag_name}")
