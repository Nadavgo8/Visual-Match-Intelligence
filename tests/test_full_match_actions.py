"""Small truth/state regressions for actions used by normal full matches."""

import math
import random

import pytest

from vmi.generator.match import _Sim
from vmi.generator.tracking import Tracker


def simulator(side="home"):
    sim = _Sim(12, "actions")
    sim.emit("period_start", period_no=1)
    sim.kick_off(side)
    holder = next(p for p in sim.on_pitch[side] if p.position == "ST")
    sim.t = 10
    sim.key(side, 70, 34, holder)
    sim.carrier = (side, holder, 70, 34)
    return sim, holder


@pytest.mark.parametrize("side", ["home", "away"])
def test_carry_reports_the_observed_span_without_changing_outcome_rng(side):
    sim, holder = simulator(side)
    start = sim.keyframes[-1]
    sim.t += 2
    sim.key(side, 73, 34, holder)
    rng = sim.rng.getstate()
    event = sim.record_carry(side, holder, start, sim.keyframes[-1])
    assert event["carry"]["start_t"] == 10
    assert event["carry"]["end_t"] == 12
    assert event["location"] == ([70, 34] if side == "home" else [35, 34])
    assert event["carry"]["end_location"] == ([73, 34] if side == "home" else [32, 34])
    assert event["t"] == sim.t and event["delivered_t"] > event["t"]
    assert event["possession_id"] == start.possession_id
    assert sim.rng.getstate() == rng


@pytest.mark.parametrize("invalid", ["stationary", "keeper", "stopped", "different_holder", "old_holder", "start_stopped", "same_time"])
def test_carry_is_not_invented_from_an_unobserved_or_invalid_hold(invalid):
    sim, holder = simulator()
    start = sim.keyframes[-1]
    sim.t += 1
    if invalid == "keeper":
        holder = sim.keeper("home")
    sim.key("home", 70 if invalid == "stationary" else 73, 34,
            sim.keeper("home") if invalid == "different_holder" else holder,
            in_play=invalid != "stopped")
    if invalid == "old_holder":
        start.holder = None
    if invalid == "start_stopped":
        start.in_play = False
    if invalid == "same_time":
        sim.keyframes[-1].t = start.t
    assert sim.record_carry("home", holder, start, sim.keyframes[-1]) is None


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("outcome", ["complete", "failed", "interrupted", "unresolved"])
def test_full_match_duel_has_matching_ball_holder_defender_and_restart(side, outcome):
    sim, holder = simulator(side)
    sim.attempt_dribble(side, holder, 70, 34, outcome)
    match = sim.export_match()
    event = next(e for e in match.events if e["type"] == "dribble")
    tracker = Tracker(match)
    end = tracker.frame(event["dribble"]["end_t"])
    defender = next(p for p in end["players"] if p["id"] == event["dribble"]["defender_id"])
    assert defender["team"] != side
    assert math.dist(end["ball"], [defender["x"], defender["y"]]) <= 1.1
    expected = holder.id if outcome == "complete" else defender["id"] if outcome == "failed" else None
    assert end["possession"]["holder_id"] == expected
    assert end["ball_in_play"] == (outcome != "interrupted")
    if outcome == "interrupted":
        foul = next(e for e in match.events if e["id"] == event["dribble"]["foul_id"])
        assert foul["type"] == "foul"
        assert any(e["type"] == "restart_taken" for e in match.events)
    if outcome == "unresolved":
        loose = next(e for e in match.events if e["type"] == "ball_loose")
        recovered = next(e for e in match.events if e["type"] == "ball_recovery")
        assert loose["t"] < recovered["t"]
        assert tracker.frame(recovered["t"])["possession"]["holder_id"] == holder.id


def test_drinks_break_preserves_awarded_restart_and_freezes_tracking_until_execution():
    sim, holder = simulator()
    sim.drinks_due = {1: 0}
    sim.stoppage(1)
    sim.maybe_drinks("home", "free_kick")
    drink = next(e for e in sim.events if e["type"] == "drinks_break")
    assert sim.play.restart_id == drink["restart_id"] and not sim.ball_in_play
    assert sim.maybe_drinks("home", "free_kick") is False
    sim.restart_free_kick("home", 70, 34)
    match = sim.export_match()
    tracker = Tracker(match)
    before, during = tracker.frame(drink["t"]), tracker.frame(drink["t"] + 30)
    assert before["ball"] == during["ball"]
    assert not during["ball_in_play"]
    taken = next(e for e in match.events if e["type"] == "restart_taken" and e["restart_id"] == drink["restart_id"])
    assert taken["t"] >= drink["t"] + 60
    assert tracker.frame(taken["t"])["ball_in_play"]


def test_drinks_break_requires_a_due_period_and_an_actual_stoppage():
    sim, holder = simulator()
    sim.drinks_due = {1: 0}
    assert sim.maybe_drinks("home", "free_kick") is False
    sim.stoppage(1)
    sim.drinks_due = {2: 4000}
    assert sim.maybe_drinks("home", "free_kick") is False
    sim.drinks_due = {1: 1000}
    assert sim.maybe_drinks("home", "free_kick") is False


