"""Deterministic first stage of the agent: typed command -> fast-lane Action or "not fast lane".

Pure function. No model, no I/O. The app name is never copied into the action: only the id
returned by apps.resolve() is.
"""

import re
import unicodedata
from dataclasses import dataclass

from agent.types import Action

FAST = "fast"
SLOW = "slow"

MAX_COMMAND_CHARS = 300
# Unicode category "Cf" (format): invisible characters such as U+FEFF and U+200B.
INVISIBLE_CATEGORY = "Cf"

LAUNCH_APP = "launch_app"
SWITCH_WINDOW = "switch_window"

# Verb phrase (casefolded) -> action kind.
VERBS = {
    "open": LAUNCH_APP,
    "launch": LAUNCH_APP,
    "start": LAUNCH_APP,
    "switch to": SWITCH_WINDOW,
    "go to": SWITCH_WINDOW,
    "show": SWITCH_WINDOW,
    "bring up": SWITCH_WINDOW,
}

# Politeness phrases that may open a command.
LEADING_POLITE = ("please", "can you", "could you", "would you", "hey")

REPLY_TOO_LONG = "That command is too long."
REPLY_WHICH_APP = "Which app?"
REPLY_UNKNOWN_APP = "I don't know an app called '{name}'."

RISK_FLAG = "low"
THOUGHT = "fast lane"

# One or more politeness phrases at the start, each followed by an optional comma and spaces.
_LEADING_POLITE_RE = re.compile(
    r"^(?:(?:" + "|".join(LEADING_POLITE) + r")\b,?\s*)+",
    re.IGNORECASE,
)

# The word "please" at the very end, standing alone or after a space or comma.
_TRAILING_POLITE_RE = re.compile(r"(?:^|[\s,])please$", re.IGNORECASE)

# Trailing sentence punctuation (. ! ?) and any spaces mixed in with it.
_TRAILING_PUNCT_RE = re.compile(r"[.!?\s]+$")

# A verb phrase as a whole word at the start, then either the end or whitespace and the rest.
_VERB_RE = re.compile(
    r"^(" + "|".join(VERBS) + r")\b(?:\s+(.*))?$",
    re.IGNORECASE,
)

# An optional leading article "the " before the app name.
_LEADING_THE_RE = re.compile(r"^the\s+", re.IGNORECASE)

# An optional trailing " app" or " window" after the app name.
_TRAILING_NOUN_RE = re.compile(r"\s+(?:app|window)$", re.IGNORECASE)


@dataclass(frozen=True)
class Route:
    lane: str  # FAST or SLOW
    action: Action | None  # set only when lane == FAST
    reply: str = ""  # message for the user when lane == SLOW ("" means: hand to the slow lane)


def _hand_to_slow_lane() -> Route:
    return Route(SLOW, None, reply="")


def _without_invisible(text: str) -> str:
    """Remove Unicode format characters (byte-order mark, zero-width space/joiner, direction
    marks). PowerShell pipes a BOM before the first line, and pasted or transcribed text can
    carry the others; they are invisible, so they must never change a route."""
    return "".join(char for char in text if unicodedata.category(char) != INVISIBLE_CATEGORY)


def _normalize(text: str) -> str:
    """Drop invisible characters, collapse whitespace, then drop trailing punctuation,
    politeness and "please"."""
    visible = _without_invisible(text)
    collapsed = " ".join(visible.split())

    without_punct = _TRAILING_PUNCT_RE.sub("", collapsed)
    without_please = _TRAILING_POLITE_RE.sub("", without_punct)
    # "open chrome, please" leaves a trailing comma behind.
    without_comma = without_please.rstrip(" ,")

    return _LEADING_POLITE_RE.sub("", without_comma).strip()


def _clean_app_name(raw_name: str) -> str:
    """Remove an optional leading "the" and trailing "app" / "window"."""
    name = _LEADING_THE_RE.sub("", raw_name.strip())
    name = _TRAILING_NOUN_RE.sub("", name)
    return name.strip()


def route(text: str, apps) -> Route:
    """Route one typed command. `apps` needs resolve(name) -> app id or None."""
    if len(text) > MAX_COMMAND_CHARS:
        return Route(SLOW, None, reply=REPLY_TOO_LONG)

    normalized = _normalize(text)
    if not normalized:
        return _hand_to_slow_lane()

    verb_match = _VERB_RE.match(normalized)
    if verb_match is None:
        return _hand_to_slow_lane()

    verb = " ".join(verb_match.group(1).casefold().split())
    kind = VERBS[verb]
    name = _clean_app_name(verb_match.group(2) or "")
    if not name:
        return Route(SLOW, None, reply=REPLY_WHICH_APP)

    app_id = apps.resolve(name.casefold())
    if app_id is None:
        return Route(SLOW, None, reply=REPLY_UNKNOWN_APP.format(name=name))

    action = Action(kind=kind, args={"app": app_id}, risk_flag=RISK_FLAG, thought=THOUGHT)
    return Route(FAST, action)
