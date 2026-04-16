# Applications and Launching

### launch()

Reads an `Environment.json`, resolves the specified loadout, and launches an
executable in the resulting environment. Returns an `Application` instance.

```python
import origin

app = origin.launch(
    executable="C:/path/to/some_program.exe",
    environment_config="V:/projects/MY_PROJECT/Environment.json",
    loadout="some_loadout",
)
```

Accepts an optional `base_env` to control what the resolved environment is
layered on top of. By default, the current process environment is used as the
base, so all system variables are inherited. Pass an empty dict to launch with
only the resolved package environment and nothing else.

All environment variable customisation flows through packages — `launch()` does
not accept ad-hoc environment overrides. If a variable needs to be set for an
application, it belongs in a `Package.json`.

### Application

A thin wrapper around `subprocess.Popen` returned by `launch()`. Holds the
executable path, the loadout name, the underlying process handle, and the
`ResolvedEnvironment` the application was launched with.

#### wait()

Blocks until the application exits and returns its exit code. Use this when
you want to perform follow-up actions after the application closes.

#### poll()

Checks whether the application has exited without blocking. Returns the exit
code if the process has finished, or `None` if it is still running.

#### has_crashed

A property that returns `True` if the application has exited with a non-zero
exit code. Intended to be checked after `wait()` to determine whether follow-up
action is needed, such as submitting a crash report or launching a ticket
submitter.

```python
import origin

app = origin.launch(
    executable="C:/path/to/some_program.exe",
    environment_config="V:/projects/MYPROJECT/Environment.json",
    loadout="some_loadout",
)

app.wait()
if app.has_crashed:
    submit_crash_ticket(app)
```

The `ResolvedEnvironment` being available on the `Application` instance is
useful for crash reporting — you know exactly which package versions were loaded
and which environment variables were set when the application went down.
