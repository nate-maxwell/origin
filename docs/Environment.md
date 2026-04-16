# Environment Config

The `Environment.json` file is the project configuration file. Each project has
its own `Environment.json` that declares the authoritative version of every
package available to that project and defines the loadouts used to launch
applications. Multiple projects can share repositories — their `Environment.json`
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

```json
"repositories": [
    "T:/shows/MYPROJECT/packages",
    "T:/studio/packages"
]
```

## packages

A flat mapping of package names to version strings. This is the authoritative
list of which version of each package this project uses. Every package referenced
in a loadout must have an entry here.

```json
"packages": {
    "pipelinecore": "1.2.0",
    "mytool": "2.3.0",
    "PySide6": "6.11.0"
}
```

## loadouts

A mapping of loadout names to lists of package names or other loadout names.
Each loadout defines the set of packages to resolve when launching a specific
application. Loadouts can reference other loadouts by name, allowing shared
base configurations to be declared once and reused across multiple applications.

```json
"loadouts": {
    "base": ["pipelinecore"],
    "nuke": ["base", "colour", "mytool"],
    "unreal": ["base", "PySide6"]
}
```
