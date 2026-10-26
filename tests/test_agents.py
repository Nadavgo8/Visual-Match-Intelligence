"""Explainer receipts, validator, workflow fallback, and the Ask chat."""

import asyncio

import pytest

from vmi.agents.explainer import Explainer, template, validate
from vmi.agents.qa import Assistant
from vmi.engine.replay import Replay, run_all
from vmi.evaluation.benchmark import benchmark_match
from vmi.generator.match import generate_match


def _roster(m):
    return {p["name"] for t in m.meta["teams"].values() for p in t["players"]}


@pytest.mark.parametrize("seed", [3, 9, 12, 17])
def test_templates_always_pass_the_validator(seed):
    m = generate_match(seed)
    for o in run_all(m):
        if o["kind"] != "analysis":
            continue
        for depth in ("basic", "deep"):
            for fav in (None, "home", "away"):
                sents = template(o["factpack"], depth, fav)
                assert 1 <= len(sents) <= 3
                assert validate(sents, o["factpack"], _roster(m)) == []


@pytest.fixture(scope="module")
def goal_pack():
    # These validator/workflow assertions name the annotated first scorer.
    # Keep their independent facts fixed when the live demo generator evolves.
    m = benchmark_match()
    replay = Replay(m)
    pack = next(o["factpack"] for o in replay.advance(1200)
                if o["kind"] == "analysis" and o["moment"] == "goal")
    return m, pack


def test_validator_rejects_invented_facts(goal_pack):
    m, pack = goal_pack
    gid = pack["facts"][0]["id"]
    r = _roster(m)
    assert validate([{"s": "It came in the 99th minute.", "evidence": [gid]}], pack, r)
    assert validate([{"s": "Reyes scored.", "evidence": ["evt_9999"]}], pack, r)
    assert validate([{"s": "Reyes scored.", "evidence": []}], pack, r)
    assert validate([{"s": "Varga made a mistake.", "evidence": [gid]}], pack, r)
    assert validate([{"s": "The crowd roared because they love Reyes.", "evidence": [gid]}], pack, r)


class _Agent:
    model_name = "test"

    def __init__(self, text):
        self.text = text

    async def run(self, msg):
        class R:
            pass
        r = R()
        r.text = self.text
        return r


def test_workflow_uses_a_valid_agent_draft(goal_pack):
    m, pack = goal_pack
    gid = pack["facts"][0]["id"]
    agent = _Agent('{"sentences":[{"s":"Reyes scored to make it 1–0.","evidence":["%s","state"]}]}' % gid)
    res = asyncio.run(Explainer(agent, _roster(m)).write(pack))
    assert res["source"] == "agent" and res["validation"] == "passed"


def test_workflow_falls_back_when_the_agent_invents(goal_pack):
    m, pack = goal_pack
    agent = _Agent('{"sentences":[{"s":"Reyes scored his 37th of the season.","evidence":["state"]}]}')
    res = asyncio.run(Explainer(agent, _roster(m)).write(pack))
    assert res["source"] == "template" and res["rejected"] and res["validation"] == "passed"


def test_workflow_falls_back_on_agent_error(goal_pack):
    m, pack = goal_pack
    res = asyncio.run(Explainer(_Agent("not json"), _roster(m)).write(pack))
    assert res["source"] == "template" and res["validation"] == "passed"


@pytest.fixture(scope="module")
def assistant():
    m = generate_match(12)
    r = Replay(m)
    r.advance(2700)
    return Assistant(r.model)


@pytest.mark.parametrize("q,agent", [
    ("why was that offside?", "rules_expert"),
    ("what did I miss?", "match_analyst"),
    ("what's the score?", "match_analyst"),
    ("who is on top?", "match_analyst"),
    ("tell me about Dumont", "match_analyst"),
    ("what's the weather in Paris?", "router"),
])
def test_ask_routes_questions(assistant, q, agent):
    res = asyncio.run(assistant.answer(q, {"depth": "basic"}))
    assert res["agent"] == agent and res["text"]
    if agent != "router":
        assert res["evidence"]
