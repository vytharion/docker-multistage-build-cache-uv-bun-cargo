"""Tiny Dockerfile structural lints.

These helpers do not validate Dockerfile semantics — they only check the
coarse shape (stage count, presence of expected install lines, COPY
count) so the article can prove the step-2 Dockerfile is genuinely the
naive single-stage baseline it claims to be.
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
    return sum(1 for line in lines if line.strip().upper().startswith("FROM "))


def count_copy_directives(lines: list[str]) -> int:
    return sum(1 for line in lines if line.strip().upper().startswith("COPY "))


def mentions(lines: list[str], needle: str) -> bool:
    return any(needle in line for line in lines)
