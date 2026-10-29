# Tasktree

A first, read-only Python terminal task viewer for Git repositories, built with
Textual. Selection and branch expansion live only in memory. There is no editing,
saving, or action console in this milestone.

## Install and run

Requires Python 3.11+ and Git on PATH. From this source checkout:

```text
python -m venv .venv
```

On Windows (PowerShell or Command Prompt, no activation required):

```text
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\tasktree init
.venv\Scripts\tasktree open
```

On macOS/Linux use `.venv/bin/python` and `.venv/bin/tasktree` instead. An
activated environment also provides the shorter commands below:

```text
tasktree init
tasktree open
python -m tasktree init
python -m tasktree open
```

Run commands inside the Git repository you want to view. Subdirectories resolve to
the checkout root using `git rev-parse --show-toplevel`; linked Git worktrees have
their own task file. Outside a Git working repository, the command reports an error.
`init` creates `.tasktree.json` exclusively and refuses to overwrite an existing
file. `open` requires a valid file and never writes it.

## Controls

| Key | Action |
| --- | --- |
| Up / Down | Move one visible task, without wrapping |
| Space | Expand or collapse the selected branch; no effect on leaves |
| Q | Exit |
| Left / Right / Enter | No task action |

All branches start expanded, with the first task selected. The selected task is
bold with a `>` marker after its hierarchy indentation. Titles occupy one row and
are clipped at the right edge. Scrolling moves only far enough to keep selection
visible, without animation or centring. Empty files show `No tasks yet.`

## File format

```json
{
  "schema_version": 1,
  "tasks": [
    {
      "id": "planning",
      "title": "Plan the project",
      "children": [
        {"id": "requirements", "title": "Review requirements", "children": []}
      ]
    }
  ]
}
```

Version 1 requires exactly `schema_version` and `tasks` at the top level, and
exactly `id`, `title`, and `children` on every task. `schema_version` is integer 1.
Task and children arrays define display order. IDs are globally unique, nonempty
strings: keep them stable when editing titles. Titles are nonempty single-line
strings. Control characters and line separators are rejected. Textual markup in
titles is displayed literally. UTF-8 files, including those with a BOM, are accepted.
Validation failures identify the affected field when possible and leave the file
unchanged. No UI state is stored in JSON.

## Sample data

`examples/sample.tasktree.json` contains 28 tasks, four sibling branches, and
three nesting levels. It is never loaded or copied automatically.

1. Run `tasktree init` in a testing repository.
2. Copy the sample explicitly using the cross-platform Python command below.
   **It replaces that repository's `.tasktree.json`: use only an empty initialized
   file, or back up existing task data first.**
3. Run `tasktree open` in the testing repository.

```text
python -c "import shutil; shutil.copyfile(r'ABSOLUTE_PATH_TO_SOURCE/examples/sample.tasktree.json', r'ABSOLUTE_PATH_TO_TEST_REPOSITORY/.tasktree.json')"
```

Replace both placeholder paths with actual absolute paths (Windows paths may use
forward slashes). To keep the source checkout's data untouched, use a separate
directory, run `git init` there, and invoke tasktree using its installed absolute
executable path or activate the source environment first.

## Development and verification

```text
.venv\Scripts\python -m pytest
```

Tests cover exclusive initialization, nested loading and invalid input, CLI
errors, discovery from subdirectories and a real linked worktree, visible-row
navigation, collapse/expand, boundary scrolling, resize visibility, marker
rendering, literal titles, empty state, quitting, and unchanged task bytes and
modification time after a viewer session. UI tests use Textual's headless pilot.

Textual is pinned to 8.2.8, whose installed source/docstrings were checked for
`Tree` bindings, `render_label`, cursor clamping, and `scroll_to_line`. The small
subclass replaces inherited bindings and uses the existing Tree/ScrollView
geometry. API reference: https://textual.textualize.io/widgets/tree/

Before relying on a terminal/platform, manually check glyph rendering and bold
selection, held arrow keys, resize behaviour, and restoration of the terminal
after Q. Headless checks do not establish real-terminal rendering or restoration.
