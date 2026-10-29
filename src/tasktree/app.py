"""Persistent, read-only Textual task viewer."""

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .action_bar import ActionBar
from .models import Task
from .search import SearchResult, TaskSearch
from .search_ui import SearchScreen
from .tree import TaskTree


class TaskTreeApp(App[None]):
    """Show repository tasks without retaining expansion or selection on disk."""

    BINDINGS = [
        Binding("q,Q", "quit", "Quit", priority=True),
        Binding("slash", "search", "Search", priority=True),
        Binding("left", "previous_action", "Previous action", priority=True),
        Binding("right", "next_action", "Next action", priority=True),
        Binding("enter", "activate_action", "Activate action", priority=True),
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
        self._action_bar = ActionBar(has_task=bool(tasks))

    def compose(self) -> ComposeResult:
        yield Static(Text(f"{self.repository_name} | Root"), id="repository")
        if self.tasks:
            yield TaskTree(self.tasks)
        else:
            yield Static("No tasks yet.", id="empty")
        yield Static("↑↓ Task  ⇧↑↓ Sibling  ←→ Action  Enter Run  Space Fold  F Focus  Esc Back  /  Q", id="help")
        yield self._action_bar

    def _is_browsing(self) -> bool:
        return self.screen is self.screen_stack[0] and (
            self.focused is None or isinstance(self.focused, TaskTree)
        )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"search", "previous_action", "next_action", "activate_action"}:
            # Priority browsing bindings must yield to text entry and search results.
            return self._is_browsing()
        if action == "quit" and isinstance(self.screen, SearchScreen):
            return False
        return True

    def action_search(self) -> None:
        self.push_screen(SearchScreen(self.search), self._search_closed)
        self._update_action_bar()

    def _search_closed(self, result: SearchResult | None) -> None:
        if result is not None:
            self.query_one(TaskTree).jump_to(result.task, result.ancestors)
        self.call_after_refresh(self._update_action_bar)

    def action_previous_action(self) -> None:
        self._action_bar.move(-1)

    def action_next_action(self) -> None:
        self._action_bar.move(1)

    def action_activate_action(self) -> None:
        action = self._action_bar.selected_action
        if self._action_bar.available(action):
            self.notify(f"{action.label} — coming soon", timeout=2, markup=False)

    def _update_action_bar(self) -> None:
        # Visibility preserves layout so canceling search cannot shift the tree viewport.
        self._action_bar.visible = self._is_browsing()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        self._update_action_bar()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        self._update_action_bar()

    def on_task_tree_scope_changed(self, message: TaskTree.ScopeChanged) -> None:
        path = " / ".join(["Root", *message.titles])
        self.query_one("#repository", Static).update(Text(f"{self.repository_name} | {path}"))
