"""Persistent selection of browsing actions."""

from dataclasses import dataclass

from rich.text import Text
from textual.widgets import Static


@dataclass(frozen=True, slots=True)
class Action:
    """One action's display and availability requirements."""

    symbol: str
    label: str
    requires_task: bool = False


class ActionBar(Static):
    """Render actions without moving keyboard focus away from the task tree."""

    ACTIONS = (Action("+", "Add task"), Action("✎", "Edit task", requires_task=True))
    DEFAULT_CSS = """
    ActionBar { height: auto; min-height: 1; padding: 0 1; }
    """

    def __init__(self, has_task: bool) -> None:
        super().__init__(id="actions")
        self.has_task = has_task
        self.selected = 0

    @property
    def selected_action(self) -> Action:
        return self.ACTIONS[self.selected]

    def available(self, action: Action) -> bool:
        return self.has_task or not action.requires_task

    def move(self, direction: int) -> None:
        enabled = [index for index, action in enumerate(self.ACTIONS) if self.available(action)]
        self.selected = enabled[(enabled.index(self.selected) + direction) % len(enabled)]
        self.refresh(layout=True)

    def render(self) -> Text:
        text = Text(overflow="fold")
        for index, action in enumerate(self.ACTIONS):
            if index:
                text.append(" ")
            selected = index == self.selected
            label = f"{action.symbol} {action.label}" if selected else action.symbol
            style = "dim strike" if not self.available(action) else "bold" if selected else ""
            text.append(f"[{label}]", style=style)
        return text
