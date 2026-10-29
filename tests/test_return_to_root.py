import pytest
from textual.widgets import Input, TextArea

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.tree import TaskTree


def tasks():
    return [
        Task("a", "Branch", [
            Task("b", "Nested", [Task("c", "Child"), Task("d", "Other")]),
            Task("e", "Sibling"),
        ]),
        Task("f", "Last"),
    ]


@pytest.mark.parametrize("key", ["r", "R"])
async def test_return_to_root_preserves_expansion_action_and_clears_scope(key):
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        bar = app.query_one(ActionBar)
        await pilot.press("down", "space", "up", "space")  # collapse B and A
        await pilot.press("f", "f", "down", "right")
        assert tree.cursor_node.data.id == "d"
        assert bar.selected == 1
        await pilot.press(key)
        assert tree.cursor_node.data.id == "a"
        assert not tree.cursor_node.is_expanded
        assert app.query_one("#repository").content.plain == "Repo | Root"
        assert bar.selected == 1
        selected = tree.cursor_node
        await pilot.press("escape")  # no stale focus history
        assert tree.cursor_node is selected
        await pilot.press("space", "down")
        assert tree.cursor_node.data.id == "b"
        assert not tree.cursor_node.is_expanded


async def test_root_shortcut_is_noop_on_descendant_at_root_and_empty_tree():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "down")
        selected = tree.cursor_node
        scroll = tree.scroll_y
        await pilot.press("r")
        assert tree.cursor_node is selected
        assert tree.scroll_y == scroll
    empty = TaskTreeApp("Repo", [])
    async with empty.run_test() as pilot:
        await pilot.press("r", "R", "escape")
        assert not empty.query(TaskTree)
        assert empty.query_one("#repository").content.plain == "Repo | Root"
        assert empty.query_one(ActionBar).selected == 0


@pytest.mark.parametrize("root_index", [3, 25])
async def test_return_to_root_selects_ancestor_and_scrolls_minimally(root_index):
    roots = [Task(str(i), f"Root {i}") for i in range(root_index)]
    roots.append(Task("branch", "Target", [Task("nested", "Nested", [Task("leaf", "Leaf")])]))
    roots.extend(Task(f"tail-{i}", f"Tail {i}") for i in range(15))
    app = TaskTreeApp("Repo", roots)
    async with app.run_test(size=(80, 13)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press(*(["shift+down"] * root_index), "f", "f")
        assert tree.cursor_node.data.id == "leaf"
        assert tree.scroll_y == 0
        await pilot.press("r")
        assert tree.cursor_node.data.id == "branch"
        assert tree.scroll_y == max(0, root_index - 9)
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "branch"


async def test_escape_still_returns_one_level_before_root_shortcut():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "f", "escape")
        assert tree.cursor_node.data.id == "b"
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch"
        await pilot.press("r")
        assert tree.cursor_node.data.id == "a"
        assert app.query_one("#repository").content.plain == "Repo | Root"


async def test_root_shortcut_types_normally_in_search_and_cancel_preserves_scope():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "f", "slash", "r", "R")
        assert app.screen.query_one(Input).value == "rR"
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "c"
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch / Nested"


@pytest.mark.parametrize("widget_type", [Input, TextArea])
async def test_root_shortcut_types_normally_in_other_text_inputs(widget_type):
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "f")
        field = widget_type()
        await app.screen.mount(field)
        field.focus()
        await pilot.press("r", "R")
        assert (field.value if isinstance(field, Input) else field.text) == "rR"
        assert tree.cursor_node.data.id == "c"
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch / Nested"
