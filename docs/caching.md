# Caching

By default, Origin resolves packages directly from the repository declared in
`Environment.json`. When caching is enabled, packages are copied to a local
cache directory on the host machine the first time they are resolved. Subsequent
launches read from the cache rather than the source repository, which can
significantly improve startup times when repositories are hosted on a remote
file server.

## Enabling caching

Caching is disabled by default and must be opted into by setting the
`ORIGIN_CACHING_ENABLED` environment variable:

```bash
set ORIGIN_CACHING_ENABLED=ENABLED   # Windows
export ORIGIN_CACHING_ENABLED=ENABLED  # Mac/Linux
```

## Cache location

The cache directory is platform-dependent:

- **Windows:** `C:/origin/cache`
- **Mac/Linux:** `~/.origin/cache`

## Cache key

Cached packages are stored under a path that includes a hash of the source
repository, the package name, and the package version:

```
cache_dir/<repo_hash>/name/version/
```

The repository hash ensures that the same package version from different
repositories is cached separately — a project-level `mytool 2.3.0` and a
studio-level `mytool 2.3.0` will occupy different cache entries and will not
interfere with each other.

## Cache invalidation

Origin does not automatically invalidate the cache when a package changes on
disk. If a package is republished at the same version, the cached copy will
continue to be used. To force a fresh copy, delete the relevant directory from
the cache manually.

## When to use caching

Caching is most beneficial when:

- Repositories are on a network file server with high latency
- Packages are large and slow to read across the network
- The same packages are resolved repeatedly across many launches

Caching adds little value when repositories are on local or fast storage. For
active package development, caching should be disabled or the cache cleared
frequently to ensure the latest version of a package is always used.
