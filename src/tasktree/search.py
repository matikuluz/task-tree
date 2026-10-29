"""Query parsing, branch filtering, and title matching independent of Textual."""

from dataclasses import dataclass

from .models import Task


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """The final slash separates a branch path from a literal title query."""

    title: str
    path: tuple[str, ...] | None = None
    anchored: bool = False

    @classmethod
    def parse(cls, text: str) -> "SearchQuery":
        if "/" not in text:
            return cls(text)
        path, title = text.rsplit("/", 1)
        segments = tuple(path.split("/"))
        anchored = segments[0].casefold() == "root"
        return cls(title, segments[1:] if anchored else segments, anchored)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A stable task identity and its actual ancestors in tree order."""

    task: Task
    ancestors: tuple[Task, ...]

    @property
    def parent_path(self) -> str:
        return " / ".join(["Root", *(task.title for task in self.ancestors)])


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """Matches and enough query context to explain empty results."""

    query: SearchQuery
    results: list[SearchResult]
    path_matched: bool = True


class TaskSearch:
    """Index all tasks once and rank literal, case-insensitive title matches."""

    def __init__(self, tasks: list[Task]) -> None:
        self.entries: list[SearchResult] = []
        self._index(tasks, ())

    def _index(self, tasks: list[Task], ancestors: tuple[Task, ...]) -> None:
        for task in tasks:
            self.entries.append(SearchResult(task, ancestors))
            self._index(task.children, (*ancestors, task))

    def find(self, query: str) -> list[SearchResult]:
        return self.evaluate(query).results

    def evaluate(self, text: str) -> SearchResponse:
        """Filter descendants once in tree order, then rank any title matches."""
        query = SearchQuery.parse(text)
        candidates = self.entries
        if query.path is not None:
            if query.anchored and not query.path:  # Root/ includes every task.
                branch_ids = None
            else:
                branch_ids = {
                    entry.task.id for entry in self.entries
                    if entry.task.children and self._matches_path(entry, query)
                }
                if not branch_ids:
                    return SearchResponse(query, [], path_matched=False)
            if branch_ids is not None:
                # Entries are visited once, so overlapping matching branches cannot duplicate IDs.
                candidates = [entry for entry in self.entries if any(
                    ancestor.id in branch_ids for ancestor in entry.ancestors
                )]
        if not query.title:
            return SearchResponse(query, candidates if query.path is not None else [])
        folded = query.title.casefold()
        groups: list[list[SearchResult]] = [[], [], []]
        for entry in candidates:
            title = entry.task.title.casefold()
            if folded in title:
                rank = 0 if title == folded else 1 if title.startswith(folded) else 2
                groups[rank].append(entry)
        return SearchResponse(query, [entry for group in groups for entry in group])

    @staticmethod
    def _matches_path(entry: SearchResult, query: SearchQuery) -> bool:
        assert query.path is not None
        if not query.path or any(not segment for segment in query.path):
            return False
        path = tuple(task.title.casefold() for task in (*entry.ancestors, entry.task))
        segments = tuple(segment.casefold() for segment in query.path)
        return path == segments if query.anchored else path[-len(segments):] == segments


def matching_spans(title: str, query: str) -> list[tuple[int, int]]:
    """Find every occurrence, mapping Unicode casefold offsets to original text."""
    if not query:
        return []
    offsets = [index for index, char in enumerate(title) for _ in char.casefold()]
    folded, needle = title.casefold(), query.casefold()
    spans = []
    start = folded.find(needle)
    while start != -1:
        spans.append((offsets[start], offsets[start + len(needle) - 1] + 1))
        start = folded.find(needle, start + 1)
    return spans
