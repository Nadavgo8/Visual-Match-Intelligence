"""Stoppage analysis: fact pack -> 2-3 sentences with receipts.

Two writers share one contract ({"sentences": [{"s": ..., "evidence": [...]}]}):
- the Foundry explainer agent (when configured), and
- deterministic templates, which are also the fallback when the agent's text
  fails validation.
The validator is plain code and runs on both.
"""

from __future__ import annotations

import json
import re
from asyncio import timeout

from .tools import POSITIONS
from .providers import TOTAL_TIMEOUT_S

VERB = {"trip": "tripped", "push": "pushed", "holding": "held", "kick": "kicked"}
CROWD_CAUSAL = re.compile(r"\b(because|due to|in protest|angry|anger|furious|outrage|boo\w*|jeer\w*|whistl\w* at|"
                          r"celebrat\w*|delight\w*|frustrat\w*)\b", re.I)


# ---------------------------------------------------------------- helpers
def _name(p: dict | None) -> str:
    return p["name"] if p else "a player"


def _team_ref(pack: dict, team_name: str, fav: str | None) -> str:
    if fav and pack["teams"].get(fav) == team_name:
        return f"your team, {team_name},"
    return team_name


def _score(pack: dict, s: dict | None = None) -> str:
    s = s or pack["score"]
    return f"{pack['teams']['home']} {s['home']}–{s['away']} {pack['teams']['away']}"


def _fact(pack: dict, ftype: str) -> dict | None:
    return next((f for f in pack["facts"] if f["type"] == ftype), None)


def _deep(pack: dict, ftype: str) -> dict | None:
    return next((f for f in pack.get("deep_context", []) if f["type"] == ftype), None)


def _ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _S(s: str, *ev: str) -> dict:
    return {"s": s[:1].upper() + s[1:], "evidence": [e for e in ev if e]}


# ---------------------------------------------------------------- templates
def template(pack: dict, depth: str = "basic", fav: str | None = None) -> list[dict]:
    kind = pack["moment"]
    fn = {"goal": _t_goal, "var_check": _t_var_check, "var_decision": _t_var_decision,
          "half_time": _t_period, "full_time": _t_period, "substitution": _t_sub, "injury": _t_injury}[kind]
    return fn(pack, depth, fav)[:max_sentences(pack)]


def max_sentences(pack: dict) -> int:
    """Half-time and full-time get a fuller report; every other moment stays short."""
    return 6 if pack.get("moment") in ("half_time", "full_time") else 3


