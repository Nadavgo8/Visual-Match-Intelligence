"""Explainer receipts, validator, workflow fallback, and the Ask chat."""

import asyncio

import pytest

from vmi.agents.explainer import Explainer, max_sentences, template, validate
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
                assert 1 <= len(sents) <= max_sentences(o["factpack"])
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


def test_stoppage_analysis_deadline_cancels_a_hung_model_and_uses_validated_template(goal_pack, monkeypatch):
    from vmi.agents import explainer

    calls, cancelled, deadlines = [], [], []

    def controlled_deadline(seconds):
        assert seconds == 20
        deadline = asyncio.timeout(None)
        deadlines.append(deadline)
        return deadline

    # Arm the real asyncio cancellation exactly when the fake model starts;
    # workflow startup speed cannot make this timeout regression flaky.
    monkeypatch.setattr(explainer, "timeout", controlled_deadline, raising=False)

    class HungAgent:
        async def run(self, message):
            calls.append(message)
            try:
                deadlines[0].reschedule(asyncio.get_running_loop().time())
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

    m, pack = goal_pack

    async def scenario():
        # The outer deadline only bounds a regression to the old unbounded path.
        return await asyncio.wait_for(Explainer(HungAgent(), _roster(m)).write(pack), 2)

    res = asyncio.run(scenario())
    assert len(calls) == 1 and cancelled == [True]
    assert res["source"] == "template" and res["model"] is None
    assert res["validation"] == "passed" and res["rejected"] == ["analysis timeout"]
    assert res["moment"] == pack["moment"]


def test_cancelled_analysis_does_not_turn_an_old_run_into_a_fallback(goal_pack):
    started, cancelled = [], []

    async def scenario():
        gate = asyncio.Event()

        class HungAgent:
            async def run(self, message):
                started.append(True)
                gate.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.append(True)

        m, pack = goal_pack
        task = asyncio.create_task(Explainer(HungAgent(), _roster(m)).write(pack))
        await asyncio.wait_for(gate.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert started == [True] and cancelled == [True]


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
