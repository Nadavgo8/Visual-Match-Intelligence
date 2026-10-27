"""Small scripted v2 segments for consumer tests; not a second match simulator."""

from copy import deepcopy
import hashlib
import math

from .analytics import delayed_xg
from .match import _Sim, Match

DEMO_CONFIGURATION = {"mode": "scripted_demo", "revision": "original-v1"}


class _PhysicalDemo(_Sim):
    """A bounded episode script using the same physical producer as seeded play.

    No ``name`` attribute: export must certify full body paths, not use the
    legacy consumer-fixture setup cuts below. Unshown bridges are for presenter
    cuts, not a claim to simulate every minute of professional football.
    """

    def __init__(self):
        super().__init__(2, "demo_0002_original_1")
        self.sub_plan = {"home": [], "away": []}
        self.drinks_due = {}

    def at(self, deadline):
        if self.t > deadline + .005:
            raise ValueError(f"physical demo deadline {deadline} is unreachable at {self.t}")
        self.hold_until(deadline)

    def player(self, side, number):
        return next(p for p in self.on_pitch[side] if p.number == number)

    def pass_to(self, side, receiver, ax, ay, *, kick_at=None, duration=2.5, header=False, setup=None):
        start = self.keyframes[-1]
        passer = next(p for p in self.on_pitch[side] if p.id == start.holder)
        point = self.to_pitch(side, ax, ay)
        if kick_at is not None:
            if self.contact_ready(receiver, point, kick_at+duration) > kick_at+duration+.005:
                raise ValueError("demo receiver cannot meet the reserved flight")
            self.at(kick_at)
        self.keyframes[-1].player_positions.update(setup or {})
        arrival = self.flight_plan(receiver, point, duration)
        self.keyframes[-1].player_positions.update(setup or {})
        departure = self.t
        if kick_at is not None and abs(departure-kick_at) > .005:
            raise ValueError("demo release cannot meet its reserved clock")
        start = self.keyframes[-1]
        start.flight_height = 2.5 if header else 0
        sx, sy = (start.x, start.y) if self.attacks_right(side) else (105-start.x, 68-start.y)
        self.t = arrival
        event = self.emit("pass", side, passer, sx, sy, t=departure, outcome="complete",
                          recipient_id=receiver.id, height="high" if header else "ground", cross=header)
        self.set_pass_end(event, side, ax, ay)
        self.key(side, ax, ay, receiver, effector="head" if header else "foot")
        if header:
            self.keyframes[-1].z = 1.65
        return event

    def carry_to(self, side, player, ax, ay):
        start = self.keyframes[-1]
        if start.holder != player.id:
            prior = next((p for squad in self.on_pitch.values() for p in squad if p.id == start.holder), None)
            if prior and prior.team == side:
                sx, sy = (start.x, start.y) if self.attacks_right(side) else (105-start.x, 68-start.y)
                self.pass_to(side, player, min(100, sx+3), sy)
            else:
                point = (start.x, start.y)
                self.hold_until(self.contact_ready(player, point, self.t))
                sx, sy = point if self.attacks_right(side) else (105-point[0], 68-point[1])
                self.key(side, sx, sy, player)
                if prior:
                    self.keyframes[-1].player_positions[prior.id] = point
                    self.keyframes[-1].contact_effectors[prior.id] = "foot"
                self.emit("tackle", side, player, sx, sy, outcome="won")
        start = self.keyframes[-1]
        self.t = self.contact_ready(player, self.to_pitch(side, ax, ay), self.t+1)
        self.key(side, ax, ay, player)
        self.record_carry(side, player, start, self.keyframes[-1])

    def onside_setup(self, side, receiver, ax, ay):
        """One covering defender and keeper, rather than a future VAR verdict."""
        opp = "away" if side == "home" else "home"
        defender = next(p for p in self.on_pitch[opp] if p.position == "CB")
        positions = {receiver.id: self.to_pitch(side, ax-7, ay),
                     defender.id: self.to_pitch(side, ax+2, 42)}
        actors = {p.id:p for squad in self.on_pitch.values() for p in squad}
        self.hold_until(max(self.contact_ready(actors[pid], point, self.t) for pid,point in positions.items()))
        self.keyframes[-1].player_positions.update(positions)
        return positions

    def goal(self, side, shooter, result_at, *, preparation=None, penalty=False, positions=None, facings=()):
        release = result_at-.6
        self.at(release)
        if penalty:
            action = self.emit("set_piece", side, shooter, 94, 34, kind="penalty")
            self.whistle(1, "short")
            self.restart(action)
        self.state(ball_in_play=True)
        current = self.keyframes[-1]
        ax, ay = (current.x, current.y) if self.attacks_right(side) else (105-current.x, 68-current.y)
        self.key(side, ax, ay, shooter, effector="foot" if penalty else "head")
        self.keyframes[-1].player_positions.update(positions or {})
        self.keyframes[-1].player_facings = facings
        self.keyframes[-1].z = 0 if penalty else 1.65
        self.keyframes[-1].flight_height = 1.0 if penalty else .8
        shot = self.emit("shot", side, shooter, ax, ay, body_part="right_foot" if penalty else "head",
                         penalty=penalty, related=[preparation["id"]] if preparation else None)
        if preparation:
            shot["preparing_pass_id"] = preparation["id"]
        self.events.append(delayed_xg(self.seed, shot, ax, ay, not penalty, self.xg_delay))
        self.t = result_at
        self.key(side, 105.5, 34, None, False)
        if penalty:
            keeper = self.keeper("away" if side == "home" else "home")
            # A late, unsuccessful lateral reaction: no invented ball contact.
            self.keyframes[-1].player_positions[keeper.id] = self.to_pitch(side, 105, 34.35)
            self.keyframes[-1].player_facings = tuple((pid, face) for pid, face in facings if pid == keeper.id)
        result = self.report("shot_result", shot_id=shot["id"], outcome="goal", team=side, player_id=shooter.id)
        self.score[side] += 1  # actual line crossing; never a post-hoc score patch
        self.stop(result, "goal")
        self.crowd_hit(.6, 22, hold=6)
        self.state(ball_in_play=False)
        return shot

    def build(self):
        self.emit("period_start", period_no=1)
        self.state(ball_in_play=False)
        self.kick_off("home")
        self.carry_to("home",self.player("home",8),58,24)
        self.pass_to("home",self.player("home",7),68,16,duration=3)
        self.carry_to("home",self.player("home",7),72,20)
        self.pass_to("home",self.player("home",10),60,42,duration=3)
        opening_end=self.t+5
        self.at(opening_end)

        # Ordinary called foul/yellow: a short physical encounter, then restart.
        self.at(580)
        victim, offender = self.player("home",7), self.player("away",6)
        self.carry_to("home", victim, 70, 34)
        self.hold_until(self.contact_ready(offender, self.to_pitch("home",70,34), self.t))
        self.key("home",70,34,victim)
        self.keyframes[-1].player_positions[offender.id] = self.to_pitch("home",70,34)
        self.keyframes[-1].contact_effectors[offender.id] = "foot"
        foul = self.emit_offence("away",offender,35,34,victim,"trip",False,handball=False)
        self.t += .3
        self.whistle()
        self.decide(foul,"free_kick","home")
        self.card_maybe("away",offender,1,foul,decision=("yellow",5))
        self.restart_free_kick("home",70,34)

        # A real mistimed run with a touch, separate from all three agreed goals.
        self.at(980)
        passer, receiver = self.player("home",7), self.player("home",9)
        self.carry_to("home",passer,70,34)
        snapshot = self.prepare_offside_kick("home",passer,receiver,70,34,90,34)
        arrival = self.flight_plan(receiver,(90,34),2)
        departure = self.t
        self.keyframes[-1].player_positions.update(snapshot["players"])
        self.keyframes[-1].flight_height = 0
        self.t = arrival
        passing = self.emit("pass","home",passer,70,34,t=departure,outcome="offside",recipient_id=receiver.id,height="ground")
        self.set_pass_end(passing,"home",90,34)
        self.key("home",90,34,receiver)
        self.t += .4
        self.whistle()
        call = self.emit("offside","home",receiver,90,34,related=[passing["id"]])
        passing["delivered_t"] = max(passing["delivered_t"],call["t"]+.75)
        self.restart_free_kick("away",15,34)

        # The momentum input is real 420s history, not a cropped fake state.
        self.at(1250)
        self.carry_to("away",self.player("away",6),48,34)
        for i in range(16):
            self.at(1260+i*25)
            player=self.player("away",8 if i%2==0 else 10)
            ax,ay=54+(i%3)*4,24 if i%2==0 else 44
            self.pass_to("away",player,ax,ay)
            self.carry_to("away",player,ax+3,ay+2)

        # A missed box foul, followed by ball-out and the original VAR reversal.
        self.at(2140)
        victim, offender = self.player("home",9), self.player("away",6)
        self.carry_to("home",victim,94,34)
        self.hold_until(self.contact_ready(offender,(94,34),self.t))
        self.key("home",94,34,victim)
        self.keyframes[-1].player_positions[offender.id]=(94,34)
        self.keyframes[-1].contact_effectors[offender.id]="foot"
        incident_t=self.t
        tackle=self.emit("tackle","away",offender,11,34,outcome="won")
        self.t += 1
        self.key("away",11,34,offender)
        self.emit("clearance","away",offender,11,34)
        self.keyframes[-1].flight_height=1.5
        self.t += 2
        self.key("away",11,-.5,None,False)
        self.whistle(2,"normal")
        original=self.decide(tackle,"no_penalty","away")
        self.state(ball_in_play=False)
        rid="demo_penalty_review"
        self.emit("var",related=[tackle["id"]],review_id=rid,phase="check",incident="penalty",
                  original_decision="no_penalty",outcome=None,incident_t=incident_t)
        self.at(2205)
        self.emit("var",review_id=rid,phase="on_field_review",incident="penalty",original_decision="no_penalty",outcome=None)
        self.at(2236)
        self.emit("var",review_id=rid,phase="decision",incident="penalty",original_decision="no_penalty",outcome="overturned")
        self.whistle(1,"long")
        foul=self.emit("foul","away",offender,11,34,t=incident_t,victim_id=victim.id,kind="trip",advantage=False,related=[tackle["id"]])
        foul["delivered_t"]=self.t+.75
        self.decide(foul,"penalty","home",supersedes=original["id"])
        positions,facings=self.penalty_setup("home",victim)
        self.goal("home",victim,2278,penalty=True,positions=positions,facings=facings)
        self.at(2310)
        self.kick_off("away")

        self.at(2570)
        passer,scorer=self.player("home",8),self.player("home",7)
        self.carry_to("home",passer,78,30)
        setup=self.onside_setup("home",scorer,94,30)
        passing=self.pass_to("home",scorer,94,30,kick_at=2610.9,duration=2.5,header=True,setup=setup)
        self.goal("home",scorer,2614,preparation=passing)
        self.at(2645)
        self.kick_off("away")
        self.at(2680)
        self.emit("added_time",minutes=3)
        self.at(2880)
        self.whistle(2,"long")
        self.emit("period_end",period_no=1)
        self.state(ball_in_play=False)
        self.at(2940)  # real source-time walking/setup interval; no pose reset
        self.period=2
        self.period_start_t=self.t
        self.clock_base=2700
        self.emit("period_start",period_no=2)
        self.kick_off("away")

        self.at(4095)
        passer,scorer=self.player("away",7),self.player("away",9)
        self.carry_to("away",passer,78,38)
        setup=self.onside_setup("away",scorer,94,38)
        passing=self.pass_to("away",scorer,94,38,kick_at=4144.9,duration=2.5,header=True,setup=setup)
        goal=self.goal("away",scorer,4148,preparation=passing)
        self.at(4180)
        self.emit("var",related=[goal["id"]],review_id="demo_goal_review",phase="check",incident="goal",original_decision="goal",outcome=None)
        self.at(4238)
        self.emit("var",review_id="demo_goal_review",phase="decision",incident="goal",original_decision="goal",outcome="stands")
        self.kick_off("home")
        self.at(max(4260,self.t+10))
        match=self.export_match()
        match.meta["configuration"]=dict(DEMO_CONFIGURATION)
        match.meta["demo_windows"]={"opening":[0,round(opening_end,2)],"foul":[580,650],
            "offside":[980,1030],"momentum_history":[1250,1670],"penalty_review":[2140,2290],
            "home_goal":[2595,2626],"away_goal":[4130,4160],"goal_review":[4180,4250]}
        return match


def generate_demo_match(seed=2):
    """The agreed 2-1 scripted demo; generic seeded matches remain independent."""
    if seed != 2:
        raise ValueError("the original physical demo uses seed 2")
    return _PhysicalDemo().build()

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
