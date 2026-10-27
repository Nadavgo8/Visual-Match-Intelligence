"""The demo match is a fixed story for the video, the judges' link and the pitch.

If a generator change alters any of these moments, this test fails before it reaches main.
Changing the demo story on purpose means updating this test and the demo script together.
"""

import os
import pytest

from vmi.generator.scenarios import generate_demo_match

DEMO_STORY = {
    "generator_version": "2.5.0",
    "final": {"home": 2, "away": 1},
    # Original agreed story: the physical demo scenario must satisfy these times.
    "goals": [("37:58", "home", "Dumont"), ("43:34", "home", "Ferreira"), ("65:08", "away", "Marsh")],
    "var": [("37:16", "penalty", "no_penalty", "overturned"), ("66:38", "goal", "goal", "stands")],
    "cancelled_goals": [],
}


def demo_moments(seed: int, match=None) -> dict:
    m = match if match is not None else generate_demo_match(seed)
    names = {p["id"]: p["name"] for side in m.meta["teams"].values() for p in side["players"]}
    by_id = {e["id"]: e for e in m.events}
    corrections = [e for e in m.events if e["type"] == "goal_cancelled"]
    cancelled_ids = {e["result_id"] for e in corrections}
    for correction in corrections:
        result = by_id[correction["result_id"]]
        assert result["type"] == "shot_result" and result["outcome"] == "goal"
        assert correction["shot_id"] == result["shot_id"]
        assert by_id[correction["decision_id"]]["type"] == "referee_decision"
    counted = {
        side: sum(
            e["type"] == "shot_result" and e["outcome"] == "goal" and e["id"] not in cancelled_ids and e["team"] == side
            for e in m.events
        )
        for side in ("home", "away")
    }
    assert counted == m.meta["final_score"]
    return {
        "generator_version": m.meta["generator_version"],
        "final": m.meta["final_score"],
        "goals": [
            (e["clock"], e["team"], names[e["player_id"]])
            for e in m.events
            if e["type"] == "shot_result" and e["outcome"] == "goal"
        ],
        "var": [
            (e["clock"], e["var"]["incident"], e["var"]["original_decision"], e["var"]["outcome"])
            for e in m.events
            if e["type"] == "var" and e["var"]["phase"] == "decision"
        ],
        "cancelled_goals": [
            (by_id[e["result_id"]]["clock"], e["team"], names[e["player_id"]], e["clock"]) for e in corrections
        ],
    }


def test_demo_seed_defaults_to_2():
    from vmi.api import server

    assert os.getenv("VMI_DEMO_SEED") is None or server.DEMO_SEED == int(os.environ["VMI_DEMO_SEED"])
    if os.getenv("VMI_DEMO_SEED") is None:
        assert server.DEMO_SEED == 2


@pytest.fixture(scope="module")
def physical_demo():
    return generate_demo_match(2)


def test_demo_match_keeps_its_story(physical_demo):
    assert demo_moments(2, physical_demo) == DEMO_STORY


def test_explicit_demo_rejects_an_ambiguous_other_seed():
    with pytest.raises(ValueError, match="seed 2"):
        generate_demo_match(12)


def test_api_dispatch_uses_the_same_declared_demo_independently_of_default_seed(monkeypatch):
    from vmi.api import server

    monkeypatch.setattr(server, "_match_cache", {})
    monkeypatch.setattr(server, "DEMO_SEED", 12)
    demo, generic = object(), object()
    calls = []
    monkeypatch.setattr(server, "generate_demo_match", lambda seed: calls.append(("demo", seed)) or demo)
    monkeypatch.setattr(server, "generate_match", lambda seed: calls.append(("seeded", seed)) or generic)
    assert server.get_match(2) is demo and server.get_match(12) is generic
    assert server.get_match(2) is demo
    assert calls == [("demo", 2), ("seeded", 12)]


def test_explicit_demo_room_starts_at_natural_speed_with_presenter_acceleration_available(monkeypatch, physical_demo):
    from vmi.api import server

    monkeypatch.setattr(server, "get_match", lambda seed: physical_demo)
    room = server.Room("physical-demo-speed", 2)
    assert room.speed == room.state("tv")["speed"] == 1
    assert server.Room("generic-speed", 12).speed == 4


def test_demo_deadline_rejects_retiming_an_action_into_the_past():
    from vmi.generator.scenarios import _PhysicalDemo

    sim = _PhysicalDemo()
    assert not hasattr(sim, "name")
    sim.key("home", 52.5, 34, None, False)
    sim.at(5)
    with pytest.raises(ValueError, match="deadline"):
        sim.at(4)
    assert sim.t == 5


