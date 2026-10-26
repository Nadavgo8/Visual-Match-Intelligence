"""The Attention Engine routes correctly and derives what the feed doesn't say."""

import pytest
import random

from vmi.engine.attention import visible_to
from vmi.engine.model import momentum_from_counts
from vmi.engine.replay import run_all
from vmi.generator.match import generate_match
from vmi.generator.scenarios import _Segment


@pytest.fixture(scope="module")
def demo():
    m = generate_match(12)
    return m, list(run_all(m))


def test_momentum_worked_example_from_spec():
    idx, val = momentum_from_counts(0.70, 3, 0, 2, 1)
    assert round(idx, 2) == 0.70 and round(val, 2) == 0.40


def test_kick_off_banner_per_half_and_goal(demo):
    m, outs = demo
    goals = sum(m.meta["final_score"].values())
    kick = [o for o in outs if o["kind"] == "banner" and o["type"] == "kick_off"]
    assert len(kick) == 2 + goals


def test_half_and_full_time_banners(demo):
    _, outs = demo
    types = [o["type"] for o in outs if o["kind"] == "banner"]
    assert types.count("half_time") == 1 and types.count("full_time") == 1


def test_overturned_penalty_is_detected_from_the_feed():
    class ReviewOverturns(random.Random):
        def random(self):
            return .01

    # This feed/VAR regression deliberately places a challenge in the box.
    # Use the existing scripted setup-cut fixture, not a continuous full match.
    sim = _Segment(12, "reviewed-penalty-regression")
    victim = next(p for p in sim.on_pitch["home"] if p.position == "ST")
    fouler = sim.opp_nearest("home", 94, 34)
    sim.key("home", 94, 34, victim)
    sim.rng = ReviewOverturns(0)
    assert sim.missed_box_foul("home", victim, fouler, 94, 34, "trip")
    outs = list(run_all(sim.finish()))
    assert any(o["kind"] == "banner" and o["type"] == "penalty" for o in outs)
    a = next(o for o in outs if o["kind"] == "analysis" and o["moment"] == "var_check")
    chk = next(f for f in a["factpack"]["facts"] if f["type"] == "var_check")
    ch = next(f for f in a["factpack"]["facts"] if f["type"] == "challenge")
    assert chk["referee_did_not_give"] and ch["inside_box"]


def test_var_stays_off_the_screen(demo):
    _, outs = demo
    banners = [o for o in outs if o["kind"] == "banner"]
    assert not any("VAR" in f"{o['label']} {o['detail'] or ''}" for o in banners)


def test_most_whistles_are_explained(demo):
    _, outs = demo
    banners = [o for o in outs if o["kind"] == "banner"]
    updated = {o["cue_id"] for o in banners if o["update"]}
    generic = [o for o in banners if o["type"] == "whistle" and o["cue_id"] not in updated]
    assert len(generic) <= 3


def test_banners_have_fixed_slots(demo):
    _, outs = demo
    slots = {}
    for o in outs:
        if o["kind"] == "banner" and o["type"] != "whistle":
            slots.setdefault(o["type"], set()).add(o["slot"])
    assert all(len(s) == 1 for s in slots.values())


def test_routine_play_is_left_out(demo):
    _, outs = demo
    skipped = [o for o in outs if o["kind"] == "skip"]
    shown = [o for o in outs if o["kind"] in ("banner", "feed", "analysis")]
    assert len(skipped) > 10 * len(shown)


def test_analysis_only_while_ball_is_dead(demo):
    _, outs = demo
    for o in outs:
        if o["kind"] == "analysis" and o["moment"] not in ("half_time", "full_time"):
            assert o["tier"] in (1, 2, 3)


def test_profile_filter():
    assert visible_to({"kind": "feed", "tier": 1}, "big")
    assert not visible_to({"kind": "feed", "tier": 2}, "big")
    assert visible_to({"kind": "feed", "tier": 3}, "everything")
    assert visible_to({"kind": "banner"}, "big")


def test_replay_meters_clock_advances_between_events_and_rebuilds_on_seek():
    from vmi.engine.replay import Replay

    match = generate_match(12)
    replay = Replay(match)
    for target, expected in [(12, "0:12"), (20, "0:20"), (21, "0:21")]:
        meters = [o for o in replay.advance(target) if o["kind"] == "meters"]
        assert meters[-1]["clock"] == expected
        assert replay.model.clock == expected
    rebuilt = Replay(match)
    rebuilt.advance(21)
    assert rebuilt.model.clock == replay.model.clock


def test_atmosphere_reports_components_and_availability_without_emotion(demo):
    _, outs = demo
    meters = [o["atmosphere"] for o in outs if o["kind"] == "meters"]
    assert meters and all("mood" not in a for a in meters)
    assert all(a["mode"] == "combined" for a in meters)
    assert all(0 <= a["level"] <= 1 for a in meters if a["available"])
    assert all(a["level"] is None for a in meters if not a["available"])


@pytest.mark.parametrize("target", [float("nan"), float("inf"), -1, True, "2"])
def test_invalid_replay_targets_fail_before_processing_any_input(target, monkeypatch):
    from vmi.engine.replay import Replay
    from vmi.generator.scenarios import generate_scenario
    replay = Replay(generate_scenario("carry"))

    def unexpected_tick(now):
        raise RuntimeError("invalid target reached the processing loop")

    # This sentinel also bounds the pre-fix NaN reproduction: it must never loop.
    monkeypatch.setattr(replay.engine, "tick", unexpected_tick)
    with pytest.raises(ValueError):
        replay.advance(target)
    assert replay.now == 0 and replay.i == 0 and replay.tracking_index == 0
    assert not replay.model.events


def test_replay_rejects_backward_advance_without_rewinding_snapshot():
    from copy import deepcopy
    from vmi.engine.replay import Replay
    from vmi.generator.scenarios import generate_scenario
    replay = Replay(generate_scenario("carry"))
    replay.advance(2)
    before = deepcopy(replay.model.__dict__)
    with pytest.raises(ValueError):
        replay.advance(1)
    assert replay.now == 2 and replay.model.__dict__ == before
    assert replay.advance(2) == []
    replay.advance(3)
    assert replay.now == 3
