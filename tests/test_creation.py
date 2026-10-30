import json
from unittest.mock import patch

import pytest

from tasktree.app import TaskTreeApp
from tasktree.action_bar import ActionBar
from tasktree.editor import TitleEditor
from tasktree.store import TaskStore
from tasktree.tree import TaskTree


def make_store(path, empty=False):
    store = TaskStore(path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [] if empty else [
        {"id": "a", "title": "Branch", "expanded": True, "children": [
            {"id": "b", "title": "First", "children": []},
            {"id": "c", "title": "Last", "children": []},
        ]}, {"id": "d", "title": "Outside", "children": []},
    ]}))
    return store


@pytest.mark.parametrize("empty,nested", [(True, False), (False, False), (False, True)])
async def test_create_at_captured_position_and_reopen(tmp_path, empty, nested):
    store = make_store(tmp_path, empty)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        if nested:
            await pilot.press("home", "down", "space", "enter", "down")  # after First
        await pilot.press("enter")
        editor = app.screen.query_one(TitleEditor)
        assert editor.value == ""
        await pilot.pause()
        y = editor.region.y
        editor.value = "Created"
        await pilot.press("enter")
        await pilot.pause()
        tree = app.query_one(TaskTree)
        assert tree.cursor_node.data.title == "Created"
        assert tree.scrollable_content_region.y + tree.cursor_line - int(tree.scroll_y) == y - int(nested)
        assert app.query_one(ActionBar).visible
        assert app.query_one(ActionBar).selected == 0
        new_id = tree.cursor_node.data.id
        assert new_id not in {"a", "b", "c", "d"}
        assert [entry.task.id for entry in app.search.find("Created")] == [new_id]
    values = store.load()
    siblings = values[0].children if nested else values
    assert [task.title for task in siblings] == (["First", "Created", "Last"] if nested else ["Created"] if empty else ["Branch", "Created", "Outside"])
    assert next(task for task in siblings if task.id == new_id).children == []
    reopened = TaskTreeApp("Repo", store.load(), store=store)
    async with reopened.run_test() as pilot:
        assert [entry.task.id for entry in reopened.search.find("Created")] == [new_id]


async def test_invalid_input_shortcuts_and_cancel(tmp_path):
    store = make_store(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        selected = tree.cursor_node
        await pilot.press("enter", "enter")
        screen = app.screen
        destination = screen.destination
        editor = app.screen.query_one(TitleEditor)
        editor.value = "  "
        await pilot.press("enter")
        assert app.focused is editor
        assert "whitespace" in str(screen._draft_error.content)
        editor.value = ""
        await pilot.press("q", "f", "r", "slash", "space", "up", "down")
        assert editor.value == "qfr/ "
        await pilot.press("home", "delete", "end", "backspace")
        assert editor.value == "fr/"
        assert screen.destination is destination
        await pilot.press("escape")
        assert tree.cursor_node is selected
        assert app.query_one(ActionBar).visible
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("retry", [False, True])
async def test_failed_save_retains_destination_and_retry_creates_once(tmp_path, retry):
    store = make_store(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("enter", "enter")
        editor = app.screen.query_one(TitleEditor)
        editor.value = "Retry"
        destination = app.screen.destination
        with patch("tasktree.store.os.replace", side_effect=PermissionError("locked")):
            await pilot.press("enter")
        assert app.focused is editor and editor.value == "Retry"
        assert app.screen.destination is destination
        assert store.path.read_bytes() == before
        assert not list(tmp_path.glob(".tasktree-*.tmp"))
        await pilot.press("enter" if retry else "escape")
        assert app.query_one(TaskTree).cursor_node.data.title == ("Retry" if retry else "Branch")
    assert [task.title for task in store.load()] == (["Branch", "Retry", "Outside"] if retry else ["Branch", "Outside"])


@pytest.mark.parametrize("position", ["first", "last", "nested-root-scope"])
async def test_other_insertion_positions_keep_order_and_scope(tmp_path, position):
    store = make_store(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        if position == "nested-root-scope":
            await pilot.press("down")
        await pilot.press("enter")
        if position != "nested-root-scope":
            await pilot.press("home" if position == "first" else "end")
        await pilot.press("enter")
        app.screen.query_one(TitleEditor).value = "New"
        await pilot.press("enter")
        assert app.query_one("#repository").content.plain == "Repo | Root"
        assert app.query_one(TaskTree).cursor_node.data.title == "New"
    loaded = store.load()
    if position == "nested-root-scope":
        assert [task.title for task in loaded[0].children] == ["First", "New", "Last"]
    else:
        assert [task.title for task in loaded] == (["New", "Branch", "Outside"] if position == "first" else ["Branch", "Outside", "New"])


async def test_cancel_draft_keeps_saved_expansion(tmp_path):
    store = make_store(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "space", "down", "enter", "x", "escape")
        assert not app.query_one(TaskTree).cursor_node.is_expanded
    assert [task.title for task in store.load()] == ["Branch", "Outside"]
    assert not store.load()[0].expanded


async def test_scrolled_creation_keeps_draft_row_position(tmp_path):
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": [
        {"id": str(i), "title": f"Task {i}", "children": []} for i in range(40)
    ]}))
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test(size=(80, 13)) as pilot:
        await pilot.press(*(["down"] * 15), "enter", "enter")
        await pilot.pause()
        editor = app.screen.query_one(TitleEditor)
        y = editor.region.y
        editor.value = "Inserted"
        await pilot.press("enter")
        await pilot.pause()
        tree = app.query_one(TaskTree)
        assert tree.cursor_node.data.title == "Inserted"
        assert tree.scrollable_content_region.y + tree.cursor_line - int(tree.scroll_y) == y
    assert store.load()[16].title == "Inserted"
