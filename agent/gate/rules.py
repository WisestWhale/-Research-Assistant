"""The safety gate: a pure function from (action, context) to allow / ask / block.

Rules run in order and the first one that fires decides. Rule numbers match docs/PLAN.md §5,
plus rule 0 for malformed actions. Nothing here reads the screen, the filesystem or the
model's text: names and paths are only compared against fixed lists, and the action's
`thought` is never looked at, so injected text cannot change a verdict.
"""

import re
from collections.abc import Mapping
from pathlib import PureWindowsPath

from agent.gate import policy
from agent.types import ALLOW, ASK, BLOCK, Action, Context, Decision, Element, PathFacts

DRIVE_PREFIX = re.compile(r"^[A-Za-z]:\\")
DRIVE_PREFIX_LENGTH = 3


# ---------- small helpers ----------

def basename(exe_path):
    return PureWindowsPath(exe_path).name.casefold()


def lookup_casefold(mapping, key):
    """Return mapping[key] comparing keys case-insensitively, or None."""
    wanted = key.strip().casefold()
    for candidate, value in mapping.items():
        if candidate.strip().casefold() == wanted:
            return value
    return None


def normalize_keys(keys):
    """Canonical form like 'ctrl+s', or None if the chord is malformed."""
    parts = []
    for raw_part in keys.split("+"):
        part = raw_part.strip().casefold()
        if not part:
            return None
        parts.append(policy.KEY_ALIASES.get(part, part))
    if len(set(parts)) != len(parts):
        return None

    modifiers = [name for name in policy.MODIFIER_ORDER if name in parts]
    others = [part for part in parts if part not in policy.MODIFIER_ORDER]
    if len(others) != 1:
        return None
    return "+".join(modifiers + others)


def path_problem(raw_path):
    """Why a path fails the text-only checks, or None if it passes."""
    path = raw_path.replace("/", "\\")
    if path.startswith("\\\\"):
        return "UNC or device namespace path"
    if not DRIVE_PREFIX.match(path):
        return "not an absolute drive path"
    if ":" in path[2:]:
        return "colon after the drive (alternate data stream or URI)"
    if "%" in path:
        return "environment variable in path"

    for segment in path[DRIVE_PREFIX_LENGTH:].split("\\"):
        if segment in (".", ".."):
            return "relative segment in path"
        if "~" in segment:
            return "short (8.3) name in path"
        if segment.endswith((".", " ")):
            return "segment ends in a dot or space"
        stem = segment.split(".")[0].strip().casefold()
        if stem in policy.DEVICE_NAMES:
            return "device name in path"
    return None


def is_inside(path, folder):
    candidate = path.replace("/", "\\").casefold().rstrip("\\")
    root = folder.replace("/", "\\").casefold().rstrip("\\")
    return candidate == root or candidate.startswith(root + "\\")


def suffix_of(name):
    return PureWindowsPath(name).suffix.casefold()


def raw_path_of(action):
    """The action's path if it is a path action, else None."""
    if action.kind in policy.PATH_KINDS:
        return action.args["path"]
    if action.kind == "find_files" and "path" in action.args:
        return action.args["path"]
    return None


def facts_for(action, context) -> PathFacts | None:
    raw_path = raw_path_of(action)
    if raw_path is None:
        return None
    return context.path_facts.get(raw_path)


def is_explorer_or_dialog(element: Element, context: Context):
    if basename(element.process_path) == policy.EXPLORER_EXE:
        return True
    return context.window_class == policy.DIALOG_WINDOW_CLASS


def is_destructive_name(name):
    label = name.strip().casefold()
    for word in policy.DESTRUCTIVE_NAMES:
        if label == word or label.startswith(word + " "):
            return True
    return False


def matching_profile_entry(action: Action, context: Context):
    """The profile entry that allows this GUI action, or None. Never matches by name."""
    element = context.target
    entries = lookup_casefold(context.app_profiles, element.process_path) or ()
    for entry in entries:
        if action.kind not in entry.kinds:
            continue
        if entry.automation_id:
            if entry.automation_id == element.automation_id:
                return entry
            continue
        same_type = entry.control_type == element.control_type
        if same_type and tuple(entry.ancestors) == tuple(element.ancestors):
            return entry
    return None


