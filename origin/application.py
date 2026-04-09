import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from origin.environment import ResolvedEnvironment


@dataclass
class Application(object):
    """
    Represents a launched application process.

    This is helpful for evaluating and reacting to the state of an application.
    For example a support ticket could be automatically submitted, or a ticket
    submitter could be launched if the application did not gracefully exit like
    so:

    >>> app = launch(Path(
    >>>     "C:/path/to/Nuke.exe"),
    >>>     Path("T:/shows/MYSHOW/Environment.json"),
    >>>     "nuke"
    >>> )

    >>> app.wait()
    >>> if app.has_crashed:
    >>>     submit_crash_ticket(app)

    Attributes:
        executable (Path): Path to the application executable.
        loadout (str): The loadout key used to resolve the environment.
        process (subprocess.Popen): The underlying process handle.
        resolved (ResolvedEnvironment): The environment the application was
            launched with.
    """

    executable: Path
    loadout: str
    process: subprocess.Popen
    resolved: ResolvedEnvironment

    def wait(self) -> int:
        """
        Block until the application exits and return its exit code.

        Returns:
            int: The process exit code.
        """
        return self.process.wait()

    def poll(self) -> Optional[int]:
        """
        Check if the application has exited without blocking.

        Returns:
            Optional[int]: The exit code if exited, None if still running.
        """
        return self.process.poll()

    @property
    def has_crashed(self) -> bool:
        """
        Returns whether the application exited with a non-zero exit code.

        Returns:
            bool: True if the process has exited with a non-zero code.
        """
        code = self.poll()
        return code is not None and code != 0
