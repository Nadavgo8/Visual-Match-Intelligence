"""The engine's picture of the match, built only from what has been delivered so far.

Everything here is deterministic. Agents read it through the read-only tool
functions at the bottom (see vmi/agents/tools.py).
"""

from __future__ import annotations

from collections import deque, OrderedDict
from bisect import bisect_left, insort
from copy import deepcopy
from dataclasses import dataclass, field

from . import derive
from ..contracts import VERSION, LINK_PARENTS, validate_record
from ..generator.export import initial_metadata
from .atmosphere import controlled_owner, crowd_component

MOMENTUM_WINDOW_S = 7 * 60
W_POSSESSION, W_KEY_PASS, W_SHOT = 0.4, 0.3, 0.3
ON_BALL = {"pass", "shot", "set_piece", "ball_recovery", "interception", "save", "carry"}
CONTROL_TYPES = ON_BALL | {"tackle"}


@dataclass
class Momentum:
    home_index: float  # 0..1, the bar's home share
    value: float  # -1 (all away) .. +1 (all home)
    possession_home: float
    key_passes: dict
    shots: dict
    window_s: int
    possession_available: bool = False

    def as_dict(self) -> dict:
        return {
            "home_index": round(self.home_index, 3), "value": round(self.value, 3),
            "possession_home": round(self.possession_home, 3),
            "key_passes": self.key_passes, "shots": self.shots, "window_s": self.window_s,
            "weights": {"possession": W_POSSESSION, "key_passes": W_KEY_PASS, "shots": W_SHOT},
            "possession_available": self.possession_available,
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
    pending_links: OrderedDict = field(default_factory=OrderedDict)
    link_errors: deque = field(default_factory=lambda: deque(maxlen=128))
    changes: list[dict] = field(default_factory=list)
    active_stoppage_id: str | None = None
    pending_restart_id: str | None = None
    decision_by_stop: dict = field(default_factory=dict)
    result_by_shot: dict = field(default_factory=dict)
    xg_by_shot: dict = field(default_factory=dict)
    last_clock_t: float = -1
    last_restart_t: float = -1
    last_stop_t: float = -1
    shots_by_id: dict = field(default_factory=dict)
    prepared_passes: set = field(default_factory=set)
    control_times: dict = field(default_factory=lambda: {"home": [], "away": []})
    tracking: dict | None = None

    def __post_init__(self):
        if self.meta.get("schema_version") != VERSION:
            raise ValueError("MatchModel requires schema v2")
        self.meta = initial_metadata(self.meta)
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
        self.changes = []
        validate_record(rec, self.meta["match_id"])
        stream = rec.get("stream")
        if stream == "crowd":
            if not self.crowd or rec["t"] >= self.crowd[-1][0]:
                q = rec.get("quality", {})
                level = rec["crowd_level"] if q.get("status") == "measured" and q.get("confidence", 0) >= 0.8 else None
                self.crowd.append((rec["t"], level))
            return rec
        if stream == "tracking":
            if self.tracking is None or rec["t"] > self.tracking["t"]:
                self.tracking = deepcopy(rec)
            return rec
        if stream == "match_state":
            # Only explicit stop / restart events govern the delivered play state.
            if rec["t"] >= self.last_clock_t:
                self.cards = deepcopy(rec["cards"])
            self._clock(rec)
            return rec
        if rec["id"] in self.by_id or rec["id"] in self.pending_links:
            return rec
        ev = deepcopy(rec)
        if self._missing_links(ev):
            if len(self.pending_links) >= 256:
                _, dropped = self.pending_links.popitem(last=False)
                self.link_errors.append({"id": dropped["id"], "reason": "link buffer full"})
            self.pending_links[ev["id"]] = ev
            return ev
        self._apply(ev)
        # A source can release several buffered dependants, including a restart chain.
        while True:
            ready = []
            for eid, e in list(self.pending_links.items()):
                try:
                    if not self._missing_links(e):
                        ready.append(e)
                except ValueError as exc:
                    del self.pending_links[eid]
                    self.link_errors.append({"id": eid, "reason": str(exc)})
            if not ready:
                break
            for e in ready:
                del self.pending_links[e["id"]]
                self._apply(e)
        return ev

    def _missing_links(self, ev: dict) -> bool:
        for key, expected in LINK_PARENTS.get(ev["type"], {}).items():
            parent = self.by_id.get(ev[key])
            if parent is None:
                return True
            if expected and parent["type"] != expected:
                raise ValueError(f"{key} references a non-{expected} event")
            if ev["t"] < parent["t"]:
                raise ValueError(f"event precedes its {key}")
            if ev["type"] in {"shot_result", "shot_xg"}:
                if ev.get("team") != parent.get("team") or ev.get("player_id") != parent.get("player_id"):
                    raise ValueError("linked shot identity mismatch")
        previous = ev.get("supersedes_decision_id")
        if previous:
            parent = self.by_id.get(previous)
            if parent is None:
                return True
            if parent["type"] != "referee_decision" or parent["stoppage_id"] != ev["stoppage_id"]:
                raise ValueError("correction must replace a decision for the same stoppage")
            if ev["t"] < parent["t"]:
                raise ValueError("correction precedes the decision it replaces")
        if ev["type"] == "restart_taken":
            parent = self.by_id[ev["restart_id"]]
            if parent["stoppage_id"] != ev["stoppage_id"] or parent["team"] != ev["team"]:
                raise ValueError("restart belongs to a different stoppage/team")
        if ev["type"] == "goal_cancelled":
            result = self.by_id[ev["result_id"]]
            shot = self.by_id[ev["shot_id"]]
            if (result["shot_id"] != shot["id"] or result["outcome"] != "goal" or shot["team"] != ev["team"]
                    or shot["player_id"] != ev.get("player_id")):
                raise ValueError("cancellation must reference this shot's goal result")
            if ev["t"] < result["t"] or ev["t"] < self.by_id[ev["decision_id"]]["t"]:
                raise ValueError("cancellation precedes its result or decision")
        return False

    def _clock(self, rec: dict):
        if rec.get("type") != "shot_xg" and rec["t"] >= self.last_clock_t:
            self.period = rec.get("period", self.period)
            self.clock = rec.get("clock", self.clock)
            self.last_clock_t = rec["t"]

    def _apply(self, ev: dict):
        ev["derived"] = self._derive(ev)
        self.events.append(ev)
        self.by_id[ev["id"]] = ev
        self.changes.append(ev)
        etype = ev["type"]
        if self.tracking and ev["t"] >= self.tracking["t"]:
            p = self.tracking.get("possession", {})
            if etype == "ball_loose" or (etype in {"tackle", "interception", "ball_recovery", "save"}
                    and (ev.get("team") != p.get("team")
                         or (ev.get("possession_id") and ev["possession_id"] != p.get("id")))):
                self.tracking = None
        if etype in ON_BALL and ev.get("team"):
            self.owner = ev["team"]
        if etype == "tackle" and ev.get("team"):
            self.owner = ev["team"]
        if etype in {"shot_result", "shot_xg"}:
            shot = self.by_id[ev["shot_id"]]
            if etype == "shot_result":
                if shot["id"] in self.result_by_shot:
                    self.changes.pop()
                    self.link_errors.append({"id": ev["id"], "reason": "second result for shot"})
                    return
                self.result_by_shot[shot["id"]] = ev["id"]
                shot["shot"]["outcome"] = ev["outcome"]
                shot["derived"]["result_id"] = ev["id"]
                if ev["outcome"] == "goal":
                    self.score[shot["team"]] += 1
            else:
                if shot["id"] in self.xg_by_shot:
                    self.changes.pop()
                    self.link_errors.append({"id": ev["id"], "reason": "second xG for shot"})
                    return
                self.xg_by_shot[shot["id"]] = ev["id"]
                shot["derived"].update(xg=ev["xg"], xg_id=ev["id"], xg_method=ev["method_version"])
        if etype == "goal_cancelled":
            shot = self.by_id[ev["shot_id"]]
            decision = self.by_id[ev["decision_id"]]
            if (shot["shot"].get("outcome") != "goal"
                    or self.decision_by_stop.get(decision["stoppage_id"]) != decision["id"]):
                self.changes.pop()
                return
            self.score[shot["team"]] -= 1
            shot["shot"]["outcome"] = "disallowed"
            shot["derived"]["result_id"] = ev["id"]
        if etype == "ball_loose":
            self.owner = None
        if etype == "play_stopped":
            # An old stop arriving after its restart must not stop the new play.
            if ev["t"] >= max(self.last_restart_t, self.last_stop_t):
                self.last_stop_t = ev["t"]
                self.active_stoppage_id = ev["id"]
                self.ball_in_play = False
                self.owner = None
        elif etype == "referee_decision":
            previous = self.decision_by_stop.get(ev["stoppage_id"])
            if previous is None or ev.get("supersedes_decision_id") == previous:
                if previous:
                    old_trigger = self.by_id[self.by_id[previous]["trigger_event_id"]]
                    old_trigger["derived"]["penalty_awarded"] = False
                self.decision_by_stop[ev["stoppage_id"]] = ev["id"]
                trigger = self.by_id[ev["trigger_event_id"]]
                if trigger["type"] in {"foul", "handball"}:
                    trigger["derived"]["penalty_awarded"] = ev["decision"] == "penalty"
                    trigger["derived"]["decision_id"] = ev["id"]
                if ev["stoppage_id"] == self.active_stoppage_id:
                    self.pending_restart_id = None
            else:
                self.changes.pop()
                self.link_errors.append({"id": ev["id"], "reason": "superseded referee decision"})
        elif etype == "restart_awarded":
            if ev["decision_id"] != self.decision_by_stop.get(ev["stoppage_id"]):
                self.changes.pop()
                self.link_errors.append({"id": ev["id"], "reason": "restart uses superseded decision"})
            elif ev["stoppage_id"] == self.active_stoppage_id:
                self.pending_restart_id = ev["id"]
        elif etype == "restart_taken":
            award = self.by_id[ev["restart_id"]]
            if award["decision_id"] != self.decision_by_stop.get(ev["stoppage_id"]):
                self.changes.pop()
                self.link_errors.append({"id": ev["id"], "reason": "execution uses superseded decision"})
            elif ev["stoppage_id"] == self.active_stoppage_id:
                self.ball_in_play = True
                self.last_restart_t = max(self.last_restart_t, ev["t"])
                self.active_stoppage_id = None
                self.pending_restart_id = None
                self.owner = ev["team"]
        if etype == "shot":
            self.shots_by_id[ev["id"]] = ev
        if etype in CONTROL_TYPES and ev.get("team") in self.control_times:
            insort(self.control_times[ev["team"]], ev["t"])
        if etype in CONTROL_TYPES | {"shot_result", "goal_cancelled"}:
            self._refresh_preparations()
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
        # Rejected conflicts remain in history for diagnostics, but cannot move
        # the authoritative clock and suppress later valid clock updates.
        if self.changes and self.changes[-1] is ev:
            self._clock(ev)

    def _derive(self, ev: dict) -> dict:
        d: dict = {}
        etype, team, period = ev["type"], ev.get("team"), ev.get("period", self.period)
        loc = ev.get("location")
        if etype == "shot":
            q = ev["shot"]
            d["xg"] = None
            d["in_box"] = derive.in_opponent_box(team, period, loc)
            d["zone"] = derive.zone(team, period, loc)
        elif etype == "foul":
            d["in_box"] = derive.in_own_box(team, period, loc)
            d["penalty_awarded"] = False  # only a linked referee decision can award it
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

    def _refresh_preparations(self):
        """A key pass and a confirmed assist are different, delivery-dependent facts."""
        for pid in self.prepared_passes:
            self.by_id[pid]["derived"]["key_pass"] = False
        self.prepared_passes.clear()
        for shot in self.shots_by_id.values():
            d = shot["derived"]
            d.pop("preparing_pass_id", None)
            d.pop("assisted_by", None)
            p = self.by_id.get(shot.get("preparing_pass_id"))
            if not p or p["type"] != "pass" or shot["shot"].get("penalty") or shot["shot"].get("outcome") == "disallowed":
                continue
            if p["pass"].get("outcome") != "complete" or p["pass"].get("recipient_id") != shot["player_id"]:
                continue
            if p["team"] != shot["team"] or not p.get("possession_id") or p["possession_id"] != shot.get("possession_id"):
                continue
            controls = self.control_times["away" if shot["team"] == "home" else "home"]
            index = bisect_left(controls, p["t"])
            if p["t"] > shot["t"] or (index < len(controls) and controls[index] <= shot["t"]):
                continue
            p["derived"]["key_pass"] = True
            self.prepared_passes.add(p["id"])
            d["preparing_pass_id"] = p["id"]
            if shot["shot"].get("outcome") == "goal":
                d["assisted_by"] = p["player_id"]

    def tick(self, t: float):
        """Called once per second of match time."""
        self.t = t
        for eid, ev in list(self.pending_links.items()):
            if t - ev["delivered_t"] > 120:
                self.link_errors.append({"id": eid, "reason": "source not delivered within 120s"})
                del self.pending_links[eid]
        owner = controlled_owner(self.tracking, t) if self.ball_in_play else None
        if owner:
            side = owner[0]["team"]
            self.possession_samples.append((t, side))
            self.possession_total[side] += 1
        while self.possession_samples and self.possession_samples[0][0] < t - MOMENTUM_WINDOW_S:
            self.possession_samples.popleft()

    # ---------- measures ----------
    def momentum(self) -> Momentum:
        t0 = self.t - MOMENTUM_WINDOW_S
        # Meters can be emitted between cleanup ticks. Apply the window at read
        # time as well, so possession and event counts describe one snapshot.
        poss = [s for sample_t, s in self.possession_samples if t0 <= sample_t <= self.t]
        ph = poss.count("home") / len(poss) if poss else 0.5
        kp = {"home": 0, "away": 0}
        sh = {"home": 0, "away": 0}
        for e in self.events:
            if e["t"] < t0:
                continue
            if e["type"] == "shot":
                sh[e["team"]] += e["shot"].get("outcome") != "disallowed"
            elif e["type"] == "pass" and e["derived"].get("key_pass"):
                kp[e["team"]] += 1
        idx, val = momentum_from_counts(ph, kp["home"], kp["away"], sh["home"], sh["away"])
        return Momentum(idx, val, ph, kp, sh, MOMENTUM_WINDOW_S, bool(poss))

    def crowd_level(self) -> float | None:
        return crowd_component(self.crowd, self.t)

    def crowd_jump(self, seconds: int = 3) -> float:
        """Rise of the (lightly smoothed) crowd level over the last few seconds."""
        if len(self.crowd) < seconds + 2:
            return 0.0
        vals = [lv for _, lv in self.crowd]
        if any(v is None for v in vals[-(seconds + 2):]):
            return 0.0
        now = (vals[-1] + vals[-2]) / 2
        return now - min(vals[-(seconds + 2):-1])

    def crowd_reaction_after(self, t: float, window: float = 5.0) -> dict | None:
        """How the crowd level moved right after time t (timing only, never why)."""
        before = [lv for ct, lv in self.crowd if t - 4 <= ct <= t and lv is not None]
        after = [lv for ct, lv in self.crowd if t < ct <= t + window and lv is not None]
        if not before or not after:
            return None
        delta = max(after) - sum(before) / len(before)
        return {"t": t, "delta": round(delta, 2), "peak": round(max(after), 2)}

    def team_stats(self, since_t: float | None = None) -> dict:
        out = {}
        for side in ("home", "away"):
            evs = [e for e in self.events if e.get("team") == side and (since_t is None or e["t"] >= since_t)]
            shots = [e for e in evs if e["type"] == "shot" and e["shot"].get("outcome") != "disallowed"]
            passes = [e for e in evs if e["type"] == "pass"]
            out[side] = {
                "goals": sum(1 for s in shots if s["shot"].get("outcome") == "goal"),
                "shots": len(shots),
                "shots_on_target": sum(1 for s in shots if s["shot"].get("outcome") in ("goal", "saved")),
                "xg": (round(sum(s["derived"]["xg"] for s in shots), 2)
                       if all(s["derived"].get("xg") is not None for s in shots) else None),
                "xg_received": sum(s["derived"].get("xg") is not None for s in shots),
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
