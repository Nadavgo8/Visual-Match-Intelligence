from copy import deepcopy

import pytest

from vmi.engine.atmosphere import Atmosphere


def frame(t, x=94, y=34, *, team="home", role="ST", period=1, possession="p1"):
    return {"t":t,"period":period,"ball":[x,y],"ball_in_play":True,
            "quality":{"status":"measured","confidence":1,"sample_t":t},
            "possession":{"status":"controlled","id":possession,"holder_id":"player","team":team,"sample_t":t},
            "players":[{"id":"player","team":team,"role":role}]}


def stable(m, x=94, y=34, **kwargs):
    m.evaluate(0,frame(0,x,y,**kwargs),True,[(0,0.5)])
    return m.evaluate(0.3,frame(0.3,x,y,**kwargs),True,[(0.3,0.5)])


@pytest.mark.parametrize("x,y,tier,expected",[(81,34,0,0.4),(82.5,34,0.3,0.46),
                                               (88.5,34,0.65,0.53),(99.5,34,1,0.6),
                                               (100,10,0,0.4)])
def test_independent_worked_examples_for_all_tiers(x,y,tier,expected):
    result=stable(Atmosphere(),x,y)
    assert result["attack"]==tier and result["level"]==expected


def test_promotion_waits_until_exactly_300ms_of_observations():
    m=Atmosphere()
    for t in (0,0.1,0.299):
        assert m.evaluate(t,frame(t),True,[(t,0)])["attack"]==0
    assert m.evaluate(0.3,frame(0.3),True,[(0.3,0)])["attack"]==0.65
    assert m.evaluate(0.301,frame(0.301),True,[(0.301,0)])["attack"]==0.65


@pytest.mark.parametrize("age,expected",[(0.499,0.65),(0.5,0.65),(0.501,0)])
def test_tracking_freshness_boundary_is_inclusive(age,expected):
    m=Atmosphere();stable(m)
    assert m.evaluate(0.3+age,frame(0.3),True,[(0.3+age,0.5)])["attack"]==expected


@pytest.mark.parametrize("change",["goalkeeper","stopped","loose","missing","quality","possession_age","inactive","new_owner"])
def test_loss_or_unreliable_input_cancels_attack_immediately(change):
    m=Atmosphere();stable(m)
    f=frame(0.31)
    live=True
    if change=="goalkeeper": f["players"][0]["role"]="GK"
    elif change=="stopped": live=False
    elif change=="loose": f["possession"]["status"]="loose"
    elif change=="missing": f=None
    elif change=="quality": f["quality"]["status"]="unreliable"
    elif change=="possession_age": f["possession"]["sample_t"]=-1
    elif change=="inactive": f["players"]=[]
    elif change=="new_owner": f["possession"]["id"]="new"
    assert m.evaluate(0.31,f,live,[(0.31,0.5)])["attack"]==0


def test_direction_flips_at_half_time_and_defence_never_counts_as_attack():
    assert stable(Atmosphere(),10,34,period=1)["attack"]==0
    assert stable(Atmosphere(),10,34,period=2)["attack"]==0.65
    assert stable(Atmosphere(),94,34,team="away",period=1)["attack"]==0
    assert stable(Atmosphere(),10,34,team="away",period=1)["attack"]==0.65


def test_quiet_is_distinct_from_missing_crowd_and_no_weight_is_hidden():
    m=Atmosphere();stable(m,100)
    assert m.evaluate(0.3,frame(0.3,100),True,[(0.3,0)])["level"]==0.2
    missing=m.evaluate(0.3,frame(0.3,100),True,[])
    assert missing["level"] is None and not missing["crowd_available"]
    assert m.evaluate(4,frame(4),True,[(0,0.5)])["level"] is None
    crowd_only=Atmosphere(mode="crowd_only").evaluate(0,frame(0),True,[(0,0.5)])
    assert crowd_only["level"]==0.5 and crowd_only["mode"]=="crowd_only"
    assert Atmosphere().evaluate(0,None,True,[(0,0.5)])["level"]==0.4


def test_jitter_and_owner_switch_restart_stability_without_mutating_input():
    m=Atmosphere();stable(m,86)
    f=frame(0.31,90);saved=deepcopy(f)
    assert m.evaluate(0.31,f,True,[(0.31,0.5)])["attack"]==0.3
    assert f==saved
    assert m.evaluate(0.4,frame(0.4,86),True,[(0.4,0.5)])["attack"]==0.3
    assert m.evaluate(0.5,frame(0.5,90),True,[(0.5,0.5)])["attack"]==0.3
    assert m.evaluate(0.799,frame(0.799,90),True,[(0.799,0.5)])["attack"]==0.3
    assert m.evaluate(0.8,frame(0.8,90),True,[(0.8,0.5)])["attack"]==0.65


