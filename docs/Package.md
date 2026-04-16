# Package

A fully resolved package, produced by the `EnvironmentResolver` after reading a
`Package.json` from disk. Holds the package name, version, root path on disk,
and its environment variable contributions. The package root is automatically
prepended to `PYTHONPATH`, making the package importable in the launched
application without any additional configuration.

## Config

The `Package.json` file is a package's own declaration of what it contributes
to the environment. Each versioned package directory on disk contains a
`Package.json` alongside the package code. Values in the `env` section are
taken as literal strings with no token expansion — if a package needs to
reference a path, the full path should be written explicitly.

#### name

The canonical name of the package. Must match the name used in the
`Environment.json` `packages` section.

#### version

The version string for this package. Should match the version declared in the
`Environment.json` `packages` section. Can be any string — Origin does not
enforce semantic versioning, though `major.minor.patch` is recommended.

#### env

A mapping of environment variable names to their values. Every variable declared
here will be set in the environment before the application launches. Values are
literal strings — no token expansion is performed.

```json
{
    "name": "mytool",
    "version": "2.3.0",
    "authors": ["Marty McFly"],
    "description": "My super cool python tool.",
    "env": {
        "MYTOOL_ROOT": "T:/packages/mytool/2.3.0",
        "MYTOOL_PLUGINS": "T:/packages/mytool/2.3.0/plugins"
    }
}
```

#### Automatic version variables

Origin automatically injects version environment variables for every package,
derived from the version string in `Package.json`. For a package named `mytool`
at version `2.3.0`:

```
ORIGIN_MYTOOL_VERSION=2.3.0
ORIGIN_MYTOOL_MAJOR_VERSION=2
ORIGIN_MYTOOL_MINOR_VERSION=3
ORIGIN_MYTOOL_PATCH_VERSION=0
```

If the version string does not contain enough parts, missing components default
to `x`. For example, a version of `2.3` would produce
`ORIGIN_MYTOOL_PATCH_VERSION=x`.