def _t_goal(pack, depth, fav):
    g = _fact(pack, "goal")
    a = _fact(pack, "assist")
    team = g["team"]
    sit = pack["context"]["scoring_team_now"]
    side_word = {"leading": "ahead", "level": "level", "trailing": "back in it"}[sit]
    how = "from the penalty spot" if g["penalty"] else ("with a header" if g.get("body_part") == "head" else "")
    out = []
    if depth == "basic":
        # Kai has just announced the goal in the chat: Ada reacts to it instead of repeating it,
        # and leaves the crowd to Kai's closing line.
        if a:
            ball = "cross" if a.get("cross") else "through ball" if a.get("through_ball") else "pass"
            out.append(_S(f"Look at the {ball} from {_name(a['by'])}: that set it up for {_name(g['scorer'])}"
                          f"{' ' + how if how else ''}.", g["id"], a["id"]))
        elif g["penalty"]:
            out.append(_S(f"{_name(g['scorer'])} put it away from the spot.", g["id"]))
        elif how:
            out.append(_S(f"{_name(g['scorer'])} did it {how}.", g["id"]))
        out.append(_S(f"That puts {_team_ref(pack, team, fav)} {side_word}: {_score(pack)}, "
                      f"with {pack['minutes_left']} minutes left." if pack["minutes_left"] else
                      f"That puts {_team_ref(pack, team, fav)} {side_word}: {_score(pack)}.", g["id"], "state"))
        return out
    pos = POSITIONS.get(g["scorer"]["position"], "") if g.get("scorer") else ""
    xg = g.get("xg")
    quality = ("a big chance" if xg and xg >= 0.3 else "a half-chance" if xg and xg >= 0.1 else "a low-probability effort")
    s1 = f"{_name(g['scorer'])} ({pos}) finished {how or 'from inside the box' if g.get('in_box') else how or 'from outside the box'}"
    s1 = s1.replace("  ", " ")
    if xg is not None and not g["penalty"]:
        s1 += f", {quality} worth {xg} xG"
    if a:
        s1 += f", set up by {_name(a['by'])}"
    out.append(_S(s1 + ".", g["id"], a["id"] if a else None))
    st = _deep(pack, "match_stats")
    if st and st["home"]["xg"] is not None and st["away"]["xg"] is not None:
        tside = "home" if pack["teams"]["home"] == team else "away"
        oside = "away" if tside == "home" else "home"
        ts, os_ = st[tside], st[oside]
        verdict = "in line with the balance of play" if ts["xg"] >= os_["xg"] else "against the balance of play"
        out.append(_S(f"{team} have {ts['shots']} shots to {os_['shots']} and {ts['xg']} xG to {os_['xg']}, "
                      f"so this is {verdict}; it's {_score(pack)}.", "stat:match", g["id"]))
    z = _deep(pack, "attack_zones_last_15_min")
    if z and z["team"] == team:
        top = z["most_used"]
        out.append(_S(f"Over the last 15 minutes {z['counts'][top]} of their {z['total']} passes into the box "
                      f"came from the {top}{'' if top == 'centre' else ' flank'}.", "stat:zones"))
    return out


def _t_var_check(pack, depth, fav):
    chk = _fact(pack, "var_check")
    ch = _fact(pack, "challenge")
    goal = _fact(pack, "goal_under_review")
    out = []
    if chk["incident"] == "goal" and goal:
        if depth == "basic":
            out.append(_S(f"VAR is checking {_name(goal['scorer'])}'s goal for {goal['team']} before play restarts.",
                          chk["id"], goal["id"]))
            out.append(_S("This is a routine check: the goal stands unless the video shows a clear error, "
                          "like an offside or a foul in the build-up.", chk["id"]))
        else:
            out.append(_S(f"Routine VAR check on {_name(goal['scorer'])}'s goal; the on-field decision is goal.",
                          chk["id"], goal["id"]))
            out.append(_S("VAR looks for offside, a foul or handball in the attacking phase; without a clear and "
                          "obvious error the goal stands.", chk["id"]))
        out.append(_S(f"For now it's {_score(pack)}.", "state"))
        return out
    victim = _name(ch.get("on")) if ch else "an attacker"
    by = _name(ch.get("by")) if ch else "a defender"
    att_team = ch["on"]["team"] if ch and ch.get("on") else None
    if depth == "basic":
        out.append(_S(f"VAR is checking for a possible penalty: {victim} went down in the box after a challenge "
                      f"from {by}, and the referee let play go on.", chk["id"], ch["id"] if ch else None))
        if att_team:
            out.append(_S(f"If it's given, {_team_ref(pack, att_team, fav)} get a penalty with the score at "
                          f"{pack['score']['home']}–{pack['score']['away']}.", chk["id"], "state"))
        return out
    pos = POSITIONS.get(ch["by"]["position"], "") if ch and ch.get("by") else ""
    out.append(_S(f"Review of a possible foul by {by} ({pos}) on {victim} inside the box; the on-field decision "
                  f"was no penalty.", chk["id"], ch["id"] if ch else None))
    out.append(_S("VAR only intervenes for a clear and obvious error, so if the contact is clear the referee "
                  "will be sent to the monitor.", chk["id"]))
    mom = _deep(pack, "momentum_last_7_min")
    if mom and att_team:
        share = mom["home_share_pct"] if pack["teams"]["home"] == att_team else mom["away_share_pct"]
        out.append(_S(f"{att_team} had {share}% of the momentum over the last 7 minutes, the spell this came from.",
                      "stat:momentum"))
    return out


