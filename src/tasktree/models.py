"""Task data, independent of the interface."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Task:
    """A task's stable identity, title, and ordered children."""

    id: str
    title: str
    children: list["Task"] = field(default_factory=list)
    expanded: bool = True
