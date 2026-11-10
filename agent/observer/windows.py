"""Thin wrappers over the Win32 window APIs: list windows, read the real exe behind a window,
check for the secure desktop, and bring a window to the front.

Kept thin on purpose: the decisions built on these facts live in agent/tools and are tested with
fakes. Exe paths come from the process (QueryFullProcessImageNameW), never from window titles.
"""

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DESKTOP_READOBJECTS = 0x0001
UOI_NAME = 2
SW_RESTORE = 9
MAX_PATH_CHARS = 32768
MAX_TEXT_CHARS = 512
DEFAULT_DESKTOP_NAME = "default"
# Desktop, taskbar and wallpaper windows belong to explorer.exe but are never app windows.
SHELL_WINDOW_CLASSES = frozenset({"progman", "workerw", "shell_traywnd", "shell_secondarytraywnd"})
FOREGROUND_WAIT_SECONDS = 2.0
POLL_SECONDS = 0.1

ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.EnumWindows.argtypes = (ENUM_PROC, wintypes.LPARAM)
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SwitchToThisWindow.argtypes = (wintypes.HWND, wintypes.BOOL)
user32.SwitchToThisWindow.restype = None
user32.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
user32.OpenInputDesktop.restype = wintypes.HANDLE
user32.GetUserObjectInformationW.argtypes = (
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
)
user32.CloseDesktop.argtypes = (wintypes.HANDLE,)
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
)
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    class_name: str
    exe_path: str

    @property
    def exe_name(self):
        return PureWindowsPath(self.exe_path).name.casefold()


def _last_error():
    return ctypes.WinError(ctypes.get_last_error())


def exe_path_of_window(hwnd):
    """Full exe path of the process that owns the window. Raises OSError if it can't be read."""
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if process_id.value == 0:
        raise OSError("window has no owning process")
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not handle:
        raise _last_error()
    try:
        size = wintypes.DWORD(MAX_PATH_CHARS)
        buffer = ctypes.create_unicode_buffer(MAX_PATH_CHARS)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise _last_error()
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def foreground_hwnd():
    return user32.GetForegroundWindow() or 0


def foreground_exe():
    """Exe path behind the foreground window. Raises OSError if there is none or it's unreadable."""
    hwnd = foreground_hwnd()
    if not hwnd:
        raise OSError("no foreground window")
    return exe_path_of_window(hwnd)


def is_secure_desktop():
    """True when input goes to a desktop other than the user's (UAC prompt, lock screen)."""
    desktop = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
    if not desktop:
        # A normal process can't open the secure desktop, so failing to open it means we're there.
        return True
    try:
        needed = wintypes.DWORD()
        buffer = ctypes.create_unicode_buffer(MAX_TEXT_CHARS)
        ok = user32.GetUserObjectInformationW(
            desktop, UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
        )
        if not ok:
            raise _last_error()
        return buffer.value.casefold() != DEFAULT_DESKTOP_NAME
    finally:
        user32.CloseDesktop(desktop)


def _window_text(hwnd):
    buffer = ctypes.create_unicode_buffer(MAX_TEXT_CHARS)
    user32.GetWindowTextW(hwnd, buffer, MAX_TEXT_CHARS)
    return buffer.value


def _class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(MAX_TEXT_CHARS)
    user32.GetClassNameW(hwnd, buffer, MAX_TEXT_CHARS)
    return buffer.value


def top_windows():
    """Visible, titled top-level app windows in z-order (front first)."""
    handles = []

    def on_window(hwnd, _unused):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            handles.append(hwnd)
        return True

    if not user32.EnumWindows(ENUM_PROC(on_window), 0):
        raise _last_error()

    windows = []
    for hwnd in handles:
        class_name = _class_name(hwnd)
        if class_name.casefold() in SHELL_WINDOW_CLASSES:
            continue
        try:
            exe_path = exe_path_of_window(hwnd)
        except OSError:
            # Its process exited or is protected. We can't verify which app it is, so it can
            # never count as a launch result or a switch target.
            continue
        windows.append(Window(hwnd, _window_text(hwnd), class_name, exe_path))
    return windows


def bring_to_front(hwnd):
    """Restore and focus the window. True only once Windows reports it as the foreground."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    if not user32.SetForegroundWindow(hwnd):
        # Windows refuses SetForegroundWindow from a process that isn't in front; this asks the
        # shell to switch instead, like clicking the taskbar button.
        user32.SwitchToThisWindow(hwnd, True)

    deadline = time.monotonic() + FOREGROUND_WAIT_SECONDS
    while time.monotonic() < deadline:
        if foreground_hwnd() == hwnd:
            return True
        time.sleep(POLL_SECONDS)
    return False
