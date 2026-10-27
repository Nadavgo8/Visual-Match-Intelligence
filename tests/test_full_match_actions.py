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
    # Isolated action setup: the prior kickoff is not a physical journey to
    # this test's independently specified 70m starting contact at t=10.
    sim.keyframes.clear()
    sim.t = 10
    sim.key(side, 70, 34, holder)
    sim.carrier = (side, holder, 70, 34)
    return sim, holder


@pytest.mark.parametrize("side", ["home", "away"])
def test_penalty_setup_and_a_saved_kick_keep_legal_roots_and_a_fixed_flight(side):
    class Saved(random.Random):
        def random(self):
            return .8

    sim = _Sim(12, "legal-penalty")
    sim.emit("period_start", period_no=1)
    sim.key(side, 94, 34, None, False)
    sim.rng = Saved(1)
    sim.penalty(side)
    match = sim.export_match()
    tracker = Tracker(match)
    shot = next(e for e in match.events if e["type"] == "shot")
    save = next(e for e in match.events if e["type"] == "save")
    frame = tracker.frame(shot["t"])
    keeper = sim.keeper("away" if side == "home" else "home")
    attack_x = lambda x: x if tracker.attacks_right(side, shot["t"]) else 105-x
    for p in frame["players"]:
        if p["id"] == keeper.id:
            assert attack_x(p["x"]) == pytest.approx(105, abs=.01)
            facing = -math.pi/2 if tracker.attacks_right(side, shot["t"]) else math.pi/2
            assert p["motion"]["facing"] == pytest.approx(facing, abs=.001)
        elif p["id"] == shot["player_id"]:
            assert attack_x(p["x"]) == pytest.approx(94-.55, abs=.01)
            assert p["y"] == pytest.approx(34, abs=.01)
            facing = math.pi/2 if tracker.attacks_right(side, shot["t"]) else -math.pi/2
            assert p["motion"]["facing"] == pytest.approx(facing, abs=.001)
            assert p["contact"]["heading"] == pytest.approx(facing, abs=.001)
        elif p["id"] != shot["player_id"]:
            assert attack_x(p["x"]) < 88.5
            assert attack_x(p["x"]) < 94
            assert math.dist([p["x"],p["y"]],frame["ball"]) >= 9.15
    assert save["t"]-shot["t"] == pytest.approx(.6, abs=.001)
    saved = tracker.frame(save["t"])
    actor = next(p for p in saved["players"] if p["id"] == keeper.id)
    assert attack_x(actor["x"]) == pytest.approx(105, abs=.01)
    assert math.dist([actor["x"],actor["y"]],saved["ball"]) == pytest.approx(.55, abs=.015)
    assert actor["contact"]["effector"] == "hands"


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


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("period", [1, 2])
def test_called_offside_has_a_reachable_offside_kick_and_an_actual_receiver_touch(side, period):
    class Offside(random.Random):
        def random(self):
            return .01

        def gauss(self, mu, sigma):
            return 20 if sigma == 9 else 0

    sim, holder = simulator(side)
    sim.keyframes.clear()  # the independent starting pose, including switched ends
    sim.period = period
    if period == 2:
        sim.emit("period_start", period_no=2)
    sim.key(side, 70, 34, holder)
    sim.rng = Offside(1)
    sim.stoppage = lambda *_: None
    sim.restart_free_kick = lambda *_: None
    sim.pass_(side, holder, 70, 34, .5)
    match = sim.export_match()
    tracker = Tracker(match)
    called = next(e for e in match.events if e["type"] == "offside")
    kick = next(e for e in match.events if e["id"] in called["related"])
    receiver = called["player_id"]
    frame = tracker.frame(kick["t"])
    attack_x = lambda x: x if tracker.attacks_right(side, kick["t"]) else 105-x
    receiver_x = attack_x(next(p["x"] for p in frame["players"] if p["id"] == receiver))
    opponents = sorted((attack_x(p["x"]) for p in frame["players"] if p["team"] != side), reverse=True)
    assert receiver_x > max(52.5, attack_x(frame["ball"][0]), opponents[1]) + 1
    touches = [k for k in match.keyframes if kick["t"] < k.t <= called["t"] and k.holder == receiver]
    assert touches, "an untouched runner alone is not an offside offence"
    touch = touches[0]
    actual = tracker.frame(touch.t)
    actor = next(p for p in actual["players"] if p["id"] == receiver)
    assert math.dist([actor["x"], actor["y"]], actual["ball"]) == pytest.approx(.55, abs=.015)
    assert actor["contact"]["kind"] == "receive"
    assert actual["ball_height"] == 0
    distance = math.dist(frame["ball"], actual["ball"])
    assert touch.t-kick["t"] == pytest.approx(math.ceil((.6+distance/17)*100)/100, abs=.011)
    assert kick["delivered_t"] >= called["t"]


