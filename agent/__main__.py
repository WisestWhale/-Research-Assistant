"""Typed desktop agent. Run from the repo root: python -m agent"""

import sys
from pathlib import Path

from agent.apps import AppTableError, load_app_table
from agent.log import ActionLog, default_log_path
from agent.loop import CommandLoop
from agent.observer import windows
from agent.tools.launch import DesktopTools

APP_TABLE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "apps.json"
QUIT_WORDS = frozenset({"quit", "exit"})
PROMPT = "> "


def observe():
    return windows.foreground_exe(), windows.is_secure_desktop()


def ask_in_terminal(question):
    try:
        return input(f"{question} [y/N] ")
    except (EOFError, KeyboardInterrupt):
        # Interrupting an approval is a no, never a yes.
        print()
        return ""


def main():
    try:
        apps = load_app_table(APP_TABLE_PATH)
    except AppTableError as error:
        print(f"App table problem: {error}", file=sys.stderr)
        return 1
    log_path = default_log_path()
    loop = CommandLoop(apps, DesktopTools(apps), ActionLog(log_path), observe, ask_in_terminal)

    print(f"Desktop agent. Apps: {', '.join(sorted(apps.entries))}. Type 'quit' to stop.")
    print(f"Log: {log_path}")
    while True:
        try:
            text = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text.strip().casefold() in QUIT_WORDS:
            return 0
        if text.strip():
            print(loop.handle(text))


if __name__ == "__main__":
    sys.exit(main())