def _t_var_decision(pack, depth, fav):
    dec = _fact(pack, "var_decision")
    foul = _fact(pack, "foul_given")
    sif = pack["context"].get("score_if_scored")
    out = []
    if dec["result"] != "penalty" or not foul:
        out.append(_S(f"VAR has changed the decision on the {dec['result']}.", dec["id"]))
        out.append(_S(f"It's {_score(pack)}.", "state"))
        return out
    verb = VERB.get(foul["kind"], "fouled")
    pen_team = foul["penalty_to"]
    if depth == "basic":
        out.append(_S(f"The replay changed the call: {_name(foul['by'])} {verb} {_name(foul['on'])} inside the box.",
                      dec["id"], foul["id"]))
        if sif:
            out.append(_S(f"A goal would make it {pack['teams']['home']} {sif['home']}–{sif['away']} "
                          f"{pack['teams']['away']}, with {pack['minutes_left']} minutes left.", foul["id"], "state"))
        if sif:
            lead = sif["home"] - sif["away"] if pack["teams"]["home"] == pen_team else sif["away"] - sif["home"]
            chance = "take the lead" if lead > 0 else "draw level" if lead == 0 else "cut the gap"
            out.append(_S(f"It's a big chance for {_team_ref(pack, pen_team, fav)} to {chance}.", dec["id"], foul["id"]))
        return out
    out.append(_S(f"Overturned after an on-field review: {foul['kind']} by {_name(foul['by'])} on "
                  f"{_name(foul['on'])}, inside the box, so a penalty to {pen_team}.", dec["id"], foul["id"]))
    if sif:
        out.append(_S(f"Penalties are scored about three times in four; a goal makes it {sif['home']}–{sif['away']}.",
                      foul["id"], "state"))
    st = _deep(pack, "match_stats")
    if st:
        out.append(_S(f"Shots so far: {pack['teams']['home']} {st['home']['shots']}, {pack['teams']['away']} "
                      f"{st['away']['shots']}.", "stat:match"))
    return out


