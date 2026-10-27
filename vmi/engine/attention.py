"""The Attention Engine: deterministic routing, timing and depth.

It reads the delivered streams in order and emits outputs, each with a `why`:

- `banner`   one event marker for the TV view (shared fixed slot)
- `meters`   once per second: atmosphere/availability and momentum
- `feed`     a companion-feed item, tagged with a tier the user's profile filters on
- `analysis` a stoppage-analysis request (fact pack included), released only
             while the ball is out of play
- `skip`     a decision to show nothing, kept for the trace

No AI runs here. Agents only word what this module decided to say.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import math

from . import derive
from .factpack import build_factpack
from .model import MatchModel
from .atmosphere import Atmosphere, FRESH_S, CROWD_FRESH_S

# Approved event markers share one screen location; crowd is represented by bars.
BANNERS = {
    "foul": {"label": "Foul", "slot": "event", "secs": 3.0},
    "offside": {"label": "Offside", "slot": "event", "secs": 3.0},
    "penalty": {"label": "Penalty", "slot": "event", "secs": 4.0},
    "stoppage": {"label": "Stoppage", "slot": "event", "secs": 3.0},
    "whistle": {"label": "Whistle", "slot": "event", "secs": 3.0},
    "kick_off": {"label": "Kick-off", "slot": "event", "secs": 3.0},
    "half_time": {"label": "Half-time", "slot": "event", "secs": 4.0},
    "full_time": {"label": "Full-time", "slot": "event", "secs": 4.0},
    "drinks_break": {"label": "Drinks break", "slot": "event", "secs": 3.0},
}

WHISTLE_WAIT_S = 2.0  # wait this long for the feed to explain a whistle, then show it generic
BIG_CHANCE_XG = 0.25  # a missed shot at or above this synthetic xG is called a big chance
MILESTONES = (3, 5)  # a player's shots or key passes are mentioned when they reach these counts
MOMENTUM_REPLY_S = 600.0  # a goal links to the analyst's momentum call made this recently
TIER_BIG, TIER_BALANCED, TIER_ALL = 1, 2, 3
AMOUNT_MAX_TIER = {"big": TIER_BIG, "balanced": TIER_BALANCED, "everything": TIER_ALL}


@dataclass
class PendingWhistle:
    rec: dict
    detected_t: float = 0.0
    shown_t: float | None = None
    shown: str | None = None  # cue id once a marker went out
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
    last_goal_t: float = -1e9
    var_open: dict | None = None
    penalty_pending: bool = False
    momentum_zone: str = "even"
    half_start_t: float = 0.0
    n_cue: int = 0
    n_in: int = 0  # feed and whistle records received
    shot_feeds: dict = field(default_factory=dict)
    cue_by_event: dict = field(default_factory=dict)  # event id -> feed cue_id, so analysis can reply to it
    last_momentum: dict | None = None  # the analyst's latest "on top" call: team, t, cue_id
    said: set = field(default_factory=set)  # big chances and player milestones already mentioned
    atmosphere: Atmosphere = field(default_factory=Atmosphere)
    last_atmosphere: dict | None = None

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

    def _feed(self, ev: dict, tier: int, icon: str, basic: str, deep: str, team: str | None = None,
              speaker: str = "commentator") -> dict:
        cue = self._cue_id()
        self.cue_by_event[ev["id"]] = cue
        return {"kind": "feed", "cue_id": cue, "t": ev["t"], "clock": ev.get("clock"),
                "tier": tier, "icon": icon, "team": team if team is not None else ev.get("team"),
                "text": {"basic": basic, "deep": deep}, "evidence": [ev["id"]], "speaker": speaker,
                "reply_to": None, "say": self._say(ev, team)}

    def _say(self, ev: dict, team: str | None) -> dict:
        """The facts a chat voice may use to word this item, taken from the event and the
        score at that moment. Code picks the wording (vmi/agents/voices.py); nothing new is claimed."""
        m = self.model
        side = team if team is not None else ev.get("team")
        say = {"type": ev.get("type"), "who": m.player_name(ev.get("player_id")), "team": m.team_name(side) if side else None,
               "score": f"{m.team_name('home')} {m.score['home']}–{m.score['away']} {m.team_name('away')}"}
        etype = ev.get("type")
        if etype == "card":
            say["colour"] = ev["card"]["colour"]
            say["left"] = len(m.on_pitch[ev["team"]])
        elif etype == "var":
            v = ev["var"]
            say.update(phase=v["phase"], incident=v["incident"], outcome=v.get("outcome"))
        elif etype == "substitution":
            say.update(on=m.player_name(ev["substitution"]["on_id"]), off=m.player_name(ev["substitution"]["off_id"]))
        elif etype == "added_time":
            say["minutes"] = ev["added_time"]["minutes"]
        elif etype in ("period_start", "period_end"):
            say["period"] = ev[etype]["period_no"]
        elif etype == "shot":
            say.update(outcome=ev["shot"].get("outcome"), penalty=bool(ev["shot"].get("penalty")))
        return say

    # ---------- main entry points ----------
    def ingest(self, rec: dict, now: float) -> list[dict]:
        stamps = (now, rec.get("t"), rec.get("delivered_t", rec.get("t")))
        if any(not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t) or t < 0 for t in stamps):
            raise ValueError("invalid delivery clock")
        if stamps[1] > now + 1e-9 or stamps[2] > now + 1e-9:
            raise ValueError("record has not been delivered at this snapshot")
        self.now = now
        score_before = dict(self.model.score)
        self.model.ingest(rec)
        self.model.t = now
        if rec.get("stream"):
            if rec["stream"] in {"tracking", "crowd"}:
                a = self.atmosphere.evaluate(now, self.model.tracking, self.model.ball_in_play, self.model.crowd)
                if a != self.last_atmosphere:
                    return [self._meters(now, a)]
            return []
        out = []
        for ev in self.model.changes:
            self.n_in += 1
            if ev["type"] == "whistle":
                out += self._on_whistle(ev)
            else:
                out += self._resolve_whistles(ev)
                out += self._route(ev)
        if self.model.changes:
            a = self.atmosphere.evaluate(now, self.model.tracking, self.model.ball_in_play, self.model.crowd)
            if a != self.last_atmosphere or self.model.score != score_before:
                out.append(self._meters(now, a))
        return out

    def tick(self, now: float) -> list[dict]:
        """Once per second of match time."""
        self.now = now
        self.model.tick(now)
        out: list[dict] = []
        out += self.poll_whistles(now)
        out += self.release_analysis(now)
        out.append(self._meters(now))
        out += self._momentum_swing()
        return out

    def next_whistle_due(self) -> float:
        return min((p.detected_t + WHISTLE_WAIT_S for p in self.pending
                    if not p.shown and not p.resolved), default=float("inf"))

    def poll_whistles(self, now: float) -> list[dict]:
        self.now = now
        out = []
        for pw in self.pending:
            if not pw.shown and not pw.resolved and now + 1e-9 >= pw.detected_t + WHISTLE_WAIT_S:
                start = pw.detected_t + WHISTLE_WAIT_S
                cue = self._banner("whistle", start, "whistle detected; feed has not said why yet", [pw.rec["id"]])
                pw.shown, pw.shown_t = cue["cue_id"], start
                out.append(cue)
        self.pending = [p for p in self.pending if now - p.detected_t < 120][-64:]
        return out

    def next_analysis_due(self) -> float:
        due = min((sa.due for sa in self.scheduled), default=float("inf"))
        return max(self.now, due)

    def release_analysis(self, now: float) -> list[dict]:
        self.now = self.model.t = now
        out = []
        for sa in list(self.scheduled):
            if sa.due > now:
                continue
            self.scheduled.remove(sa)
            if sa.needs_dead_ball and self.model.ball_in_play:
                out.append({"kind": "skip", "t": now, "what": f"analysis:{sa.kind}",
                            "why": "play restarted before there was time to read it"})
                continue
            # The analyst replies to the commentator's item for the event it explains: one reply,
            # written once per scheduled moment, so the two voices can't trigger each other.
            out.append({"kind": "analysis", "cue_id": self._cue_id(), "t": round(now, 2),
                        "clock": self.model.clock, "moment": sa.kind, "tier": sa.tier,
                        "reply_to": self.cue_by_event.get(sa.trigger.get("id")),
                        "factpack": build_factpack(self.model, sa.kind, sa.trigger)})
        return out

    def next_meter_expiry(self) -> float:
        deadlines = []
        frame = self.model.tracking
        if self.atmosphere.attack and frame:
            stamps = (frame["t"], frame["quality"]["sample_t"], frame["possession"]["sample_t"])
            deadlines.append(min(stamps) + FRESH_S + 0.000001)
        if self.last_atmosphere and self.last_atmosphere["crowd_available"] and self.model.crowd:
            deadlines.append(self.model.crowd[-1][0] + CROWD_FRESH_S + 0.000001)
        return max(self.now, min(deadlines)) if deadlines else float("inf")

    def poll_meters(self, now: float) -> list[dict]:
        """Expire missing inputs even when no new packet arrives; do not sample possession twice."""
        self.now = self.model.t = now
        a = self.atmosphere.evaluate(now, self.model.tracking, self.model.ball_in_play, self.model.crowd)
        return [self._meters(now, a)] if a != self.last_atmosphere else []

    def _expect(self, what: str, for_s: float):
        self.expect, self.expect_until = what, self.now + for_s

    # ---------- whistles ----------
    def _on_whistle(self, w: dict) -> list[dict]:
        q = w["whistle"]
        clock_s = derive.clock_seconds(w["clock"])
        # audio patterns alone are enough for the end of a half
        if q["blasts"] == 3:
            return [self._banner("full_time", self.now, "three long blasts", [w["id"]])]
        if q["blasts"] == 2 and q["length"] == "long" and 2700 <= clock_s < 5400 and w["period"] == 1:
            return [self._banner("half_time", self.now, "two long blasts at the end of the first half", [w["id"]])]
        self.pending.append(PendingWhistle(w, detected_t=self.now))
        self.pending = self.pending[-64:]
        # A linked reason can itself have been delivered before the audio detection.
        # Prefer the current explicit decision over its original foul/handball.
        # Delivery can put the entire correction chain before the audio record.
        current = set(self.model.decision_by_stop.values())
        reasons = sorted(self.model.events, key=lambda ev: ev["id"] not in current)
        for ev in reasons:
            if self._whistle_link(ev) == w["id"]:
                resolved = self._resolve_whistles(ev)
                if self.pending[-1].resolved:
                    return resolved
        return []

    def _whistle_link(self, ev: dict) -> str | None:
        if ev["type"] == "referee_decision":
            stop = self.model.by_id.get(ev.get("stoppage_id"), {})
            return ev.get("whistle_id") or stop.get("trigger_event_id")
        return ev.get("whistle_id") or ev.get("trigger_event_id")

    def _resolve_whistles(self, ev: dict) -> list[dict]:
        etype = ev["type"]
        if etype == "referee_decision" and self.model.decision_by_stop.get(ev["stoppage_id"]) != ev["id"]:
            return []
        reason, detail = None, None
        if etype == "referee_decision" and ev["decision"] == "penalty":
            reason = "penalty"
        elif etype == "referee_decision" and ev["decision"] == "free_kick":
            reason = "foul"
        elif etype == "foul" and not ev["foul"].get("advantage"):
            reason = "foul"
        elif etype == "handball":
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
        whistle_id = self._whistle_link(ev)
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
            start = pw.shown_t if pw.shown_t is not None else self.now
            banner = self._banner(reason, start, why, [pw.rec["id"], ev["id"]], update_of=pw.shown,
                                  detail=detail)
            pw.shown, pw.shown_t = banner["cue_id"], start
            return [banner]
        return []

    # ---------- routing ----------
    def _route(self, ev: dict) -> list[dict]:
        m = self.model
        etype, team = ev["type"], ev.get("team")
        if etype == "referee_decision" and m.decision_by_stop.get(ev["stoppage_id"]) != ev["id"]:
            return []  # several buffered decisions can resolve in this same batch
        tn = m.team_name(team)
        who = m.player_name(ev.get("player_id"))
        out: list[dict] = []
        if etype == "drinks_break":
            out.append(self._banner("drinks_break", self.now, "delivered drinks break; restart remains pending", [ev["id"]]))
        elif etype == "period_start":
            self._expect("kick_off", 180)
            n = ev["period_start"]["period_no"]
            self.half_start_t = ev["t"]
            out.append(self._feed(ev, TIER_BIG, "whistle", "Kick-off!" if n == 1 else "Second half under way.",
                                  "Kick-off." if n == 1 else "Second half under way; ends have switched.",
                                  team=None))
        elif etype in {"shot", "shot_result", "shot_xg", "goal_cancelled"}:
            shot = ev if etype == "shot" else m.by_id[ev["shot_id"]]
            out.append(self._shot_feed(shot))
            out += self._shot_followups(shot)
            if etype == "goal_cancelled":
                self.scheduled = [sa for sa in self.scheduled if not (sa.kind == "goal" and sa.trigger["id"] == shot["id"])]
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
        deep = text + (f" xG {d['xg']}." if d.get("xg") is not None
                       else " xG not yet available.")
        old = self.shot_feeds.get(shot["id"])
        feed = self._feed(shot, TIER_BIG if outcome == "goal" or q.get("penalty") else TIER_ALL,
                          "goal" if outcome == "goal" else "chance", text, deep)
        if old:
            feed["cue_id"] = old["cue_id"]
            feed["reply_to"] = old["reply_to"]
        elif outcome == "goal":
            feed["reply_to"] = self._momentum_reply(shot)
        self.cue_by_event[shot["id"]] = feed["cue_id"]
        feed.update(shot_id=shot["id"], update=bool(old), xg=d.get("xg"))
        feed["evidence"] += [d[k] for k in ("result_id", "xg_id") if d.get(k)]
        self.shot_feeds[shot["id"]] = deepcopy(feed)
        return feed

    def _shot_followups(self, shot: dict) -> list[dict]:
        """Replies to a shot item, each said once: Ada calls a missed big chance once its delivered
        synthetic xG reaches BIG_CHANCE_XG; Kai notes a player reaching 3 or 5 shots or key passes.
        Counts are what has been delivered so far; the engine derives key passes."""
        m, out = self.model, []
        q, d = shot["shot"], shot["derived"]
        cue = self.cue_by_event.get(shot["id"])
        outcome, xg = q.get("outcome"), d.get("xg")
        if outcome and outcome not in ("goal", "disallowed") and xg is not None and xg >= BIG_CHANCE_XG                 and ("big", shot["id"]) not in self.said:
            self.said.add(("big", shot["id"]))
            who, xg = m.player_name(shot["player_id"]), round(xg, 2)
            ev = {"id": f"{shot['id']}:big", "t": self.now, "clock": m.clock, "team": shot["team"]}
            item = self._feed(ev, TIER_BALANCED, "big_chance", f"Big chance missed by {who}: {xg} xG.",
                              f"Big chance missed: {who}, {xg} xG ({outcome.replace('_', ' ')}).",
                              speaker="analyst")
            item.update(reply_to=cue, evidence=[shot["id"]] + [d[k] for k in ("xg_id",) if d.get(k)])
            item["say"].update(who=who, xg=xg)
            out.append(item)
        if q.get("outcome") == "disallowed":
            return out
        shooter = shot["player_id"]
        shots = sum(1 for s in m.shots_by_id.values() if s["player_id"] == shooter
                    and s["shot"].get("outcome") != "disallowed")
        out += self._milestone(shot, cue, shooter, "shots", shots)
        passer = m.by_id.get(d.get("preparing_pass_id"), {}).get("player_id")
        if passer:
            kps = sum(1 for pid in m.prepared_passes if m.by_id[pid]["player_id"] == passer)
            out += self._milestone(shot, cue, passer, "key_passes", kps)
        return out

    def _milestone(self, shot: dict, cue: str | None, pid: str, kind: str, n: int) -> list[dict]:
        if n not in MILESTONES or (kind, pid, n) in self.said:
            return []
        self.said.add((kind, pid, n))
        m = self.model
        who = m.player_name(pid)
        ev = {"id": f"{shot['id']}:{kind}{n}", "t": self.now, "clock": m.clock, "team": m.players[pid]["team"]}
        text = (f"That's {n} shots for {who} now." if kind == "shots"
                else f"{who} has set up {n} shots now: {n} key passes.")
        item = self._feed(ev, TIER_BALANCED, "milestone", text, text)
        item.update(reply_to=cue, evidence=[shot["id"]])
        item["say"].update(who=who, n=n, stat=kind)
        return [item]

    def _momentum_reply(self, shot: dict) -> str | None:
        """A goal builds on the analyst's "on top" call when it came from the same team within
        the last 10 minutes. Only a link: the text claims nothing about cause."""
        lm = self.last_momentum
        if lm and lm["team"] == shot["team"] and 0 <= shot["t"] - lm["t"] <= MOMENTUM_REPLY_S:
            return lm["cue_id"]
        return None

    def _schedule(self, due: float, kind: str, trigger: dict, tier: int, needs_dead_ball: bool = True):
        self.scheduled.append(ScheduledAnalysis(due, kind, trigger, tier, needs_dead_ball))

    # ---------- meters ----------
    def _meters(self, now: float, atmosphere: dict | None = None) -> dict:
        m = self.model
        a = atmosphere if atmosphere is not None else self.atmosphere.evaluate(now, m.tracking, m.ball_in_play, m.crowd)
        self.last_atmosphere = dict(a)
        mom = m.momentum()
        return {"kind": "meters", "t": round(now, 2), "clock": m.clock, "period": m.period,
                "score": dict(m.score), "ball_in_play": m.ball_in_play,
                "atmosphere": a,
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
        possession_text = f"{round(poss * 100)}% possession" if mom.possession_available else "possession unavailable"
        feed = self._feed(pseudo, TIER_ALL, "momentum", f"{tn} are on top right now.",
                          f"Momentum {tn}: {possession_text}, "
                          f"{mom.key_passes[zone]} key passes and {mom.shots[zone]} shots in the last 7 min.",
                          speaker="analyst")
        self.last_momentum = {"team": zone, "t": self.now, "cue_id": feed["cue_id"]}
        return [feed]


def _opp(side: str) -> str:
    return "away" if side == "home" else "home"


def visible_to(output: dict, amount: str) -> bool:
    """Profile filter for feed and analysis items ("how much do you want")."""
    if output["kind"] not in ("feed", "analysis"):
        return True
    return output["tier"] <= AMOUNT_MAX_TIER.get(amount, TIER_BALANCED)