def test_single_repeated_packet_does_not_prove_300ms_stability():
    m=Atmosphere()
    m.evaluate(0,frame(0),True,[(0,0.5)])
    assert m.evaluate(0.3,frame(0),True,[(0.3,0.5)])["attack"]==0


def test_replay_delivers_lazy_tracking_and_lean_sample_matches_rendered_ball():
    from vmi.generator.scenarios import generate_scenario
    from vmi.generator.tracking import Tracker
    from vmi.engine.replay import Replay
    m=generate_scenario("dribble_complete")
    tracker=Tracker(m)
    for t in (0,3,4,5):
        rendered,lean=tracker.frame(t),tracker.observation(t)
        for key in ("ball","ball_height","ball_in_play","possession","quality","period"):
            assert rendered[key]==lean[key]
        assert len(lean["players"])<=1
    r=Replay(m);r.advance(2)
    assert r.tracking_index==40 and r.model.tracking["t"]==1.95
    assert not any(rec.get("stream")=="tracking" for _,_,rec in r.stream)
    latest=deepcopy(r.model.tracking)
    r.model.ingest(tracker.observation(1))
    assert r.model.tracking==latest


def test_momentum_window_includes_lower_boundary_and_excludes_older_samples():
    from collections import deque
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    m=MatchModel(generate_scenario("carry").meta)
    m.possession_samples=deque([(0,"home"),(1,"away")])
    m.events=[{"type":"shot","shot":{},"team":"home","t":0},
              {"type":"shot","shot":{},"team":"away","t":1}]
    m.tick(420)
    assert m.momentum().shots=={"home":1,"away":1}
    assert list(m.possession_samples)==[(0,"home"),(1,"away")]
    m.tick(420.01)
    assert m.momentum().shots=={"home":0,"away":1}
    assert list(m.possession_samples)==[(1,"away")]


@pytest.mark.parametrize("now,home,available", [(420, 0.5, True), (420.05, 0, True), (421.05, 0.5, False)])
def test_fractional_meter_uses_one_window_for_possession_and_events(now, home, available):
    from collections import deque
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.engine.attention import AttentionEngine
    m = MatchModel(generate_scenario("carry").meta)
    m.possession_samples = deque([(0, "home"), (1, "away")])
    m.events = [{"type": "shot", "shot": {}, "team": "home", "t": 0},
                {"type": "shot", "shot": {}, "team": "away", "t": 1}]
    m.tick(420)  # cleanup happens on integer ticks, delivery can happen in between
    engine = AttentionEngine(m)
    output = engine.ingest({"schema_version": "2.0", "match_id": m.meta["match_id"],
                            "stream": "crowd", "t": now, "crowd_level": 0.5,
                            "quality": {"status": "measured", "confidence": 1}}, now)
    momentum = next(o["momentum"] for o in output if o["kind"] == "meters")
    assert momentum["possession_home"] == home
    assert momentum["possession_available"] is available
    assert momentum["shots"] == {"home": int(now <= 420), "away": int(now <= 421)}


def test_tracking_gap_requires_stability_again_after_recovery():
    m=Atmosphere();stable(m)
    assert m.evaluate(0.9,frame(0.9),True,[(0.9,0.5)])["attack"]==0
    assert m.evaluate(1.2,frame(1.2),True,[(1.2,0.5)])["attack"]==0.65


def test_dribble_and_xg_fields_cannot_add_a_bonus():
    m=Atmosphere();stable(m)
    f=frame(0.31)
    f.update(xg=1,dribble={"outcome":"complete"})
    result=m.evaluate(0.31,f,True,[(0.31,0.5)])
    assert result["attack"]==0.65 and result["level"]==0.53


def test_invalid_modes_fail_and_missing_possession_is_not_reported_as_measured_50_percent():
    with pytest.raises(ValueError): Atmosphere(mode="automatic")
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.agents.qa import Assistant
    import asyncio
    m=MatchModel(generate_scenario("carry").meta)
    assert not m.momentum().as_dict()["possession_available"]
    result=asyncio.run(Assistant(m).answer("who is on top?"))
    assert "possession data unavailable" in result["text"] and "50%" not in result["text"]


