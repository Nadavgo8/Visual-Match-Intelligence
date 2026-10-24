from copy import deepcopy

import pytest

from vmi.contracts import validate_record
from vmi.engine.attention import AttentionEngine
from vmi.engine.model import MatchModel
from vmi.engine.factpack import build_factpack
from vmi.engine.replay import Replay
from vmi.agents.tools import MatchTools
from vmi.agents.explainer import template, validate
from vmi.generator.match import generate_match


@pytest.fixture(scope="module")
def match():
    return generate_match(12)


def event(match, kind, eid, t=10, **fields):
    return {"schema_version": "2.0", "id": eid, "match_id": match.meta["match_id"],
            "source": "event_feed", "type": kind, "t": t, "delivered_t": t + 1,
            "period": 1, "clock": "0:10", "team": "home", "player_id": "H9", **fields}


def shot(match, eid="s1"):
    return event(match, "shot", eid, shot={"body_part": "right_foot", "penalty": False}, location=[94, 34])


def result(match, sid="s1", eid="r1", outcome="goal"):
    return event(match, "shot_result", eid, t=11, shot_id=sid, outcome=outcome)


def xg(match, sid="s1", eid="x1", value=0.24):
    return event(match, "shot_xg", eid, t=13, shot_id=sid, xg=value,
                 source="synthetic_analytics", method_version="fixture-1")


def test_all_generator_records_are_v2_with_separate_results(match):
    by_id = {e["id"]: e for e in match.events}
    assert len(by_id) == len(match.events)
    for e in [*match.events, *match.crowd, *match.match_state]:
        validate_record(e, match.meta["match_id"])
        if e.get("type") in {"shot_result", "shot_xg"}:
            parent = by_id[e["shot_id"]]
            assert parent["type"] == "shot" and parent["t"] < e["t"]
            assert "outcome" not in parent["shot"] and "xg" not in parent["shot"]
            if e["type"] == "shot_xg":
                assert 1.99 <= e["t"] - parent["t"] <= 5.01


def test_two_shots_link_in_reverse_order_and_duplicate_once(match):
    m = MatchModel(match.meta)
    inputs = [xg(match, "s2", "x2", 0.6), result(match, "s2", "r2", "saved"),
              result(match), xg(match), shot(match), shot(match, "s2")]
    original = deepcopy(inputs)
    for e in inputs:
        m.ingest(e)
        m.ingest(e)
    assert inputs == original
    assert not m.pending_links
    assert m.score == {"home": 1, "away": 0}
    assert m.team_stats()["home"]["shots"] == 2
    assert m.by_id["s1"]["derived"]["xg"] == 0.24
    assert m.by_id["s2"]["derived"]["xg"] == 0.6
    assert m.team_stats()["home"]["xg"] == 0.84


def test_unknown_result_and_xg_stay_missing_and_feed_upserts(match):
    m = MatchModel(match.meta)
    engine = AttentionEngine(m)
    first = engine.ingest(shot(match), 11)[0]
    assert m.score["home"] == 0
    assert m.team_stats()["home"]["xg"] is None
    assert "pending" in first["text"]["basic"]
    updated = [o for o in engine.ingest(result(match), 12) if o["kind"] == "feed"][0]
    assert updated["cue_id"] == first["cue_id"] and updated["update"]
    before = deepcopy(updated)
    enriched = engine.ingest(xg(match), 14)[0]
    assert enriched["cue_id"] == first["cue_id"]
    assert enriched["xg"] == 0.24 and "x1" in enriched["evidence"]
    assert updated == before  # published responses are snapshots
    assert engine.ingest(xg(match), 15) == []


def test_missing_source_buffer_is_bounded_and_expires(match):
    m = MatchModel(match.meta)
    for n in range(260):
        m.ingest(xg(match, f"missing{n}", f"x{n}"))
    assert len(m.pending_links) == 256 and len(m.link_errors) == 4
    assert not m.events and m.score["home"] == 0
    m.tick(135)
    assert len(m.pending_links) == 0 and len(m.link_errors) == 128


@pytest.mark.parametrize("patch", [{"schema_version": "1.0"}, {"match_id": "other"},
                                   {"t": float("nan")}, {"delivered_t": 0}, {"id": ""},
                                   {"shot": {"outcome": "goal"}}, {"xg": 0.5}])
def test_bad_shots_rejected_before_state_change(match, patch):
    m = MatchModel(match.meta)
    with pytest.raises(ValueError):
        m.ingest(shot(match) | patch)
    assert not m.events and not m.by_id and m.score["home"] == 0


def test_foul_coordinates_do_not_award_penalty_and_award_does_not_restart(match):
    m = MatchModel(match.meta)
    f = event(match, "foul", "f", foul={"advantage": False}, location=[2, 34])
    m.ingest(f)
    assert not m.by_id["f"]["derived"]["penalty_awarded"]
    stop = event(match, "play_stopped", "stop", trigger_event_id="f", reason="unknown")
    decision = event(match, "referee_decision", "d", trigger_event_id="f", stoppage_id="stop", decision="penalty")
    award = event(match, "restart_awarded", "a", decision_id="d", stoppage_id="stop", restart_kind="penalty")
    taken = event(match, "restart_taken", "taken", t=12, restart_id="a", stoppage_id="stop")
    for e in (award, decision, stop):
        m.ingest(e)
    assert m.by_id["f"]["derived"]["penalty_awarded"]
    assert not m.ball_in_play and m.pending_restart_id == "a"
    m.ingest(taken)
    assert m.ball_in_play and m.active_stoppage_id is None
    m.ingest(stop)
    assert m.ball_in_play


