from conftest import centered_scroll
from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.tree import TaskTree


def tasks():
    return [
        Task("a", "Task 1", [
            Task("b", "Task 1.1", [Task("c", "Leaf"), Task("d", "Other leaf")]),
            Task("e", "Task 1.2", [Task("f", "Last leaf")]),
        ]),
        Task("g", "Task 2"),
    ]


def visible_ids(tree):
    return [tree.get_node_at_line(line).data.id for line in range(tree.last_line + 1)]


def selected_id(tree):
    return tree.cursor_node.data.id


def breadcrumb(app):
    return app.query_one("#repository").content.plain


async def test_nested_focus_and_return():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        assert breadcrumb(app) == "Repo | Root"
        await pilot.press("f")
        assert visible_ids(tree) == ["b", "c", "d", "e", "f"]
        assert selected_id(tree) == "b"
        assert breadcrumb(app) == "Repo | Root / Task 1"
        await pilot.press("F")
        assert visible_ids(tree) == ["c", "d"]
        assert selected_id(tree) == "c"
        assert breadcrumb(app) == "Repo | Root / Task 1 / Task 1.1"
        await pilot.press("escape")
        assert selected_id(tree) == "b"
        assert breadcrumb(app) == "Repo | Root / Task 1"
        await pilot.press("escape")
        assert selected_id(tree) == "a"
        assert breadcrumb(app) == "Repo | Root"
        assert visible_ids(tree) == ["a", "b", "c", "d", "e", "f", "g"]
        await pilot.press("escape")
        assert selected_id(tree) == "a"
        assert breadcrumb(app) == "Repo | Root"


async def test_focus_deep_descendant_returns_one_hierarchy_level():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "f")
        assert breadcrumb(app) == "Repo | Root / Task 1 / Task 1.1"
        await pilot.press("escape")
        assert breadcrumb(app) == "Repo | Root / Task 1"
        assert selected_id(tree) == "b"
        await pilot.press("escape")
        assert selected_id(tree) == "a"


async def test_focus_scope_boundaries_and_leaf_noop():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "up", "shift+up", "left", "right", "enter")
        assert selected_id(tree) == "b"
        assert breadcrumb(app) == "Repo | Root / Task 1"
        await pilot.press("shift+down")
        assert selected_id(tree) == "e"
        await pilot.press("shift+down")
        assert selected_id(tree) == "e"
        await pilot.press("down", "down", "shift+down", "shift+up", "f", "enter")
        assert selected_id(tree) == "f"
        assert breadcrumb(app) == "Repo | Root / Task 1"
        await pilot.press("up", "shift+up")
        assert selected_id(tree) == "b"
        await pilot.press("f", "up", "shift+up")
        assert selected_id(tree) == "c"
        await pilot.press("down", "down", "shift+down")
        assert selected_id(tree) == "d"
        assert visible_ids(tree) == ["c", "d"]
        assert not tree.show_root


async def test_focus_preserves_expansion_inside_and_outside_scope():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "shift+down", "space")  # collapse E
        await pilot.press("shift+up", "space")  # collapse B
        assert visible_ids(tree) == ["a", "b", "e", "g"]
        await pilot.press("f")  # focus collapsed B without changing its saved state
        assert visible_ids(tree) == ["c", "d"]
        await pilot.press("escape")
        assert selected_id(tree) == "b"
        assert not tree.cursor_node.is_expanded
        assert visible_ids(tree) == ["b", "e"]
        await pilot.press("escape")
        assert visible_ids(tree) == ["a", "b", "e", "g"]
        await pilot.press("space", "f")  # focus collapsed A
        assert visible_ids(tree) == ["b", "e"]
        await pilot.press("space")  # expand B while A is hidden
        assert visible_ids(tree) == ["b", "c", "d", "e"]
        await pilot.press("escape")
        assert selected_id(tree) == "a"
        assert not tree.cursor_node.is_expanded
        await pilot.press("space")
        assert visible_ids(tree) == ["a", "b", "c", "d", "e", "g"]


async def test_focus_scrolling_return_and_resize():
    branches = [Task(str(i), f"Branch {i}", [Task(f"{i}-{j}", f"Child {j}") for j in range(25)]) for i in range(2)]
    app = TaskTreeApp("Repo", branches)
    async with app.run_test(size=(60, 13)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("shift+down", "f")
        assert selected_id(tree) == "1-0"
        assert tree.scroll_y == centered_scroll(tree)
        await pilot.press(*(["down"] * 9))
        assert tree.scroll_y == centered_scroll(tree)
        await pilot.press("down")
        assert tree.scroll_y == centered_scroll(tree)
        await pilot.press("up")
        assert tree.scroll_y == centered_scroll(tree)
        await pilot.press("shift+down")
        assert selected_id(tree) == "1-10"
        await pilot.resize_terminal(40, 8)
        await pilot.pause()
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height
        await pilot.press("escape")
        assert selected_id(tree) == "1"
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height


async def test_focus_breadcrumb_renders_titles_literally():
    app = TaskTreeApp("[Repo]", [Task("a", "[bold]Task", [Task("b", "Child")])])
    async with app.run_test() as pilot:
        await pilot.press("f")
        assert breadcrumb(app) == "[Repo] | Root / [bold]Task"
