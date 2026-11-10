import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from agent.apps import AppEntry, AppTable
from agent.log import ActionLog
from agent.loop import SLOW_LANE_MISSING, CommandLoop
from agent.tools.launch import ToolResult
from agent.types import ASK, Decision

NOTEPAD_EXE = r"C:\Windows\System32\notepad.exe"
APPS = AppTable([AppEntry("notepad", ("notepad",), NOTEPAD_EXE, "notepad.exe")])
FIXED_TIME = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


class RecordingTools:
    def __init__(self, result=ToolResult(True, "Opened notepad.")):
        self.result = result
        self.calls = []

    def run(self, action):
        self.calls.append(action)
        return self.result


class MemoryLog:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


def make_loop(answer="", foreground=NOTEPAD_EXE, secure=False, tools=None):
    questions = []

    def ask(question):
        questions.append(question)
        return answer

    def observe():
        return foreground, secure

    loop = CommandLoop(APPS, tools or RecordingTools(), MemoryLog(), observe, ask)
    return loop, questions


class TestAllowAndBlock(unittest.TestCase):
    def test_allowed_command_runs_and_is_logged(self):
        loop, questions = make_loop()
        message = loop.handle("open notepad")
        self.assertEqual(message, "Opened notepad.")
        self.assertEqual(questions, [])
        record = loop.log.records[0]
        self.assertEqual(record["lane"], "fast")
        self.assertEqual(record["action"], {"kind": "launch_app", "args": {"app": "notepad"}})
        self.assertEqual(record["decision"]["verdict"], "allow")
        self.assertTrue(record["result"]["ok"])

    def test_tool_failure_is_reported_and_logged(self):
        tools = RecordingTools(ToolResult(False, "notepad isn't open."))
        loop, _ = make_loop(tools=tools)
        self.assertEqual(loop.handle("switch to notepad"), "notepad isn't open.")
        self.assertFalse(loop.log.records[0]["result"]["ok"])

    def test_secure_desktop_blocks_without_running(self):
        tools = RecordingTools()
        loop, _ = make_loop(secure=True, tools=tools)
        message = loop.handle("open notepad")
        self.assertTrue(message.startswith("Blocked:"))
        self.assertEqual(tools.calls, [])
        self.assertEqual(loop.log.records[0]["decision"]["rule"], 1)

    def test_unreadable_foreground_refuses(self):
        tools = RecordingTools()

        def broken_observe():
            raise OSError("access denied")

        loop = CommandLoop(APPS, tools, MemoryLog(), broken_observe, lambda question: "y")
        message = loop.handle("open notepad")
        self.assertIn("couldn't read which window is in front", message)
        self.assertEqual(tools.calls, [])


class TestSlowLane(unittest.TestCase):
    def test_unknown_app_reply_is_shown_and_nothing_runs(self):
        tools = RecordingTools()
        loop, _ = make_loop(tools=tools)
        self.assertEqual(loop.handle("open cmd"), "I don't know an app called 'cmd'.")
        self.assertEqual(tools.calls, [])
        self.assertEqual(loop.log.records[0]["lane"], "slow")

    def test_non_command_gets_the_not_built_message(self):
        loop, _ = make_loop()
        self.assertEqual(loop.handle("delete everything"), SLOW_LANE_MISSING)


class TestApproval(unittest.TestCase):
    """The fast lane's actions are normally allowed, so force an "ask" to test the prompt."""

    def run_with_answer(self, answer):
        tools = RecordingTools()
        loop, questions = make_loop(answer=answer, tools=tools)
        forced = Decision(ASK, 13, "test")
        with mock.patch("agent.loop.decide", return_value=forced):
            message = loop.handle("open notepad")
        return message, tools, questions, loop.log.records[0]

    def test_clear_yes_runs(self):
        for answer in ("y", "Y", "yes", " YES "):
            with self.subTest(answer=answer):
                message, tools, questions, record = self.run_with_answer(answer)
                self.assertEqual(len(tools.calls), 1)
                self.assertEqual(len(questions), 1)
                self.assertTrue(record["approved"])

    def test_anything_else_is_no(self):
        for answer in ("", "n", "no", "yeah", "sure", "y es", "ok", "yes please", "1"):
            with self.subTest(answer=answer):
                message, tools, questions, record = self.run_with_answer(answer)
                self.assertEqual(message, "Not done.")
                self.assertEqual(tools.calls, [])
                self.assertFalse(record["approved"])


class TestLogging(unittest.TestCase):
    def test_every_command_gets_one_numbered_record(self):
        loop, _ = make_loop()
        loop.handle("open notepad")
        loop.handle("open cmd")
        loop.handle("hello")
        steps = [record["step"] for record in loop.log.records]
        self.assertEqual(steps, [1, 2, 3])

    def test_long_command_is_truncated_in_the_log(self):
        loop, _ = make_loop()
        loop.handle("x" * 1000)
        self.assertEqual(len(loop.log.records[0]["command"]), 300)


class TestActionLogFile(unittest.TestCase):
    def test_appends_json_lines_and_keeps_earlier_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "actions.jsonl"
            log = ActionLog(path, now=lambda: FIXED_TIME)
            log.append({"step": 1, "command": "open notepad"})
            log.append({"step": 2, "command": "öffne Notepad"})
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        self.assertEqual(first["step"], 1)
        self.assertEqual(second["command"], "öffne Notepad")
        self.assertEqual(first["time"], FIXED_TIME.isoformat())

    def test_append_does_not_modify_the_record(self):
        with tempfile.TemporaryDirectory() as folder:
            log = ActionLog(Path(folder) / "actions.jsonl", now=lambda: FIXED_TIME)
            record = {"step": 1}
            log.append(record)
        self.assertEqual(record, {"step": 1})


if __name__ == "__main__":
    unittest.main()