@pytest.mark.parametrize("case", ["own_half", "equal_opponent", "equal_ball", "behind_ball", "no_touch",
                                  "corner", "throw_in", "goal_kick", "free_kick"])
@pytest.mark.parametrize("side", ["home", "away"])
def test_var_uses_kick_geometry_actual_involvement_and_only_direct_restart_exemptions(case, side):
    sim, receiver = simulator(side)
    passer = next(p for p in sim.on_pitch[side] if p.position == "RW")
    sim.keyframes.clear()
    sim.key(side, 70, 34, passer)
    snapshot = sim.prepare_offside_kick(side, passer, receiver, 70, 34, 94, 34)
    if case == "equal_opponent":
        defender = next(p for p in sim.on_pitch["away" if side == "home" else "home"] if p.position == "CB")
        snapshot["players"][defender.id] = sim.to_pitch(side, 91, 30)
        sim.keyframes[-1].player_positions[defender.id] = snapshot["players"][defender.id]
    own_x = {"own_half": 50, "equal_opponent": 91, "equal_ball": 70, "behind_ball": 69}.get(case)
    if own_x is not None:
        point = sim.to_pitch(side, own_x, 34)
        snapshot["players"][receiver.id] = point
        sim.keyframes[-1].player_positions[receiver.id] = point
    if case in {"corner", "throw_in", "goal_kick", "free_kick"}:
        sim.emit("set_piece", side, passer, 70, 34, kind=case)
    preparing = sim.emit("pass", side, passer, 70, 34, recipient_id=receiver.id, outcome="complete")
    sim.offside_kicks[preparing["id"]] = snapshot
    sim.t += 2
    if case != "no_touch":
        sim.key(side, 94, 34, receiver)
    shot = sim.emit("shot", side, receiver, 94, 34, body_part="right_foot")
    shot["preparing_pass_id"] = preparing["id"]
    assert sim.offside_preparing_pass(shot) is (case == "free_kick")


@pytest.mark.parametrize("side", ["home", "away"])
def test_missed_offside_is_prepared_before_a_real_completed_pass_without_a_public_verdict(side):
    class Forward(random.Random):
        def random(self):
            return .5

        def gauss(self, mu, sigma):
            return 20 if sigma == 9 else 0

    sim, holder = simulator(side)
    sim.rng, sim.detail_rng = Forward(1), Choice(0)
    receiver, _, _, kick, _ = sim.pass_(side, holder, 70, 34, .5)
    assert kick["id"] in sim.offside_kicks and kick["pass"]["outcome"] == "complete"
    assert not any(e["type"] == "offside" for e in sim.events)
    assert not any("offside" in key for key in kick if key != "id")
    tracker = Tracker(sim.export_match())
    frame = tracker.frame(kick["t"])
    attack_x = lambda x: x if tracker.attacks_right(side, kick["t"]) else 105-x
    rx = attack_x(next(p["x"] for p in frame["players"] if p["id"] == receiver.id))
    opponents = sorted((attack_x(p["x"]) for p in frame["players"] if p["team"] != side), reverse=True)
    assert rx > max(52.5, attack_x(frame["ball"][0]), opponents[1]) + 1
    assert sim.offside_kicks[kick["id"]]["t"] == kick["t"]
    assert tracker.frame(sim.t)["possession"]["holder_id"] == receiver.id


def test_var_cannot_cancel_an_onside_preparing_pass_merely_from_a_random_draw():
    sim, holder = simulator()
    passer = next(p for p in sim.on_pitch["home"] if p.id != holder.id and p.position != "GK")
    preparing = sim.emit("pass", "home", passer, 90, 34, recipient_id=holder.id, outcome="complete")
    shot = sim.emit("shot", "home", holder, 94, 34, body_part="right_foot")
    shot["preparing_pass_id"] = preparing["id"]
    sim.report("shot_result", shot_id=shot["id"], outcome="goal", team="home", player_id=holder.id)
    sim.score["home"] = 1
    sim.detail_rng = Choice(0)
    assert sim.var_goal_check(shot) is False
    assert sim.score["home"] == 1
    assert not any(e["type"] == "goal_cancelled" for e in sim.events)


