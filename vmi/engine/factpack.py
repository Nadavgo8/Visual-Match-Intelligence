"""Fact packs: the only material the explainer may use.

Built by code from the delivered feed. Every fact has the ID of the event (or
stat) it came from, so each sentence the explainer writes can carry receipts.
"""

from __future__ import annotations
from copy import deepcopy

from . import derive
from .model import MatchModel

PEAK_MOMENTS = {"goal", "var_decision"}


def _opp(side: str) -> str:
    return "away" if side == "home" else "home"


def _player(m: MatchModel, pid: str | None) -> dict | None:
    p = m.players.get(pid or "")
    if not p:
        return None
    return {"id": pid, "name": p["name"], "number": p["number"], "position": m.player_role(pid),
            "team": m.team_name(p["team"])}


def _carrier_before(m: MatchModel, ev: dict) -> dict | None:
    """Who had the ball for the attacking side just before a defender's action."""
    idx = m.events.index(ev)
    for prev in reversed(m.events[max(0, idx - 6):idx]):
        if prev.get("team") and prev["team"] != ev["team"] and prev.get("player_id"):
            if prev["type"] == "pass" and prev["pass"].get("outcome") == "complete" and prev["pass"].get("recipient_id"):
                return {"player": _player(m, prev["pass"]["recipient_id"]), "evidence": prev["id"]}
            return {"player": _player(m, prev["player_id"]), "evidence": prev["id"]}
    return None


def _crowd_fact(m: MatchModel, ev: dict) -> dict | None:
    r = m.crowd_reaction_after(ev["t"])
    if not r or r["delta"] < 0.12:
        return None
    return {"id": f"crowd@{int(ev['t'])}", "type": "crowd_reaction", "after": ev["id"],
            "rise": r["delta"], "peak": r["peak"],
            "note": "timing only: the crowd got louder right after this; the reason is not measured"}


def _deep_context(m: MatchModel, team: str | None) -> list[dict]:
    """Extra engine stats for the deep (analyst) level."""
    facts: list[dict] = []
    st = m.team_stats()
    facts.append({"id": "stat:match", "type": "match_stats",
                  "home": {k: st["home"][k] for k in ("shots", "shots_on_target", "xg", "key_passes", "corners")},
                  "away": {k: st["away"][k] for k in ("shots", "shots_on_target", "xg", "key_passes", "corners")}})
    mom = m.momentum()
    facts.append({"id": "stat:momentum", "type": "momentum_last_7_min",
                  "home_share_pct": round(mom.home_index * 100),
                  "away_share_pct": 100 - round(mom.home_index * 100),
                  "possession_home_pct": round(mom.possession_home * 100),
                  "key_passes": mom.key_passes, "shots": mom.shots, "window_minutes": 7})
    if team:
        since = max(0.0, m.t - 15 * 60)
        z = m.attack_zones(team, since)
        if sum(z.values()) >= 3:
            top = max(z, key=z.get)
            facts.append({"id": "stat:zones", "type": "attack_zones_last_15_min", "team": m.team_name(team),
                          "counts": z, "total": sum(z.values()), "most_used": top, "window_minutes": 15})
    return facts


