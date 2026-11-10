"""launch_app and switch_window: the fast lane's two tool actions.

Both only ever act on entries from the trusted app table, and both verify the result
deterministically (a window of that app appeared or came to the front) instead of trusting
that the call worked. Windows facts come in as functions so tests can use fakes.
"""

import subprocess
import time
from dataclasses import dataclass

from agent.observer import windows as win32

POLL_SECONDS = 0.25
# A detached process with its own group, so Ctrl+C in the agent's terminal never reaches it.
DETACHED_FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    message: str


def start_process(argv):
    """Start an exe with fixed arguments. No shell, so nothing in argv is interpreted."""
    subprocess.Popen(
        argv,
        shell=False,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
    )


class DesktopTools:
    def __init__(
        self,
        apps,
        list_windows=win32.top_windows,
        foreground_hwnd=win32.foreground_hwnd,
        bring_to_front=win32.bring_to_front,
        start=start_process,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        self.apps = apps
        self.list_windows = list_windows
        self.foreground_hwnd = foreground_hwnd
        self.bring_to_front = bring_to_front
        self.start = start
        self.clock = clock
        self.sleep = sleep

    def run(self, action):
        entry = self.apps.entries.get(action.args.get("app"))
        if entry is None:
            # The gate only allows ids from the table, so reaching this is a bug, not user error.
            raise ValueError(f"app '{action.args.get('app')}' is not in the app table")
        if action.kind == "launch_app":
            return self.launch(entry)
        if action.kind == "switch_window":
            return self.switch(entry)
        raise ValueError(f"the fast lane cannot run '{action.kind}'")

    def launch(self, entry):
        before = set()
        for window in self.list_windows():
            before.add(window.hwnd)
        foreground_before = self.foreground_hwnd()

        try:
            self.start([entry.exe, *entry.args])
        except OSError as error:
            return ToolResult(False, f"Could not start {entry.app_id}: {error}")

        deadline = self.clock() + entry.launch_timeout_seconds
        while True:
            if self._app_window_appeared(entry, before, foreground_before):
                return ToolResult(True, f"Opened {entry.app_id}.")
            if self.clock() >= deadline:
                return ToolResult(
                    False,
                    f"Started {entry.app_id}, but no window of it appeared within "
                    f"{entry.launch_timeout_seconds} s.",
                )
            self.sleep(POLL_SECONDS)

    def _app_window_appeared(self, entry, before, foreground_before):
        """A new window of the app, or (single-instance apps like VS Code) an existing window
        of the app that has just come to the front."""
        foreground_now = self.foreground_hwnd()
        for window in self.list_windows():
            if window.exe_name != entry.window_exe:
                continue
            if window.hwnd not in before:
                return True
            if window.hwnd == foreground_now and foreground_now != foreground_before:
                return True
        return False

    def switch(self, entry):
        target = None
        for window in self.list_windows():
            if window.exe_name == entry.window_exe:
                target = window
                break
        if target is None:
            return ToolResult(False, f"{entry.app_id} isn't open.")
        if self.bring_to_front(target.hwnd):
            return ToolResult(True, f"Switched to {entry.app_id}.")
        return ToolResult(False, f"Windows didn't let me bring {entry.app_id} to the front.")
