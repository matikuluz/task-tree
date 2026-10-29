"""Shared task-area scrolling with natural content limits."""

from textual.widgets import Tree


def center_task_row(tree: Tree, line: int) -> None:
    """Centre a row immediately; Textual clamps at the actual content boundaries."""
    if line >= 0 and tree.scrollable_content_region.height > 0:
        midpoint = (tree.scrollable_content_region.height - 1) // 2
        tree.scroll_to(y=line - midpoint, animate=False, immediate=True, force=True)