@pytest.mark.parametrize("invalid", ["unknown_outcome", "stopped", "keeper"])
def test_invalid_dribble_cannot_create_an_encounter(invalid):
    sim, holder = simulator()
    if invalid == "stopped":
        sim.ball_in_play = False
    if invalid == "keeper":
        holder = sim.keeper("home")
    before = len(sim.events)
    with pytest.raises(ValueError):
        sim.attempt_dribble("home", holder, 70, 34, "unknown" if invalid == "unknown_outcome" else "complete")
    assert len(sim.events) == before


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("period", [1, 2])
@pytest.mark.parametrize("outcome", ["complete", "failed", "interrupted", "unresolved"])
def test_defender_closes_and_leaves_duel_without_a_teleport(side, period, outcome):
    sim, holder = simulator(side)
    sim.period = period
    if period == 2:
        sim.emit("period_start", period_no=2)
    sim.key(side, 70, 34, holder)
    entry_t = sim.t
    sim.attempt_dribble(side, holder, 70, 34, outcome)
    duel = next(e["dribble"] for e in sim.events if e["type"] == "dribble")
    tracker = Tracker(sim.export_match())
    previous = None
    for index in range(math.floor((sim.t - entry_t) * 20) + 1):
        frame = tracker.frame(entry_t + index / 20)
        defender = next(p for p in frame["players"] if p["id"] == duel["defender_id"])
        position = (defender["x"], defender["y"])
        if previous:
            assert math.dist(position, previous) <= 6 / 20 + 0.02
        previous = position


class Choice:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


@pytest.mark.parametrize("draw,advantage,kind", [(0, False, "handball"), (1, False, "foul"), (0, True, "foul")])
def test_handball_is_an_explicit_offence_and_never_an_inferred_advantage(draw, advantage, kind):
    sim, holder = simulator()
    sim.detail_rng = Choice(draw)
    defender = sim.opp_nearest("home", 70, 34)
    event = sim.emit_offence("away", defender, 35, 34, holder, "trip", advantage)
    assert event["type"] == kind
    if kind == "handball":
        assert event["handball"]["offence"] is True
    else:
        assert event["foul"]["advantage"] is advantage
    assert event[kind]["victim_id"] == holder.id


@pytest.mark.parametrize("draw,cancelled", [(0, True), (1, False)])
def test_goal_review_links_the_actual_result_and_adjusts_only_a_cancelled_goal(draw, cancelled):
    sim, holder = simulator()
    passer = next(p for p in sim.on_pitch["home"] if p.id != holder.id and p.position != "GK")
    preparing = sim.emit("pass", "home", passer, 90, 34, recipient_id=holder.id, outcome="complete")
    shot = sim.emit("shot", "home", holder, 94, 34, body_part="right_foot")
    shot["preparing_pass_id"] = preparing["id"]
    sim.t += 0.6
    result = sim.report("shot_result", shot_id=shot["id"], outcome="goal", team="home", player_id=holder.id)
    sim.score["home"] = 1
    sim.stop(result, "goal")
    sim.detail_rng = Choice(draw)
    assert sim.var_goal_check(shot) is cancelled
    assert sim.score["home"] == (0 if cancelled else 1)
    corrections = [e for e in sim.events if e["type"] == "goal_cancelled"]
    assert len(corrections) == int(cancelled)
    if cancelled:
        correction = corrections[0]
        by_id = {e["id"]: e for e in sim.events}
        decision = by_id[correction["decision_id"]]
        assert correction["shot_id"] == shot["id"] and correction["result_id"] == result["id"]
        assert decision["decision"] == "free_kick" and decision["team"] == "away"
        assert by_id[decision["trigger_event_id"]]["type"] == "offside"


@pytest.mark.parametrize("penalty", [True, False])
def test_review_cannot_invent_offside_for_penalty_or_a_solo_attempt(penalty):
    sim, holder = simulator()
    shot = sim.emit("shot", "home", holder, 94, 34, penalty=penalty)
    sim.report("shot_result", shot_id=shot["id"], outcome="goal", team="home", player_id=holder.id)
    sim.score["home"] = 1
    sim.detail_rng = Choice(0)
    assert sim.var_goal_check(shot) is False
    assert sim.score["home"] == 1
    assert not any(e["type"] == "goal_cancelled" for e in sim.events)


def test_handball_penalty_is_an_explicit_decision_and_does_not_imply_a_card():
    sim, holder = simulator()
    sim.detail_rng = Choice(0)
    defender = sim.opp_nearest("home", 94, 34)
    offence = sim.emit_offence("away", defender, 11, 34, holder, "trip", False)
    sim.whistle()
    decision = sim.decide(offence, "penalty", "home")
    assert decision["trigger_event_id"] == offence["id"]
    assert offence["type"] == "handball" and not sim.ball_in_play
    assert not any(e["type"] == "card" for e in sim.events)


def test_long_possession_cannot_skip_the_added_time_announcement():
    sim = _Sim(12, "long-possession")
    sim.play_possession = lambda: setattr(sim, "t", sim.period_start_t + 3100)
    match = sim.run()
    announcements = [e for e in match.events if e["type"] == "added_time"]
    assert [e["period"] for e in announcements] == [1, 2]
    for event in announcements:
        start = next(e["t"] for e in match.events if e["type"] == "period_start" and e["period"] == event["period"])
        assert event["t"] == start + 2680
        assert event["delivered_t"] >= event["t"]


@pytest.mark.parametrize("kind", ["foul", "handball"])
def test_card_points_to_its_actual_offence_and_player(kind):
    sim, holder = simulator()
    defender = sim.opp_nearest("home", 70, 34)
    offence = sim.emit(kind, "away", defender, 35, 34)
    # An intervening record must not become the card's parent by accident.
    sim.emit("foul", "home", holder, 70, 34)
    sim.rng = random.Random(0)
    sim.card_maybe("away", defender, base=1, offence=offence)
    card = next(e for e in sim.events if e["type"] == "card")
    assert card["offence_id"] == offence["id"]
    assert card["player_id"] == offence["player_id"]
    assert card["related"] == [offence["id"]]
