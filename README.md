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
        "nuke": ["pipelinecore", "mytool"]
    }
}
```

**2. Define your packages.**

Each package lives at `packages_root/name/version/` and contains a `Package.json`:

```json
{
    "name": "mytool",
    "version": "2.3.0",
    "env": {
        "MYTOOL_ROOT": "{root}",
        "MYTOOL_PLUGINS": "{root}/plugins"
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
explicitly in the Package.json.

### Loadout

A named list of packages defined in `Environment.json` that should be resolved
together for a specific application. For example, a `nuke` loadout might include
`pipelinecore`, `colour`, and `mytool`. When `launch()` is called with a loadout,
the resolver walks the list in order, building up the environment as it goes.
A package that appears in multiple loadouts is only resolved once.

### Package

A fully resolved package, produced by the `EnvironmentResolver` after reading a
`Package.json` from disk. Holds the package name, version, root path on disk,
and its fully expanded environment variable contributions. The package root is
automatically prepended to `PYTHONPATH`, making the package importable in the
launched application without any additional configuration.

### EnvironmentResolver

Takes an `EnvironmentConfig` and resolves one or more loadouts into a
`ResolvedEnvironment`. Handles version lookup, locating the package directory
on disk, reading and parsing `Package.json`, expanding `{root}` and `$VAR`
tokens in env values, and accumulating `PYTHONPATH`. Later packages in a loadout
can reference environment variables set by earlier ones.

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
`packages_root` from an `Environment.json`, reads the package name and version
from the source directory's `Package.json`, copies the source to `packages_root/name/version/`
(excluding development artifacts like virtual environments, caches, and editor
configs), and creates a version branch in the source git repository and pushes
it to the remote. The git step ensures every deployed artifact is traceable to
an exact point in source history. The publish will refuse to proceed if the
repository has uncommitted changes or unpushed commits.

### git_utils

Internal utilities for git operations used by the publish workflow. Provides
`check_git_available()` to verify git is on the system PATH, `check_repo_is_clean()`
to assert no uncommitted changes or unpushed commits exist, and `create_and_push_branch()`
to create a version branch and push it to the remote before returning to the
original branch.
