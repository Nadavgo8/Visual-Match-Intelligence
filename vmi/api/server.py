"""FastAPI app: the TV view, the companion app, and a live WebSocket per room.

A room is one replayed match shared by every screen that joins it: the TV view
drives playback, phones join the same room as companions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ..agents.explainer import Explainer
from ..agents.llm import explainer_agent, foundry_client
from ..agents.qa import Assistant
from ..engine import derive
from ..engine.attention import visible_to
from ..engine.replay import Replay
from ..generator.match import Match, generate_match
from ..generator.tracking import Tracker

log = logging.getLogger("vmi")
WEB = Path(__file__).resolve().parents[2] / "web"
DEMO_SEED = int(os.getenv("VMI_DEMO_SEED", "12"))
TICK_HZ = 10
SPEEDS = [1, 2, 4, 8, 16, 32]
DEFAULT_PROFILE = {"depth": "basic", "team": None, "amount": "balanced"}

app = FastAPI(title="Visual Match Intelligence", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")

_client, _model_name = foundry_client()
_match_cache: dict[int, Match] = {}


def get_match(seed: int) -> Match:
    if seed not in _match_cache:
        _match_cache[seed] = generate_match(seed)
    return _match_cache[seed]


def chapters(match: Match) -> list[dict]:
    """Jump points for the replay controls (from the generated feed)."""
    out = []
    for e in match.events:
        label = None
        if e["type"] == "shot" and e["shot"]["outcome"] == "goal":
            label = "Goal"
        elif e["type"] == "var" and e["var"]["phase"] == "check":
            label = "VAR check"
        elif e["type"] == "card" and e["card"]["colour"] != "yellow":
            label = "Red card"
        elif e["type"] == "period_end":
            label = "Half-time" if e["period_end"]["period_no"] == 1 else "Full-time"
        if label:
            out.append({"t": max(0.0, e["t"] - 20), "label": label, "clock": e["clock"]})
    return out


@dataclass
class Client:
    ws: WebSocket
    role: str
    profile: dict = field(default_factory=lambda: dict(DEFAULT_PROFILE))


class Room:
    def __init__(self, name: str, seed: int):
        self.name = name
        self.seed = seed
        self.clients: list[Client] = []
        self.speed = 4
        self.playing = False
        self.task: asyncio.Task | None = None
        self.reset()

    def reset(self, seed: int | None = None):
        self.counts = {"in": 0, "banner": 0, "feed": 0, "analysis": 0, "skip": 0}
        self.recent = []
        if seed is not None:
            self.seed = seed
        self.match = get_match(self.seed)
        self.replay = Replay(self.match)
        self.tracker = Tracker(self.match)
        roster = {p["name"] for t in self.match.meta["teams"].values() for p in t["players"]}
        self.explainer = Explainer(explainer_agent(_client, _model_name) if _client else None, roster)
        self.assistant = Assistant(self.replay.model, _client, _model_name)
        self.feed: list[dict] = []
        self.analyses: list[dict] = []
        self.texts: dict[tuple, dict] = {}  # (cue_id, depth, team) -> explainer result
        self.pending: dict[tuple, asyncio.Task] = {}
        self.last_meters: dict | None = None

    # ---------- broadcast ----------
    async def send(self, c: Client, msg: dict):
        try:
            await c.ws.send_text(json.dumps(msg))
        except Exception:
            pass

    async def to_role(self, role: str, msg: dict):
        await asyncio.gather(*(self.send(c, msg) for c in self.clients if c.role == role))

    def state(self) -> dict:
        m = self.replay.model
        return {"type": "state", "room": self.name, "seed": self.seed, "t": round(self.replay.now, 2),
                "duration": self.match.duration, "playing": self.playing, "speed": self.speed,
                "clock": m.clock, "period": m.period, "score": m.score,
                "teams": {s: {k: v for k, v in tm.items() if k != "players"} for s, tm in self.match.meta["teams"].items()},
                "chapters": chapters(self.match), "agents": "foundry" if _client else "local",
                "model": _model_name}

    # ---------- playback ----------
    def ensure_loop(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.loop())

    async def loop(self):
        last = time.perf_counter()
        while self.clients:
            await asyncio.sleep(1 / TICK_HZ)
            now = time.perf_counter()
            dt, last = now - last, now
            if self.playing and not self.replay.done:
                outs = self.replay.advance(self.replay.now + dt * self.speed)
                await self.route(outs)
                if self.replay.done:
                    self.playing = False
                    await self.broadcast_state()
            await self.to_role("tv", {"type": "frame", **self.tracker.frame(self.replay.now)})

    async def broadcast_state(self):
        st = self.state()
        await asyncio.gather(*(self.send(c, st) for c in self.clients))

    async def seek(self, t: float):
        if t < self.replay.now:
            self.reset()
        outs = self.replay.advance(t)
        for o in outs:
            self.trace(o)
        self.recent = self.recent[-12:]
        # a jump replays history silently: keep feed and analyses, drop transient banners
        await self.route([o for o in outs if o["kind"] in ("feed", "analysis")], live=False, traced=True)
        meters = [o for o in outs if o["kind"] == "meters"]
        if meters:
            await self.route(meters[-1:])
        await self.broadcast_state()
        for c in self.clients:
            if c.role == "app":
                await self.send_backlog(c)

    # ---------- routing engine outputs ----------
    def trace(self, o: dict):
        k = o["kind"]
        if k == "meters" or (k == "banner" and o["update"]):
            return
        self.counts[k] += 1
        if k in ("skip", "banner", "feed", "analysis"):
            what = {"banner": f"screen · {o.get('label')}", "feed": "feed",
                    "analysis": f"analysis · {o.get('moment')}", "skip": "left out"}[k]
            why = o.get("why") or (o["text"]["basic"] if k == "feed" else f"stoppage, tier {o.get('tier')}")
            self.recent.append({"clock": o.get("clock") or self.replay.model.clock, "decision": what, "why": why})

    async def route(self, outs: list[dict], live: bool = True, traced: bool = False):
        for o in outs:
            if not traced:
                self.trace(o)
            k = o["kind"]
            if k == "banner":
                await self.to_role("tv", {**o, "type": "banner", "banner": o["type"]})
            elif k == "meters":
                self.last_meters = o
                self.counts["in"] = self.replay.engine.n_in
                await self.to_role("tv", {"type": "trace", "counts": self.counts, "recent": self.recent[-12:]})
                self.recent.clear()
                await self.to_role("tv", {"type": "meters", **o})
                await self.to_role("app", {"type": "meters", "clock": o["clock"], "score": o["score"],
                                           "atmosphere": o["atmosphere"], "momentum": o["momentum"]})
            elif k == "feed":
                self.feed.append(o)
                if live:
                    for c in self.clients:
                        if c.role == "app" and visible_to(o, c.profile["amount"]):
                            await self.send(c, self.feed_msg(o, c.profile))
            elif k == "analysis":
                self.analyses.append(o)
                for c in self.clients:
                    if c.role == "app" and visible_to(o, c.profile["amount"]):
                        self.request_text(o, c.profile, notify=live)

    def feed_msg(self, o: dict, profile: dict) -> dict:
        return {"type": "feed", "cue_id": o["cue_id"], "clock": o["clock"], "t": o["t"], "icon": o["icon"],
                "team": o["team"], "mine": bool(profile.get("team") and o["team"] == profile["team"]),
                "text": o["text"][profile["depth"]], "evidence": o["evidence"], "tier": o["tier"]}

    def request_text(self, a: dict, profile: dict, notify: bool = True):
        key = (a["cue_id"], profile["depth"], profile.get("team"))
        if key in self.texts:
            if notify:
                asyncio.create_task(self.push_analysis(a, key))
            return
        if key in self.pending:
            return
        self.pending[key] = asyncio.create_task(self._generate(a, key))

    async def _generate(self, a: dict, key: tuple):
        res = await self.explainer.write(a["factpack"], key[1], key[2])
        self.texts[key] = res
        self.pending.pop(key, None)
        await self.push_analysis(a, key)

    async def push_analysis(self, a: dict, key: tuple):
        res = self.texts[key]
        msg = {"type": "analysis", "cue_id": a["cue_id"], "clock": a["clock"], "t": a["t"], "moment": a["moment"],
               "text": res["text"], "sentences": res["sentences"], "receipts": {
                   "source": res["source"], "model": res["model"], "latency_ms": res["latency_ms"],
                   "validation": res["validation"], "rejected": res.get("rejected")},
               "facts": a["factpack"]["facts"] + a["factpack"].get("deep_context", [])}
        for c in self.clients:
            if c.role == "app" and (c.profile["depth"], c.profile.get("team")) == key[1:] \
                    and visible_to(a, c.profile["amount"]):
                await self.send(c, msg)

    async def send_backlog(self, c: Client):
        items = [self.feed_msg(o, c.profile) for o in self.feed if visible_to(o, c.profile["amount"])]
        await self.send(c, {"type": "backlog", "feed": items})
        for a in self.analyses:
            if visible_to(a, c.profile["amount"]):
                self.request_text(a, c.profile)


rooms: dict[str, Room] = {}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/tv")
def tv():
    return FileResponse(WEB / "tv.html")


@app.get("/app")
def companion():
    return FileResponse(WEB / "app.html")


@app.get("/api/health")
def health():
    return {"ok": True, "agents": "foundry" if _client else "local", "model": _model_name, "rooms": len(rooms)}


@app.get("/api/match/{seed}/{stream}")
def export(seed: int, stream: str):
    """Download a generated match's raw streams as JSONL (the input data, for inspection)."""
    m = get_match(seed)
    if stream == "meta":
        return JSONResponse(m.meta)
    rows = {"events": m.events, "crowd": m.crowd, "match_state": m.match_state}.get(stream)
    if rows is None:
        return JSONResponse({"error": "stream must be meta, events, crowd or match_state"}, status_code=404)
    return PlainTextResponse("\n".join(json.dumps(r) for r in rows), media_type="application/x-ndjson")


