import json
from rich.style import Style

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.placement_ui import PlacementScreen
from tasktree.placement_ui import PlacementTree
from tasktree.store import TaskStore
from tasktree.tree import TaskTree


async def test_delete_targets_folders_cancel_and_preserves_file(tmp_path):
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [
        {"id": "a", "title": "Branch", "children": [
            {"id": "b", "title": "Leaf", "children": []}]},
        {"id": "c", "title": "Other", "children": []}]}))
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        original = tree.cursor_node
        before = store.path.read_bytes()
        await pilot.press("left", "enter")
        screen = app.screen
        assert isinstance(screen, PlacementScreen) and screen.model.delete
        assert screen.model.current.kind == "task" and screen.model.current.task.id == "a"
        assert not app.query_one(ActionBar).visible
        assert all(entry.kind != "insert" for entry in screen.model.entries)
        await pilot.press("enter")
        assert any(note.message == "Deletion — coming soon" for note in app._notifications)
        await pilot.press("space", "enter")
        assert screen.model.path[-1].id == "a"
        assert screen.model.current.kind == "task" and screen.model.current.task.id == "b"
        await pilot.press("home", "enter")
        assert screen.model.current.kind == "folder"
        await pilot.press("escape")
        assert tree.cursor_node is original
        assert app.query_one(ActionBar).selected == 0
        assert [task.title for task in store.load()] == ["Branch", "Other"]


async def test_contextual_folder_row_and_collapsed_folder_entry():
    app = TaskTreeApp("Repo", [Task("a", "Branch", [Task("b", "Leaf")])])
    async with app.run_test() as pilot:
        await pilot.press("left", "enter", "space", "down")
        screen = app.screen
        tree = screen.query_one(PlacementTree)
        assert screen.model.current.kind == "folder"
        rows = [tree.render_line(i).text for i in range(tree.last_line + 1)]
        assert sum("Branch" in row for row in rows) == 1
        assert "[Enter folder]" in rows[0]
        assert "▶" in rows[0]
        await pilot.press("enter")
        assert screen.model.current.kind == "task" and screen.model.current.task.id == "b"
        await pilot.press("escape")


async def test_empty_delete_unavailable_and_wrap():
    app = TaskTreeApp("Repo", [])
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        await pilot.press("left", "right")
        assert bar.selected == 0 and not bar.available(bar.ACTIONS[2])


async def test_delete_collapse_persists_on_cancel(tmp_path):
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [{"id": "a", "title": "Branch", "children": [{"id": "b", "title": "Leaf", "children": []}]}]}))
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("left", "enter", "space", "escape")
        assert not app.query_one(TaskTree).cursor_node.is_expanded
    assert not store.load()[0].expanded
    assert store.load()[0].children[0].id == "b"

async def test_delete_guides_and_cursor_are_red_but_titles_keep_selection_colors():
    app = TaskTreeApp("Repo", [Task("a", "Branch", [Task("b", "Leaf"), Task("c", "Other")])])
    async with app.run_test() as pilot:
        await pilot.press("4")
        tree = app.screen.query_one(PlacementTree)
        red = Style(color="red").color
        child = list(tree.render_line(1 - int(tree.scroll_y)))
        assert any(any(char in segment.text for char in "├└│─") and segment.style.color.get_truecolor().hex.lower() == "#ff0000" for segment in child)
        await pilot.press("down")
        line = list(tree.render_line(tree.cursor_line - int(tree.scroll_y)))
        assert any("🗑" in segment.text and segment.style.color == red for segment in line)
        assert any("Leaf" in segment.text and segment.style.color.get_truecolor().hex.lower() == "#ffffff" for segment in line)
        other = list(tree.render_line(tree.cursor_line + 1 - int(tree.scroll_y)))
        assert any("Other" in segment.text and segment.style.color.get_truecolor().hex.lower() == "#888888" for segment in other)
        await pilot.press("down")
        selected = list(tree.render_line(tree.cursor_line - int(tree.scroll_y)))
        assert any("🗑" in segment.text and segment.style.color == red for segment in selected)
        assert any("Other" in segment.text and segment.style.color.get_truecolor().hex.lower() == "#ffffff" for segment in selected)
