import json
import pytest

from rich.console import Console
from rich.style import Style
from textual.widgets import Input

from tasktree.action_bar import ActionBar
from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.placement import PlacementModel
from tasktree.placement_ui import PlacementScreen, PlacementTree
from tasktree.store import TaskStore
from tasktree.tree import TaskTree


def tasks():
    return [
        Task("a", "Branch", [
            Task("b", "Nested", [Task("c", "Leaf")]),
            Task("d", "Sibling"),
        ]),
        Task("e", "Last"),
    ]


def key(entry):
    if entry.kind == "insert":
        return ("insert", entry.ancestors[-1].id if entry.ancestors else None, entry.index)
    return (entry.kind, entry.task.id if entry.task else None)


def test_insertion_order_and_initial_position_after_expanded_subtree():
    model = PlacementModel(tasks(), after_id="a")
    assert [key(entry) for entry in model.entries] == [
        ("insert", None, 0), ("folder", "a"),
        ("insert", "a", 0), ("folder", "b"),
        ("insert", "b", 0), ("insert", "b", 1),
        ("insert", "a", 1), ("insert", "a", 2),
        ("insert", None, 1), ("insert", None, 2),
    ]
    assert key(model.current) == ("insert", None, 1)
    selected_row = next(index for index, row in enumerate(model.rows) if row.entry == model.current)
    assert [row.task.id for row in model.rows[:selected_row] if row.task] == ["a", "b", "c", "d"]
    nested = PlacementModel(tasks(), after_id="b")
    assert key(nested.current) == ("insert", "a", 1)
    assert not hasattr(nested.current, "id")


def test_collapsed_branches_folder_options_and_space_toggle():
    expansion = {"a": False, "b": False}
    model = PlacementModel(tasks(), expanded=expansion, after_id="a")
    assert [key(entry) for entry in model.entries] == [
        ("insert", None, 0), ("folder", "a"), ("insert", None, 1), ("insert", None, 2),
    ]
    model.move(-1)
    assert key(model.current) == ("folder", "a")
    model.toggle()
    assert model.path == ()
    assert key(model.current) == ("folder", "a")
    assert ("folder", "b") in [key(entry) for entry in model.entries]
    assert ("insert", "b", 0) not in [key(entry) for entry in model.entries]
    assert expansion == {"a": False, "b": False}  # copied, not mutated
    model.toggle()
    assert not model.expanded["a"]


def test_folder_entry_nested_go_back_and_empty_scope():
    values = tasks()
    model = PlacementModel(values, expanded={"a": False, "b": False}, after_id="a")
    model.move(-1)
    assert model.enter()
    assert [task.id for task in model.path] == ["a"]
    assert key(model.current) == ("insert", "a", 0)
    model.move(1)
    assert key(model.current) == ("folder", "b")
    model.enter()
    assert [task.id for task in model.path] == ["a", "b"]
    assert key(model.current) == ("insert", "b", 0)
    model.boundary(False)
    assert model.current.kind == "back"
    model.enter()
    assert key(model.current) == ("folder", "b")
    model.boundary(False)
    model.enter()
    assert key(model.current) == ("folder", "a")
    assert not any(entry.kind == "back" for entry in model.entries)
    empty = PlacementModel([])
    assert len(empty.entries) == 1
    empty.move(-1)
    empty.move(1)
    assert empty.selected == 0
    assert not empty.enter()
    # An empty scoped container still has a back command and one insertion gap.
    empty_task = Task("empty", "Empty")
    empty_scope = PlacementModel([empty_task], path=(empty_task,))
    assert [entry.kind for entry in empty_scope.entries] == ["back", "insert"]


async def test_ui_initial_row_and_navigation_to_folder_and_back():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        bar = app.query_one(ActionBar)
        await pilot.press("enter")
        screen = app.screen
        assert isinstance(screen, PlacementScreen)
        assert not bar.visible
        assert key(screen.model.current) == ("insert", None, 1)
        selected = next(row for row in screen.model.rows if row.entry == screen.model.current)
        assert screen._label(selected).plain == "Add task here"
        await pilot.press("home", "down")
        assert key(screen.model.current) == ("folder", "a")
        folder = next(row for row in screen.model.rows if row.entry == screen.model.current)
        assert "Branch  [Enter folder]" in screen._label(folder).plain
        await pilot.press("enter")
        assert key(screen.model.current) == ("insert", "a", 0)
        assert "Root / Branch" in str(screen.query_one("#placement-path").content)
        await pilot.press("home")
        assert screen.model.current.kind == "back"
        await pilot.press("enter")
        assert key(screen.model.current) == ("folder", "a")
        assert screen.model.path == ()


