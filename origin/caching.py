import os
from pathlib import Path

CACHING_ENABLED = "ENABLED"
CACHING_DISABLED = "DISABLED"
ENV_CACHING = "ORIGIN_CACHING_ENABLED"

if ENV_CACHING not in dict(os.environ):
    os.environ[ENV_CACHING] = CACHING_DISABLED


def get_caching_enabled() -> bool:
    """Is caching enabled?"""
    caching = os.environ.get(ENV_CACHING, CACHING_DISABLED)
    return caching == CACHING_ENABLED


def get_package_cache_dir() -> Path:
    """
    Return the platform-appropriate root directory for Origin's cache.

    Returns:
        Path: The cache root directory for the current platform.
            Windows: C:/origin/cache
            Mac/Linux: ~/.origin/cache
    """
    if os.name == "nt":
        system_drive = os.environ.get("SYSTEMDRIVE", "C:")
        return Path(system_drive) / "/origin/cache"
    return Path.home() / ".origin/cache"
