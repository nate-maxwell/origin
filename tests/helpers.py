import json
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import mock_open


def make_mock_open(files: dict[str, dict]) -> MagicMock:
    """
    Return a mock for builtins.open that serves different JSON content per path.

    Args:
        files (dict[str, dict]): Maps file path strings to the dict that
            should be returned when that path is opened and JSON-decoded.
    Returns:
        MagicMock: A mock suitable for patching builtins.open.
    """
    normalized = {str(Path(k)): v for k, v in files.items()}

    def _open(path, *args, **kwargs):
        content = json.dumps(normalized[str(Path(path))])
        return mock_open(read_data=content)()

    return MagicMock(side_effect=_open)
