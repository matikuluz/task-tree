"""Persistent, read-only Textual task viewer."""

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .models import Task
from .tree import TaskTree


class TaskTreeApp(App[None]):
    """Show repository tasks without retaining expansion or selection on disk."""

    BINDINGS = [Binding("q,Q", "quit", "Quit", priority=True)]
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { layout: vertical; }
    #repository { height: 1; text-style: bold; padding: 0 1; }
    #tasks { height: 1fr; padding: 0; overflow-x: hidden; }
    #tasks > .tree--cursor { background: transparent; text-style: bold; }
    #tasks:focus > .tree--cursor { background: transparent; text-style: bold; }
    #empty { height: 1fr; padding: 0 1; }
    #help { height: 1; padding: 0 1; color: $text-muted; }
    """

    def __init__(self, repository_name: str, tasks: list[Task]) -> None:
        super().__init__()
        self.repository_name = repository_name
        self.tasks = tasks

    def compose(self) -> ComposeResult:
        yield Static(Text(self.repository_name), id="repository")
        if self.tasks:
            yield TaskTree(self.tasks)
        else:
            yield Static("No tasks yet.", id="empty")
        yield Static("↑/↓ Move   Space Expand/collapse   Q Quit", id="help")
