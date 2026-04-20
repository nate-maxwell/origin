"""Tests for build_command support in publish.py"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from origin.publish import BuildCommandError, _run_build_command
from origin.publish import publish_package
from tests.helpers import make_mock_open

# -----_run_build_command------------------------------------------------------


def test_run_build_command_calls_subprocess(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_build_command("python build.py", tmp_path)

    mock_run.assert_called_once_with(
        "python build.py",
        shell=True,
        cwd=tmp_path,
    )


def test_run_build_command_runs_in_source_dir(tmp_path: Path) -> None:
    source_a = tmp_path / "package_a"
    source_b = tmp_path / "package_b"
    source_a.mkdir()
    source_b.mkdir()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_build_command("python build.py", source_a)
        _run_build_command("python build.py", source_b)

    assert mock_run.call_args_list[0] == call(
        "python build.py", shell=True, cwd=source_a
    )
    assert mock_run.call_args_list[1] == call(
        "python build.py", shell=True, cwd=source_b
    )


def test_run_build_command_raises_on_nonzero_exit(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(BuildCommandError):
            _run_build_command("python build.py", tmp_path)


def test_run_build_command_error_contains_exit_code(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=2)
        with pytest.raises(BuildCommandError, match="2"):
            _run_build_command("python build.py", tmp_path)


def test_run_build_command_error_contains_command(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(BuildCommandError, match="python build.py"):
            _run_build_command("python build.py", tmp_path)


def test_run_build_command_does_not_raise_on_zero_exit(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _run_build_command("python build.py", tmp_path)


# -----publish_package build command integration-------------------------------


PACKAGE_YAML_WITH_BUILD = {
    "name": "mytool",
    "version": "2.3.0",
    "env": {},
    "build_command": "python build.py",
}

PACKAGE_YAML_WITHOUT_BUILD = {
    "name": "mytool",
    "version": "2.3.0",
    "env": {},
}


def make_exists_in(*roots: str):
    """Return a side effect that returns True only for paths under the given roots."""

    def _exists(self) -> bool:
        normalized = str(self).replace("\\", "/")
        normalized_roots = [r.replace("\\", "/") for r in roots]
        return any(root in normalized for root in normalized_roots)

    return _exists


@pytest.fixture()
def env_config_path(tmp_path: Path) -> Path:
    return tmp_path / "shows" / "MYSHOW" / "environment.yaml"


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    d = tmp_path / "source" / "mytool"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def repository(tmp_path: Path) -> Path:
    d = tmp_path / "repository"
    d.mkdir()
    return d


def test_publish_runs_build_command_before_copy(
    source_dir: Path, repository: Path
) -> None:
    pkg_yaml_path = str(source_dir / "package.yaml")
    files = {pkg_yaml_path: PACKAGE_YAML_WITH_BUILD}

    call_order = []

    def fake_run(cmd, shell, cwd):
        call_order.append("build")
        return MagicMock(returncode=0)

    def fake_copytree(*args, **kwargs):
        call_order.append("copy")

    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.exists", make_exists_in(source_dir.as_posix())):
            with patch("subprocess.run", side_effect=fake_run):
                with patch("shutil.copytree", side_effect=fake_copytree):
                    with patch("pathlib.Path.rename"):
                        with patch("origin.git_utils.check_git_available"):
                            with patch("origin.git_utils.check_repo_is_clean"):
                                with patch("origin.git_utils.create_and_push_tag"):
                                    publish_package(
                                        repository=repository,
                                        source_dir=source_dir,
                                    )

    assert call_order == ["build", "copy"]


def test_publish_skips_build_command_when_not_set(
    source_dir: Path, repository: Path
) -> None:

    pkg_yaml_path = str(source_dir / "package.yaml")
    files = {pkg_yaml_path: PACKAGE_YAML_WITHOUT_BUILD}

    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.exists", make_exists_in(source_dir.as_posix())):
            with patch("subprocess.run") as mock_run:
                with patch("shutil.copytree"):
                    with patch("pathlib.Path.rename"):
                        with patch("origin.git_utils.check_git_available"):
                            with patch("origin.git_utils.check_repo_is_clean"):
                                with patch("origin.git_utils.create_and_push_tag"):
                                    publish_package(
                                        repository=repository,
                                        source_dir=source_dir,
                                    )

    mock_run.assert_not_called()


def test_publish_aborts_if_build_command_fails(
    source_dir: Path, repository: Path
) -> None:

    pkg_yaml_path = str(source_dir / "package.yaml")
    files = {pkg_yaml_path: PACKAGE_YAML_WITH_BUILD}

    with patch("builtins.open", make_mock_open(files)):
        with patch("pathlib.Path.exists", make_exists_in(source_dir.as_posix())):
            with patch("subprocess.run", return_value=MagicMock(returncode=1)):
                with patch("shutil.copytree") as mock_copytree:
                    with pytest.raises(BuildCommandError):
                        publish_package(
                            repository=repository,
                            source_dir=source_dir,
                        )

    mock_copytree.assert_not_called()
