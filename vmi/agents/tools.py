"""Read-only tools over the engine's match model.

Agents call these instead of seeing raw data. Every result carries the IDs of
the events or stats it came from, so answers can show their receipts.
"""

from __future__ import annotations

import re

from ..engine import derive
from ..engine.model import MatchModel
from . import rules

POSITIONS = {"GK": "goalkeeper", "RB": "right-back", "CB": "centre-back", "LB": "left-back",
             "CM": "central midfielder", "DM": "defensive midfielder", "RW": "right winger",
             "ST": "striker", "LW": "left winger"}
SHOWN_TYPES = {"shot", "card", "substitution", "var", "foul", "offside", "injury_stoppage", "period_end",
               "period_start", "added_time"}


def _side(m: MatchModel, team: str | None) -> str | None:
    if not team:
        return None
    t = team.lower()
    for side in ("home", "away"):
        if t == side or t in m.team_name(side).lower() or t == m.meta["teams"][side]["short"].lower():
            return side
    return None


def describe_event(m: MatchModel, e: dict) -> str:
    who = m.player_name(e.get("player_id"))
    tn = m.team_name(e.get("team"))
    t = e["type"]
    if t == "shot":
        q = e["shot"]
        xg = e["derived"].get("xg")
        kind = "penalty" if q.get("penalty") else (q.get("body_part") or "shot").replace("_", " ")
        return f"{who} ({tn}) {kind}: {q['outcome'].replace('_', ' ')}" + (f", xG {xg}" if xg is not None else "")
    if t == "card":
        return f"{e['card']['colour'].replace('_', ' ')} card for {who} ({tn})"
    if t == "substitution":
        s = e["substitution"]
        return f"{tn} sub: {m.player_name(s['on_id'])} on for {m.player_name(s['off_id'])} ({s['reason']})"
    if t == "var":
        v = e["var"]
        return f"VAR {v['phase'].replace('_', ' ')}: {v['incident']}" + (f", {v['outcome']}" if v.get("outcome") else "")
    if t == "foul":
        d = e["derived"]
        extra = " in the box (penalty)" if d.get("penalty_awarded") else (" (advantage played)" if e["foul"].get("advantage") else "")
        return f"foul by {who} ({tn}) on {m.player_name(e['foul'].get('victim_id'))}{extra}"
    if t == "offside":
        return f"{who} ({tn}) caught offside"
    if t == "injury_stoppage":
        return f"{who} ({tn}) down injured, play stopped"
    if t == "period_end":
        return "half-time" if e["period_end"]["period_no"] == 1 else "full-time"
    if t == "period_start":
        return "kick-off" if e["period_start"]["period_no"] == 1 else "second half kick-off"
    if t == "added_time":
        return f"{e['added_time']['minutes']} minutes added"
    return t


