"""Launch an application with a resolved environment."""

import os
import subprocess
from pathlib import Path
from typing import Optional
from typing import Union

from origin.environment import EnvironmentConfig
from origin.environment import EnvironmentResolver
from origin.application import Application


def launch(
    executable: Union[str, os.PathLike],
    environment_config: Union[str, os.PathLike],
    loadout: str,
    base_env: Optional[dict[str, str]] = None,
    args: Optional[list[str]] = None,
) -> Application:
    """
    Resolve an environment and launch an application.
    Custom environment variables are read from packages.

    Args:
        executable (Union[str, os.PathLike]): The application executable to launch.
        environment_config (Union[str, os.PathLike]): Path to the Environment.json file.
        loadout (str): The loadout key to resolve from the environment config.
        base_env (Optional[dict[str, str]]): Environment to build on top of.
                When omitted, the current process environment is used as the base.
        args (Optional[list[str]]): Additional arguments to pass to the application.
    Returns:
        subprocess.Popen: The launch application process.
    """
    exe_ = Path(executable)
    env: dict[str, str] = base_env if base_env is not None else dict(os.environ)
    cfg = EnvironmentConfig.from_file(Path(environment_config))
    resolver = EnvironmentResolver(cfg)
    resolved = resolver.resolve([loadout], env)

    cmd = [exe_.as_posix()] + (args or [])
    proc = subprocess.Popen(
        cmd, env=resolved.env, creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    return Application(
        executable=exe_,
        loadout=loadout,
        process=proc,
        resolved=resolved,
    )
