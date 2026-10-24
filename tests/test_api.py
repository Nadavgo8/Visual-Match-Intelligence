import json
import os
import asyncio

os.environ["VMI_WARM_DEMO"] = "0"
os.environ["VMI_OFFLINE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from vmi.api.server import app, Room, chapters  # noqa: E402


def test_health_and_pages():
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"]
    for path in ("/", "/tv", "/app"):
        assert c.get(path).status_code == 200
    rows = c.get("/api/match/12/events").text.splitlines()
    assert json.loads(rows[0])["source"] in ("event_feed", "audio")


def test_room_seek_feed_and_ask():
    c = TestClient(app)
    with c.websocket_connect("/ws/test?role=app") as ws:
        assert json.loads(ws.receive_text())["type"] == "state"
        ws.send_text(json.dumps({"cmd": "profile", "profile": {"depth": "deep", "amount": "everything"}}))
        assert json.loads(ws.receive_text())["type"] == "backlog"
        ws.send_text(json.dumps({"cmd": "seek", "t": 1200}))
        seen = set()
        for _ in range(60):
            m = json.loads(ws.receive_text())
            seen.add(m["type"])
            if m["type"] == "backlog" and m["feed"]:
                break
        assert "backlog" in seen
        ws.send_text(json.dumps({"cmd": "ask", "q": "what's the score?", "id": "q1"}))
        for _ in range(60):
            m = json.loads(ws.receive_text())
            if m["type"] == "answer":
                assert m["id"] == "q1" and "Harbour City" in m["text"]
                break
        else:
            raise AssertionError("no answer")


def test_v2_companion_hides_future_chapters_and_upserts_shot_items():
    room = Room("v2-upsert-test", 12)
    state = room.state("app")
    assert state["chapters"] == [] and state["duration"] is None
    assert room.state("tv")["chapters"] == chapters(room.match)
    outputs = room.replay.advance(1200)
    asyncio.run(room.route(outputs, live=False))
    ids = [o["cue_id"] for o in room.feed]
    assert len(ids) == len(set(ids))
    shots = [o for o in room.feed if o.get("shot_id")]
    assert shots and any(o["xg"] is not None for o in shots)
    for shot in shots:
        assert sum(o.get("shot_id") == shot["shot_id"] for o in room.feed) == 1
    c = TestClient(app)
    with c.websocket_connect("/ws/v2-boundary-test?role=app") as ws:
        initial = json.loads(ws.receive_text())
        assert initial["chapters"] == [] and initial["duration"] is None


def test_3d_assets_are_served_locally_and_state_identifies_source_match():
    room = Room("3d-source-identity", 12)
    assert room.state("tv")["match_id"] == room.tracker.frame(0)["match_id"]
    original = room.state("tv")["match_id"]
    room.reset(13)
    assert room.state("tv")["match_id"] != original
    client = TestClient(app)
    for asset in ("match-3d.mjs", "stadium.mjs", "footballers.mjs", "renderer-host.mjs",
                  "vendor/three/three.module.js", "vendor/three/three.core.js"):
        response = client.get("/static/" + asset)
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
