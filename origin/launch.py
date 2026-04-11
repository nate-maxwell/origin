"""Launch an application with a resolved environment."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from origin.environment import EnvironmentConfig
from origin.environment import EnvironmentResolver
from origin.application import Application


def launch(
    executable: Path,
    environment_config: Path,
    loadout: str,
    base_env: Optional[dict[str, str]] = None,
    args: Optional[list[str]] = None,
) -> Application:
    """
    Resolve an environment and launch an application.
    Custom environment variables are read from packages.

    Args:
        executable (Path): The application executable to launch.
        environment_config (Path): Path to the Environment.json file.
        loadout (str): The loadout key to resolve from the environment config.
        base_env (Optional[dict[str, str]]): Environment to build on top of.
                When omitted, the current process environment is used as the base.
        args (Optional[list[str]]): Additional arguments to pass to the application.
    Returns:
        subprocess.Popen: The launch application process.
    """
    env: dict[str, str] = base_env if base_env is not None else dict(os.environ)
    cfg = EnvironmentConfig.from_file(environment_config)
    resolver = EnvironmentResolver(cfg)
    resolved = resolver.resolve([loadout], env)

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
