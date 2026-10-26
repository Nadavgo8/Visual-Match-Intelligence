"""The "Ask" chat: one commentator voice over several agents.

With Foundry configured, these are Agent Framework agents. The router calls the specialists as
tools (agent-as-tool handoff) and then writes the final answer in the commentator's voice:
- match analyst: the facts, through the read-only engine tools;
- rules expert: the Laws of the Game, linked to this match;
- meaning analyst: what the match analyst's facts suggest, always labelled as interpretation.
Code then checks the evidence, numbers and labels. Without Foundry, the same roles run as
deterministic code over the same tools, so the chat always works.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import os
import re
import time
from pathlib import Path

from ..engine import derive
from ..engine.model import MatchModel
from . import rules
from .providers import TOTAL_TIMEOUT_S
from .tools import MatchTools

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
MAX_TOOL_CALLS = 6
# gpt-5-mini reasons before answering; low effort keeps the agent chain inside the 20 s limit.
AGENT_OPTIONS = {"reasoning": {"effort": os.getenv("VMI_REASONING_EFFORT", "low")}}

FOOTBALL_WORDS = re.compile(
    r"\b(match|game|score|goal|shot|pass|foul|card|var|offside|penalty|referee|ref|whistle|half|minute|team|"
    r"player|keeper|striker|defen\w*|attack\w*|win|winning|lose|losing|lead|draw|stats?|xg|possession|corner|"
    r"momentum|tactic\w*|formation|crowd|fans?|atmosphere|sub\w*|injur\w*|happen\w*|miss\w*|why|rule|ball|"
    r"press\w*|chance|save|kick|free|throw|book\w*|sent|red|yellow|added|time|left|who)\b", re.I)


# Questions about meaning go to the meaning analyst with facts gathered in code.
MEANING_Q = re.compile(r"\b(on top|dominat\w*|who'?s (better|winning the battle)|in control|pressure|"
                       r"what (changed|does (it|that|this) mean)|why does (it|that|this) matter|"
                       r"how (are|is) .{1,30} (doing|playing)|momentum)\b", re.I)


# Two voices in one chat. Kai, the commentator, says what happened; Ada, the analyst, says what
# it means, and also answers rules questions. The choice is made in code from the question and
# the agent that answered, so a fan never has to pick who to ask.
ANALYST_AGENTS = {"meaning_analyst", "rules_expert", "both"}
ANALYST_Q = re.compile(r"\b(why|how come|dominat\w*|on top|better|in control|pressure|tactic\w*|formation|"
                       r"momentum|chang\w*|mean\w*|matter\w*|turning point|influential|dangerous|expect\w*|"
                       r"predict\w*|think|maintain|rules?|laws?|allowed|offside|handball|explain)\b", re.I)


def speaker_for(question: str, agent: str | None) -> str:
    """'analyst' for interpretation and rules, 'commentator' for what happened."""
    if agent in ANALYST_AGENTS or MEANING_Q.search(question) or ANALYST_Q.search(question):
        return "analyst"
    return "commentator"


class _Recorder:
    """Wraps tools so we know which ones ran and which evidence IDs they returned."""

    def __init__(self, tools: MatchTools):
        self.calls: list[str] = []
        self.evidence: set[str] = set()
        self.outputs: list[dict] = []
        self.tools = [self._wrap(f) for f in tools.all()]

    def _wrap(self, fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if len(self.calls) >= MAX_TOOL_CALLS:
                return {"error": "tool budget reached; answer with what you have"}
            self.calls.append(fn.__name__)
            out = fn(*args, **kwargs)
            self.outputs.append(out)
            self.evidence.update(e for e in out.get("evidence", []) if e)
            return out
        return inner


class Assistant:
    def __init__(self, model: MatchModel, client=None, model_name: str | None = None):
        self.m = model
        self.tools = MatchTools(model)
        self.client = client
        self.model_name = model_name

    async def answer(self, question: str, profile: dict | None = None) -> dict:
        """Answer against a copy of the match frozen when the question was asked: events that
        arrive while an agent is still working can't leak into this answer."""
        profile = profile or {}
        t0 = time.perf_counter()
        frozen = type(self)(copy.deepcopy(self.m), self.client, self.model_name)
        fallback_reason = None
        if self.client is not None:
            try:
                path = frozen._meaning if MEANING_Q.search(question) else frozen._agents
                res = await asyncio.wait_for(path(question, profile), timeout=TOTAL_TIMEOUT_S)
                if res:
                    return self._finish(res, frozen, t0, question)
                fallback_reason = "agent answer failed validation"
            except asyncio.TimeoutError:
                fallback_reason = "timeout"
            except Exception as e:  # fall back to the local agents
                fallback_reason = f"agent error: {type(e).__name__}"
        res = frozen._local(question, profile)
        if fallback_reason:
            res["fallback_reason"] = fallback_reason
        return self._finish(res, frozen, t0, question)

    @staticmethod
    def _finish(res: dict, frozen: "Assistant", t0: float, question: str = "") -> dict:
        res["speaker"] = speaker_for(question, res.get("agent"))
        res["latency_ms"] = round((time.perf_counter() - t0) * 1000)
        res["answer_kind"] = "live" if res.get("source") == "agent" else "template"  # never present code as AI
        res["snapshot_clock"] = frozen.m.clock
        return res

    # ------------------------------------------------------------ Foundry agents
    def meaning_facts(self) -> dict:
        """The data tools' facts for a 'what does it mean' question, gathered in code (no model call)."""
        m = self.m
        facts = {"score_and_clock": self.tools.get_score_and_clock(), "momentum": self.tools.get_momentum(),
                 "last_15_minutes": self.tools.get_team_stats(15),
                 "attack_patterns": [self.tools.get_attack_pattern(side, 15) for side in ("home", "away")],
                 "recent_events": self.tools.get_events(max(0, derive.minute_of(m.clock) - 15), 130)}
        facts["evidence"] = sorted({e for f in facts.values() for e in
                                    (f.get("evidence", []) if isinstance(f, dict) else
                                     [x for g in f for x in g.get("evidence", [])])})
        return facts

    async def _meaning(self, question: str, profile: dict) -> dict | None:
        """Data tools (code) -> meaning analyst (one model call) -> code checks. One hop, so an
        interpretation fits the 20 s limit; the router's longer chain didn't."""
        from agent_framework import Agent

        facts = self.meaning_facts()
        agent = Agent(self.client, (PROMPTS / "meaning_analyst.md").read_text(), default_options=AGENT_OPTIONS, name="meaning_analyst")
        msg = json.dumps({"question": question, "depth": profile.get("depth", "basic"), "facts": facts},
                         ensure_ascii=False)
        resp = await agent.run(msg)
        text = resp.text.strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        answer, cited = data.get("answer", "").strip(), data.get("evidence", [])
        if check_agent_answer(answer, cited, "meaning_analyst", set(facts["evidence"]), [facts]):
            return None
        return {"text": answer, "evidence": [e for e in cited if e in facts["evidence"]],
                "agent": "meaning_analyst", "source": "agent", "model": self.model_name,
                "tool_calls": ["get_score_and_clock", "get_momentum", "get_team_stats", "get_attack_pattern",
                               "get_events"], "validation": "passed"}

    async def _agents(self, question: str, profile: dict) -> dict | None:
        from agent_framework import Agent

        rec = _Recorder(self.tools)
        depth = profile.get("depth", "basic")
        fav = profile.get("team")
        ctx = (f"Fan profile: depth={depth}, favourite team="
               f"{self.m.team_name(fav) if fav in ('home', 'away') else 'neutral'}. "
               f"Live: {self.m.team_name('home')} {self.m.score['home']}–{self.m.score['away']} "
               f"{self.m.team_name('away')}, clock {self.m.clock}.")
        analyst = Agent(self.client, (PROMPTS / "match_analyst.md").read_text(), default_options=AGENT_OPTIONS, name="match_analyst",
                        description="Answers questions about this match: events, stats, players, momentum, tactics.",
                        tools=rec.tools)
        rules_agent = Agent(self.client, (PROMPTS / "rules_expert.md").read_text(), default_options=AGENT_OPTIONS, name="rules_expert",
                            description="Explains the Laws of the Game and this app's indicators, linked to this match.",
                            tools=[t for t in rec.tools if t.__name__ in ("get_rule", "get_events")])
        # The meaning analyst gathers nothing itself: it reasons only over the facts the router passes
        # on from the match analyst, so its view can't bring in new numbers or events.
        meaning = Agent(self.client, (PROMPTS / "meaning_analyst.md").read_text(), default_options=AGENT_OPTIONS, name="meaning_analyst",
                        description="Explains what the match analyst's facts suggest, labelled as interpretation.",
                        tools=[])
        router = Agent(self.client, (PROMPTS / "router.md").read_text(), default_options=AGENT_OPTIONS, name="router",
                       tools=[analyst.as_tool(name="ask_match_analyst"), rules_agent.as_tool(name="ask_rules_expert"),
                              meaning.as_tool(name="ask_meaning_analyst")])
        resp = await router.run(f"{ctx}\n\nQuestion: {question}")
        text = resp.text.strip()
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        answer, cited = data.get("answer", "").strip(), data.get("evidence", [])
        if data.get("declined"):
            return {"text": answer, "evidence": [], "agent": "router", "source": "agent",
                    "model": self.model_name, "tool_calls": rec.calls, "validation": "passed"}
        if check_agent_answer(answer, cited, data.get("agent"), rec.evidence, rec.outputs):
            return None
        return {"text": answer, "evidence": [e for e in cited if e in rec.evidence],
                "agent": data.get("agent", "router"), "source": "agent", "model": self.model_name,
                "tool_calls": rec.calls, "validation": "passed"}

    # ------------------------------------------------------------ local agents
    def _local(self, q: str, profile: dict) -> dict:
        ql = q.lower()
        t = self.tools
        m = self.m
        deep = profile.get("depth") == "deep"
        names = {p["name"].lower() for p in m.players.values()}
        named = [n for n in names if re.search(rf"\b{n}\b", ql)]
        team_named = any(m.team_name(s).lower().split()[0] in ql for s in ("home", "away"))
        if not FOOTBALL_WORDS.search(ql) and not named and not team_named:
            return self._out("I can only help with this match: what happened, the rules, stats and tactics. "
                             "Try “why was that offside?” or “what did I miss?”", [], "router", [])

        rule = rules.lookup(ql)
        asks_rule = re.search(r"\b(what is|what's an?|what does|how does|rule|explain|mean|why (was|is|did)|allowed|can a)\b", ql)
        # Rules expert
        if rule["found"] and asks_rule and not re.search(r"\b(score|stats?|possession)\b", ql):
            text = rule["text"]
            ev = list(rule["evidence"])
            calls = ["get_rule"]
            link = self._latest_for_rule(rule["topic"])
            if link and (re.search(r"\b(that|this|the last|just|did|was)\b", ql)):
                text = f"In this match: {link['what']} ({link['clock']}). " + text
                ev.append(link["id"])
                calls.append("get_events")
            if not deep:
                text = _first_sentences(text, 2)
            return self._out(text, ev, "rules_expert", calls)

        # Match analyst
        mins = re.search(r"\b(?:minute|min)\s*(\d{1,3})\b|\b(\d{1,3})(?:st|nd|rd|th)?\s*(?:minute|min)\b", ql)
        if named or re.search(r"#\d+", ql):
            key = named[0] if named else re.search(r"#\d+", ql).group()
            r = t.get_player(key + " " + ql)
            if "error" in r:
                return self._out(f"I couldn't find {key} in either squad.", [], "match_analyst", ["get_player"])
            p = r["players"][0]
            bits = [f"{p['name']} (#{p['number']}) plays {p['position']} for {p['team']}"
                    + ("" if p["on_pitch"] else " and is no longer on the pitch") + "."]
            bits.append(f"{p['passes_completed']} of {p['passes']} passes completed"
                        + (f", {p['key_passes']} key pass{'es' if p['key_passes'] != 1 else ''}" if p["key_passes"] else "") + ".")
            if p["shots"]:
                bits.append(f"{p['shots']} shot{'s' if p['shots'] != 1 else ''}, {p['shots_on_target']} on target, "
                            f"{p['goals']} goal{'s' if p['goals'] != 1 else ''}"
                            + (f" (synthetic xG {p['xg']})." if deep and p["xg"] is not None
                               else " (xG not yet available)." if deep else "."))
            if p["other"]:
                bits.append("Also: " + "; ".join(p["other"][-3:]) + ".")
            return self._out(" ".join(bits), r["evidence"], "match_analyst", ["get_player"])
        if re.search(r"\b(score|winning|who.?s (winning|ahead)|time left|how long|minutes left)\b", ql):
            s = t.get_score_and_clock()
            text = (f"{s['home']} {s['score']['home']}–{s['score']['away']} {s['away']}, {s['clock']} on the clock"
                    + (f", about {s['minutes_left']} minutes of normal time left." if s["minutes_left"] else "."))
            return self._out(text, s["evidence"], "match_analyst", ["get_score_and_clock"])
        if re.search(r"\b(crowd|loud|noise|atmosphere|fans)\b", ql):
            r = t.get_crowd_peaks()
            if not r["available"] and not r["peaks"]:
                return self._out("Crowd data is unavailable; I cannot tell how loud the stadium is.", [], "match_analyst", ["get_crowd_peaks"])
            if not r["peaks"]:
                return self._out("The crowd hasn't hit a big peak in the last ten minutes.", [], "match_analyst",
                                 ["get_crowd_peaks"])
            p = r["peaks"][0]
            text = (f"The loudest moment recently came right after this: {p['just_after']}." if p["just_after"]
                    else "The crowd peaked recently without a logged event just before it.")
            text += " The sensor measures loudness only, so I can't tell you whether it was cheers or boos."
            return self._out(text, r["evidence"], "match_analyst", ["get_crowd_peaks"])
        if re.search(r"\b(momentum|on top|dominat\w*|pressure|tactic\w*|pattern|better|attack\w*|flank|wing)\b", ql):
            mo = t.get_momentum()
            share = round(mo["home_index"] * 100)
            lead = mo["home_team"] if share >= 55 else mo["away_team"] if share <= 45 else None
            possession = (f"{round(mo['possession_home'] * 100)}% possession for {mo['home_team']}"
                          if mo["possession_available"] else "possession data unavailable")
            text = (f"Interpretation: over the last 7 minutes {'it has been even' if not lead else lead + ' have been on top'}. "
                    f"Facts: {possession}, key passes "
                    f"{mo['key_passes']['home']}–{mo['key_passes']['away']}, shots {mo['shots']['home']}–{mo['shots']['away']}.")
            ev, calls = list(mo["evidence"]), ["get_momentum"]
            if deep or re.search(r"\b(tactic\w*|pattern|flank|wing|attack\w*)\b", ql):
                for side in ("home", "away"):
                    z = t.get_attack_pattern(side, 15)
                    tot = sum(z["counts"].values())
                    if tot >= 3:
                        top = max(z["counts"], key=z["counts"].get)
                        text += f" {z['team']} played {z['counts'][top]} of {tot} passes into the box from the {top} in the last 15 minutes."
                        ev += z["evidence"]
                calls.append("get_attack_pattern")
            return self._out(text, ev, "match_analyst", calls)
        if re.search(r"\b(stats?|shots?|possession|xg|corners?|fouls?|cards?|passes|offsides?)\b", ql) and not mins:
            st = t.get_team_stats()
            h, a = m.team_name("home"), m.team_name("away")
            hs, as_ = st[h], st[a]
            text = f"Shots {hs['shots']}–{as_['shots']} ({hs['shots_on_target']}–{as_['shots_on_target']} on target)"
            if hs.get("possession") is not None:
                text += f", possession {round(hs['possession'] * 100)}%–{round(as_['possession'] * 100)}%"
            text += f", corners {hs['corners']}–{as_['corners']}, fouls {hs['fouls']}–{as_['fouls']}"
            text += f", yellow cards {hs['yellow_cards']}–{as_['yellow_cards']}"
            if deep or "xg" in ql:
                text += (f", synthetic xG {hs['xg']}–{as_['xg']}"
                         if hs["xg"] is not None and as_["xg"] is not None else ", xG not yet available")
            text += f" ({h} first)."
            return self._out(text, st["evidence"], "match_analyst", ["get_team_stats"])
        # recap / what happened
        now_min = derive.minute_of(m.clock)
        if mins:
            mm = int(mins.group(1) or mins.group(2))
            r = t.get_events(mm - 1, mm + 1)
        elif re.search(r"\b(half|first half)\b", ql) and m.period == 2:
            r = t.get_events(0, 45)
        else:
            span = 10 if re.search(r"\b(missed|just|last|recent|now)\b", ql) else now_min + 1
            r = t.get_events(max(0, now_min - span), now_min + 1)
        evs = [e for e in r["events"] if not e["what"].startswith(("kick-off", "second half"))]
        if not evs:
            return self._out("Nothing major in that spell: no goals, cards, VAR checks or big chances.",
                             [], "match_analyst", ["get_events"])
        lines = [f"{e['clock']} {e['what']}" for e in evs[-6:]]
        return self._out("Here's what happened: " + "; ".join(lines) + ".", [e["id"] for e in evs[-6:]],
                         "match_analyst", ["get_events"])

    def _latest_for_rule(self, topic: str) -> dict | None:
        types = {"offside": "offside", "penalty": "foul", "var": "var", "yellow_card": "card", "red_card": "card",
                 "foul": "foul", "advantage": "foul", "substitution": "substitution"}.get(topic)
        if not types:
            return None
        r = self.tools.get_events(0, 130, types)
        evs = [e for e in r["events"] if topic != "penalty" or "penalty" in e["what"]]
        if not evs or derive.minute_of(self.m.clock) - evs[-1]["minute"] > 15:
            return None
        return evs[-1]

    def _out(self, text, evidence, agent, calls) -> dict:
        return {"text": text, "evidence": evidence, "agent": agent, "source": "local", "model": None,
                "tool_calls": calls, "validation": "passed"}


def _norm_number(n: str) -> str:
    return n.rstrip("0").rstrip(".") if "." in n else n


def check_agent_answer(answer: str, cited: list, agent: str | None, evidence: set[str],
                       outputs: list[dict]) -> list[str]:
    """Problems with the agents' final answer; empty means it may be shown.

    Cited ids must come from tool results, numbers must appear in tool results, and an answer that
    used the meaning analyst must keep its view marked as interpretation."""
    problems = [] if answer else ["empty answer"]
    problems += [f"unknown evidence {e}" for e in cited if e not in evidence]
    allowed = {_norm_number(n) for o in outputs for n in re.findall(r"\d+(?:\.\d+)?", json.dumps(o))}
    for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", answer):
        if _norm_number(n) not in allowed and _norm_number(n) not in {"1", "2", "3", "7", "11", "40", "30"}:
            problems.append(f"number {n} not in tool results")
    if agent in ("meaning_analyst", "several") and "interpretation" not in answer.lower():
        problems.append("interpretation is not labelled")
    return problems


def _first_sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:n])
