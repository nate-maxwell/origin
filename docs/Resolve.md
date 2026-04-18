# EnvironmentResolver

Takes an `EnvironmentConfig` and resolves one or more loadouts into a
`ResolvedEnvironment`. The resolver handles the full resolution pipeline:

- Expands loadouts recursively, flattening nested loadout references into an
  ordered, deduplicated list of package names
- Looks up each package version from the `packages` section of the config
- Searches repositories in order to locate the versioned package directory on disk
- Reads and parses the `package.yaml` from the located directory
- Prepends the package root to `PYTHONPATH`
- Merges the package's `env` contributions into the accumulating environment

```python
import origin

ENVIRONMENT_CONFIG = "T:/facility/projects/MY_PROJECT/Environment.json"
env_cfg = origin.EnvironmentConfig.from_file(ENVIRONMENT_CONFIG)
resolver = origin.EnvironmentResolver(env_cfg)
resolved = resolver.resolve(["some_loadout"])

for i in resolved.packages:
    print(i.root)
```

Packages that appear in multiple loadouts are resolved only once. The resolver
raises `VersionNotSpecifiedError` if a package in the loadout has no entry in
the `packages` section, and `PackageNotFoundError` if the versioned directory
cannot be found in any repository.

When caching is enabled, located packages are copied to the local cache before
being used. The cache key includes a hash of the source repository path, ensuring
that the same package version from different repositories is cached separately.

## ResolvedEnvironment

The output of a single `resolve()` call. Contains the fully built environment
dictionary, ready to pass directly to `subprocess.Popen(env=...)`, and the
ordered list of resolved `Package` instances in resolution order.

The environment dictionary is a complete, self-contained snapshot — it does not
require merging with `os.environ` unless you explicitly pass `os.environ` as the
`base_env`. By default, `base_env` is set to the current process environment,
so all system variables are inherited unless you explicitly pass an empty dict.
