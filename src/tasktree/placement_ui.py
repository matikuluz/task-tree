"""Modal placement navigator; cancellation leaves the browsing tree untouched."""

from rich.text import Text
from collections.abc import Callable
from .models import Task
from rich.style import Style
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.geometry import Region
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from .placement import PlacementModel, PlacementRow
from .scrolling import center_task_row
from .editor import TitleEditor
from .store import TaskStore, TaskStoreError, validate_title
from dataclasses import dataclass
from .placement import PlacementEntry


@dataclass(frozen=True)
class CreatedTask:
    task: Task
    destination: PlacementEntry
    path: tuple[Task, ...]
    expanded: dict[str, bool]
    viewport_y: int


class PlacementTree(Tree[PlacementRow], inherit_bindings=False):
    """Use browsing's native connectors and active guides for temporary rows."""

    def __init__(self, delete: bool = False) -> None:
        super().__init__("Placement", id="placement-list")
        self.delete = delete
        self.show_root = False
        self.auto_expand = False
        self.center_scroll = False
        self.guide_depth = 4
        self.root.expand()

    def render_label(self, node: TreeNode[PlacementRow], base_style: Style, style: Style) -> Text:
        selected = node is self.cursor_node
        cursor = "🗑 " if self.delete else "+ "
        text = Text(cursor if selected else "  ", no_wrap=True, overflow="ellipsis")
        label = super().render_label(node, base_style, style)
        if self.delete and node.data and node.data.task and node.data.task.children and not self.screen.model.expanded.get(node.data.task.id, node.data.task.expanded):
            label = Text(label.plain.replace("▼ ", "▶ ", 1))
        text.append_text(label)
        if selected:
            text.stylize("bold")
        return text

    def scroll_to_line(self, line: int, animate: bool = False) -> None:
        center_task_row(self, line)

    def _toggle_node(self, node: TreeNode[PlacementRow]) -> None:
        # Disclosure clicks follow the same model/save path as placement's Space key.
        if self.screen.editor is not None:
            return
        row = node.data
        if row is not None and row.entry is not None and row.entry.kind in ("folder", "task"):
            self.screen.model.selected = self.screen.model.entries.index(row.entry)
            self.screen.action_toggle()


