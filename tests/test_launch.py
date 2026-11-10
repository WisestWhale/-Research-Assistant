import unittest

from agent.apps import AppEntry, AppTable
from agent.observer.windows import Window
from agent.tools.launch import DesktopTools
from agent.types import Action

NOTEPAD = AppEntry("notepad", ("notepad",), r"C:\Windows\System32\notepad.exe", "notepad.exe",
                   launch_timeout_seconds=5)
VSCODE = AppEntry("vscode", ("code",), r"C:\Apps\Code.exe", "code.exe", args=("--new",),
                  launch_timeout_seconds=5)
PACKAGED_NOTEPAD = r"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad\Notepad\Notepad.exe"


class FakeDesktop:
    """Windows, foreground and a clock that only moves when the tool sleeps."""

    def __init__(self, windows=(), foreground=0):
        self.windows = list(windows)
        self.foreground = foreground
        self.time = 0.0
        self.started = []
        self.on_start = None
        self.front_requests = []
        self.front_succeeds = True

    def list_windows(self):
        return list(self.windows)

    def foreground_hwnd(self):
        return self.foreground

    def bring_to_front(self, hwnd):
        self.front_requests.append(hwnd)
        if self.front_succeeds:
            self.foreground = hwnd
        return self.front_succeeds

    def start(self, argv):
        self.started.append(list(argv))
        if self.on_start is not None:
            self.on_start()

    def clock(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds


def tools_for(desktop):
    apps = AppTable([NOTEPAD, VSCODE])
    return DesktopTools(apps, desktop.list_windows, desktop.foreground_hwnd,
                        desktop.bring_to_front, desktop.start, desktop.clock, desktop.sleep)


def window(hwnd, exe):
    return Window(hwnd, f"window {hwnd}", "SomeClass", exe)


def launch(app):
    return Action("launch_app", args={"app": app})


def switch(app):
    return Action("switch_window", args={"app": app})


class TestLaunch(unittest.TestCase):
    def test_new_window_means_success(self):
        desktop = FakeDesktop([window(1, r"C:\Other\other.exe")])
        desktop.on_start = lambda: desktop.windows.append(window(2, NOTEPAD.exe))
        result = tools_for(desktop).run(launch("notepad"))
        self.assertTrue(result.ok)
        self.assertEqual(result.message, "Opened notepad.")

    def test_starts_exe_and_args_as_a_list(self):
        desktop = FakeDesktop()
        desktop.on_start = lambda: desktop.windows.append(window(2, VSCODE.exe))
        tools_for(desktop).run(launch("vscode"))
        self.assertEqual(desktop.started, [[VSCODE.exe, "--new"]])

    def test_window_from_a_different_process_path_still_counts(self):
        # Windows 11: notepad.exe hands off to the packaged Notepad.exe.
        desktop = FakeDesktop()
        desktop.on_start = lambda: desktop.windows.append(window(2, PACKAGED_NOTEPAD))
        self.assertTrue(tools_for(desktop).run(launch("notepad")).ok)

    def test_existing_window_of_the_app_is_not_a_new_window(self):
        desktop = FakeDesktop([window(1, NOTEPAD.exe)], foreground=1)
        result = tools_for(desktop).run(launch("notepad"))
        self.assertFalse(result.ok)
        self.assertIn("no window of it appeared within 5 s", result.message)

    def test_single_instance_app_coming_to_front_counts(self):
        desktop = FakeDesktop([window(1, VSCODE.exe), window(9, r"C:\Other\other.exe")],
                              foreground=9)

        def focus_existing():
            desktop.foreground = 1

        desktop.on_start = focus_existing
        self.assertTrue(tools_for(desktop).run(launch("vscode")).ok)

    def test_new_window_of_another_app_does_not_count(self):
        desktop = FakeDesktop()
        desktop.on_start = lambda: desktop.windows.append(window(2, r"C:\Other\other.exe"))
        self.assertFalse(tools_for(desktop).run(launch("notepad")).ok)

    def test_window_appearing_late_but_inside_the_timeout_counts(self):
        desktop = FakeDesktop()
        real_sleep = desktop.sleep

        def slow_sleep(seconds):
            real_sleep(seconds)
            if desktop.time >= 4.0 and not desktop.windows:
                desktop.windows.append(window(2, NOTEPAD.exe))

        desktop.sleep = slow_sleep
        self.assertTrue(tools_for(desktop).run(launch("notepad")).ok)

    def test_timeout_stops_waiting(self):
        desktop = FakeDesktop()
        result = tools_for(desktop).run(launch("notepad"))
        self.assertFalse(result.ok)
        self.assertGreaterEqual(desktop.time, NOTEPAD.launch_timeout_seconds)
        self.assertLess(desktop.time, NOTEPAD.launch_timeout_seconds + 1)

    def test_start_failure_is_reported_not_raised(self):
        desktop = FakeDesktop()

        def fail(argv):
            raise FileNotFoundError("missing exe")

        desktop.start = fail
        result = tools_for(desktop).run(launch("notepad"))
        self.assertFalse(result.ok)
        self.assertIn("Could not start notepad", result.message)


class TestSwitch(unittest.TestCase):
    def test_switches_to_the_frontmost_window_of_the_app(self):
        desktop = FakeDesktop([window(5, r"C:\Other\other.exe"), window(6, NOTEPAD.exe),
                               window(7, NOTEPAD.exe)], foreground=5)
        result = tools_for(desktop).run(switch("notepad"))
        self.assertTrue(result.ok)
        self.assertEqual(desktop.front_requests, [6])

    def test_app_not_open_is_reported_and_nothing_is_launched(self):
        desktop = FakeDesktop([window(5, r"C:\Other\other.exe")])
        result = tools_for(desktop).run(switch("notepad"))
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "notepad isn't open.")
        self.assertEqual(desktop.started, [])

    def test_refused_foreground_change_is_reported(self):
        desktop = FakeDesktop([window(6, NOTEPAD.exe)])
        desktop.front_succeeds = False
        result = tools_for(desktop).run(switch("notepad"))
        self.assertFalse(result.ok)
        self.assertIn("didn't let me", result.message)

    def test_matching_is_by_exe_name_not_title(self):
        impostor = Window(5, "Notepad", "Notepad", r"C:\Windows\System32\cmd.exe")
        desktop = FakeDesktop([impostor])
        self.assertFalse(tools_for(desktop).run(switch("notepad")).ok)


class TestBadInput(unittest.TestCase):
    def test_unknown_app_id_is_a_bug(self):
        with self.assertRaises(ValueError):
            tools_for(FakeDesktop()).run(launch("cmd"))

    def test_unsupported_kind_is_a_bug(self):
        with self.assertRaises(ValueError):
            tools_for(FakeDesktop()).run(Action("read_file", args={"app": "notepad"}))


if __name__ == "__main__":
    unittest.main()
