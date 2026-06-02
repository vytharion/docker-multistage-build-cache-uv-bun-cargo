"""Tiny Dockerfile structural lints.

These helpers do not validate Dockerfile semantics — they only check the
coarse shape (stage count + names, COPY count, presence of expected
install lines) so the article can prove the Dockerfile under review is
the multistage shape it claims to be.
"""
from __future__ import annotations

from pathlib import Path


def read_dockerfile_lines(path: str | Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if _is_meaningful(line)]


def _is_meaningful(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return not stripped.startswith("#")


def count_stages(lines: list[str]) -> int:
    return sum(1 for line in lines if _is_from_line(line))


def stage_names(lines: list[str]) -> list[str | None]:
    names: list[str | None] = []
    for line in lines:
        if _is_from_line(line):
            names.append(_extract_stage_name(line))
    return names


def has_stage(lines: list[str], name: str) -> bool:
    return name in stage_names(lines)


def count_copy_directives(lines: list[str]) -> int:
    return sum(1 for line in lines if line.strip().upper().startswith("COPY "))


def count_copy_from_directives(lines: list[str]) -> int:
    matches = 0
    for line in lines:
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        if "--from=" in stripped:
            matches += 1
    return matches


def copy_from_sources(lines: list[str]) -> list[str]:
    sources: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        if "--from=" not in stripped:
            continue
        sources.append(_extract_copy_from_target(stripped))
    return sources


def mentions(lines: list[str], needle: str) -> bool:
    return any(needle in line for line in lines)


def cache_mount_targets(lines: list[str]) -> list[str]:
    targets: list[str] = []
    for line in lines:
        targets.extend(_extract_cache_targets_from_line(line))
    return targets


def stage_cache_mount_targets(lines: list[str], stage: str) -> list[str]:
    targets: list[str] = []
    for line in _lines_in_stage(lines, stage):
        targets.extend(_extract_cache_targets_from_line(line))
    return targets


def count_cache_mounts(lines: list[str]) -> int:
    return len(cache_mount_targets(lines))


def stage_copy_sources(lines: list[str], stage: str) -> list[str]:
    sources: list[str] = []
    for line in _lines_in_stage(lines, stage):
        sources.extend(_extract_copy_sources(line))
    return sources


def stage_copies_path(lines: list[str], stage: str, path: str) -> bool:
    return path in stage_copy_sources(lines, stage)


def stage_lines(lines: list[str], stage: str) -> list[str]:
    return _lines_in_stage(lines, stage)


def stage_base_image(lines: list[str], stage: str) -> str | None:
    for line in lines:
        if not _is_from_line(line):
            continue
        if _extract_stage_name(line) != stage:
            continue
        return _extract_from_image(line)
    return None


def stage_user(lines: list[str], stage: str) -> str | None:
    last: str | None = None
    for line in _lines_in_stage(lines, stage):
        stripped = line.strip()
        if not stripped.upper().startswith("USER "):
            continue
        last = stripped.split(None, 1)[1].strip()
    return last


def stage_has_directive(lines: list[str], stage: str, directive: str) -> bool:
    return _find_directive_line(lines, stage, directive) is not None


def stage_directive_line(lines: list[str], stage: str, directive: str) -> str | None:
    return _find_directive_line(lines, stage, directive)


def stage_mentions(lines: list[str], stage: str, needle: str) -> int:
    return sum(1 for line in _lines_in_stage(lines, stage) if needle in line)


def _find_directive_line(lines: list[str], stage: str, directive: str) -> str | None:
    prefix = directive.upper() + " "
    for line in _lines_in_stage(lines, stage):
        if line.strip().upper().startswith(prefix):
            return line.strip()
    return None


def _extract_from_image(line: str) -> str | None:
    tokens = line.strip().split()
    if len(tokens) < 2:
        return None
    return tokens[1]


def _extract_copy_sources(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.upper().startswith("COPY "):
        return []
    tokens = stripped.split()[1:]
    operands = [token for token in tokens if not token.startswith("--")]
    if len(operands) < 2:
        return []
    return operands[:-1]


def _lines_in_stage(lines: list[str], stage: str) -> list[str]:
    inside = False
    collected: list[str] = []
    for line in lines:
        if _is_from_line(line):
            inside = _extract_stage_name(line) == stage
            continue
        if inside:
            collected.append(line)
    return collected


def _extract_cache_targets_from_line(line: str) -> list[str]:
    if "--mount=type=cache" not in line:
        return []
    targets: list[str] = []
    for token in line.split():
        if not token.startswith("--mount="):
            continue
        target = _parse_mount_target(token)
        if target:
            targets.append(target)
    return targets


def _parse_mount_target(token: str) -> str | None:
    payload = token.split("=", 1)[1]
    fields = payload.split(",")
    if "type=cache" not in fields:
        return None
    for field in fields:
        if field.startswith("target="):
            return field.split("=", 1)[1]
    return None


def _is_from_line(line: str) -> bool:
    return line.strip().upper().startswith("FROM ")


def _extract_stage_name(line: str) -> str | None:
    tokens = line.strip().split()
    for index, token in enumerate(tokens):
        if token.upper() == "AS" and index + 1 < len(tokens):
            return tokens[index + 1]
    return None


def _extract_copy_from_target(line: str) -> str:
    for token in line.split():
        if token.startswith("--from="):
            return token.split("=", 1)[1]
    return ""
