# Origin

A lightweight pipeline environment resolver and application launcher for small
teams.

Origin manages package versions per project, builds environments before launching
applications, and provides a publish workflow that ties deployed packages to git history.
It is intentionally simple — no graph-based dependency solving, no platform
variant system, no install tooling.

---

## Quickstart

**1. Define your project environment.**

Create an `Environment.json` for your project, pointing at your packages root and
declaring which version of each package the project uses:

```json
{
    "name": "MYPROJECT",
    "packages_root": "T:/packages",
    "packages": {
        "pipelinecore": "1.2.0",
        "mytool": "2.3.0"
    },
    "loadouts": {
        "base": ["pipelinecore"],
        "nuke": ["base", "mytool"]
    }
}
```

**2. Define your packages.**

Each package lives at `packages_root/name/version/` and contains a `Package.json`:

```json
{
    "name": "mytool",
    "version": "2.3.0",
    "description": "This is a cool tool I wrote...",
    "authors": ["Marty McFly"],
    "env": {
        "MYTOOL_PLUGINS": "T:/plugins/mytool"
    }
}
```

**3. Launch an application.**

```python
from pathlib import Path
import origin

app = origin.launch(
    executable=Path("C:/Program Files/Nuke15.0/Nuke15.0.exe"),
    environment_config=Path("V:/projects/MYPROJECT/Environment.json"),
    loadout="nuke",
)

app.wait()
if app.has_crashed:
    print(f"Nuke exited with code {app.poll()}")
```

**4. Publish a package.**

From the root of a package's source repository:

```python
from pathlib import Path
from origin.publish import publish_package

publish_package(
    environment_config=Path("V:/projects/MYPROJECT/Environment.json"),
    source_dir=Path("T:/git/mytool"),
)
```

This copies the package to the packages root and creates a version branch in
the source repository.

**5. Publish a PyPI package.**

```python
from pathlib import Path
from origin.publish import pip_publish

pip_publish(
    environment_config=Path("V:/projects/MYPROJECT/Environment.json"),
    package_name="requests",
)
```

This installs the package and all of its dependencies from PyPI, merges them
into a single Origin package directory.

---

## Concepts

### Environment.json

The project configuration file. Each project has its own `Environment.json` that
declares the authoritative version of every package available to that project,
and defines loadouts — named groups of packages to resolve together for a specific
application. Multiple projects can share the same `packages_root`; their `Environment.json`
files simply declare different versions of the packages they need.

### Package.json

The package's own declaration of what it contributes to the environment. Each
versioned package directory on disk contains a `Package.json` that declares
environment variables to set. Values are taken as literal strings with no token
expansion. If a package needs to reference a path, the full path should be written
explicitly in the `Package.json`.

Origin automatically injects version environment variables for every package.
For a package named `mytool` at version `2.3.0`, the following variables are
set automatically:

```
ORIGIN_MYTOOL_VERSION=2.3.0
ORIGIN_MYTOOL_MAJOR_VERSION=2
ORIGIN_MYTOOL_MINOR_VERSION=3
ORIGIN_MYTOOL_PATCH_VERSION=0
```

### Loadout

A named list of packages or other loadouts defined in `Environment.json` that
should be resolved together for a specific application. Loadouts can reference
other loadouts by name, allowing shared base configurations to be declared once
and reused:

```json
"loadouts": {
    "base": ["pipelinecore"],
    "nuke": ["base", "colour", "mytool"],
    "houdini": ["base", "mytool"]
}
```

When `launch()` is called with a loadout, the resolver walks the list in order,
recursively expanding any nested loadouts and building up the environment as it
goes. A package that appears in multiple loadouts is only resolved once. Circular
loadout references are detected and raise an error.

Each entry in a loadout list is first checked against the defined loadouts. If
found, it is recursed into as a nested loadout. If not found in loadouts, it is
treated as a package name. Loadout names and package names must therefore be
unique across both — an entry cannot be both a loadout and a package name.

### Package

A fully resolved package, produced by the `EnvironmentResolver` after reading a
`Package.json` from disk. Holds the package name, version, root path on disk,
and its environment variable contributions. The package root is automatically
prepended to `PYTHONPATH`, making the package importable in the launched
application without any additional configuration.

### EnvironmentResolver

Takes an `EnvironmentConfig` and resolves one or more loadouts into a
`ResolvedEnvironment`. Handles version lookup, locating the package directory
on disk, reading and parsing `Package.json`, and accumulating `PYTHONPATH`.
Packages that appear across multiple loadouts are deduplicated.

### ResolvedEnvironment

The output of a single `resolve()` call. Contains the fully built environment
dictionary, ready to pass directly to `subprocess.Popen(env=...)`, and the ordered
list of resolved `Package` instances. The environment dictionary is a complete,
self-contained snapshot — it does not require merging with `os.environ` unless
you explicitly pass `os.environ` as the `base_env`.

### Application

A thin wrapper around `subprocess.Popen` returned by `launch()`. Holds the
executable path, the loadout name, the underlying process handle, and the
`ResolvedEnvironment` the application was launched with. Provides `wait()`,
`poll()`, and a `has_crashed` property for reacting to the application's exit
state. The resolved environment being available on the `Application` instance
is useful for crash reporting — you know exactly which package versions were
loaded when the application went down.

### launch()

Reads an `Environment.json`, resolves the specified loadout, and launches an
executable in the resulting environment. Returns an `Application` instance.
Accepts an optional `base_env` to control what the resolved environment is layered
on top of — by default the current process environment is used as the base. All
environment variable customisation flows through packages; `launch()` does not
accept ad-hoc environment overrides.

### publish_package()

Publishes a package from a source directory to the packages root. Reads the
package name and version from the source directory's `Package.json`, copies the
source to `packages_root/name/version/` (excluding development artifacts like
virtual environments, caches, and editor configs), and creates a version branch
in the source git repository and pushes it to the remote. The git step ensures
every deployed artifact is traceable to an exact point in source history. The
publish will refuse to proceed if the repository has uncommitted changes or
unpushed commits.

### pip_publish()

Downloads a package from PyPI and publishes it to the packages root as a single
Origin package. All distributions installed as dependencies are merged into one
directory, mirroring the flat layout of a `site-packages` folder.

### Caching

By default, Origin resolves packages directly from the `packages_root` defined
in `Environment.json`. When caching is enabled, packages are copied to a local
cache directory on the host machine before being used. Subsequent launches read
from the cache rather than the network share, which can improve startup times
when the packages root is on a remote file server.

The cache directory is platform-dependent:

- **Windows:** `C:/origin/cache`
- **Mac/Linux:** `~/.origin/cache`

Caching is disabled by default and must be opted into by setting the
`ORIGIN_CACHING_ENABLED` environment variable to `ENABLED`.
