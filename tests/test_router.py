import copy
import unittest

from agent.router import FAST, MAX_COMMAND_CHARS, SLOW, Route, route
from agent.types import Action

KNOWN_APPS = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "notepad": "notepad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "premiere": "premiere",
    "premiere pro": "premiere",
    "vs code": "vscode",
}

TOO_LONG = "That command is too long."


class FakeApps:
    """Stand-in for the app table. Records every name it was asked to resolve."""

    def __init__(self, names=None):
        self.names = dict(KNOWN_APPS if names is None else names)
        self.calls = []

    def resolve(self, name):
        self.calls.append(name)
        return self.names.get(name)


def launch(app_id):
    return Action(kind="launch_app", args={"app": app_id}, risk_flag="low", thought="fast lane")


def switch(app_id):
    return Action(kind="switch_window", args={"app": app_id}, risk_flag="low", thought="fast lane")


def slow(reply=""):
    return Route(SLOW, None, reply=reply)


def unknown(name):
    return slow("I don't know an app called '" + name + "'.")


# (input text, expected action)
FAST_CASES = [
    # every launch verb
    ("open chrome", launch("chrome")),
    ("launch chrome", launch("chrome")),
    ("start chrome", launch("chrome")),
    # every switch verb
    ("switch to chrome", switch("chrome")),
    ("go to chrome", switch("chrome")),
    ("show chrome", switch("chrome")),
    ("bring up chrome", switch("chrome")),
    # aliases and multi-word names
    ("open google chrome", launch("chrome")),
    ("open file explorer", launch("explorer")),
    ("switch to premiere pro", switch("premiere")),
    ("open vs code", launch("vscode")),
    ("launch notepad", launch("notepad")),
    # casing
    ("Open Chrome", launch("chrome")),
    ("OPEN CHROME", launch("chrome")),
    ("Switch To Premiere", switch("premiere")),
    ("BRING UP notepad", switch("notepad")),
    # whitespace
    ("  open chrome  ", launch("chrome")),
    ("open    chrome", launch("chrome")),
    ("open\tchrome\n", launch("chrome")),
    ("switch   to   premiere   pro", switch("premiere")),
    ("bring    up notepad", switch("notepad")),
    # trailing punctuation
    ("open chrome.", launch("chrome")),
    ("open chrome!", launch("chrome")),
    ("open chrome?", launch("chrome")),
    ("open chrome...", launch("chrome")),
    ("open chrome?!", launch("chrome")),
    ("open chrome !", launch("chrome")),
    # politeness prefixes
    ("please open chrome", launch("chrome")),
    ("can you open chrome", launch("chrome")),
    ("could you open chrome", launch("chrome")),
    ("would you open chrome", launch("chrome")),
    ("hey open chrome", launch("chrome")),
    ("hey, open chrome", launch("chrome")),
    ("can you please open chrome", launch("chrome")),
    ("Could you please switch to premiere", switch("premiere")),
    ("hey can you open notepad", launch("notepad")),
    ("can you open chrome?", launch("chrome")),
    # trailing please
    ("open chrome please", launch("chrome")),
    ("open chrome, please", launch("chrome")),
    ("open chrome please.", launch("chrome")),
    ("open chrome, please!", launch("chrome")),
    ("Switch to notepad PLEASE", switch("notepad")),
    ("please open chrome please", launch("chrome")),
    # "the", "app" and "window"
    ("open the chrome", launch("chrome")),
    ("open chrome app", launch("chrome")),
    ("open the chrome app", launch("chrome")),
    ("switch to the notepad window", switch("notepad")),
    ("show the premiere pro window", switch("premiere")),
    ("open The Chrome App", launch("chrome")),
    ("go to explorer window", switch("explorer")),
]

