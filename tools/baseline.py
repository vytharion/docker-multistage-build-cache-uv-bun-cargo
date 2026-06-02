"""Measure the cold and warm Docker build baseline.

Cold  = ``docker build --no-cache`` (every layer rebuilt from scratch).
Warm  = a second ``docker build`` immediately afterwards, where the local
        layer cache is fully populated.

The module is split into small pure pieces so the timing logic can be
exercised under pytest without ever shelling out to docker.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class BuildTiming:
    label: str
    seconds: float
    exit_code: int


Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]
Timer = Callable[[], float]


def default_runner(args: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(args), check=False, capture_output=True, text=True)


def build_command(image_tag: str, context: str, *, no_cache: bool) -> list[str]:
    parts = ["docker", "build", "--tag", image_tag]
    if no_cache:
        parts.append("--no-cache")
    parts.append(str(context))
    return parts


def measure_one(
    command: Sequence[str],
    runner: Runner,
    timer: Timer,
    label: str,
) -> BuildTiming:
    start = timer()
    completed = runner(command)
    elapsed = timer() - start
    return BuildTiming(label=label, seconds=elapsed, exit_code=completed.returncode)


def measure_baseline(
    image_tag: str,
    context: str,
    *,
    runner: Runner = default_runner,
    timer: Timer = time.monotonic,
) -> list[BuildTiming]:
    cold_cmd = build_command(image_tag, context, no_cache=True)
    warm_cmd = build_command(image_tag, context, no_cache=False)
    cold = measure_one(cold_cmd, runner, timer, "cold")
    warm = measure_one(warm_cmd, runner, timer, "warm")
    return [cold, warm]


def serialize_baseline(timings: Iterable[BuildTiming]) -> str:
    payload = {"timings": [asdict(t) for t in timings]}
    return json.dumps(payload, indent=2) + "\n"


def write_baseline(path: str | Path, timings: Iterable[BuildTiming]) -> str:
    text = serialize_baseline(timings)
    Path(path).write_text(text, encoding="utf-8")
    return text


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the cold and warm Docker build baseline.",
    )
    parser.add_argument("--image", default="polyglot:naive")
    parser.add_argument("--context", default=".")
    parser.add_argument("--output", default="baseline.json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    timings = measure_baseline(args.image, args.context)
    write_baseline(args.output, timings)
    for timing in timings:
        print(f"{timing.label}: {timing.seconds:.2f}s (exit {timing.exit_code})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
