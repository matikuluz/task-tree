"""A search screen that leaves the underlying tree state untouched until Enter."""

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Static

from .search import SearchResult, TaskSearch, matching_spans


def shortened_path(path: str, width: int) -> str:
    """Keep the end of long parent paths within the available terminal cells."""
    if cell_len(path) <= width:
        return path
    suffix = path
    while suffix and cell_len(suffix) > max(0, width - 1):
        suffix = suffix[1:]
    return "…" + suffix if width > 0 else ""


class SearchScreen(ModalScreen[SearchResult | None]):
    """Keep input focused while arrow keys move a highlighted result row."""

    BINDINGS = [
        Binding("up", "previous_result", "Previous", priority=True),
        Binding("down", "next_result", "Next", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "accept", "Open", priority=True),
        Binding("tab,shift+tab", "keep_input", "Type", show=False, priority=True),
    ]
    DEFAULT_CSS = """
    SearchScreen { layout: vertical; background: $surface; }
    #search-heading { height: 1; padding: 0 1; text-style: bold; }
    #search-results { height: 1fr; overflow-x: hidden; }
    #search-results > .datatable--cursor { background: $primary 35%; text-style: none; }
    #search-status { height: 1; padding: 0 1; }
    #search-input { height: 3; dock: bottom; }
    #search-help { height: 1; padding: 0 1; }
    """

    def __init__(self, search: TaskSearch) -> None:
        super().__init__()
        self.search = search
        self.response = search.evaluate("")
        self.results: list[SearchResult] = []
        self.selected = -1

    def compose(self) -> ComposeResult:
        yield Static("Search all tasks", id="search-heading")
        yield DataTable(id="search-results", cursor_type="row", show_row_labels=False)
        yield Static("Type to search", id="search-status")
        yield Static("↑/↓ Results   Enter Open   Esc Cancel", id="search-help")
        yield Input(placeholder="Search title or Branch/title", id="search-input")

    def on_mount(self) -> None:
        self.query_one(DataTable).can_focus = False
        self.query_one(Input).focus()
        self._render_results()

    def _title(self, index: int) -> Text:
        title = self.results[index].task.title
        text = Text("> " if index == self.selected else "  ", no_wrap=True, overflow="ellipsis")
        highlighted = Text(title, no_wrap=True, overflow="ellipsis")
        for start, end in matching_spans(title, self.response.query.title):
            highlighted.stylize("bold", start, end)
        text.append_text(highlighted)
        return text

    def on_input_changed(self, message: Input.Changed) -> None:
        self.response = self.search.evaluate(message.value)
        self.results = self.response.results
        self.selected = 0 if self.results else -1
        self._render_results()

    def _render_results(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        # Leave room for cell padding and the vertical scrollbar.
        available = max(2, self.size.width - 6)
        title_width = max(1, available // 2)
        path_width = max(1, available - title_width)
        table.add_column("Task title", key="title", width=title_width)
        table.add_column("Parent path", key="path", width=path_width)
        for index, result in enumerate(self.results):
            table.add_row(
                self._title(index), Text(shortened_path(result.parent_path, path_width)),
                key=result.task.id,
            )
        if self.selected >= 0:
            table.move_cursor(row=self.selected, animate=False)
        self.query_one("#search-status", Static).update(
            "Type to search" if not self.query_one(Input).value else
            "No matching branch path" if not self.response.path_matched else
            "No matching tasks" if not self.results else f"{len(self.results)} matching tasks"
        )

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._render_results)

    def _move_result(self, delta: int) -> None:
        if not self.results:
            return
        old = self.selected
        self.selected = max(0, min(len(self.results) - 1, old + delta))
        table = self.query_one(DataTable)
        for index in (old, self.selected):
            table.update_cell(self.results[index].task.id, "title", self._title(index))
        table.move_cursor(row=self.selected, animate=False)

    def action_previous_result(self) -> None:
        self._move_result(-1)

    def action_next_result(self) -> None:
        self._move_result(1)

    def action_keep_input(self) -> None:
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_accept(self) -> None:
        if self.selected >= 0:
            self.dismiss(self.results[self.selected])