# (input text, expected reply)
UNKNOWN_APP_CASES = [
    ("open cmd", "I don't know an app called 'cmd'."),
    ("launch powershell", "I don't know an app called 'powershell'."),
    ("Open CMD", "I don't know an app called 'CMD'."),
    ("open the Terminal app", "I don't know an app called 'Terminal'."),
    ("switch to spotify", "I don't know an app called 'spotify'."),
    ("open C:\\file.txt", "I don't know an app called 'C:\\file.txt'."),
    ("open chrome and notepad", "I don't know an app called 'chrome and notepad'."),
    ("please open   Foo   Bar!", "I don't know an app called 'Foo Bar'."),
    ("open the app window", "I don't know an app called 'app'."),
]

# Verb matched but no app name.
EMPTY_APP_INPUTS = [
    "open",
    "switch to",
    "Open.",
    "please launch",
    "go to ",
    "bring up",
]

# Not commands at all: handed to the slow lane with an empty reply.
NON_COMMANDS = [
    "run chrome",
    "delete everything",
    "what time is it",
    "rename the newest file in Downloads",
    "chrome",
    "please",
    "hey",
    "can you",
    "opener chrome",
    "reopen chrome",
    "openchrome",
    "starting chrome",
    "showing chrome",
    "launcher chrome",
    "go tomorrow",
    "switch too chrome",
    "bring upchrome",
    "open-chrome",
    "we should open chrome",
]


