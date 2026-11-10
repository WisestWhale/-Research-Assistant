"""Data shared by the gate, the observer and the executor. All records are immutable."""

from dataclasses import dataclass, field
from typing import Mapping

ALLOW = "allow"
ASK = "ask"
BLOCK = "block"


@dataclass(frozen=True)
class Element:
    """One UI Automation element, as the observer saw it and the executor re-resolved it."""

    element_id: str
    control_type: str
    name: str = ""
    automation_id: str = ""
    class_name: str = ""
    value: str = ""
    # Control types and automation ids of the ancestors, window first, parent last.
    ancestors: tuple[str, ...] = ()
    ancestor_ids: tuple[str, ...] = ()
    is_password: bool = False
    process_path: str = ""


@dataclass(frozen=True)
class Action:
    """One step proposed by the brain or the fast lane."""

    kind: str
    target: str | None = None
    args: Mapping[str, str] = field(default_factory=dict)
    risk_flag: str = "low"
    thought: str = ""


@dataclass(frozen=True)
class PathFacts:
    """Filesystem facts about a path, resolved outside the gate so the gate stays pure."""

    final_path: str
    exists: bool
    is_reparse: bool
    size_bytes: int


@dataclass(frozen=True)
class ProfileEntry:
    """One allowed GUI action in an app profile. Matches by automation id, or by control type
    plus the full ancestor chain. Never by name."""

    kinds: tuple[str, ...]
    automation_id: str = ""
    control_type: str = ""
    ancestors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Context:
    """Everything the gate may look at besides the action itself."""

    foreground_exe: str = ""
    secure_desktop: bool = False
    window_title: str = ""
    window_class: str = ""
    target: Element | None = None
    # App id -> full exe path. launch_app and switch_window only accept these ids.
    app_table: Mapping[str, str] = field(default_factory=dict)
    # Full exe path (any case) -> allowed GUI actions for that app.
    app_profiles: Mapping[str, tuple[ProfileEntry, ...]] = field(default_factory=dict)
    allowed_folders: tuple[str, ...] = ()
    # Raw path from the action -> facts resolved by the tool layer.
    path_facts: Mapping[str, PathFacts] = field(default_factory=dict)
    read_size_cap_bytes: int = 0


@dataclass(frozen=True)
class Decision:
    verdict: str
    rule: int
    reason: str