def build_factpack(m: MatchModel, kind: str, trigger: dict) -> dict:
    team = trigger.get("team")
    pack: dict = {
        "moment": kind,
        "snapshot_t": m.t,
        "peak": kind in PEAK_MOMENTS,
        "clock": m.clock, "minute": derive.minute_of(m.clock), "period": m.period,
        "minutes_left": m.minutes_left() if kind != "full_time" else 0,
        "teams": {"home": m.team_name("home"), "away": m.team_name("away")},
        "score": dict(m.score),
        "facts": [],
        "context": {},
    }
    facts = pack["facts"]
    if kind == "goal":
        q, d = trigger["shot"], trigger["derived"]
        f = {"id": d["result_id"], "shot_id": trigger["id"], "type": "goal", "team": m.team_name(team), "scorer": _player(m, trigger["player_id"]),
             "penalty": q.get("penalty", False), "body_part": q.get("body_part"), "xg": d.get("xg"),
             "in_box": d.get("in_box")}
        facts.append(f)
        if d.get("xg_id"):
            facts.append({"id": d["xg_id"], "type": "shot_xg", "shot_id": trigger["id"],
                          "xg": d["xg"], "method_version": d["xg_method"]})
        for rid in trigger.get("related", []):
            p = m.by_id.get(rid)
            if p and p["type"] == "pass":
                facts.append({"id": p["id"], "type": "assist", "by": _player(m, p["player_id"]),
                              "cross": p["pass"].get("cross"), "through_ball": p["pass"].get("through_ball")})
        c = _crowd_fact(m, trigger)
        if c:
            facts.append(c)
        lead = m.score[team] - m.score[_opp(team)]
        pack["context"]["scoring_team_now"] = "leading" if lead > 0 else "level" if lead == 0 else "trailing"
        pack["context"]["goal_margin"] = abs(lead)
    elif kind in ("var_check", "var_decision"):
        v = trigger["var"]
        check = trigger
        if kind == "var_decision":
            check = next((e for e in m.events if e["type"] == "var" and e["var"]["review_id"] == v["review_id"]
                          and e["var"]["phase"] == "check"), trigger)
        facts.append({"id": check["id"], "type": "var_check", "incident": v["incident"],
                      "on_field_decision": v["original_decision"].replace("_", " "),
                      "referee_did_not_give": check["derived"].get("referee_did_not_give", False)})
        for rid in check.get("related", []):
            inc = m.by_id.get(rid)
            if not inc:
                continue
            if inc["type"] == "tackle":
                f = {"id": inc["id"], "type": "challenge", "by": _player(m, inc["player_id"]),
                     "inside_box": derive.in_own_box(inc["team"], inc["period"], inc.get("location"))}
                carrier = _carrier_before(m, inc)
                if carrier:
                    f["on"] = carrier["player"]
                facts.append(f)
                c = _crowd_fact(m, inc)
                if c:
                    facts.append(c)
            elif inc["type"] == "shot":
                facts.append({"id": inc["id"], "type": "goal_under_review", "scorer": _player(m, inc["player_id"]),
                              "team": m.team_name(inc["team"])})
        if kind == "var_decision":
            facts.append({"id": trigger["id"], "type": "var_decision", "outcome": v["outcome"],
                          "result": "penalty" if v["outcome"] == "overturned" and v["incident"] == "penalty" else v["incident"]})
            foul = next((e for e in reversed(m.events) if e["type"] == "foul" and e["t"] >= trigger["t"] - 1), None)
            if foul:
                pen_team = _opp(foul["team"])
                facts.append({"id": foul["id"], "type": "foul_given", "kind": foul["foul"]["kind"],
                              "by": _player(m, foul["player_id"]), "on": _player(m, foul["foul"].get("victim_id")),
                              "penalty_to": m.team_name(pen_team)})
                s = dict(m.score)
                s[pen_team] += 1
                pack["context"]["score_if_scored"] = s
    elif kind in ("half_time", "full_time"):
        st = m.team_stats()
        facts.append({"id": "stat:match", "type": "match_stats", "home": st["home"], "away": st["away"]})
        for e in m.events:
            if e["type"] == "shot" and e["shot"].get("outcome") == "goal":
                facts.append({"id": e["derived"]["result_id"], "type": "goal", "minute": derive.minute_of(e["clock"]),
                              "team": m.team_name(e["team"]), "scorer": _player(m, e["player_id"]),
                              "penalty": e["shot"].get("penalty", False)})
            elif e["type"] == "card" and e["card"]["colour"] != "yellow":
                facts.append({"id": e["id"], "type": "red_card", "minute": derive.minute_of(e["clock"]),
                              "player": _player(m, e["player_id"])})
        best = max((e for e in m.events if e["type"] == "shot" and e["shot"].get("outcome") in
                    {"saved", "blocked", "post", "off_target"}),
                   key=lambda e: e["derived"].get("xg") or 0, default=None)
        if best and (best["derived"].get("xg") or 0) >= 0.2:
            facts.append({"id": best["id"], "type": "best_missed_chance", "minute": derive.minute_of(best["clock"]),
                          "player": _player(m, best["player_id"]), "team": m.team_name(best["team"]),
                          "xg": best["derived"]["xg"], "outcome": best["shot"].get("outcome")})
    elif kind == "substitution":
        sub = trigger["substitution"]
        facts.append({"id": trigger["id"], "type": "substitution", "team": m.team_name(team),
                      "on": _player(m, sub["on_id"]), "off": _player(m, sub["off_id"]), "reason": sub["reason"]})
        lead = m.score[team] - m.score[_opp(team)]
        pack["context"]["team_situation"] = "leading" if lead > 0 else "level" if lead == 0 else "trailing"
    elif kind == "injury":
        facts.append({"id": trigger["id"], "type": "injury", "player": _player(m, trigger["player_id"]),
                      "team": m.team_name(team)})
        for rid in trigger.get("related", []):
            f = m.by_id.get(rid)
            if f and f["type"] == "foul":
                facts.append({"id": f["id"], "type": "foul_before", "by": _player(m, f["player_id"]),
                              "kind": f["foul"]["kind"]})
    pack["deep_context"] = _deep_context(m, team if kind not in ("half_time", "full_time") else None)
    return deepcopy(pack)
