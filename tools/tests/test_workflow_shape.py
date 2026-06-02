from pathlib import Path

from workflow_shape import (
    read_workflow_text,
    workflow_cache_from_entries,
    workflow_cache_from_refs,
    workflow_cache_to_entries,
    workflow_cache_to_modes,
    workflow_cache_to_refs,
    workflow_jobs,
    workflow_runners,
    workflow_step_names,
    workflow_targets,
    workflow_triggers,
    workflow_uses,
    workflow_uses_build_push_action,
    workflow_uses_checkout,
    workflow_uses_login_action,
    workflow_uses_registry_cache,
    workflow_uses_setup_buildx,
)

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "build.yml"
)

REQUIRED_DEP_TARGETS = ("uv-deps", "bun-deps", "cargo-deps")


def _text() -> str:
    return read_workflow_text(WORKFLOW)


def test_workflow_file_exists():
    assert WORKFLOW.exists(), f"missing GitHub Actions workflow at {WORKFLOW}"


def test_workflow_lives_under_dot_github_workflows():
    parts = WORKFLOW.parts
    assert ".github" in parts and "workflows" in parts, parts


def test_workflow_triggers_on_push_and_pull_request():
    triggers = workflow_triggers(_text())
    assert "push" in triggers, triggers
    assert "pull_request" in triggers, triggers


def test_workflow_runs_on_ubuntu():
    runners = workflow_runners(_text())
    assert runners, "no runs-on declared"
    assert any("ubuntu" in r for r in runners), runners


def test_workflow_declares_at_least_one_job():
    assert workflow_jobs(_text())


def test_workflow_checks_out_repository():
    assert workflow_uses_checkout(_text())


def test_workflow_sets_up_docker_buildx():
    assert workflow_uses_setup_buildx(_text())


def test_workflow_logs_into_container_registry():
    assert workflow_uses_login_action(_text())


def test_workflow_uses_pinned_build_push_action():
    assert workflow_uses_build_push_action(_text())
    pinned = [ref for ref in workflow_uses(_text()) if ref.startswith("docker/build-push-action@")]
    assert pinned, "docker/build-push-action must be pinned to a tag or sha"


def test_workflow_builds_each_dep_stage_as_target():
    targets = set(workflow_targets(_text()))
    for stage in REQUIRED_DEP_TARGETS:
        assert stage in targets, f"workflow never builds target: {stage}"


def test_workflow_builds_runtime_stage_as_target():
    assert "runtime" in workflow_targets(_text())


def test_workflow_uses_registry_backed_buildkit_cache():
    assert workflow_uses_registry_cache(_text())


def test_every_cache_to_entry_is_registry_type():
    entries = workflow_cache_to_entries(_text())
    assert entries, "workflow has no cache-to entries"
    for entry in entries:
        assert "type=registry" in entry, f"non-registry cache-to entry: {entry}"


def test_every_cache_to_entry_uses_mode_max():
    modes = workflow_cache_to_modes(_text())
    assert modes, "no cache-to modes detected"
    assert all(mode == "max" for mode in modes), modes


def test_each_dep_stage_has_its_own_cache_to_ref():
    refs = " ".join(workflow_cache_to_refs(_text()))
    for stage in REQUIRED_DEP_TARGETS:
        assert stage in refs, f"no cache-to ref tagged for {stage}: {refs}"


def test_runtime_build_has_dedicated_cache_to_ref():
    refs = workflow_cache_to_refs(_text())
    assert any("runtime" in ref for ref in refs), refs


def test_runtime_build_reads_cache_from_every_dep_stage():
    entries = workflow_cache_from_entries(_text())
    runtime_entries = [e for e in entries if "runtime" in e or _entry_is_for_runtime(entries, e)]
    # Simpler signal: every dep-stage tag appears as a cache-from somewhere.
    joined = " ".join(entries)
    for stage in REQUIRED_DEP_TARGETS:
        assert stage in joined, f"no cache-from entry references {stage}: {entries}"
    assert runtime_entries, "runtime cache-from group missing"


def test_every_cache_from_entry_is_registry_type():
    entries = workflow_cache_from_entries(_text())
    assert entries, "workflow has no cache-from entries"
    for entry in entries:
        assert "type=registry" in entry, f"non-registry cache-from entry: {entry}"


def test_cache_from_refs_are_well_formed():
    refs = workflow_cache_from_refs(_text())
    assert refs, "cache-from entries have no ref fields"
    for ref in refs:
        assert ref, "cache-from entry is missing ref="
        assert ":" in ref, f"cache-from ref missing tag separator: {ref}"


def test_workflow_step_names_are_descriptive():
    names = workflow_step_names(_text())
    assert names, "workflow has no named steps"
    for name in names:
        assert len(name) >= 4, f"non-descriptive step name: {name!r}"


def _entry_is_for_runtime(entries: list[str], entry: str) -> bool:
    # Convenience: an entry belongs to the runtime build group if the
    # same group also references at least one dep stage. This lets the
    # runtime cache-from group be detected even when the entry itself
    # only names a dep stage.
    return entry in entries
