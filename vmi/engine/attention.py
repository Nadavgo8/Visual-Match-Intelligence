"""The Attention Engine: deterministic routing, timing and depth.

It reads the delivered streams in order and emits outputs, each with a `why`:

- `banner`   a whistle or crowd-surge banner for the TV view (fixed slot per type)
- `meters`   once per second: atmosphere (level + mood) and momentum
- `feed`     a companion-feed item, tagged with a tier the user's profile filters on
- `analysis` a stoppage-analysis request (fact pack included), released only
             while the ball is out of play
- `skip`     a decision to show nothing, kept for the trace

No AI runs here. Agents only word what this module decided to say.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy

from . import derive
from .factpack import build_factpack
from .model import MatchModel

# Banner types and their fixed slots on the TV view.
BANNERS = {
    "foul": {"label": "Foul", "slot": "whistle-1", "secs": 3.0},
    "offside": {"label": "Offside", "slot": "whistle-2", "secs": 3.0},
    "penalty": {"label": "Penalty", "slot": "whistle-3", "secs": 4.0},
    "stoppage": {"label": "Stoppage", "slot": "whistle-4", "secs": 3.0},
    "whistle": {"label": "Whistle", "slot": "whistle-4", "secs": 3.0},
    "kick_off": {"label": "Kick-off", "slot": "period", "secs": 3.0},
    "half_time": {"label": "Half-time", "slot": "period", "secs": 4.0},
    "full_time": {"label": "Full-time", "slot": "period", "secs": 4.0},
    "crowd": {"label": "Crowd erupts", "slot": "crowd", "secs": 3.0},
}

WHISTLE_WAIT_S = 2.0  # wait this long for the feed to explain a whistle, then show it generic
WHISTLE_MATCH_S = 4.0
SURGE_JUMP, SURGE_MIN_LEVEL, SURGE_COOLDOWN = 0.22, 0.55, 12.0
TIER_BIG, TIER_BALANCED, TIER_ALL = 1, 2, 3
AMOUNT_MAX_TIER = {"big": TIER_BIG, "balanced": TIER_BALANCED, "everything": TIER_ALL}


@dataclass
class PendingWhistle:
    rec: dict
    shown: str | None = None  # cue id once a banner went out
    resolved: str | None = None


@dataclass
class ScheduledAnalysis:
    due: float
    kind: str
    trigger: dict
    tier: int
    needs_dead_ball: bool = True


@dataclass
class AttentionEngine:
    model: MatchModel
    now: float = 0.0
    pending: list[PendingWhistle] = field(default_factory=list)
    scheduled: list[ScheduledAnalysis] = field(default_factory=list)
    expect: str | None = "kick_off"  # what the next whistle most likely is, from context
    expect_until: float = 600.0
    last_surge: float = -1e9
    last_goal_t: float = -1e9
    var_open: dict | None = None
    penalty_pending: bool = False
    momentum_zone: str = "even"
    half_start_t: float = 0.0
    n_cue: int = 0
    n_in: int = 0  # feed and whistle records received
    shot_feeds: dict = field(default_factory=dict)

    # ---------- helpers ----------
    def _cue_id(self) -> str:
        self.n_cue += 1
        return f"cue_{self.n_cue:04d}"

    def _banner(self, btype: str, t: float, why: str, evidence: list[str], update_of: str | None = None,
                detail: str | None = None) -> dict:
        b = BANNERS[btype]
        return {"kind": "banner", "cue_id": update_of or self._cue_id(), "update": bool(update_of),
                "type": btype, "label": b["label"], "detail": detail, "slot": b["slot"],
                "t_start": round(t, 2), "t_end": round(t + b["secs"], 2), "why": why,
                "evidence": evidence}

    def _feed(self, ev: dict, tier: int, icon: str, basic: str, deep: str, team: str | None = None) -> dict:
        return {"kind": "feed", "cue_id": self._cue_id(), "t": ev["t"], "clock": ev.get("clock"),
                "tier": tier, "icon": icon, "team": team if team is not None else ev.get("team"),
                "text": {"basic": basic, "deep": deep}, "evidence": [ev["id"]]}

    # ---------- main entry points ----------
    def ingest(self, rec: dict, now: float) -> list[dict]:
        self.now = now
        self.model.ingest(rec)
        if rec.get("stream"):
            return []
        out = []
        for ev in self.model.changes:
            self.n_in += 1
            if ev["type"] == "whistle":
                out += self._on_whistle(ev)
            else:
                out += self._resolve_whistles(ev)
                out += self._route(ev)
        return out

    def tick(self, now: float) -> list[dict]:
        """Once per second of match time."""
        self.now = now
        self.model.tick(now)
        out: list[dict] = []
        # whistles the feed has not explained yet: show them generic
        for pw in self.pending:
            if not pw.shown and not pw.resolved and now - pw.rec["t"] >= WHISTLE_WAIT_S:
                b = self._banner("whistle", pw.rec["t"] + WHISTLE_WAIT_S, "whistle detected; feed has not said why yet",
                                 [pw.rec["id"]])
                pw.shown = b["cue_id"]
                out.append(b)
        self.pending = [p for p in self.pending if now - p.rec["t"] < WHISTLE_MATCH_S + 2]
        # crowd surge
        jump = self.model.crowd_jump(3)
        level = self.model.crowd_level()
        if jump >= SURGE_JUMP and level >= SURGE_MIN_LEVEL and now - self.last_surge > SURGE_COOLDOWN:
            self.last_surge = now
            out.append(self._banner("crowd", now, f"crowd level rose {jump:+.2f} in 3 s to {level:.2f}",
                                    [f"crowd@{int(now)}"]))
        # stoppage analysis that is due
        for sa in list(self.scheduled):
            if sa.due > now:
                continue
            self.scheduled.remove(sa)
            if sa.needs_dead_ball and self.model.ball_in_play:
                out.append({"kind": "skip", "t": now, "what": f"analysis:{sa.kind}",
                            "why": "play restarted before there was time to read it"})
                continue
            out.append({"kind": "analysis", "cue_id": self._cue_id(), "t": round(now, 2),
                        "clock": self.model.clock, "moment": sa.kind, "tier": sa.tier,
                        "factpack": build_factpack(self.model, sa.kind, sa.trigger)})
        out.append(self._meters(now))
        out += self._momentum_swing()
        return out

    def _expect(self, what: str, for_s: float):
        self.expect, self.expect_until = what, self.now + for_s

    # ---------- whistles ----------
    def _on_whistle(self, w: dict) -> list[dict]:
        q = w["whistle"]
        clock_s = derive.clock_seconds(w["clock"])
        # audio patterns alone are enough for the end of a half
        if q["blasts"] == 3:
            return [self._banner("full_time", w["t"], "three long blasts", [w["id"]])]
        if q["blasts"] == 2 and q["length"] == "long" and 2700 <= clock_s < 5400 and w["period"] == 1:
            return [self._banner("half_time", w["t"], "two long blasts at the end of the first half", [w["id"]])]
        self.pending.append(PendingWhistle(w))
        # A linked reason can itself have been delivered before the audio detection.
        for ev in self.model.events:
            if ev.get("whistle_id") == w["id"] or ev.get("trigger_event_id") == w["id"]:
                resolved = self._resolve_whistles(ev)
                if self.pending[-1].resolved:
                    return resolved
        return []

    def _resolve_whistles(self, ev: dict) -> list[dict]:
        etype = ev["type"]
        reason, detail = None, None
        if etype == "referee_decision" and ev["decision"] == "penalty":
            reason = "penalty"
        elif etype == "referee_decision" and ev["decision"] == "free_kick":
            reason = "foul"
        elif etype == "foul" and not ev["foul"].get("advantage"):
            reason = "foul"
        elif etype == "offside":
            reason = "offside"
        elif etype == "var" and ev["var"]["phase"] == "check":
            reason = "stoppage"  # VAR itself goes to the app only; the screen just shows play stopped
        elif etype == "injury_stoppage":
            reason, detail = "stoppage", "Injury"
        elif etype == "set_piece" and ev["set_piece"]["kind"] in ("kick_off", "penalty"):
            reason = ev["set_piece"]["kind"] + "_restart"
        if not reason:
            return []
        stop = self.model.by_id.get(ev.get("stoppage_id"), {})
        whistle_id = ev.get("whistle_id") or ev.get("trigger_event_id")
        if etype == "referee_decision":
            whistle_id = ev.get("whistle_id") or stop.get("trigger_event_id")
        for pw in self.pending:
            if pw.rec["id"] != whistle_id:
                continue
            if pw.resolved == reason:
                return []
            pw.resolved = reason
            if reason == "penalty_restart":
                return []  # the restart whistle for a penalty kick gets no banner
            if reason == "kick_off_restart":
                reason = "kick_off"
                if self.expect == "kick_off":
                    self.expect = None
            why = f"whistle explained by feed event {ev['type']}"
            if reason == "penalty":
                why += " (explicit linked referee decision)"
            banner = self._banner(reason, pw.rec["t"], why, [pw.rec["id"], ev["id"]], update_of=pw.shown,
                                  detail=detail)
            pw.shown = banner["cue_id"]
            return [banner]
        return []

    # ---------- routing ----------
    def _route(self, ev: dict) -> list[dict]:
        m = self.model
        etype, team = ev["type"], ev.get("team")
        tn = m.team_name(team)
        who = m.player_name(ev.get("player_id"))
        out: list[dict] = []
        if etype == "period_start":
            self._expect("kick_off", 180)
            n = ev["period_start"]["period_no"]
            self.half_start_t = ev["t"]
            out.append(self._feed(ev, TIER_BIG, "whistle", "Kick-off!" if n == 1 else "Second half under way.",
                                  "Kick-off." if n == 1 else "Second half under way; ends have switched.",
                                  team=None))
        elif etype in {"shot", "shot_result", "shot_xg"}:
            shot = ev if etype == "shot" else m.by_id[ev["shot_id"]]
            out.append(self._shot_feed(shot))
            if etype == "shot_result" and ev["outcome"] == "goal":
                self.last_goal_t = ev["t"]
                self._expect("kick_off", 180)
                self.penalty_pending = False
                self._schedule(self.now + 8, "goal", shot, TIER_BIG)
        elif etype == "referee_decision":
            self.penalty_pending = ev["decision"] == "penalty"
            if self.penalty_pending:
                self._expect("penalty_kick", 180)
                out.append(self._feed(ev, TIER_BIG, "penalty", f"Penalty awarded to {tn}!",
                                      f"Penalty to {tn}: explicit referee decision.", team=team))
            elif ev.get("supersedes_decision_id"):
                text = f"Referee decision corrected: {ev['decision'].replace('_', ' ')}."
                out.append(self._feed(ev, TIER_BIG, "whistle", text, text, team=team))
            else:
                out.append({"kind": "skip", "t": ev["t"], "what": ev["id"], "why": "restart decision recorded"})
        elif etype == "card":
            c = ev["card"]["colour"]
            tier = TIER_BALANCED if c == "yellow" else TIER_BIG
            label = {"yellow": "Yellow card", "second_yellow": "Second yellow — sent off", "red": "Red card"}[c]
            out.append(self._feed(ev, tier, f"card_{'yellow' if c == 'yellow' else 'red'}",
                                  f"{label}: {who} ({tn}).",
                                  f"{label}: {who}, {m.player_role(ev['player_id'])}, {tn}. "
                                  f"{tn} now have {m.cards[team]['yellow']} yellow(s)."
                                  if c == "yellow" else f"{label}: {who}. {tn} down to {len(m.on_pitch[team])}."))
        elif etype == "var":
            v = ev["var"]
            if v["phase"] == "check":
                self.var_open = ev
                what = "a possible penalty" if v["incident"] == "penalty" else f"the {v['incident']}"
                out.append(self._feed(ev, TIER_BALANCED, "var", f"VAR is checking {what}.",
                                      f"VAR check: {v['incident']} (on-field decision: {v['original_decision'].replace('_', ' ')}).",
                                      team=None))
                self._schedule(ev["t"] + 8, "var_check", ev, TIER_BIG)
            elif v["phase"] == "on_field_review":
                out.append(self._feed(ev, TIER_BALANCED, "var", "The referee is going to the pitch-side monitor.",
                                      "On-field review: referee at the monitor.", team=None))
            elif v["phase"] == "decision":
                self.var_open = None
                if v["outcome"] == "overturned" and v["incident"] == "penalty":
                    self._expect("penalty", 6)
                    self.penalty_pending = True
                    txt = "VAR: PENALTY given. The decision is overturned."
                else:
                    txt = f"VAR: {v['incident']} — the decision stands."
                out.append(self._feed(ev, TIER_BIG, "var", txt, txt, team=None))
                if v["outcome"] == "overturned":
                    self._schedule(ev["t"] + 6, "var_decision", ev, TIER_BIG)
        elif etype == "foul":
            d = ev["derived"]
            if d.get("penalty_awarded") and d.get("called_on_field"):
                self.penalty_pending = True
                out.append(self._feed(ev, TIER_BIG, "penalty", f"Penalty to {m.team_name(_opp(team))}! {who} fouled in the box.",
                                      f"Penalty: {ev['foul']['kind']} by {who} inside the box.", team=_opp(team)))
            else:
                out.append({"kind": "skip", "t": ev["t"], "what": ev["id"],
                            "why": "ordinary foul: the whistle banner covers it"})
        elif etype == "set_piece" and ev["set_piece"]["kind"] == "penalty":
            self._expect("penalty_kick", 15)
        elif etype == "substitution":
            sub = ev["substitution"]
            out.append(self._feed(ev, TIER_BALANCED, "sub",
                                  f"Substitution, {tn}: {m.player_name(sub['on_id'])} on for {m.player_name(sub['off_id'])}.",
                                  f"Sub {tn}: {m.player_name(sub['on_id'])} ({m.player_role(sub['on_id'])}) replaces "
                                  f"{m.player_name(sub['off_id'])} ({m.player_role(sub['off_id'])}), {sub['reason']}."))
            self._schedule(ev["t"] + 3, "substitution", ev, TIER_BALANCED)
        elif etype == "injury_stoppage":
            out.append(self._feed(ev, TIER_ALL, "injury", f"Play stopped: {who} is down injured.",
                                  f"Injury stoppage: {who} ({tn})."))
            self._schedule(ev["t"] + 10, "injury", ev, TIER_ALL)
        elif etype == "added_time":
            mins = ev["added_time"]["minutes"]
            out.append(self._feed(ev, TIER_BALANCED, "clock", f"{mins} minutes of added time.",
                                  f"Added time: {mins} min.", team=None))
        elif etype == "period_end":
            self._expect("kick_off", 180)
            n = ev["period_end"]["period_no"]
            s = m.score
            txt = f"{'Half-time' if n == 1 else 'Full-time'}: {m.team_name('home')} {s['home']}–{s['away']} {m.team_name('away')}."
            out.append(self._feed(ev, TIER_BIG, "whistle", txt, txt, team=None))
            self._schedule(ev["t"] + 5, "half_time" if n == 1 else "full_time", ev, TIER_BIG, needs_dead_ball=False)
        else:
            out.append({"kind": "skip", "t": ev["t"], "what": ev["id"], "why": f"{etype}: visible on the pitch"})
        return out

    def _shot_feed(self, shot: dict) -> dict:
        q, d = shot["shot"], shot["derived"]
        outcome = q.get("outcome")
        who = self.model.player_name(shot["player_id"])
        text = f"Shot by {who}: {outcome.replace('_', ' ') if outcome else 'result pending'}."
        if outcome == "goal":
            text = f"GOAL! {who} scores for {self.model.team_name(shot['team'])}."
        deep = text + (f" Synthetic xG {d['xg']} ({d['xg_method']})." if d.get("xg") is not None
                       else " xG not yet available.")
        old = self.shot_feeds.get(shot["id"])
        feed = self._feed(shot, TIER_BIG if outcome == "goal" or q.get("penalty") else TIER_ALL,
                          "goal" if outcome == "goal" else "chance", text, deep)
        if old:
            feed["cue_id"] = old["cue_id"]
        feed.update(shot_id=shot["id"], update=bool(old), xg=d.get("xg"))
        feed["evidence"] += [d[k] for k in ("result_id", "xg_id") if d.get(k)]
        self.shot_feeds[shot["id"]] = deepcopy(feed)
        return feed

    def _schedule(self, due: float, kind: str, trigger: dict, tier: int, needs_dead_ball: bool = True):
        self.scheduled.append(ScheduledAnalysis(due, kind, trigger, tier, needs_dead_ball))

    # ---------- meters ----------
    def _meters(self, now: float) -> dict:
        m = self.model
        level = m.crowd_level()
        level5 = 1 + sum(level >= x for x in (0.3, 0.42, 0.55, 0.7))
        minute = derive.minute_of(m.clock)
        diff = abs(m.score["home"] - m.score["away"])
        if now - self.last_goal_t < 25 or (now - self.last_surge < 6 and level >= 0.7):
            mood, why = "eruption", "goal or sudden surge in the last seconds"
        elif self.var_open is not None:
            mood, why = "tension", "VAR check in progress"
        elif self.penalty_pending:
            mood, why = "tension", "penalty about to be taken"
        elif m.period == 2 and minute >= 75 and diff <= 1 and level >= 0.42:
            mood, why = "tension", "late in a close game"
        elif level >= 0.5:
            mood, why = "cheering", "sustained high crowd level"
        else:
            mood, why = "calm", "low crowd level, nothing happening"
        mom = m.momentum()
        return {"kind": "meters", "t": round(now, 2), "clock": m.clock, "period": m.period,
                "score": dict(m.score), "ball_in_play": m.ball_in_play,
                "atmosphere": {"level": round(level, 3), "level5": level5, "mood": mood, "why": why},
                "momentum": mom.as_dict()}

    def _momentum_swing(self) -> list[dict]:
        if self.model.t - self.half_start_t < 300:
            return []  # the 7-minute window is too thin early in a half
        mom = self.model.momentum()
        v = mom.value
        zone = self.momentum_zone
        if v >= 0.3:
            zone = "home"
        elif v <= -0.3:
            zone = "away"
        elif abs(v) < 0.15:
            zone = "even"
        if zone == self.momentum_zone:
            return []
        self.momentum_zone = zone
        if zone == "even":
            return []
        tn = self.model.team_name(zone)
        pseudo = {"id": f"momentum@{int(self.now)}", "t": self.now, "clock": self.model.clock, "team": zone}
        poss = mom.possession_home if zone == "home" else 1 - mom.possession_home
        return [self._feed(pseudo, TIER_ALL, "momentum", f"{tn} are on top right now.",
                           f"Momentum {tn}: {round(poss * 100)}% possession, "
                           f"{mom.key_passes[zone]} key passes and {mom.shots[zone]} shots in the last 7 min.")]


def _opp(side: str) -> str:
    return "away" if side == "home" else "home"


def visible_to(output: dict, amount: str) -> bool:
    """Profile filter for feed and analysis items ("how much do you want")."""
    if output["kind"] not in ("feed", "analysis"):
        return True
    return output["tier"] <= AMOUNT_MAX_TIER.get(amount, TIER_BALANCED)
