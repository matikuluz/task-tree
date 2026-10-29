import pytest
from rich.console import Console
from rich.cells import cell_len
from textual.widgets import DataTable, Input, TextArea

from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.search import TaskSearch, matching_spans
from tasktree.search_ui import SearchScreen, shortened_path
from tasktree.tree import TaskTree


def sample():
    return [
        Task("a", "Implementation", [
            Task("b", "Storage", [Task("c", "Target leaf"), Task("d", "Target leaf")]),
            Task("e", "Viewer", [Task("f", "Other leaf")]),
        ]),
        Task("g", "Root leaf"),
    ]


def test_search_ranking_case_and_duplicate_titles():
    tasks = [
        Task("sub", "A target", [Task("exact1", "TARGET")]),
        Task("prefix1", "Target one"),
        Task("exact2", "target"),
        Task("prefix2", "target two"),
        Task("sub2", "Another TARGET"),
    ]
    search = TaskSearch(tasks)
    assert [result.task.id for result in search.find("tArGeT")] == [
        "exact1", "exact2", "prefix1", "prefix2", "sub", "sub2",
    ]
    assert search.find("exact1") == []  # titles only, not IDs
    assert search.find("") == []
    assert search.find("targte") == []  # no fuzzy matching
    assert search.find("TARGET")[0].parent_path == "Root / A target"


@pytest.mark.parametrize("title, query, expected", [
    ("Target TARGET target", "TaRgEt", [(0, 6), (7, 13), (14, 20)]),
    ("Straße STRASSE", "strasse", [(0, 6), (7, 14)]),
    ("banana", "ana", [(1, 4), (3, 6)]),
    ("Title", "", []),
])
def test_matching_spans(title, query, expected):
    assert matching_spans(title, query) == expected


def test_path_truncation_preserves_end():
    assert shortened_path("Root / Implementation", 16) == "… Implementation"
    assert shortened_path("Root", 10) == "Root"
    shortened = shortened_path("Root / 分支", 7)
    assert shortened.endswith("/ 分支")
    assert cell_len(shortened) <= 7


async def test_slash_opens_empty_search_and_types_normally_inside():
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        await pilot.press("ctrl+f")
        assert not isinstance(app.screen, SearchScreen)
        await pilot.press("slash")
        screen = app.screen
        assert isinstance(screen, SearchScreen)
        field = screen.query_one(Input)
        assert app.focused is field
        assert field.value == ""
        await pilot.press("slash", "a", "slash")
        assert app.screen is screen
        assert field.value == "/a/"
        await pilot.press("escape", "slash")
        assert isinstance(app.screen, SearchScreen)
        assert app.screen is not screen
        assert app.screen.query_one(Input).value == ""


@pytest.mark.parametrize("widget_type", [Input, TextArea])
async def test_slash_types_in_other_text_inputs(widget_type):
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        field = widget_type()
        await app.screen.mount(field)
        field.focus()
        await pilot.press("slash")
        assert not isinstance(app.screen, SearchScreen)
        assert app.focused is field
        assert (field.value if isinstance(field, Input) else field.text) == "/"


async def test_search_input_empty_no_matches_and_shortcuts():
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("slash")
        screen = app.screen
        assert isinstance(screen, SearchScreen)
        assert app.focused is screen.query_one(Input)
        assert str(screen.query_one("#search-status").content) == "Type to search"
        await pilot.press("enter")
        assert app.screen is screen
        await pilot.press("f", "space", "q", "F")
        assert screen.query_one(Input).value == "f qF"
        assert tree.cursor_node.data.id == "a"
        assert tree.cursor_node.is_expanded
        assert str(screen.query_one("#search-status").content) == "No matching tasks"
        await pilot.press("enter", "escape")
        assert app.screen is not screen
        assert tree.cursor_node.data.id == "a"


