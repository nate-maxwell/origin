"""Tests for git_utils.py"""

from unittest.mock import MagicMock
from unittest.mock import patch

import git
import pytest

from origin.git_utils import (
    UncommittedChangesError,
    check_git_available,
    create_and_push_tag,
)

# -----Fixtures----------------------------------------------------------------


@pytest.fixture()
def mock_repo() -> MagicMock:
    return MagicMock(spec=git.Repo)


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


# -----create_and_push_tag-----------------------------------------------------


def test_create_and_push_tag_succeeds(mock_repo: MagicMock) -> None:
    mock_repo.is_dirty.return_value = False
    mock_repo.tags = []
    mock_remote = MagicMock()
    mock_repo.remote.return_value = mock_remote

    with patch("git.Repo", return_value=mock_repo):
        create_and_push_tag("/fake/repo", "1.0.0")

    mock_repo.create_tag.assert_called_once_with("1.0.0")
    mock_remote.push.assert_called_once_with(refspec="refs/tags/1.0.0:refs/tags/1.0.0")


def test_create_and_push_tag_raises_on_uncommitted_changes(
    mock_repo: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = True

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(UncommittedChangesError):
            create_and_push_tag("/fake/repo", "1.0.0")


def test_create_and_push_tag_raises_if_tag_exists(mock_repo: MagicMock) -> None:
    mock_repo.is_dirty.return_value = False
    existing_tag = MagicMock()
    existing_tag.name = "1.0.0"
    mock_repo.tags = [existing_tag]

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(ValueError):
            create_and_push_tag("/fake/repo", "1.0.0")


def test_create_and_push_tag_does_not_push_if_tag_exists(
    mock_repo: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = False
    existing_tag = MagicMock()
    existing_tag.name = "1.0.0"
    mock_repo.tags = [existing_tag]
    mock_remote = MagicMock()
    mock_repo.remote.return_value = mock_remote

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(ValueError):
            create_and_push_tag("/fake/repo", "1.0.0")

    mock_remote.push.assert_not_called()


def test_create_and_push_tag_does_not_create_tag_on_dirty_repo(
    mock_repo: MagicMock,
) -> None:
    mock_repo.is_dirty.return_value = True

    with patch("git.Repo", return_value=mock_repo):
        with pytest.raises(UncommittedChangesError):
            create_and_push_tag("/fake/repo", "1.0.0")

    mock_repo.create_tag.assert_not_called()
