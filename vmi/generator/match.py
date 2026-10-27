"""Seeded match truth with separate v2 event, motion and delayed analytics exports."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

from .teams import Player, Team, make_teams
from .analytics import chance_quality, delayed_xg
from .export import finish_export
from .motion import Keyframe, PLAYER_SPEED, formation_position
from .physics import CONTACT_REACH, reach as physical_reach, travel_time, stage_physical_players
from .state import PlayState

PITCH_X, PITCH_Y = 105.0, 68.0
BOX_X = PITCH_X - 16.5
BOX_Y = (13.84, 54.16)
HT_GAP = 60.0  # half-time compressed to 60 s on the timeline
SCHEMA_VERSION = "2.0"
GENERATOR_VERSION = "2.5.0"


def _other(side: str) -> str:
    return "away" if side == "home" else "home"


@dataclass
class _Impulse:
    t: float
    amp: float
    decay: float  # seconds to fall to ~37%
    hold: float = 0.0  # seconds at full amplitude before decaying


@dataclass
class Match:
    meta: dict
    events: list[dict] = field(default_factory=list)  # feed + whistle records
    crowd: list[dict] = field(default_factory=list)
    match_state: list[dict] = field(default_factory=list)
    keyframes: list[Keyframe] = field(default_factory=list)
    player_paths: dict = field(default_factory=dict)  # private physical trajectories

    @property
    def duration(self) -> float:
        return self.meta["end_t"]


class _Sim:
    def __init__(self, seed: int, match_id: str, xg_delay: tuple[float, float] = (2, 5)):
        self.rng = random.Random(seed)
        self.detail_rng = random.Random(seed ^ 0xD12026)
        self.drinks_due = {period: minute * 60 for period, minute in ((1, 22), (2, 67))
                           if self.detail_rng.random() < 0.25}
        self.seed = seed
        self.match_id = match_id
        self.teams: dict[str, Team] = make_teams()
        self.initial_roles = {p.id: p.position for team in self.teams.values()
                              for p in [*team.players, *team.bench]}
        self.initial_bases = {p.id: (p.base_x, p.base_y) for team in self.teams.values()
                              for p in [*team.players, *team.bench]}
        self.on_pitch: dict[str, list[Player]] = {s: list(t.players) for s, t in self.teams.items()}
        self.bench: dict[str, list[Player]] = {s: list(t.bench) for s, t in self.teams.items()}
        self.events: list[dict] = []
        self.states: list[dict] = []
        self.keyframes: list[Keyframe] = []
        self.impulses: list[_Impulse] = []
        self.murmurs: list[tuple[float, float, float]] = []  # (start, end, depth)
        self.pressure_spans: list[tuple[float, float]] = []  # ball in a final third
        self.t = 0.0
        self.period = 1
        self.period_start_t = 0.0
        self.clock_base = 0.0
        self.score = {"home": 0, "away": 0}
        self.yellows: dict[str, int] = {}
        self.sent_off: set[str] = set()
        self.cards = {"home": {"yellow": 0, "red": 0}, "away": {"yellow": 0, "red": 0}}
        self.subs_done = {"home": 0, "away": 0}
        self.sub_plan = {
            s: sorted(self.rng.uniform(55, 86) * 60 for _ in range(self.rng.choice([2, 3, 3])))
            for s in ("home", "away")
        }
        self.n = 0
        self.ball_in_play = False
        self.subbed_on: list[Player] = []
        self.play = PlayState()
        self.xg_delay = xg_delay
        self.aux_n = 0
        self.stop_whistle: dict | None = None

    def report(self, etype: str, *, t: float | None = None, **fields) -> dict:
        """Extra v2 records use a separate clock/id/RNG path from match outcomes."""
        self.aux_n += 1
        at = self.t if t is None else t
        rec = {"id": f"aux_{self.aux_n:05d}", "match_id": self.match_id,
               "schema_version": SCHEMA_VERSION, "source": "event_feed", "type": etype,
               "t": round(at, 2), "delivered_t": round(at + 0.75, 2),
               "period": self.period, "clock": self.clock_str(at), "team": None,
               "player_id": None, **fields}
        self.events.append(rec)
        if etype=="pass" and not hasattr(self,"name"):
            rec["delivered_t"]=round(max(at,self.t)+.75,2)
        return rec

    def stop(self, trigger: dict, reason: str = "unknown"):
        if self.play.stoppage_id is not None:
            return
        origin = self.stop_whistle or trigger
        stopped = self.report("play_stopped", trigger_event_id=origin["id"],
                              reason="unknown" if self.stop_whistle else reason)
        self.play.stoppage_id = stopped["id"]
        self.play.trigger_event_id = origin["id"]
        self.ball_in_play = False
        self.play.restart_id = None
        self.play.possession_team = None
        if self.keyframes:
            k = self.keyframes[-1]
            self.keyframes.append(Keyframe(round(self.t, 2), k.x, k.y, None, False,
                                           player_positions=dict(k.player_positions)))

    def decide(self, trigger: dict, kind: str, team: str, *, supersedes: str | None = None):
        self.stop(trigger)
        decision = self.report("referee_decision", trigger_event_id=trigger["id"],
                               stoppage_id=self.play.stoppage_id, decision=kind, team=team,
                               whistle_id=self.stop_whistle["id"] if self.stop_whistle else None,
                               supersedes_decision_id=supersedes)
        self.play.decision_id = decision["id"]
        trigger["stoppage_id"] = self.play.stoppage_id
        trigger["trigger_event_id"] = self.play.trigger_event_id
        if kind != "no_penalty":
            award = self.report("restart_awarded", stoppage_id=self.play.stoppage_id,
                                decision_id=decision["id"], restart_kind=kind, team=team)
            self.play.restart_id = award["id"]
        return decision

    def restart(self, action: dict):
        kind = action["set_piece"]["kind"]
        if self.play.stoppage_id is None:
            self.stop(action, "period_start" if kind == "kick_off" else "ball_out")
        decision = self.play.decision_id
        if decision is None:
            decision = self.decide(action, kind, action["team"])["id"]
        awarded = next((e for e in self.events if e["id"] == self.play.restart_id), None)
        if awarded is None:
            awarded = self.report("restart_awarded", stoppage_id=self.play.stoppage_id,
                                  decision_id=decision, restart_kind=kind, team=action["team"])
        action["restart_id"] = awarded["id"]
        action["stoppage_id"] = self.play.stoppage_id
        action["trigger_event_id"] = self.play.trigger_event_id
        action["whistle_id"] = self.stop_whistle["id"] if self.stop_whistle else None
        taken = self.report("restart_taken", stoppage_id=self.play.stoppage_id,
                            restart_id=awarded["id"], decision_id=decision,
                            action_event_id=action["id"], team=action["team"])
        self.play.restart_id = None
        self.play.stoppage_id = None
        self.play.decision_id = None
        self.stop_whistle = None
        self.play.possession(action["team"], force=True)
        self.play.play_context = kind

    # ---------- coordinates and time ----------
    def attacks_right(self, side: str) -> bool:
        return (side == "home") == (self.period == 1)

    def to_pitch(self, side: str, ax: float, ay: float) -> tuple[float, float]:
        if self.attacks_right(side):
            return ax, ay
        return PITCH_X - ax, PITCH_Y - ay

    def clock_s(self, t: float | None = None) -> float:
        t = self.t if t is None else t
        return self.clock_base + (t - self.period_start_t)

    def clock_str(self, t: float | None = None) -> str:
        s = self.clock_s(t)
        regular_end = 2700 if self.period == 1 else 5400
        if s > regular_end:
            extra = s - regular_end
            return f"{int(regular_end // 60)}+{int(extra // 60) + 1}'"
        return f"{int(s // 60)}:{int(s % 60):02d}"

    # ---------- emitters ----------
    def _id(self) -> str:
        self.n += 1
        return f"evt_{self.n:04d}"

    def emit(self, etype: str, team: str | None = None, player: Player | None = None,
             ax: float | None = None, ay: float | None = None, t: float | None = None,
             related: list[str] | None = None, **qualifiers) -> dict:
        t = self.t if t is None else t
        rec = {
            "id": self._id(), "match_id": self.match_id, "source": "event_feed",
            "period": self.period, "t": round(t, 2), "clock": self.clock_str(t),
            "type": etype, "team": team, "player_id": player.id if player else None,
        }
        if ax is not None and team is not None:
            x, y = self.to_pitch(team, ax, ay)
            # operator logging error, about +-1 m
            rec["location"] = [round(min(max(x + self.rng.gauss(0, 0.5), 0), PITCH_X), 1),
                               round(min(max(y + self.rng.gauss(0, 0.5), 0), PITCH_Y), 1)]
        if related:
            rec["related"] = related
        if qualifiers:
            rec[etype] = qualifiers
        # feed latency: logged and delivered after the fact
        rec["delivered_t"] = round(t + self.rng.uniform(0.5, 3.0), 2)
        if etype=="pass" and not hasattr(self,"name"):
            rec["delivered_t"]=round(max(t,self.t)+rec["delivered_t"]-round(t,2),2)
        self.events.append(rec)
        rec["schema_version"] = SCHEMA_VERSION
        if etype == "set_piece" and qualifiers.get("kind") != "penalty":
            self.restart(rec)
        if etype == "var" and self.play.stoppage_id:
            rec["stoppage_id"] = self.play.stoppage_id
            rec["trigger_event_id"] = self.play.trigger_event_id
        if etype in {"pass", "shot", "tackle", "interception", "ball_recovery", "save", "set_piece"} and team:
            rec["possession_id"] = self.play.possession(team)
            rec["play_context"] = self.play.play_context
        if etype in {"offside", "period_end", "injury_stoppage"}:
            self.stop(rec, etype)
            rec["stoppage_id"] = self.play.stoppage_id
            rec["trigger_event_id"] = self.play.trigger_event_id
        if etype == "card":
            rec["decision_id"] = self.play.decision_id
            rec["stoppage_id"] = self.play.stoppage_id
        return rec

    def whistle(self, blasts: int = 1, length: str = "short", t: float | None = None) -> dict:
        t = self.t if t is None else t
        rec = {
            "id": self._id(), "match_id": self.match_id, "source": "audio",
            "period": self.period, "t": round(t, 2), "clock": self.clock_str(t),
            "type": "whistle",
            "whistle": {"blasts": blasts, "length": length,
                        "confidence": round(self.rng.uniform(0.82, 0.99), 2)},
            "delivered_t": round(t + self.rng.uniform(0.1, 0.3), 2),
        }
        self.events.append(rec)
        rec["schema_version"] = SCHEMA_VERSION
        self.stop_whistle = rec
        return rec

    def state(self, **changes):
        if "ball_in_play" in changes:
            self.ball_in_play = changes["ball_in_play"]
        self.states.append({
            "stream": "match_state", "match_id": self.match_id, "source": "event_feed", "t": round(self.t, 2),
            "period": self.period, "clock": self.clock_str(),
            "score": dict(self.score), "ball_in_play": self.ball_in_play,
            "cards": {s: dict(c) for s, c in self.cards.items()},
            "on_pitch": {s: len(p) for s, p in self.on_pitch.items()},
            "active_stoppage_id": self.play.stoppage_id,
            "pending_restart_id": self.play.restart_id if not self.ball_in_play else None,
            "quality": {"status": "measured", "confidence": 1.0},
        })

    def key(self, side: str, ax: float, ay: float, holder: Player | None, in_play: bool = True, *, effector=None):
        if holder and not hasattr(self, "name"):
            self.t = self.contact_ready(holder, self.to_pitch(side, ax, ay), self.t)
        self.t = round(self.t, 2)
        x, y = self.to_pitch(side, ax, ay)
        inherited = self.keyframes[-1] if self.keyframes else None
        if holder and effector is None:
            effector = (
                inherited.contact_effectors.get(holder.id, "foot")
                if inherited and inherited.holder == holder.id
                else "foot"
            )
        self.keyframes.append(
            Keyframe(
                round(self.t, 2),
                round(x, 2),
                round(y, 2),
                holder.id if holder else None,
                in_play,
                possession_id=self.play.possession(holder.team) if holder and in_play else None,
            )
        )
        if holder:
            self.keyframes[-1].contact_effectors[holder.id] = effector
            if inherited and inherited.holder == holder.id and effector == "hands":
                self.keyframes[-1].z = inherited.z

    def crowd_hit(self, amp: float, decay: float, dt: float = 0.0, hold: float = 0.0):
        self.impulses.append(_Impulse(self.t + dt, amp, decay, hold))

    # ---------- squad helpers ----------
    def shifted(self, side: str, p: Player, ball_ax: float) -> tuple[float, float]:
        shift = (ball_ax - 52.5) * 0.45 if p.position != "GK" else 0
        return min(max(p.base_x + shift, 3), 100), p.base_y

    def nearest(self, side: str, ax: float, ay: float, exclude: Player | None = None,
                outfield: bool = True) -> Player:
        best, bd = None, 1e9
        for p in self.on_pitch[side]:
            if p is exclude or (outfield and p.position == "GK"):
                continue
            px, py = self.shifted(side, p, ax)
            d = (px - ax) ** 2 + (py - ay) ** 2
            if d < bd:
                best, bd = p, d
        return best

    def opp_nearest(self, side: str, ax: float, ay: float) -> Player:
        """Nearest opponent to a point given in `side`'s attack coordinates."""
        opp = _other(side)
        return self.nearest(opp, PITCH_X - ax, PITCH_Y - ay)

    def keeper(self, side: str) -> Player:
        return next(p for p in self.on_pitch[side] if p.position == "GK")

    # ---------- the match ----------
    def run(self) -> Match:
        added = [self.rng.randint(1, 4), self.rng.randint(3, 6)]
        first = self.rng.choice(["home", "away"])
        self.state(ball_in_play=False)
        for period in (1, 2):
            self.period = period
            self.period_start_t = self.t
            self.clock_base = 0.0 if period == 1 else 2700.0
            self.emit("period_start", period_no=period)
            end_clock = self.clock_base + 2700 + added[period - 1] * 60
            kicker = first if period == 1 else _other(first)
            self.kick_off(kicker)
            announced = False
            while self.clock_s() < end_clock:
                if not announced and self.clock_s() >= self.clock_base + 2700 - 20:
                    self.emit("added_time", minutes=added[period - 1])
                    announced = True
                self.play_possession()
            if not announced:
                # A long possession, review or substitution can cross the
                # announcement window before control returns to this loop.
                # Place the scheduled announcement on its source clock; do not
                # omit it or announce injury time after the final whistle.
                self.emit("added_time", t=self.period_start_t + 2680, minutes=added[period - 1])
            # end of period
            self.whistle(blasts=2 if period == 1 else 3, length="long")
            self.emit("period_end", period_no=period)
            self.state(ball_in_play=False)
            self.keyframes.append(
                replace(
                    self.keyframes[-1],
                    t=round(self.t, 2),
                    holder=None,
                    in_play=False,
                    flight_height=0,
                    player_positions=dict(self.keyframes[-1].player_positions),
                    contact_effectors=dict(self.keyframes[-1].contact_effectors),
                )
            )
            if period == 1:
                self.t += HT_GAP
        self.t += 5
        return self.export_match()

    def export_match(self) -> Match:
        """Export either a full match or a short deterministic scenario."""
        crowd = self.build_crowd()
        teams_meta = {
            s: {
                "name": tm.name,
                "short": tm.short,
                "colour": tm.colour,
                "players": [
                    vars(p)
                    | {
                        "starter": starter,
                        "position": self.initial_roles[p.id],
                        "base_x": self.initial_bases[p.id][0],
                        "base_y": self.initial_bases[p.id][1],
                    }
                    for starter, squad in ((True, tm.players), (False, tm.bench))
                    for p in squad
                ],
            }
            for s, tm in self.teams.items()
        }
        meta = {
            "schema_version": SCHEMA_VERSION,
            "match_id": self.match_id,
            "seed": self.seed,
            "generator_version": GENERATOR_VERSION,
            "synthetic": True,
            "pitch": [PITCH_X, PITCH_Y],
            "teams": teams_meta,
            "end_t": round(self.t, 2),
            "final_score": dict(self.score),
            "home_attacks_right_in_period": {"1": True, "2": False},
        }
        finish_export(self.events, self.states, crowd)
        # Physical staging must not feed its derived body positions back into
        # simulation or treat them as new hard anchors on a second export.
        keys = [
            replace(k, player_positions=dict(k.player_positions), contact_effectors=dict(k.contact_effectors))
            for k in self.keyframes
        ]
        match = Match(meta, self.events, crowd, self.states, keys)
        # Scripted fixtures deliberately retain their documented setup cuts;
        # ordinary matches freeze full continuous player paths in source truth.
        if not hasattr(self, "name"):
            stage_physical_players(match)
            meta["motion_model"] = "source-paths-2"
        return match

    def kick_off(self, side: str):
        if hasattr(self, "name"):
            self.key(side, 52.5, 34, None, in_play=False)
            self.t += self.rng.uniform(2, 4)
            self.whistle(1, "short")
            # These short event/latency fixtures have documented setup cuts;
            # preserve their intentionally isolated parent-event ordering.
            st = self.nearest(side, 52.5, 34)
            self.emit("set_piece", side, st, 52.5, 34, kind="kick_off")
            self.state(ball_in_play=True)
            self.key(side, 52.5, 34, st)
            self.carrier = (side, st, 52.5, 34.0)
            return
        self.set_restart_ball(side, 52.5, 34)
        self.t += self.rng.uniform(2, 4)
        self.whistle(1, "short")
        self.restart_pass(side, "kick_off", 52.5, 34, prepared=True)

    def stoppage(self, seconds: float):
        """Ball out of play; also the moment pending substitutions are made."""
        if self.play.stoppage_id is None:
            trigger = self.report("ball_out")
            self.stop(trigger, "ball_out")
        self.state(ball_in_play=False)
        self.t += seconds
        self.maybe_subs()

    def maybe_subs(self):
        for side in ("home", "away"):
            plan = self.sub_plan[side]
            while plan and self.clock_s() >= plan[0] and self.period == 2 and self.bench[side]:
                plan.pop(0)
                self.substitute(side, reason="tactical")

    def substitute(self, side: str, reason: str, off: Player | None = None):
        if not self.bench[side] or self.subs_done[side] >= 5:
            return
        cands = [p for p in self.on_pitch[side] if p.position != "GK" and p not in self.subbed_on]
        if off is None:
            if not cands:
                return
            # tired attackers and midfielders come off first
            cands.sort(key=lambda p: -p.base_x + self.rng.uniform(0, 30))
            off = cands[0]
        if off not in self.on_pitch[side]:
            return
        on = self.bench[side].pop(0)
        self.subbed_on.append(on)
        on.base_x, on.base_y = off.base_x, off.base_y
        # Injury substitutions can replace the keeper with a bench outfielder.
        # Preserve the occupied role, as we already preserve its coordinates.
        if off.position == "GK":
            on.position = "GK"
        idx = self.on_pitch[side].index(off)
        self.on_pitch[side][idx] = on
        self.subs_done[side] += 1
        self.t += self.rng.uniform(20, 35)
        self.emit("substitution", side, on, off_id=off.id, on_id=on.id, reason=reason)
        self.state()

    # A possession is a chain of actions by one team until it loses the ball
    # or play stops.
    def play_possession(self):
        side, holder, ax, ay = self.carrier
        rng = self.rng
        strength = self.teams[side].strength
        chain_start = self.t
        last_pass: dict | None = None
        last_pass_cross = False
        for _ in range(40):
            if self.clock_s() >= self.clock_base + 2700 + 7 * 60:
                return
            # carry a little before acting
            start = self.keyframes[-1]
            hold = rng.uniform(0.6, 2.2)
            old_ax, old_ay = ax, ay
            ax = min(ax + rng.uniform(0, 3.0), 101)
            ay = min(max(ay + rng.gauss(0, 1.5), 1), 67)
            distance = math.hypot(ax - old_ax, ay - old_ay)
            if distance > PLAYER_SPEED * hold:
                ratio = PLAYER_SPEED * hold / distance
                ax, ay = old_ax + (ax - old_ax) * ratio, old_ay + (ay - old_ay) * ratio
            self.t = math.ceil((self.t + hold) * 100) / 100
            self.key(side, ax, ay, holder)
            self.record_carry(side, holder, start, self.keyframes[-1])
            if ax > 70:
                self.pressure_spans.append((self.t - hold, self.t))

            central = abs(ay - 34) < 20
            shot_p = 0.0
            if ax > 83 and central:
                shot_p = 0.11 + 0.22 * (ax - 83) / 22
            elif ax > 74 and abs(ay - 34) < 14:
                shot_p = 0.035
            in_box = ax >= BOX_X and BOX_Y[0] <= ay <= BOX_Y[1]
            foul_p = 0.007 if in_box else 0.022 + (0.03 if ax > 70 else 0)
            tackle_p = 0.075 + (0.05 if ax > 70 else 0) - 0.04 * (strength - 0.5)
            r = rng.random()
            if r < shot_p:
                self.shot(side, holder, ax, ay, last_pass, header=last_pass_cross)
                return
            r -= shot_p
            if r < foul_p:
                if self.foul(side, holder, ax, ay):
                    return
                continue
            r -= foul_p
            if r < tackle_p:
                tackler = self.opp_nearest(side, ax, ay)
                kind = rng.choice(["tackle", "tackle", "interception"])
                self.t = self.contact_ready(tackler, self.to_pitch(side, ax, ay), self.t)
                self.key(side, ax, ay, tackler)
                self.emit(kind, _other(side), tackler, PITCH_X - ax, PITCH_Y - ay,
                          outcome="won")
                self.carrier = (_other(side), tackler, PITCH_X - ax, PITCH_Y - ay)
                return
            # pass
            if holder.position != "GK" and self.detail_rng.random() < 0.012:
                outcome = self.detail_rng.choices(
                    ["complete", "failed", "interrupted", "unresolved"], [60, 25, 10, 5])[0]
                carried = self.attempt_dribble(side, holder, ax, ay, outcome)
                if carried is None:
                    return
                holder, ax, ay = carried
                continue
            res = self.pass_(side, holder, ax, ay, strength)
            if res is None:
                return
            holder, ax, ay, last_pass, last_pass_cross = res
        self.carrier = (side, holder, ax, ay)

    def record_carry(self, side, holder, start, end):
        """Report completed observed movement, independently of outcome RNG."""
        if (holder.position == "GK" or not start.in_play or not end.in_play
                or start.holder != holder.id or end.holder != holder.id
                or end.t <= start.t or math.hypot(end.x - start.x, end.y - start.y) < 1):
            return None
        return self.report("carry", team=side, player_id=holder.id,
                           location=[start.x, start.y], possession_id=start.possession_id,
                           play_context=self.play.play_context,
                           carry={"start_t": start.t, "end_t": end.t,
                                  "end_location": [end.x, end.y]})

    def attempt_dribble(self, side, holder, ax, ay, outcome):
        """Simulate the encounter first; the renderer only receives its tracking."""
        if outcome not in {"complete", "failed", "interrupted", "unresolved"}:
            raise ValueError("unsupported dribble outcome")
        if not self.ball_in_play or holder.position == "GK":
            raise ValueError("a dribble requires an active outfield carrier")
        opponent = _other(side)
        defender = self.opp_nearest(side, ax, ay)
        entry = self.keyframes[-1]
        position = entry.player_positions.get(
            defender.id,
            formation_position(
                defender.base_x,
                defender.base_y,
                defender.position,
                defender.id,
                self.attacks_right(opponent),
                entry.x,
                entry.y,
                entry.t,
            ),
        )
        for previous in reversed(self.keyframes[:-1]):
            anchor = (
                (previous.x, previous.y)
                if previous.holder == defender.id
                else previous.player_positions.get(defender.id)
            )
            if anchor is not None:
                distance = math.dist(anchor, position)
                available = max(0, physical_reach(entry.t - previous.t) - CONTACT_REACH)
                if distance > available:
                    position = tuple(a + (p - a) * available / distance for a, p in zip(anchor, position))
                break
        entry.player_positions[defender.id] = position
        target = self.to_pitch(side, min(ax + 1, 104), ay)
        # Give the defender time to close down, rather than teleporting into a duel.
        self.t += max(0.4, travel_time(math.dist(position, target) + 2 * CONTACT_REACH))
        self.key(side, ax, ay, holder)
        start = self.keyframes[-1]
        start.player_positions[defender.id] = target
        nx = min(ax + 3, 101)
        self.t += max(1, travel_time(math.hypot(nx - ax, 0.6) + 2 * CONTACT_REACH))
        if outcome == "failed":
            self.key(opponent, 105 - nx, 68 - ay, defender)
        else:
            self.key(side, nx, ay, holder if outcome == "complete" else None, in_play=outcome != "interrupted")
        end = self.keyframes[-1]
        end.player_positions[defender.id] = self.to_pitch(side, nx, ay + 0.6)
        foul = None
        if outcome == "interrupted":
            self.whistle()
            foul = self.emit(
                "foul", opponent, defender, 105 - nx, 68 - ay, victim_id=holder.id, kind="trip", advantage=False
            )
            self.decide(foul, "free_kick", side)
            self.state(ball_in_play=False)
        payload = {
            "outcome": outcome,
            "defender_id": defender.id,
            "start_t": start.t,
            "end_t": end.t,
            "end_location": [end.x, end.y],
        }
        if foul:
            payload["foul_id"] = foul["id"]
        event = self.report(
            "dribble",
            team=side,
            player_id=holder.id,
            location=[start.x, start.y],
            possession_id=start.possession_id,
            dribble=payload,
        )
        if outcome == "interrupted":
            self.stoppage(12)
            self.restart_free_kick(side, nx, ay)
            return None
        if outcome == "failed":
            self.report(
                "ball_recovery",
                team=opponent,
                player_id=defender.id,
                possession_id=end.possession_id,
                related=[event["id"]],
            )
            self.carrier = (opponent, defender, 105 - nx, 68 - ay)
            return None
        if outcome == "unresolved":
            self.report("ball_loose", related=[event["id"]])
            self.t += 0.25
            self.play.possession(side, force=True)
            self.key(side, nx, ay, holder)
            self.keyframes[-1].player_positions[defender.id] = end.player_positions[defender.id]
            self.report(
                "ball_recovery",
                team=side,
                player_id=holder.id,
                possession_id=self.play.possession_id,
                related=[event["id"]],
            )
        position = end.player_positions[defender.id]
        # Return to the formation over source time before the next action can
        # replace the encounter endpoint. Bound speed even as the baseline moves.
        settle_t = self.t
        for _ in range(4):
            baseline = formation_position(
                defender.base_x,
                defender.base_y,
                defender.position,
                defender.id,
                self.attacks_right(opponent),
                end.x,
                end.y,
                settle_t,
            )
            settle_t = max(settle_t, self.t + 0.4, self.t + math.dist(position, baseline) / 4)
        self.t = settle_t
        self.key(side, nx, ay, holder)
        return holder, nx, ay

    def maybe_drinks(self, side, kind):
        """Optional scheduled break during a real stoppage, before execution."""
        due = self.drinks_due.get(self.period)
        if due is None or self.clock_s() < due or self.play.stoppage_id is None:
            return False
        self.drinks_due.pop(self.period)
        if self.play.restart_id is None:
            trigger = next(e for e in self.events if e["id"] == self.play.trigger_event_id)
            self.decide(trigger, kind, side)
        self.report(
            "drinks_break",
            stoppage_id=self.play.stoppage_id,
            restart_id=self.play.restart_id,
            trigger_event_id=self.play.trigger_event_id,
            reason="drinks_break",
        )
        self.state(ball_in_play=False)
        frozen = self.keyframes[-1]
        self.keyframes.append(
            replace(
                frozen,
                t=round(self.t, 2),
                holder=None,
                in_play=False,
                player_positions=dict(frozen.player_positions),
                contact_effectors=dict(frozen.contact_effectors),
            )
        )
        self.t += 60
        self.keyframes.append(
            replace(
                self.keyframes[-1],
                t=round(self.t, 2),
                player_positions=dict(self.keyframes[-1].player_positions),
                contact_effectors=dict(self.keyframes[-1].contact_effectors),
            )
        )
        self.state(ball_in_play=False)
        return True

    def pass_(self, side, holder, ax, ay, strength):
        rng = self.rng
        if self.keyframes:
            self.keyframes[-1].contact_effectors[holder.id] = "foot"
            if holder.position == "GK":
                self.keyframes[-1].z = 0
        cross = ax > 78 and abs(ay - 34) > 18 and rng.random() < 0.45
        if cross:
            tx, ty = rng.uniform(92, 100), rng.uniform(26, 42)
        else:
            dx = rng.gauss(4 + 8 * strength, 9)
            if ax < 30:
                dx += 6
            tx = min(max(ax + dx, 2), 99)
            ty = min(max(ay + rng.gauss(0, 13), 1), 67)
        dist = math.hypot(tx - ax, ty - ay)
        if self.keyframes:
            self.keyframes[-1].flight_height = 3.0 if cross else 1.5 if dist > 35 else 0.0
        p_ok = 0.93 - 0.011 * max(0, tx - ax) - (0.16 if tx > 82 else 0) + 0.12 * (strength - 0.5)
        if cross:
            p_ok = 0.32
        through = tx - ax > 18 and tx > 70
        # offside on forward balls into the final third
        if tx - ax > 10 and tx > 68 and rng.random() < 0.06:
            target = self.nearest(side, tx, ty, exclude=holder)
            p = self.emit(
                "pass",
                side,
                holder,
                ax,
                ay,
                end_location=None,
                outcome="offside",
                recipient_id=target.id,
                height="ground",
            )
            self.set_pass_end(p, side, tx, ty)
            self.t += 0.6 + dist / 17
            self.key(side, tx, ty, None)
            self.t += rng.uniform(0.4, 1.2)
            self.whistle(1, "short")
            self.emit("offside", side, target, tx, ty, related=[p["id"]])
            if not hasattr(self,"name"):
                p["delivered_t"]=round(self.t+p["delivered_t"]-p["t"],2)
            self.stoppage(rng.uniform(12, 22))
            self.restart_free_kick(_other(side), PITCH_X - tx, PITCH_Y - ty)
            return None
        target = self.nearest(side, tx, ty, exclude=holder)
        height = "high" if cross or dist > 35 else "ground"
        complete = rng.random() < p_ok
        out = not complete and (tx > 98 or ty < 1.5 or ty > 66.5 or rng.random() < 0.3)
        ix, iy = ax + (tx - ax) * 0.75, ay + (ty - ay) * 0.75
        opp = _other(side)
        cutter = self.nearest(opp, PITCH_X - ix, PITCH_Y - iy) if not complete and not out else None
        arrival = self.flight_plan(
            target if complete else cutter,
            self.to_pitch(side, tx, ty) if complete or out else self.to_pitch(side, ix, iy),
            0.5 + (dist if complete or out else 0.75 * dist) / 16,
        )
        departure = self.t
        self.t = arrival
        if complete:
            p = self.emit(
                "pass",
                side,
                holder,
                ax,
                ay,
                outcome="complete",
                recipient_id=target.id,
                height=height,
                cross=cross,
                through_ball=through,
                t=departure,
            )
            if rng.random() < 0.03:  # missing qualifier, like a real feed
                p["pass"].pop("recipient_id")
            self.set_pass_end(p, side, tx, ty)
            self.key(side, tx, ty, target)
            return target, tx, ty, p, cross
        # failed pass
        p = self.emit(
            "pass",
            side,
            holder,
            ax,
            ay,
            outcome="incomplete",
            height=height,
            cross=cross,
            through_ball=through,
            t=departure,
        )
        if out:
            # out of play
            if tx > 96:
                self.set_pass_end(p, side, 105, ty)
                self.key(side, 105.5, ty, None, in_play=False)
                if rng.random() < 0.3 or cross:
                    self.stoppage(rng.uniform(14, 24))
                    self.corner(side, 105, 0 if ty < 34 else 68)
                else:
                    self.stoppage(rng.uniform(10, 18))
                    self.goal_kick(_other(side))
                return None
            edge = 0 if ty < 34 else 68
            self.set_pass_end(p, side, tx, edge)
            self.key(side, tx, edge + (-0.5 if edge == 0 else 0.5), None, in_play=False)
            self.stoppage(rng.uniform(6, 12))
            self.throw_in(_other(side), PITCH_X - tx, PITCH_Y - edge)
            return None
        self.set_pass_end(p, side, ix, iy)
        self.key(side, ix, iy, None)
        if ix > 80 and rng.random() < 0.5:
            self.t = self.contact_ready(cutter, self.to_pitch(side, ix, iy), self.t)
            self.key(side, ix, iy, cutter)
            self.emit("clearance", opp, cutter, PITCH_X - ix, PITCH_Y - iy)
            nx = PITCH_X - ix + rng.uniform(20, 35)
            ny = min(max(PITCH_Y - iy + rng.gauss(0, 12), 2), 66)
            self.t += 1.6
            self.key(opp, nx, ny, None)
            # second ball: 50/50
            win = opp if rng.random() < 0.55 else side
            if win == opp:
                rec = self.nearest(opp, nx, ny)
                self.t = self.contact_ready(rec, self.to_pitch(opp, nx, ny), self.t)
                self.key(opp, nx, ny, rec)
                self.emit("ball_recovery", opp, rec, nx, ny)
                self.carrier = (opp, rec, nx, ny)
            else:
                rec = self.nearest(side, PITCH_X - nx, PITCH_Y - ny)
                self.t = self.contact_ready(rec, self.to_pitch(opp, nx, ny), self.t)
                self.key(opp, nx, ny, rec)
                self.emit("ball_recovery", side, rec, PITCH_X - nx, PITCH_Y - ny)
                self.carrier = (side, rec, PITCH_X - nx, PITCH_Y - ny)
            return None
        self.t = self.contact_ready(cutter, self.to_pitch(side, ix, iy), self.t)
        self.key(side, ix, iy, cutter)
        self.emit("interception", opp, cutter, PITCH_X - ix, PITCH_Y - iy)
        self.carrier = (opp, cutter, PITCH_X - ix, PITCH_Y - iy)
        return None

    def set_pass_end(self, p: dict, side: str, tx: float, ty: float):
        x, y = self.to_pitch(side, tx, ty)
        p["pass"]["end_location"] = [round(x, 1), round(y, 1)]

    # ---------- restarts ----------
    def contact_ready(self, player, point, earliest):
        """A player's next source touch must be reachable from their last one."""
        point = tuple(round(value, 2) for value in point)
        for k in reversed(self.keyframes):
            previous = (k.x, k.y) if k.holder == player.id else k.player_positions.get(player.id)
            if previous is not None:
                previous = tuple(round(value, 2) for value in previous)
                distance = math.dist(previous, point)
                # Root-to-contact orientation can change at the next touch.
                # Reserve its reach in the real source schedule, never a draw clamp.
                duration = travel_time(distance + 2 * CONTACT_REACH) if distance > 1e-7 else 0
                return math.ceil(100 * max(earliest, k.t + duration + (0.002 if distance > 1e-7 else 0)) - 1e-7) / 100
        return math.ceil(100 * earliest - 1e-7) / 100

    def hold_until(self, at):
        """Keep the current source ball controlled/stationary while actors prepare."""
        if at <= self.t:
            return
        previous = self.keyframes[-1]
        self.t = round(at, 2)
        self.keyframes.append(
            replace(
                previous,
                t=self.t,
                flight_height=0,
                player_positions={},
                contact_effectors=dict(previous.contact_effectors),
            )
        )
        # A pending flight belongs to the actual release, not its setup wait.
        self.keyframes[-1].flight_height = previous.flight_height
        previous.flight_height = 0

    def flight_plan(self, receiver, point, duration):
        """Delay the kick for a reachable encounter; never slow an airborne ball."""
        duration = math.ceil(duration * 100 - 1e-7) / 100
        arrival = self.contact_ready(receiver, point, self.t + duration) if receiver else round(self.t + duration, 2)
        self.hold_until(round(arrival - duration, 2))
        return arrival

    def set_restart_ball(self, side, ax, ay, taker=None, hands=False):
        """An active player retrieves, carries and places the stopped ball."""
        taker = taker or self.nearest(side, ax, ay)
        if self.keyframes:
            last = self.keyframes[-1]
            self.keyframes.append(
                replace(
                    last,
                    t=round(self.t, 2),
                    holder=None,
                    in_play=False,
                    flight_height=0,
                    player_positions={},
                    contact_effectors={},
                )
            )
            pickup = (last.x, last.y)
            self.hold_until(self.contact_ready(taker, pickup, self.t))
            px, py = pickup if self.attacks_right(side) else (PITCH_X - pickup[0], PITCH_Y - pickup[1])
            self.key(side, px, py, taker, False, effector="hands")
            self.t += 0.35
            self.key(side, px, py, taker, False, effector="hands")
            self.keyframes[-1].z = 1.0
            self.t = self.contact_ready(taker, self.to_pitch(side, ax, ay), self.t)
            self.key(side, ax, ay, taker, False, effector="hands")
            self.keyframes[-1].z = 1.0
            self.t += 0.35
            self.key(side, ax, ay, taker, False, effector="hands")
            self.keyframes[-1].z = 1.7 if hands else 0
        else:
            self.key(side, ax, ay, taker, False, effector="hands" if hands else "foot")
            self.keyframes[-1].z = 1.7 if hands else 0
        self.t += 1.2
        self.key(side, ax, ay, taker if hands else None, False, effector="hands" if hands else None)
        self.keyframes[-1].z = 1.7 if hands else 0

    def restart_pass(self, side, kind, ax, ay, prepared=False):
        """Execution is a release, flight and another player's first touch."""
        taker = self.keeper(side) if kind == "goal_kick" else self.nearest(side, ax, ay)
        tx = ax + (9 if ax < 85 and kind != "kick_off" else -9)
        ty = min(62, max(6, ay + (8 if ay < 34 else -8))) if kind == "throw_in" else ay + (6 if ay <= 34 else -6)
        receiver = self.nearest(side, tx, ty, exclude=taker)
        self.t = self.contact_ready(taker, self.to_pitch(side, ax, ay), self.t)
        if not prepared:
            self.set_restart_ball(side, ax, ay, taker, hands=kind == "throw_in")
        if kind == "throw_in":
            # Lift during the existing dead-ball setup, then release from
            # hand/head height rather than labelling a ground ball a throw.
            self.keyframes[-1].z = 1.7
        duration = math.hypot(tx - ax, ty - ay) / (9 if kind == "throw_in" else 12)
        arrival = self.flight_plan(receiver, self.to_pitch(side, tx, ty), duration)
        action = self.emit("set_piece", side, taker, ax, ay, kind=kind)
        self.state(ball_in_play=True)
        self.key(side, ax, ay, None)
        self.keyframes[-1].contact_effectors[taker.id] = "hands" if kind == "throw_in" else "foot"
        if kind == "throw_in":
            self.keyframes[-1].z = 1.7
        positions = dict(self.keyframes[-2].player_positions)
        # The release replaces the taker's previous encounter position. Do not
        # restore that stale position on the receiver's arrival keyframe.
        positions[taker.id] = self.to_pitch(side, ax, ay)
        self.keyframes[-1].player_positions.update(positions)
        self.keyframes[-1].player_positions[taker.id] = self.to_pitch(side, ax, ay)
        self.keyframes[-1].flight_height = 1.6 if kind == "throw_in" else 0.25
        departure = self.t
        self.t = arrival
        self.report(
            "pass",
            t=departure,
            team=side,
            player_id=taker.id,
            location=list(self.to_pitch(side, ax, ay)),
            possession_id=self.play.possession_id,
            play_context=kind,
            restart_id=action["restart_id"],
            **{
                "pass": {
                    "outcome": "complete",
                    "recipient_id": receiver.id,
                    "height": "high" if kind == "throw_in" else "ground",
                    "end_location": list(self.to_pitch(side, tx, ty)),
                }
            },
        )
        self.key(side, tx, ty, receiver)
        self.keyframes[-1].player_positions.update(positions)
        self.carrier = (side, receiver, tx, ty)

    def throw_in(self, side, ax, ay):
        self.maybe_drinks(side, "throw_in")
        self.restart_pass(side, "throw_in", ax, ay)

    def goal_kick(self, side):
        self.maybe_drinks(side, "goal_kick")
        self.restart_pass(side, "goal_kick", 5.5, 34)

    def corner(self, side, ax, ay):
        self.maybe_drinks(side, "corner")
        taker = self.nearest(side, ax, ay)
        sy = 0.5 if ay < 34 else 67.5
        self.t = self.contact_ready(taker, self.to_pitch(side, 104.5, sy), self.t)
        self.set_restart_ball(side, 104.5, sy, taker)
        duration = self.rng.uniform(1.2, 2.0)
        tx, ty = self.rng.uniform(93, 100), self.rng.uniform(28, 40)
        target = self.nearest(side, tx, ty, exclude=taker)
        complete = self.rng.random() < 0.3
        opp = _other(side)
        clr = self.nearest(opp, PITCH_X - tx, PITCH_Y - ty) if not complete else None
        arrival = self.flight_plan(target if complete else clr, self.to_pitch(side, tx, ty), duration)
        self.emit("set_piece", side, taker, 104.5, sy, kind="corner")
        self.state(ball_in_play=True)
        self.key(side, 104.5, sy, None)
        self.keyframes[-1].player_positions[taker.id] = self.to_pitch(side, 104.5, sy)
        self.keyframes[-1].flight_height = 3
        departure = self.t
        self.t = arrival
        if complete:
            p = self.emit(
                "pass",
                side,
                taker,
                104.5,
                sy,
                t=departure,
                outcome="complete",
                recipient_id=target.id,
                height="high",
                cross=True,
                through_ball=False,
            )
            self.set_pass_end(p, side, tx, ty)
            self.key(side, tx, ty, target)
            self.shot(side, target, tx, ty, p, header=True)
            return
        p = self.emit(
            "pass",
            side,
            taker,
            104.5,
            sy,
            t=departure,
            outcome="incomplete",
            height="high",
            cross=True,
            through_ball=False,
        )
        self.set_pass_end(p, side, tx, ty)
        self.key(side, tx, ty, clr)
        self.keyframes[-1].flight_height = 2
        nx, ny = PITCH_X - tx + 25, PITCH_Y - ty
        receiver = self.nearest(opp, nx, ny, exclude=clr)
        arrival = self.flight_plan(receiver, self.to_pitch(opp, nx, ny), 1.6)
        self.emit("clearance", opp, clr, PITCH_X - tx, PITCH_Y - ty)
        self.t = arrival
        self.key(opp, nx, ny, receiver)
        self.emit("ball_recovery", opp, receiver, nx, ny)
        self.carrier = (opp, receiver, nx, ny)

    def restart_free_kick(self, side, ax, ay):
        self.maybe_drinks(side, "free_kick")
        self.restart_pass(side, "free_kick", ax, ay)

    # ---------- shots ----------
    @staticmethod
    def true_chance(ax: float, ay: float, header: bool) -> float:
        return chance_quality(ax, ay, header)

    def shot(self, side, shooter, ax, ay, last_pass, header=False, penalty=False, before_release=None):
        rng = self.rng
        opp = _other(side)
        self.crowd_hit(0.14, 2.5, dt=-1.0)
        if penalty:
            p_goal = 0.77
        else:
            # hidden quality: pressure, body shape, keeper position
            p_goal = min(self.true_chance(ax, ay, header) * math.exp(rng.gauss(0, 0.35)), 0.9)
        body = "head" if header else rng.choice(["right_foot", "right_foot", "left_foot"])
        if header and self.keyframes and self.keyframes[-1].holder == shooter.id:
            self.keyframes[-1].z = 1.65
            self.keyframes[-1].contact_effectors[shooter.id] = "head"
        related = [last_pass["id"]] if last_pass else []
        r = rng.random()
        if r < p_goal:
            outcome = "goal"
        elif r < p_goal + (1 - p_goal) * 0.33:
            outcome = "saved"
        elif r < p_goal + (1 - p_goal) * 0.55 and not penalty:
            outcome = "blocked"
        elif r < p_goal + (1 - p_goal) * 0.58:
            outcome = "post"
        else:
            outcome = "off_target"
        q = {"body_part": body, "penalty": penalty}
        if rng.random() < 0.05 and not penalty:
            q.pop("body_part")
        self.t += 0 if penalty else 0.3
        blocker = self.opp_nearest(side, ax + 2, ay) if outcome == "blocked" else None
        contact_actor = self.keeper(opp) if outcome == "saved" else blocker
        contact_point = self.to_pitch(side, 102 if outcome == "saved" else ax + 2, ay)
        arrival = self.flight_plan(contact_actor, contact_point, 0.6)
        if before_release:
            before_release()
        self.key(side, ax, ay, shooter, effector="head" if header else "foot")
        if header:
            self.keyframes[-1].z = 1.65
        self.keyframes[-1].flight_height = 0.8 if header else 1.5
        s = self.emit("shot", side, shooter, ax, ay, related=related, **q)
        if last_pass:
            s["preparing_pass_id"] = last_pass["id"]
        s["play_context"] = "penalty" if penalty else self.play.play_context
        self.events.append(delayed_xg(self.seed, s, ax, ay, header, self.xg_delay))
        self.t = arrival
        result = self.report("shot_result", shot_id=s["id"], outcome=outcome, team=side, player_id=shooter.id)
        if outcome == "goal":
            self.key(side, 105.5, 34 + rng.uniform(-3, 3), None, in_play=False)
            self.score[side] += 1
            self.stop(result, "goal")
            self.crowd_hit(0.6, 22, hold=6)
            self.state(ball_in_play=False)
            self.t += rng.uniform(45, 70)  # celebration
            cancelled = self.var_goal_check(s) if rng.random() < 0.18 else False
            self.maybe_subs()
            if cancelled:
                self.restart_free_kick(opp, 105 - ax, 68 - ay)
            else:
                self.kick_off(opp)
            return
        self.crowd_hit(0.2, 4)
        if outcome in ("saved",):
            gk = self.keeper(opp)
            self.emit("save", opp, gk, PITCH_X - 102, PITCH_Y - ay, related=[s["id"]])
            self.key(side, 102, ay, gk, effector="hands")
            if rng.random() < 0.4:
                self.t += 0.25  # physical deflection after the save contact
                self.key(side, 105.5, 34, None, in_play=False)
                self.stoppage(rng.uniform(14, 22))
                self.corner(side, 105, rng.choice([0, 68]))
            else:
                self.t += 0.35
                self.key(side, 102, ay, gk, effector="hands")
                self.keyframes[-1].z = 1.0
                self.carrier = (opp, gk, 3.0, PITCH_Y - ay)
            return
        if outcome == "blocked":
            blk = blocker
            self.key(side, ax + 2, ay, None)
            self.keyframes[-1].player_positions[blk.id] = self.to_pitch(side, ax + 2, ay)
            self.keyframes[-1].contact_effectors[blk.id] = "foot"
            self.emit("block", opp, blk, PITCH_X - ax - 2, PITCH_Y - ay, related=[s["id"]])
            if rng.random() < 0.45:
                self.t += max(0.25, (105.5 - ax - 2) / 20)
                self.key(side, 105.5, ay, None, in_play=False)
                self.stoppage(rng.uniform(14, 22))
                self.corner(side, 105, 0 if ay < 34 else 68)
            else:
                self.t += 0.35
                self.key(side, ax - 6, ay, None)
                self.t = self.contact_ready(blk, self.to_pitch(side, ax - 6, ay), self.t + 0.3)
                self.key(side, ax - 6, ay, blk)
                self.emit("ball_recovery", opp, blk, PITCH_X - ax + 6, PITCH_Y - ay, related=[s["id"]])
                self.carrier = (opp, blk, PITCH_X - ax + 6, PITCH_Y - ay)
            return
        if outcome == "post":
            # A post/crossbar rebound which stays on the field is still live.
            # The private trajectory chooses that concrete case; it is not an
            # automatic goal-kick or an invented outcome in the renderer.
            lateral = rng.choice([-1, 1])
            self.key(side, 105, 34 + lateral * 3.66, None)
            self.t += 0.45
            self.key(side, 100, 34 + lateral * 2.5, None)
            winner = rng.choice([side, opp])
            wx, wy = (100, 34 + lateral * 2.5) if winner == side else (5, 34 - lateral * 2.5)
            receiver = self.nearest(winner, wx, wy)
            self.t = self.contact_ready(receiver, self.to_pitch(winner, wx, wy), self.t + 0.6)
            self.key(winner, wx, wy, receiver)
            self.emit("ball_recovery", winner, receiver, wx, wy, related=[s["id"]])
            self.carrier = (winner, receiver, wx, wy)
            return
        # off target
        self.key(side, 105.5, 34 + rng.choice([-1, 1]) * rng.uniform(4, 10), None, in_play=False)
        self.stoppage(rng.uniform(12, 20))
        self.goal_kick(opp)

    def var_goal_check(self, goal_evt: dict):
        rid = f"var_{self.n:04d}"
        self.emit("var", None, None, related=[goal_evt["id"]], review_id=rid, phase="check",
                  incident="goal", original_decision="goal", outcome=None)
        self.murmurs.append((self.t, self.t + 35, 0.12))
        self.t += self.rng.uniform(25, 45)
        cancelled = (not goal_evt["shot"].get("penalty") and bool(goal_evt.get("preparing_pass_id"))
                     and self.detail_rng.random() < 0.25)
        self.emit("var", None, None, review_id=rid, phase="decision", incident="goal",
                  original_decision="goal", outcome="overturned" if cancelled else "stands")
        if cancelled:
            side = goal_evt["team"]
            result = next(e for e in self.events if e["type"] == "shot_result"
                          and e["shot_id"] == goal_evt["id"])
            offence = self.report("offside", t=goal_evt["t"], delivered_t=round(self.t + 0.75, 2),
                                  team=side, player_id=goal_evt["player_id"], location=list(goal_evt["location"]))
            decision = self.decide(offence, "free_kick", _other(side))
            self.report("goal_cancelled", shot_id=goal_evt["id"], result_id=result["id"],
                        decision_id=decision["id"], team=side, player_id=goal_evt["player_id"])
            self.score[side] -= 1
            self.state(ball_in_play=False)
        return cancelled

    def emit_offence(self, side, fouler, ax, ay, victim, kind, advantage, *, handball=None, incident_t=None):
        if handball is None:
            handball=not advantage and self.detail_rng.random()<.06
        if handball:
            return self.emit("handball", side, fouler, ax, ay, t=incident_t,
                             offence=True, victim_id=victim.id)
        return self.emit("foul", side, fouler, ax, ay,
                         victim_id=victim.id, kind=kind, advantage=advantage)

    def handball_encounter(self, side, victim, fouler, ax, ay):
        """An actual chip meets a hand, then deflects free before the whistle."""
        hx=min(ax+1.5,104)
        point=self.to_pitch(side,hx,ay)
        arrival=self.flight_plan(fouler,point,.45)
        self.key(side,ax,ay,victim,effector="foot")
        departure=self.t
        self.keyframes[-1].flight_height=.2
        self.t=arrival
        self.key(side,hx,ay,None)
        touch=self.keyframes[-1]
        touch.z=1.1
        touch.player_positions[fouler.id]=point
        touch.contact_effectors[fouler.id]="hands"
        self.report("pass",t=departure,team=side,player_id=victim.id,
                    location=list(self.to_pitch(side,ax,ay)),possession_id=self.play.possession_id,
                    play_context=self.play.play_context,
                    **{"pass":{"outcome":"incomplete","height":"high","end_location":list(point)}})
        incident=self.t
        self.t+=.3
        self.key(side,hx-.5,ay,None)  # a real downward/free-ball deflection
        return hx,ay,incident

    # ---------- fouls ----------
    def foul(self, side, victim, ax, ay) -> bool:
        """Defending team fouls the carrier. Returns True if the possession ended."""
        rng = self.rng
        opp = _other(side)
        fouler = self.opp_nearest(side, ax, ay)
        in_box = ax >= BOX_X and BOX_Y[0] <= ay <= BOX_Y[1]
        kind = rng.choice(["trip", "trip", "push", "holding", "kick"])
        called=in_box and rng.random()<.6
        advantage=not in_box and ax>60 and rng.random()<.22
        handball=(not in_box or called) and not advantage and self.detail_rng.random()<.06
        incident=None
        if handball:
            ax,ay,incident=self.handball_encounter(side,victim,fouler,ax,ay)
            # The chip can cross the box boundary: award at the actual hand
            # contact, not at the carrier's earlier ground-ball location.
            in_box=ax>=BOX_X and BOX_Y[0]<=ay<=BOX_Y[1]
            called=in_box
        else:
            self.t = self.contact_ready(fouler, self.to_pitch(side, ax, ay), self.t)
            self.key(side, ax, ay, victim)
            self.keyframes[-1].player_positions[fouler.id] = self.to_pitch(side, ax, ay)
            self.keyframes[-1].contact_effectors[fouler.id] = "foot"
        if in_box:
            # the referee sees it about 60% of the time; VAR catches some of the rest
            if called:
                self.whistle(1, "long")
                self.crowd_hit(0.42, 12, dt=0.4)
                f = self.emit_offence(opp, fouler, PITCH_X - ax, PITCH_Y - ay, victim, kind, False,
                                      handball=handball,incident_t=incident)
                self.decide(f, "penalty", side)
                self.card_maybe(opp, fouler, base=0.35, offence=f)
                self.stoppage(rng.uniform(55, 80))
                self.penalty(side)
                return True
            return self.missed_box_foul(side, victim, fouler, ax, ay, kind)
        f = self.emit_offence(opp, fouler, PITCH_X - ax, PITCH_Y - ay, victim, kind, advantage,
                              handball=handball,incident_t=incident)
        if advantage:
            self.card_maybe(opp, fouler, base=0.12, offence=f)
            return False
        self.t += 0 if handball else .3
        self.whistle(1, "normal" if rng.random() < 0.8 else "long")
        self.decide(f, "free_kick", side)
        self.state(ball_in_play=False)
        stopped=self.keyframes[-1]
        self.keyframes.append(replace(stopped,t=round(self.t,2),holder=None,in_play=False,
                                      player_positions=dict(stopped.player_positions),contact_effectors={}))
        self.card_maybe(opp, fouler, base=0.12, offence=f)
        if rng.random() < 0.05:
            self.emit("injury_stoppage", side, victim, related=[f["id"]])
            self.t += rng.uniform(45, 90)
            if rng.random() < 0.35:
                self.substitute(side, reason="injury", off=victim)
        self.stoppage(rng.uniform(10, 22))
        self.restart_free_kick(side, ax, ay)
        return True

    def missed_box_foul(self, side, victim, fouler, ax, ay, kind) -> bool:
        """Contact in the box, no whistle. The feed sees a tackle; VAR may review."""
        rng = self.rng
        opp = _other(side)
        self.t = self.contact_ready(fouler, self.to_pitch(side, ax, ay), self.t)
        self.key(side, ax, ay, fouler)
        tk = self.emit("tackle", opp, fouler, PITCH_X - ax, PITCH_Y - ay, outcome="won")
        incident_t = self.t
        self.crowd_hit(0.36, 7, dt=0.6)
        # play continues until the ball goes out
        self.t += rng.uniform(1.0, 2.0)
        cx, cy = PITCH_X - ax + rng.uniform(20, 40), min(max(PITCH_Y - ay + rng.gauss(0, 10), 3), 65)
        self.key(side, ax, ay, fouler)
        self.emit("clearance", opp, fouler, PITCH_X - ax, PITCH_Y - ay)
        self.keyframes[-1].flight_height = 1.5
        self.t += max(0.5, math.dist(self.to_pitch(side, ax, ay), self.to_pitch(opp, cx, cy)) / 20)
        self.key(opp, cx, cy, None)
        self.t += rng.uniform(3, 8)
        edge = 0 if cy < 34 else 68
        self.key(opp, cx, edge, None, in_play=False)
        self.whistle(2, "normal")  # stop for review
        self.stop(tk, "review")
        original = self.decide(tk, "no_penalty", opp)
        self.state(ball_in_play=False)
        rid = f"var_{self.n:04d}"
        self.emit(
            "var",
            None,
            None,
            related=[tk["id"]],
            review_id=rid,
            phase="check",
            incident="penalty",
            original_decision="no_penalty",
            outcome=None,
            incident_t=round(incident_t, 2),
        )
        check_start = self.t
        overturn = rng.random() < 0.6
        self.t += rng.uniform(25, 45)
        if overturn:
            self.emit(
                "var",
                None,
                None,
                review_id=rid,
                phase="on_field_review",
                incident="penalty",
                original_decision="no_penalty",
                outcome=None,
            )
            self.t += rng.uniform(25, 40)
            self.murmurs.append((check_start, self.t, 0.16))
            self.emit(
                "var",
                None,
                None,
                review_id=rid,
                phase="decision",
                incident="penalty",
                original_decision="no_penalty",
                outcome="overturned",
            )
            self.whistle(1, "long")
            self.crowd_hit(0.5, 14, dt=0.3)
            f = self.emit(
                "foul",
                opp,
                fouler,
                PITCH_X - ax,
                PITCH_Y - ay,
                victim_id=victim.id,
                kind=kind,
                advantage=False,
                related=[tk["id"]],
                incident_t=round(incident_t, 2),
            )
            self.decide(f, "penalty", side, supersedes=original["id"])
            self.card_maybe(opp, fouler, base=0.5, offence=f)
            self.stoppage(rng.uniform(40, 60))
            self.penalty(side)
            return True
        self.murmurs.append((check_start, self.t, 0.14))
        self.emit(
            "var",
            None,
            None,
            review_id=rid,
            phase="decision",
            incident="penalty",
            original_decision="no_penalty",
            outcome="stands",
        )
        self.crowd_hit(0.12, 5)
        self.stoppage(rng.uniform(5, 10))
        self.throw_in(side, PITCH_X - cx, PITCH_Y - edge)
        return True

    def penalty(self, side):
        taker = next((p for p in self.on_pitch[side] if p.position == "ST"), self.on_pitch[side][-1])
        self.key(side, 94, 34, taker, in_play=False)
        action = self.emit("set_piece", side, taker, 94, 34, kind="penalty")
        self.murmurs.append((self.t - 6, self.t + 1, 0.25))  # the hush before the kick
        self.t += 1.0

        def signal():
            self.whistle(1, "short")
            action["delivered_t"] = round(action["delivered_t"] + self.t - action["t"], 2)
            action["t"] = round(self.t, 2)
            action["clock"] = self.clock_str()
            self.restart(action)
            action["possession_id"] = self.play.possession_id
            action["play_context"] = "penalty"
            self.state(ball_in_play=True)

        self.shot(side, taker, 94, 34, None, penalty=True, before_release=signal)

    def card_maybe(self, side, player, base: float, offence: dict):
        rng = self.rng
        if player.id in self.sent_off:
            return
        r = rng.random()
        colour = None
        if r < 0.012:
            colour = "red"
        elif r < base:
            colour = "second_yellow" if self.yellows.get(player.id) else "yellow"
        if not colour:
            return
        self.t += rng.uniform(4, 9)
        card = self.emit("card", side, player, colour=colour, related=[offence["id"]])
        card["offence_id"] = offence["id"]
        self.crowd_hit(0.12, 5)
        if colour == "yellow":
            self.yellows[player.id] = 1
            self.cards[side]["yellow"] += 1
        else:
            self.cards[side]["red"] += 1
            self.sent_off.add(player.id)
            if player in self.on_pitch[side] and player.position != "GK":
                self.on_pitch[side].remove(player)
        self.state()

    # ---------- crowd ----------
    def build_crowd(self) -> list[dict]:
        rng = self.rng
        out = []
        level = 0.4
        end = int(self.t)
        spans = sorted(self.pressure_spans)
        si = 0
        for sec in range(0, end + 1):
            target = 0.36 + 0.03 * math.sin(sec / 47.0) + 0.02 * math.sin(sec / 13.0)
            while si < len(spans) and spans[si][1] < sec - 4:
                si += 1
            if any(a - 1 <= sec <= b + 3 for a, b in spans[si:si + 6]):
                target += 0.1
            for a, b, depth in self.murmurs:
                if a <= sec <= b:
                    target -= depth
            for imp in self.impulses:
                dt = sec - imp.t
                if dt < 0 or dt > imp.hold + imp.decay * 5:
                    continue
                target += imp.amp if dt <= imp.hold else imp.amp * math.exp(-(dt - imp.hold) / imp.decay)
            level += (target - level) * 0.55  # crowd and mic lag
            noisy = min(max(level + rng.gauss(0, 0.025), 0.0), 1.0)
            out.append({"stream": "crowd", "match_id": self.match_id, "source": "audio", "t": float(sec),
                        "quality": {"status": "measured", "confidence": 1.0},
                        "crowd_level": round(noisy, 3)})
        return out


def generate_match(seed: int = 7, match_id: str | None = None,
                   xg_delay: tuple[float, float] = (2, 5)) -> Match:
    return _Sim(seed, match_id or f"syn_{seed:04d}", xg_delay).run()
