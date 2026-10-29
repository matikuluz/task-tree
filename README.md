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
| Shift + Up / Down | Move to the previous / next task with the same parent, skipping descendants |
| Space | Expand or collapse the selected branch; no effect on leaves |
| F | Focus the selected branch, showing its children and descendants |
| Escape | Return one scope level and select the branch just exited |
| / | Open title search across the entire task tree |
| Q | Exit |
| Left / Right / Enter | No task action |

All branches start expanded, with the first task selected. The selected task is
bold with a `>` marker after its hierarchy indentation. Titles occupy one row and
are clipped at the right edge. Scrolling moves only far enough to keep selection
visible, without animation or centring. Empty files show `No tasks yet.`

Sibling navigation works at every nesting level, including top-level tasks. At
the first or last sibling, movement in that direction does nothing: it never
wraps or jumps to another parent. Expansion states are preserved, and sibling
jumps use the same scrolling behaviour as ordinary navigation.

Focus mode shows the current path in the header, for example
`Root / Planning / Define scope`. The focused task becomes the scope root in
the breadcrumb and is not a selectable row. Its first child is selected, and
the existing expansion states determine which descendants are visible. Press F
again on a child branch to focus further. Escape moves to the parent scope,
selecting the task whose branch you exited; focusing a deeply nested task builds
the full ancestor path, so Escape still returns one hierarchy level at a time.
At Root, Escape does nothing; F on a leaf does nothing. Enter remains available
for future action confirmation and currently has no task action.

Arrow keys, sibling shortcuts, and scrolling operate only within the current
scope. Expansion changes persist across scope changes for the current session,
including when focusing a collapsed branch. Focus, selection, and expansion never
modify the task file.

## Search

Press / while browsing to open a results view with a text input at the bottom.
The opening slash is consumed, so the query starts empty. Inside search or any
other text input, / types normally. Ctrl + F is not bound to search.
Results update as you type and include all tasks, even collapsed descendants and tasks outside the
current focus. Matching is case-insensitive and literal: exact titles rank first,
then title prefixes, then substrings. Each group retains depth-first tree order.
There is no fuzzy matching or attribute filtering.

Queries without `/` search titles globally. With `/`, everything before the final
slash filters branches, and everything after it searches descendant titles:

| Query | Results |
| --- | --- |
| `Implementation/` | All descendants of every Implementation branch, in tree order |
| `Implementation/login` | Descendants with login in their titles, ranked as above |
| `Implementation/Storage/check` | Titles matching check beneath consecutive Implementation → Storage branches |
| `Root/Implementation/` | Descendants of top-level Implementation branches only |
| `Root/` | Every task, in tree order |

Branch names match complete, case-insensitive segments. Paths beginning with
`Root/` are anchored at the tree root; other paths may start anywhere. Segments
must be consecutive: `Implementation/Storage/` does not match an intervening
branch. Every matching branch is searched, including collapsed descendants, and
overlapping matches return each stable task ID only once. The filtered branch
itself is excluded (but can appear as a descendant of another matching branch).
Empty path segments do not match a branch.

A trailing slash lists descendants without title-match bolding. When a title
query follows the slash, only matching title substrings are bold; paths are not
highlighted. Results always display their full actual parent paths, truncated
only when necessary. Unmatched paths show `No matching branch path`; a matched
path with no matching titles shows `No matching tasks`.

Results show two columns: the task title and its parent path, such as
`Root / Implementation`. All matching portions of the original title are bold.
The selected row has a `>` marker and background highlight. Long paths use `…`
at the beginning to preserve the final path components where possible. An empty
query shows `Type to search`; a query without matches shows `No matching tasks`.

While searching, Up / Down move through results without wrapping and scroll only
as needed to keep the selection visible. Typing stays in the input, including
F, Q, and Space; tree shortcuts are inactive. Enter opens the selected result:

- For a task with children, focus into that task and select its first child.
- For a leaf, focus into its parent and select the leaf. A root-level leaf is
  selected at Root.

Destination ancestors are expanded as needed, and the full actual ancestor chain
is restored in the breadcrumb. Escape after a jump navigates up those parents.
Enter with no selected result does nothing. Escape while searching cancels and
restores the exact previous scope, selection, expansion, and scroll position.
Search and result navigation never write to the task file.

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
navigation, sibling jumps and boundaries, nested focus and return, scope
boundaries, expansion preservation, boundary scrolling, resize visibility, marker
rendering, literal titles and breadcrumbs, empty state, quitting, and unchanged task bytes and
modification time after a viewer session. UI tests use Textual's headless pilot.
Search tests cover ranking, Unicode case-insensitive matching and highlighting,
duplicate titles with stable IDs, hidden tasks, input isolation, cancellation,
result scrolling and truncation, and jumps to branch and leaf results.
Path tests cover trailing slashes, consecutive nested segments, root anchoring,
case-insensitive complete names, overlapping duplicate branches, unmatched paths,
title-only ranking, and title-only highlighting.

Textual is pinned to 8.2.8, whose installed source/docstrings were checked for
`Tree` bindings, `render_label`, cursor clamping, and `scroll_to_line`. The small
subclass replaces inherited bindings and uses the existing Tree/ScrollView
geometry. API reference: https://textual.textualize.io/widgets/tree/

Before relying on a terminal/platform, manually check glyph rendering and bold
selection, held arrow keys, resize behaviour, and restoration of the terminal
after Q. Headless checks do not establish real-terminal rendering or restoration.
