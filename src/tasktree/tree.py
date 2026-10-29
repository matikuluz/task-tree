"""Small adaptations to Textual's tree rendering and keyboard bindings."""

from rich.style import Style
from collections.abc import Callable
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from .models import Task
from .editor import TitleEditor


class TaskTree(Tree[Task], inherit_bindings=False):
    """Navigate visible task rows and temporary branch scopes."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("home", "scope_boundary(False)", "First visible task", show=False),
        Binding("end", "scope_boundary(True)", "Last visible task", show=False),
        Binding("shift+up", "cursor_previous_sibling", "Previous sibling", show=False),
        Binding("shift+down", "cursor_next_sibling", "Next sibling", show=False),
        Binding("space", "toggle_node", "Expand/collapse", show=False),
        Binding("f,F", "focus_branch", "Focus branch", show=False),
        Binding("escape", "leave_scope", "Back", show=False),
        Binding("r,R", "return_to_root", "Return to root", show=False),
    ]

    class ScopeChanged(Message):
        """Notify the app that the breadcrumb path changed."""

        def __init__(self, titles: list[str]) -> None:
            super().__init__()
            self.titles = titles

    def __init__(self, tasks: list[Task], save_expansion: Callable[[Task, bool], bool] | None = None) -> None:
        super().__init__("Tasks", id="tasks")
        self._tasks = tasks
        self._save_expansion = save_expansion
        self._scope_path: list[Task] = []
        self._expanded: dict[str, bool] = {}
        self.editor: TitleEditor | None = None
        self._edit_error: Static | None = None
        self._edit_scroll = (0.0, 0.0)
        self.show_root = False
        self.auto_expand = False
        self.center_scroll = False
        self.guide_depth = 4
        self.root.expand()
        self._add_tasks(self.root, tasks)

    def _add_tasks(self, parent: TreeNode[Task], tasks: list[Task]) -> None:
        for task in tasks:
            node = parent.add(
                Text(task.title), task, expand=self._expanded.get(task.id, task.expanded),
                allow_expand=bool(task.children),
            )
            self._add_tasks(node, task.children)

    def on_mount(self) -> None:
        self.focus()
        self.move_cursor_to_line(0)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return self.editor is None

    def action_toggle_node(self) -> None:
        node = self.cursor_node
        if node is not None:
            self._toggle_node(node)

    def _toggle_node(self, node: TreeNode[Task]) -> None:
        # The native tree uses this hook for both Space and disclosure clicks.
        if node.data is not None and node.data.children:
            expanded = not node.is_expanded
            if self._save_expansion is None or self._save_expansion(node.data, expanded):
                node.toggle()

    def apply_expansion_changes(self, changes: dict[str, bool]) -> None:
        """Apply saved Add-mode preferences without restoring its temporary scope."""
        self._expanded.update(changes)
        selected = self.cursor_node
        def visit(parent: TreeNode[Task]) -> None:
            for node in parent.children:
                if node.data.id in changes:
                    node.expand() if changes[node.data.id] else node.collapse()
                visit(node)
        visit(self.root)
        self.get_node_at_line(0)
        if selected is not None:
            parent = selected.parent
            while parent is not None and parent is not self.root:
                if not parent.is_expanded:
                    selected = parent
                parent = parent.parent
            self.cursor_line = selected.line

    async def begin_edit(self) -> None:
        """Overlay an input on the title without rebuilding or moving the tree."""
        node = self.cursor_node
        if self.editor is not None or node is None or node.data is None:
            return
        self._edit_scroll = (self.scroll_x, self.scroll_y)
        self.editor = TitleEditor(node.data.title)
        self._edit_error = Static("", id="title-error", markup=False)
        self._edit_error.styles.position = "absolute"
        self._edit_error.styles.height = 1
        self._edit_error.styles.color = "red"
        self._edit_error.display = False
        await self.screen.mount(self.editor, self._edit_error)
        self._position_editor()
        self.editor.focus(scroll_visible=False)
        self.editor.cursor_position = len(self.editor.value)

    def _position_editor(self) -> None:
        node = self.cursor_node
        if self.editor is None or node is None:
            return
        depth = 0
        parent = node.parent
        while parent is not None and parent is not self.root:
            depth += 1
            parent = parent.parent
        # Keep the tree guides, selection marker, and branch disclosure icon visible.
        x = depth * self.guide_depth + 2 + (2 if node.allow_expand else 0)
        x = min(x, max(0, self.scrollable_content_region.width - 2))
        region = self.scrollable_content_region
        y = region.y + self.cursor_line - int(self.scroll_y)
        self.editor.styles.offset = (region.x + x, y)
        self.editor.styles.width = max(1, self.scrollable_content_region.width - x)
        if self._edit_error is not None:
            error_y = y + 1 if y + 1 < region.bottom else max(region.y, y - 1)
            self._edit_error.styles.offset = (region.x + x, error_y)
            self._edit_error.styles.width = max(1, self.scrollable_content_region.width - x)

    def edit_error(self, message: str) -> None:
        if self._edit_error is not None:
            self._edit_error.update(message)
            self._edit_error.display = True

    async def finish_edit(self, title: str | None = None) -> None:
        """Apply a successfully saved title, or discard the input on cancellation."""
        if self.editor is None:
            return
        if title is not None and self.cursor_node is not None:
            self.cursor_node.data.title = title
            self.cursor_node.set_label(Text(title))
        editor, error = self.editor, self._edit_error
        self.editor = None
        self._edit_error = None
        await editor.remove()
        if error is not None:
            await error.remove()
        self.focus(scroll_visible=False)
        self.scroll_to(*self._edit_scroll, animate=False, immediate=True, force=True)

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

    def action_return_to_root(self) -> None:
        """Exit all scopes and select the current task's top-level ancestor."""
        if self._scope_path:
            ancestor = self._scope_path[0]
            self._scope_path.clear()
            self._show_scope(ancestor.id)

    def action_scope_boundary(self, end: bool) -> None:
        """Select a visible scope boundary without changing expansion or wrapping."""
        last = self.last_line
        target = last if end else 0
        if last >= 0 and self.cursor_line != target:
            self.cursor_line = target
            self.scroll_to_line(target, animate=False)

    def _remember_expansion(self, parent: TreeNode[Task]) -> None:
        for node in parent.children:
            assert node.data is not None
            self._expanded[node.data.id] = node.is_expanded
            self._remember_expansion(node)

    @property
    def scope_path(self) -> tuple[Task, ...]:
        return tuple(self._scope_path)

    def expansion_snapshot(self) -> dict[str, bool]:
        """Copy current and hidden branch states for a temporary navigation mode."""
        self._remember_expansion(self.root)
        return dict(self._expanded)

    def jump_to(self, task: Task, ancestors: tuple[Task, ...]) -> None:
        """Reveal a search destination using its actual ancestor chain."""
        self._remember_expansion(self.root)
        for ancestor in ancestors:
            self._expanded[ancestor.id] = True
        self._scope_path = list(ancestors)
        if task.children:
            self._expanded[task.id] = True
            self._scope_path.append(task)
        self._show_scope(None if task.children else task.id, remember_expansion=False)

    def _show_scope(self, selected_id: str | None = None, *, remember_expansion: bool = True) -> None:
        if remember_expansion:
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
        self.call_after_refresh(self._position_editor)

    def _scroll_cursor_into_view(self) -> None:
        # A key may have moved the cursor since the resize was queued.
        self.scroll_to_line(self.cursor_line, animate=False)
