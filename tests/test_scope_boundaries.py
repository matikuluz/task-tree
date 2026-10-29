import pytest
from textual.widgets import Input, TextArea

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.editor import TitleEditor
from tasktree.models import Task
from tasktree.tree import TaskTree


def tasks():
    return [
        Task("a", "Branch", [
            Task("b", "Nested", [Task("c", "Child"), Task("d", "Other")]),
            Task("e", "Sibling", [Task("f", "Final child")]),
        ]),
        Task("z", "Last branch", [Task("y", "Last descendant")]),
    ]


async def test_root_boundaries_skip_collapsed_descendants_and_preserve_action():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("right", "end")
        assert tree.cursor_node.data.id == "y"
        await pilot.press("up", "space", "home")
        assert tree.cursor_node.data.id == "a"
        await pilot.press("end")
        assert tree.cursor_node.data.id == "z"
        assert not tree.cursor_node.is_expanded
        assert app.query_one(ActionBar).selected == 1
        assert app.query_one("#repository").content.plain == "Repo | Root"


async def test_focused_and_nested_scope_boundaries():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "right", "end")
        assert tree.cursor_node.data.id == "f"
        await pilot.press("up", "space", "home")
        assert tree.cursor_node.data.id == "b"
        await pilot.press("end")
        assert tree.cursor_node.data.id == "e"
        assert not tree.cursor_node.is_expanded
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch"
        await pilot.press("home", "f", "end")
        assert tree.cursor_node.data.id == "d"
        await pilot.press("home")
        assert tree.cursor_node.data.id == "c"
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch / Nested"
        assert app.query_one(ActionBar).selected == 1
        await pilot.press("escape", "end")
        assert tree.cursor_node.data.id == "e"
        assert not tree.cursor_node.is_expanded


@pytest.mark.parametrize("focused", [False, True])
async def test_boundary_scrolling_is_minimal_and_boundary_noops(focused):
    children = [Task(str(i), f"Task {i}") for i in range(40)]
    roots = [Task("branch", "Scope", children), Task("outside", "Outside")] if focused else children
    app = TaskTreeApp("Repo", roots)
    async with app.run_test(size=(80, 13)) as pilot:
        tree = app.query_one(TaskTree)
        if focused:
            await pilot.press("f")
        assert tree.scrollable_content_region.height == 10
        await pilot.press(*(["down"] * 4), "home")
        assert tree.cursor_node.data.id == "0"
        assert tree.scroll_y == 0
        await pilot.press("end")
        assert tree.cursor_node.data.id == "39"
        assert tree.scroll_y == 30
        selected = tree.cursor_node
        await pilot.press("end")
        assert tree.cursor_node is selected
        assert tree.scroll_y == 30
        await pilot.press("up")
        assert tree.scroll_y == 30
        await pilot.press("home")
        assert tree.cursor_node.data.id == "0"
        assert tree.scroll_y == 0
        selected = tree.cursor_node
        await pilot.press("home")
        assert tree.cursor_node is selected
        assert tree.scroll_y == 0


async def test_empty_tree_and_single_row_scope():
    app = TaskTreeApp("Repo", [])
    async with app.run_test() as pilot:
        await pilot.press("home", "end")
        assert not app.query(TaskTree)
        assert app.query_one(ActionBar).selected == 0
    app = TaskTreeApp("Repo", [Task("branch", "Branch", [Task("leaf", "Only child")])])
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f")
        selected = tree.cursor_node
        await pilot.press("end", "home")
        assert tree.cursor_node is selected


async def test_boundary_shortcuts_do_not_navigate_search_results_or_tree():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "slash")
        screen = app.screen
        screen.query_one(Input).value = "child"
        await pilot.pause()
        field = screen.query_one(Input)
        await pilot.press("home")
        assert field.cursor_position == 0
        await pilot.press("end")
        assert field.cursor_position == len(field.value)
        assert screen.selected == 0
        assert tree.cursor_node.data.id == "b"
        assert app.focused is screen.query_one(Input)
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "b"


async def test_boundary_shortcuts_are_disabled_in_inline_editor():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "right", "enter")
        editor = app.query_one(TitleEditor)
        selected = tree.cursor_node
        value = editor.value
        await pilot.press("home")
        assert editor.cursor_position == 0
        await pilot.press("end")
        assert editor.cursor_position == len(value)
        assert tree.cursor_node is selected
        assert editor.value == value
        assert app.focused is editor
        assert app.query_one(ActionBar).selected == 1
        await pilot.press("escape")


@pytest.mark.parametrize("widget_type", [Input, TextArea])
async def test_boundary_shortcuts_do_not_navigate_tree_from_other_text_inputs(widget_type):
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down")
        selected = tree.cursor_node
        field = widget_type()
        await app.screen.mount(field)
        field.focus()
        await pilot.press("a", "b", "c", "home", "x", "end", "y")
        assert (field.value if isinstance(field, Input) else field.text) == "xabcy"
        assert tree.cursor_node is selected
        assert app.focused is field


async def test_old_control_arrows_and_letter_alternatives_are_unbound():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "down")
        selected = tree.cursor_node
        await pilot.press("ctrl+up", "ctrl+down", "t", "T", "b", "B")
        assert tree.cursor_node is selected
