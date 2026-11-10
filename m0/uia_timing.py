"""M0 spike: time a read-only UI Automation "observer snapshot" per app.

Read-only: never clicks, types, sends keys, invokes patterns or sets values.
Only windows opened by this script (found by top-level handle diff) are
closed, by handle, with WM_CLOSE.
"""

import ctypes
import json
import os
import statistics
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

import uiautomation as auto
from comtypes import COMError

MAX_DEPTH = 25
MAX_ELEMENTS = 3000
NAME_MAX_CHARS = 80
SAMPLE_SIZE = 5
WARM_RUNS = 10
P95_FRACTION = 0.95
MS_PER_SECOND = 1000.0

WINDOW_WAIT_SECONDS = 15.0
WINDOW_POLL_SECONDS = 0.25
WINDOW_SETTLE_SECONDS = 1.5
CLOSE_WAIT_SECONDS = 5.0
BETWEEN_APPS_SECONDS = 1.0

WM_CLOSE = 0x0010
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
RESULTS_PATH = Path(r"C:\Users\hamza\Desktop\Research-Assistant\m0\results\uia-timing.json")

ACTIONABLE_TYPES = {
    auto.ControlType.ButtonControl,
    auto.ControlType.EditControl,
    auto.ControlType.MenuItemControl,
    auto.ControlType.ListItemControl,
    auto.ControlType.TreeItemControl,
    auto.ControlType.TabItemControl,
    auto.ControlType.CheckBoxControl,
    auto.ControlType.RadioButtonControl,
    auto.ControlType.ComboBoxControl,
    auto.ControlType.HyperlinkControl,
    auto.ControlType.SplitButtonControl,
    auto.ControlType.DataItemControl,
}

