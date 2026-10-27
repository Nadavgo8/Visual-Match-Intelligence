"""Cold source preparation must not freeze connected match rooms."""

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vmi.api import server
from vmi.evaluation.benchmark import benchmark_match

GET_MATCH = server.get_match


@pytest.fixture
def source(monkeypatch):
    match = benchmark_match()
    monkeypatch.setattr(server, "_match_cache", {})
    monkeypatch.setattr(server, "get_match", lambda seed: match)
    return match


def test_switching_to_a_cold_match_leaves_the_event_loop_responsive(source, monkeypatch):
    async def scenario():
        room = server.Room("loading", 12)
        loop = asyncio.get_running_loop()
        release, calls = threading.Event(), []

        def cold(seed):
            calls.append(seed)
            # The source worker requires an event-loop callback to proceed.
            # This deadline only bounds a regression to synchronous generation.
            loop.call_soon_threadsafe(release.set)
            assert release.wait(1), "cold generation blocked the shared event loop"
            return source

        monkeypatch.setattr(server, "get_match", cold)
        await room.new_match(99)
        assert calls == [99] and room.match is source
        assert room.seed == 99 and room.run == 2 and not room.playing

    asyncio.run(scenario())


class Socket:
    def __init__(self):
        self.closed = None
        self.received = []
        self.snapshot = asyncio.Event()

    async def accept(self):
        pass

    async def close(self, **kwargs):
        self.closed = kwargs

    async def receive_text(self):
        await asyncio.Event().wait()

    async def send_text(self, text):
        message = json.loads(text)
        self.received.append(message)
        if message["type"] == "snapshot":
            self.snapshot.set()


def test_two_connections_finishing_the_same_load_join_one_room(source, monkeypatch):
    async def scenario():
        monkeypatch.setattr(server, "rooms", {})
        entered, release = asyncio.Event(), asyncio.Event()
        entries = []

        async def prepare(seed):
            entries.append(seed)
            if len(entries) == 2:
                entered.set()
            await release.wait()
            return source

        monkeypatch.setattr(server, "prepare_match", prepare)
        sockets = [Socket(), Socket()]
        tasks = [asyncio.create_task(server.ws(ws, "shared", role="app", seed=7)) for ws in sockets]
        try:
            await asyncio.wait_for(entered.wait(), 1)
            release.set()
            await asyncio.wait_for(asyncio.gather(*(ws.snapshot.wait() for ws in sockets)), 1)
            assert len(server.rooms) == 1
            room = server.rooms["shared"]
            assert len(room.clients) == 2 and room.seed == 7 and room.run == 1
            assert room.match is source
            assert all(ws.received[0]["state"]["seed"] == 7 for ws in sockets)
        finally:
            release.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize("busy", [False, True])
def test_socket_admission_rechecks_room_capacity_after_preparation(source, monkeypatch, busy):
    async def scenario():
        monkeypatch.setattr(server, "rooms", {})
        monkeypatch.setattr(server, "MAX_ROOMS", 1)

        async def prepare(seed):
            if busy:
                raise server.MatchLoadBusy()
            server.rooms["other"] = object()  # A concurrent arrival fills the last slot.
            return source

        monkeypatch.setattr(server, "prepare_match", prepare)
        ws = Socket()
        await server.ws(ws, "late", role="app")
        assert ws.closed["code"] == 1013 and not ws.received
        assert "late" not in server.rooms

    asyncio.run(scenario())


def test_warm_scan_yields_to_the_event_loop_and_uses_a_private_replay(source, monkeypatch):
    async def scenario():
        loop, release, calls = asyncio.get_running_loop(), threading.Event(), []

        def scan(to_t):
            calls.append(to_t)
            loop.call_soon_threadsafe(release.set)
            assert release.wait(1), "warm-up scan blocked the shared event loop"
            return []

        monkeypatch.setattr(server, "Room", lambda *a, **kw: SimpleNamespace())
        monkeypatch.setattr(server, "Replay", lambda match: SimpleNamespace(advance=scan))
        await server.warm_demo(99)
        assert calls == [source.duration]

    asyncio.run(scenario())


def test_service_shutdown_cancels_the_owned_warm_task(monkeypatch):
    async def scenario():
        started, stopped = asyncio.Event(), asyncio.Event()

        async def warm():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setenv("VMI_WARM_DEMO", "1")
        monkeypatch.setattr(server, "warm_demo", warm)
        async with server.lifespan(server.app):
            await asyncio.wait_for(started.wait(), 1)
        assert stopped.is_set()

    asyncio.run(scenario())


def test_host_gets_a_retryable_error_without_losing_its_run_when_loading_is_busy(source, monkeypatch):
    monkeypatch.setattr(server, "rooms", {})
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/busy-host?seed=12") as ws:
            first = ws.receive_json()
            assert first["type"] == "snapshot" and first["host"]

            async def busy(seed):
                raise server.MatchLoadBusy()

            monkeypatch.setattr(server, "prepare_match", busy)
            ws.send_json({"cmd": "new_match", "seed": 99})
            for _ in range(20):
                error = ws.receive_json()
                if error["type"] == "error":
                    break
            assert error["code"] == "match_busy" and error["run_id"] == first["run_id"]
            room = server.rooms["busy-host"]
            assert room.seed == 12 and room.match is source and room.run == 1


