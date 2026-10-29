"""Temporary insertion positions and folder navigation, separate from task data."""

from dataclasses import dataclass
from typing import Literal

from .models import Task


@dataclass(frozen=True, slots=True)
class PlacementEntry:
    """An insertion gap, folder option, or back command; never a persisted task."""

    kind: Literal["insert", "folder", "back"]
    ancestors: tuple[Task, ...]
    index: int = 0
    task: Task | None = None


@dataclass(frozen=True, slots=True)
class PlacementRow:
    """A contextual task row or a temporary selectable entry."""

    depth: int
    entry: PlacementEntry | None = None
    task: Task | None = None


class PlacementModel:
    """Navigate visible gaps and folders without changing the original tree."""

    def __init__(self, tasks: list[Task], path: tuple[Task, ...] = (),
                 expanded: dict[str, bool] | None = None, after_id: str | None = None) -> None:
        self.tasks = tasks
        self.path = path
        self.expanded = dict(expanded or {})
        self.rows: list[PlacementRow] = []
        self.entries: list[PlacementEntry] = []
        self.selected = 0
        self._build()
        if after_id is not None:
            # The gap follows the selected sibling's entire visible subtree.
            for index, entry in enumerate(self.entries):
                if entry.kind == "insert" and entry.index > 0:
                    siblings = entry.ancestors[-1].children if entry.ancestors else self.tasks
                    if siblings[entry.index - 1].id == after_id:
                        self.selected = index
                        break
        elif self.path:
            self.selected = 1  # Before the first child, after Go back.

    @property
    def current(self) -> PlacementEntry:
        return self.entries[self.selected]

    def _build(self) -> None:
        self.rows = []
        if self.path:
            self.rows.append(PlacementRow(0, PlacementEntry("back", self.path)))
        self._walk(self.path[-1].children if self.path else self.tasks, self.path, 0)
        self.entries = [row.entry for row in self.rows if row.entry is not None]

    def _walk(self, tasks: list[Task], ancestors: tuple[Task, ...], depth: int) -> None:
        self.rows.append(PlacementRow(depth, PlacementEntry("insert", ancestors)))
        for index, task in enumerate(tasks):
            entry = PlacementEntry("folder", ancestors, index, task) if task.children else None
            self.rows.append(PlacementRow(depth, entry, task))
            if task.children and self.expanded.get(task.id, True):
                self._walk(task.children, (*ancestors, task), depth + 1)
            self.rows.append(PlacementRow(depth, PlacementEntry("insert", ancestors, index + 1)))

    def move(self, delta: int) -> None:
        self.selected = max(0, min(len(self.entries) - 1, self.selected + delta))

    def boundary(self, end: bool) -> None:
        self.selected = len(self.entries) - 1 if end else 0

    def toggle(self) -> None:
        entry = self.current
        if entry.kind == "folder" and entry.task is not None:
            self.expanded[entry.task.id] = not self.expanded.get(entry.task.id, True)
            self._build()
            self.selected = self.entries.index(entry)

    def enter(self) -> bool:
        """Navigate a folder or Go back; return False for an insertion activation."""
        entry = self.current
        if entry.kind == "folder" and entry.task is not None:
            self.path = (*entry.ancestors, entry.task)
            self._build()
            self.selected = 1
        elif entry.kind == "back":
            exited = self.path[-1]
            self.path = self.path[:-1]
            self._build()
            self.selected = next(index for index, item in enumerate(self.entries)
                                 if item.kind == "folder" and item.task.id == exited.id)
        else:
            return False
        return True