class PlacementScreen(ModalScreen[CreatedTask | None]):
    """Display contextual tasks with one movable insertion row and folder options."""

    BINDINGS = [
        Binding("up", "move(-1)", "Previous", priority=True),
        Binding("down", "move(1)", "Next", priority=True),
        Binding("home", "boundary(False)", "First", priority=True),
        Binding("end", "boundary(True)", "Last", priority=True),
        Binding("space", "toggle", "Expand/collapse folder", priority=True),
        Binding("enter", "activate", "Choose", priority=True),
        Binding("escape", "cancel", "Cancel Add", priority=True),
        Binding("f,F,r,R,slash,left,right,shift+up,shift+down,tab,shift+tab", "stay", "", show=False, priority=True),
    ]
    DEFAULT_CSS = """
    PlacementScreen { layout: vertical; background: $surface; }
    #placement-path { height: 1; padding: 0 1; text-style: bold; }
    #placement-list { height: 1fr; border: none; padding: 0; overflow-x: hidden; }
    #placement-list > .tree--cursor,
    #placement-list:focus > .tree--cursor { background: transparent; text-style: none; }
    #placement-list > .tree--highlight-line { background: transparent; }
    #placement-help { height: 1; color: $text-muted; }
    #creation-error { background: $surface; }
    """

    def __init__(self, repository_name: str, model: PlacementModel, *, anchor: tuple[str, int] | None = None,
                 save_expansion: Callable[[Task, bool], bool] | None = None,
                 store: TaskStore | None = None) -> None:
        super().__init__()
        self.repository_name = repository_name
        self.model = model
        self._anchor = anchor
        self._centering_started = False
        self._save_expansion = save_expansion
        self.store = store
        self.editor: TitleEditor | None = None
        self.destination: PlacementEntry | None = None
        self._draft_error: Static | None = None
        self._saving = False

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return self.editor is None or action == "cancel"

    def compose(self) -> ComposeResult:
        yield Static("", id="placement-path")
        yield PlacementTree(self.model.delete)
        yield Static(f"{'Delete' if self.model.delete else 'Add'}: ↑↓ Move Home/End Enter Choose Space Fold Esc Cancel | ▶ Enter folder", id="placement-help")

    def on_mount(self) -> None:
        self.query_one(PlacementTree).focus(scroll_visible=False)
        self._render_entries()
        self.call_after_refresh(self._keep_selection_visible)

    def _label(self, row: PlacementRow) -> Text:
        selected = row.entry == self.model.current
        text = Text(no_wrap=True, overflow="ellipsis")
        if row.task is not None:
            text.append(row.task.title)
            if selected and row.entry is not None and row.entry.kind == "folder":
                text.append("  [Enter folder]")
        elif row.entry.kind == "folder":
            text.append(f"{row.entry.task.title}  [Enter folder]")
        elif row.entry.kind == "back":
            text.append("Go back")
        else:
            text.append("Add task here")
        return text

    def _render_entries(self, *, preserve_scroll: bool = False) -> None:
        tree = self.query_one(PlacementTree)
        scroll = tree.scroll_y
        tree.unselect()
        tree.clear()
        rows = [row for row in self.model.rows if
                (row.entry is None or row.entry.kind != "insert" or row.entry == self.model.current)
                and not (self.model.delete and row.entry is not None and
                         row.entry.kind == "folder" and row.entry != self.model.current)
                and not (self.model.delete and self.model.current.kind == "folder" and
                         row.entry is not None and row.entry.kind == "task" and
                         row.task.id == self.model.current.task.id)]
        parents = [tree.root]
        selected = None
        for row in rows:
            node = parents[row.depth].add(
                self._label(row), row,
                expand=(True if self.model.delete else self.model.expanded.get(row.task.id, True)) if row.task else True,
                allow_expand=bool(row.task and row.task.children),
            )
            parents = [*parents[:row.depth + 1], node]
            if row.entry == self.model.current:
                selected = node
        tree.get_node_at_line(0)  # Build native connector geometry before restoring the cursor.
        tree.scroll_to(y=scroll, animate=False, immediate=True, force=True)
        tree.cursor_line = selected.line
        if self.model.current.kind == "insert" and selected.parent is not tree.root:
            # Textual 8.2.8 uses this visual flag to color a branch's native guides.
            # The cursor stays on the temporary row; task data and labels are unaffected.
            selected.parent._selected = True
        if preserve_scroll:
            tree.scroll_to_region(Region(0, tree.cursor_line, 1, 1), animate=False,
                                  immediate=True, force=True, x_axis=False)
        elif self._centering_started:
            tree.scroll_to_line(tree.cursor_line, animate=False)
        tree.refresh()
        path = " / ".join(["Root", *(task.title for task in self.model.path)])
        self.query_one("#placement-path", Static).update(Text(f"{self.repository_name} | {path} | {'Delete' if self.model.delete else 'Add'}"))

    def action_move(self, delta: int) -> None:
        self._centering_started = True
        self.model.move(delta)
        self._render_entries()

    def action_boundary(self, end: bool) -> None:
        self._centering_started = True
        self.model.boundary(end)
        self._render_entries()

    def action_toggle(self) -> None:
        entry = self.model.current
        if entry.kind in ("folder", "task") and entry.task.children and self._save_expansion is not None:
            previous = self.model.expanded.setdefault(entry.task.id, entry.task.expanded)
            expanded = not previous
            if not self._save_expansion(entry.task, expanded):
                return
        self.model.toggle()
        self._render_entries(preserve_scroll=True)

    async def action_activate(self) -> None:
        self._centering_started = True
        if self.model.delete and self.model.current.kind == "task":
            self.notify("Deletion — coming soon", timeout=2, markup=False)
            return
        if not self.model.delete and self.model.current.kind == "task":
            return
        if self.model.current.kind != "insert":
            self.model.enter()
            self._render_entries()
            return
        self.destination = self.model.current
        self.editor = TitleEditor("")
        self._draft_error = Static("", id="creation-error", markup=False)
        self._draft_error.styles.position = "absolute"
        self._draft_error.styles.layer = "editor"
        self._draft_error.styles.color = "red"
        self._draft_error.styles.height = 1
        self._draft_error.display = False
        await self.mount(self.editor, self._draft_error)
        tree = self.query_one(PlacementTree)
        tree.cursor_node.set_label(Text(""))
        self._position_editor()
        self.editor.focus(scroll_visible=False)
        self.query_one("#placement-help", Static).update("Enter Save task  Esc Cancel Add")

    def _position_editor(self) -> None:
        if self.editor is not None:
            tree = self.query_one(PlacementTree)
            row = tree.cursor_node.data
            x = tree.scrollable_content_region.x + row.depth * tree.guide_depth + 2
            y = tree.scrollable_content_region.y + tree.cursor_line - int(tree.scroll_y)
            self.editor.styles.offset = (x, y)
            self.editor.styles.width = max(1, tree.scrollable_content_region.right - x)
            if self._draft_error is not None:
                error_y = y + 1 if y + 1 < tree.scrollable_content_region.bottom else max(tree.scrollable_content_region.y, y - 1)
                self._draft_error.styles.offset = (x, error_y)
                self._draft_error.styles.width = self.editor.styles.width

    async def on_input_submitted(self, message: TitleEditor.Submitted) -> None:
        message.stop()
        if self._saving:
            return
        self._saving = True
        try:
            validate_title(message.value)
            if self.store is None:
                raise TaskStoreError("No task file is connected to this viewer.")
            entry = self.destination
            parent_id = entry.ancestors[-1].id if entry.ancestors else None
            task = self.store.create_task(parent_id, entry.index, message.value)
        except TaskStoreError as error:
            self._saving = False
            self._draft_error.update(str(error))
            self._draft_error.display = True
            return
        tree = self.query_one(PlacementTree)
        self.dismiss(CreatedTask(task, entry, self.model.path, dict(self.model.expanded),
                                tree.scrollable_content_region.y + tree.cursor_line - int(tree.scroll_y)))

    def on_title_editor_cancelled(self, message: TitleEditor.Cancelled) -> None:
        message.stop()
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss()

    def action_stay(self) -> None:
        pass

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._keep_selection_visible)

    def _keep_selection_visible(self) -> None:
        if self.editor is not None:
            self._position_editor()
            return
        tree = self.query_one(PlacementTree)
        if self._centering_started:
            tree.scroll_to_line(tree.cursor_line, animate=False)
            return
        if self._anchor is not None:
            task_id, viewport_y = self._anchor
            for line in range(tree.last_line + 1):
                row = tree.get_node_at_line(line).data
                if row.task is not None and row.task.id == task_id:
                    tree.scroll_to(y=line + tree.scrollable_content_region.y - viewport_y,
                                   animate=False, immediate=True, force=True)
                    break
            self._anchor = None
        tree.scroll_to_region(Region(0, tree.cursor_line, 1, 1), animate=False,
                              immediate=True, force=True, x_axis=False)
