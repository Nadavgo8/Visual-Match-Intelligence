"""Football minutes and ordinary fouls in the chat."""

import pytest

from vmi.agents.voices import chat_line
from vmi.engine import derive
from vmi.engine.attention import visible_to
from vmi.engine.replay import Replay
from vmi.generator.match import generate_match


@pytest.mark.parametrize("clock,minute", [("0:00", 1), ("0:45", 1), ("1:00", 2), ("44:59", 45),
                                          ("66:08", 67), ("45+2'", 45), ("90+3'", 90)])
def test_minutes_follow_football_convention(clock, minute):
    # A goal in the first seconds is a 1st-minute goal, never "minute 0".
    assert derive.minute_of(clock) == minute


@pytest.fixture(scope="module")
def outputs():
    m = generate_match(2)
    return m, Replay(m).advance(m.duration)


def test_every_ordinary_foul_reaches_the_chat_at_the_default_amount(outputs):
    m, outs = outputs
    fouls = {e["id"]: e for e in m.events if e["type"] == "foul"}
    feed = {o["evidence"][0]: o for o in outs if o["kind"] == "feed" and o["icon"] == "foul"}
    penalties = {o["evidence"][0] for o in outs if o["kind"] == "feed" and o["icon"] == "penalty"}
    assert fouls and set(fouls) == set(feed) | (penalties & set(fouls))
    for eid, item in feed.items():
        assert visible_to(item, "balanced") and item["text"]["basic"].startswith("Foul by ")
        assert ("advantage" in item["text"]["basic"]) == bool(fouls[eid]["foul"].get("advantage"))
        assert item["say"]["type"] == "foul" and item["say"]["to"]
        assert chat_line(item, "basic")  # Kai has a line for it


def test_foul_lines_name_the_fouler_and_the_free_kick_side(outputs):
    m, outs = outputs
    item = next(o for o in outs if o["kind"] == "feed" and o["icon"] == "foul" and not o["say"]["advantage"])
    line = chat_line(item, "basic")
    assert item["say"]["who"] in line
    assert "his " not in line and "her " not in line and "fouls on" not in line
    for advantage in (False, True):  # every phrasing, not just the one this cue picks
        from vmi.agents.voices import _kai_options
        for option in _kai_options("foul", {**item["say"], "advantage": advantage}):
            assert "fouls on" not in option and "down on" not in option

