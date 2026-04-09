"""Launch an application with a resolved environment."""

import subprocess
from pathlib import Path

from origin.environment import EnvironmentConfig
from origin.environment import EnvironmentResolver
from origin.application import Application


def launch(
    executable: Path,
    environment_config: Path,
    loadout: str,
    args: list[str] | None = None,
) -> Application:
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
    proc = subprocess.Popen(
        cmd, env=resolved.env, creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    return Application(
        executable=executable,
        loadout=loadout,
        process=proc,
        resolved=resolved,
    )