user32 = ctypes.windll.user32
ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def visible_titled_handles():
    """Handles of visible top-level windows that have a non-empty title."""
    found = set()

    def on_window(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.add(int(hwnd))
        return True

    user32.EnumWindows(ENUM_PROC(on_window), 0)
    return found


def wait_for_new_window(before):
    """Return (handle, note). handle is None unless exactly one new window appeared."""
    deadline = time.monotonic() + WINDOW_WAIT_SECONDS
    appeared = False
    while time.monotonic() < deadline:
        if visible_titled_handles() - before:
            appeared = True
            break
        time.sleep(WINDOW_POLL_SECONDS)
    if not appeared:
        return None, "no new window appeared before timeout"
    time.sleep(WINDOW_SETTLE_SECONDS)
    new_handles = visible_titled_handles() - before
    if len(new_handles) != 1:
        return None, "ambiguous: %d new windows appeared" % len(new_handles)
    return new_handles.pop(), "ok"


def read_element(control):
    """Collect the kept-element fields, or None if the element is filtered out."""
    if control.IsOffscreen:
        return None
    if control.ControlType not in ACTIONABLE_TYPES:
        return None
    name = control.Name
    if not name:
        return None
    if control.IsPassword:
        return None
    rect = control.BoundingRectangle
    return {
        "type": control.ControlTypeName,
        "name": name[:NAME_MAX_CHARS],
        "automation_id": control.AutomationId,
        "class_name": control.ClassName,
        "rect": (rect.left, rect.top, rect.right, rect.bottom),
        "runtime_id": tuple(control.GetRuntimeId()),
    }


def child_controls(control, errors):
    """Direct children of a control; COM failures are counted, not hidden."""
    children = []
    try:
        child = control.GetFirstChildControl()
        while child is not None:
            children.append(child)
            child = child.GetNextSiblingControl()
    except COMError as error:
        errors.append("children: %s" % type(error).__name__)
    return children


def snapshot(window):
    """Walk the tree; return (kept, walked, truncated flags, errors)."""
    kept = []
    errors = []
    walked = 0
    truncated = {"depth": False, "elements": False}
    stack = [(window, 0)]
    while stack:
        if walked >= MAX_ELEMENTS:
            truncated["elements"] = True
            break
        control, depth = stack.pop()
        walked += 1
        try:
            element = read_element(control)
        except COMError as error:
            element = None
            errors.append("read: %s" % type(error).__name__)
        if element is not None:
            kept.append(element)
        children = child_controls(control, errors)
        if depth >= MAX_DEPTH:
            if children:
                truncated["depth"] = True
            continue
        for child in children:
            stack.append((child, depth + 1))
    return kept, walked, truncated, errors


def close_window(hwnd):
    """Post WM_CLOSE to a window we opened; return True if it went away."""
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    deadline = time.monotonic() + CLOSE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not user32.IsWindow(hwnd):
            return True
        time.sleep(WINDOW_POLL_SECONDS)
    return False


def timed_snapshot(window):
    start = time.perf_counter()
    result = snapshot(window)
    elapsed_ms = (time.perf_counter() - start) * MS_PER_SECOND
    return elapsed_ms, result


def p95(values):
    ordered = sorted(values)
    index = int(round(P95_FRACTION * (len(ordered) - 1)))
    return ordered[index]


def measure_app(label, launch):
    """Launch one app, find its new window, time 1 cold + WARM_RUNS warm snapshots."""
    entry = {"app": label, "window_closed": None}
    before = visible_titled_handles()
    try:
        launch()
    except OSError as error:
        entry["error"] = "launch failed: %s" % error
        return entry
    hwnd, note = wait_for_new_window(before)
    entry["window_note"] = note
    if hwnd is None:
        entry["window_closed"] = "left open (not identified with certainty)"
        return entry
    try:
        window = auto.ControlFromHandle(hwnd)
        cold_ms, (kept, walked, truncated, errors) = timed_snapshot(window)
        warm_ms = []
        for _ in range(WARM_RUNS):
            elapsed, _result = timed_snapshot(window)
            warm_ms.append(elapsed)
    except COMError as error:
        entry["error"] = "measure failed: %s" % error
    else:
        entry.update({
            "cold_ms": round(cold_ms, 1),
            "warm_median_ms": round(statistics.median(warm_ms), 1),
            "warm_p95_ms": round(p95(warm_ms), 1),
            "walked": walked,
            "kept": len(kept),
            "truncated_depth": truncated["depth"],
            "truncated_elements": truncated["elements"],
            "com_error_count": len(errors),
            "com_error_kinds": sorted(set(errors)),
            "sample": [
                {"type": item["type"], "automation_id": item["automation_id"]}
                for item in kept[:SAMPLE_SIZE]
            ],
        })
    finally:
        entry["window_closed"] = close_window(hwnd)
    return entry


def launch_notepad():
    subprocess.Popen(["notepad.exe"])


def launch_explorer():
    subprocess.Popen(["explorer.exe", str(Path.home() / "Documents")])


def launch_settings():
    os.startfile("ms-settings:")


def launch_chrome_blank():
    subprocess.Popen([str(CHROME_PATH), "--new-window", "about:blank"])


def format_table(results):
    lines = [
        "| App | Cold ms | Warm median ms | Warm p95 ms | Walked | Kept | Truncated (depth/elements) |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in results:
        if "cold_ms" not in entry:
            reason = entry.get("error") or entry.get("window_note") or entry.get("note")
            lines.append("| %s | - | - | - | - | - | %s |" % (entry["app"], reason))
            continue
        lines.append("| %s | %s | %s | %s | %s | %s | %s/%s |" % (
            entry["app"], entry["cold_ms"], entry["warm_median_ms"],
            entry["warm_p95_ms"], entry["walked"], entry["kept"],
            entry["truncated_depth"], entry["truncated_elements"]))
    return "\n".join(lines)


def main():
    results = []
    cases = [
        ("Notepad", launch_notepad),
        ("File Explorer (Documents)", launch_explorer),
        ("Settings", launch_settings),
    ]
    chrome_installed = CHROME_PATH.exists()
    if chrome_installed:
        cases.append(("Chrome (about:blank)", launch_chrome_blank))
    for label, launch in cases:
        results.append(measure_app(label, launch))
        time.sleep(BETWEEN_APPS_SECONDS)
    if not chrome_installed:
        results.append({"app": "Chrome", "note": "not installed"})
    results.append({
        "app": "Chrome (example.com)",
        "note": "skipped: same-window navigation would need typing/clicking",
    })
    output = {
        "max_depth": MAX_DEPTH,
        "max_elements": MAX_ELEMENTS,
        "warm_runs": WARM_RUNS,
        "results": results,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(format_table(results))
    for entry in results:
        print(entry["app"], "| window:", entry.get("window_note"),
              "| closed:", entry.get("window_closed"),
              "| com errors:", entry.get("com_error_count"), entry.get("com_error_kinds"))


if __name__ == "__main__":
    main()
