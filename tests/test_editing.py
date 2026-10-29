import json
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Input

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.editor import TitleEditor
from tasktree.store import TaskStore, TaskStoreError
from tasktree.tree import TaskTree


def make_store(tmp_path):
    data = {"schema_version": 1, "tasks": [
        {"id": "a", "title": "Branch", "children": [
            {"id": "b", "title": "Original title", "children": [
                {"id": "c", "title": "Child", "children": []},
            ]},
            {"id": "d", "title": "Other", "children": []},
        ]},
    ]}
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps(data), encoding="utf-8")
    return store, data


async def test_save_reopen_preserve_other_data_and_search(tmp_path):
    store, original = make_store(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "right", "enter")
        editor = app.query_one(TitleEditor)
        await pilot.pause()
        assert editor.value == "Original title"
        assert editor.cursor_position == len(editor.value)
        assert editor.selection.start == editor.selection.end == len(editor.value)
        assert editor.cursor_blink
        assert editor.region.height == 1
        assert editor.region.x == tree.region.x + tree.guide_depth + 4
        assert not app.query_one(ActionBar).visible
        editor.value = "Renamed title"
        await pilot.press("enter")
        assert not app.query(TitleEditor)
        assert tree.cursor_node.data.id == "b"
        assert tree.cursor_node.label.plain == "Renamed title"
        assert app.query_one(ActionBar).selected == 1
        assert app.query_one(ActionBar).visible
        assert tree.cursor_node.is_expanded
        assert [result.task.id for result in app.search.find("Renamed")] == ["b"]
        assert app.search.find("Original") == []
    original["tasks"][0]["children"][0]["title"] = "Renamed title"
    assert json.loads(store.path.read_text(encoding="utf-8")) == original
    assert TaskStore(tmp_path).load()[0].children[0].title == "Renamed title"
    assert not list(tmp_path.glob(".tasktree-*.tmp"))
    reopened = TaskTreeApp("Repo", store.load(), store=store)
    async with reopened.run_test() as pilot:
        await pilot.press("down")
        assert reopened.query_one(TaskTree).cursor_node.data.title == "Renamed title"


async def test_cancel_preserves_scope_selection_scroll_and_file(tmp_path):
    store, _ = make_store(tmp_path)
    before = store.path.read_bytes()
    timestamp = store.path.stat().st_mtime_ns
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "space", "right")
        node = tree.cursor_node
        scroll = tree.scroll_y
        await pilot.press("enter", "x", "escape")
        assert tree.cursor_node is node
        assert node.data.title == "Original title"
        assert not node.is_expanded
        assert tree.scroll_y == scroll
        assert app.query_one("#repository").content.plain == "Repo | Root / Branch"
        assert app.query_one(ActionBar).selected == 1
        assert app.query_one(ActionBar).visible
    assert store.path.read_bytes() == before
    assert store.path.stat().st_mtime_ns == timestamp


@pytest.mark.parametrize("title", ["", "   ", "\t", "Bad\nTitle", "Bad\x1bTitle"])
async def test_invalid_title_retains_draft_and_allows_cancel(tmp_path, title):
    store, _ = make_store(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("right", "enter")
        editor = app.query_one(TitleEditor)
        editor.value = title
        await pilot.press("enter")
        assert app.query_one(TitleEditor) is editor
        assert editor.value == title
        assert app.query_one("#title-error").display
        assert store.path.read_bytes() == before
        await pilot.press("escape")
        assert app.query_one(TaskTree).cursor_node.data.title == "Branch"


async def test_edit_shortcut_isolation_and_native_editing_keys(tmp_path):
    store, _ = make_store(tmp_path)
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "right", "enter")
        editor = app.query_one(TitleEditor)
        selected = tree.cursor_node
        editor.value = ""
        await pilot.press("q", "f", "r", "slash", "space", "Q", "F", "R")
        assert editor.value == "qfr/ QFR"
        await pilot.press("up", "down", "shift+up", "shift+down", "shift+left", "shift+right", "tab")
        assert app.focused is editor
        assert tree.cursor_node is selected
        assert app.is_running
        assert app.query_one(ActionBar).selected == 1
        editor.value = "abcd"
        await pilot.press("home", "delete", "end", "backspace", "left", "x", "right")
        assert editor.value == "bxc"
        assert tree.cursor_node is selected
        await pilot.press("escape")


