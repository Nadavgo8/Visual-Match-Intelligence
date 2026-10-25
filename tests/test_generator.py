"""The generator is deterministic and its matches look like real football."""

import statistics

import pytest

from vmi.generator.match import generate_match
from vmi.generator.tracking import Tracker

SEEDS = range(1, 21)
FORBIDDEN = {"xg", "in_box", "called_on_field", "severity", "dogso", "events_driving", "mood", "reason_inferred"}


@pytest.fixture(scope="module")
def matches():
    return [generate_match(s) for s in SEEDS]


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def test_deterministic():
    a, b = generate_match(12), generate_match(12)
    assert a.events == b.events and a.crowd == b.crowd


def test_raw_feed_has_only_observable_fields(matches):
    for m in matches:
        for e in m.events:
            assert e["source"] in ("event_feed", "audio", "synthetic_analytics")
            allowed = {"xg"} if e["type"] == "shot_xg" else set()
            assert not (FORBIDDEN - allowed) & set(_walk_keys(e)), e
            if e["type"] == "whistle":
                assert set(e["whistle"]) == {"blasts", "length", "confidence"}
        assert all(c["source"] == "audio" and 0 <= c["crowd_level"] <= 1 for c in m.crowd)


def test_feed_is_delayed_like_a_real_one(matches):
    lat = []
    for match in matches:
        by_id = {e["id"]: e for e in match.events}
        # A reviewed offside is reported after VAR, with its original incident
        # timestamp. Only this explicitly linked correction has review latency.
        reviewed = {}
        for correction in (e for e in match.events if e["type"] == "goal_cancelled"):
            decision = by_id[correction["decision_id"]]
            offence = by_id[decision["trigger_event_id"]]
            assert offence["type"] == "offside"
            assert offence["t"] == by_id[correction["shot_id"]]["t"]
            assert offence["delivered_t"] == round(decision["t"] + 0.75, 2)
            reviewed[offence["id"]] = offence
        lat.extend(e["delivered_t"] - e["t"] for e in match.events
                   if e["source"] == "event_feed" and e["id"] not in reviewed)
    assert 0.5 <= min(lat) and max(lat) <= 3.01


def _per_match(matches, fn):
    return [fn(m) for m in matches]


def test_realistic_match_statistics(matches):
    goals = _per_match(matches, lambda m: sum(m.meta["final_score"].values()))
    shots = _per_match(matches, lambda m: sum(e["type"] == "shot" for e in m.events))
    fouls = _per_match(matches, lambda m: sum(e["type"] == "foul" for e in m.events))
    passes = _per_match(matches, lambda m: [e for e in m.events if e["type"] == "pass"])
    acc = [sum(p["pass"]["outcome"] == "complete" for p in ps) / len(ps) for ps in passes]
    cards = _per_match(matches, lambda m: sum(e["type"] == "card" for e in m.events))
    # top-flight ranges (per match, both teams), with room for small samples
    assert 1.8 <= statistics.mean(goals) <= 4.2
    assert 18 <= statistics.mean(shots) <= 40
    assert 15 <= statistics.mean(fouls) <= 40
    assert 650 <= statistics.mean(len(p) for p in passes) <= 1300
    assert 0.70 <= statistics.mean(acc) <= 0.90
    assert 1.5 <= statistics.mean(cards) <= 7


def test_match_length_and_periods(matches):
    for m in matches:
        assert 90 * 60 <= m.duration <= 105 * 60
        ends = [e for e in m.events if e["type"] == "period_end"]
        assert [e["period_end"]["period_no"] for e in ends] == [1, 2]


def test_tracking_frames(matches):
    m = matches[0]
    tr = Tracker(m)
    f = tr.frame(1000.0)
    assert len(f["players"]) in (20, 21, 22)
    assert all(0 <= p["x"] <= 105 and 0 <= p["y"] <= 68 for p in f["players"])


def test_normal_full_matches_emit_the_actions_previously_only_in_fixtures():
    # Rare events belong across a population, not forcibly in every match.
    from vmi.contracts import LINK_PARENTS, validate_record

    types, outcomes = set(), set()
    without_break = False
    for seed in range(1, 101):
        match = generate_match(seed)  # one match at a time, no full-frame allocation
        by_id = {e["id"]: e for e in match.events}
        assert len(by_id) == len(match.events)
        score = {"home": 0, "away": 0}
        for event in match.events:
            validate_record(event, match.meta["match_id"])
            types.add(event["type"])
            for link, expected_type in LINK_PARENTS.get(event["type"], {}).items():
                parent = by_id[event[link]]
                assert expected_type is None or parent["type"] == expected_type
                assert parent["t"] <= event["t"]
            if event["type"] == "dribble":
                outcomes.add(event["dribble"]["outcome"])
            if event["type"] == "shot_result" and event["outcome"] == "goal":
                score[event["team"]] += 1
            if event["type"] == "goal_cancelled":
                score[event["team"]] -= 1
            if event["type"] == "card":
                offence = by_id[event["offence_id"]]
                assert offence["type"] in {"foul", "handball"}
                assert offence["player_id"] == event["player_id"]
        assert score == match.meta["final_score"]
        additions = [e for e in match.events if e["type"] == "added_time"]
        assert [e["period"] for e in additions] == [1, 2]
        for event in additions:
            period = next(e for e in match.events if e["type"] == "period_start" and e["period"] == event["period"])
            end = next(e for e in match.events if e["type"] == "period_end" and e["period"] == event["period"])
            assert period["t"] + 2680 <= event["t"] <= end["t"]
        breaks = sum(e["type"] == "drinks_break" for e in match.events)
        assert breaks <= 2
        without_break |= breaks == 0
    assert {"carry", "dribble", "ball_loose", "handball", "drinks_break", "goal_cancelled"} <= types
    assert outcomes == {"complete", "failed", "interrupted", "unresolved"}
    assert without_break
