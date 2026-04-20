# Building Packages

Packages that consist of pure Python source and static assets can be published
directly from their source directory with no build step. For packages that
require compilation, code generation, or any transformation of source files
before deployment, Origin supports an optional `build_command` field in
`package.yaml`.

---

## How it works

When `publish_package()` encounters a `build_command` it runs that command as a
shell process in the source directory before doing anything to the repository.
If the command exits with a non-zero return code the publish is aborted
immediately — nothing has been written to the repository and the source
directory is left exactly as it was.

If the command succeeds, the publish continues as normal: the source directory
is copied to a temporary location in the repository, renamed into its final
location, and the git tag is created and pushed.

The build command runs in whatever environment the caller of
`publish_package()` is running in. Origin makes no attempt to construct a
controlled build environment — that is the responsibility of the team or the
CI machine performing the publish.

---

## Defining a build command

Add `build_command` to your `package.yaml`:

```yaml
name: mytool
version: 2.3.0
build_command: "python build.py"
env:
  MYTOOL_ROOT: "//mnt/package/mytool/2.3.0/"
```

The value is any shell command. It runs with the source directory as the
working directory, so relative paths within the script resolve correctly.

If no `build_command` is present the publish skips the build step entirely.
Setting `build_command: null` is equivalent to omitting the field.

---

## Writing a build script

There are no constraints on what the build script does or what language it is
written in, as long as it exits with code `0` on success and a non-zero code
on failure.

A typical Python build script follows this pattern:

```python
# build.py
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def build() -> None:
    # Example: copy python source into a python/ subdirectory
    dest = ROOT / "python"
    dest.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "src", dest, dirs_exist_ok=True)


def compile_extension() -> None:
    # Example: compile a C extension
    result = subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError("Extension compilation failed.")


if __name__ == "__main__":
    build()
    compile_extension()
```

Because the build script runs before the copy step, any files it produces in
the source directory will be included in the published package. Files and
directories excluded by Origin's ignore list (virtual environments, caches,
editor configs, etc.) will still be excluded regardless of whether they were
produced by the build.

---

## What the build step is not

The build step is not a dependency resolver. Origin does not inspect the build
command, does not construct a special environment for it, and does not attempt
to resolve `build_requires` the way Rez does. If your build depends on a
specific version of a compiler or tool, that tool must already be present and
correct in the environment where you run `publish_package()`.

This is a deliberate design choice. Reproducibility is the team's
responsibility — enforced through CI, documented setup scripts, or convention —
not Origin's. Origin provides the mechanism; the team provides the discipline.

---

## Error handling

If the build command fails, `publish_package()` raises `BuildCommandError` with
the exit code and the command string:

```python
from origin.publish import publish_package, BuildCommandError

try:
    publish_package(
        repository="T:/studio/packages",
        source_dir="T:/git/mytool",
    )
except BuildCommandError as e:
    print(f"Build failed: {e}")
```

No cleanup is required on failure — the repository is untouched.
