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
            assert by[ev["trigger_event_id"]]["type"] in {"foul", "handball"}
    for ev in match.events:
        if ev["type"] == "shot":
            assert ev["play_context"] in {"open_play", "corner", "penalty", "free_kick", "kick_off", "throw_in", "goal_kick"}


def test_penalty_execution_and_its_whistle_have_same_clock():
    from vmi.generator.match import _Sim
    sim=_Sim(12,"penalty-clock")
    sim.t=120
    sim.penalty("home")
    action=next(e for e in sim.events if e["type"]=="set_piece" and e["set_piece"]["kind"]=="penalty")
    whistle=next(e for e in sim.events if e["type"]=="whistle" and e["t"]==action["t"])
    assert action["clock"]==whistle["clock"]=="2:01"


@pytest.mark.parametrize("kind", ["kick_off", "throw_in", "goal_kick", "free_kick"])
def test_restart_releases_ball_to_another_player_before_open_play(kind):
    from vmi.generator.match import _Sim
    sim = _Sim(12, "restart-contact")
    sim.emit("period_start", period_no=1)
    sim.t = 10
    if kind == "kick_off":
        sim.kick_off("home")
    elif kind == "throw_in":
        sim.throw_in("home", 60, 0)
    elif kind == "goal_kick":
        sim.goal_kick("home")
    else:
        sim.restart_free_kick("home", 60, 34)
    action = next(e for e in sim.events if e["type"] == "set_piece")
    assert sim.carrier[1].id != action["player_id"]
    tr = Tracker(sim.export_match())
    release = tr.frame(action["t"] + .05)
    assert release["ball_in_play"] and release["possession"]["holder_id"] is None
    arrival = tr.frame(sim.t)
    assert arrival["possession"]["holder_id"] == sim.carrier[1].id
    if kind == "throw_in":
        assert release["ball_height"] > 0


def test_full_match_source_positions_are_continuous_through_touch_and_half_time(match):
    tr = Tracker(match)
    # Look across every source knot, including the half-time side change.
    for knot in match.keyframes:
        if knot.t < .05:
            continue
        a, b = tr.frame(knot.t - .05), tr.frame(knot.t)
        before = {p["id"]: p for p in a["players"]}
        for p in b["players"]:
            if p["id"] in before:
                q = before[p["id"]]
                assert math.dist((p["x"], p["y"]), (q["x"], q["y"])) <= .47, (knot.t, p["id"])


def test_restart_ball_is_set_before_execution_and_does_not_drift_during_the_wait():
    from vmi.generator.match import _Sim
    sim = _Sim(12, "restart-setup")
    sim.key("home", 105.5, 25, None, False)
    sim.stoppage(20)
    sim.goal_kick("away")
    action = next(e for e in sim.events if e["type"] == "set_piece")
    tr = Tracker(sim.export_match())
    a, b = tr.frame(action["t"] - 1), tr.frame(action["t"] - .1)
    assert a["ball"] == b["ball"]
    assert not a["ball_in_play"] and not b["ball_in_play"]


def test_source_motion_is_exactly_the_same_after_reverse_seek_or_a_fresh_tracker(match):
    tr = Tracker(match)
    expected = tr.frame(137.125)
    assert all(set(p["motion"]) == {"speed", "heading", "distance"} for p in expected["players"])
    assert all(0 <= p["motion"]["speed"] <= 9.00001 for p in expected["players"])
    tr.frame(match.duration)
    tr.frame(0)
    assert tr.frame(137.125) == expected == Tracker(match).frame(137.125)


@pytest.mark.parametrize("motion", [{"heading": 0, "speed": -1, "distance": 1},
                                    {"heading": float("nan"), "speed": 0, "distance": 1},
                                    {"heading": 0, "speed": 0},
                                    {"heading": 4, "speed": 0, "distance": 1}])
def test_invalid_optional_source_motion_is_rejected(motion):
    from vmi.contracts import validate_record
    frame = {"schema_version": "2.0", "stream": "tracking", "match_id": "m", "t": 0,
             "players": [{"motion": motion}]}
    with pytest.raises(ValueError, match="source player motion"):
        validate_record(frame, "m")


def test_corner_cross_is_emitted_at_release_and_is_airborne_before_contact():
    from vmi.generator.match import _Sim
    sim = _Sim(12, "corner-flight")
    sim.t = 10
    sim.corner("home", 105, 0)
    action = next(e for e in sim.events if e["type"] == "set_piece")
    cross = next(e for e in sim.events if e["type"] == "pass")
    assert cross["t"] == action["t"]
    tr = Tracker(sim.export_match())
    frame = tr.frame(cross["t"] + .3)
    assert frame["ball_height"] > .5 and frame["possession"]["holder_id"] is None
    assert math.dist(cross["location"], frame["ball"]) > 1