def test_correction_replaces_only_current_decision_for_same_stop(match):
    m = MatchModel(match.meta)
    for e in (event(match, "foul", "f", foul={"advantage": False}, location=[2, 34]),
              event(match, "play_stopped", "stop", trigger_event_id="f", reason="unknown"),
              event(match, "referee_decision", "d", trigger_event_id="f", stoppage_id="stop", decision="penalty")):
        m.ingest(e)
    m.ingest(event(match, "referee_decision", "correct", trigger_event_id="f", stoppage_id="stop",
                   decision="no_penalty", supersedes_decision_id="d"))
    assert not m.by_id["f"]["derived"]["penalty_awarded"]
    assert m.decision_by_stop["stop"] == "correct"
    m.ingest(event(match, "referee_decision", "stale", trigger_event_id="f", stoppage_id="stop", decision="penalty"))
    assert not m.by_id["f"]["derived"]["penalty_awarded"]


def test_factpack_freezes_delivered_analytics_and_tools_report_missing(match):
    m = MatchModel(match.meta)
    m.ingest(shot(match))
    tools = MatchTools(m)
    assert "pending" in tools.get_events(types="shot")["events"][0]["what"]
    assert tools.get_player("#9 home")["players"][0]["xg"] is None
    m.ingest(result(match))
    pack = build_factpack(m, "goal", m.by_id["s1"])
    snapshot = deepcopy(pack)
    assert pack["facts"][0]["id"] == "r1"
    m.ingest(xg(match))
    m.tick(20)
    assert pack == snapshot and pack["facts"][0]["xg"] is None
    assert build_factpack(m, "goal", m.by_id["s1"])["facts"][0]["xg"] == 0.24
    roster = {p["name"] for side in match.meta["teams"].values() for p in side["players"]}
    for depth in ("basic", "deep"):
        text = template(pack, depth)
        assert validate(text, pack, roster) == []
        assert "None" not in str(text)


@pytest.mark.parametrize("patch", [{"team": "away"}, {"player_id": "A9"}, {"t": 9}])
def test_invalid_link_identity_or_time_cannot_change_state(match, patch):
    m = MatchModel(match.meta)
    m.ingest(shot(match))
    before = deepcopy(m.events)
    with pytest.raises(ValueError):
        m.ingest(result(match) | patch)
    assert m.events == before and m.score["home"] == 0


def test_invalid_buffered_record_does_not_poison_source_delivery(match):
    m = MatchModel(match.meta)
    m.ingest(result(match) | {"team": "away"})
    m.ingest(shot(match))
    assert m.score["home"] == 0 and not m.pending_links
    assert m.link_errors[-1]["id"] == "r1"


def test_analytics_and_buffered_results_cannot_rewind_clock(match):
    m = MatchModel(match.meta)
    m.ingest(shot(match))
    m.ingest(event(match, "ball_recovery", "later", t=50, clock="0:50"))
    m.ingest(xg(match))
    m.ingest(result(match))
    assert m.clock == "0:50"


def test_replay_score_matches_delivered_results_and_has_no_future_metadata(match):
    r = Replay(match)
    assert "final_score" not in r.model.meta and "end_t" not in r.model.meta
    goal = next(e for e in match.events if e["type"] == "shot_result" and e["outcome"] == "goal")
    r.advance(goal["delivered_t"] - 0.01)
    assert sum(r.model.score.values()) == 0
    r.advance(goal["delivered_t"])
    assert sum(r.model.score.values()) == 1
    r.advance(match.duration)
    assert r.model.score == match.meta["final_score"] and not r.model.pending_links


def test_whistle_reason_delivered_before_audio_still_links_exact_id(match):
    engine = AttentionEngine(MatchModel(match.meta))
    foul = event(match, "foul", "f", foul={"advantage": False}, trigger_event_id="w")
    engine.ingest(foul, 11)
    engine.ingest(event(match, "whistle", "unrelated", whistle={"blasts": 1, "length": "short"}), 11)
    out = engine.ingest(event(match, "whistle", "w", whistle={"blasts": 1, "length": "short"}), 11.1)
    banner = next(o for o in out if o["kind"] == "banner")
    assert banner["type"] == "foul" and banner["evidence"] == ["w", "f"]


