"""Startup warm-up of the Foundry answer paths (no network: the model is faked)."""

import asyncio

from vmi.agents.qa import MEANING_Q
from vmi.api import server


class _FakeAssistant:
    def __init__(self, asked):
        self.asked = asked

    async def answer(self, question, profile=None):
        self.asked.append(question)
        return {"source": "agent"}


def _fake_room(asked, made):
    class Room:
        def __init__(self, name, seed, *, match=None):
            made.append((name, seed, match))
            self.assistant = _FakeAssistant(asked)

    return Room


def test_warm_up_asks_once_per_answer_path(monkeypatch):
    asked, made, source = [], [], object()

    async def prepare(seed):
        return source

    monkeypatch.setattr(server, "_client", object())
    monkeypatch.setattr(server, "prepare_match", prepare)
    monkeypatch.setattr(server, "Room", _fake_room(asked, made))
    assert asyncio.run(server.warm_foundry(7)) == ["agent", "agent"]
    assert asked == list(server.WARM_QUESTIONS)
    # One question takes the meaning analyst, the other the routed agents.
    assert [bool(MEANING_Q.search(q)) for q in asked] == [False, True]
    # A private room: never registered where viewers could join it.
    assert made == [("_warm_ai", 7, source)] and "_warm_ai" not in server.rooms


def test_warm_up_does_nothing_offline(monkeypatch):
    monkeypatch.setattr(server, "_client", None)

    async def prepare(seed):
        raise AssertionError("offline warm-up must not load a match")

    monkeypatch.setattr(server, "prepare_match", prepare)
    assert asyncio.run(server.warm_foundry()) == []


def test_lifespan_starts_the_warm_up_with_foundry_and_cancels_it_on_shutdown(monkeypatch):
    started, cancelled = asyncio.Event(), []

    async def warm():
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    monkeypatch.setattr(server, "_client", object())
    monkeypatch.setattr(server, "warm_foundry", warm)
    monkeypatch.setenv("VMI_WARM_DEMO", "0")
    monkeypatch.delenv("VMI_WARM_FOUNDRY", raising=False)

    async def run():
        async with server.lifespan(server.app):
            await asyncio.wait_for(started.wait(), 1)

    asyncio.run(run())
    assert cancelled == [True]


def test_lifespan_skips_the_warm_up_when_disabled(monkeypatch):
    monkeypatch.setattr(server, "_client", object())

    async def warm():
        raise AssertionError("warm-up disabled")

    monkeypatch.setattr(server, "warm_foundry", warm)
    monkeypatch.setenv("VMI_WARM_DEMO", "0")
    monkeypatch.setenv("VMI_WARM_FOUNDRY", "0")

    async def run():
        async with server.lifespan(server.app):
            await asyncio.sleep(0)

    asyncio.run(run())
