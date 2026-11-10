"""Fixed lists the gate rules use. All entries are casefolded so lookups are case-insensitive."""

GUI_KINDS = frozenset({"invoke", "set_text", "key"})
TOOL_KINDS = frozenset({
    "launch_app", "switch_window", "open_file", "read_file", "find_files",
    "search_index", "analyze_video", "sum_column", "count_rows",
})
CONTROL_KINDS = frozenset({"wait", "done", "fail"})
ALL_KINDS = GUI_KINDS | TOOL_KINDS | CONTROL_KINDS
RISK_LEVELS = frozenset({"low", "medium", "high"})

REQUIRED_ARGS = {
    "set_text": ("text",),
    "key": ("keys",),
    "launch_app": ("app",),
    "switch_window": ("app",),
    "open_file": ("path",),
    "read_file": ("path",),
    "analyze_video": ("path",),
    "count_rows": ("path",),
    "sum_column": ("path", "column"),
    "search_index": ("query",),
    "find_files": ("query",),
}

# Kinds that always carry a path. find_files is a path kind only when it has one.
PATH_KINDS = frozenset({"open_file", "read_file", "analyze_video", "sum_column", "count_rows"})
SIZE_CAPPED_KINDS = frozenset({"read_file", "sum_column", "count_rows"})

SECURE_DESKTOP_EXES = frozenset({"consent.exe", "logonui.exe"})
TERMINAL_EXES = frozenset({
    "windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "conhost.exe", "openconsole.exe", "mintty.exe",
})
IDE_EXES = frozenset({"code.exe", "idea64.exe", "pycharm64.exe", "devenv.exe"})
BROWSER_EXES = frozenset({"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"})
EXPLORER_EXE = "explorer.exe"
DIALOG_WINDOW_CLASS = "#32770"
RUN_DIALOG_TITLE = "run"
TERMINAL_MARKER = "terminal"

MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
KEY_ALIASES = {
    "control": "ctrl",
    "escape": "esc",
    "return": "enter",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "windows": "win",
    "meta": "win",
}
ALLOWED_KEYS = frozenset({
    "enter", "tab", "esc", "up", "down", "left", "right", "home", "end",
    "pgup", "pgdn", "backspace", "ctrl+c", "ctrl+f", "ctrl+z", "ctrl+s",
})
SAVE_KEYS = "ctrl+s"

ADDRESS_NAME_PREFIX = "address"
SEARCH_MARKER = "search"
ADDRESS_MARKER = "address"

DATA_EXTENSIONS = frozenset({
    ".txt", ".md", ".csv", ".json", ".pdf", ".docx", ".xlsx",
    ".png", ".jpg", ".jpeg", ".mp4", ".mkv",
})
EXECUTABLE_EXTENSIONS = frozenset({
    ".exe", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".js", ".jse", ".wsf", ".wsh",
    ".hta", ".lnk", ".url", ".scr", ".msi", ".msc", ".cpl", ".jar", ".reg", ".pif",
})
DEVICE_NAMES = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{number}" for number in range(1, 10)]
    + [f"lpt{number}" for number in range(1, 10)]
)

PERMANENT_DELETE_MARKERS = ("empty recycle bin", "permanently delete")
DESTRUCTIVE_NAMES = ("delete", "rename", "move to", "cut", "replace", "yes")

BROWSER_CONTENT_TYPE = "Document"
EXPLORER_LIST_TYPE = "List"
EXPLORER_ITEM_TYPES = frozenset({"ListItem", "DataItem"})