class MatchTools:
    """The functions exposed to agents. All read-only."""

    def __init__(self, model: MatchModel):
        self.m = model

    def get_score_and_clock(self) -> dict:
        """Current score, clock, period and whether the ball is in play."""
        m = self.m
        return {"home": m.team_name("home"), "away": m.team_name("away"), "score": dict(m.score),
                "clock": m.clock, "period": m.period, "ball_in_play": m.ball_in_play,
                "minutes_left": m.minutes_left(), "evidence": ["state"]}

    def get_events(self, from_minute: int = 0, to_minute: int = 120, types: str = "") -> dict:
        """Notable events between two match minutes. `types` is an optional comma list,
        e.g. "shot,card". Returns at most 25 events, newest last."""
        m = self.m
        wanted = {t.strip() for t in types.split(",") if t.strip()} or SHOWN_TYPES
        out = []
        for e in m.events:
            if e["type"] not in wanted:
                continue
            minute = derive.minute_of(e["clock"])
            if from_minute <= minute <= to_minute:
                out.append({"id": e["id"], "minute": minute, "clock": e["clock"], "what": describe_event(m, e)})
        return {"events": out[-25:], "evidence": [e["id"] for e in out[-25:]]}

    def get_team_stats(self, last_minutes: int = 0) -> dict:
        """Team stats for the whole match so far, or only the last N minutes."""
        since = self.m.t - last_minutes * 60 if last_minutes else None
        st = self.m.team_stats(since)
        return {"window": f"last {last_minutes} min" if last_minutes else "match so far",
                self.m.team_name("home"): st["home"], self.m.team_name("away"): st["away"],
                "note": "xG is our estimate from shot location and angle",
                "evidence": ["stat:match"]}

    def get_momentum(self) -> dict:
        """Momentum over the last 7 minutes: possession, key passes and shots (40/30/30)."""
        mom = self.m.momentum().as_dict()
        mom["home_team"] = self.m.team_name("home")
        mom["away_team"] = self.m.team_name("away")
        mom["evidence"] = ["stat:momentum"]
        return mom

    def get_attack_pattern(self, team: str, last_minutes: int = 15) -> dict:
        """Which flank a team's shots and passes into the box came from recently."""
        side = _side(self.m, team)
        if not side:
            return {"error": f"unknown team {team!r}"}
        z = self.m.attack_zones(side, self.m.t - last_minutes * 60)
        return {"team": self.m.team_name(side), "last_minutes": last_minutes, "counts": z,
                "evidence": ["stat:zones"]}

    def get_player(self, name_or_number: str) -> dict:
        """A player's position and involvement so far. Accepts a surname or "#9" with a team."""
        m = self.m
        q = name_or_number.lower().strip()
        num = re.search(r"\d+", q)
        hits = [p for p in m.players.values()
                if p["name"].lower() in q or q in p["name"].lower()
                or (num and str(p["number"]) == num.group() and (m.team_name(p["team"]).lower().split()[0] in q
                                                                  or p["team"] in q))]
        if not hits and num:
            hits = [p for p in m.players.values() if str(p["number"]) == num.group()]
        if not hits:
            return {"error": f"no player matching {name_or_number!r}"}
        res = []
        for p in hits[:2]:
            evs = [e for e in m.events if e.get("player_id") == p["id"] and e["type"] in SHOWN_TYPES | {"pass"}]
            passes = [e for e in evs if e["type"] == "pass"]
            shots = [e for e in evs if e["type"] == "shot"]
            res.append({
                "id": p["id"], "name": p["name"], "number": p["number"], "team": m.team_name(p["team"]),
                "position": POSITIONS.get(p["position"], p["position"]),
                "on_pitch": p["id"] in m.on_pitch[p["team"]],
                "passes": len(passes),
                "passes_completed": sum(1 for e in passes if e["pass"]["outcome"] == "complete"),
                "key_passes": sum(1 for e in passes if e["derived"].get("key_pass")),
                "shots": [describe_event(m, e) for e in shots],
                "other": [f"{e['clock']} {describe_event(m, e)}" for e in evs if e["type"] not in ("pass", "shot")],
                "evidence": [e["id"] for e in shots] + [e["id"] for e in evs if e["type"] not in ("pass", "shot")],
            })
        return {"players": res, "evidence": [i for r in res for i in r["evidence"]]}

    def get_crowd_peaks(self, top: int = 3) -> dict:
        """When the crowd was loudest, and which logged event came just before. Timing only:
        the crowd level does not say why people got loud."""
        m = self.m
        series = list(m.crowd)
        peaks = []
        for i in range(2, len(series) - 2):
            t, lv = series[i]
            if lv >= max(x[1] for x in series[i - 2:i + 3]) and lv > 0.55:
                peaks.append((lv, t))
        peaks.sort(reverse=True)
        out = []
        for lv, t in peaks[:top]:
            before = next((e for e in reversed(m.events) if t - 8 <= e["t"] <= t and e["type"] in SHOWN_TYPES | {"tackle"}), None)
            out.append({"t": t, "level": lv, "just_after": describe_event(m, before) if before else None,
                        "event_id": before["id"] if before else None})
        return {"peaks": out, "note": "the crowd sensor measures loudness only (last 10 min kept)",
                "evidence": [p["event_id"] for p in out if p["event_id"]]}

    def get_rule(self, topic: str) -> dict:
        """Plain-language Laws of the Game explanation for a topic (offside, penalty, VAR, cards...)."""
        return rules.lookup(topic)

    def all(self) -> list:
        return [self.get_score_and_clock, self.get_events, self.get_team_stats, self.get_momentum,
                self.get_attack_pattern, self.get_player, self.get_crowd_peaks, self.get_rule]
