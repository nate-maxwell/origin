"""Launch an application with a resolved environment."""

import subprocess
from pathlib import Path

from environment import EnvironmentConfig
from environment import EnvironmentResolver


def launch(
    executable: Path,
    environment_config: Path,
    loadout: str,
    args: list[str] | None = None,
) -> subprocess.Popen:
    """
    Resolve an environment and launch an application.

    Args:
        executable (Path): The application executable to launch.
        environment_config (Path): Path to the Environment.json file.
        loadout (str): The loadout key to resolve from the environment config.
        args (list[str]): Additional arguments to pass to the application.
    Returns:
        subprocess.Popen: The launch application process.
    """
    cfg = EnvironmentConfig.from_file(environment_config)
    resolver = EnvironmentResolver(cfg)
    resolved = resolver.resolve([loadout])

    cmd = [executable.as_posix()] + (args or [])
    return subprocess.Popen(
        cmd, env=resolved.env, creationflags=subprocess.CREATE_NEW_CONSOLE
    )