class RouteTest(unittest.TestCase):
    def test_fast_lane_commands(self):
        for text, expected_action in FAST_CASES:
            with self.subTest(text=text):
                result = route(text, FakeApps())
                self.assertEqual(result.lane, FAST)
                self.assertEqual(result.action, expected_action)
                self.assertEqual(result.reply, "")

    def test_unknown_app_reply(self):
        for text, expected_reply in UNKNOWN_APP_CASES:
            with self.subTest(text=text):
                result = route(text, FakeApps())
                self.assertEqual(result, slow(expected_reply))

    def test_empty_app_name_asks_which_app(self):
        for text in EMPTY_APP_INPUTS:
            with self.subTest(text=text):
                apps = FakeApps()
                result = route(text, apps)
                self.assertEqual(result, slow("Which app?"))
                self.assertEqual(apps.calls, [])

    def test_non_commands_go_to_slow_lane(self):
        for text in NON_COMMANDS:
            with self.subTest(text=text):
                result = route(text, FakeApps())
                self.assertEqual(result, slow())

    def test_empty_and_whitespace_input(self):
        for text in ["", " ", "   ", "\t\n", "...", "?!", " . "]:
            with self.subTest(text=text):
                apps = FakeApps()
                result = route(text, apps)
                self.assertEqual(result, slow())
                self.assertEqual(apps.calls, [])

    def test_length_limit_allows_exactly_max(self):
        padding = " " * (MAX_COMMAND_CHARS - len("open chrome"))
        text = "open chrome" + padding
        self.assertEqual(len(text), MAX_COMMAND_CHARS)
        result = route(text, FakeApps())
        self.assertEqual(result.lane, FAST)
        self.assertEqual(result.action, launch("chrome"))

    def test_length_limit_rejects_one_over_without_resolving(self):
        padding = " " * (MAX_COMMAND_CHARS + 1 - len("open chrome"))
        text = "open chrome" + padding
        self.assertEqual(len(text), MAX_COMMAND_CHARS + 1)
        apps = FakeApps()
        result = route(text, apps)
        self.assertEqual(result, slow(TOO_LONG))
        self.assertEqual(apps.calls, [])

    def test_very_long_input_rejected_without_resolving(self):
        apps = FakeApps()
        result = route("open " + "x" * 5000, apps)
        self.assertEqual(result, slow(TOO_LONG))
        self.assertEqual(apps.calls, [])

    def test_max_constant_value(self):
        self.assertEqual(MAX_COMMAND_CHARS, 300)

    def test_resolve_receives_clean_casefolded_name(self):
        cases = [
            ("Open The Google Chrome App", "google chrome"),
            ("please switch to  Premiere   Pro window!", "premiere pro"),
            ("OPEN CHROME", "chrome"),
        ]
        for text, expected_name in cases:
            with self.subTest(text=text):
                apps = FakeApps()
                route(text, apps)
                self.assertEqual(apps.calls, [expected_name])

    def test_and_is_not_split(self):
        apps = FakeApps()
        result = route("open chrome and notepad", apps)
        self.assertEqual(apps.calls, ["chrome and notepad"])
        self.assertEqual(result, unknown("chrome and notepad"))

    def test_args_contain_only_resolved_id(self):
        # The typed alias differs from the id, so any leak of raw text would show up.
        cases = [
            ("open Google Chrome", {"app": "chrome"}),
            ("switch to the Premiere Pro window", {"app": "premiere"}),
            ("please open VS Code!", {"app": "vscode"}),
        ]
        for text, expected_args in cases:
            with self.subTest(text=text):
                result = route(text, FakeApps())
                self.assertEqual(dict(result.action.args), expected_args)

    def test_action_fields_are_fixed(self):
        for text in ["open chrome", "switch to chrome"]:
            with self.subTest(text=text):
                action = route(text, FakeApps()).action
                self.assertIsNone(action.target)
                self.assertEqual(action.risk_flag, "low")
                self.assertEqual(action.thought, "fast lane")

    def test_slow_routes_have_no_action(self):
        for text in ["run x", "open cmd", "open", "", "x" * 301]:
            with self.subTest(text=text):
                result = route(text, FakeApps())
                self.assertEqual(result.lane, SLOW)
                self.assertIsNone(result.action)

    def test_resolver_decides_the_id(self):
        apps = FakeApps({"chrome": "browser-7"})
        result = route("open chrome", apps)
        self.assertEqual(result.action.args["app"], "browser-7")

    def test_does_not_mutate_inputs(self):
        apps = FakeApps()
        names_before = copy.deepcopy(apps.names)
        text = "  Please open   the Chrome app. "
        text_before = str(text)
        route(text, apps)
        self.assertEqual(text, text_before)
        self.assertEqual(apps.names, names_before)

    def test_deterministic(self):
        inputs = ["open chrome", "open cmd", "open", "run x", "", "x" * 301]
        for text in inputs:
            with self.subTest(text=text[:20]):
                first = route(text, FakeApps())
                second = route(text, FakeApps())
                third = route(text, FakeApps())
                self.assertEqual(first, second)
                self.assertEqual(second, third)

    def test_route_is_frozen(self):
        result = route("open chrome", FakeApps())
        with self.assertRaises(AttributeError):
            result.lane = SLOW

    def test_unicode_input_does_not_crash(self):
        cases = [
            ("открой хром", slow()),
            ("開啟 chrome", slow()),
            ("open Ünïcode", unknown("Ünïcode")),
            ("open 😀", unknown("😀")),
            ("OPEN STRASSE", unknown("STRASSE")),
            ("open\u00a0chrome", Route(FAST, launch("chrome"))),
            ("open chrome\u3002", unknown("chrome\u3002")),
            ("\u200b", slow()),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(route(text, FakeApps()), expected)

    def test_invisible_characters_are_ignored(self):
        # Found live: PowerShell pipes a byte-order mark in front of the first line.
        cases = [
            ("﻿open notepad", Route(FAST, launch("notepad"))),
            ("​open chrome", Route(FAST, launch("chrome"))),
            ("open‍ chrome⁠", Route(FAST, launch("chrome"))),
            ("switch to﻿ notepad", Route(FAST, switch("notepad"))),
            ("﻿", slow()),
        ]
        for text, expected in cases:
            with self.subTest(text=repr(text)):
                self.assertEqual(route(text, FakeApps()), expected)

    def test_case_tables_have_at_least_45_cases(self):
        total = len(FAST_CASES) + len(UNKNOWN_APP_CASES)
        total += len(EMPTY_APP_INPUTS) + len(NON_COMMANDS)
        self.assertGreaterEqual(total, 45)


if __name__ == "__main__":
    unittest.main()
