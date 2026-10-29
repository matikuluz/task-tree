# Tasktree

A Python terminal task tree for Git repositories, built with Textual. Selection,
focus, and branch expansion live only in memory. The bottom bar offers inline
title editing and an Add placeholder.

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
file. `open` requires a valid file. Browsing does not write it; explicitly saving
an edited title updates that title atomically.

## Controls

| Key | Action |
| --- | --- |
| Up / Down | Move one visible task, without wrapping |
| Shift + Up / Down | Move to the previous / next task with the same parent, skipping descendants |
| Space | Expand or collapse the selected branch; no effect on leaves |
| F | Focus the selected branch, showing its children and descendants |
| Escape | Return one scope level and select the branch just exited |
| R | Return directly to Root and select the current task's top-level ancestor |
| / | Open title search across the entire task tree |
| Q | Exit |
| Left / Right | Select a bottom-bar action, wrapping around available actions |
| Enter | Activate Add's placeholder or edit the selected task's title |

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
At Root, Escape does nothing; F on a leaf does nothing. Enter activates the
selected bottom-bar action while browsing.

R exits all nested focus scopes at once, clears the focus path, and selects the
top-level ancestor of the previously selected task. It scrolls only as needed to
reveal that task, preserving expansion states and the selected bottom-bar action.
At Root (including an empty tree), R does nothing. In search and other text
inputs, r types normally. Escape continues to return just one hierarchy level.

Arrow keys, sibling shortcuts, and scrolling operate only within the current
scope. Expansion changes persist across scope changes for the current session,
including when focusing a collapsed branch. Focus, selection, and expansion never
modify the task file.

## Action bar

The bottom bar starts with Add selected: **[+ Add task]** [✎]. Left / Right
switches to Edit: [+] **[✎ Edit task]**, wrapping at either end. The entire
selected item is bold; unselected items show only their bracketed symbol.
Task selection remains highlighted, and Up / Down, sibling navigation, focus,
and returning from search preserve the selected action.

Enter on Add shows a temporary, non-blocking notification: `Add task — coming soon`.
Enter on Edit opens the selected task's inline title editor.
In an empty tree, Add remains selected and Edit is dimmed and struck through;
navigation skips unavailable actions. The bar wraps onto extra rows if needed
when the terminal narrows. During search or text entry the bar is hidden and its
bindings yield to the input. Enter in search still jumps to a result, and Escape
still cancels. Only an explicitly saved title edit modifies the task file.

## Inline title editing

Select Edit with Left / Right, then press Enter. An input replaces the selected
task's title in place, preserving the surrounding tree, indentation, expansion,
selection, and scroll. It starts with the original title, a blinking cursor at
the end, and no selected text. The action bar is hidden during editing.

Normal text editing works, including Backspace, Delete, Home, End, and Left /
Right. All browsing shortcuts are suspended: q, f, r, /, and Space type normally,
Up / Down do not navigate tasks, and Tab keeps focus in the editor.

Enter validates and saves the title. Empty or whitespace-only titles, line
breaks, and control characters are rejected with a small message beside the
edited row. Validation and save errors retain the draft so you can correct it
and press Enter to retry, or Escape to cancel without writing. Saving changes
only the matching stable ID's title in the latest validated file, preserving IDs,
children, order, and other task data. A flushed temporary file in the same
directory is atomically replaced into `.tasktree.json`; a failed replacement
leaves the original file intact. JSON whitespace may be reformatted on save.

After save or cancellation, the same task and Edit action remain selected and
the action bar returns. Search results and parent paths use saved titles.
Add remains a placeholder; task creation is not implemented.

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
Action-bar tests cover wraparound, task and focus navigation, unavailable Edit in
empty trees, temporary placeholder messages, search and text-input isolation,
selection restoration, and narrow-terminal wrapping.
Return-to-root tests cover nested scopes, ancestor selection and minimal scrolling,
expansion and action preservation, root and empty-tree no-ops, unchanged Escape
navigation, and typing r in search and text inputs.
Editing tests cover saving and reopening, cancellation, invalid titles, native
editing keys, shortcut isolation, scrolled-row geometry, preservation of other
task data, atomic replacement, save failure recovery, and retry or cancellation.

Textual is pinned to 8.2.8, whose installed source/docstrings were checked for
`Tree` bindings, `render_label`, cursor clamping, and `scroll_to_line`. The small
subclass replaces inherited bindings and uses the existing Tree/ScrollView
geometry. API reference: https://textual.textualize.io/widgets/tree/

Before relying on a terminal/platform, manually check glyph rendering and bold
selection, held arrow keys, resize behaviour, and restoration of the terminal
after Q. Headless checks do not establish real-terminal rendering or restoration.
