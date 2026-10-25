"""Substitution invariants across simulation, feed and tracking consumers."""

import pytest

from vmi.generator.match import _Sim, generate_match
from vmi.generator.tracking import Tracker
from vmi.engine.model import MatchModel


@pytest.mark.parametrize("side", ["home", "away"])
def test_injured_keeper_replacement_can_take_goal_kick(side):
    sim = _Sim(12, "keeper-substitution")
    keeper = sim.keeper(side)
    replacement = sim.bench[side][0]
    sim.substitute(side, "injury", off=keeper)
    sim.goal_kick(side)
    assert sim.keeper(side).id == replacement.id
    assert len(sim.on_pitch[side]) == 11
    assert keeper not in sim.on_pitch[side]
    kick = next(e for e in sim.events if e["type"] == "set_piece" and e["set_piece"]["kind"] == "goal_kick")
    assert kick["player_id"] == replacement.id
    assert kick["set_piece"]["kind"] == "goal_kick"


def test_tactical_substitution_with_no_eligible_starter_preserves_state():
    sim = _Sim(12, "no-eligible-starter")
    sim.subbed_on = [p for p in sim.on_pitch["home"] if p.position != "GK"]
    roster = list(sim.on_pitch["home"])
    bench = list(sim.bench["home"])
    sim.substitute("home", "tactical")
    assert sim.on_pitch["home"] == roster
    assert sim.bench["home"] == bench
    assert sim.subs_done["home"] == 0
    assert sim.events == []


@pytest.mark.parametrize("side,keeper_id", [("home", "H1"), ("away", "A1")])
def test_injured_keeper_role_is_time_local_across_tracking_seek(side, keeper_id):
    # Seed 112 exposed the original bug in v1. Trigger the same injury directly
    # so a new generator version cannot silently remove this regression case.
    sim = _Sim(112, "keeper-injury-regression")
    sim.emit("period_start", period_no=1)
    sim.kick_off(side)
    sim.bench[side].sort(key=lambda p: p.position != "CB")
    sim.t = 100
    sim.substitute(side, "injury", off=sim.keeper(side))
    sim.goal_kick(side)
    sim.t = 5400
    match = sim.export_match()
    players = {p["id"]: p for team in match.meta["teams"].values() for p in team["players"]}
    substitution = next(e for e in match.events if e["type"] == "substitution"
                        and e["substitution"]["off_id"] == keeper_id)
    replacement = substitution["substitution"]["on_id"]
    # The initial roster must not reveal a future emergency role assignment.
    assert players[replacement]["position"] == "CB"
    tracker = Tracker(match)
    before = tracker.lineup(side, substitution["t"] - 0.01)
    after = tracker.lineup(side, substitution["t"])
    assert keeper_id in before and replacement not in before
    assert keeper_id not in after and replacement in after
    assert tracker.role_at(replacement, substitution["t"] - 0.01) == "CB"
    assert tracker.role_at(replacement, substitution["t"]) == "GK"
    assert sum(tracker.role_at(pid, substitution["t"]) == "GK" for pid in after) == 1
    # A reverse seek must restore the earlier role rather than retain GK.
    assert tracker.role_at(replacement, substitution["t"] - 0.01) == "CB"
    model = MatchModel(match.meta)
    assert model.player_role(replacement) == "CB"
    for event in match.events:
        if event["id"] == substitution["id"]:
            break
        model.ingest(event)
    assert model.player_role(replacement) == "CB"
    model.ingest(substitution)
    assert model.player_role(replacement) == "GK"
    assert MatchModel(match.meta).player_role(replacement) == "CB"
    assert match.duration >= 5400
