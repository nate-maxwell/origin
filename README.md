# Origin

A lightweight pipeline environment resolver and application launcher for small
production teams.

Origin manages package versions per project, builds environments before launching
applications, and provides a publish workflow that ties deployed packages to git
history. It is intentionally simple — no graph-based dependency solving, no
platform variant system.

---

## Quickstart

**1. Define your project environment.**

Create an `environment.yaml` for your project:

```yaml
name: MY_PROJECT

repositories:
  - T:/project/packages
  - T:/facility/packages

packages:
  pipelinecore: 1.2.0
  app_essentials: 1.0.1
  colour: 0.4.2
  service: 15.0.1
  mytool: 2.3.0

loadouts:
  nuke:
    - colour
    - mytool
    - myapp
  myapp:
    - pipelinecore
    - app_essentials

```

**2. Define your packages.**

Each package lives at `repository/name/version/` and contains a `package.yaml`:

```yaml
name: hello_world
authors:
  - Marty McFly
description: Python-based hello world example package.
version: 1.0.0
env: {}

```

**3. Launch an application.**

```python
import origin

app = origin.launch(
    executable="C:/Program Files/Nuke15.0/Nuke15.0.exe",
    environment_config="V:/projects/MY_PROJECT/Environment.json",
    loadout="nuke",
)

app.wait()
if app.has_crashed:
    print(f"Nuke exited with code {app.poll()}")
```

**4. Publish a package.**

```python
from origin.publish import publish_package

publish_package(
    repository="T:/studio/packages",
    source_dir="T:/git/mytool",
)
```

---

## Documentation

### [Environment Config](docs/Environment.md)

The `Environment.json` file declares the package versions available to a project,
the repositories to search for packages, and the loadouts used to launch
applications.

### [Package](docs/Package.md)

A `Package.json` declares what environment variables a package contributes when
resolved. Also covers the `Package` object produced by the resolver and the
automatic version variables Origin injects for every package.

### [Resolving](docs/Resolve.md)

How the `EnvironmentResolver` expands loadouts, searches repositories, and
builds a `ResolvedEnvironment` ready to pass to a process.

### [Applications and Launching](docs/Applications.md)

How to launch an application with a resolved environment using `launch()`, and
how to use the `Application` object to react to the application's exit state.

### [Publishing](docs/Publishing.md)

How to publish first-party packages with `publish_package()` and third-party
PyPI packages with `pip_publish()`.

### [Caching](docs/caching.md)

How to enable host-machine caching to speed up package resolution when
repositories are on remote storage.
