from dataclasses import dataclass

import pytest

from baseline import (
    BuildTiming,
    build_command,
    measure_baseline,
    measure_one,
    serialize_baseline,
    write_baseline,
)


@dataclass
class FakeCompleted:
    returncode: int


class FakeClock:
    def __init__(self, ticks):
        self._ticks = list(ticks)

    def __call__(self):
        return self._ticks.pop(0)


def test_build_command_cold_includes_no_cache():
    cmd = build_command("polyglot:naive", ".", no_cache=True)
    assert cmd[:4] == ["docker", "build", "--tag", "polyglot:naive"]
    assert "--no-cache" in cmd
    assert cmd[-1] == "."


def test_build_command_warm_skips_no_cache():
    cmd = build_command("polyglot:naive", ".", no_cache=False)
    assert "--no-cache" not in cmd
    assert cmd[-1] == "."


def test_measure_one_returns_elapsed_and_exit_code():
    clock = FakeClock([10.0, 12.5])

    def runner(_args):
        return FakeCompleted(returncode=0)

    timing = measure_one(["docker", "build", "."], runner, clock, "cold")
    assert timing == BuildTiming(label="cold", seconds=2.5, exit_code=0)


def test_measure_baseline_runs_cold_then_warm():
    captured: list[list[str]] = []

    def runner(args):
        captured.append(list(args))
        return FakeCompleted(returncode=0)

    clock = FakeClock([0.0, 30.0, 30.0, 35.0])
    timings = measure_baseline(
        "polyglot:naive",
        ".",
        runner=runner,
        timer=clock,
    )
    labels = [t.label for t in timings]
    assert labels == ["cold", "warm"]
    assert timings[0].seconds == pytest.approx(30.0)
    assert timings[1].seconds == pytest.approx(5.0)
    assert "--no-cache" in captured[0]
    assert "--no-cache" not in captured[1]


def test_measure_baseline_propagates_exit_codes():
    def runner(_args):
        return FakeCompleted(returncode=2)

    clock = FakeClock([0.0, 1.0, 1.0, 2.0])
    timings = measure_baseline("img", ".", runner=runner, timer=clock)
    assert timings[0].exit_code == 2
    assert timings[1].exit_code == 2


def test_serialize_baseline_round_trip():
    timings = [BuildTiming("cold", 30.0, 0), BuildTiming("warm", 5.0, 0)]
    text = serialize_baseline(timings)
    assert '"cold"' in text
    assert '"warm"' in text
    assert text.endswith("\n")


def test_write_baseline_writes_file(tmp_path):
    out = tmp_path / "baseline.json"
    timings = [BuildTiming("cold", 30.0, 0), BuildTiming("warm", 5.0, 0)]
    write_baseline(out, timings)
    text = out.read_text(encoding="utf-8")
    assert '"cold"' in text
    assert '"warm"' in text
