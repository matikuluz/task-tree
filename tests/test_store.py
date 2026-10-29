import json
from pathlib import Path
import subprocess

import pytest

from tasktree.cli import main
from tasktree.store import TaskStore, TaskStoreError, repository_root


def task(id="one", title="First", children=None):
    return {"id": id, "title": title, "children": children or []}


def write_tasks(root: Path, tasks: list) -> TaskStore:
    store = TaskStore(root)
    store.path.write_text(json.dumps({"schema_version": 1, "tasks": tasks}), encoding="utf-8")
    return store


def test_init_never_overwrites(tmp_path):
    store = TaskStore(tmp_path)
    store.init()
    assert json.loads(store.path.read_text()) == {"schema_version": 1, "tasks": []}
    original = store.path.read_bytes()
    with pytest.raises(TaskStoreError, match="already exists"):
        store.init()
    assert store.path.read_bytes() == original
    store.path.write_text("invalid user content")
    with pytest.raises(TaskStoreError):
        store.init()
    assert store.path.read_text() == "invalid user content"


def test_load_nested(tmp_path):
    tasks = write_tasks(tmp_path, [task(children=[task("two", children=[task("three")])])]).load()
    assert tasks[0].children[0].children[0].id == "three"


@pytest.mark.parametrize("data, message", [
    ([], "expected an object"),
    ({"schema_version": True, "tasks": []}, "schema_version"),
    ({"schema_version": 2, "tasks": []}, "schema_version"),
    ({"schema_version": 1, "tasks": {}}, "tasks must be an array"),
    ({"schema_version": 1, "tasks": [None]}, r"tasks\[0\]"),
    ({"schema_version": 1, "tasks": [{"id": "x"}]}, "exactly"),
    ({"schema_version": 1, "tasks": [task(title=" ")]}, "title"),
    ({"schema_version": 1, "tasks": [task(title="line\nbreak")]}, "single-line"),
    ({"schema_version": 1, "tasks": [task(id=3)]}, "id"),
    ({"schema_version": 1, "tasks": [task(children=[task()])]}, "duplicates"),
    ({"schema_version": 1, "tasks": [{"id": "x", "title": "x", "children": 3}]}, "children"),
])
def test_invalid_data_is_unchanged(tmp_path, data, message):
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps(data), encoding="utf-8")
    before = store.path.read_bytes()
    with pytest.raises(TaskStoreError, match=message):
        store.load()
    assert store.path.read_bytes() == before


def test_missing_and_malformed(tmp_path):
    store = TaskStore(tmp_path)
    with pytest.raises(TaskStoreError, match="tasktree init"):
        store.load()
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(TaskStoreError, match="Cannot read"):
        store.load()
    store.path.write_bytes(b"\xff")
    with pytest.raises(TaskStoreError, match="Cannot read"):
        store.load()


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_repository_subdirectory_and_cli(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init")
    child = tmp_path / "nested"
    child.mkdir()
    assert repository_root(child) == tmp_path.resolve()
    monkeypatch.chdir(child)
    assert main(["open"]) == 1
    assert "tasktree init" in capsys.readouterr().err
    assert main(["init"]) == 0
    assert (tmp_path / ".tasktree.json").exists()
    assert main(["init"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_outside_repository(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 1
    assert "Git working repository" in capsys.readouterr().err


def test_linked_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-m", "test")
    worktree = tmp_path / "linked"
    git(repo, "worktree", "add", "--detach", str(worktree))
    try:
        child = worktree / "nested"
        child.mkdir()
        assert (worktree / ".git").is_file()
        assert repository_root(child) == worktree.resolve()
        TaskStore(repository_root(child)).init()
        assert (worktree / ".tasktree.json").exists()
        assert not (repo / ".tasktree.json").exists()
    finally:
        git(repo, "worktree", "remove", "--force", str(worktree))