async def test_placeholder_activation_and_conflicting_shortcuts_are_isolated():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        tree = app.query_one(TaskTree)
        selected = tree.cursor_node
        await pilot.press("enter", "enter")
        screen = app.screen
        assert isinstance(screen, PlacementScreen)
        assert [notification.message for notification in app._notifications] == ["Task creation — coming soon"]
        current = screen.model.current
        await pilot.press("f", "F", "r", "R", "slash", "left", "right", "shift+up", "shift+down", "q")
        assert app.screen is screen
        assert screen.model.current == current
        assert tree.cursor_node is selected
        assert not app.query(Input)
        assert app.query_one(ActionBar).selected == 0
        await pilot.press("up", "down")
        assert app.screen is screen


async def test_empty_tree_shows_one_position_and_cancels():
    app = TaskTreeApp("Repo", [])
    async with app.run_test() as pilot:
        await pilot.press("enter")
        screen = app.screen
        assert len(screen.model.entries) == 1
        assert screen.query_one(PlacementTree).last_line == 0
        await pilot.press("up", "down", "home", "end", "enter")
        assert screen.model.selected == 0
        await pilot.press("escape")
        assert not isinstance(app.screen, PlacementScreen)
        assert app.query_one(ActionBar).visible
        assert not app.query(TaskTree)


async def test_cancellation_restores_focused_browsing_state_and_scroll():
    values = [Task("a", "Branch", [
        Task(str(i), f"Child {i}", [Task(f"leaf-{i}", "Leaf")]) for i in range(25)
    ])]
    app = TaskTreeApp("Repo", values)
    async with app.run_test(size=(80, 13)) as pilot:
        tree = app.query_one(TaskTree)
        await pilot.press("f", "space", *(["down"] * 20))
        selected = tree.cursor_node
        scroll = tree.scroll_y
        expansion = tree.expansion_snapshot()
        path = app.query_one("#repository").content.plain
        search_ids = [entry.task.id for entry in app.search.entries]
        await pilot.press("enter", "home", "down", "down", "space", "enter", "end")
        assert len(app.screen.model.path) == 2
        assert app.screen.model.expanded["0"]
        await pilot.press("escape")
        assert tree.cursor_node is selected
        assert tree.scroll_y == scroll
        assert tree.expansion_snapshot() == expansion
        assert app.query_one("#repository").content.plain == path
        assert app.query_one(ActionBar).selected == 0
        assert app.query_one(ActionBar).visible
        assert app.focused is tree
        assert [entry.task.id for entry in app.search.entries] == search_ids


async def test_placement_scrolling_is_minimal_and_does_not_wrap():
    app = TaskTreeApp("Repo", [Task(str(i), f"Task {i}") for i in range(35)])
    async with app.run_test(size=(60, 12)) as pilot:
        await pilot.press("enter", "home")
        screen = app.screen
        options = screen.query_one(PlacementTree)
        assert options.scroll_y == 0
        await pilot.press(*(["down"] * 8))
        assert screen.model.current.index == 8
        assert options.scroll_y == 0
        await pilot.press("down")
        assert screen.model.current.index == 9
        assert options.scroll_y == 0
        await pilot.press("down")
        assert options.scroll_y == 1
        await pilot.press("up")
        assert options.scroll_y == 1
        await pilot.press("end")
        assert screen.model.current.index == 35
        last_scroll = options.scroll_y
        await pilot.press("down")
        assert options.scroll_y == last_scroll
        await pilot.resize_terminal(40, 10)
        await pilot.pause()
        assert options.scroll_y > 0
        await pilot.press("home", "up")
        assert screen.model.selected == 0
        assert options.scroll_y == 0


async def test_placement_only_saves_expansion_preferences(tmp_path):
    data = {"schema_version": 1, "tasks": [
        {"id": "a", "title": "Branch", "children": [
            {"id": "b", "title": "Child", "children": []},
        ]},
    ]}
    store = TaskStore(tmp_path)
    store.path.write_text(json.dumps(data), encoding="utf-8")
    before = store.path.read_bytes()
    timestamp = store.path.stat().st_mtime_ns
    app = TaskTreeApp("Repo", store.load(), store=store)
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "space", "enter", "enter", "home", "enter", "escape")
    data["tasks"][0]["expanded"] = False
    assert json.loads(store.path.read_text()) == data


def rendered_rows(tree):
    return [tree.render_line(line).text.rstrip() for line in range(tree.last_line + 1)]


