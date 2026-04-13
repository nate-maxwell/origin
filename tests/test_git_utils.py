"""Tests for git_utils.py"""

from unittest.mock import MagicMock
from unittest.mock import patch

import git
import pytest

from origin.git_utils import (
    UncommittedChangesError,
    UnpushedCommitsError,
    check_git_available,
    check_repo_is_clean,
    create_and_push_branch,
)

# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def mock_repo() -> MagicMock:
    return MagicMock(spec=git.Repo)


@pytest.fixture()
def mock_branch() -> MagicMock:
    branch = MagicMock()
    branch.name = "main"
    branch.__str__ = lambda self: "main"
    return branch


@pytest.fixture()
def mock_tracking_branch() -> MagicMock:
    tracking = MagicMock()
    tracking.__str__ = lambda self: "origin/main"
    return tracking


# -----check_git_available-----------------------------------------------------


def test_check_git_available_succeeds() -> None:
    with patch("git.cmd.Git") as mock_git:
        mock_git.return_value.version.return_value = "git version 2.40.0"
        check_git_available()


def test_check_git_available_raises_when_git_missing() -> None:
    with patch("git.cmd.Git") as mock_git:
        mock_git.return_value.version.side_effect = git.exc.GitCommandNotFound(
            "git", "not found"
        )
        with pytest.raises(EnvironmentError):
            check_git_available()


# -----check_repo_is_clean-----------------------------------------------------


def test_check_repo_is_clean_passes_on_clean_repo(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
    mock_tracking_branch: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = False
    mock_repo.active_branch = mock_branch
    mock_branch.tracking_branch.return_value = mock_tracking_branch
    mock_repo.iter_commits.return_value = iter([])

    with patch("git.Repo", return_value=mock_repo):
        check_repo_is_clean("/fake/repo")


def test_check_repo_is_clean_raises_on_uncommitted_changes(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = True
    mock_repo.active_branch = mock_branch

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(UncommittedChangesError):
            check_repo_is_clean("/fake/repo")


def test_check_repo_is_clean_raises_on_unpushed_commits(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
    mock_tracking_branch: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = False
    mock_repo.active_branch = mock_branch
    mock_branch.tracking_branch.return_value = mock_tracking_branch
    mock_repo.iter_commits.return_value = iter([MagicMock()])

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(UnpushedCommitsError):
            check_repo_is_clean("/fake/repo")


def test_check_repo_is_clean_passes_with_no_tracking_branch(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = False
    mock_repo.active_branch = mock_branch
    mock_branch.tracking_branch.return_value = None

    with patch("git.Repo", return_value=mock_repo):
        check_repo_is_clean("/fake/repo")


# -----create_and_push_branch--------------------------------------------------


def test_create_and_push_branch_succeeds(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
) -> None:
    mock_repo.active_branch = mock_branch
    mock_repo.branches = []
    mock_new_branch = MagicMock()
    mock_repo.create_head.return_value = mock_new_branch
    mock_remote = MagicMock()
    mock_repo.remote.return_value = mock_remote

    with patch("git.Repo", return_value=mock_repo):
        create_and_push_branch("/fake/repo", "1.0.0")

    mock_repo.create_head.assert_called_once_with("1.0.0")
    mock_new_branch.checkout.assert_called_once()
    mock_remote.push.assert_called_once_with(refspec="1.0.0:1.0.0")
    mock_branch.checkout.assert_called_once()


def test_create_and_push_branch_raises_if_branch_exists(
    mock_repo: MagicMock,
) -> None:
    existing_branch = MagicMock()
    existing_branch.name = "1.0.0"
    mock_repo.branches = [existing_branch]

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(ValueError):
            create_and_push_branch("/fake/repo", "1.0.0")


def test_create_and_push_branch_restores_original_branch(
    mock_repo: MagicMock,
    mock_branch: MagicMock,
) -> None:
    mock_repo.active_branch = mock_branch
    mock_repo.branches = []
    mock_repo.create_head.return_value = MagicMock()
    mock_repo.remote.return_value = MagicMock()

    with patch("git.Repo", return_value=mock_repo):
        create_and_push_branch("/fake/repo", "1.0.0")

    mock_branch.checkout.assert_called_once()


def test_create_and_push_branch_does_not_push_if_branch_exists(
    mock_repo: MagicMock,
) -> None:
    existing_branch = MagicMock()
    existing_branch.name = "1.0.0"
    mock_repo.branches = [existing_branch]
    mock_remote = MagicMock()
    mock_repo.remote.return_value = mock_remote

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(ValueError):
            create_and_push_branch("/fake/repo", "1.0.0")

    mock_remote.push.assert_not_called()
