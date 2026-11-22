"""The category tree behind the category dropdown and the new-category
screen: which categories exist, which match a typed fragment, and what
adding a new one would create.

No urwid in here, so everything is testable without a terminal.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from typeguard import typechecked

from tui_labeller.categories.category_yaml import (
    load_categories,
    save_categories,
)

SEPARATOR = ":"
WILDCARD = "*"
# Two sibling names this alike are probably the same category misspelt.
SIMILARITY_CUTOFF = 0.8
_SEGMENT = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class AdditionPlan:
    """What adding ``text`` under ``parent`` would do."""

    parent: str
    full_path: str
    created: Tuple[str, ...]
    # Set when nothing may be created (empty name, bad characters, ...).
    error: Optional[str]
    already_exists: bool
    # Existing siblings a new name resembles: probably a typo or duplicate.
    look_alikes: Tuple[str, ...]
    # The same name in another branch: information, not a problem.
    same_name_elsewhere: Tuple[str, ...]


@typechecked
def _join(*, parent: str, name: str) -> str:
    return f"{parent}{SEPARATOR}{name}" if parent else name


@typechecked
def _resembles(*, new: str, existing: str) -> bool:
    if new == existing:
        return False
    if new.startswith(existing) or existing.startswith(new):
        return True
    return SequenceMatcher(None, new, existing).ratio() >= SIMILARITY_CUTOFF


@typechecked
def _contains_in_order(*, path: str, chunks: List[str]) -> bool:
    position = 0
    for chunk in chunks:
        found = path.find(chunk, position)
        if found < 0:
            return False
        position = found + len(chunk)
    return True


@typechecked
def _rank(*, path: str, query: str, chunks: List[str]) -> int:
    """0 exact, 1 path starts with it, 2 a segment starts with it, 3 other."""
    first = chunks[0]
    if path == query:
        return 0
    if path.startswith(first):
        return 1
    if f"{SEPARATOR}{first}" in f"{SEPARATOR}{path}":
        return 2
    return 3


@typechecked
def _insert(*, tree: Dict[Any, Any], segments: List[str]) -> List[str]:
    """Create the missing nodes along *segments*; return their paths."""
    created: List[str] = []
    node = tree
    walked: List[str] = []
    for segment in segments:
        walked.append(segment)
        if segment not in node:
            node[segment] = {}
            created.append(SEPARATOR.join(walked))
        elif not isinstance(node[segment], dict):
            # A bare ``name:`` leaf (None) becomes a parent.
            node[segment] = {}
        node = node[segment]
    return created


class CategoryStore:
    """A view on the category tree, optionally backed by the categories file.

    *hierarchy* is shared with whoever passed it in (the config's
    category namespace): additions are made in place, so they see them
    too.
    """

    @typechecked
    def __init__(
        self, *, hierarchy: Dict[Any, Any], yaml_path: Optional[str] = None
    ) -> None:
        self._hierarchy = hierarchy
        self._yaml_path = yaml_path

    @typechecked
    def _children_of(self, *, path: str) -> Optional[Dict[Any, Any]]:
        """The child mapping of *path* ('' is the root), None if absent."""
        node: Any = self._hierarchy
        if path:
            for segment in path.split(SEPARATOR):
                if not isinstance(node, dict) or segment not in node:
                    return None
                node = node[segment]
        return node if isinstance(node, dict) else {}

    @typechecked
    def paths(self) -> List[str]:
        """Every category, parents included, in tree order (siblings
        alphabetical, children directly under their parent)."""
        found: List[str] = []

        def walk(node: Dict[Any, Any], parent: str) -> None:
            for name in sorted(key for key in node if isinstance(key, str)):
                path = _join(parent=parent, name=name)
                found.append(path)
                child = node[name]
                if isinstance(child, dict):
                    walk(child, path)

        walk(self._hierarchy, "")
        return found

    @typechecked
    def exists(self, *, path: str) -> bool:
        wanted = path.strip().lower()
        if not wanted:
            return False
        return self._children_of(path=wanted) is not None

    @typechecked
    def children(self, *, path: str) -> List[str]:
        """Child names of *path*, alphabetical; '' is the root."""
        node = self._children_of(path=path.strip().lower())
        if node is None:
            return []
        return sorted(key for key in node if isinstance(key, str))

    @typechecked
    def matches(self, *, text: str) -> List[str]:
        """Categories containing *text*, best first.

        ``*`` splits the text into chunks that must occur in that order.
        Empty text matches everything.
        """
        query = text.strip().lower()
        all_paths = self.paths()
        chunks = [chunk for chunk in query.split(WILDCARD) if chunk]
        if not chunks:
            return all_paths
        ranked = [
            (_rank(path=path, query=query, chunks=chunks), index, path)
            for index, path in enumerate(all_paths)
            if _contains_in_order(path=path, chunks=chunks)
        ]
        return [path for _, _, path in sorted(ranked)]

    @typechecked
    def deepest_existing_ancestor(self, *, path: str) -> Tuple[str, str]:
        """Split *path* into (the part that exists, the rest)."""
        segments = [
            segment
            for segment in (
                part.strip() for part in path.lower().split(SEPARATOR)
            )
            if segment
        ]
        existing = 0
        for end in range(1, len(segments) + 1):
            if not self.exists(path=SEPARATOR.join(segments[:end])):
                break
            existing = end
        return (
            SEPARATOR.join(segments[:existing]),
            SEPARATOR.join(segments[existing:]),
        )

    @typechecked
    def plan_addition(self, *, parent: str, text: str) -> AdditionPlan:
        """Preview adding *text* (may contain ':') under *parent* ('' is the
        root).

        Nothing is changed.
        """
        parent = parent.strip().lower()
        raw = text.strip().lower()

        def failed(message: str) -> AdditionPlan:
            return AdditionPlan(
                parent=parent,
                full_path="",
                created=(),
                error=message,
                already_exists=False,
                look_alikes=(),
                same_name_elsewhere=(),
            )

        if not raw:
            return failed("Type a name for the new category.")
        segments = raw.split(SEPARATOR)
        if any(segment == "" for segment in segments):
            return failed(f"A name is missing next to '{SEPARATOR}'.")
        for segment in segments:
            if not _SEGMENT.match(segment):
                return failed(f"Use only a-z, 0-9 and _ in '{segment}'.")
        if parent and not self.exists(path=parent):
            return failed(f"'{parent}' does not exist.")

        all_paths = self.paths()
        created: List[str] = []
        look_alikes: List[str] = []
        elsewhere: List[str] = []
        walked = parent
        for segment in segments:
            child = _join(parent=walked, name=segment)
            if not self.exists(path=child):
                created.append(child)
                # A parent that is itself new has no siblings to resemble.
                for sibling in self.children(path=walked):
                    if _resembles(new=segment, existing=sibling):
                        look_alikes.append(_join(parent=walked, name=sibling))
                elsewhere.extend(
                    path
                    for path in all_paths
                    if path.split(SEPARATOR)[-1] == segment
                )
            walked = child
        return AdditionPlan(
            parent=parent,
            full_path=walked,
            created=tuple(created),
            error=None,
            already_exists=not created,
            look_alikes=tuple(look_alikes),
            same_name_elsewhere=tuple(dict.fromkeys(elsewhere)),
        )

    @typechecked
    def add(self, *, path: str) -> List[str]:
        """Create *path* and its missing parents; return the created paths.

        With a categories file: the file is read again first, so an edit made
        in an editor meanwhile is kept, then saved, and only then is the
        shared tree updated.  A failed save changes nothing.
        """
        plan = self.plan_addition(parent="", text=path)
        if plan.error is not None:
            raise ValueError(plan.error)
        segments = plan.full_path.split(SEPARATOR)

        if self._yaml_path is None:
            return _insert(tree=self._hierarchy, segments=segments)

        fresh = load_categories(yaml_path=self._yaml_path)
        created = _insert(tree=fresh, segments=segments)
        if created:
            save_categories(yaml_path=self._yaml_path, hierarchy=fresh)
        self._hierarchy.clear()
        self._hierarchy.update(fresh)
        return created
