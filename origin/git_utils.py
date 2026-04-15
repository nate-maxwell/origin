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


path_type = Optional[Union[str, os.PathLike]]


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


def check_repo_is_clean(repo_path: path_type) -> None:
    """
    Verify that a git repository has no uncommitted changes and no unpushed commits.

    Args:
        repo_path (str | PathLike): Path to the root of the git repository.
    Raises:
        UncommittedChangesError: If the repository has uncommitted changes.
        UnpushedCommitsError: If the local branch has commits not pushed to the remote.
    """
    repo = git.Repo(repo_path)

    if repo.is_dirty(untracked_files=True):
        raise UncommittedChangesError(
            f"Repository at '{repo_path}' has uncommitted changes."
        )

    branch = repo.active_branch
    tracking = branch.tracking_branch()

    if tracking is None:
        return

    unpushed = list(repo.iter_commits(f"{tracking}..{branch}"))
    if unpushed:
        raise UnpushedCommitsError(
            f"Local branch '{branch}' has {len(unpushed)} unpushed commit(s)."
        )


def create_and_push_tag(repo_path: path_type, tag_name: str) -> None:
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
    if repo.is_dirty(untracked_files=True):
        raise UncommittedChangesError(
            f"Repository at '{repo_path}' has uncommitted changes."
        )

    if tag_name in [t.name for t in repo.tags]:
        raise ValueError(
            f"Tag '{tag_name}' already exists locally. "
            f"If a previous publish attempt failed, delete it manually before retrying."
        )

    repo.create_tag(tag_name)
    repo.remote("origin").push(refspec=f"refs/tags/{tag_name}:refs/tags/{tag_name}")


def create_and_push_branch(repo_path: path_type, branch_name: str) -> None:
    """
    In a git repository, save the current branch, create a new branch and push
    it to the remote, then switch back to the original branch.

    Args:
        repo_path (str | PathLike): Path to the root of the git repository.
        branch_name (str): Name of the branch to create and push.
    Raises:
        git.GitCommandError: If the branch already exists or the push fails.
    """
    repo = git.Repo(repo_path)
    if branch_name in [b.name for b in repo.branches]:
        raise ValueError(
            f"Branch '{branch_name}' already exists locally. "
            f"If a previous publish attempt failed, delete it manually before retrying."
        )

    original_branch = repo.active_branch

    new_branch = repo.create_head(branch_name)
    new_branch.checkout()
    repo.remote("origin").push(refspec=f"{branch_name}:{branch_name}")

    original_branch.checkout()
