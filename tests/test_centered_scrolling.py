import pytest
from textual.widgets import Input

from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.tree import TaskTree
from tasktree.placement_ui import PlacementTree


@pytest.mark.parametrize("focused", [False, True])
async def test_midpoint_both_directions_and_natural_limits(focused):
    values = [Task(str(i), str(i)) for i in range(40)]
    app = TaskTreeApp("Repo", [Task("branch", "Branch", values)] if focused else values)
    async with app.run_test(size=(80, 13)) as pilot:
        if focused:
            await pilot.press("f")
        tree = app.query_one(TaskTree)
        await pilot.pause()
        assert tree.scroll_y == 0
        await pilot.press(*(["down"] * 4))
        assert tree.scroll_y == 0
        await pilot.press("down")
        assert tree.scroll_y == 1
        await pilot.press(*(["down"] * 15))
        assert tree.cursor_line == 20 and tree.scroll_y == 16
        await pilot.press("up")
        assert tree.scroll_y == 15
        await pilot.press("end")
        assert tree.scroll_y == 30
        await pilot.press(*(["up"] * 5))
        assert tree.scroll_y == 30
        await pilot.press("up")
        assert tree.scroll_y == 29
        await pilot.resize_terminal(80, 17)
        await pilot.pause()
        assert tree.scroll_y == 26  # 40 content rows, 14 viewport rows
        await pilot.press("home")
        assert tree.scroll_y == 0


async def test_short_lists_and_editing_remain_stationary():
    app = TaskTreeApp("Repo", [Task(str(i), str(i)) for i in range(3)])
    async with app.run_test(size=(80, 13)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("end", "home", "down")
        assert tree.scroll_y == 0
        await pilot.press("right", "enter")
        before = tree.scroll_y
        await pilot.press("home", "end")
        await pilot.resize_terminal(70, 15)
        await pilot.pause()
        assert tree.scroll_y == before
        await pilot.press("escape")


async def test_add_preserves_entry_view_then_centers_navigation():
    app = TaskTreeApp("Repo", [Task(str(i), str(i)) for i in range(40)])
    async with app.run_test(size=(80, 13)) as pilot:
        browsing = app.query_one(TaskTree)
        await pilot.press(*(["down"] * 15))
        old_y = browsing.cursor_line - int(browsing.scroll_y)
        await pilot.press("2")
        await pilot.pause()
        tree = app.screen.query_one(PlacementTree)
        assert tree.cursor_line - 1 - int(tree.scroll_y) == old_y
        await pilot.press("down")
        assert tree.cursor_line - int(tree.scroll_y) == 5  # 11-row Add viewport
        await pilot.press("up")
        assert tree.cursor_line - int(tree.scroll_y) == 5
        await pilot.press("end")
        assert tree.scroll_y == tree.max_scroll_y
        await pilot.press("home")
        assert tree.scroll_y == 0
