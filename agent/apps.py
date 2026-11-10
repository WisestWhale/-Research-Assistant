"""The trusted app table: which apps the agent may launch or switch to, and how.

The table is user-edited config, never model output. It is validated when loaded so a bad entry
fails loudly at startup instead of half-working later.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from agent.gate.policy import TERMINAL_EXES

DEFAULT_LAUNCH_TIMEOUT_SECONDS = 15
MAX_LAUNCH_TIMEOUT_SECONDS = 300
APP_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DRIVE_PATH = re.compile(r"^[A-Za-z]:\\")
REQUIRED_FIELDS = ("id", "names", "exe", "window_exe")
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS + ("args", "launch_timeout_seconds"))


class AppTableError(ValueError):
    """The app table file is missing, unreadable or has an invalid entry."""


@dataclass(frozen=True)
class AppEntry:
    app_id: str
    names: tuple[str, ...]
    exe: str
    window_exe: str
    args: tuple[str, ...] = ()
    launch_timeout_seconds: int = DEFAULT_LAUNCH_TIMEOUT_SECONDS


class AppTable:
    def __init__(self, entries):
        self.entries = {}
        self._by_name = {}
        for entry in entries:
            if entry.app_id in self.entries:
                raise AppTableError(f"duplicate app id '{entry.app_id}'")
            self.entries[entry.app_id] = entry
            for name in (entry.app_id,) + entry.names:
                key = normalize_name(name)
                owner = self._by_name.get(key)
                if owner is not None and owner != entry.app_id:
                    raise AppTableError(f"name '{name}' is used by '{owner}' and '{entry.app_id}'")
                self._by_name[key] = entry.app_id

    def resolve(self, name):
        """App id for a typed or spoken app name, or None."""
        return self._by_name.get(normalize_name(name))

    def exe_table(self):
        """App id -> exe path, the shape the gate's Context expects."""
        table = {}
        for app_id, entry in self.entries.items():
            table[app_id] = entry.exe
        return table


def normalize_name(name):
    return " ".join(name.split()).casefold()


def _require_text(raw, field, app_label):
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AppTableError(f"{app_label}: '{field}' must be a non-empty string")
    return value.strip()


def _parse_names(raw, app_label):
    names = raw.get("names")
    if not isinstance(names, list) or not names:
        raise AppTableError(f"{app_label}: 'names' must be a non-empty list")
    parsed = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise AppTableError(f"{app_label}: every name must be a non-empty string")
        parsed.append(name.strip())
    return tuple(parsed)


def _parse_args(raw, app_label):
    args = raw.get("args", [])
    if not isinstance(args, list):
        raise AppTableError(f"{app_label}: 'args' must be a list of strings")
    for arg in args:
        if not isinstance(arg, str):
            raise AppTableError(f"{app_label}: 'args' must be a list of strings")
    return tuple(args)


def _parse_timeout(raw, app_label):
    timeout = raw.get("launch_timeout_seconds", DEFAULT_LAUNCH_TIMEOUT_SECONDS)
    # bool is a subclass of int, so reject it explicitly.
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise AppTableError(f"{app_label}: 'launch_timeout_seconds' must be a whole number")
    if timeout < 1 or timeout > MAX_LAUNCH_TIMEOUT_SECONDS:
        raise AppTableError(
            f"{app_label}: 'launch_timeout_seconds' must be 1-{MAX_LAUNCH_TIMEOUT_SECONDS}"
        )
    return timeout


def parse_entry(raw, exists=os.path.isfile, expand_vars=os.path.expandvars):
    """Validate one raw JSON object and return an AppEntry."""
    if not isinstance(raw, dict):
        raise AppTableError("every app entry must be an object")
    app_label = f"app '{raw.get('id', '?')}'"
    unknown = sorted(set(raw) - KNOWN_FIELDS)
    if unknown:
        raise AppTableError(f"{app_label}: unknown fields {unknown}")

    app_id = _require_text(raw, "id", app_label)
    if not APP_ID.match(app_id):
        raise AppTableError(f"{app_label}: id must be lowercase letters, digits and '-'")

    # Trusted config may say %LOCALAPPDATA% so the file holds no user name; model paths never
    # get this expansion (the gate blocks '%').
    exe = expand_vars(_require_text(raw, "exe", app_label))
    if "%" in exe:
        raise AppTableError(f"{app_label}: unknown environment variable in 'exe'")
    if not DRIVE_PATH.match(exe) or ":" in exe[2:]:
        raise AppTableError(f"{app_label}: 'exe' must be a full path like C:\\...\\app.exe")
    if PureWindowsPath(exe).suffix.casefold() != ".exe":
        raise AppTableError(f"{app_label}: 'exe' must point at an .exe file")
    if PureWindowsPath(exe).name.casefold() in TERMINAL_EXES:
        raise AppTableError(f"{app_label}: terminals are not allowed in the app table")
    if not exists(exe):
        raise AppTableError(f"{app_label}: exe not found at {exe}")

    window_exe = _require_text(raw, "window_exe", app_label).casefold()
    if "\\" in window_exe or "/" in window_exe or not window_exe.endswith(".exe"):
        raise AppTableError(f"{app_label}: 'window_exe' must be a bare name like app.exe")
    if window_exe in TERMINAL_EXES:
        raise AppTableError(f"{app_label}: terminals are not allowed in the app table")

    return AppEntry(
        app_id=app_id,
        names=_parse_names(raw, app_label),
        exe=exe,
        window_exe=window_exe,
        args=_parse_args(raw, app_label),
        launch_timeout_seconds=_parse_timeout(raw, app_label),
    )


def load_app_table(path, exists=os.path.isfile, expand_vars=os.path.expandvars):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise AppTableError(f"cannot read app table {path}: {error}") from error
    try:
        raw_entries = json.loads(text)
    except json.JSONDecodeError as error:
        raise AppTableError(f"app table {path} is not valid JSON: {error}") from error
    if not isinstance(raw_entries, list):
        raise AppTableError("the app table must be a JSON list of app entries")

    entries = []
    for raw in raw_entries:
        entries.append(parse_entry(raw, exists, expand_vars))
    return AppTable(entries)