@pytest.mark.parametrize("side", ["home", "away"])
def test_cancelled_goal_restarts_at_the_actual_offside_touch_not_the_later_shot(side):
    class Goal(random.Random):
        def random(self):
            return .1

    sim, receiver = simulator(side)
    passer = next(p for p in sim.on_pitch[side] if p.position == "RW")
    sim.keyframes.clear()
    sim.key(side, 70, 34, passer)
    snapshot = sim.prepare_offside_kick(side, passer, receiver, 70, 34, 94, 34)
    preparing = sim.emit("pass", side, passer, 70, 34, outcome="complete", recipient_id=receiver.id)
    sim.offside_kicks[preparing["id"]] = snapshot
    sim.t += 2
    sim.key(side, 94, 34, receiver)
    expected = sim.to_pitch(side, 94, 34)
    sim.rng, sim.true_chance = Goal(1), lambda *_: 1
    restarts = []
    sim.restart_free_kick = lambda team, x, y: restarts.append((team, sim.to_pitch(team, x, y)))
    sim.shot(side, receiver, 98, 34, preparing)
    assert restarts == [("away" if side == "home" else "home", expected)]
    assert sim.score[side] == 0


def test_offside_kick_snapshot_excludes_a_sent_off_keeper_even_before_lineup_cleanup():
    sim, receiver = simulator()
    passer = next(p for p in sim.on_pitch["home"] if p.position == "RW")
    keeper = sim.keeper("away")
    sim.sent_off.add(keeper.id)
    snapshot = sim.prepare_offside_kick("home", passer, receiver, 70, 34, 94, 34)
    assert keeper.id not in snapshot["opponents"] and keeper.id not in snapshot["players"]
    assert len(snapshot["opponents"]) == 10


def test_advantage_caution_waits_for_the_next_stop_without_advancing_play_or_redrawing():
    class Counted(random.Random):
        draws = 0
        delays = 0

        def random(self):
            self.draws += 1
            return .05

        def uniform(self, a, b):
            self.delays += 1
            return (a+b)/2

    sim, victim = simulator()
    offender = sim.opp_nearest("home", 70, 34)
    offence = sim.emit_offence("away", offender, 35, 34, victim, "trip", True, handball=False)
    sim.rng = Counted(1)
    before = sim.t
    sim.card_maybe("away", offender, .12, offence)
    assert sim.t == before and sim.ball_in_play
    assert not any(e["type"] == "card" for e in sim.events)
    assert not sim.yellows and not sim.sent_off
    assert (sim.rng.draws, sim.rng.delays) == (1, 1)
    sim.card_maybe("away", offender, .12, offence)  # a retry is the same decision
    sim.t += 2
    end = sim.emit("period_end", period_no=1)
    cards = [e for e in sim.events if e["type"] == "card"]
    assert len(cards) == 1 and cards[0]["offence_id"] == offence["id"]
    assert cards[0]["t"] >= end["t"] and cards[0]["stoppage_id"] == sim.play.stoppage_id
    assert sim.yellows[offender.id] == 1 and not sim.ball_in_play
    draws = (sim.rng.draws, sim.rng.delays)
    sim.stop(end)
    assert len([e for e in sim.events if e["type"] == "card"]) == 1
    # One decision, one delay, then the period-end/card packet latencies.
    assert (sim.rng.draws, sim.rng.delays) == draws == (1, 3)


@pytest.mark.parametrize("draw,already_booked,expected", [(.005, False, "red"), (.05, True, "second_yellow")])
def test_generic_advantage_is_not_applied_for_a_sending_off(draw, already_booked, expected):
    class Fixed(random.Random):
        def random(self):
            return draw

    sim, victim = simulator()
    offender = sim.opp_nearest("home", 70, 34)
    if already_booked:
        sim.yellows[offender.id] = 1
    sim.rng, sim.detail_rng = Fixed(1), Choice(1)
    sim.stoppage = lambda *_: None
    sim.restart_free_kick = lambda *_: None
    assert sim.foul("home", victim, 70, 34) is True
    offence = next(e for e in sim.events if e["type"] == "foul")
    card = next(e for e in sim.events if e["type"] == "card")
    assert offence["foul"]["advantage"] is False
    assert card["card"]["colour"] == expected and card["offence_id"] == offence["id"]
    assert card["stoppage_id"] and card["decision_id"]
    assert offence["t"] < card["t"] and not sim.ball_in_play
    assert offender.id in sim.sent_off and offender not in sim.on_pitch["away"]


