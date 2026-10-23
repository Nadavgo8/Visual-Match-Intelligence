"""Small scripted v2 segments for consumer tests; not a second match simulator."""

from copy import deepcopy
import hashlib

from .analytics import delayed_xg
from .match import _Sim, Match

SCENARIOS = (
    "shots_reversed", "xg_missing", "xg_duplicate", "source_late", "source_missing",
    "carry", "dribble_complete", "dribble_failed", "dribble_interrupted", "dribble_unresolved",
    "handball", "penalty_no_card", "penalty_card", "penalty_late_card",
    "assist", "assist_source_late", "no_goal", "rebound", "goal_cancelled", "drinks_break",
)


class _Segment(_Sim):
    def __init__(self, seed: int, name: str):
        opaque = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        super().__init__(seed, f"segment_{seed}_{opaque}")
        self.name = name
        self.expected_anomalies: list[str] = []
        self.emit("period_start", period_no=1)
        self.kick_off("home")
        self.attacker = next(p for p in self.on_pitch["home"] if p.number == 9)
        self.defender = next(p for p in self.on_pitch["away"] if p.number == 4)

    def place(self, side, player, ax, ay):
        if player not in self.on_pitch[side]:
            raise ValueError("scenario holder must be active")
        self.key(side, ax, ay, player, in_play=self.ball_in_play)
        self.carrier = (side, player, ax, ay)

    def prepared_pass(self):
        passer = next(p for p in self.on_pitch["home"] if p.number == 11)
        self.place("home", passer, 85, 34)
        p = self.emit("pass", "home", passer, 85, 34, outcome="complete",
                      recipient_id=self.attacker.id, height="ground", end_location=[94, 34])
        self.t += 1
        self.place("home", self.attacker, 94, 34)
        return p

    def attempt(self, outcome="saved", preparation=None, penalty=False):
        self.place("home", self.attacker, 94, 34)
        self.keyframes[-1].flight_height = 1.5
        e = self.emit("shot", "home", self.attacker, 94, 34, body_part="right_foot", penalty=penalty,
                      related=[preparation["id"]] if preparation else None)
        if preparation:
            e["preparing_pass_id"] = preparation["id"]
        self.events.append(delayed_xg(self.seed, e, 94, 34, False, self.xg_delay))
        self.t += 0.6
        result = self.report("shot_result", shot_id=e["id"], outcome=outcome,
                             team="home", player_id=self.attacker.id)
        if outcome == "goal":
            self.key("home", 105.5, 34, None, False)
            self.score["home"] += 1
            self.stop(result, "goal")
            self.state(ball_in_play=False)
        elif outcome == "saved":
            keeper = self.keeper("away")
            self.place("away", keeper, 3, 34)
        else:
            self.key("home", 105.5, 44, None, False)
            self.stoppage(0)
        return e, result

    def dribble(self, outcome: str):
        if outcome not in {"complete", "failed", "interrupted", "unresolved"}:
            raise ValueError("unsupported dribble outcome")
        self.place("home", self.attacker, 70, 34)
        start_t = self.t
        self.keyframes[-1].player_positions[self.defender.id] = (74, 34)
        pid = self.play.possession("home")
        self.t += 1
        self.key("home", 73, 34, self.attacker)
        self.keyframes[-1].player_positions[self.defender.id] = (74, 34)
        self.t += 1
        holder = self.attacker if outcome == "complete" else self.defender if outcome == "failed" else None
        self.key("home", 77, 34, holder, in_play=outcome != "interrupted")
        self.keyframes[-1].player_positions[self.defender.id] = (77, 34) if outcome == "failed" else (74, 35)
        e = self.emit("dribble", "home", self.attacker, 70, 34, outcome=outcome,
                      defender_id=self.defender.id, end_location=[77, 34], possession_id=pid,
                      start_t=round(start_t, 2), end_t=round(self.t, 2))
        e["possession_id"] = e["dribble"].pop("possession_id")
        if outcome == "failed":
            self.play.possession("away", force=True)
            self.emit("ball_recovery", "away", self.defender, 28, 34, related=[e["id"]])
        elif outcome == "interrupted":
            self.whistle()
            foul = self.emit("foul", "away", self.defender, 28, 34, advantage=False,
                             victim_id=self.attacker.id, kind="trip", related=[e["id"]])
            self.decide(foul, "free_kick", "home")
            e["dribble"]["foul_id"] = foul["id"]
            self.state(ball_in_play=False)
        elif outcome == "unresolved":
            self.report("ball_loose", related=[e["id"]])
        return e

    def offence(self, handball=False, penalty=False):
        self.place("home", self.attacker, 94 if penalty else 75, 34)
        self.whistle()
        kind = "handball" if handball else "foul"
        q = {"offence": True} if handball else {"advantage": False, "kind": "trip", "victim_id": self.attacker.id}
        e = self.emit(kind, "away", self.defender, 11 if penalty else 30, 34, **q)
        self.decide(e, "penalty" if penalty else "free_kick", "home")
        self.state(ball_in_play=False)
        return e

    def card(self, offence, late=False):
        self.t += 1
        card = self.emit("card", "away", self.defender, colour="yellow", related=[offence["id"]])
        card["offence_id"] = offence["id"]
        self.cards["away"]["yellow"] += 1
        if late:
            card["delivered_t"] = round(self.t + 20, 2)
        self.state()

    def penalty_attempt(self, variant):
        offence = self.offence(penalty=True)
        if variant != "penalty_no_card":
            self.card(offence, late=variant == "penalty_late_card")
        self.t += 10
        self.whistle()
        self.emit("set_piece", "home", self.attacker, 94, 34, kind="penalty")
        action = self.events[-1]
        self.restart(action)
        action["possession_id"] = self.play.possession_id
        self.state(ball_in_play=True)
        self.attempt("goal", penalty=True)

    def drinks(self):
        self.key("home", 105, 0, None, False)
        out = self.report("ball_out")
        self.stop(out, "ball_out")
        self.decide(out, "corner", "home")
        pending = self.play.restart_id
        self.report("drinks_break", stoppage_id=self.play.stoppage_id, restart_id=pending,
                    reason="drinks_break", trigger_event_id=out["id"])
        self.state(ball_in_play=False)
        self.t += 60
        self.state(ball_in_play=False)
        self.emit("set_piece", "home", self.attacker, 104.5, 0.5, kind="corner")
        self.state(ball_in_play=True)
        self.place("home", self.attacker, 104.5, 0.5)

    def finish(self) -> Match:
        last_delivery = max(e["delivered_t"] for e in self.events)
        self.t = max(self.t + 12, last_delivery + 2)
        k = self.keyframes[-1]
        self.keyframes.append(deepcopy(k))
        self.keyframes[-1].t = self.t
        match = self.export_match()
        match.meta.update(scenario=self.name, expected_anomalies=self.expected_anomalies)
        return match


