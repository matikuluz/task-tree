import json
import pytest

from tasktree.app import TaskTreeApp
from tasktree.placement_ui import PlacementTree
from tasktree.store import TaskStore
from tasktree.tree import TaskTree
from tasktree.models import Task


@pytest.mark.parametrize("delete", [False, True])
async def test_folder_option_tracks_expansion_and_stays_on_target(tmp_path, delete):
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [
        {"id": "a", "title": "Branch", "children": [
            {"id": "b", "title": "Leaf", "children": []}]}]}))
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        if delete:
            await pilot.press("left", "enter")
        else:
            await pilot.press("enter", "home", "down")
        screen = app.screen
        tree = screen.query_one(PlacementTree)
        assert screen.model.current.kind == "task"
        assert "[Enter folder]" not in tree.render_line(tree.cursor_line).text
        await pilot.press("enter")
        assert not screen.model.path  # expanded branch cannot enter a hidden folder option
        await pilot.press("space")
        assert screen.model.current.kind == "folder"
        assert screen.model.current.task.id == "a"
        assert "[Enter folder]" in tree.render_line(tree.cursor_line).text
        assert not store.load()[0].expanded
        await pilot.press("space")
        assert screen.model.current.kind == "task"
        assert screen.model.current.task.id == "a"
        assert "[Enter folder]" not in tree.render_line(tree.cursor_line).text
        assert store.load()[0].expanded
        await pilot.press("space", "enter")
        assert screen.model.path[-1].id == "a"
        await pilot.press("home", "enter")
        assert screen.model.current.kind == "folder"
        await pilot.press("escape")
        assert not app.query_one(TaskTree).cursor_node.is_expanded


@pytest.mark.parametrize("delete", [False, True])
async def test_toggle_keeps_the_target_at_its_scrolled_position(delete):
    values = [Task(str(i), f"Task {i}") for i in range(20)]
    values += [Task("branch", "Branch", [Task("leaf", "Leaf")])]
    values += [Task(f"tail{i}", f"Tail {i}") for i in range(30)]
    app = TaskTreeApp("Repo", values)
    async with app.run_test(size=(80, 13)) as pilot:
        if delete:
            await pilot.press(*(["down"] * 20), "left", "enter")
        else:
            await pilot.press("enter", "home", *(["down"] * 21))
        tree = app.screen.query_one(PlacementTree)
        assert app.screen.model.current.task.id == "branch"
        before = (tree.cursor_line, tree.scroll_y)
        await pilot.press("space")
        assert app.screen.model.current.kind == "folder"
        assert (tree.cursor_line, tree.scroll_y) == before
        await pilot.press("space")
        assert app.screen.model.current.kind == "task"
        assert (tree.cursor_line, tree.scroll_y) == before
