"""Reproduction must survive other matches and non-monotonic playback."""

from dataclasses import asdict

import pytest

from vmi.generator.match import generate_match
from vmi.generator.tracking import Tracker


@pytest.mark.parametrize("seed", [3, 12, 17])
def test_match_reproduction_is_isolated_from_other_runs(seed):
    first = generate_match(seed)
    expected = asdict(first)
    generate_match(seed + 100)
    reproduced = generate_match(seed)
    assert asdict(reproduced) == expected
    assert asdict(first) == expected


def test_tracking_seek_is_independent_of_previous_frame_requests():
    match = generate_match(12)
    tracker = Tracker(match)
    times = [0.0, 100.05, 1000.0, match.duration]
    expected = {t: Tracker(match).frame(t) for t in times}
    for t in reversed(times):
        assert tracker.frame(t) == expected[t]
    for t in times:
        assert tracker.frame(t) == expected[t]


def test_tracking_requests_do_not_mutate_generated_match():
    match = generate_match(12)
    expected = asdict(match)
    tracker = Tracker(match)
    for t in [match.duration, 0.0, 2700.0, 100.05]:
        tracker.frame(t)
    assert asdict(match) == expected