def generate_scenario(name: str, seed: int = 12) -> Match:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {name}")
    s = _Segment(seed, name)
    if name == "carry":
        s.place("home", s.attacker, 65, 34)
        start_t = s.t
        s.t += 3
        s.place("home", s.attacker, 75, 34)
        s.emit("carry", "home", s.attacker, 65, 34, end_location=[75, 34], start_t=round(start_t, 2), end_t=round(s.t, 2))
    elif name.startswith("dribble_"):
        s.dribble(name.removeprefix("dribble_"))
    elif name.startswith("penalty_"):
        s.penalty_attempt(name)
    elif name == "handball":
        s.offence(handball=True)
    elif name == "drinks_break":
        s.drinks()
    elif name in {"assist", "assist_source_late", "no_goal", "goal_cancelled"}:
        p = s.prepared_pass()
        shot, result = s.attempt("saved" if name == "no_goal" else "goal", p)
        if name == "assist_source_late":
            p["delivered_t"] = round(s.t + 5, 2)
        if name == "goal_cancelled":
            s.t += 4
            offside = s.emit("offside", "home", s.attacker, 94, 34)
            decision = s.decide(offside, "free_kick", "away")
            s.report("goal_cancelled", shot_id=shot["id"], result_id=result["id"],
                     decision_id=decision["id"], team="home", player_id=s.attacker.id)
            s.score["home"] -= 1
            s.state()
    elif name == "rebound":
        s.attempt("saved", s.prepared_pass())
        s.t += 1
        s.emit("ball_recovery", "home", s.attacker, 94, 34)
        s.attempt("goal")  # deliberately no preparing pass on a rebound
    else:
        shot, _ = s.attempt("saved")
        if name == "shots_reversed":
            s.t += 1
            s.emit("ball_recovery", "home", s.attacker, 94, 34)
            second, _ = s.attempt("goal")
            analytics = {e["shot_id"]: e for e in s.events if e["type"] == "shot_xg"}
            for parent, delay in ((shot, 5), (second, 2)):
                e = analytics[parent["id"]]
                e["t"] = round(parent["t"] + delay, 2)
                e["delivered_t"] = round(e["t"] + 0.2, 2)
        elif name == "xg_missing":
            s.events = [e for e in s.events if e["type"] != "shot_xg"]
            s.expected_anomalies.append("missing_xg")
        elif name == "xg_duplicate":
            s.events.append(deepcopy(next(e for e in s.events if e["type"] == "shot_xg")))
            s.expected_anomalies.append("duplicate_event")
        elif name == "source_late":
            shot["delivered_t"] = round(s.t + 7, 2)
        elif name == "source_missing":
            s.events.remove(shot)
            s.expected_anomalies.append("missing_source")
    return s.finish()
