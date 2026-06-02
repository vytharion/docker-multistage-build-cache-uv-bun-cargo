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
    stage_copies_path,
    stage_copy_sources,
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


def test_uv_deps_has_uv_cache_mount():
    targets = stage_cache_mount_targets(_lines(), "uv-deps")
    assert "/root/.cache/uv" in targets, targets


def test_bun_deps_has_bun_install_cache_mount():
    targets = stage_cache_mount_targets(_lines(), "bun-deps")
    assert "/root/.bun/install/cache" in targets, targets


def test_every_dep_stage_has_a_cache_mount():
    lines = _lines()
    for stage in REQUIRED_DEP_STAGES:
        targets = stage_cache_mount_targets(lines, stage)
        assert targets, f"{stage} has no cache mounts"


def test_cache_mounts_only_attach_to_dep_stages():
    base_targets = stage_cache_mount_targets(_lines(), "base")
    runtime_targets = stage_cache_mount_targets(_lines(), "runtime")
    assert base_targets == []
    assert runtime_targets == []


def test_cache_mount_targets_are_absolute_paths():
    for target in cache_mount_targets(_lines()):
        assert target.startswith("/"), f"non-absolute cache mount target: {target}"


ALLOWED_LOCKFILE_SOURCES = {
    "uv-deps": {"pyproject.toml", "uv.lock", "services/api/pyproject.toml"},
    "bun-deps": {"package.json", "services/web/package.json"},
    "cargo-deps": {"Cargo.toml", "Cargo.lock", "services/edge/Cargo.toml"},
}


def test_uv_deps_copies_root_lockfile():
    assert stage_copies_path(_lines(), "uv-deps", "uv.lock")


def test_cargo_deps_copies_root_lockfile():
    assert stage_copies_path(_lines(), "cargo-deps", "Cargo.lock")


def test_dep_stages_only_copy_manifest_or_lockfiles():
    lines = _lines()
    for stage, allowed in ALLOWED_LOCKFILE_SOURCES.items():
        sources = stage_copy_sources(lines, stage)
        assert sources, f"{stage} has no COPY instructions"
        unexpected = [src for src in sources if src not in allowed]
        assert unexpected == [], f"{stage} copies non-lockfile sources: {unexpected}"


def test_dep_stages_never_copy_whole_workspace():
    lines = _lines()
    for stage in ALLOWED_LOCKFILE_SOURCES:
        sources = stage_copy_sources(lines, stage)
        assert "." not in sources, f"{stage} copies the whole context"
        for src in sources:
            assert not src.startswith("services/api/src"), src
            assert not src.startswith("services/edge/src"), src
            assert not src.startswith("services/web/src"), src


def test_dep_stages_never_copy_source_directories():
    lines = _lines()
    for stage in ALLOWED_LOCKFILE_SOURCES:
        for src in stage_copy_sources(lines, stage):
            assert "/src" not in src, f"{stage} reaches into a /src tree: {src}"


def test_runtime_stage_does_copy_full_context():
    sources = stage_copy_sources(_lines(), "runtime")
    assert "." in sources, sources
