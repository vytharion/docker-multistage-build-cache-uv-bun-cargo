from pathlib import Path

from dockerfile_shape import (
    count_copy_directives,
    count_stages,
    mentions,
    read_dockerfile_lines,
)

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _lines() -> list[str]:
    return read_dockerfile_lines(DOCKERFILE)


def test_dockerfile_exists():
    assert DOCKERFILE.exists(), f"missing Dockerfile at {DOCKERFILE}"


def test_dockerfile_is_single_stage():
    assert count_stages(_lines()) == 1


def test_dockerfile_copies_workspace_in_one_shot():
    assert count_copy_directives(_lines()) == 1


def test_dockerfile_installs_uv():
    assert mentions(_lines(), "uv")


def test_dockerfile_installs_bun():
    assert mentions(_lines(), "bun")


def test_dockerfile_installs_rust_toolchain():
    lines = _lines()
    assert mentions(lines, "rustup") or mentions(lines, "cargo")