def _t_period(pack, depth, fav):
    """The break is the one long pause in a match, so this is a fuller report at both depths:
    score and goals, shots and accuracy, chance quality, possession, the best chance not taken,
    and who finished the half stronger. Every number is from the pack."""
    st = _fact(pack, "match_stats")
    goals = [f for f in pack["facts"] if f["type"] == "goal"]
    miss = _fact(pack, "best_missed_chance")
    mom = _deep(pack, "momentum_last_7_min")
    half = pack["moment"] == "half_time"
    h, a = pack["teams"]["home"], pack["teams"]["away"]
    hs, as_ = st["home"], st["away"]
    label = "Half-time" if half else "Full-time"
    if goals:
        parts = [f"{_name(g['scorer'])} ({_ordinal(g['minute'])}{', pen' if g['penalty'] else ''})" for g in goals]
        out = [_S(f"{label}: {_score(pack)}. Goals: " + ", ".join(parts) + ".", "state", *[g["id"] for g in goals])]
    else:
        out = [_S(f"{label}: {_score(pack)}, no goals {'yet' if half else 'in this one'}.", "state")]
    if hs["shots"] != as_["shots"]:
        more, mst, lst, less = (h, hs, as_, a) if hs["shots"] > as_["shots"] else (a, as_, hs, h)
        out.append(_S(f"{more} took more shots, {mst['shots']} to {lst['shots']}, with {mst['shots_on_target']} on "
                      f"target against {lst['shots_on_target']} for {less}.", "stat:match"))
    else:
        out.append(_S(f"Both sides had {hs['shots']} shots; {h} put {hs['shots_on_target']} on target, "
                      f"{a} {as_['shots_on_target']}.", "stat:match"))
    if hs["xg"] is not None and as_["xg"] is not None and hs["xg"] != as_["xg"]:
        better = h if hs["xg"] > as_["xg"] else a
        out.append(_S(f"{better} had the better chances: xG {hs['xg']} for {h}, {as_['xg']} for {a}.",
                      "stat:match"))
    if hs.get("possession") is not None and as_.get("possession") is not None:
        hp, ap = round(hs["possession"] * 100), round(as_["possession"] * 100)
        lead = "Possession was close" if abs(hp - ap) <= 10 else "Possession"
        out.append(_S(f"{lead}: {h} {hp}%, {a} {ap}%.", "stat:match"))
    ld = _fact(pack, "player_leaders")
    if ld:
        bits = [f"most {'shots' if k == 'shots' else 'key passes'}, {_name(v['player'])} of {v['team']} with {v['value']}"
                for k, v in ld.items() if k in ("shots", "key_passes")]
        out.append(_S("Top players: " + "; ".join(bits) + ".", "stat:leaders"))
    if miss:
        out.append(_S(f"Best chance not taken: {_name(miss['player'])} for {miss['team']} in the "
                      f"{_ordinal(miss['minute'])} minute ({miss['outcome'].replace('_', ' ')}).", miss["id"]))
    if half and mom and mom["home_share_pct"] != mom["away_share_pct"]:
        side, pct = (h, mom["home_share_pct"]) if mom["home_share_pct"] > mom["away_share_pct"] else (a, mom["away_share_pct"])
        out.append(_S(f"{side} finished the half stronger, with {pct}% of the momentum in the last 7 minutes.",
                      "stat:momentum"))
    return out


def _t_sub(pack, depth, fav):
    s = _fact(pack, "substitution")
    on, off = s["on"], s["off"]
    team = s["team"]
    sit = pack["context"]["team_situation"]
    out = [_S(f"{_team_ref(pack, team, fav)} bring on {_name(on)} for {_name(off)}.".replace(",,", ","), s["id"])]
    pon, poff = POSITIONS.get(on["position"], ""), POSITIONS.get(off["position"], "")
    if depth == "basic":
        if pon == poff:
            out.append(_S(f"It's a like-for-like change: a fresh {pon} for a tired one.", s["id"]))
        else:
            out.append(_S(f"A {pon} replaces a {poff}, so the shape may shift a little.", s["id"]))
        out.append(_S(f"They are {sit} with {pack['minutes_left']} minutes to go.", "state"))
        return out
    out.append(_S(f"{poff.capitalize()} off, {pon} on ({s['reason']}), with {team} {sit} "
                  f"and {pack['minutes_left']} minutes left.", s["id"], "state"))
    z = _deep(pack, "attack_zones_last_15_min")
    if z and z["team"] == team:
        top = z["most_used"]
        out.append(_S(f"{team}'s passes into the box in the last 15 minutes: {z['counts']['left']} from the left, "
                      f"{z['counts']['centre']} from the centre, {z['counts']['right']} from the right.",
                      "stat:zones"))
    return out


def _t_injury(pack, depth, fav):
    inj = _fact(pack, "injury")
    foul = _fact(pack, "foul_before")
    out = [_S(f"{_name(inj['player'])} of {inj['team']} is down injured, so play has stopped.", inj["id"])]
    if foul:
        out.append(_S(f"It came straight after a {foul['kind']} by {_name(foul['by'])}.", foul["id"]))
    out.append(_S(f"It's {_score(pack)} while the medical staff work.", "state"))
    return out


# ---------------------------------------------------------------- validator
def _pack_numbers(obj, acc: set[str]):
    if isinstance(obj, dict):
        for v in obj.values():
            _pack_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _pack_numbers(v, acc)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        acc.add(_num(obj))
        if isinstance(obj, float) and obj <= 1:
            acc.add(_num(round(obj * 100)))  # shares quoted as percentages
    elif isinstance(obj, str):
        for n in re.findall(r"\d+(?:\.\d+)?", obj):
            acc.add(_num(float(n)))


