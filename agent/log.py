"""Append-only action log: one JSON object per line, never rewritten.

Lives under %LOCALAPPDATA%\\desktop-agent so it stays on this machine and is easy to delete.
Typed text (set_text) will need redaction once GUI actions exist; the fast lane logs only
commands and app ids.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_FOLDER_NAME = "desktop-agent"
LOG_FILE_NAME = "actions.jsonl"


def default_log_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise OSError("LOCALAPPDATA is not set, so there is nowhere local to keep the log")
    return Path(local_app_data) / LOG_FOLDER_NAME / LOG_FILE_NAME


class ActionLog:
    def __init__(self, path, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def append(self, record):
        """Write one record as a line. Opens in append mode every time, so earlier lines are
        never touched and a crash loses at most the line being written."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = dict(record)
        line["time"] = self.now().isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