async def test_save_failure_retains_text_and_allows_retry(tmp_path, monkeypatch):
    store, _ = make_store(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("right", "enter")
        editor = app.query_one(TitleEditor)
        editor.value = "New branch"
        with patch("tasktree.store.os.replace", side_effect=PermissionError("File is locked")):
            await pilot.press("enter")
        assert editor.value == "New branch"
        assert app.focused is editor
        assert "File is locked" in str(app.query_one("#title-error").content)
        assert app.query_one(TaskTree).cursor_node.data.title == "Branch"
        assert store.path.read_bytes() == before
        assert not list(tmp_path.glob(".tasktree-*.tmp"))
        await pilot.press("enter")
        assert not app.query(TitleEditor)
        assert store.load()[0].title == "New branch"


async def test_save_failure_then_cancel_does_not_write(tmp_path):
    store, _ = make_store(tmp_path)
    before = store.path.read_bytes()
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("right", "enter")
        app.query_one(TitleEditor).value = "Draft"
        with patch("tasktree.store.os.replace", side_effect=OSError("Disk error")):
            await pilot.press("enter", "escape")
        assert app.query_one(TaskTree).cursor_node.data.title == "Branch"
    assert store.path.read_bytes() == before


def test_atomic_update_preserves_latest_other_data_and_uses_same_directory(tmp_path):
    store, data = make_store(tmp_path)
    # The save reads the current disk contents rather than serializing a stale UI model.
    data["tasks"][0]["children"][1]["title"] = "Externally changed"
    store.path.write_text(json.dumps(data), encoding="utf-8")
    import os

    replace = os.replace
    calls = []

    def record(source, destination):
        calls.append((Path(source), Path(destination)))
        replace(source, destination)

    with patch("tasktree.store.os.replace", side_effect=record):
        store.update_title("b", "Updated")
    data["tasks"][0]["children"][0]["title"] = "Updated"
    assert json.loads(store.path.read_text()) == data
    assert calls[0][0].parent == tmp_path
    assert calls[0][1] == store.path


def test_missing_task_or_invalid_disk_data_is_not_overwritten(tmp_path):
    store, _ = make_store(tmp_path)
    before = store.path.read_bytes()
    with pytest.raises(TaskStoreError, match="no longer exists"):
        store.update_title("missing", "New")
    assert store.path.read_bytes() == before
    store.path.write_text("invalid", encoding="utf-8")
    with pytest.raises(TaskStoreError):
        store.update_title("b", "New")
    assert store.path.read_text() == "invalid"


async def test_edit_scrolled_row_preserves_geometry_scroll_and_expansion(tmp_path):
    data = {"schema_version": 1, "tasks": [
        {"id": str(i), "title": f"Task {i}", "children": []} for i in range(40)
    ]}
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps(data), encoding="utf-8")
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test(size=(60, 13)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press(*(["down"] * 14), "right")
        before = tree.scroll_y
        node = tree.cursor_node
        await pilot.press("enter")
        await pilot.pause()
        editor = app.query_one(TitleEditor)
        assert tree.scroll_y == before
        assert editor.region.y == tree.scrollable_content_region.y + tree.cursor_line - int(before)
        editor.value = ""
        await pilot.press("enter")
        assert app.query_one("#title-error").region.y != editor.region.y
        editor.value = "Saved title"
        await pilot.press("enter")
        assert tree.cursor_node is node
        assert tree.scroll_y == before
        assert node.label.plain == "Saved title"
        await pilot.press("enter")
        await pilot.resize_terminal(45, 13)
        await pilot.pause()
        assert app.query_one(TitleEditor).region.width <= 45
        await pilot.press("escape")
        assert tree.scroll_y == before