def test_meter_deadline_expires_attack_without_another_packet_or_possession_tick():
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.engine.attention import AttentionEngine
    m=MatchModel(generate_scenario("carry").meta);m.ball_in_play=True
    engine=AttentionEngine(m)
    for t in (0,0.3):
        sample=frame(t)|{"schema_version":"2.0","match_id":m.meta["match_id"],"stream":"tracking","source":"tracking"}
        engine.ingest(sample,t)
    assert engine.atmosphere.attack==0.65
    deadline=engine.next_meter_expiry()
    assert 0.8<deadline<0.801
    outputs=engine.poll_meters(deadline)
    assert outputs[0]["atmosphere"]["attack"]==0
    assert not m.possession_samples


def test_declared_crowd_only_replay_keeps_original_weight_and_label():
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.replay import Replay
    r=Replay(generate_scenario("carry"),atmosphere_mode="crowd_only")
    out=r.advance(1)
    meter=next(o["atmosphere"] for o in reversed(out) if o["kind"]=="meters" and o["atmosphere"]["available"])
    assert meter["mode"]=="crowd_only" and meter["level"]==meter["crowd"] and meter["attack"]==0


def test_final_analysis_releases_on_fractional_deadline_without_an_extra_tick():
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.replay import Replay
    m=generate_scenario("carry")
    m.meta["end_t"]=6.25
    m.events=[{"schema_version":"2.0","match_id":m.meta["match_id"],"id":"end",
               "source":"event_feed","type":"period_end","period":2,"clock":"90:00",
               "t":1.25,"delivered_t":1.75,"team":None,"player_id":None,"period_end":{"period_no":2}}]
    outputs=Replay(m).advance(6.25)
    summary=[o for o in outputs if o["kind"]=="analysis" and o["moment"]=="full_time"]
    assert len(summary)==1 and summary[0]["t"]==6.25


@pytest.mark.parametrize("stamp",["quality","possession"])
@pytest.mark.parametrize("age,expected",[(0.5,0.65),(0.501,0)])
def test_independent_measurement_and_possession_timestamps_must_be_fresh(stamp,age,expected):
    m=Atmosphere()
    m.evaluate(1,frame(1),True,[(1,0.5)])
    m.evaluate(1.3,frame(1.3),True,[(1.3,0.5)])
    f=frame(1.8);f[stamp]["sample_t"]=1.8-age
    assert m.evaluate(1.8,f,True,[(1.8,0.5)])["attack"]==expected


@pytest.mark.parametrize("kind",["play_stopped","ball_loose","ball_recovery"])
def test_delivered_stop_or_loss_resets_meter_in_same_ingest_call(kind):
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.engine.attention import AttentionEngine
    m=MatchModel(generate_scenario("carry").meta);m.ball_in_play=True
    e=AttentionEngine(m)
    for t in (0,0.3):
        e.ingest(frame(t)|{"schema_version":"2.0","match_id":m.meta["match_id"],"stream":"tracking","source":"tracking"},t)
    assert e.atmosphere.attack==0.65
    event={"schema_version":"2.0","match_id":m.meta["match_id"],"source":"event_feed","id":"loss",
           "type":kind,"t":0.31,"delivered_t":0.32,"team":"away","player_id":"A4",
           "trigger_event_id":"cause","reason":"unknown"}
    outputs=e.ingest(event,0.32)
    meters=[o for o in outputs if o["kind"]=="meters"]
    assert meters and meters[-1]["atmosphere"]["attack"]==0


def test_engine_rejects_future_delivery_before_mutating_state():
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.engine.attention import AttentionEngine
    match=generate_scenario("assist")
    shot=next(e for e in match.events if e["type"]=="shot")
    engine=AttentionEngine(MatchModel(match.meta))
    with pytest.raises(ValueError): engine.ingest(shot,shot["delivered_t"]-0.01)
    assert not engine.model.events and engine.now==0


def test_crowd_tools_skip_missing_windows_and_do_not_call_missing_data_quiet():
    import asyncio
    from vmi.generator.scenarios import generate_scenario
    from vmi.engine.model import MatchModel
    from vmi.agents.tools import MatchTools
    from vmi.agents.qa import Assistant
    m=MatchModel(generate_scenario("carry").meta)
    m.crowd.extend([(0,0.1),(1,0.2),(2,None),(3,0.8),(4,0.1),(5,0.2)])
    m.t=5
    assert MatchTools(m).get_crowd_peaks()["peaks"]==[]
    m.crowd.append((6,None));m.t=6
    answer=asyncio.run(Assistant(m).answer("is the crowd quiet?"))
    assert "unavailable" in answer["text"]
