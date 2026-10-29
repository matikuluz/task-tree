"""Persistent Textual task viewer with explicit title editing."""

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .action_bar import ActionBar
from .editor import TitleEditor
from .models import Task
from .placement import PlacementModel
from .placement_ui import PlacementScreen
from .search import SearchResult, TaskSearch
from .search_ui import SearchScreen
from .tree import TaskTree
from .store import TaskStore, TaskStoreError, validate_title


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
    Screen { layout: vertical; layers: base editor; }
    #title-editor, #title-editor:focus { layer: editor; border: none; padding: 0; }
    #title-error { layer: editor; background: $surface; }
    #repository { height: 1; text-style: bold; padding: 0 1; }
    #tasks { height: 1fr; padding: 0; overflow-x: hidden; }
    #tasks > .tree--cursor { background: transparent; text-style: bold; }
    #tasks:focus > .tree--cursor { background: transparent; text-style: bold; }
    #empty { height: 1fr; padding: 0 1; }
    #help { height: 1; padding: 0 1; color: $text-muted; }
    """

    def __init__(self, repository_name: str, tasks: list[Task], *, store: TaskStore | None = None) -> None:
        super().__init__()
        self.repository_name = repository_name
        self.tasks = tasks
        self.search = TaskSearch(tasks)
        self.store = store
        self._action_bar = ActionBar(has_task=bool(tasks))
        self._placement_expansions: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        yield Static(Text(f"{self.repository_name} | Root"), id="repository")
        if self.tasks:
            yield TaskTree(self.tasks, self.persist_expansion)
        else:
            yield Static("No tasks yet.", id="empty")
        yield Static("↑↓ Task ⇧↑↓ Sibling Home/End ←→ Action Enter ␠ Fold F Focus Esc R Root / Q", id="help")
        yield self._action_bar

    def _is_browsing(self) -> bool:
        return self.screen is self.screen_stack[0] and (
            self.focused is None or isinstance(self.focused, TaskTree)
        ) and not self.query(TitleEditor)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"search", "previous_action", "next_action", "activate_action"}:
            # Priority browsing bindings must yield to text entry and search results.
            return self._is_browsing()
        if action == "quit" and (isinstance(self.screen, (SearchScreen, PlacementScreen)) or self.query(TitleEditor)):
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

    async def action_activate_action(self) -> None:
        action = self._action_bar.selected_action
        if self._action_bar.available(action):
            if action.requires_task:
                await self.query_one(TaskTree).begin_edit()
                self._update_action_bar()
            else:
                tree = next(iter(self.query(TaskTree)), None)
                model = PlacementModel(
                    self.tasks, tree.scope_path if tree else (),
                    tree.expansion_snapshot() if tree else {},
                    tree.cursor_node.data.id if tree and tree.cursor_node else None,
                )
                anchor = None
                if tree and tree.cursor_node:
                    anchor = (tree.cursor_node.data.id,
                              tree.scrollable_content_region.y + tree.cursor_line - int(tree.scroll_y))
                self._placement_expansions = {}
                self.push_screen(PlacementScreen(self.repository_name, model, anchor=anchor,
                                                save_expansion=self.persist_expansion), self._placement_closed)
                self._update_action_bar()

    def _placement_closed(self, result: None) -> None:
        if self._placement_expansions:
            self.query_one(TaskTree).apply_expansion_changes(self._placement_expansions)
        self.call_after_refresh(self._update_action_bar)

    def persist_expansion(self, task: Task, expanded: bool) -> bool:
        if self.store is None:
            return True
        try:
            self.store.update_expanded(task.id, expanded)
        except TaskStoreError as error:
            self.notify(str(error), severity="error", markup=False)
            return False
        task.expanded = expanded
        if isinstance(self.screen, PlacementScreen):
            self._placement_expansions[task.id] = expanded
        return True

    async def on_input_submitted(self, message: TitleEditor.Submitted) -> None:
        if not isinstance(message.input, TitleEditor):
            return
        message.stop()
        tree = self.query_one(TaskTree)
        title = message.value
        try:
            validate_title(title)
            if self.store is None:
                raise TaskStoreError("No task file is connected to this viewer.")
            self.store.update_title(tree.cursor_node.data.id, title)
        except TaskStoreError as error:
            tree.edit_error(str(error))
            return
        await tree.finish_edit(title)
        self._update_action_bar()

    async def on_title_editor_cancelled(self, message: TitleEditor.Cancelled) -> None:
        await self.query_one(TaskTree).finish_edit()
        self._update_action_bar()

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