def test_one_scripted_header_has_real_onside_pass_head_contact_flight_and_result():
    import math
    from vmi.generator.scenarios import _PhysicalDemo
    from vmi.generator.tracking import Tracker

    sim = _PhysicalDemo()
    passer, scorer = sim.player("home",8), sim.player("home",7)
    sim.key("home",78,30,passer)
    setup = sim.onside_setup("home",scorer,94,30)
    passing = sim.pass_to("home",scorer,94,30,kick_at=10,duration=2.5,header=True,setup=setup)
    shot = sim.goal("home",scorer,13.4,preparation=passing)
    match = sim.export_match()
    tracker = Tracker(match)
    kick = tracker.frame(passing["t"])
    rx = next(p["x"] for p in kick["players"] if p["id"] == scorer.id)
    opponents = sorted((p["x"] for p in kick["players"] if p["team"] == "away"),reverse=True)
    assert rx < opponents[1]-1
    contact = tracker.frame(shot["t"])
    player = next(p for p in contact["players"] if p["id"] == scorer.id)
    assert player["contact"]["effector"] == "head" and contact["ball_height"] == 1.65
    assert math.dist([player["x"],player["y"]],contact["ball"]) == pytest.approx(.55,abs=.015)
    result = next(e for e in match.events if e["type"] == "shot_result")
    assert result["t"] == 13.4 and result["t"]-shot["t"] == pytest.approx(.6)
    assert tracker.frame(result["t"])["ball"][0] > 105 and not tracker.frame(result["t"])["ball_in_play"]
    assert sim.score == {"home":1,"away":0}


def test_called_foul_stop_preserves_both_actor_roots_through_the_whistle_and_exit(physical_demo):
    import math
    from vmi.generator.tracking import Tracker

    foul = next(e for e in physical_demo.events if e["type"] == "foul")
    tracker = Tracker(physical_demo)
    for i in range(-50, 101):
        frame = tracker.frame(foul["t"] + i/50)
        actors = {p["id"]: (p["x"], p["y"]) for p in frame["players"]}
        assert math.dist(actors[foul["foul"]["victim_id"]], actors[foul["player_id"]]) >= .7


def test_demo_penalty_kicker_is_behind_the_ball_facing_goal_and_keeper_reacts(physical_demo):
    import math
    from vmi.generator.tracking import Tracker

    shot = next(e for e in physical_demo.events if e["type"] == "shot" and e["shot"]["penalty"])
    tracker = Tracker(physical_demo)
    frame = tracker.frame(shot["t"])
    players = {p["id"]: p for p in frame["players"]}
    taker = players[shot["player_id"]]
    assert (taker["x"], taker["y"]) == pytest.approx((93.45, 34), abs=.01)
    assert taker["motion"]["facing"] == pytest.approx(math.pi/2)
    assert taker["contact"]["heading"] == pytest.approx(math.pi/2)
    keeper = next(p for p in frame["players"] if p["team"] == "away" and p["role"] == "GK")
    later = next(p for p in tracker.frame(shot["t"]+.6)["players"] if p["id"] == keeper["id"])
    assert math.dist((keeper["x"],keeper["y"]), (later["x"],later["y"])) >= .25
    assert later["motion"]["facing"] == pytest.approx(-math.pi/2)
    assert "contact" not in later  # unsuccessful reaction must not fabricate a save


def test_demo_initial_metadata_does_not_disclose_episode_schedule_or_final_score(physical_demo):
    from vmi.generator.export import initial_metadata

    meta = initial_metadata(physical_demo.meta)
    assert "demo_windows" not in meta and "final_score" not in meta
    assert meta["configuration"] == {"mode": "scripted_demo", "revision": "original-v1"}


def test_demo_offside_is_eligible_at_the_kick_and_has_an_actual_touch_before_call(physical_demo):
    from vmi.generator.tracking import Tracker

    call = next(e for e in physical_demo.events if e["type"] == "offside")
    passing = next(e for e in physical_demo.events if e["id"] in call["related"] and e["type"] == "pass")
    tracker = Tracker(physical_demo)
    kick = tracker.frame(passing["t"])
    receiver = next(p for p in kick["players"] if p["id"] == passing["pass"]["recipient_id"])
    opponents = sorted((p["x"] for p in kick["players"] if p["team"] != passing["team"]), reverse=True)
    assert receiver["x"] > max(52.5, kick["ball"][0], opponents[1]) + 1
    touch = next(k for k in physical_demo.keyframes if passing["t"] < k.t < call["t"] and k.holder == receiver["id"])
    frame = tracker.frame(touch.t)
    assert frame["possession"]["holder_id"] == receiver["id"]
    assert frame["ball"] == passing["pass"]["end_location"]
    assert passing["delivered_t"] >= call["t"]


def test_demo_has_an_opening_sequence_and_active_420_second_momentum_history(physical_demo):
    opening_end = physical_demo.meta["demo_windows"]["opening"][1]
    opening = [e for e in physical_demo.events if 0 <= e["t"] <= opening_end]
    assert sum(e["type"] == "pass" for e in opening) >= 2
    assert sum(e["type"] == "carry" for e in opening) >= 2
    history = [e for e in physical_demo.events if 1250 <= e["t"] <= 1670]
    assert sum(e["type"] == "pass" for e in history) >= 16
    assert sum(e["type"] == "carry" for e in history) >= 16
    assert len({e["player_id"] for e in history if e["type"] in {"pass", "carry"}}) >= 3
