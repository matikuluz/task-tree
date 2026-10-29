import json
from unittest.mock import patch

import pytest

from tasktree.app import TaskTreeApp
from tasktree.store import TaskStore, TaskStoreError
from tasktree.tree import TaskTree
from tasktree.placement_ui import PlacementTree


def store_at(path):
    store = TaskStore(path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [
        {"id": "a", "title": "Branch", "children": [
            {"id": "b", "title": "Nested", "children": [
                {"id": "c", "title": "Leaf", "children": []},
            ]},
        ]},
    ]}), encoding="utf-8")
    return store


async def test_nested_reopen_focus_and_title_save(tmp_path):
    store = store_at(tmp_path)
    assert store.load()[0].expanded
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("f", "space")
        assert not store.load()[0].children[0].expanded
        before = store.path.read_bytes()
        await pilot.press("f", "escape", "escape")
        assert store.path.read_bytes() == before  # focus is not a preference change
        await pilot.press("space")
        assert not store.load()[0].expanded
    store.update_title("a", "Renamed")
    loaded = store.load()
    assert loaded[0].title == "Renamed"
    assert not loaded[0].expanded and not loaded[0].children[0].expanded
    reopened = TaskTreeApp("Repo", loaded, store=store)
    async with reopened.run_test() as pilot:
        tree = reopened.query_one(TaskTree)
        assert tree.last_line == 0
        await pilot.press("space")
        assert tree.last_line == 1
        assert not tree.get_node_at_line(1).is_expanded


async def test_add_cancel_keeps_saved_expansion(tmp_path):
    store = store_at(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "space", "escape")
        tree = app.query_one(TaskTree)
        assert not tree.cursor_node.is_expanded
        assert not store.load()[0].expanded
        assert set(json.loads(store.path.read_text())["tasks"][0]) == {"id", "title", "children", "expanded"}
        await pilot.press("enter", "home", "down", "space", "escape")
        assert tree.cursor_node.is_expanded
        assert store.load()[0].expanded


@pytest.mark.parametrize("placement", [False, True])
async def test_failed_expansion_save_preserves_file_and_state(tmp_path, placement):
    store = store_at(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        if placement:
            await pilot.press("enter", "home", "down")
        with patch("tasktree.store.os.replace", side_effect=PermissionError("locked")):
            await pilot.press("space")
        assert store.path.read_bytes() == before
        assert any("locked" in notification.message for notification in app._notifications)
        if placement:
            await pilot.press("escape")
        assert app.query_one(TaskTree).cursor_node.is_expanded
        assert not list(tmp_path.glob(".tasktree-*.tmp"))


def test_expanded_requires_boolean_and_other_data_survives(tmp_path):
    store = store_at(tmp_path)
    store.update_expanded("b", False)
    data = json.loads(store.path.read_text())
    store.update_title("c", "Updated leaf")
    data["tasks"][0]["children"][0]["children"][0]["title"] = "Updated leaf"
    assert json.loads(store.path.read_text()) == data
    data["tasks"][0]["expanded"] = "false"
    store.path.write_text(json.dumps(data))
    with pytest.raises(TaskStoreError, match="expanded must be a boolean"):
        store.load()


@pytest.mark.parametrize("placement", [False, True])
async def test_native_disclosure_toggle_uses_atomic_save_path(tmp_path, placement):
    store = store_at(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        if placement:
            await pilot.press("enter", "home", "down")
            tree = app.screen.query_one(PlacementTree)
        else:
            tree = app.query_one(TaskTree)
        tree._toggle_node(tree.cursor_node)
        await pilot.pause()
        assert not store.load()[0].expanded
        if placement:
            await pilot.press("escape")
        assert not app.query_one(TaskTree).cursor_node.is_expanded
