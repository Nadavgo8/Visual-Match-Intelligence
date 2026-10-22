"""The engine's picture of the match, built only from what has been delivered so far.

Everything here is deterministic. Agents read it through the read-only tool
functions at the bottom (see vmi/agents/tools.py).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from . import derive

MOMENTUM_WINDOW_S = 7 * 60
W_POSSESSION, W_KEY_PASS, W_SHOT = 0.4, 0.3, 0.3
ON_BALL = {"pass", "shot", "set_piece", "ball_recovery", "interception", "save"}


@dataclass
class Momentum:
    home_index: float  # 0..1, the bar's home share
    value: float  # -1 (all away) .. +1 (all home)
    possession_home: float
    key_passes: dict
    shots: dict
    window_s: int

    def as_dict(self) -> dict:
        return {
            "home_index": round(self.home_index, 3), "value": round(self.value, 3),
            "possession_home": round(self.possession_home, 3),
            "key_passes": self.key_passes, "shots": self.shots, "window_s": self.window_s,
            "weights": {"possession": W_POSSESSION, "key_passes": W_KEY_PASS, "shots": W_SHOT},
        }


def momentum_from_counts(poss_home: float, kp_home: int, kp_away: int,
                         shots_home: int, shots_away: int) -> tuple[float, float]:
    """The momentum formula from docs/spec.md §3. Returns (home_index, value)."""
    k = (kp_home + 1) / (kp_home + kp_away + 2)
    s = (shots_home + 1) / (shots_home + shots_away + 2)
    idx = W_POSSESSION * poss_home + W_KEY_PASS * k + W_SHOT * s
    return idx, 2 * idx - 1


@dataclass
class MatchModel:
    meta: dict
    events: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    score: dict = field(default_factory=lambda: {"home": 0, "away": 0})
    period: int = 1
    ball_in_play: bool = False
    clock: str = "0:00"
    t: float = 0.0
    cards: dict = field(default_factory=lambda: {"home": {"yellow": 0, "red": 0},
                                                 "away": {"yellow": 0, "red": 0}})
    owner: str | None = None
    possession_samples: deque = field(default_factory=deque)  # (t, team) per in-play second
    possession_total: dict = field(default_factory=lambda: {"home": 0, "away": 0})
    crowd: deque = field(default_factory=lambda: deque(maxlen=600))  # (t, level)
    on_pitch: dict = field(default_factory=dict)
    finished: bool = False
    role_overrides: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.players = {p["id"]: p for side in self.meta["teams"].values() for p in side["players"]}
        self.on_pitch = {s: [p["id"] for p in tm["players"] if p["starter"]]
                         for s, tm in self.meta["teams"].items()}

    # ---------- names ----------
    def team_name(self, side: str | None) -> str:
        return self.meta["teams"][side]["name"] if side in ("home", "away") else ""

    def player_name(self, pid: str | None) -> str | None:
        p = self.players.get(pid or "")
        return f"{p['name']} (#{p['number']})" if p else None

    def player_role(self, pid: str | None) -> str | None:
        p = self.players.get(pid or "")
        return self.role_overrides.get(pid, p["position"]) if p else None

    # ---------- ingest ----------
    def ingest(self, rec: dict) -> dict:
        """Add a delivered record. Returns the (possibly annotated) record."""
        stream = rec.get("stream")
        if stream == "crowd":
            self.crowd.append((rec["t"], rec["crowd_level"]))
            return rec
        if stream == "match_state":
            self.ball_in_play = rec["ball_in_play"]
            self.period = rec["period"]
            self.clock = rec["clock"]
            self.cards = rec["cards"]
            return rec
        ev = dict(rec)
        ev["derived"] = self._derive(ev)
        self.events.append(ev)
        self.by_id[ev["id"]] = ev
        if ev.get("period"):
            self.period = ev["period"]
        self.clock = ev.get("clock", self.clock)
        etype = ev["type"]
        if etype in ON_BALL and ev.get("team"):
            self.owner = ev["team"]
        if etype == "tackle" and ev.get("team"):
            self.owner = ev["team"]
        if etype == "shot" and ev["shot"].get("outcome") == "goal":
            self.score[ev["team"]] += 1
        if etype == "substitution":
            side, sub = ev["team"], ev["substitution"]
            if sub["off_id"] in self.on_pitch[side]:
                if self.player_role(sub["off_id"]) == "GK":
                    self.role_overrides[sub["on_id"]] = "GK"
                self.on_pitch[side][self.on_pitch[side].index(sub["off_id"])] = sub["on_id"]
        if etype == "card" and ev["card"]["colour"] != "yellow":
            side = ev["team"]
            if ev["player_id"] in self.on_pitch[side]:
                self.on_pitch[side].remove(ev["player_id"])
        if etype == "period_end" and ev["period_end"]["period_no"] == 2:
            self.finished = True
        return ev

    def _derive(self, ev: dict) -> dict:
        d: dict = {}
        etype, team, period = ev["type"], ev.get("team"), ev.get("period", self.period)
        loc = ev.get("location")
        if etype == "shot":
            q = ev["shot"]
            d["xg"] = derive.estimate_xg(team, period, loc, q.get("body_part"), q.get("penalty", False))
            d["in_box"] = derive.in_opponent_box(team, period, loc)
            d["zone"] = derive.zone(team, period, loc)
            for rid in ev.get("related", []):
                p = self.by_id.get(rid)
                if p and p["type"] == "pass" and p["team"] == team:
                    p["derived"]["key_pass"] = True
                    d["assisted_by"] = p["player_id"]
        elif etype == "foul":
            d["in_box"] = derive.in_own_box(team, period, loc)
            d["penalty_awarded"] = bool(d["in_box"]) and not ev["foul"].get("advantage")
            # A foul logged well after the incident (after a VAR review) was not given on the field.
            inc_t = ev["foul"].get("incident_t")
            d["called_on_field"] = inc_t is None or ev["t"] - inc_t < 5
        elif etype == "pass":
            d["key_pass"] = False
            if ev["pass"].get("end_location"):
                d["into_box"] = derive.in_opponent_box(team, period, ev["pass"]["end_location"])
            d["zone"] = derive.zone(team, period, ev["pass"].get("end_location"))
        elif etype == "var":
            v = ev["var"]
            if v["phase"] == "check" and v["incident"] == "penalty" and v["original_decision"] == "no_penalty":
                # the referee let play go on; VAR is looking at a possible foul
                d["referee_did_not_give"] = True
        return d

    def tick(self, t: float):
        """Called once per second of match time."""
        self.t = t
        if self.ball_in_play and self.owner:
            self.possession_samples.append((t, self.owner))
            self.possession_total[self.owner] += 1
        while self.possession_samples and self.possession_samples[0][0] < t - MOMENTUM_WINDOW_S:
            self.possession_samples.popleft()

    # ---------- measures ----------
    def momentum(self) -> Momentum:
        t0 = self.t - MOMENTUM_WINDOW_S
        poss = [s for _, s in self.possession_samples]
        ph = poss.count("home") / len(poss) if poss else 0.5
        kp = {"home": 0, "away": 0}
        sh = {"home": 0, "away": 0}
        for e in reversed(self.events):
            if e["t"] < t0:
                break
            if e["type"] == "shot":
                sh[e["team"]] += 1
            elif e["type"] == "pass" and e["derived"].get("key_pass"):
                kp[e["team"]] += 1
        idx, val = momentum_from_counts(ph, kp["home"], kp["away"], sh["home"], sh["away"])
        return Momentum(idx, val, ph, kp, sh, MOMENTUM_WINDOW_S)

    def crowd_level(self) -> float:
        if not self.crowd:
            return 0.0
        recent = [lv for t, lv in list(self.crowd)[-3:]]
        return sum(recent) / len(recent)

    def crowd_jump(self, seconds: int = 3) -> float:
        """Rise of the (lightly smoothed) crowd level over the last few seconds."""
        if len(self.crowd) < seconds + 2:
            return 0.0
        vals = [lv for _, lv in self.crowd]
        now = (vals[-1] + vals[-2]) / 2
        return now - min(vals[-(seconds + 2):-1])

    def crowd_reaction_after(self, t: float, window: float = 5.0) -> dict | None:
        """How the crowd level moved right after time t (timing only, never why)."""
        before = [lv for ct, lv in self.crowd if t - 4 <= ct <= t]
        after = [lv for ct, lv in self.crowd if t < ct <= t + window]
        if not before or not after:
            return None
        delta = max(after) - sum(before) / len(before)
        return {"t": t, "delta": round(delta, 2), "peak": round(max(after), 2)}

    def team_stats(self, since_t: float | None = None) -> dict:
        out = {}
        for side in ("home", "away"):
            evs = [e for e in self.events if e.get("team") == side and (since_t is None or e["t"] >= since_t)]
            shots = [e for e in evs if e["type"] == "shot"]
            passes = [e for e in evs if e["type"] == "pass"]
            out[side] = {
                "goals": sum(1 for s in shots if s["shot"]["outcome"] == "goal"),
                "shots": len(shots),
                "shots_on_target": sum(1 for s in shots if s["shot"]["outcome"] in ("goal", "saved")),
                "xg": round(sum(s["derived"].get("xg") or 0 for s in shots), 2),
                "passes": len(passes),
                "pass_accuracy": round(sum(1 for p in passes if p["pass"]["outcome"] == "complete")
                                       / len(passes), 2) if passes else None,
                "key_passes": sum(1 for p in passes if p["derived"].get("key_pass")),
                "fouls": sum(1 for e in evs if e["type"] == "foul"),
                "corners": sum(1 for e in evs if e["type"] == "set_piece" and e["set_piece"]["kind"] == "corner"),
                "offsides": sum(1 for e in evs if e["type"] == "offside"),
                "yellow_cards": sum(1 for e in evs if e["type"] == "card" and e["card"]["colour"] == "yellow"),
                "red_cards": sum(1 for e in evs if e["type"] == "card" and e["card"]["colour"] != "yellow"),
            }
        tot = self.possession_total["home"] + self.possession_total["away"]
        if since_t is None and tot:
            out["home"]["possession"] = round(self.possession_total["home"] / tot, 2)
            out["away"]["possession"] = round(1 - out["home"]["possession"], 2)
        return out

    def attack_zones(self, side: str, since_t: float) -> dict:
        """Which flank a team's passes into the opponent's box were played from, since a time."""
        z = {"left": 0, "centre": 0, "right": 0}
        for e in self.events:
            if e["t"] < since_t or e.get("team") != side or e["type"] != "pass":
                continue
            if e["derived"].get("into_box"):
                zz = derive.zone(side, e["period"], e.get("location"))
                if zz:
                    z[zz] += 1
        return z

    def minutes_left(self) -> int:
        return max(0, 90 - derive.minute_of(self.clock))