def test_superseded_award_cannot_restart_or_publish_penalty(match):
    engine = AttentionEngine(MatchModel(match.meta))
    for e in (event(match, "foul", "f", foul={"advantage": False}),
              event(match, "play_stopped", "stop", trigger_event_id="f", reason="unknown"),
              event(match, "referee_decision", "d", trigger_event_id="f", stoppage_id="stop", decision="penalty"),
              event(match, "restart_awarded", "award", decision_id="d", stoppage_id="stop", restart_kind="penalty"),
              event(match, "referee_decision", "correction", trigger_event_id="f", stoppage_id="stop",
                    decision="free_kick", supersedes_decision_id="d")):
        engine.ingest(e, 11)
    out = engine.ingest(event(match, "referee_decision", "stale", trigger_event_id="f", stoppage_id="stop", decision="penalty"), 12)
    assert out == []
    out = engine.ingest(event(match, "restart_taken", "taken", t=12, restart_id="award", stoppage_id="stop"), 13)
    assert not engine.model.ball_in_play and out == []


def test_xg_enrichment_does_not_change_screen_meters_or_momentum(match):
    engine = AttentionEngine(MatchModel(match.meta))
    engine.ingest(shot(match), 11)
    before = engine._meters(11)
    outputs = engine.ingest(xg(match), 14)
    assert all(o["kind"] == "feed" for o in outputs)
    assert engine._meters(11) == before


@pytest.mark.parametrize("patch", [{"xg": -0.1}, {"xg": 1.1}, {"xg": float("nan")},
                                   {"xg": True}, {"source": "event_feed"}, {"method_version": ""},
                                   {"shot_id": ""}, {"shot_id": "x1"}])
def test_invalid_analytics_rejected_without_mutation(match, patch):
    m = MatchModel(match.meta)
    with pytest.raises(ValueError):
        m.ingest(xg(match) | patch)
    assert not m.events and not m.pending_links


def test_xg_without_result_is_not_called_a_missed_chance_in_period_summary(match):
    m = MatchModel(match.meta)
    m.ingest(shot(match))
    m.ingest(xg(match))
    pack = build_factpack(m, "full_time", event(match, "period_end", "end", period_end={"period_no": 2}))
    assert not any(f["type"] == "best_missed_chance" for f in pack["facts"])
    text = template(pack, "deep")
    assert "missed" not in str(text).lower()


def test_rejected_execution_cannot_hide_a_later_valid_stop(match):
    m = MatchModel(match.meta)
    for e in (event(match, "foul", "f", foul={"advantage": False}),
              event(match, "play_stopped", "s", trigger_event_id="f", reason="unknown"),
              event(match, "referee_decision", "d", trigger_event_id="f", stoppage_id="s", decision="penalty"),
              event(match, "restart_awarded", "a", decision_id="d", stoppage_id="s", restart_kind="penalty"),
              event(match, "referee_decision", "correction", trigger_event_id="f", stoppage_id="s",
                    decision="free_kick", supersedes_decision_id="d"),
              event(match, "restart_awarded", "a2", decision_id="correction", stoppage_id="s", restart_kind="free_kick"),
              event(match, "restart_taken", "valid", t=15, restart_id="a2", stoppage_id="s"),
              event(match, "restart_taken", "invalid", t=100, restart_id="a", stoppage_id="s")):
        m.ingest(e)
    assert m.ball_in_play
    m.ingest(event(match, "play_stopped", "s2", t=20, trigger_event_id="f", reason="unknown"))
    assert not m.ball_in_play and m.active_stoppage_id == "s2"


def test_delayed_older_stop_cannot_replace_the_current_stoppage(match):
    m = MatchModel(match.meta)
    for e in (event(match, "foul", "f", foul={"advantage": False}),
              event(match, "play_stopped", "current", t=30, trigger_event_id="f", reason="unknown"),
              event(match, "play_stopped", "older", t=20, trigger_event_id="f", reason="unknown")):
        m.ingest(e)
    assert m.active_stoppage_id == "current"
    assert not m.ball_in_play
    for e in (event(match, "referee_decision", "d", t=31, trigger_event_id="f",
                    stoppage_id="current", decision="free_kick"),
              event(match, "restart_awarded", "a", t=31, decision_id="d",
                    stoppage_id="current", restart_kind="free_kick"),
              event(match, "restart_taken", "taken", t=35, restart_id="a", stoppage_id="current")):
        m.ingest(e)
    assert m.ball_in_play and m.active_stoppage_id is None


@pytest.mark.parametrize("buffered", [False, True])
def test_restart_cannot_precede_its_stoppage_or_award(match, buffered):
    m = MatchModel(match.meta)
    impossible = event(match, "restart_taken", "impossible", t=19, restart_id="a", stoppage_id="s")
    if buffered:
        m.ingest(impossible)
    for e in (event(match, "foul", "f", foul={"advantage": False}),
              event(match, "play_stopped", "s", t=20, trigger_event_id="f", reason="unknown"),
              event(match, "referee_decision", "d", t=21, trigger_event_id="f", stoppage_id="s", decision="free_kick"),
              event(match, "restart_awarded", "a", t=22, decision_id="d", stoppage_id="s", restart_kind="free_kick")):
        m.ingest(e)
    before = deepcopy(m.events)
    if buffered:
        assert not m.pending_links and m.link_errors[-1]["id"] == "impossible"
    else:
        with pytest.raises(ValueError):
            m.ingest(impossible)
    assert m.events == before and not m.ball_in_play
