"""Repository discovery, validated loading, and atomic title updates."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4
from typing import Any

from .models import Task


class TaskStoreError(Exception):
    """An actionable repository or task file error."""


def validate_title(title: str) -> None:
    """Reject blank, multiline, or control-character titles without trimming text."""
    if not isinstance(title, str) or not title.strip():
        raise TaskStoreError("Title must not be empty or whitespace-only.")
    if any(ord(char) < 32 or 127 <= ord(char) < 160 or char in "\u2028\u2029" for char in title):
        raise TaskStoreError("Title must be a single line without control characters.")


def repository_root(start: Path | None = None) -> Path:
    """Ask Git for the checkout root, including linked worktrees."""
    try:
        result = subprocess.run(
            ["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
    except FileNotFoundError as error:
        raise TaskStoreError("Git is required; install Git and make it available on PATH.") from error
    except OSError as error:
        raise TaskStoreError(f"Could not run Git: {error}") from error
    if result.returncode:
        raise TaskStoreError("Run tasktree inside a Git working repository.")
    return Path(result.stdout.strip()).resolve()


class TaskStore:
    """Load task data and atomically save explicit per-task preferences and titles."""

    def __init__(self, root: Path) -> None:
        self.path = root / ".tasktree.json"

    def init(self) -> None:
        """Create exclusively: an existing file is never overwritten."""
        try:
            with self.path.open("x", encoding="utf-8") as stream:
                stream.write('{"schema_version": 1, "tasks": []}\n')
        except FileExistsError as error:
            raise TaskStoreError(f"{self.path} already exists; nothing was changed.") from error
        except OSError as error:
            raise TaskStoreError(f"Cannot create {self.path}: {error}") from error

    def load(self) -> list[Task]:
        """Load schema version 1 and report the location of invalid data."""
        return self._validate(self._read_data())

    def _read_data(self) -> Any:
        try:
            return json.loads(self.path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as error:
            raise TaskStoreError(f"{self.path} is missing. Run 'tasktree init' first.") from error
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise TaskStoreError(f"Cannot read {self.path}: {error}") from error

    def _validate(self, data: Any) -> list[Task]:
        try:
            if not isinstance(data, dict) or set(data) != {"schema_version", "tasks"}:
                raise ValueError("expected an object with schema_version and tasks")
            if type(data["schema_version"]) is not int or data["schema_version"] != 1:
                raise ValueError("schema_version must be the integer 1")
            return self._tasks(data["tasks"], "tasks", set())
        except (ValueError, RecursionError) as error:
            raise TaskStoreError(f"Invalid {self.path}: {error}") from error

    def update_title(self, task_id: str, title: str) -> None:
        """Change only one title in the latest validated file, replacing it atomically."""
        validate_title(title)
        self._update_task(task_id, "title", title)

    def update_expanded(self, task_id: str, expanded: bool) -> None:
        """Atomically update a real task's expansion preference by stable ID."""
        if type(expanded) is not bool:
            raise TaskStoreError("expanded must be a boolean")
        self._update_task(task_id, "expanded", expanded)

    def _update_task(self, task_id: str, field: str, value: Any) -> None:
        data = self._read_data()
        self._validate(data)

        def find(values: list[dict[str, Any]]) -> dict[str, Any] | None:
            for value in values:
                if value["id"] == task_id:
                    return value
                found = find(value["children"])
                if found is not None:
                    return found
            return None

        task = find(data["tasks"])
        if task is None:
            raise TaskStoreError(f"Task {task_id!r} no longer exists in {self.path}.")
        task[field] = value
        self._write_data(data, field)

    def create_task(self, parent_id: str | None, index: int, title: str) -> Task:
        """Insert a new stable ID at the captured sibling position, atomically."""
        validate_title(title)
        data = self._read_data()
        self._validate(data)
        ids: set[str] = set()
        parent = None
        def visit(values):
            nonlocal parent
            for value in values:
                ids.add(value["id"])
                if value["id"] == parent_id:
                    parent = value
                visit(value["children"])
        visit(data["tasks"])
        if parent_id is not None and parent is None:
            raise TaskStoreError("The insertion parent no longer exists.")
        siblings = data["tasks"] if parent_id is None else parent["children"]
        if not 0 <= index <= len(siblings):
            raise TaskStoreError("The insertion position no longer exists.")
        task_id = str(uuid4())
        while task_id in ids:
            task_id = str(uuid4())
        siblings.insert(index, {"id": task_id, "title": title, "children": [], "expanded": True})
        self._write_data(data, "new task")
        return Task(task_id, title)

    def _write_data(self, data: Any, field: str) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".tasktree-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise TaskStoreError(f"Could not save {field}: {error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass  # Never mask the save error if temporary cleanup also fails.

    def _tasks(self, values: Any, location: str, seen: set[str]) -> list[Task]:
        if not isinstance(values, list):
            raise ValueError(f"{location} must be an array")
        tasks = []
        for index, value in enumerate(values):
            here = f"{location}[{index}]"
            if not isinstance(value, dict) or set(value) not in ({"id", "title", "children"}, {"id", "title", "children", "expanded"}):
                raise ValueError(f"{here} must have exactly id, title, and children")
            if type(value.get("expanded", True)) is not bool:
                raise ValueError(f"{here}.expanded must be a boolean")
            for key in ("id", "title"):
                text = value[key]
                if not isinstance(text, str) or not text.strip() or any(
                    ord(char) < 32 or 127 <= ord(char) < 160 or char in "\u2028\u2029"
                    for char in text
                ):
                    raise ValueError(f"{here}.{key} must be a nonempty single-line string without control characters")
            if value["id"] in seen:
                raise ValueError(f"{here}.id duplicates {value['id']!r}")
            seen.add(value["id"])
            tasks.append(Task(value["id"], value["title"], self._tasks(value["children"], f"{here}.children", seen), value.get("expanded", True)))
        return tasks
