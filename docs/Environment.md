# Environment Config

The `environment.yaml` file is the project configuration file. Each project has
its own `environment.yaml` that declares the authoritative version of every
package available to that project and defines the loadouts used to launch
applications. Multiple projects can share repositories — their `environment.yaml`
files simply declare different versions of the packages they need.

## name

A string identifying the project this config belongs to. Used in error messages
when a package version cannot be resolved.

## repositories

An ordered list of directory paths to search when locating a package on disk.
The resolver searches repositories from first to last, using the first match it
finds. This allows project-specific packages to shadow studio-level packages —
place the project repository before the studio repository and any package present
in both will resolve to the project version.

```yaml
repositories:
  - T:/project/packages
  - T:/facility/packages
```

## packages

A flat mapping of package names to version strings. This is the authoritative
list of which version of each package this project uses. Every package referenced
in a loadout must have an entry here.

```yaml
packages:
  pipelinecore: 1.2.0
  app_essentials: 1.0.1
  colour: 0.4.2
  service: 15.0.1
  mytool: 2.3.0
```

## loadouts

A mapping of loadout names to lists of package names or other loadout names.
Each loadout defines the set of packages to resolve when launching a specific
application. Loadouts can reference other loadouts by name, allowing shared
base configurations to be declared once and reused across multiple applications.

```yaml
loadouts:
  nuke:
    - colour
    - mytool
    - myapp
  myapp:
    - pipelinecore
    - app_essentials
```
