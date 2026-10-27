"""Pre-built random matches: new rooms and "Random match" never wait for a cold source."""

import asyncio
import json

from vmi.api import server


def _fake_sources(monkeypatch, built):
    def generate(seed):
        built.append(seed)
        return {"seed": seed}

    monkeypatch.setattr(server, "_match_cache", {})
    monkeypatch.setattr(server, "_pool", [])
    monkeypatch.setattr(server, "generate_match", generate)
    monkeypatch.setattr(server, "generate_demo_match", generate)


def test_prebuild_builds_the_demo_then_distinct_random_matches(monkeypatch):
    built = []
    _fake_sources(monkeypatch, built)
    pool = asyncio.run(server.prebuild_matches(4))
    assert built[0] == server.DEMO_SEED and len(pool) == 4 == len(set(pool))
    assert server.DEMO_SEED not in pool and all(1 <= s <= server.MAX_SEED for s in pool)
    assert all(s in server._match_cache for s in [server.DEMO_SEED, *pool])
    # The pool leaves cache room for requested seeds.
    assert len(asyncio.run(server.prebuild_matches(50))) == server.MATCH_CACHE_MAX - 2


def test_new_rooms_and_random_pick_a_built_match_other_than_the_current_one(monkeypatch):
    built = []
    _fake_sources(monkeypatch, built)
    monkeypatch.setenv("VMI_DEMO", "0")
    pool = asyncio.run(server.prebuild_matches(3))
    assert all(server.new_room_seed(None) in pool for _ in range(30))
    assert server.new_room_seed(41) == 41  # an explicit seed still wins
    for current in pool:
        assert all(server.ready_seed(exclude=current) in set(pool) - {current} for _ in range(30))
    monkeypatch.setenv("VMI_DEMO", "1")
    assert server.new_room_seed(None) == server.DEMO_SEED


def test_without_a_pool_a_fresh_random_seed_is_used(monkeypatch):
    _fake_sources(monkeypatch, [])
    assert 1 <= server.ready_seed() <= server.MAX_SEED


def test_eviction_keeps_the_demo_and_pre_built_matches(monkeypatch):
    built = []
    _fake_sources(monkeypatch, built)
    pool = asyncio.run(server.prebuild_matches(3))
    for seed in range(10_000, 10_010):  # viewers asking for other seeds
        server.get_match(seed)
    assert len(server._match_cache) == server.MATCH_CACHE_MAX
    assert all(s in server._match_cache for s in [server.DEMO_SEED, *pool])
    assert 10_009 in server._match_cache and 10_000 not in server._match_cache


def test_random_command_loads_a_built_match_for_the_room(monkeypatch):
    asked = []

    class FakeRoom:
        seed = 5

        async def new_match(self, seed):
            asked.append(seed)

    monkeypatch.setattr(server, "ready_seed", lambda exclude=None: 900 + exclude)
    asyncio.run(server.control(FakeRoom(), "new_match", {"cmd": "new_match", "random": True}))
    assert asked == [905]
    asyncio.run(server.control(FakeRoom(), "new_match", json.loads('{"cmd": "new_match", "seed": 7}')))
    assert asked == [905, 7]


def test_lifespan_prebuilds_unless_disabled(monkeypatch):
    calls = []

    async def prebuild():
        calls.append(1)

    monkeypatch.setattr(server, "prebuild_matches", prebuild)
    monkeypatch.setattr(server, "_client", None)
    monkeypatch.setenv("VMI_WARM_DEMO", "0")

    async def run():
        async with server.lifespan(server.app):
            await asyncio.sleep(0)

    monkeypatch.setenv("VMI_PREBUILD", "1")
    asyncio.run(run())
    monkeypatch.setenv("VMI_PREBUILD", "0")
    asyncio.run(run())
    assert calls == [1]
