from copy import deepcopy
import math

import pytest

from vmi.engine.replay import Replay
from vmi.engine.factpack import build_factpack
from vmi.generator.scenarios import SCENARIOS, generate_scenario
from vmi.generator.tracking import Tracker


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_reproducibility_and_delivered_score(name):
    a, b = generate_scenario(name), generate_scenario(name)
    assert a == b
    original = deepcopy(a)
    r = Replay(a)
    r.advance(a.duration)
    assert r.model.score == a.meta["final_score"]
    assert a == original
    assert "scenario" not in r.model.meta and "expected_anomalies" not in r.model.meta
    if name != "source_missing":
        assert not r.model.pending_links


@pytest.mark.parametrize("outcome", ["complete", "failed", "interrupted", "unresolved"])
def test_dribble_control_and_opponent_match_declared_result(outcome):
    m = generate_scenario(f"dribble_{outcome}")
    ev = next(e for e in m.events if e["type"] == "dribble")
    frame = Tracker(m).frame(ev["t"])
    active = {p["id"] for p in frame["players"]}
    assert ev["player_id"] in active and ev["dribble"]["defender_id"] in active
    expected = ev["player_id"] if outcome == "complete" else ev["dribble"]["defender_id"] if outcome == "failed" else None
    assert frame["possession"]["holder_id"] == expected
    assert frame["ball_in_play"] == (outcome != "interrupted")
    if outcome == "interrupted":
        assert any(e["id"] == ev["dribble"]["foul_id"] for e in m.events)
    encounter=Tracker(m).frame(ev["t"]-1)
    defender=next(p for p in encounter["players"] if p["id"]==ev["dribble"]["defender_id"])
    assert math.dist(encounter["ball"],[defender["x"],defender["y"]])<=1.1


def test_reversed_analytics_and_missing_source_are_intentional():
    m = generate_scenario("shots_reversed")
    shots = [e for e in m.events if e["type"] == "shot"]
    analytics = sorted((e for e in m.events if e["type"] == "shot_xg"), key=lambda e:e["delivered_t"])
    assert [e["shot_id"] for e in analytics] == [shots[1]["id"], shots[0]["id"]]
    missing = generate_scenario("source_missing")
    r = Replay(missing)
    r.advance(missing.duration)
    assert len(r.model.pending_links) == 2
    assert r.model.team_stats()["home"]["shots"] == 0


@pytest.mark.parametrize("name,count", [("penalty_no_card",0), ("penalty_card",1), ("penalty_late_card",1)])
def test_penalty_does_not_implicitly_create_a_card(name, count):
    m=generate_scenario(name)
    cards=[e for e in m.events if e["type"]=="card"]
    assert len(cards)==count
    if count:
        assert cards[0]["offence_id"] and cards[0]["decision_id"] and cards[0]["stoppage_id"]
        if name=="penalty_late_card":
            result=next(e for e in m.events if e["type"]=="shot_result")
            assert cards[0]["delivered_t"]>result["delivered_t"]


def test_drinks_keeps_the_pending_restart_until_explicit_execution():
    m=generate_scenario("drinks_break")
    drink=next(e for e in m.events if e["type"]=="drinks_break")
    taken=next(e for e in m.events if e["type"]=="restart_taken" and e["restart_id"]==drink["restart_id"])
    r=Replay(m)
    r.advance(drink["delivered_t"]+30)
    assert not r.model.ball_in_play
    assert r.model.pending_restart_id==drink["restart_id"]
    r.advance(taken["delivered_t"])
    assert r.model.ball_in_play and r.model.pending_restart_id is None


@pytest.mark.parametrize("name,expected", [("assist",True), ("assist_source_late",True),
                                           ("no_goal",False), ("rebound",False), ("goal_cancelled",False)])
def test_assists_require_valid_confirmed_goal_preparation(name, expected):
    m=generate_scenario(name)
    r=Replay(m); r.advance(m.duration)
    goals=[e for e in r.model.events if e["type"]=="shot" and e["shot"].get("outcome")=="goal"]
    assists=[]
    for goal in goals:
        pack=build_factpack(r.model,"goal",goal)
        assists += [f for f in pack["facts"] if f["type"]=="assist"]
    assert bool(assists)==expected
    if name=="goal_cancelled":
        assert r.model.score["home"]==0
        assert not any(e["derived"].get("assisted_by") for e in r.model.events)


def test_tracking_stream_is_lazy_exact_20hz_and_validates_bounds():
    m=generate_scenario("assist")
    tr=Tracker(m)
    frames=tr.frames(0,1)
    assert iter(frames) is frames
    assert [f["t"] for f in frames]==[i/20 for i in range(21)]
    for start,end,hz in [(-1,1,20),(0,m.duration+1,20),(0,1,0),(0,float("nan"),20),(0,1,True)]:
        with pytest.raises(ValueError): list(tr.frames(start,end,hz))