# ---------- rules, in order ----------

def rule_0_malformed(action, context):
    if not isinstance(action.args, Mapping):
        return "arguments are not a mapping"
    if action.kind not in policy.ALL_KINDS:
        return "unknown action kind"
    if action.risk_flag not in policy.RISK_LEVELS:
        return "unknown risk flag"
    for name in policy.REQUIRED_ARGS.get(action.kind, ()):
        if not isinstance(action.args.get(name), str):
            return f"missing argument '{name}'"
    if action.kind in policy.GUI_KINDS:
        if not action.target:
            return "GUI action without a target"
        if context.target is None:
            return "target element was not resolved"
        if context.target.element_id != action.target:
            return "resolved element does not match the proposed target"
    return None


def rule_1_secure_desktop(action, context):
    if context.secure_desktop:
        return "secure desktop is active"
    if basename(context.foreground_exe) in policy.SECURE_DESKTOP_EXES:
        return "a UAC or sign-in prompt is in front"
    return None


def rule_2_terminal(action, context):
    if action.kind in ("launch_app", "switch_window"):
        exe_path = lookup_casefold(context.app_table, action.args["app"])
        if exe_path is not None and basename(exe_path) in policy.TERMINAL_EXES:
            return "app is a terminal"
        return None
    if action.kind not in policy.GUI_KINDS:
        return None

    element = context.target
    if basename(element.process_path) in policy.TERMINAL_EXES:
        return "target is in a terminal"
    if basename(context.foreground_exe) in policy.TERMINAL_EXES:
        return "a terminal is in front"
    is_dialog = context.window_class == policy.DIALOG_WINDOW_CLASS
    if is_dialog and context.window_title.strip().casefold() == policy.RUN_DIALOG_TITLE:
        return "target is the Run dialog"
    if basename(element.process_path) in policy.IDE_EXES:
        labels = [element.automation_id, element.class_name] + list(element.ancestor_ids)
        for label in labels:
            if policy.TERMINAL_MARKER in label.casefold():
                return "target is an IDE terminal pane"
    return None


def rule_3_key_allow_list(action, context):
    if action.kind != "key":
        return None
    if normalize_keys(action.args["keys"]) not in policy.ALLOWED_KEYS:
        return "key is not on the allow-list"
    return None


def rule_4_unsafe_text(action, context):
    if action.kind != "set_text":
        return None
    element = context.target
    text = action.args["text"]
    if "\r" in text or "\n" in text:
        return "text contains a line break (implicit Enter)"
    if element.is_password:
        return "target is a password field"
    name = element.name.casefold()
    automation_id = element.automation_id.casefold()
    if name.startswith(policy.ADDRESS_NAME_PREFIX) or policy.SEARCH_MARKER in name:
        return "target is an address or search box"
    if policy.SEARCH_MARKER in automation_id or policy.ADDRESS_MARKER in automation_id:
        return "target is an address or search box"
    return None


def rule_5_unknown_app(action, context):
    if action.kind not in ("launch_app", "switch_window"):
        return None
    if lookup_casefold(context.app_table, action.args["app"]) is None:
        return "app is not in the app table"
    return None


def rule_6_path_canonical(action, context):
    raw_path = raw_path_of(action)
    if raw_path is None:
        return None
    problem = path_problem(raw_path)
    if problem:
        return problem
    facts = facts_for(action, context)
    if facts is None:
        return "path was not resolved"
    if facts.is_reparse:
        return "path is a junction or symlink"
    if not facts.exists:
        return "path does not exist"
    final_problem = path_problem(facts.final_path)
    if final_problem:
        return f"resolved path: {final_problem}"
    return None


def rule_7_open_file_type(action, context):
    if action.kind != "open_file":
        return None
    final_path = PureWindowsPath(facts_for(action, context).final_path)
    suffixes = [suffix.casefold() for suffix in final_path.suffixes]
    if not suffixes or suffixes[-1] not in policy.DATA_EXTENSIONS:
        return "file type is not a data type"
    if len(suffixes) >= 2 and suffixes[-2] in policy.EXECUTABLE_EXTENSIONS:
        return "double extension hides an executable type"
    return None


