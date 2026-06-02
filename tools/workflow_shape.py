"""Tiny GitHub Actions workflow structural lints.

These helpers do not validate YAML semantics — they only check the
coarse shape (which actions are pinned, which `target:` stages are
built, which cache refs are wired in `cache-from` / `cache-to`) so the
article can prove the CI under review actually runs the multistage
Dockerfile with a registry-backed BuildKit cache.

The parser is deliberately line-oriented to match the style of the
companion ``dockerfile_shape`` module — no third-party YAML
dependency, no nested structural model. The cost is that the helpers
assume the workflow uses the conventional ``key: value`` and
``- list-item`` indentation that GitHub Actions itself emits; that is
sufficient for the lint surface this article cares about.
"""
from __future__ import annotations

from pathlib import Path

_BUILD_PUSH_ACTION_PREFIX = "docker/build-push-action"
_SETUP_BUILDX_ACTION_PREFIX = "docker/setup-buildx-action"
_LOGIN_ACTION_PREFIX = "docker/login-action"
_CHECKOUT_ACTION_PREFIX = "actions/checkout"


def read_workflow_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def workflow_uses(text: str) -> list[str]:
    refs: list[str] = []
    for line in text.splitlines():
        ref = _extract_key_value(line, "uses")
        if ref is not None:
            refs.append(ref)
    return refs


def workflow_targets(text: str) -> list[str]:
    targets: list[str] = []
    for line in text.splitlines():
        value = _extract_key_value(line, "target")
        if value is None:
            continue
        targets.append(value)
    return targets


def workflow_triggers(text: str) -> list[str]:
    triggers: list[str] = []
    inside = False
    for line in text.splitlines():
        if _is_top_level_key(line, "on"):
            inside = True
            continue
        if not inside:
            continue
        if _is_top_level_key(line, None):
            break
        nested_key = _extract_nested_key(line, indent=2)
        if nested_key:
            triggers.append(nested_key)
    return triggers


def workflow_jobs(text: str) -> list[str]:
    jobs: list[str] = []
    inside = False
    for line in text.splitlines():
        if _is_top_level_key(line, "jobs"):
            inside = True
            continue
        if not inside:
            continue
        if _is_top_level_key(line, None):
            break
        nested_key = _extract_nested_key(line, indent=2)
        if nested_key:
            jobs.append(nested_key)
    return jobs


def workflow_has_action(text: str, action_prefix: str) -> bool:
    return any(ref.startswith(action_prefix) for ref in workflow_uses(text))


def workflow_uses_setup_buildx(text: str) -> bool:
    return workflow_has_action(text, _SETUP_BUILDX_ACTION_PREFIX)


def workflow_uses_build_push_action(text: str) -> bool:
    return workflow_has_action(text, _BUILD_PUSH_ACTION_PREFIX)


def workflow_uses_login_action(text: str) -> bool:
    return workflow_has_action(text, _LOGIN_ACTION_PREFIX)


def workflow_uses_checkout(text: str) -> bool:
    return workflow_has_action(text, _CHECKOUT_ACTION_PREFIX)


def workflow_cache_from_entries(text: str) -> list[str]:
    return _collect_cache_entries(text, "cache-from")


def workflow_cache_to_entries(text: str) -> list[str]:
    return _collect_cache_entries(text, "cache-to")


def workflow_cache_to_refs(text: str) -> list[str]:
    return [_extract_ref_field(entry) for entry in workflow_cache_to_entries(text)]


def workflow_cache_from_refs(text: str) -> list[str]:
    return [_extract_ref_field(entry) for entry in workflow_cache_from_entries(text)]


def workflow_cache_to_modes(text: str) -> list[str]:
    return [_extract_mode_field(entry) for entry in workflow_cache_to_entries(text)]


def workflow_uses_registry_cache(text: str) -> bool:
    entries = workflow_cache_from_entries(text) + workflow_cache_to_entries(text)
    return any("type=registry" in entry for entry in entries)


def workflow_runners(text: str) -> list[str]:
    runners: list[str] = []
    for line in text.splitlines():
        value = _extract_key_value(line, "runs-on")
        if value is not None:
            runners.append(value)
    return runners


def workflow_step_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("- name:"):
            continue
        _, _, raw_value = line.partition("name:")
        names.append(_clean_value(raw_value))
    return names


# ---- internals ----------------------------------------------------------


def _is_top_level_key(line: str, key: str | None) -> bool:
    if not line or line.startswith(" "):
        return False
    if line.startswith("#"):
        return False
    if ":" not in line:
        return False
    name = line.split(":", 1)[0].strip()
    if key is None:
        return bool(name)
    return name == key


def _extract_nested_key(line: str, *, indent: int) -> str | None:
    if not line.startswith(" " * indent):
        return None
    if line.startswith(" " * (indent + 1)) and not line.startswith(" " * indent + "  "):
        return None
    body = line[indent:]
    if body.startswith(" ") or body.startswith("-") or body.startswith("#"):
        return None
    if ":" not in body:
        return None
    return body.split(":", 1)[0].strip() or None


def _extract_key_value(line: str, key: str) -> str | None:
    stripped = line.lstrip()
    prefix_dash = f"- {key}:"
    prefix_plain = f"{key}:"
    if stripped.startswith(prefix_dash):
        _, _, raw_value = stripped.partition(prefix_dash)
    elif stripped.startswith(prefix_plain):
        _, _, raw_value = stripped.partition(prefix_plain)
    else:
        return None
    return _clean_value(raw_value)


def _clean_value(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith("\"") and value.endswith("\"") and len(value) >= 2:
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        value = value[1:-1]
    return value


def _collect_cache_entries(text: str, key: str) -> list[str]:
    entries: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        value = _extract_key_value(line, key)
        if value is None:
            index += 1
            continue
        if value == "|" or value == ">":
            block, consumed = _collect_block_scalar(lines, index + 1, _leading_spaces(line))
            entries.extend(block)
            index += 1 + consumed
            continue
        if value:
            entries.append(value)
        index += 1
    return entries


def _collect_block_scalar(lines: list[str], start: int, base_indent: int) -> tuple[list[str], int]:
    collected: list[str] = []
    consumed = 0
    for index in range(start, len(lines)):
        line = lines[index]
        if not line.strip():
            consumed += 1
            continue
        if _leading_spaces(line) <= base_indent:
            break
        collected.append(line.strip())
        consumed += 1
    return collected, consumed


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _extract_ref_field(entry: str) -> str:
    for field in entry.split(","):
        field = field.strip()
        if field.startswith("ref="):
            return field.split("=", 1)[1]
    return ""


def _extract_mode_field(entry: str) -> str:
    for field in entry.split(","):
        field = field.strip()
        if field.startswith("mode="):
            return field.split("=", 1)[1]
    return ""
