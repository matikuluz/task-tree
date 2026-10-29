"""Persistent, read-only Textual task viewer."""

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .models import Task
from .search import SearchResult, TaskSearch
from .search_ui import SearchScreen
from .tree import TaskTree


class TaskTreeApp(App[None]):
    """Show repository tasks without retaining expansion or selection on disk."""

    BINDINGS = [
        Binding("q,Q", "quit", "Quit", priority=True),
        Binding("slash", "search", "Search", priority=True),
    ]
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
        self.search = TaskSearch(tasks)

    def compose(self) -> ComposeResult:
        yield Static(Text(f"{self.repository_name} | Root"), id="repository")
        if self.tasks:
            yield TaskTree(self.tasks)
        else:
            yield Static("No tasks yet.", id="empty")
        yield Static("↑/↓ Move  Shift+↑/↓ Sibling  Space Toggle  F Focus  Esc Back  / Search  Q Quit", id="help")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "search":
            # A priority binding consumes the opening slash, but must yield to text entry.
            return not isinstance(self.screen, SearchScreen) and (
                self.focused is None or isinstance(self.focused, TaskTree)
            )
        if action == "quit" and isinstance(self.screen, SearchScreen):
            return False
        return True

    def action_search(self) -> None:
        self.push_screen(SearchScreen(self.search), self._search_closed)

    def _search_closed(self, result: SearchResult | None) -> None:
        if result is not None:
            self.query_one(TaskTree).jump_to(result.task, result.ancestors)

    def on_task_tree_scope_changed(self, message: TaskTree.ScopeChanged) -> None:
        path = " / ".join(["Root", *message.titles])
        self.query_one("#repository", Static).update(Text(f"{self.repository_name} | {path}"))
