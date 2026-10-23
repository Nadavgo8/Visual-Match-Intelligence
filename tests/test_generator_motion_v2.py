import math

import pytest

from vmi.generator.match import Match, generate_match
from vmi.generator.motion import Keyframe
from vmi.generator.tracking import Tracker


@pytest.fixture(scope="module")
def match():
    return generate_match(12)


def test_ball_flight_height_continuity_and_control_boundaries(match):
    # One explicit pass; expected positions are calculated independently.
    fixture = Match(match.meta, keyframes=[
        Keyframe(10, 20, 30, "H9", True, flight_height=3, possession_id="p1"),
        Keyframe(12, 40, 50, "H10", True, possession_id="p1"),
        Keyframe(14, 40, 50, None, False),
    ])
    tr = Tracker(fixture)
    start, middle, end = [tr.frame(t) for t in (10, 11, 12)]
    assert start["ball"] == [20, 30] and start["ball_height"] == 0
    assert middle["ball"] == [30, 40] and middle["ball_height"] == 3
    assert middle["possession"]["holder_id"] is None
    assert end["ball"] == [40, 50] and end["ball_height"] == 0
    assert end["possession"]["holder_id"] == "H10"
    assert tr.frame(14)["possession"]["status"] == "stopped"
    assert not tr.frame(14)["ball_in_play"]
    assert math.dist(tr.frame(11.999)["ball"], end["ball"]) < 0.03
    assert tr.frame(11) == middle  # reverse seek is stateless


def test_controlled_ball_matches_active_holder_and_quality(match):
    tr = Tracker(match)
    for k in match.keyframes[::11]:
        frame = tr.frame(k.t)
        assert frame["quality"]["sample_t"] == frame["t"]
        assert frame["ball_height"] >= 0
        holder = frame["possession"]["holder_id"]
        if holder:
            player = next(p for p in frame["players"] if p["id"] == holder)
            assert math.dist(frame["ball"], [player["x"], player["y"]]) < 0.02
            assert frame["possession"]["id"] is not None


def test_all_restarts_link_to_stop_award_and_execution(match):
    by = {e["id"]: e for e in match.events}
    for ev in match.events:
        if ev["type"] == "restart_taken":
            award = by[ev["restart_id"]]
            stop = by[ev["stoppage_id"]]
            action = by[ev["action_event_id"]]
            assert award["type"] == "restart_awarded"
            assert stop["type"] == "play_stopped"
            assert by[stop["trigger_event_id"]]
            assert award["stoppage_id"] == stop["id"]
            assert stop["t"] <= award["t"] <= ev["t"]
            assert action["restart_id"] == award["id"]
            assert action["team"] == award["team"] == ev["team"]
        elif ev["type"] == "referee_decision" and ev["decision"] == "penalty":
            assert by[ev["trigger_event_id"]]["type"] == "foul"
    for ev in match.events:
        if ev["type"] == "shot":
            assert ev["play_context"] in {"open_play", "corner", "penalty", "free_kick", "kick_off", "throw_in", "goal_kick"}
