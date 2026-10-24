from copy import deepcopy

import pytest

from vmi.engine.attention import AttentionEngine
from vmi.engine.model import MatchModel
from vmi.engine.replay import Replay
from vmi.generator.scenarios import generate_scenario


def isolated_whistle(reason_delay=None):
    match = generate_scenario("handball")
    reason = next(e for e in match.events if e["type"] == "handball")
    whistle = next(e for e in match.events if e["id"] == reason["trigger_event_id"])
    match.events = [whistle]
    match.crowd = []
    match.match_state = []
    if reason_delay is not None:
        reason["delivered_t"] = whistle["delivered_t"] + reason_delay
        match.events.append(reason)
    return match, whistle


def banners(outputs):
    return [o for o in outputs if o["kind"] == "banner"]


def test_generic_wait_is_two_seconds_from_detection_at_fractional_deadline():
    match, whistle = isolated_whistle()
    replay = Replay(match)
    deadline = whistle["delivered_t"] + 2
    assert banners(replay.advance(deadline - 0.001)) == []
    shown = banners(replay.advance(deadline))
    assert len(shown) == 1 and shown[0]["type"] == "whistle"
    assert shown[0]["t_start"] == pytest.approx(deadline)
    assert shown[0]["t_end"] == pytest.approx(deadline + 3)


def test_reason_at_deadline_wins_without_generic_flash():
    match, whistle = isolated_whistle(2)
    shown = banners(Replay(match).advance(whistle["delivered_t"] + 2))
    assert [o["type"] for o in shown] == ["foul"]


def test_late_reason_enriches_one_cue_without_restarting_its_lifetime():
    match, whistle = isolated_whistle(2.5)
    shown = banners(Replay(match).advance(whistle["delivered_t"] + 3))
    assert [o["type"] for o in shown] == ["whistle", "foul"]
    assert shown[0]["cue_id"] == shown[1]["cue_id"] and shown[1]["update"]
    assert shown[0]["t_start"] == shown[1]["t_start"]
    assert shown[0]["t_end"] == shown[1]["t_end"]


def test_drinks_break_is_a_three_second_marker_and_keeps_the_ball_stopped():
    match = generate_scenario("drinks_break")
    event = next(e for e in match.events if e["type"] == "drinks_break")
    replay = Replay(match)
    shown = [o for o in banners(replay.advance(event["delivered_t"])) if o["type"] == "drinks_break"]
    assert len(shown) == 1
    assert shown[0]["t_start"] == event["delivered_t"]
    assert shown[0]["t_end"] - shown[0]["t_start"] == 3
    replay.advance(event["delivered_t"] + 4)
    assert not replay.model.ball_in_play


@pytest.mark.parametrize("name", ["shots_reversed", "penalty_late_card", "dribble_complete", "drinks_break"])
def test_only_approved_marker_types_share_one_slot(name):
    match = generate_scenario(name)
    shown = banners(Replay(match).advance(match.duration))
    assert shown
    allowed = {"whistle", "foul", "offside", "penalty", "stoppage", "kick_off", "half_time", "full_time", "drinks_break"}
    for cue in shown:
        assert cue["type"] in allowed and cue["slot"] == "event"
        assert cue["t_end"] - cue["t_start"] == pytest.approx(4 if cue["type"] in {"penalty", "half_time", "full_time"} else 3)


def test_crowd_jump_does_not_create_a_screen_banner():
    match = generate_scenario("carry")
    engine = AttentionEngine(MatchModel(deepcopy(match.meta)))
    engine.model.crowd.extend([(0, 0.1), (1, 0.9)])
    assert not banners(engine.tick(1))


@pytest.mark.parametrize("corrected,expected", [(False, "penalty"), (True, "foul")])
def test_reason_before_audio_uses_the_current_explicit_decision(corrected, expected):
    match = generate_scenario("penalty_no_card")
    reason = next(e for e in match.events if e["type"] == "referee_decision" and e["decision"] == "penalty")
    whistle = next(e for e in match.events if e["id"] == reason["whistle_id"])
    source_ids = {reason["trigger_event_id"], reason["stoppage_id"]}
    engine = AttentionEngine(MatchModel(match.meta))
    for e in match.events:
        if e["id"] in source_ids:
            engine.ingest(e, max(20, e["delivered_t"]))
    engine.ingest(reason, 21)
    correction = {**reason, "id": "correction", "t": reason["t"] + 1,
                  "delivered_t": reason["t"] + 2, "decision": "free_kick",
                  "supersedes_decision_id": reason["id"]}
    if corrected:
        engine.ingest(correction, 22)
    shown = banners(engine.ingest(whistle, 23))
    assert [o["type"] for o in shown] == [expected]
    assert shown[0]["evidence"] == [whistle["id"], "correction" if corrected else reason["id"]]
