"""Inline single-line title editing with explicit save and cancellation."""

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


class TitleEditor(Input):
    """Keep editing keys local instead of invoking surrounding tree bindings."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("up,down,shift+up,shift+down,tab,shift+tab", "stay", "Edit", show=False, priority=True),
    ]
    DEFAULT_CSS = """
    TitleEditor { position: absolute; height: 1; border: none; padding: 0;
                  margin: 0; background: $surface; }
    """

    class Cancelled(Message):
        """Discard the draft without saving."""

    def __init__(self, title: str) -> None:
        super().__init__(title, id="title-editor", select_on_focus=False)
        self.cursor_blink = True

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())

    def action_stay(self) -> None:
        pass
