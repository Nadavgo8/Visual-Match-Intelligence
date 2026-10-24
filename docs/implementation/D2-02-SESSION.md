# D2-02 — Real-time session contract

How the match screen (`/tv`) and the companion app (`/app`) stay in step with a room. Server: `vmi/api/server.py`. Client: `web/session.mjs`, used by `web/tv.js` and `web/app.js`.

## Connection

`GET /ws/{room}?role=tv|app[&host=<token>]`. Room names are cut to 40 characters. At most 64 rooms exist; past that, a new room is refused with close code 1013. A room with no clients is deleted after 120 s, so a screen that reconnects quickly keeps its match.

## Host

Only the host controls playback: `play`, `pause`, `speed`, `seek`, `new_match`. Anyone else gets `{"type": "error", "code": "not_host"}`, and the room doesn't change.

- A phone (`role=app`) is never the host, even with the token.
- A match screen that presents the room's token is the host.
- If no connected client is the host, the next match screen becomes host and receives a fresh `host_token` in its snapshot (the old token stops working). `web/session.mjs` keeps it in `sessionStorage` for that room and sends it on reconnect.

## Messages

Every server message carries:

| Field | Meaning |
|---|---|
| `run_id` | The room's current run (`r1`, `r2`, …). Every `seek` and `new_match` starts a new run. |
| `seq` | Per connection, starting at 1 and rising by exactly 1. |

`snapshot` is always the first message on a connection and the first message of every new run:

```json
{"type": "snapshot", "run_id": "r2", "seq": 14, "host": false,
 "state": {"t": 1200.0, "clock": "19:59", "score": {"home": 1, "away": 0}, "...": "..."},
 "meters": {"type": "meters", "...": "..."},
 "feed": [{"type": "feed", "cue_id": "...", "...": "..."}]}
```

`feed` is present only for phones and follows the phone's current settings. The phone's `state` still hides the match duration and future chapters. After a snapshot come the existing live messages: `state`, `frame`, `banner`, `meters`, `trace` (match screen), `feed`, `backlog`, `analysis`, `answer` (phone).

## Rules the client applies (`MessageGate`)

- Nothing is applied before the first snapshot.
- A message whose `seq` isn't higher than the last one is a duplicate or out of order, and is dropped.
- A message from another run is dropped. A snapshot always switches to its run.
- A dropped connection is shown as disconnected, and the screen clears its temporary marker; it never animates play that wasn't delivered. Reconnect waits 0.5, 1, 2, 4, then 8 s, staying at 8 s.

## Rules the server applies

- **Old runs never publish.** A new run cancels pending analysis writing. A text that finishes for an old run is neither stored nor sent. An Ask answer that finishes after a jump is replaced with `{"type": "answer_discarded", "id": ..., "reason": "run_changed"}`, and the app asks the viewer to ask again.
- **Slow clients don't stall the match.** Each client has its own outbox and writer. Only the newest tracking frame waits to be sent, and it is replaced, never queued. Events are never dropped silently: if 256 events are waiting, the backlog is replaced by one snapshot and the client's `resyncs` count goes up.
- **The end of the match.** The full-time analysis is released at the last tick and reaches the phone (regression test).

## Tests

`tests/test_realtime_session.py` (17) and the updated `tests/test_api.py`; `tests/web/session.test.mjs` (6). Multi-connection tests use `with TestClient(app)` so that every connection shares one event loop, as under uvicorn. Without it, Starlette runs each connection on its own loop.

Not covered here: linking events that arrive before their source, and duplicate or reverse-order feed records. The engine handles those (D1-01/D1-02 contract tests).