@pytest.mark.parametrize("seed", [3, 8, 15, 20])
def test_carry_turnover_and_second_ball_contacts_are_reachable_from_the_previous_touch(seed):
    match = generate_match(seed)
    for a, b in zip(match.keyframes, match.keyframes[1:]):
        if b.t <= a.t:
            continue
        for pid, start in a.player_positions.items():
            assert math.dist(start, b.player_positions[pid]) <= 9 * (b.t - a.t) + 1e-5


def test_post_rebound_stays_live_and_is_recovered_without_a_goal_kick():
    import random
    from vmi.generator.match import _Sim
    class PostDraw(random.Random):
        def random(self):
            return .56
    sim = _Sim(12, "post-rebound")
    sim.t = 10
    holder = next(p for p in sim.on_pitch["home"] if p.position == "ST")
    sim.ball_in_play = True
    sim.key("home", 94, 34, holder)
    sim.rng = PostDraw(1)
    sim.true_chance = lambda *args: 0
    sim.shot("home", holder, 94, 34, None)
    result = next(e for e in sim.events if e["type"] == "shot_result")
    assert result["outcome"] == "post"
    assert not any(e["type"] == "set_piece" for e in sim.events)
    assert any(e["type"] == "ball_recovery" for e in sim.events)
    tr = Tracker(sim.export_match())
    assert tr.frame(result["t"] + .1)["ball_in_play"]
    assert tr.frame(sim.t)["possession"]["holder_id"] == sim.carrier[1].id


def test_source_distance_and_velocity_are_metric_segment_values(match):
    meta = dict(match.meta, motion_model="source-paths-1")
    fixture = Match(meta, keyframes=[
        Keyframe(0, 20, 30, "H9", True, player_positions={"H9": (20, 30)}),
        Keyframe(2, 26, 38, "H9", True, player_positions={"H9": (26, 38)}),
        Keyframe(3, 26, 38, "H9", True, player_positions={"H9": (26, 38)}),
    ])
    tracker = Tracker(fixture)
    player = next(p for p in tracker.frame(1)["players"] if p["id"] == "H9")
    assert player["motion"]["speed"] == 5
    assert player["motion"]["distance"] == 5
    assert player["motion"]["heading"] == pytest.approx(math.atan2(6, -8))
    stopped = next(p for p in tracker.frame(2.5)["players"] if p["id"] == "H9")
    assert stopped["motion"]["speed"] == 0 and stopped["motion"]["distance"] == 10
    assert stopped["motion"]["heading"] == player["motion"]["heading"]


def test_impossible_contacts_are_rejected_instead_of_hiding_a_teleport(match):
    from vmi.generator.motion import stage_players
    fixture = Match(match.meta, keyframes=[Keyframe(0, 20, 30, "H9", True),
                                          Keyframe(1, 40, 30, "H9", True)])
    with pytest.raises(ValueError, match="unreachable source contact: H9"):
        stage_players(fixture)


def test_support_targets_change_with_possession_and_mirror_with_playing_direction():
    from vmi.generator.motion import support_position
    winger = {"id": "H7", "team": "home", "base_x": 62, "base_y": 12, "position": "RW"}
    attacking = support_position(winger, True, (80, 20), 10, "home")
    defending = support_position(winger, True, (80, 20), 10, "away")
    assert abs(attacking[1] - 34) > abs(defending[1] - 34)
    opposite = support_position(winger, False, (25, 48), 10, "home")
    assert opposite == pytest.approx((105 - attacking[0], 68 - attacking[1]))


def test_initial_roster_does_not_disclose_a_substitutes_future_occupied_slot():
    from vmi.generator.export import initial_metadata
    from vmi.generator.match import _Sim
    sim = _Sim(12, "initial-bases")
    outgoing = next(p for p in sim.on_pitch["home"] if p.position == "LB")
    incoming = sim.bench["home"][0]
    initial_slot = (incoming.base_x, incoming.base_y)
    sim.substitute("home", "tactical", off=outgoing)
    match = sim.export_match()
    roster = initial_metadata(match.meta)["teams"]["home"]["players"]
    public = next(p for p in roster if p["id"] == incoming.id)
    assert (public["base_x"], public["base_y"]) == initial_slot == (0, 0)
    # Truth/tracking still inherit the actual occupied slot after the sub.
    tracker = Tracker(match)
    assert tracker.base[incoming.id] == (outgoing.base_x, outgoing.base_y)
    assert outgoing.id in tracker.lineup("home", 0)
    changed = next(e for e in match.events if e["type"] == "substitution")
    assert incoming.id in tracker.lineup("home", changed["t"])
