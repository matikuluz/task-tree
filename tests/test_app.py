from pathlib import Path

from rich.style import Style

from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.store import TaskStore
from tasktree.tree import TaskTree


def branch_tasks():
    return [
        Task("a", "Branch", [Task("b", "Child", [Task("c", "Grandchild")]), Task("d", "Sibling")]),
        Task("e", "Last"),
    ]


async def test_navigation_and_collapse():
    app = TaskTreeApp("Repository", branch_tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        assert not tree.show_root
        assert tree.cursor_node.data.id == "a"
        assert tree.last_line == 4
        await pilot.press("up", "up")
        assert tree.cursor_line == 0
        for expected in ["b", "c", "d", "e", "e"]:
            await pilot.press("down")
            assert tree.cursor_node.data.id == expected
        await pilot.press("space")
        assert tree.last_line == 4  # leaf is a no-op
        await pilot.press("up", "up", "up")
        assert tree.cursor_node.data.id == "b"
        await pilot.press("space")
        assert tree.cursor_node.data.id == "b"
        assert not tree.cursor_node.is_expanded
        await pilot.press("down")
        assert tree.cursor_node.data.id == "d"
        await pilot.press("up")
        assert tree.cursor_node.data.id == "b"
        await pilot.press("left", "right", "enter", "shift+space", "shift+left", "shift+down")
        assert tree.cursor_node.data.id == "b"
        assert not tree.cursor_node.is_expanded
        await pilot.press("space", "down")
        assert tree.cursor_node.data.id == "c"
        await pilot.press("up", "up", "space")
        assert tree.cursor_node.data.id == "a"
        assert tree.last_line == 1
        await pilot.press("down")
        assert tree.cursor_node.data.id == "e"
        await pilot.press("up", "space")
        assert tree.last_line == 4


async def test_viewport_boundary_and_resize():
    app = TaskTreeApp("Repository", [Task(str(i), f"Task {i}") for i in range(40)])
    async with app.run_test(size=(60, 12)) as pilot:
        tree = app.query_one(TaskTree)
        assert tree.scrollable_content_region.height == 10
        assert tree.scroll_y == 0
        await pilot.press(*(["down"] * 9))
        assert tree.cursor_line == 9
        assert tree.scroll_y == 0
        await pilot.press("down")
        assert tree.cursor_line == 10
        assert tree.scroll_y == 1
        await pilot.press("up")
        assert tree.cursor_line == 9
        assert tree.scroll_y == 1
        await pilot.press(*(["up"] * 8))
        assert tree.cursor_line == 1
        assert tree.scroll_y == 1
        await pilot.press("up")
        assert tree.scroll_y == 0
        await pilot.press(*(["down"] * 39))
        assert tree.cursor_line == 39
        assert tree.scroll_y == 30  # no blank padding at bottom
        await pilot.resize_terminal(40, 8)
        await pilot.pause()
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height
        await pilot.press("up")
        assert tree.scroll_y == 34
        await pilot.resize_terminal(80, 20)
        await pilot.pause()
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height


async def test_nested_scroll_and_collapse():
    tasks = [Task("branch", "Branch", [Task(str(i), f"Child {i}") for i in range(25)]), Task("last", "Last")]
    app = TaskTreeApp("Repository", tasks)
    async with app.run_test(size=(50, 12)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press(*(["down"] * 10))
        assert tree.cursor_node.data.id == "9"
        assert tree.scroll_y == 1
        await pilot.press("up")
        assert tree.scroll_y == 1
        await pilot.press(*(["up"] * 9), "space")
        assert tree.last_line == 1
        assert tree.scroll_y == 0
        await pilot.press("down")
        assert tree.cursor_node.data.id == "last"


async def test_selection_rendering_and_one_row():
    app = TaskTreeApp("[literal repo]", [Task("a", "[bold]" + "Long title " * 30, [Task("b", "Child")])])
    async with app.run_test(size=(35, 10)) as pilot:
        tree = app.query_one(TaskTree)
        first = tree.cursor_node
        label = tree.render_label(first, Style(), Style())
        assert label.plain.startswith("> ")
        assert label.get_style_at_offset(app.console, 0).bold
        assert "[bold]" in label.plain
        assert tree.last_line == 1
        assert tree.virtual_size.height == 2
        assert tree.scroll_x == 0
        await pilot.press("down")
        assert tree.render_label(first, Style(), Style()).plain.startswith("  ")
        assert tree.render_label(tree.cursor_node, Style(), Style()).plain.startswith("> ")
        # Inspect final rendered rows: the child's marker follows the tree indentation.
        rows = [tree.render_line(i).text for i in range(2)]
        assert ">" not in rows[0]
        assert rows[1].index(">") > 0


async def test_empty_and_quit():
    app = TaskTreeApp("Repository", [])
    async with app.run_test() as pilot:
        assert str(app.query_one("#empty").content) == "No tasks yet."
        assert not app.query(TaskTree)
        await pilot.press("up", "down", "space", "q")
        assert not app.is_running


async def test_open_close_does_not_write(tmp_path):
    sample = Path(__file__).parents[1] / "examples" / "sample.tasktree.json"
    store = TaskStore(tmp_path)
    store.path.write_bytes(sample.read_bytes())
    before = store.path.read_bytes()
    stat = store.path.stat()
    app = TaskTreeApp("Repository", store.load())
    async with app.run_test() as pilot:
        await pilot.press("space", "down", "space", "Q")
    assert store.path.read_bytes() == before
    assert store.path.stat().st_mtime_ns == stat.st_mtime_ns