def _num(x) -> str:
    f = float(x)
    return str(int(f)) if f == int(f) else str(round(f, 2))


def _pack_strings(obj, acc: list[str]):
    if isinstance(obj, dict):
        for v in obj.values():
            _pack_strings(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _pack_strings(v, acc)
    elif isinstance(obj, str):
        acc.append(obj.lower())


def validate(sentences: list[dict], pack: dict, roster_names: set[str]) -> list[str]:
    """Return a list of problems; empty means the text may be shown."""
    problems = []
    if not 1 <= len(sentences) <= max_sentences(pack):
        problems.append(f"expected 1-{max_sentences(pack)} sentences, got {len(sentences)}")
    ids = {f["id"] for f in pack["facts"]} | {f["id"] for f in pack.get("deep_context", [])} | {"state"}
    nums: set[str] = set()
    _pack_numbers(pack, nums)
    strings: list[str] = []
    _pack_strings(pack, strings)
    blob = " ".join(strings)
    for i, s in enumerate(sentences):
        text = s.get("s", "")
        ev = s.get("evidence") or []
        if not ev:
            problems.append(f"sentence {i + 1} has no evidence")
        bad = [e for e in ev if e not in ids]
        if bad:
            problems.append(f"sentence {i + 1} cites unknown evidence {bad}")
        for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text):
            if _num(float(n)) not in nums:
                problems.append(f"sentence {i + 1} uses number {n} not in the fact pack")
        for name in roster_names:
            if re.search(rf"\b{re.escape(name)}\b", text) and name.lower() not in blob:
                problems.append(f"sentence {i + 1} names {name}, who is not in the fact pack")
        if re.search(r"\b(crowd|stadium|fans|supporters)\b", text, re.I) and CROWD_CAUSAL.search(text):
            problems.append(f"sentence {i + 1} claims why the crowd reacted")
    return problems


# ---------------------------------------------------------------- writer
async def agent_draft(agent, pack: dict, depth: str, fav: str | None) -> tuple[list[dict], str]:
    """Ask the Foundry Explainer agent for a draft. The validator decides if it is used."""
    style = "B_friend" if depth == "basic" else "C_analyst"
    if pack.get("peak"):
        style += "+A_touch"
    slim = dict(pack)
    if depth == "basic":
        slim.pop("deep_context", None)
    msg = json.dumps({"style": style, "favourite_team": pack["teams"].get(fav) if fav else None,
                      "fact_pack": slim}, ensure_ascii=False)
    resp = await agent.run(msg)
    text = resp.text.strip()
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return data["sentences"], getattr(agent, "model_name", "foundry")


class Explainer:
    """Runs the stoppage-analysis workflow (writer -> validator -> fallback)."""

    def __init__(self, llm=None, roster_names: set[str] | None = None):
        self.llm = llm  # an agent_framework Agent, or None for templates only
        self.roster = roster_names or set()

    async def write(self, pack: dict, depth: str = "basic", fav: str | None = None) -> dict:
        from .workflow import AnalysisJob, _result, build_analysis_workflow

        wf = build_analysis_workflow(self.llm, self.roster)
        job = AnalysisJob(pack, depth, fav)
        try:
            async with timeout(TOTAL_TIMEOUT_S):
                result = await wf.run(job)
        except TimeoutError:
            # Bound the entire workflow, not only the provider's HTTP call.
            # Cancellation from seek/reset still propagates to the room owner.
            sentences = template(pack, depth, fav)
            fallback = _result(job, sentences, "template", None, validate(sentences, pack, self.roster))
            fallback["rejected"] = ["analysis timeout"]
            return fallback
        return result.get_outputs()[-1]