def test_cancelled_waiter_does_not_cancel_a_shared_load_or_free_its_slot(source, monkeypatch):
    async def scenario():
        loop, started = asyncio.get_running_loop(), asyncio.Event()
        release, calls = threading.Event(), []

        def cold(seed):
            calls.append(seed)
            loop.call_soon_threadsafe(started.set)
            assert release.wait(2)
            return source

        monkeypatch.setattr(server, "get_match", cold)
        first = asyncio.create_task(server.prepare_match(99))
        await asyncio.wait_for(started.wait(), 1)
        second = asyncio.create_task(server.prepare_match(99))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await asyncio.wait_for(second, 1) is source
        assert calls == [99]

    asyncio.run(scenario())


def test_pending_work_is_bounded_but_existing_and_cached_sources_can_join(source, monkeypatch):
    async def scenario():
        loop, started = asyncio.get_running_loop(), asyncio.Event()
        release, calls = threading.Event(), []

        def cold(seed):
            calls.append(seed)
            loop.call_soon_threadsafe(started.set)
            assert release.wait(2)
            return source

        monkeypatch.setattr(server, "get_match", cold)
        tasks = [asyncio.create_task(server.prepare_match(100+i)) for i in range(4)]
        try:
            await asyncio.wait_for(started.wait(), 1)
            with pytest.raises(server.MatchLoadBusy):
                await server.prepare_match(104)
            server._match_cache[888] = source
            assert await server.prepare_match(888) is source
            joined = asyncio.create_task(server.prepare_match(100))
            await asyncio.sleep(0)
        finally:
            release.set()
        assert all(m is source for m in await asyncio.gather(*tasks, joined))
        assert calls == [100, 101, 102, 103]

    asyncio.run(scenario())


def test_failed_work_can_retry_without_poisoning_singleflight(source, monkeypatch):
    calls = []

    def cold(seed):
        calls.append(seed)
        if len(calls) == 1:
            raise ValueError("bad source")
        return source

    monkeypatch.setattr(server, "get_match", cold)

    async def scenario():
        with pytest.raises(ValueError, match="bad source"):
            await server.prepare_match(99)
        assert await server.prepare_match(99) is source

    asyncio.run(scenario())
    assert calls == [99, 99]


@pytest.mark.parametrize("superseding", ["seek", "expire", "new_match"])
def test_late_preparation_cannot_replace_a_newer_room_state(source, monkeypatch, superseding):
    async def scenario():
        room = server.Room("superseded", 12)
        monkeypatch.setattr(server, "rooms", {room.name: room})
        started, release = asyncio.Event(), asyncio.Event()

        async def prepare(seed):
            if seed == 99:
                started.set()
                await release.wait()
            return source

        monkeypatch.setattr(server, "prepare_match", prepare)
        old = asyncio.create_task(room.new_match(99))
        await asyncio.wait_for(started.wait(), 1)
        if superseding == "seek":
            await room.seek(1)
        elif superseding == "expire":
            server.drop_room_if_empty(room.name)
        else:
            await room.new_match(88)
        expected = room.seed, room.run, room.replay.now
        release.set()
        await old
        assert (room.seed, room.run, room.replay.now) == expected
        assert room.match is source
        if superseding == "expire":
            assert room.name not in server.rooms

    asyncio.run(scenario())


def test_backwards_seek_reuses_the_room_source_even_if_the_cache_evicted_it(source, monkeypatch):
    async def scenario():
        room = server.Room("backwards", 12)
        room.replay.advance(2)

        def unavailable(seed):
            raise AssertionError("backward seek must not regenerate the same world")

        monkeypatch.setattr(server, "get_match", unavailable)
        await room.seek(1)
        assert room.match is source and room.replay.now == 1 and room.run == 2

    asyncio.run(scenario())


def test_closed_request_loop_does_not_lose_the_shared_worker(source, monkeypatch):
    release, calls = threading.Event(), []

    async def abandon():
        loop, started = asyncio.get_running_loop(), asyncio.Event()

        def cold(seed):
            calls.append(seed)
            loop.call_soon_threadsafe(started.set)
            assert release.wait(2)
            return source

        monkeypatch.setattr(server, "get_match", cold)
        task = asyncio.create_task(server.prepare_match(99))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(abandon())

    async def rejoin():
        task = asyncio.create_task(server.prepare_match(99))
        await asyncio.sleep(0)
        release.set()
        assert await asyncio.wait_for(task, 1) is source

    try:
        asyncio.run(rejoin())
    finally:
        release.set()
    assert calls == [99]


def test_sync_generation_shares_cache_and_retains_only_a_bounded_number_of_sources(source, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    calls, barrier = [], threading.Barrier(8)
    monkeypatch.setattr(server, "generate_match", lambda seed: calls.append(seed) or source)

    def join():
        barrier.wait(timeout=2)
        return GET_MATCH(99)

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert all(m is source for m in list(workers.map(lambda _: join(), range(8))))
    assert calls == [99]
    for seed in range(100, 110):
        assert GET_MATCH(seed) is source
    assert len(server._match_cache) == server.MATCH_CACHE_MAX
    assert 99 not in server._match_cache  # A live room still owns its original Match.


def test_cached_source_does_not_wait_for_the_generation_lock(source, monkeypatch):
    async def scenario():
        loop, started = asyncio.get_running_loop(), asyncio.Event()
        release = threading.Event()
        server._match_cache[12] = source

        def cold(seed):
            loop.call_soon_threadsafe(started.set)
            assert release.wait(2), "a cached read waited behind cold generation"
            return source

        monkeypatch.setattr(server, "get_match", GET_MATCH)
        monkeypatch.setattr(server, "generate_match", cold)
        task = asyncio.create_task(server.prepare_match(99))
        await asyncio.wait_for(started.wait(), 1)
        try:
            assert GET_MATCH(12) is source
            assert await server.prepare_match(12) is source
        finally:
            release.set()
        assert await task is source

    asyncio.run(scenario())
