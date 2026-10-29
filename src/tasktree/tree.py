"""Small adaptations to Textual's tree rendering and keyboard bindings."""

from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from .models import Task


class TaskTree(Tree[Task], inherit_bindings=False):
    """Navigate visible task rows and temporary branch scopes."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("shift+up", "cursor_previous_sibling", "Previous sibling", show=False),
        Binding("shift+down", "cursor_next_sibling", "Next sibling", show=False),
        Binding("space", "toggle_node", "Expand/collapse", show=False),
        Binding("f,F", "focus_branch", "Focus branch", show=False),
        Binding("escape", "leave_scope", "Back", show=False),
    ]

    class ScopeChanged(Message):
        """Notify the app that the breadcrumb path changed."""

        def __init__(self, titles: list[str]) -> None:
            super().__init__()
            self.titles = titles

    def __init__(self, tasks: list[Task]) -> None:
        super().__init__("Tasks", id="tasks")
        self._tasks = tasks
        self._scope_path: list[Task] = []
        self._expanded: dict[str, bool] = {}
        self.show_root = False
        self.auto_expand = False
        self.center_scroll = False
        self.guide_depth = 4
        self.root.expand()
        self._add_tasks(self.root, tasks)

    def _add_tasks(self, parent: TreeNode[Task], tasks: list[Task]) -> None:
        for task in tasks:
            node = parent.add(
                Text(task.title), task, expand=self._expanded.get(task.id, True),
                allow_expand=bool(task.children),
            )
            self._add_tasks(node, task.children)

    def on_mount(self) -> None:
        self.focus()
        self.move_cursor_to_line(0)

    def action_focus_branch(self) -> None:
        """Hide the selected branch root and show its children in a new scope."""
        node = self.cursor_node
        if node is None or node.data is None or not node.data.children:
            return
        path: list[Task] = []
        while node is not None and node is not self.root:
            assert node.data is not None
            path.append(node.data)
            node = node.parent
        self._scope_path.extend(reversed(path))
        self._show_scope()

    def action_leave_scope(self) -> None:
        """Return to the parent scope and select the branch just exited."""
        if self._scope_path:
            exited = self._scope_path.pop()
            self._show_scope(exited.id)

    def _remember_expansion(self, parent: TreeNode[Task]) -> None:
        for node in parent.children:
            assert node.data is not None
            self._expanded[node.data.id] = node.is_expanded
            self._remember_expansion(node)

    def _show_scope(self, selected_id: str | None = None) -> None:
        self._remember_expansion(self.root)
        self.unselect()
        self.clear()
        tasks = self._scope_path[-1].children if self._scope_path else self._tasks
        self._add_tasks(self.root, tasks)
        # Building visible rows through the public API also updates node line numbers.
        self.cursor_line = 0
        if selected_id is not None:
            for line in range(self.last_line + 1):
                node = self.get_node_at_line(line)
                if node is not None and node.data is not None and node.data.id == selected_id:
                    self.cursor_line = line
                    break
        self.call_after_refresh(self._scroll_cursor_into_view)
        self.post_message(self.ScopeChanged([task.title for task in self._scope_path]))

    def action_cursor_previous_sibling(self) -> None:
        """Select the previous sibling, stopping at the current parent's boundary."""
        node = self.cursor_node
        if node is not None and node.previous_sibling is not None:
            self.cursor_line = node.previous_sibling.line
            self.scroll_to_line(self.cursor_line, animate=False)

    def action_cursor_next_sibling(self) -> None:
        """Select the next sibling without visiting descendants or another parent."""
        node = self.cursor_node
        if node is not None and node.next_sibling is not None:
            self.cursor_line = node.next_sibling.line
            self.scroll_to_line(self.cursor_line, animate=False)

    def render_label(self, node: TreeNode[Task], base_style: Style, style: Style) -> Text:
        selected = node is self.cursor_node
        label = super().render_label(node, base_style, style)
        text = Text("> " if selected else "  ", no_wrap=True, overflow="ellipsis")
        text.append_text(label)
        if selected:
            text.stylize("bold")
        return text

    def on_resize(self, event: events.Resize) -> None:
        # Tree rebuilds its geometry on resize; keep the cursor visible afterwards.
        self.call_after_refresh(self._scroll_cursor_into_view)

    def _scroll_cursor_into_view(self) -> None:
        # A key may have moved the cursor since the resize was queued.
        self.scroll_to_line(self.cursor_line, animate=False)
