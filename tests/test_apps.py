import copy
import json
import tempfile
import unittest
from pathlib import Path

from agent.apps import AppTableError, load_app_table, parse_entry

NOTEPAD = r"C:\Windows\System32\notepad.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPO_APP_TABLE = Path(__file__).resolve().parents[1] / "profiles" / "apps.json"


def always_exists(path):
    return True


def never_exists(path):
    return False


def no_expansion(path):
    return path


def entry(**overrides):
    raw = {"id": "notepad", "names": ["notepad"], "exe": NOTEPAD, "window_exe": "notepad.exe"}
    raw.update(overrides)
    return raw


def load(entries, exists=always_exists, expand=no_expansion):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "apps.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return load_app_table(path, exists, expand)


class TestValidEntries(unittest.TestCase):
    def test_minimal_entry_loads_with_defaults(self):
        table = load([entry()])
        loaded = table.entries["notepad"]
        self.assertEqual(loaded.exe, NOTEPAD)
        self.assertEqual(loaded.args, ())
        self.assertEqual(loaded.launch_timeout_seconds, 15)

    def test_resolve_by_id_alias_case_and_spacing(self):
        table = load([entry(id="chrome", names=["Google Chrome"], exe=CHROME,
                            window_exe="chrome.exe")])
        cases = ["chrome", "CHROME", "google chrome", "  Google   Chrome "]
        for name in cases:
            with self.subTest(name=name):
                self.assertEqual(table.resolve(name), "chrome")

    def test_unknown_name_resolves_to_none(self):
        table = load([entry()])
        for name in ["cmd", "", "notepad.exe", "C:\\Windows\\System32\\notepad.exe"]:
            with self.subTest(name=name):
                self.assertIsNone(table.resolve(name))

    def test_exe_table_maps_ids_to_paths(self):
        table = load([entry(), entry(id="chrome", names=["chrome"], exe=CHROME,
                                     window_exe="chrome.exe")])
        self.assertEqual(table.exe_table(), {"notepad": NOTEPAD, "chrome": CHROME})

    def test_window_exe_is_casefolded(self):
        table = load([entry(window_exe="Notepad.EXE")])
        self.assertEqual(table.entries["notepad"].window_exe, "notepad.exe")

    def test_environment_variables_expand_in_exe(self):
        def expand(path):
            return path.replace("%LOCALAPPDATA%", r"C:\Users\me\AppData\Local")

        table = load([entry(exe=r"%LOCALAPPDATA%\Programs\notepad.exe")], expand=expand)
        expected = r"C:\Users\me\AppData\Local\Programs\notepad.exe"
        self.assertEqual(table.entries["notepad"].exe, expected)

    def test_timeout_boundaries(self):
        for timeout in (1, 300):
            with self.subTest(timeout=timeout):
                table = load([entry(launch_timeout_seconds=timeout)])
                self.assertEqual(table.entries["notepad"].launch_timeout_seconds, timeout)

    def test_parse_does_not_modify_the_raw_entry(self):
        raw = entry(args=["--new-window"])
        before = copy.deepcopy(raw)
        parse_entry(raw, always_exists, no_expansion)
        self.assertEqual(raw, before)

    def test_repo_app_table_is_valid_shape(self):
        # Checks the committed file's structure; exe existence is machine-specific.
        table = load_app_table(REPO_APP_TABLE, always_exists)
        for app_id in ("notepad", "explorer", "chrome", "edge", "vscode", "premiere"):
            with self.subTest(app_id=app_id):
                self.assertIn(app_id, table.entries)


class TestInvalidEntries(unittest.TestCase):
    CASES = [
        ("missing id", {"names": ["x"], "exe": NOTEPAD, "window_exe": "x.exe"}),
        ("upper-case id", entry(id="Notepad")),
        ("id with space", entry(id="note pad")),
        ("empty names", entry(names=[])),
        ("names not a list", entry(names="notepad")),
        ("blank name", entry(names=["  "])),
        ("relative exe", entry(exe=r"notepad.exe")),
        ("UNC exe", entry(exe=r"\\server\share\notepad.exe")),
        ("URI exe", entry(exe="ms-settings:")),
        ("ADS in exe", entry(exe=r"C:\Windows\notepad.exe:evil")),
        ("not an exe", entry(exe=r"C:\Windows\System32\notes.txt")),
        ("shortcut", entry(exe=r"C:\Users\me\Desktop\Notepad.lnk")),
        ("cmd is a terminal", entry(exe=r"C:\Windows\System32\cmd.exe")),
        ("powershell is a terminal",
         entry(exe=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")),
        ("terminal window_exe", entry(window_exe="WindowsTerminal.exe")),
        ("window_exe with a path", entry(window_exe=r"C:\Windows\notepad.exe")),
        ("window_exe not .exe", entry(window_exe="notepad")),
        ("args not a list", entry(args="--flag")),
        ("args with a number", entry(args=[1])),
        ("timeout zero", entry(launch_timeout_seconds=0)),
        ("timeout too big", entry(launch_timeout_seconds=301)),
        ("timeout as text", entry(launch_timeout_seconds="15")),
        ("timeout as bool", entry(launch_timeout_seconds=True)),
        ("unknown field", entry(shell=True)),
        ("entry not an object", "notepad"),
    ]

    def test_each_invalid_entry_is_refused(self):
        for description, raw in self.CASES:
            with self.subTest(description):
                with self.assertRaises(AppTableError):
                    load([raw])

    def test_missing_exe_on_disk_is_refused(self):
        with self.assertRaises(AppTableError) as caught:
            load([entry()], exists=never_exists)
        self.assertIn("not found", str(caught.exception))

    def test_unexpanded_variable_is_refused(self):
        with self.assertRaises(AppTableError):
            load([entry(exe=r"%NOT_A_REAL_VAR%\notepad.exe")])

    def test_duplicate_id_is_refused(self):
        with self.assertRaises(AppTableError):
            load([entry(), entry(names=["other"])])

    def test_name_shared_by_two_apps_is_refused(self):
        second = entry(id="chrome", names=["notepad"], exe=CHROME, window_exe="chrome.exe")
        with self.assertRaises(AppTableError):
            load([entry(), second])

    def test_alias_equal_to_another_id_is_refused(self):
        second = entry(id="chrome", names=["Notepad"], exe=CHROME, window_exe="chrome.exe")
        with self.assertRaises(AppTableError):
            load([entry(names=["text"]), second])


class TestFileProblems(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(AppTableError):
            load_app_table(Path("C:/definitely/not/here/apps.json"))

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "apps.json"
            path.write_text("[{", encoding="utf-8")
            with self.assertRaises(AppTableError):
                load_app_table(path, always_exists)

    def test_top_level_must_be_a_list(self):
        with self.assertRaises(AppTableError):
            load({"id": "notepad"})


if __name__ == "__main__":
    unittest.main()
