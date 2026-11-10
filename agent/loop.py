"""One typed command, end to end: route -> gate -> approval -> run -> log.

Every action passes the gate, and anything the gate marks "ask" needs a clear yes; an empty or
unclear answer counts as no.
"""

import time

from agent.gate import decide
from agent.router import FAST, route
from agent.types import ALLOW, ASK, BLOCK, Context

MAX_LOGGED_CHARS = 300
YES_ANSWERS = frozenset({"y", "yes"})
SLOW_LANE_MISSING = "I can't do that yet: only 'open <app>' and 'switch to <app>' work so far."


def describe(action):
    return f"{action.kind} {action.args.get('app', '')}".strip()


def is_clear_yes(answer):
    return answer.strip().casefold() in YES_ANSWERS


class CommandLoop:
    def __init__(self, apps, tools, log, observe, ask, clock=time.perf_counter):
        """observe() -> (foreground_exe, secure_desktop); ask(question) -> the user's answer."""
        self.apps = apps
        self.tools = tools
        self.log = log
        self.observe = observe
        self.ask = ask
        self.clock = clock
        self.step = 0

    def handle(self, text):
        """Run one command and return the message to show the user."""
        self.step += 1
        started = self.clock()
        record = {"step": self.step, "command": text[:MAX_LOGGED_CHARS]}

        routed = route(text, self.apps)
        record["lane"] = routed.lane
        if routed.lane != FAST:
            message = routed.reply or SLOW_LANE_MISSING
            return self._finish(record, started, message, ok=False)

        action = routed.action
        record["action"] = {"kind": action.kind, "args": dict(action.args)}
        try:
            foreground_exe, secure_desktop = self.observe()
        except OSError as error:
            message = f"Not done: couldn't read which window is in front ({error})."
            return self._finish(record, started, message, ok=False)

        context = Context(
            foreground_exe=foreground_exe,
            secure_desktop=secure_desktop,
            app_table=self.apps.exe_table(),
        )
        decision = decide(action, context)
        record["decision"] = {
            "verdict": decision.verdict, "rule": decision.rule, "reason": decision.reason,
        }

        if decision.verdict == BLOCK:
            return self._finish(record, started, f"Blocked: {decision.reason}.", ok=False)
        if decision.verdict == ASK:
            answer = self.ask(f"{describe(action)} ({decision.reason}). Do it?")
            record["approved"] = is_clear_yes(answer)
            if not record["approved"]:
                return self._finish(record, started, "Not done.", ok=False)
        elif decision.verdict != ALLOW:
            raise ValueError(f"unknown verdict {decision.verdict!r}")

        result = self.tools.run(action)
        return self._finish(record, started, result.message, ok=result.ok)

    def _finish(self, record, started, message, ok):
        record["result"] = {"ok": ok, "message": message}
        record["ms"] = round((self.clock() - started) * 1000)
        self.log.append(record)
        return message