@pytest.mark.parametrize("change", ["incomplete", "recipient", "possession", "opponent_control"])
def test_nearby_pass_is_not_enough_for_assist(change):
    m=generate_scenario("assist")
    p=next(e for e in m.events if e["type"]=="pass")
    shot=next(e for e in m.events if e["type"]=="shot")
    if change=="incomplete": p["pass"]["outcome"]="incomplete"
    elif change=="recipient": p["pass"]["recipient_id"]="H8"
    elif change=="possession": p["possession_id"]="other"
    else:
        at=(p["t"]+shot["t"])/2
        m.events.append({"schema_version":"2.0","id":"intervening","match_id":m.meta["match_id"],
                         "source":"event_feed","type":"ball_recovery","t":at,"delivered_t":at+0.1,
                         "clock":p["clock"],"period":1,"team":"away","player_id":"A4"})
    r=Replay(m);r.advance(m.duration)
    goal=r.model.by_id[shot["id"]]
    assert not goal["derived"].get("assisted_by")
    assert not any(f["type"]=="assist" for f in build_factpack(r.model,"goal",goal)["facts"])


def test_late_pass_enriches_new_factpack_without_rewriting_old_one():
    m=generate_scenario("assist_source_late")
    p=next(e for e in m.events if e["type"]=="pass")
    shot=next(e for e in m.events if e["type"]=="shot")
    r=Replay(m);r.advance(p["delivered_t"]-0.01)
    before=build_factpack(r.model,"goal",r.model.by_id[shot["id"]])
    frozen=deepcopy(before)
    assert not any(f["type"]=="assist" for f in before["facts"])
    r.advance(p["delivered_t"])
    after=build_factpack(r.model,"goal",r.model.by_id[shot["id"]])
    assert any(f["type"]=="assist" for f in after["facts"])
    assert before==frozen


def test_cancelled_goal_removes_pending_goal_analysis_and_official_counts():
    m=generate_scenario("goal_cancelled")
    r=Replay(m);outputs=r.advance(m.duration)
    assert not any(o["kind"]=="analysis" and o["moment"]=="goal" for o in outputs)
    assert r.model.team_stats()["home"]["shots"]==0
    assert r.model.momentum().shots["home"]==0
    feed=[o for o in outputs if o["kind"]=="feed" and o.get("shot_id")]
    assert len({o["cue_id"] for o in feed})==1
    assert "disallowed" in feed[-1]["text"]["basic"]


def test_segment_setup_and_anomaly_names_cannot_reveal_future_to_model():
    metas=[Replay(generate_scenario(name)).model.meta for name in SCENARIOS]
    assert len({meta["match_id"] for meta in metas})==len(SCENARIOS)
    clean=[{k:v for k,v in meta.items() if k!="match_id"} for meta in metas]
    assert all(meta==clean[0] for meta in clean)
    assert not any(name in meta["match_id"] for name,meta in zip(SCENARIOS,metas))
    carry=generate_scenario("carry")
    assert any(e["type"]=="carry" for e in carry.events)
    assert not any(e["type"]=="dribble" for e in carry.events)


@pytest.mark.parametrize("change", ["outcome", "defender", "handball"])
def test_invalid_action_reports_are_rejected(change):
    from vmi.contracts import validate_record
    m=generate_scenario("handball" if change=="handball" else "dribble_complete")
    e=next(e for e in m.events if e["type"] in {"dribble","handball"})
    if change=="handball": e["handball"]["offence"]=False
    elif change=="outcome": e["dribble"]["outcome"]="maybe"
    else: e["dribble"]["defender_id"]=e["player_id"]
    with pytest.raises(ValueError): validate_record(e,m.meta["match_id"])


@pytest.mark.parametrize("patch", [{"player_id":"A9"},{"t":0}])
def test_bad_cancellation_cannot_subtract_a_delivered_goal(patch):
    m=generate_scenario("goal_cancelled")
    cancel=next(e for e in m.events if e["type"]=="goal_cancelled")
    # Deliver every prerequisite but withhold the authoritative cancellation.
    # Otherwise this deliberately malformed record correctly waits for its source.
    m.events.remove(cancel)
    r=Replay(m);r.advance(m.duration)
    assert r.model.score["home"]==1
    with pytest.raises(ValueError): r.model.ingest(cancel|patch|{"id":"bad-cancellation"})
    assert r.model.score["home"]==1
