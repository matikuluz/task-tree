"""Thin command-line interface."""

import argparse
import sys

from .store import TaskStore, TaskStoreError, repository_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="View a Git repository's task tree.")
    parser.add_argument("command", choices=("init", "open"))
    args = parser.parse_args(argv)
    try:
        root = repository_root()
        store = TaskStore(root)
        if args.command == "init":
            store.init()
            print(f"Created {store.path}")
        else:
            tasks = store.load()
            from .app import TaskTreeApp

            TaskTreeApp(root.name, tasks, store=store).run()
    except TaskStoreError as error:
        print(f"tasktree: {error}", file=sys.stderr)
        return 1
    return 0
