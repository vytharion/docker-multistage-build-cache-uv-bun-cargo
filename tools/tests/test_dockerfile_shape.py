from pathlib import Path

from dockerfile_shape import (
    cache_mount_targets,
    copy_from_sources,
    count_cache_mounts,
    count_copy_directives,
    count_copy_from_directives,
    count_stages,
    has_stage,
    mentions,
    read_dockerfile_lines,
    stage_cache_mount_targets,
    stage_names,
)

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"

REQUIRED_DEP_STAGES = ("uv-deps", "bun-deps", "cargo-deps")


def _lines() -> list[str]:
    return read_dockerfile_lines(DOCKERFILE)


def test_dockerfile_exists():
    assert DOCKERFILE.exists(), f"missing Dockerfile at {DOCKERFILE}"


def test_dockerfile_is_multistage():
    assert count_stages(_lines()) >= 4


def test_dockerfile_has_dedicated_dep_stage_per_toolchain():
    lines = _lines()
    for stage in REQUIRED_DEP_STAGES:
        assert has_stage(lines, stage), f"missing dependency stage: {stage}"


def test_dockerfile_has_shared_base_stage():
    assert has_stage(_lines(), "base")


def test_dockerfile_has_runtime_stage():
    assert has_stage(_lines(), "runtime")


def test_every_stage_is_named():
    names = stage_names(_lines())
    assert all(name is not None for name in names), names


def test_runtime_copies_from_each_dep_stage():
    lines = _lines()
    sources = set(copy_from_sources(lines))
    for stage in REQUIRED_DEP_STAGES:
        assert stage in sources, f"runtime missing COPY --from={stage}"


def test_dockerfile_has_multiple_copy_directives():
    assert count_copy_directives(_lines()) > 1


def test_dockerfile_has_cross_stage_copies():
    assert count_copy_from_directives(_lines()) >= 3


def test_dockerfile_installs_uv():
    assert mentions(_lines(), "uv")


def test_dockerfile_installs_bun():
    assert mentions(_lines(), "bun")


def test_dockerfile_installs_rust_toolchain():
    lines = _lines()
    assert mentions(lines, "rustup") or mentions(lines, "cargo")


def test_dockerfile_declares_buildkit_syntax():
    text = DOCKERFILE.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith("# syntax=docker/dockerfile:")


def test_dockerfile_has_at_least_one_cache_mount():
    assert count_cache_mounts(_lines()) >= 1


def test_cargo_deps_has_registry_cache_mount():
    targets = stage_cache_mount_targets(_lines(), "cargo-deps")
    assert "/root/.cargo/registry" in targets


def test_cargo_deps_has_target_cache_mount():
    targets = stage_cache_mount_targets(_lines(), "cargo-deps")
    assert any(target.rstrip("/").endswith("/target") for target in targets), targets


def test_cargo_deps_has_cargo_git_cache_mount():
    targets = stage_cache_mount_targets(_lines(), "cargo-deps")
    assert "/root/.cargo/git" in targets


def test_cache_mounts_only_attach_to_dep_stages():
    base_targets = stage_cache_mount_targets(_lines(), "base")
    runtime_targets = stage_cache_mount_targets(_lines(), "runtime")
    assert base_targets == []
    assert runtime_targets == []


def test_cache_mount_targets_are_absolute_paths():
    for target in cache_mount_targets(_lines()):
        assert target.startswith("/"), f"non-absolute cache mount target: {target}"