async def test_search_duplicate_titles_markers_highlights_and_typing():
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        await pilot.press("slash")
        screen = app.screen
        screen.query_one(Input).value = "TARGET"
        await pilot.pause()
        assert [result.task.id for result in screen.results] == ["c", "d"]
        table = screen.query_one(DataTable)
        first = table.get_cell("c", "title")
        assert first.plain == "> Target leaf"
        assert first.get_style_at_offset(Console(), 2).bold
        assert not first.get_style_at_offset(Console(), 9).bold
        assert table.get_cell("c", "path").plain == "Root / Implementation / Storage"
        await pilot.press("up")
        assert screen.selected == 0
        await pilot.press("down", "down")
        assert screen.selected == 1
        assert table.cursor_row == 1
        assert table.get_cell("c", "title").plain.startswith("  ")
        assert table.get_cell("d", "title").plain.startswith("> ")
        assert app.focused is screen.query_one(Input)
        await pilot.press("space", "l")
        assert screen.query_one(Input).value == "TARGET l"
        assert screen.selected == 0


async def test_search_hidden_tasks_and_jump_leaf_actual_parent_chain():
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("down", "space", "up", "space", "slash")  # collapse B and A
        app.screen.query_one(Input).value = "target leaf"
        await pilot.pause()
        await pilot.press("down", "enter")  # duplicate title, stable ID D
        assert tree.cursor_node.data.id == "d"
        assert app.query_one("#repository").content.plain == "Repo | Root / Implementation / Storage"
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "b"
        assert tree.cursor_node.is_expanded
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "a"
        assert tree.cursor_node.is_expanded


async def test_search_outside_focus_jump_branch_and_root_leaf():
    app = TaskTreeApp("Repo", sample())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "f", "slash")  # inside Storage
        app.screen.query_one(Input).value = "VIEWER"
        await pilot.pause()
        await pilot.press("enter")
        assert tree.cursor_node.data.id == "f"
        assert app.query_one("#repository").content.plain == "Repo | Root / Implementation / Viewer"
        await pilot.press("escape")
        assert tree.cursor_node.data.id == "e"
        await pilot.press("slash")
        app.screen.query_one(Input).value = "root leaf"
        await pilot.pause()
        await pilot.press("enter")
        assert tree.cursor_node.data.id == "g"
        assert app.query_one("#repository").content.plain == "Repo | Root"


async def test_search_cancel_restores_focus_expansion_selection_and_scroll():
    tasks = [Task("a", "Branch", [Task(str(i), f"Child {i}", [Task(f"leaf-{i}", "Leaf")]) for i in range(30)])]
    app = TaskTreeApp("Repo", tasks)
    async with app.run_test(size=(65, 12)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "space", *(["down"] * 20))
        selected = tree.cursor_node.data.id
        scroll = tree.scroll_y
        path = app.query_one("#repository").content.plain
        expanded = {node.data.id: node.is_expanded for node in tree.root.children}
        await pilot.press("slash")
        app.screen.query_one(Input).value = "leaf"
        await pilot.pause()
        await pilot.press(*(["down"] * 15), "escape")
        assert tree.cursor_node.data.id == selected
        assert tree.scroll_y == scroll
        assert app.query_one("#repository").content.plain == path
        assert {node.data.id: node.is_expanded for node in tree.root.children} == expanded
        assert app.focused is tree


async def test_search_results_scroll_and_path_resize():
    tasks = [Task("root", "A very long parent branch", [Task(str(i), f"Match {i}") for i in range(30)])]
    app = TaskTreeApp("Repo", tasks)
    async with app.run_test(size=(60, 14)) as pilot:
        await pilot.press("slash")
        screen = app.screen
        screen.query_one(Input).value = "match"
        await pilot.pause()
        table = screen.query_one(DataTable)
        assert table.scroll_y == 0
        await pilot.press(*(["down"] * 15))
        assert screen.selected == 15
        assert table.scroll_y > 0
        scroll = table.scroll_y
        await pilot.press("up")
        assert table.scroll_y == scroll
        await pilot.resize_terminal(40, 14)
        await pilot.pause()
        path = table.get_cell("0", "path").plain
        assert path.startswith("…")
        assert path.endswith("parent branch")
        assert screen.selected == 14


async def test_empty_repository_search():
    app = TaskTreeApp("Repo", [])
    async with app.run_test() as pilot:
        await pilot.press("slash", "x", "enter")
        assert isinstance(app.screen, SearchScreen)
        assert app.screen.selected == -1
        await pilot.press("escape")
        assert str(app.query_one("#empty").content) == "No tasks yet."
