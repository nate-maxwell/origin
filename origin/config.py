"""Config file handling and helpers."""

import os
from pathlib import Path
from typing import Optional
from typing import Union

import yaml

YAML_TYPE = Union[dict, list, int, float, bool, str, None]
YAML_EXPORT_TYPE = Union[dict[YAML_TYPE, YAML_TYPE], list[YAML_TYPE]]


def export_data_to_yaml(
    path: Union[str, os.PathLike], data: YAML_EXPORT_TYPE, overwrite: bool = False
) -> None:
    """
    Export dict to YAML file path.

    Args:
        path (Union[str, os.PathLike]): the file path to place the .yaml file.
        data (YAML_EXPORT_TYPE): the data to export into the .yaml file.
        overwrite(bool): to overwrite YAML file if it already exists in path.
            Defaults to False.
    """
    if not overwrite and Path(path).exists():
        return

    with open(path, "w") as outfile:
        yaml.dump(data, outfile, default_flow_style=False, sort_keys=False)


def import_data_from_yaml(filepath: Union[str, os.PathLike]) -> Optional[dict]:
    """
    Import data from a .yaml file.

    Args:
        filepath (Union[str, os.PathLike]): the filepath to the YAML file to
            extract data from.
    Returns:
        any: will return data if YAML file exists, None if it doesn't.
    """
    if not Path(filepath).exists():
        return None

    with open(filepath) as file:
        data = yaml.safe_load(file)
        return data