@pytest.mark.parametrize("focused, steps", [(False, 3), (False, 14), (True, 3), (True, 9)])
async def test_transition_anchors_existing_task_after_layout_and_cancel(focused, steps):
    values = [Task("a", "Implementation", [Task("b", "Storage", [
        Task(str(i), f"Task {i}") for i in range(30)
    ])])]
    app = TaskTreeApp("Repo", values)
    async with app.run_test(size=(80, 13)) as pilot:
        browsing = app.query_one(TaskTree)
        if focused:
            await pilot.press("f", "f")
        await pilot.press(*(["down"] * steps))
        await pilot.pause()
        task_id = browsing.cursor_node.data.id
        old_scroll = browsing.scroll_y
        old_y = browsing.scrollable_content_region.y + browsing.cursor_line - int(old_scroll)
        old_line = browsing.render_line(browsing.cursor_line - int(old_scroll)).text
        await pilot.press("enter")
        await pilot.pause()
        tree = app.screen.query_one(PlacementTree)
        line = next(i for i in range(tree.last_line + 1)
                    if tree.get_node_at_line(i).data.task is not None and
                    tree.get_node_at_line(i).data.task.id == task_id)
        # Only minimum scrolling is permitted when the insertion is below the viewport.
        excess = max(0, old_y + 1 - (tree.scrollable_content_region.bottom - 1))
        assert tree.scrollable_content_region.y + line - int(tree.scroll_y) == old_y - excess
        current_line = tree.render_line(line - int(tree.scroll_y)).text
        assert current_line.index(f"Task {task_id}") == old_line.index(f"Task {task_id}")
        assert tree.cursor_line == line + 1
        assert tree.scroll_y <= tree.cursor_line < tree.scroll_y + tree.scrollable_content_region.height
        await pilot.press("escape")
        await pilot.pause()
        assert browsing.scroll_y == old_scroll
        assert browsing.cursor_node.data.id == task_id
        assert browsing.render_line(browsing.cursor_line - int(old_scroll)).text == old_line


async def test_folder_labels_are_contextual_and_do_not_leave_rows_or_spacing():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "down", "down")
        screen = app.screen
        tree = screen.query_one(PlacementTree)
        assert key(screen.model.current) == ("folder", "b")
        rows = rendered_rows(tree)
        assert len(rows) == 5
        assert sum("[Enter folder]" in row for row in rows) == 1
        assert "+ ▼ Nested  [Enter folder]" in rows[1]
        assert rows[0].endswith("Branch")
        await pilot.press("down")
        rows = rendered_rows(tree)
        assert len(rows) == 6  # only the insertion row was added
        assert not any("[Enter folder]" in row for row in rows)
        assert rows[1].endswith("Nested")
        await pilot.press("up", "space")
        rows = rendered_rows(tree)
        assert len(rows) == 4
        assert "+ ▶ Nested  [Enter folder]" in rows[1]
        assert not any("Leaf" in row for row in rows)
        await pilot.press("space")
        assert len(rendered_rows(tree)) == 5


async def test_temporary_rows_use_native_connectors_before_and_after_children():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "down", "down", "down")
        tree = app.screen.query_one(PlacementTree)
        rows = rendered_rows(tree)
        assert rows[1] == "├──   ▼ Nested"
        assert rows[2] == "│   ├── + Add task here"
        assert rows[3] == "│   └──   Leaf"
        assert rows[4] == "└──   Sibling"
        await pilot.press("down")
        rows = rendered_rows(tree)
        assert rows[2] == "│   ├──   Leaf"
        assert rows[3] == "│   └── + Add task here"
        await pilot.press("down", "down")
        rows = rendered_rows(tree)
        assert rows[3] == "├──   Sibling"
        assert rows[4] == "└── + Add task here"


async def test_placement_uses_browsing_blue_guides_and_label_only_selection():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        browsing = app.query_one(TaskTree)
        active_guide_color = browsing.get_component_rich_style("tree--guides-selected").color
        await pilot.press("enter", "home", "down", "down", "down", "down")
        tree = app.screen.query_one(PlacementTree)
        assert tree.get_component_rich_style("tree--guides-selected").color == active_guide_color
        line = list(tree.render_line(tree.cursor_line))
        guides = [segment for segment in line if "├" in segment.text or "└" in segment.text]
        assert any(segment.style.color == active_guide_color for segment in guides)
        assert len({segment.style.bgcolor for segment in line}) == 1
        assert all(not segment.style.bold for segment in guides)
        label = tree.render_label(tree.cursor_node, Style(), Style())
        assert label.plain == "+ Add task here"
        assert all(label.get_style_at_offset(Console(), i).bold for i in range(len(label)))
        await pilot.press("up")
        selected_line = list(tree.render_line(tree.cursor_line))
        assert len({segment.style.bgcolor for segment in selected_line}) == 1
        assert "+ ▼ Nested  [Enter folder]" in tree.render_line(tree.cursor_line).text


async def test_focused_scope_connectors_and_go_back_alignment():
    app = TaskTreeApp("Repo", tasks())
    async with app.run_test() as pilot:
        await pilot.press("enter", "home", "down", "enter", "down")
        tree = app.screen.query_one(PlacementTree)
        rows = rendered_rows(tree)
        assert rows[0] == "  Go back"
        assert rows[1] == "+ ▼ Nested  [Enter folder]"
        assert rows[2] == "└──   Leaf"
        await pilot.press("enter")
        rows = rendered_rows(tree)
        assert rows == ["  Go back", "+ Add task here", "  Leaf"]
        await pilot.press("home", "enter")
        assert rendered_rows(tree)[1] == "+ ▼ Nested  [Enter folder]"
        await pilot.press("home", "enter")
        assert rendered_rows(tree)[0] == "+ ▼ Branch  [Enter folder]"
