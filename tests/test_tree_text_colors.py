import pytest

from tasktree.app import TaskTreeApp
from tasktree.models import Task
from tasktree.placement_ui import PlacementTree
from tasktree.tree import TaskTree


@pytest.mark.parametrize("mode", ["view", "add", "delete"])
async def test_selected_and_unselected_titles_change_color_with_navigation(mode):
    app = TaskTreeApp("Repo", [Task("a", "Alpha"), Task("b", "Beta")])
    async with app.run_test() as pilot:
        if mode != "view":
            await pilot.press("2" if mode == "add" else "4")
            tree = app.screen.query_one(PlacementTree)
        else:
            tree = app.query_one(TaskTree)

        def title_color(title):
            for line in range(tree.last_line + 1):
                strip = tree.render_line(line - int(tree.scroll_y))
                for segment in strip:
                    if title in segment.text:
                        return segment.style.color.get_truecolor().hex
            raise AssertionError(f"{title} not visible")

        if mode == "add":
            await pilot.press("home", "down")
            # Leaf tasks are context rows in Add mode; the insertion row is selected.
            selected = tree.cursor_line
            assert "Add task here" in tree.render_line(selected - int(tree.scroll_y)).text
            assert title_color("Add task here").lower() == "#ffffff"
            assert title_color("Alpha").lower() == "#888888"
            await pilot.press("down")
            assert title_color("Add task here").lower() == "#ffffff"
            assert title_color("Beta").lower() == "#888888"
        else:
            assert title_color("Alpha").lower() == "#ffffff"
            assert title_color("Beta").lower() == "#888888"
            await pilot.press("down")
            assert title_color("Alpha").lower() == "#888888"
            assert title_color("Beta").lower() == "#ffffff"