@app.websocket("/ws/{room_name}")
async def ws(websocket: WebSocket, room_name: str, role: str = "tv", seed: int | None = None):
    await websocket.accept()
    room_name = room_name[:40]
    room = rooms.get(room_name)
    if room is None:
        room = rooms[room_name] = Room(room_name, seed or DEMO_SEED)
    c = Client(websocket, "app" if role == "app" else "tv")
    room.clients.append(c)
    room.ensure_loop()
    await room.send(c, room.state())
    if room.last_meters:
        await room.route([room.last_meters])
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            cmd = msg.get("cmd")
            if cmd == "play":
                room.playing = True
                await room.broadcast_state()
            elif cmd == "pause":
                room.playing = False
                await room.broadcast_state()
            elif cmd == "speed" and msg.get("value") in SPEEDS:
                room.speed = msg["value"]
                await room.broadcast_state()
            elif cmd == "seek":
                await room.seek(float(msg.get("t", 0)))
            elif cmd == "new_match":
                room.reset(int(msg.get("seed", DEMO_SEED)))
                room.playing = False
                await room.broadcast_state()
                for cc in room.clients:
                    if cc.role == "app":
                        await room.send_backlog(cc)
            elif cmd == "profile":
                p = msg.get("profile", {})
                c.profile = {
                    "depth": "deep" if p.get("depth") == "deep" else "basic",
                    "team": p.get("team") if p.get("team") in ("home", "away") else None,
                    "amount": p.get("amount") if p.get("amount") in ("big", "balanced", "everything") else "balanced",
                }
                await room.send_backlog(c)
            elif cmd == "ask":
                q = str(msg.get("q", ""))[:400]
                res = await room.assistant.answer(q, c.profile)
                await room.send(c, {"type": "answer", "id": msg.get("id"), "q": q, **res,
                                    "clock": room.replay.model.clock})
    except WebSocketDisconnect:
        pass
    finally:
        room.clients.remove(c)
        if not room.clients:
            room.playing = False
