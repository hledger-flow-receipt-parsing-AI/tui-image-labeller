"""Read and write the categories file in one canonical style.

The file is the user's own bookkeeping data, so a save is verified before
anything is replaced and the replacement is atomic: either the complete new
file is in place, or the original is untouched.
"""

import os
import shutil
import tempfile
from typing import Any, Dict, List

import yaml
from typeguard import typechecked

INDENT = "  "


class CategorySaveError(Exception):
    """The categories file could not be read or written safely."""


@typechecked
def normalise_hierarchy(*, hierarchy: Dict[Any, Any]) -> Dict[Any, Any]:
    """Return a copy in which every leaf is an empty dict.

    A leaf may be written as ``name: {}`` or as a bare ``name:`` (None).
    """
    return {
        key: (
            normalise_hierarchy(hierarchy=value)
            if isinstance(value, dict)
            else {}
        )
        for key, value in hierarchy.items()
    }


@typechecked
def _format_key(*, key: Any) -> str:
    """Write a key the way YAML reads it back unchanged ('no' -> "'no'")."""
    dumped: str = yaml.safe_dump(key, width=10**6)
    return dumped.split("\n")[0]


@typechecked
def _dump_lines(*, node: Dict[Any, Any], depth: int) -> List[str]:
    lines: List[str] = []
    for key, value in node.items():
        label = f"{INDENT * depth}{_format_key(key=key)}"
        if isinstance(value, dict) and value:
            lines.append(f"{label}:")
            lines.extend(_dump_lines(node=value, depth=depth + 1))
        else:
            lines.append(f"{label}: {{}}")
    return lines


@typechecked
def dump_categories(*, hierarchy: Dict[Any, Any]) -> str:
    """Canonical text: two-space indent, ``{}`` leaves, key order kept."""
    if not hierarchy:
        return "{}\n"
    return "\n".join(_dump_lines(node=hierarchy, depth=0)) + "\n"


@typechecked
def load_categories(*, yaml_path: str) -> Dict[Any, Any]:
    """Load the categories file as a normalised tree."""
    try:
        with open(yaml_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as error:
        raise CategorySaveError(f"Cannot read {yaml_path}: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CategorySaveError(
            f"{yaml_path} must contain a mapping at the top level."
        )
    return normalise_hierarchy(hierarchy=data)


@typechecked
def save_categories(*, yaml_path: str, hierarchy: Dict[Any, Any]) -> None:
    """Replace the categories file with the canonical text of *hierarchy*.

    Raises CategorySaveError, leaving the original file untouched, when
    the text would not read back as the same tree or the file cannot be
    written.
    """
    wanted = normalise_hierarchy(hierarchy=hierarchy)
    text = dump_categories(hierarchy=wanted)
    try:
        reloaded = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise CategorySaveError(
            f"Refusing to write {yaml_path}: {error}"
        ) from error
    if (
        not isinstance(reloaded, dict)
        or normalise_hierarchy(hierarchy=reloaded) != wanted
    ):
        raise CategorySaveError(
            f"Refusing to write {yaml_path}: it would not read back as the"
            " same categories."
        )

    # Write through a symlink instead of replacing the link itself.
    target = os.path.realpath(yaml_path)
    temp_path = ""
    try:
        descriptor, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(target), prefix=".categories-", suffix=".tmp"
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if os.path.exists(target):
            shutil.copymode(target, temp_path)
        os.replace(temp_path, target)
    except OSError as error:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise CategorySaveError(f"Cannot write {yaml_path}: {error}") from error
