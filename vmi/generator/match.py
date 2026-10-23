"""Seeded match truth with separate v2 event, motion and delayed analytics exports."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .teams import Player, Team, make_teams
from .analytics import chance_quality, delayed_xg
from .export import finish_export
from .motion import Keyframe
from .state import PlayState

PITCH_X, PITCH_Y = 105.0, 68.0
BOX_X = PITCH_X - 16.5
BOX_Y = (13.84, 54.16)
HT_GAP = 60.0  # half-time compressed to 60 s on the timeline
SCHEMA_VERSION = "2.0"


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

    @property
    def duration(self) -> float:
        return self.meta["end_t"]


class _Sim:
    def __init__(self, seed: int, match_id: str, xg_delay: tuple[float, float] = (2, 5)):
        self.rng = random.Random(seed)
        self.seed = seed
        self.match_id = match_id
        self.teams: dict[str, Team] = make_teams()
        self.initial_roles = {p.id: p.position for team in self.teams.values()
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
            self.keyframes.append(Keyframe(round(self.t, 2), k.x, k.y, None, False))

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

    def key(self, side: str, ax: float, ay: float, holder: Player | None, in_play: bool = True):
        x, y = self.to_pitch(side, ax, ay)
        self.keyframes.append(Keyframe(round(self.t, 2), round(x, 2), round(y, 2),
                                       holder.id if holder else None, in_play,
                                       possession_id=self.play.possession(side) if holder and in_play else None))

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
            # end of period
            self.whistle(blasts=2 if period == 1 else 3, length="long")
            self.emit("period_end", period_no=period)
            self.state(ball_in_play=False)
            self.key("home", 52.5, 34, None, in_play=False)
            if period == 1:
                self.t += HT_GAP
        self.t += 5
        crowd = self.build_crowd()
        teams_meta = {
            s: {"name": tm.name, "short": tm.short, "colour": tm.colour,
                "players": [vars(p) | {"starter": True, "position": self.initial_roles[p.id]} for p in tm.players]
                + [vars(p) | {"starter": False, "position": self.initial_roles[p.id]} for p in tm.bench]}
            for s, tm in self.teams.items()
        }
        meta = {
            "schema_version": SCHEMA_VERSION, "match_id": self.match_id, "seed": self.seed,
            "synthetic": True, "pitch": [PITCH_X, PITCH_Y], "teams": teams_meta,
            "end_t": round(self.t, 2), "final_score": dict(self.score),
            "home_attacks_right_in_period": {"1": True, "2": False},
        }
        finish_export(self.events, self.states, crowd)
        return Match(meta, self.events, crowd, self.states, self.keyframes)

    def kick_off(self, side: str):
        self.key(side, 52.5, 34, None, in_play=False)
        self.t += self.rng.uniform(2, 4)
        self.whistle(1, "short")
        st = self.nearest(side, 52.5, 34)
        self.emit("set_piece", side, st, 52.5, 34, kind="kick_off")
        self.state(ball_in_play=True)
        self.key(side, 52.5, 34, st)
        self.carrier = (side, st, 52.5, 34.0)

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
            hold = rng.uniform(0.6, 2.2)
            ax = min(ax + rng.uniform(0, 3.0), 101)
            ay = min(max(ay + rng.gauss(0, 1.5), 1), 67)
            self.t += hold
            self.key(side, ax, ay, holder)
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
                self.emit(kind, _other(side), tackler, PITCH_X - ax, PITCH_Y - ay,
                          outcome="won")
                self.carrier = (_other(side), tackler, PITCH_X - ax, PITCH_Y - ay)
                return
            # pass
            res = self.pass_(side, holder, ax, ay, strength)
            if res is None:
                return
            holder, ax, ay, last_pass, last_pass_cross = res
        self.carrier = (side, holder, ax, ay)

    def pass_(self, side, holder, ax, ay, strength):
        rng = self.rng
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
            p = self.emit("pass", side, holder, ax, ay, end_location=None, outcome="offside",
                          recipient_id=target.id, height="ground")
            self.set_pass_end(p, side, tx, ty)
            self.t += 0.6 + dist / 17
            self.key(side, tx, ty, None)
            self.t += rng.uniform(0.4, 1.2)
            self.whistle(1, "short")
            self.emit("offside", side, target, tx, ty, related=[p["id"]])
            self.stoppage(rng.uniform(12, 22))
            self.restart_free_kick(_other(side), PITCH_X - tx, PITCH_Y - ty)
            return None
        target = self.nearest(side, tx, ty, exclude=holder)
        height = "high" if cross or dist > 35 else "ground"
        self.t += 0.5 + dist / 16
        if rng.random() < p_ok:
            p = self.emit("pass", side, holder, ax, ay, outcome="complete",
                          recipient_id=target.id, height=height, cross=cross, through_ball=through,
                          t=self.t - (0.5 + dist / 16))
            if rng.random() < 0.03:  # missing qualifier, like a real feed
                p["pass"].pop("recipient_id")
            self.set_pass_end(p, side, tx, ty)
            self.key(side, tx, ty, target)
            return target, tx, ty, p, cross
        # failed pass
        p = self.emit("pass", side, holder, ax, ay, outcome="incomplete", height=height,
                      cross=cross, through_ball=through, t=self.t - (0.5 + dist / 16))
        if tx > 98 or ty < 1.5 or ty > 66.5 or rng.random() < 0.3:
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
        ix, iy = ax + (tx - ax) * 0.75, ay + (ty - ay) * 0.75
        self.set_pass_end(p, side, ix, iy)
        self.key(side, ix, iy, None)
        opp = _other(side)
        cutter = self.nearest(opp, PITCH_X - ix, PITCH_Y - iy)
        if ix > 80 and rng.random() < 0.5:
            self.emit("clearance", opp, cutter, PITCH_X - ix, PITCH_Y - iy)
            nx = PITCH_X - ix + rng.uniform(20, 35)
            ny = min(max(PITCH_Y - iy + rng.gauss(0, 12), 2), 66)
            self.t += 1.6
            self.key(opp, nx, ny, None)
            # second ball: 50/50
            win = opp if rng.random() < 0.55 else side
            if win == opp:
                rec = self.nearest(opp, nx, ny)
                self.carrier = (opp, rec, nx, ny)
            else:
                rec = self.nearest(side, PITCH_X - nx, PITCH_Y - ny)
                self.emit("ball_recovery", side, rec, PITCH_X - nx, PITCH_Y - ny)
                self.carrier = (side, rec, PITCH_X - nx, PITCH_Y - ny)
            return None
        self.emit("interception", opp, cutter, PITCH_X - ix, PITCH_Y - iy)
        self.carrier = (opp, cutter, PITCH_X - ix, PITCH_Y - iy)
        return None

    def set_pass_end(self, p: dict, side: str, tx: float, ty: float):
        x, y = self.to_pitch(side, tx, ty)
        p["pass"]["end_location"] = [round(x, 1), round(y, 1)]

    # ---------- restarts ----------
    def throw_in(self, side, ax, ay):
        taker = self.nearest(side, ax, ay)
        self.emit("set_piece", side, taker, ax, ay, kind="throw_in")
        self.state(ball_in_play=True)
        self.key(side, ax, ay, taker)
        self.carrier = (side, taker, ax, min(max(ay, 3), 65))

    def goal_kick(self, side):
        gk = self.keeper(side)
        self.emit("set_piece", side, gk, 5.5, 34, kind="goal_kick")
        self.state(ball_in_play=True)
        self.key(side, 5.5, 34, gk)
        self.carrier = (side, gk, 5.5, 34.0)

    def corner(self, side, ax, ay):
        taker = self.nearest(side, ax, ay)
        self.emit("set_piece", side, taker, 104.5, ay, kind="corner")
        self.state(ball_in_play=True)
        self.key(side, 104.5, 0.5 if ay < 34 else 67.5, taker)
        self.t += self.rng.uniform(1.2, 2.0)
        tx, ty = self.rng.uniform(93, 100), self.rng.uniform(28, 40)
        target = self.nearest(side, tx, ty, exclude=taker)
        if self.rng.random() < 0.3:
            p = self.emit("pass", side, taker, 104.5, ay, outcome="complete", recipient_id=target.id,
                          height="high", cross=True, through_ball=False)
            self.set_pass_end(p, side, tx, ty)
            self.key(side, tx, ty, target)
            self.shot(side, target, tx, ty, p, header=True)
            return
        p = self.emit("pass", side, taker, 104.5, ay, outcome="incomplete", height="high",
                      cross=True, through_ball=False)
        self.set_pass_end(p, side, tx, ty)
        opp = _other(side)
        clr = self.nearest(opp, PITCH_X - tx, PITCH_Y - ty)
        self.key(side, tx, ty, None)
        self.emit("clearance", opp, clr, PITCH_X - tx, PITCH_Y - ty)
        self.carrier = (opp, clr, PITCH_X - tx + 25, PITCH_Y - ty)

    def restart_free_kick(self, side, ax, ay):
        taker = self.nearest(side, ax, ay)
        self.emit("set_piece", side, taker, ax, ay, kind="free_kick")
        self.state(ball_in_play=True)
        self.key(side, ax, ay, taker)
        self.carrier = (side, taker, ax, ay)

    # ---------- shots ----------
    @staticmethod
    def true_chance(ax: float, ay: float, header: bool) -> float:
        return chance_quality(ax, ay, header)

    def shot(self, side, shooter, ax, ay, last_pass, header=False, penalty=False):
        rng = self.rng
        opp = _other(side)
        self.crowd_hit(0.14, 2.5, dt=-1.0)
        if penalty:
            p_goal = 0.77
        else:
            # hidden quality: pressure, body shape, keeper position
            p_goal = min(self.true_chance(ax, ay, header) * math.exp(rng.gauss(0, 0.35)), 0.9)
        body = "head" if header else rng.choice(["right_foot", "right_foot", "left_foot"])
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
        self.t += 0.3
        self.key(side, ax, ay, shooter)
        self.keyframes[-1].flight_height = 0.8 if header else 1.5
        s = self.emit("shot", side, shooter, ax, ay, related=related, **q)
        s["play_context"] = "penalty" if penalty else self.play.play_context
        self.events.append(delayed_xg(self.seed, s, ax, ay, header, self.xg_delay))
        self.t += 0.6
        result = self.report("shot_result", shot_id=s["id"], outcome=outcome, team=side,
                             player_id=shooter.id)
        if outcome == "goal":
            self.key(side, 105.5, 34 + rng.uniform(-3, 3), None, in_play=False)
            self.score[side] += 1
            self.stop(result, "goal")
            self.crowd_hit(0.6, 22, hold=6)
            self.state(ball_in_play=False)
            self.t += rng.uniform(45, 70)  # celebration
            if rng.random() < 0.18:
                self.var_goal_check(s)
            self.maybe_subs()
            self.kick_off(opp)
            return
        self.crowd_hit(0.2, 4)
        if outcome in ("saved",):
            gk = self.keeper(opp)
            self.emit("save", opp, gk, PITCH_X - 101, PITCH_Y - ay, related=[s["id"]])
            self.key(side, 102, ay, gk)
            if rng.random() < 0.4:
                self.key(side, 105.5, 34, None, in_play=False)
                self.stoppage(rng.uniform(14, 22))
                self.corner(side, 105, rng.choice([0, 68]))
            else:
                self.carrier = (opp, gk, 4.0, 34.0)
            return
        if outcome == "blocked":
            blk = self.opp_nearest(side, ax + 2, ay)
            self.emit("block", opp, blk, PITCH_X - ax - 2, PITCH_Y - ay, related=[s["id"]])
            if rng.random() < 0.45:
                self.key(side, 105.5, ay, None, in_play=False)
                self.stoppage(rng.uniform(14, 22))
                self.corner(side, 105, 0 if ay < 34 else 68)
            else:
                self.key(side, ax - 6, ay, None)
                self.carrier = (opp, blk, PITCH_X - ax + 6, PITCH_Y - ay)
            return
        # post or off target
        self.key(side, 106, 34 + rng.choice([-1, 1]) * rng.uniform(4, 10), None, in_play=False)
        self.stoppage(rng.uniform(12, 20))
        self.goal_kick(opp)

    def var_goal_check(self, goal_evt: dict):
        rid = f"var_{self.n:04d}"
        self.emit("var", None, None, related=[goal_evt["id"]], review_id=rid, phase="check",
                  incident="goal", original_decision="goal", outcome=None)
        self.murmurs.append((self.t, self.t + 35, 0.12))
        self.t += self.rng.uniform(25, 45)
        self.emit("var", None, None, review_id=rid, phase="decision", incident="goal",
                  original_decision="goal", outcome="stands")

    # ---------- fouls ----------
    def foul(self, side, victim, ax, ay) -> bool:
        """Defending team fouls the carrier. Returns True if the possession ended."""
        rng = self.rng
        opp = _other(side)
        fouler = self.opp_nearest(side, ax, ay)
        in_box = ax >= BOX_X and BOX_Y[0] <= ay <= BOX_Y[1]
        kind = rng.choice(["trip", "trip", "push", "holding", "kick"])
        if in_box:
            # the referee sees it about 60% of the time; VAR catches some of the rest
            if rng.random() < 0.6:
                self.whistle(1, "long")
                self.crowd_hit(0.42, 12, dt=0.4)
                f = self.emit("foul", opp, fouler, PITCH_X - ax, PITCH_Y - ay, victim_id=victim.id,
                              kind=kind, advantage=False)
                self.decide(f, "penalty", side)
                self.card_maybe(opp, fouler, base=0.35)
                self.stoppage(rng.uniform(55, 80))
                self.penalty(side)
                return True
            return self.missed_box_foul(side, victim, fouler, ax, ay, kind)
        advantage = ax > 60 and rng.random() < 0.22
        f = self.emit("foul", opp, fouler, PITCH_X - ax, PITCH_Y - ay, victim_id=victim.id,
                      kind=kind, advantage=advantage)
        if advantage:
            self.card_maybe(opp, fouler, base=0.12)
            return False
        self.t += 0.3
        self.whistle(1, "normal" if rng.random() < 0.8 else "long")
        self.decide(f, "free_kick", side)
        self.state(ball_in_play=False)
        self.key(side, ax, ay, None, in_play=False)
        self.card_maybe(opp, fouler, base=0.12)
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
        tk = self.emit("tackle", opp, fouler, PITCH_X - ax, PITCH_Y - ay, outcome="won")
        incident_t = self.t
        self.crowd_hit(0.36, 7, dt=0.6)
        # play continues until the ball goes out
        self.t += rng.uniform(1.0, 2.0)
        cx, cy = PITCH_X - ax + rng.uniform(20, 40), min(max(PITCH_Y - ay + rng.gauss(0, 10), 3), 65)
        self.emit("clearance", opp, fouler, PITCH_X - ax, PITCH_Y - ay)
        self.key(opp, cx, cy, None)
        self.t += rng.uniform(3, 8)
        edge = 0 if cy < 34 else 68
        self.key(opp, cx, edge, None, in_play=False)
        self.whistle(2, "normal")  # stop for review
        self.stop(tk, "review")
        original = self.decide(tk, "no_penalty", opp)
        self.state(ball_in_play=False)
        rid = f"var_{self.n:04d}"
        self.emit("var", None, None, related=[tk["id"]], review_id=rid, phase="check",
                  incident="penalty", original_decision="no_penalty", outcome=None,
                  incident_t=round(incident_t, 2))
        check_start = self.t
        overturn = rng.random() < 0.6
        self.t += rng.uniform(25, 45)
        if overturn:
            self.emit("var", None, None, review_id=rid, phase="on_field_review", incident="penalty",
                      original_decision="no_penalty", outcome=None)
            self.t += rng.uniform(25, 40)
            self.murmurs.append((check_start, self.t, 0.16))
            self.emit("var", None, None, review_id=rid, phase="decision", incident="penalty",
                      original_decision="no_penalty", outcome="overturned")
            self.whistle(1, "long")
            self.crowd_hit(0.5, 14, dt=0.3)
            f = self.emit("foul", opp, fouler, PITCH_X - ax, PITCH_Y - ay, victim_id=victim.id,
                          kind=kind, advantage=False, related=[tk["id"]], incident_t=round(incident_t, 2))
            self.decide(f, "penalty", side, supersedes=original["id"])
            self.card_maybe(opp, fouler, base=0.5)
            self.stoppage(rng.uniform(40, 60))
            self.penalty(side)
            return True
        self.murmurs.append((check_start, self.t, 0.14))
        self.emit("var", None, None, review_id=rid, phase="decision", incident="penalty",
                  original_decision="no_penalty", outcome="stands")
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
        self.whistle(1, "short")
        # Preserve the simulation RNG order while reporting execution at the kick.
        action["t"] = round(self.t, 2)
        action["delivered_t"] = round(action["delivered_t"] + 1, 2)
        self.restart(action)
        action["possession_id"] = self.play.possession_id
        action["play_context"] = "penalty"
        self.state(ball_in_play=True)
        self.shot(side, taker, 94, 34, None, penalty=True)

    def card_maybe(self, side, player, base: float):
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
        self.emit("card", side, player, colour=colour)
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
