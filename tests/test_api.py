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
    # D2-02: the hosting match screen seeks; the phone follows through a new snapshot.
    with TestClient(app) as c:
        with c.websocket_connect("/ws/test?role=tv") as tv, c.websocket_connect("/ws/test?role=app") as ws:
            assert json.loads(tv.receive_text())["host"] is True
            assert json.loads(ws.receive_text())["type"] == "snapshot"
            ws.send_text(json.dumps({"cmd": "profile", "profile": {"depth": "deep", "amount": "everything"}}))
            assert json.loads(ws.receive_text())["type"] == "backlog"
            tv.send_text(json.dumps({"cmd": "seek", "t": 1200}))
            for _ in range(60):
                m = json.loads(ws.receive_text())
                if m["type"] == "snapshot" and m["feed"]:
                    break
            else:
                raise AssertionError("no snapshot with the feed after the seek")
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
        assert initial["type"] == "snapshot"
        assert initial["state"]["chapters"] == [] and initial["state"]["duration"] is None


def test_browser_modules_are_served_as_javascript():
    # Browsers refuse module scripts whose MIME type isn't JavaScript; the OS mapping for .mjs varies.
    c = TestClient(app)
    for name in ("session.mjs", "atmosphere.mjs", "overlay-state.mjs", "app.js", "tv.js"):
        r = c.get(f"/static/{name}")
        assert r.status_code == 200 and "javascript" in r.headers["content-type"], (name, r.headers["content-type"])
