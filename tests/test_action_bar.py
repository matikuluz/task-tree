from rich.console import Console
import pytest
from textual.widgets import Input, TextArea

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.placement_ui import PlacementScreen
from tasktree.search_ui import SearchScreen
from tasktree.tree import TaskTree
from tasktree.editor import TitleEditor


def tasks():
    return [Task("a", "Branch", [Task("b", "Child"), Task("c", "Other")]), Task("d", "Last")]


async def test_action_order_rendering_wrap_and_task_highlight():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        tree = app.query_one(TaskTree)
        original = tree.cursor_node
        assert bar.render().plain == "[+ Add task] [✎]"
        text = bar.render()
        for index in range(len("[+ Add task]")):
            assert text.get_style_at_offset(Console(), index).bold
        assert not text.get_style_at_offset(Console(), len(text) - 1).bold
        await pilot.press("left")
        assert bar.render().plain == "[+] [✎ Edit task]"
        await pilot.press("left")
        assert bar.selected == 0
        await pilot.press("right", "right")
        assert bar.selected == 0
        assert tree.cursor_node is original
        assert app.focused is tree
        assert tree.render_line(0).text.lstrip().startswith(">")


async def test_action_preserved_by_task_navigation_and_focus():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        tree = app.query_one(TaskTree)
        await pilot.press("right", "down", "down", "up")
        assert tree.cursor_node.data.id == "b"
        assert bar.selected == 1
        await pilot.press("shift+down", "shift+up", "up", "f")
        assert tree.cursor_node.data.id == "b"
        assert bar.selected == 1 and bar.visible
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "a"
        assert bar.selected == 1 and bar.visible


async def test_empty_tree_skips_unavailable_edit_and_activates_add():
    app = TaskTreeApp("Repo", [])
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        assert bar.visible and bar.selected == 0
        style = bar.render().get_style_at_offset(Console(), len(bar.render()) - 1)
        assert style.dim and style.strike
        await pilot.press("right", "right", "left", "left", "enter", "enter")
        assert bar.selected == 0
        assert isinstance(app.screen, PlacementScreen)
        assert app.screen.query_one(TitleEditor).value == ""


async def test_add_activation_opens_empty_draft_and_cancels():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("enter", "enter", "down")
        assert tree.cursor_node.data.id == "a"
        assert isinstance(app.screen, PlacementScreen)
        assert app.screen.query_one(TitleEditor).value == ""
        await pilot.press("escape")
        assert app.query_one(ActionBar).visible


async def test_search_hides_bar_disables_actions_and_restores_selection():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        await pilot.press("right", "slash")
        assert isinstance(app.screen, SearchScreen)
        assert not bar.visible
        field = app.screen.query_one(Input)
        field.value = "xy"
        await pilot.pause()
        await pilot.press("left", "z", "right")
        assert field.value == "xzy"
        await pilot.press("enter")  # no match: no action notification
        assert not list(app._notifications)
        assert bar.selected == 1
        await pilot.press("escape")
        assert bar.visible and bar.selected == 1
        await pilot.press("slash")
        app.screen.query_one(Input).value = "Child"
        await pilot.pause()
        await pilot.press("enter")
        assert app.query_one(TaskTree).cursor_node.data.id == "b"
        assert bar.visible and bar.selected == 1
        assert not list(app._notifications)


@pytest.mark.parametrize("widget_type", [Input, TextArea])
async def test_text_entry_hides_bar_and_keeps_native_keys(widget_type):
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        tree = app.query_one(TaskTree)
        await pilot.press("right")
        field = widget_type()
        await app.screen.mount(field)
        field.focus()
        await pilot.pause()
        assert not bar.visible
        await pilot.press("x", "y", "left", "z", "right", "enter")
        assert (field.value if isinstance(field, Input) else field.text).startswith("xzy")
        assert bar.selected == 1
        assert not list(app._notifications)
        tree.focus()
        await pilot.pause()
        assert bar.visible and bar.selected == 1


async def test_action_bar_wraps_after_resize_and_task_stays_visible():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        tree = app.query_one(TaskTree)
        await pilot.press("right", "down")
        await pilot.resize_terminal(14, 12)
        await pilot.pause()
        assert bar.size.height >= 2
        assert bar.region.bottom <= app.screen.size.height
        assert bar.render().plain == "[+] [✎ Edit task]"
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height
        await pilot.press("right")
        assert bar.render().plain == "[+ Add task] [✎]"