def test_queued_caution_is_counted_when_deciding_a_second_caution():
    class Caution(random.Random):
        def random(self):
            return .05

    sim, victim = simulator()
    offender = sim.opp_nearest("home", 70, 34)
    first = sim.emit_offence("away", offender, 35, 34, victim, "trip", True, handball=False)
    sim.rng, sim.detail_rng = Caution(1), Choice(1)
    sim.card_maybe("away", offender, .12, first)
    assert not sim.yellows and not sim.sent_off
    sim.stoppage = lambda *_: None
    sim.restart_free_kick = lambda *_: None
    assert sim.foul("home", victim, 70, 34) is True
    cards = [e for e in sim.events if e["type"] == "card"]
    assert [e["card"]["colour"] for e in cards] == ["yellow", "second_yellow"]
    assert cards[0]["offence_id"] == first["id"]
    assert len({e["offence_id"] for e in cards}) == 2 and not sim.pending_cards
    assert offender.id in sim.sent_off


@pytest.mark.parametrize("already_sent_off", [False, True])
def test_pending_caution_is_not_lost_when_the_actor_leaves_and_never_duplicates_a_dismissal(already_sent_off):
    sim, victim = simulator()
    offender = sim.opp_nearest("home", 70, 34)
    offence = sim.emit_offence("away", offender, 35, 34, victim, "trip", True, handball=False)
    sim.card_maybe("away", offender, .12, offence, decision=("yellow", 5))
    sim.on_pitch["away"].remove(offender)  # the disciplinary identity is not a roster slot
    if already_sent_off:
        sim.sent_off.add(offender.id)
    sim.stop(offence)
    cards = [e for e in sim.events if e["type"] == "card"]
    assert len(cards) == int(not already_sent_off) and not sim.pending_cards
    if cards:
        assert cards[0]["player_id"] == offender.id and cards[0]["offence_id"] == offence["id"]
    assert offender not in sim.on_pitch["away"]


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


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("offside,cancelled", [(True, True), (False, False)])
def test_goal_review_links_the_actual_result_and_adjusts_only_a_cancelled_goal(side, offside, cancelled):
    sim, holder = simulator(side)
    opp = "away" if side == "home" else "home"
    passer = next(p for p in sim.on_pitch[side] if p.id != holder.id and p.position != "GK")
    sim.keyframes.clear()  # independent small setup: passer controls the ball
    sim.key(side, 70, 34, passer)
    snapshot = sim.prepare_offside_kick(side, passer, holder, 70, 34, 94, 34) if offside else None
    preparing = sim.emit("pass", side, passer, 70, 34, recipient_id=holder.id, outcome="complete")
    if snapshot:
        sim.offside_kicks[preparing["id"]] = snapshot
    sim.t += 2
    sim.key(side, 94, 34, holder)
    involvement = sim.t
    sim.t += .3
    sim.key(side, 94, 34, holder)
    shot = sim.emit("shot", side, holder, 94, 34, body_part="right_foot")
    shot["preparing_pass_id"] = preparing["id"]
    sim.t += 0.6
    result = sim.report("shot_result", shot_id=shot["id"], outcome="goal", team=side, player_id=holder.id)
    sim.score[side] = 1
    sim.stop(result, "goal")
    sim.detail_rng = Choice(0)  # a random draw alone must never invent the offence
    assert sim.var_goal_check(shot) is cancelled
    assert sim.score[side] == (0 if cancelled else 1)
    corrections = [e for e in sim.events if e["type"] == "goal_cancelled"]
    assert len(corrections) == int(cancelled)
    if cancelled:
        correction = corrections[0]
        by_id = {e["id"]: e for e in sim.events}
        decision = by_id[correction["decision_id"]]
        assert correction["shot_id"] == shot["id"] and correction["result_id"] == result["id"]
        assert decision["decision"] == "free_kick" and decision["team"] == opp
        offence = by_id[decision["trigger_event_id"]]
        assert offence["type"] == "offside" and offence["t"] == involvement
        assert offence["related"] == [preparing["id"]]
        tracker = Tracker(sim.export_match())
        frame = tracker.frame(preparing["t"])
        direction = lambda x: x if tracker.attacks_right(side, preparing["t"]) else 105-x
        rx = direction(next(p["x"] for p in frame["players"] if p["id"] == holder.id))
        opponents = sorted((direction(p["x"]) for p in frame["players"] if p["team"] == opp), reverse=True)
        assert rx > max(52.5, direction(frame["ball"][0]), opponents[1]) + 1


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
