"""D2-02 session contract: snapshot first, run_id and seq on every message, host-only control,
no publishing across runs, bounded per-client queues and room clean-up."""

import asyncio
import json
import os

os.environ["VMI_WARM_DEMO"] = "0"
os.environ["VMI_OFFLINE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from vmi.api import server  # noqa: E402
from vmi.api.server import Client, Room, app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_rooms():
    server.rooms.clear()
    yield
    server.rooms.clear()


def client():
    """One TestClient portal: every connection shares one event loop, as under uvicorn."""
    return TestClient(app)


def recv(ws):
    return json.loads(ws.receive_text())


def until(ws, kind, limit=200):
    for _ in range(limit):
        m = recv(ws)
        if m["type"] == kind:
            return m
    raise AssertionError(f"no {kind} message")


class FakeWS:
    """Records what a client would receive; can block to simulate a slow connection."""

    def __init__(self, block=False):
        self.sent, self.block = [], block

    async def send_text(self, text):
        if self.block:
            await asyncio.Event().wait()
        self.sent.append(json.loads(text))


def test_first_message_is_a_numbered_snapshot_without_future_data():
    with TestClient(app).websocket_connect("/ws/s1?role=app") as ws:
        m = recv(ws)
    assert m["type"] == "snapshot" and m["seq"] == 1 and m["run_id"] == "r1"
    assert m["host"] is False and "host_token" not in m
    assert m["state"]["chapters"] == [] and m["state"]["duration"] is None
    assert m["feed"] == []


def test_phone_cannot_control_playback():
    with client() as c:
        with c.websocket_connect("/ws/s2?role=tv"), c.websocket_connect("/ws/s2?role=app") as phone:
            recv(phone)
            for cmd in ({"cmd": "play"}, {"cmd": "seek", "t": 1200}, {"cmd": "speed", "value": 32},
                        {"cmd": "new_match", "seed": 7}):
                phone.send_text(json.dumps(cmd))
                assert until(phone, "error")["code"] == "not_host"
            room = server.rooms["s2"]
            expected_speed = 1 if server.DEMO_SEED == 2 else 4
            assert (room.playing, room.speed, room.seed, room.replay.now, room.run) == (False, expected_speed, server.DEMO_SEED, 0.0, 1)


def test_only_the_token_holder_or_the_first_screen_is_host():
    with client() as c:
        with c.websocket_connect("/ws/s3?role=tv") as first:
            snap = recv(first)
            token = snap["host_token"]
            assert snap["host"] is True and token
            with c.websocket_connect("/ws/s3?role=tv&host=wrong") as second:
                assert recv(second)["host"] is False
            with c.websocket_connect(f"/ws/s3?role=app&host={token}") as phone:
                assert recv(phone)["host"] is False  # a phone never becomes host, even with the token
        with c.websocket_connect(f"/ws/s3?role=tv&host={token}") as back:
            snap = recv(back)
            assert snap["host"] is True and "host_token" not in snap  # same token, nothing new handed out


def test_seek_starts_a_new_run_with_a_snapshot_and_seq_keeps_rising():
    with client() as c:
        with c.websocket_connect("/ws/s4?role=tv") as tv, c.websocket_connect("/ws/s4?role=app") as phone:
            recv(tv)
            first = recv(phone)
            tv.send_text(json.dumps({"cmd": "seek", "t": 1200}))
            snap = until(phone, "snapshot")
            assert snap["run_id"] == "r2" and snap["seq"] > first["seq"]
            assert snap["feed"] and all(f["t"] <= 1200 for f in snap["feed"])
            phone.send_text(json.dumps({"cmd": "ask", "q": "what's the score?", "id": "q1"}))
            answer = until(phone, "answer")
            assert answer["run_id"] == "r2" and answer["id"] == "q1" and "Harbour City" in answer["text"]


def test_malformed_host_commands_are_refused_without_dropping_the_connection():
    with client() as c:
        with c.websocket_connect("/ws/bad?role=tv") as tv:
            recv(tv)
            for cmd in ({"cmd": "seek", "t": "abc"}, {"cmd": "seek", "t": None}, {"cmd": "new_match", "seed": "x"},
                        {"cmd": "seek", "t": float("nan")}):
                tv.send_text(json.dumps(cmd))
                assert until(tv, "error")["code"] == "bad_command"
            tv.send_text(json.dumps({"cmd": "pause"}))
            assert until(tv, "state")["playing"] is False  # still connected and in control
            assert server.rooms["bad"].run == 1


def test_malformed_transport_data_does_not_disconnect_or_change_the_room():
    with client() as c:
        with c.websocket_connect("/ws/input?role=tv") as tv:
            first = recv(tv)
            room = server.rooms["input"]
            token = room.host_token
            for raw in ("[]", "{", "null", '{"cmd":[]}',
                        '{"cmd":"profile","profile":[]}',
                        '{"cmd":"speed","value":true}',
                        '{"cmd":"seek","t":true}',
                        '{"cmd":"new_match","seed":false}',
                        '{"cmd":"pause"}' + " " * 4096):
                tv.send_text(raw)
                error = until(tv, "error")
                assert error["code"] == "bad_command" and error["run_id"] == first["run_id"]
                expected_speed = 1 if server.DEMO_SEED == 2 else 4
                assert (room.run, room.replay.now, room.seed, room.speed) == (1, 0, server.DEMO_SEED, expected_speed)
                assert room.host_token == token and room.clients[0].profile == server.DEFAULT_PROFILE
            tv.send_text('{"cmd":"pause"}')
            assert until(tv, "state")["playing"] is False
            tv.send_text('{"cmd":"profile","profile":{"depth":"deep"}}')
            until(tv, "backlog")
            assert room.clients[0].profile["depth"] == "deep"


def test_unknown_client_role_is_rejected_before_creating_a_room():
    with client() as c:
        with pytest.raises(WebSocketDisconnect) as closed:
            with c.websocket_connect("/ws/unknown-role?role=admin"):
                pass
        assert closed.value.code == 1008
        assert "unknown-role" not in server.rooms


def test_analysis_written_for_an_old_run_is_never_published():
    async def scenario():
        room = Room("s5", 12)
        gate = asyncio.Event()

        class SlowExplainer:
            async def write(self, pack, depth, team):
                await gate.wait()
                return {"text": "old", "sentences": [], "source": "template", "model": None,
                        "latency_ms": 0, "validation": "passed"}

        room.explainer = SlowExplainer()
        phone = Client(FakeWS(), "app")
        room.clients.append(phone)
        analysis = {"cue_id": "a1", "moment": "goal", "t": 10.0, "clock": "0:10", "tier": 1,
                    "factpack": {"facts": [], "moment": "goal"}}
        room.request_text(analysis, phone.profile)
        task = next(iter(room.pending.values()))
        await asyncio.sleep(0)
        room.new_run()  # a seek happens while the text is being written
        gate.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert room.texts == {} and not phone.outbox
    asyncio.run(scenario())


def test_ask_answered_after_a_seek_is_discarded_not_shown():
    async def scenario():
        room = Room("s6", 12)
        gate = asyncio.Event()

        class SlowAssistant:
            async def answer(self, q, profile):
                await gate.wait()
                return {"text": "stale", "evidence": []}

        server.rooms["s6"] = room
        room.assistant = SlowAssistant()
        ws = FakeWS()
        incoming = asyncio.Queue()
        ws.accept = lambda: asyncio.sleep(0)
        ws.receive_text = incoming.get
        await incoming.put(json.dumps({"cmd": "ask", "q": "score?", "id": "q9"}))
        endpoint = asyncio.create_task(server.ws(ws, "s6", role="app"))
        for _ in range(20):
            await asyncio.sleep(0)
        await room.seek(300)
        gate.set()
        for _ in range(50):
            await asyncio.sleep(0)
        kinds = [m["type"] for m in ws.sent]
        endpoint.cancel()
        return kinds, ws.sent
    kinds, sent = asyncio.run(scenario())
    assert "answer" not in kinds
    discarded = next(m for m in sent if m["type"] == "answer_discarded")
    assert discarded["id"] == "q9" and discarded["reason"] == "run_changed"


def test_slow_client_keeps_only_the_newest_frame_and_resyncs_instead_of_dropping_events():
    async def scenario():
        room = Room("s7", 12)
        c = Client(FakeWS(block=True), "tv")
        room.clients.append(c)
        room.queue_frame(c, {"t": 1.0})
        room.queue_frame(c, {"t": 2.0})
        assert c.frame["t"] == 2.0
        for i in range(server.OUTBOX_MAX):
            await room.send(c, {"type": "feed", "i": i})
        assert len(c.outbox) == server.OUTBOX_MAX and c.resyncs == 0
        await room.send(c, {"type": "feed", "i": "overflow"})
        assert c.resyncs == 1 and len(c.outbox) == 1 and c.outbox[0]["type"] == "snapshot"
    asyncio.run(scenario())


def test_writer_numbers_messages_in_order_and_sends_events_before_frames():
    async def scenario():
        room = Room("s8", 12)
        ws = FakeWS()
        c = Client(ws, "tv")
        room.queue_frame(c, {"t": 5.0})
        await room.send(c, {"type": "banner", "n": 1})
        await room.send(c, {"type": "meters", "n": 2})
        task = asyncio.create_task(room.writer(c))
        for _ in range(10):
            await asyncio.sleep(0)
        task.cancel()
        return ws.sent
    sent = asyncio.run(scenario())
    assert [(m["type"], m["seq"]) for m in sent] == [("banner", 1), ("meters", 2), ("frame", 3)]
    assert all(m["run_id"] == "r1" for m in sent)


def test_empty_room_expires_after_the_grace_period(monkeypatch):
    monkeypatch.setattr(server, "ROOM_GRACE_S", 0.0)
    with client() as c:
        with c.websocket_connect("/ws/s9?role=tv") as tv:
            recv(tv)
            assert "s9" in server.rooms
        with c.websocket_connect("/ws/other?role=app") as ws:  # lets the event loop run the expiry
            recv(ws)
            assert "s9" not in server.rooms


def test_room_cap_refuses_new_rooms(monkeypatch):
    monkeypatch.setattr(server, "MAX_ROOMS", 1)
    with client() as c:
        with c.websocket_connect("/ws/cap1?role=tv") as tv:
            recv(tv)
            with c.websocket_connect("/ws/cap2?role=tv") as refused:
                with pytest.raises(WebSocketDisconnect) as closed:
                    refused.receive_text()
            assert closed.value.code == 1013


def test_full_time_card_reaches_the_phone_after_the_last_tick(monkeypatch):
    monkeypatch.setattr(server, "OUTBOX_MAX", 10**6)  # a whole match of meters at once
    async def scenario():
        room = Room("s10", 12)
        phone = Client(FakeWS(), "app")
        phone.profile = {"depth": "basic", "team": None, "amount": "everything"}
        room.clients.append(phone)
        await room.route(room.replay.advance(room.match.duration))
        for task in list(room.pending.values()):
            await task
        for _ in range(10):
            await asyncio.sleep(0)
        return [m for m in phone.outbox if m["type"] == "analysis"]
    cards = asyncio.run(scenario())
    assert any(m["moment"] == "full_time" for m in cards)


def test_host_plays_changes_speed_and_loads_a_new_match_for_everyone():
    with client() as c:
        with c.websocket_connect("/ws/h1?role=tv") as tv, c.websocket_connect("/ws/h1?role=app") as phone:
            recv(tv)
            recv(phone)
            tv.send_text(json.dumps({"cmd": "play"}))
            assert until(tv, "state")["playing"] is True
            tv.send_text(json.dumps({"cmd": "speed", "value": 3}))  # not an allowed speed: ignored
            tv.send_text(json.dumps({"cmd": "speed", "value": 8}))
            assert until(tv, "state")["speed"] == 8
            tv.send_text(json.dumps({"cmd": "new_match", "seed": 7}))
            snap = until(phone, "snapshot")
            assert snap["state"]["seed"] == 7 and snap["run_id"] == "r2" and snap["state"]["playing"] is False
            assert snap["feed"] == []


def test_texts_and_pushes_for_an_old_run_are_dropped_even_without_cancellation():
    async def scenario():
        room = Room("h2", 12)
        phone = Client(FakeWS(), "app")
        room.clients.append(phone)

        class Fast:
            async def write(self, pack, depth, team):
                return {"text": "late", "sentences": [], "source": "template", "model": None,
                        "latency_ms": 0, "validation": "passed"}

        room.explainer = Fast()
        analysis = {"cue_id": "a9", "moment": "goal", "t": 5.0, "clock": "0:05", "tier": 1,
                    "factpack": {"facts": [], "moment": "goal"}}
        key = ("a9", "basic", None)
        old = room.run
        room.new_run()
        await room._generate(analysis, key, old)
        assert key not in room.texts
        room.texts[key] = {"text": "x", "sentences": [], "source": "template", "model": None,
                           "latency_ms": 0, "validation": "passed"}
        await room.push_analysis(analysis, key, old)
        assert not phone.outbox
    asyncio.run(scenario())


def test_writer_stops_quietly_when_the_socket_breaks():
    class Broken:
        async def send_text(self, text):
            raise ConnectionError("gone")

    async def scenario():
        room = Room("h3", 12)
        c = Client(Broken(), "tv")
        await room.send(c, {"type": "state"})
        await asyncio.wait_for(room.writer(c), timeout=1)  # returns instead of raising or hanging
    asyncio.run(scenario())


def test_reconnecting_within_the_grace_period_keeps_the_room_and_its_run():
    with client() as c:
        with c.websocket_connect("/ws/h4?role=tv") as tv:
            token = recv(tv)["host_token"]
            tv.send_text(json.dumps({"cmd": "seek", "t": 600}))
            until(tv, "snapshot")
        room = server.rooms["h4"]
        assert room.expiry is not None
        with c.websocket_connect(f"/ws/h4?role=tv&host={token}") as back:
            snap = recv(back)
            assert server.rooms["h4"] is room and room.expiry is None
            assert snap["host"] is True and snap["run_id"] == "r2" and snap["state"]["t"] == 600


def test_dropping_a_room_only_removes_empty_known_rooms():
    server.drop_room_if_empty("never-existed")
    room = Room("h5", 12)
    room.clients.append(Client(FakeWS(), "tv"))
    server.rooms["h5"] = room
    server.drop_room_if_empty("h5")
    assert server.rooms["h5"] is room
    room.clients.clear()
    server.drop_room_if_empty("h5")
    assert "h5" not in server.rooms


def test_catch_up_covers_delivered_items_up_to_the_press_and_is_per_run():
    with client() as c:
        with c.websocket_connect("/ws/cu?role=tv") as tv, c.websocket_connect("/ws/cu?role=app") as phone:
            recv(tv)
            recv(phone)
            phone.send_text(json.dumps({"cmd": "profile", "profile": {"depth": "basic", "amount": "everything"}}))
            until(phone, "backlog")
            tv.send_text(json.dumps({"cmd": "seek", "t": 2400}))
            snap = until(phone, "snapshot")
            room = server.rooms["cu"]
            phone.send_text(json.dumps({"cmd": "catch_up", "id": "c1", "since_t": None}))
            first = until(phone, "catch_up")
            assert first["id"] == "c1" and first["run_id"] == snap["run_id"]
            assert (first["from_t"], first["to_t"]) == (2100.0, 2400.0) and first["first_use"] is True
            delivered = {o["cue_id"]: o["delivered"] for o in room.feed}
            assert first["items"] and all(2100.0 < delivered[i] <= 2400.0 for i in first["items"])
            assert "Score:" in first["text"] and first["text"].startswith(f"From {first['from_clock']} to ")
            phone.send_text(json.dumps({"cmd": "catch_up", "id": "c2", "since_t": first["to_t"]}))
            again = until(phone, "catch_up")
            assert again["items"] == [] and again["text"].startswith("Nothing important happened")
            phone.send_text(json.dumps({"cmd": "catch_up", "id": "c3", "since_t": "yesterday"}))
            assert until(phone, "error")["code"] == "bad_command"


def test_feed_messages_carry_their_first_delivery_time():
    room = Room("cu2", 12)
    asyncio.run(room.route(room.replay.advance(1200), live=False))
    assert all(0 <= o["delivered"] <= 1200 and o["delivered"] >= o["t"] for o in room.feed)
    msg = room.feed_msg(room.feed[0], dict(server.DEFAULT_PROFILE))
    assert msg["delivered"] == room.feed[0]["delivered"]
