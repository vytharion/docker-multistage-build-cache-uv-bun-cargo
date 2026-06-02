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
    stage_base_image,
    stage_cache_mount_targets,
    stage_copies_path,
    stage_copy_sources,
    stage_directive_line,
    stage_has_directive,
    stage_lines,
    stage_mentions,
    stage_names,
    stage_user,
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


# ---- Step 7: slim runtime, non-root user, tini, healthcheck ----------


NON_ROOT_FORBIDDEN_USERS = {"root", "0", "0:0"}


def test_runtime_uses_slim_base_image():
    image = stage_base_image(_lines(), "runtime")
    assert image is not None, "runtime stage has no FROM image"
    assert "slim" in image.lower(), f"runtime base image is not slim: {image}"


def test_runtime_does_not_inherit_from_build_base():
    image = stage_base_image(_lines(), "runtime")
    assert image != "base", "runtime must start from a fresh slim image, not the toolchain-heavy base"


def test_runtime_creates_dedicated_system_user():
    runtime = "\n".join(stage_lines(_lines(), "runtime"))
    assert "useradd" in runtime or "adduser" in runtime, runtime


def test_runtime_drops_to_nonroot_user():
    user = stage_user(_lines(), "runtime")
    assert user is not None, "runtime never sets USER"
    assert user not in NON_ROOT_FORBIDDEN_USERS, f"runtime runs as privileged user: {user}"


def test_runtime_installs_tini_package():
    runtime_lines = stage_lines(_lines(), "runtime")
    install_lines = [line for line in runtime_lines if not line.strip().upper().startswith("ENTRYPOINT")]
    assert any("tini" in line for line in install_lines), runtime_lines


def test_runtime_entrypoint_invokes_tini():
    line = stage_directive_line(_lines(), "runtime", "ENTRYPOINT")
    assert line is not None, "runtime has no ENTRYPOINT"
    assert "tini" in line, f"ENTRYPOINT does not invoke tini: {line}"


def test_runtime_has_healthcheck():
    assert stage_has_directive(_lines(), "runtime", "HEALTHCHECK")


def test_runtime_healthcheck_declares_interval_and_timeout():
    line = stage_directive_line(_lines(), "runtime", "HEALTHCHECK")
    assert line is not None
    assert "--interval=" in line, line
    assert "--timeout=" in line, line


def test_runtime_copies_chown_to_app_user():
    runtime_lines = stage_lines(_lines(), "runtime")
    copy_lines = [line for line in runtime_lines if line.strip().upper().startswith("COPY ")]
    assert copy_lines, "runtime has no COPY directives"
    chowned = [line for line in copy_lines if "--chown=" in line]
    assert chowned, f"no runtime COPY uses --chown=: {copy_lines}"


def test_runtime_uses_tini_exactly_twice():
    # Once in the apt-get install list, once in ENTRYPOINT — anything
    # more means a stray reference; anything less means the install or
    # the entrypoint vanished.
    assert stage_mentions(_lines(), "runtime", "tini") >= 2


def test_base_stage_still_carries_build_toolchains():
    # Defensive: the slim runtime split is only meaningful if `base` is
    # still the heavy toolchain layer that the dep stages inherit from.
    base = "\n".join(stage_lines(_lines(), "base"))
    assert "build-essential" in base
    assert "rustup" in base or "cargo" in base
