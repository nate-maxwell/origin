# Package Publishing

Origin supports publishing of first-party packages, those you have the sourcecode
for, and publishing third-party packages found on [PyPi](https://pypi.org/).

## publish_package()

Publishes a package from a source directory to a repository. Copies the source
to `repository/name/version/` as defined by the `Package.json` found in the
source directory, then creates and pushes a version tag in the source git
repository. The git step ensures every deployed artifact is traceable to an
exact point in source history.

```python
from origin.publish import publish_package

publish_package(
    repository="T:/studio/packages",
    source_dir="T:/git/mytool",
)
```

The publish will refuse to proceed if the repository has uncommitted changes or
unpushed commits.

After publishing, add the package to your `Environment.json` manually:

```json
"packages": {
    "mytool": "2.3.0"
}
```

### What gets excluded

The following are excluded from the copy:

- Virtual environments (`venv`, `.venv`, `env`, `.env`)
- Python caches (`__pycache__`, `*.pyc`)
- Editor configs (`.vscode`, `.idea`)
- Git metadata (`.git`, `.gitignore`, `.github`)
- Package build artifacts (`*.egg-info`)

## pip_publish()

Downloads a package from PyPI and publishes it to a repository as a single
Origin package. All distributions installed as dependencies are merged into one
directory, mirroring the flat layout of a `site-packages` folder. This is
necessary for packages like PySide6 whose components use relative paths to
locate each other on disk.

```python
from origin import pip_publish

pip_publish(
    repository="T:/studio/packages",
    package_name="requests",
)
```

A specific version can be requested using standard pip version specifier syntax:

```python
origin.pip_publish(
    repository="T:/studio/packages",
    package_name="numpy==1.26.0",
)
```

After publishing, the package is automatically added to the `packages` section
of the `Environment.json` file passed as `environment_config`. The package can
then be referenced in loadouts like any other package.

PyPI packages are generally best published to a studio-level repository rather
than a project repository, since they are not project-specific and can be shared
across all projects.
