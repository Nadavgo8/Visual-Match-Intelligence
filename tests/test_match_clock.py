"""The scorebug advances on simulation time, including dead-ball intervals."""

import pytest

from vmi.engine.model import MatchModel
from vmi.engine.match_clock import MatchClock
from vmi.generator.scenarios import generate_scenario


@pytest.fixture
def model():
    return MatchModel(generate_scenario("carry").meta)


def boundary(model, kind, t, period=1, clock="0:00", eid=None):
    model.ingest({"schema_version": "2.0", "id": eid or f"{kind}-{period}",
                  "match_id": model.meta["match_id"], "source": "event_feed",
                  "type": kind, "t": t, "delivered_t": t,
                  "period": period, "clock": clock, "team": None, "player_id": None,
                  kind: {"period_no": period}})


@pytest.mark.parametrize("in_play", [True, False])
def test_score_clock_advances_without_new_football_events(model, in_play):
    boundary(model, "period_start", 0)
    model.ball_in_play = in_play
    model.tick(17)
    assert model.clock == "0:17"
    model.tick(65)
    assert model.clock == "1:05"


def test_clock_read_uses_snapshot_time_between_possession_ticks(model):
    boundary(model, "period_start", 0)
    model.t = 12.75
    assert model.clock == "0:12"


def test_half_time_freezes_only_after_delivered_period_end(model):
    boundary(model, "period_start", 0)
    model.tick(2770)
    assert model.clock == "45+2'"
    boundary(model, "period_end", 2770, clock="45+2'")
    model.tick(3000)
    assert model.clock == "45+2'"
    boundary(model, "period_start", 3000, period=2, clock="45:00")
    model.tick(3017)
    assert model.clock == "45:17"


def test_a_late_old_period_end_cannot_freeze_second_half(model):
    boundary(model, "period_start", 0)
    boundary(model, "period_start", 3000, period=2, clock="45:00")
    boundary(model, "period_end", 2770, clock="45+2'")
    model.tick(3017)
    assert model.clock == "45:17"


@pytest.mark.parametrize("elapsed,expected", [(2699.999,"44:59"), (2700,"45:00"),
                                            (2700.001,"45+1'"), (2759.999,"45+1'"),
                                            (2760,"45+2'")])
def test_clock_preserves_generator_added_time_notation(model, elapsed, expected):
    boundary(model, "period_start", 10.25)
    model.t = 10.25 + elapsed
    assert model.clock == expected


def test_full_time_freezes_after_second_half_end(model):
    boundary(model, "period_start", 3000, period=2, clock="45:00")
    boundary(model, "period_end", 5760, period=2, clock="90+2'")
    model.tick(6000)
    assert model.clock == "90+2'"
    assert model.finished


def test_period_end_delivered_before_its_start_still_freezes(model):
    boundary(model, "period_end", 2770, clock="45+2'")
    boundary(model, "period_start", 0)
    model.tick(3000)
    assert model.clock == "45+2'"


def test_late_origin_does_not_roll_back_the_latest_observed_period():
    clock = MatchClock()
    clock.observe({"t": 3001, "period": 2, "clock": "45:01"})
    assert clock.read(3010) == "45:01"  # No trustworthy origin delivered yet.
    clock.observe({"type": "period_start", "t": 3000, "period": 2, "clock": "45:00"})
    assert clock.read(3010) == "45:10"
    clock.observe({"type": "period_start", "t": 0, "period": 1, "clock": "0:00"})
    assert clock.read(3011) == "45:11"


def test_duplicate_start_cannot_unfreeze_a_delivered_period_end():
    clock = MatchClock()
    start = {"type": "period_start", "t": 0, "period": 1, "clock": "0:00"}
    clock.observe(start)
    clock.observe({"type": "period_end", "t": 2770, "period": 1, "clock": "45+2'"})
    clock.observe(start)
    clock.observe({"type": "period_end", "t": 2772, "period": 1, "clock": "45+2'"})
    assert clock.read(3000) == "45+2'"
    assert clock.end == 2770


def test_analytics_availability_never_overrides_clock_and_event_labels_are_immutable():
    clock = MatchClock()
    start = {"type": "period_start", "t": 0, "period": 1, "clock": "0:00"}
    clock.observe(start)
    clock.observe({"type": "shot_xg", "t": 3000, "period": 1, "clock": "0:02"})
    assert clock.read(12) == "0:12"
    assert start["clock"] == "0:00"
    assert clock.last_t == 0


def test_next_period_state_before_its_origin_uses_reported_time():
    clock = MatchClock()
    clock.observe({"type": "period_start", "t": 0, "period": 1, "clock": "0:00"})
    clock.observe({"t": 3010, "period": 2, "clock": "45:10"})
    assert clock.read(3015) == "45:10"
    clock.observe({"type": "period_start", "t": 3000, "period": 2, "clock": "45:00"})
    assert clock.read(3015) == "45:15"


def test_observation_without_clock_preserves_label_until_origin_is_known():
    clock = MatchClock()
    clock.observe({"t": 12, "period": 1, "clock": "0:12"})
    clock.observe({"t": 13})
    assert clock.read(20) == "0:12"


def test_repeated_read_and_paused_snapshot_never_use_wall_time(model):
    boundary(model, "period_start", 0)
    model.tick(65.75)
    for _ in range(100):
        assert model.clock == "1:05"


def test_no_read_can_go_back_before_the_latest_delivered_record():
    clock = MatchClock()
    clock.observe({"type": "period_start", "t": 0, "period": 1, "clock": "0:00"})
    clock.observe({"t": 12, "period": 1, "clock": "0:12"})
    assert clock.read(0) == "0:12"
