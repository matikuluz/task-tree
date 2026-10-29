"""Small adaptations to Textual's tree rendering and keyboard bindings."""

from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from .models import Task


class TaskTree(Tree[Task], inherit_bindings=False):
    """Navigate Textual's visible rows with only the milestone's task keys."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("shift+up", "cursor_previous_sibling", "Previous sibling", show=False),
        Binding("shift+down", "cursor_next_sibling", "Next sibling", show=False),
        Binding("space", "toggle_node", "Expand/collapse", show=False),
    ]

    def __init__(self, tasks: list[Task]) -> None:
        super().__init__("Tasks", id="tasks")
        self.show_root = False
        self.auto_expand = False
        self.center_scroll = False
        self.guide_depth = 4
        self.root.expand()
        self._add_tasks(self.root, tasks)

    def _add_tasks(self, parent: TreeNode[Task], tasks: list[Task]) -> None:
        for task in tasks:
            node = parent.add(
                Text(task.title), task, expand=True, allow_expand=bool(task.children)
            )
            self._add_tasks(node, task.children)

    def on_mount(self) -> None:
        self.focus()
        self.move_cursor_to_line(0)

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
