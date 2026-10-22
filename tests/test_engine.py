"""The Attention Engine routes correctly and derives what the feed doesn't say."""

import pytest

from vmi.engine.attention import visible_to
from vmi.engine.model import momentum_from_counts
from vmi.engine.replay import run_all
from vmi.generator.match import generate_match


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


def test_overturned_penalty_is_detected_from_the_feed(demo):
    _, outs = demo
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


def test_atmosphere_moods_are_known(demo):
    _, outs = demo
    moods = {o["atmosphere"]["mood"] for o in outs if o["kind"] == "meters"}
    assert moods <= {"calm", "cheering", "tension", "eruption"} and "eruption" in moods