def rule_8_allowed_folders(action, context):
    facts = facts_for(action, context)
    if facts is None:
        return None
    inside_any = False
    for folder in context.allowed_folders:
        if is_inside(facts.final_path, folder):
            inside_any = True
            break
    if not inside_any:
        return "path is outside the allowed folders"
    if action.kind in policy.SIZE_CAPPED_KINDS and facts.size_bytes > context.read_size_cap_bytes:
        return "file is over the size cap"
    return None


def rule_9_permanent_delete(action, context):
    if action.kind != "invoke":
        return None
    name = context.target.name.casefold()
    for marker in policy.PERMANENT_DELETE_MARKERS:
        if marker in name:
            return "permanent delete"
    return None


def rule_10_file_changes(action, context):
    if action.kind not in policy.GUI_KINDS:
        return None
    element = context.target
    if not is_explorer_or_dialog(element, context):
        return None
    if action.kind == "key" and normalize_keys(action.args["keys"]) == policy.SAVE_KEYS:
        return "save in a file window may overwrite"
    if action.kind == "invoke" and is_destructive_name(element.name):
        return "command deletes, renames, moves or replaces files"
    if action.kind == "set_text":
        current = element.value or element.name
        if suffix_of(action.args["text"]) != suffix_of(current):
            return "text changes a file extension"
    return None


def rule_11_content_region(action, context):
    if action.kind not in policy.GUI_KINDS:
        return None
    element = context.target
    exe = basename(element.process_path)
    if exe in policy.BROWSER_EXES:
        in_document = policy.BROWSER_CONTENT_TYPE in element.ancestors
        if in_document or element.control_type == policy.BROWSER_CONTENT_TYPE:
            return "target is inside a web page"
    if exe == policy.EXPLORER_EXE:
        in_list = policy.EXPLORER_LIST_TYPE in element.ancestors
        if in_list or element.control_type in policy.EXPLORER_ITEM_TYPES:
            return "target is a file in the item view"
    return None


def rule_12_unidentified_element(action, context):
    if action.kind not in policy.GUI_KINDS:
        return None
    if context.target.automation_id:
        return None
    if matching_profile_entry(action, context) is None:
        return "element has no automation id and no profile match"
    return None


def rule_13_model_risk(action, context):
    if action.risk_flag != "low":
        return "model flagged the action as risky"
    return None


def rule_14_tools_and_control(action, context):
    if action.kind in policy.CONTROL_KINDS or action.kind in policy.TOOL_KINDS:
        return "tool or control action passed every check"
    return None


def rule_15_profile_allow(action, context):
    if action.kind not in policy.GUI_KINDS:
        return None
    if matching_profile_entry(action, context) is not None:
        return "matches the app profile"
    return None


def rule_16_default(action, context):
    return "no rule allows this"


RULES = (
    (0, BLOCK, rule_0_malformed),
    (1, BLOCK, rule_1_secure_desktop),
    (2, BLOCK, rule_2_terminal),
    (3, BLOCK, rule_3_key_allow_list),
    (4, BLOCK, rule_4_unsafe_text),
    (5, BLOCK, rule_5_unknown_app),
    (6, BLOCK, rule_6_path_canonical),
    (7, BLOCK, rule_7_open_file_type),
    (8, BLOCK, rule_8_allowed_folders),
    (9, BLOCK, rule_9_permanent_delete),
    (10, ASK, rule_10_file_changes),
    (11, ASK, rule_11_content_region),
    (12, ASK, rule_12_unidentified_element),
    (13, ASK, rule_13_model_risk),
    (14, ALLOW, rule_14_tools_and_control),
    (15, ALLOW, rule_15_profile_allow),
    (16, ASK, rule_16_default),
)


def decide(action: Action, context: Context) -> Decision:
    for number, verdict, rule in RULES:
        reason = rule(action, context)
        if reason:
            return Decision(verdict, number, reason)
    raise AssertionError("rule 16 always fires")
