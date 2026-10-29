import pytest
from rich.console import Console
from textual.widgets import DataTable, Input

from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.search import SearchQuery, TaskSearch
from tasktree.tree import TaskTree


def tasks():
    return [
        Task("i", "Implementation", [
            Task("s", "Storage", [
                Task("c", "check"), Task("p", "Check CHECK config"), Task("x", "Run check"),
            ]),
            Task("n", "Intermediate", [Task("ss", "Storage", [Task("y", "check")])]),
            Task("ni", "Implementation", [
                Task("z", "login"), Task("deep", "Storage", [Task("k", "CHECK")]),
            ]),
            Task("l", "Login"),
        ]),
        Task("w", "Wrapper", [
            Task("j", "IMPLEMENTATION", [Task("t", "STORAGE", [Task("q", "Check")])]),
        ]),
        Task("outside", "check"),
    ]


def ids(query):
    return [result.task.id for result in TaskSearch(tasks()).find(query)]


@pytest.mark.parametrize("text, expected", [
    ("check", SearchQuery("check")),
    ("Implementation/", SearchQuery("", ("Implementation",))),
    ("Implementation/Storage/check", SearchQuery("check", ("Implementation", "Storage"))),
    ("rOoT/Implementation/check", SearchQuery("check", ("Implementation",), True)),
    ("Root/", SearchQuery("", (), True)),
])
def test_parse_final_slash(text, expected):
    assert SearchQuery.parse(text) == expected


def test_trailing_slash_descendants_only_tree_order_and_duplicate_branches():
    assert ids("Implementation/") == [
        "s", "c", "p", "x", "n", "ss", "y", "ni", "z", "deep", "k", "l", "t", "q",
    ]
    # NI is inside I and also matches the filter; its descendants appear once.
    assert len(ids("Implementation/")) == len(set(ids("Implementation/")))
    assert "i" not in ids("Implementation/")
    assert "j" not in ids("Implementation/")


def test_nested_consecutive_segments_and_title_ranking():
    assert ids("Implementation/Storage/check") == ["c", "k", "q", "p", "x"]
    assert ids("Implementation/Storage/") == ["c", "p", "x", "k", "q"]
    assert "y" not in ids("Implementation/Storage/")  # intervening Intermediate
    assert ids("Implementation/login") == ["z", "l"]
    assert ids("Implementation/Implementation/") == ["z", "deep", "k"]


def test_root_anchoring_and_root_lists_every_task():
    search = TaskSearch(tasks())
    assert ids("Root/") == [entry.task.id for entry in search.entries]
    assert ids("Root/Implementation/") == [
        "s", "c", "p", "x", "n", "ss", "y", "ni", "z", "deep", "k", "l",
    ]
    assert ids("Root/Implementation/Storage/") == ["c", "p", "x"]
    assert ids("Root/Storage/") == []
    assert ids("Root/check") == ids("check")
    response = TaskSearch([]).evaluate("Root/")
    assert response.path_matched and response.results == []


def test_path_case_insensitive_complete_segments():
    assert ids("iMPLEMENTATION/sTORAGE/ChEcK") == ids("Implementation/Storage/check")
    assert ids("rOoT/iMPLEMENTATION/sTORAGE/ChEcK") == ["c", "p", "x"]
    assert ids("Implement/") == []
    assert ids("Implementation/Stor/") == []


@pytest.mark.parametrize("query", ["Missing/", "Implementation/Missing/check", "Login/", "/", "Implementation//"])
def test_unmatched_paths(query):
    response = TaskSearch(tasks()).evaluate(query)
    assert not response.path_matched
    assert response.results == []


def test_title_only_search_unchanged_and_path_without_title_matches():
    assert ids("check") == ["c", "y", "k", "q", "outside", "p", "x"]
    assert ids("CHECK") == ids("check")
    assert ids("") == []
    response = TaskSearch(tasks()).evaluate("Implementation/unknown title")
    assert response.path_matched
    assert response.results == []


async def test_path_results_highlighting_full_paths_and_cancel():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test(size=(100, 20)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("space", "slash")  # search a collapsed branch
        screen = app.screen
        field = screen.query_one(Input)
        field.value = "Implementation"
        await pilot.pause()
        await pilot.press("slash")  # literal slash inside the active input
        assert app.screen is screen
        assert field.value == "Implementation/"
        assert [result.task.id for result in screen.results] == ids("Implementation/")
        table = screen.query_one(DataTable)
        title = table.get_cell("p", "title")
        assert not any(title.get_style_at_offset(Console(), index).bold for index in range(len(title)))
        assert table.get_cell("c", "path").plain == "Root / Implementation / Storage"
        field.value = "Implementation/Storage/check"
        await pilot.pause()
        title = table.get_cell("p", "title")
        assert title.plain == "  Check CHECK config"
        assert title.get_style_at_offset(Console(), 2).bold
        assert title.get_style_at_offset(Console(), 8).bold
        assert not title.get_style_at_offset(Console(), 14).bold
        field.value = "Missing/check"
        await pilot.pause()
        assert str(screen.query_one("#search-status").content) == "No matching branch path"
        field.value = "Implementation/missing title"
        await pilot.pause()
        assert str(screen.query_one("#search-status").content) == "No matching tasks"
        await pilot.press("enter")
        assert app.screen is screen
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "i"
        assert not tree.cursor_node.is_expanded


async def test_path_result_jump_outside_focus_and_parent_navigation():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "f", "slash")
        app.screen.query_one(Input).value = "Wrapper/Implementation/Storage/check"
        await pilot.pause()
        await pilot.press("enter")
        assert tree.cursor_node.data.id == "q"
        assert app.query_one("#repository").content.plain == "Repo | Root / Wrapper / IMPLEMENTATION / STORAGE"
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "t"
