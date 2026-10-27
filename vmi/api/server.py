"""FastAPI app: the TV view, the companion app, and a live WebSocket per room.

A room is one replayed match shared by every screen that joins it. Only the host
(the first match screen, holding the room's host token) drives playback; phones join
the same room as companions and can never change the match.

Session contract (D2-02): every message carries the room's `run_id` and a
per-connection `seq`. A client first receives a `snapshot`, and gets a new one
whenever a seek or a new match starts a new run. Work started for an older run
(analysis text, Ask answers) is never published into a newer one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import mimetypes
import os
import random
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, RLock
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ..agents.explainer import Explainer
from . import catchup
from .messages import decode_command
from ..agents.llm import explainer_agent, foundry_client
from ..agents.qa import Assistant
from ..agents.voices import chat_line, kai_followup
from ..engine import derive
from ..engine.attention import visible_to
from ..engine.replay import Replay
from ..generator.match import Match, generate_match
from ..generator.scenarios import generate_demo_match
from ..generator.tracking import Tracker

log = logging.getLogger("vmi")
WEB = Path(__file__).resolve().parents[2] / "web"
# Browsers only run ES modules served as JavaScript; some OS registries map .mjs to text/plain.
mimetypes.add_type("text/javascript", ".mjs")
DEMO_SEED = int(os.getenv("VMI_DEMO_SEED", "2"))
MAX_SEED = 99999


def demo_mode() -> bool:
    """VMI_DEMO=1 (set before recording): every new room plays the locked demo match."""
    return os.getenv("VMI_DEMO") == "1"


def new_room_seed(requested: int | None) -> int:
    """The match a new room starts with: the one asked for, the demo match in demo mode,
    otherwise a fresh random match each time."""
    if requested:
        return requested
    return DEMO_SEED if demo_mode() else random.randint(1, MAX_SEED)
TICK_HZ = 20
SPEEDS = [1, 2, 4, 8, 16, 32]
DEFAULT_PROFILE = {"depth": "basic", "team": None, "amount": "balanced"}
CONTROL_COMMANDS = {"play", "pause", "speed", "seek", "new_match"}
OUTBOX_MAX = 256  # queued events per client before it is resynced with a snapshot
ROOM_GRACE_S = 120.0  # an empty room survives this long, so a reconnecting screen keeps its match
MAX_ROOMS = 64
MATCH_CACHE_MAX = 8
MATCH_LOAD_MAX = 4

def _telemetry():
    """Application Insights via OpenTelemetry when a connection string is set (Azure)."""
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(logger_name="vmi")
    except ImportError:
        log.warning("azure-monitor-opentelemetry not installed; telemetry off")


@asynccontextmanager
async def lifespan(_app):
    _telemetry()
    warm = []
    # Pre-writing the demo match's analyses only pays off when the demo will be played.
    if os.getenv("VMI_WARM_DEMO", "1" if demo_mode() else "0") == "1":
        warm.append(asyncio.create_task(warm_demo()))
    if _client is not None and os.getenv("VMI_WARM_FOUNDRY", "1") == "1":
        warm.append(asyncio.create_task(warm_foundry()))
    try:
        yield
    finally:
        for task in warm:
            task.cancel()
        await asyncio.gather(*warm, return_exceptions=True)


app = FastAPI(title="Visual Match Intelligence", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB), name="static")

_client, _model_name = foundry_client()
_match_cache: dict[int, Match] = {}
_match_lock = Lock()
_match_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vmi-source")
_match_loads: dict[int, Future[Match]] = {}
_match_load_lock = RLock()  # Only future bookkeeping; never held during generation.
# explainer results shared by all rooms: (seed, moment, t, depth, team) -> result.
# Replays are deterministic, so the demo match is written once and then served instantly.
_text_cache: dict[tuple, dict] = {}


def get_match(seed: int) -> Match:
    # Cached reads must not wait behind an unrelated cold seed's generation.
    match = _match_cache.get(seed)
    if match is not None:
        return match
    with _match_lock:
        if seed not in _match_cache:
            _match_cache[seed] = generate_demo_match(seed) if seed == 2 else generate_match(seed)
            while len(_match_cache) > MATCH_CACHE_MAX:
                del _match_cache[next(iter(_match_cache))]
        return _match_cache[seed]


class MatchLoadBusy(Exception):
    """The bounded source preparation queue has no free slot."""


async def prepare_match(seed: int) -> Match:
    """Share cold work without blocking rooms or cancelling another caller's load."""
    cached = _match_cache.get(seed)
    if cached is not None:
        return cached
    with _match_load_lock:
        future = _match_loads.get(seed)
        if future is None:
            if len(_match_loads) >= MATCH_LOAD_MAX:
                raise MatchLoadBusy("match preparation is busy; try again shortly")
            future = _match_loads[seed] = _match_worker.submit(get_match, seed)

            def finished(done):
                # Release admission only when the actual worker has stopped,
                # even if a caller disconnects or its event loop closes.
                with _match_load_lock:
                    if _match_loads.get(seed) is done:
                        del _match_loads[seed]

            future.add_done_callback(finished)
    wrapped = asyncio.wrap_future(future)
    wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
    return await asyncio.shield(wrapped)


def chapters(match: Match) -> list[dict]:
    """Jump points for the replay controls (from the generated feed)."""
    out = []
    by_id = {e["id"]: e for e in match.events}
    for e in match.events:
        label = None
        start = e["t"]
        if e["type"] == "shot_result" and e["outcome"] == "goal":
            label = "Goal"
        elif e["type"] == "var" and e["var"]["phase"] == "check":
            label = "VAR check"
        elif e["type"] == "card":
            if e["card"]["colour"] == "yellow":
                label = "Yellow card"
                offence = by_id.get(e.get("offence_id"))
                if offence and offence["type"] in {"foul", "handball"}:
                    label = "Foul / yellow card"
                    start = min(start, offence["t"])
            else:
                label = "Red card"
        elif e["type"] == "offside":
            label = "Offside"
            passes = [by_id[link] for link in e.get("related", [])
                      if link in by_id and by_id[link]["type"] == "pass"]
            if passes:
                start = min(start, *(p["t"] for p in passes))
        elif e["type"] == "period_end":
            label = "Half-time" if e["period_end"]["period_no"] == 1 else "Full-time"
        if label:
            out.append({"t": max(0.0, start - 20), "label": label, "clock": e["clock"]})
    return out


@dataclass(eq=False)
class Client:
    ws: WebSocket
    role: str
    profile: dict = field(default_factory=lambda: dict(DEFAULT_PROFILE))
    is_host: bool = False
    seq: int = 0
    outbox: deque = field(default_factory=deque)
    frame: dict | None = None  # only the newest tracking frame waits; older ones are replaced
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    writer: asyncio.Task | None = None
    resyncs: int = 0


class Room:
    def __init__(self, name: str, seed: int, *, match: Match | None = None):
        self.name = name
        self.seed = seed
        self.clients: list[Client] = []
        self.speed = 1 if seed == 2 else 4
        self.playing = False
        self.task: asyncio.Task | None = None
        self.host_token: str | None = None
        self.expiry: asyncio.TimerHandle | None = None
        self.run = 0
        self.match_request = 0
        self.pending: dict[tuple, asyncio.Task] = {}
        self.reset(match=match)

    @property
    def run_id(self) -> str:
        return f"r{self.run}"

    def new_run(self):
        """A seek or a new match: cancel work for the old run so it can't publish."""
        self.run += 1
        for task in self.pending.values():
            task.cancel()
        self.pending = {}
        self.held: list[tuple[dict, tuple, int]] = []  # explanations waiting for the next stoppage

    def reset(self, seed: int | None = None, *, match: Match | None = None):
        self.new_run()
        self.counts = {"in": 0, "banner": 0, "feed": 0, "analysis": 0, "skip": 0}
        self.recent = []
        if seed is not None:
            self.seed = seed
        self.match = match if match is not None else get_match(self.seed)
        self.replay = Replay(self.match, atmosphere_mode=os.getenv("VMI_ATMOSPHERE_MODE", "combined"))
        self.tracker = Tracker(self.match)
        roster = {p["name"] for t in self.match.meta["teams"].values() for p in t["players"]}
        self.explainer = Explainer(explainer_agent(_client, _model_name) if _client else None, roster)
        self.assistant = Assistant(self.replay.model, _client, _model_name)
        self.feed: list[dict] = []
        self.analyses: list[dict] = []
        self.texts: dict[tuple, dict] = {}  # (cue_id, depth, team) -> explainer result
        self.last_meters: dict | None = None
        self.clock_marks: list[tuple[float, str]] = [(0.0, "0:00")]  # (t, clock) seen each second

    # ---------- delivery ----------
    async def send(self, c: Client, msg: dict):
        """Queue a message for one client. Never blocks playback on a slow connection."""
        if len(c.outbox) >= OUTBOX_MAX:
            # The client fell too far behind: replace its backlog with a full snapshot
            # rather than dropping events silently.
            c.outbox.clear()
            c.resyncs += 1
            c.outbox.append(self.snapshot(c))
        else:
            c.outbox.append({**msg, "run_id": self.run_id})
        c.wake.set()

    def queue_frame(self, c: Client, frame: dict):
        c.frame = {**frame, "type": "frame", "run_id": self.run_id}
        c.wake.set()

    async def writer(self, c: Client):
        """Send queued messages in order, numbering each one for this connection."""
        try:
            while True:
                await c.wake.wait()
                c.wake.clear()
                while c.outbox or c.frame is not None:
                    if c.outbox:
                        msg = c.outbox.popleft()
                    else:
                        msg, c.frame = c.frame, None
                    c.seq += 1
                    await c.ws.send_text(json.dumps({**msg, "seq": c.seq}))
        except Exception:  # connection gone; the receive loop cleans up
            return

    async def to_role(self, role: str, msg: dict):
        for c in self.clients:
            if c.role == role:
                await self.send(c, msg)

    def snapshot(self, c: Client, host_token: str | None = None) -> dict:
        """Everything a client needs to (re)build its view for the current run."""
        snap = {"type": "snapshot", "run_id": self.run_id, "state": self.state(c.role), "host": c.is_host,
                "meters": self.meters_view(self.last_meters, c.role) if self.last_meters else None}
        if c.role == "app":
            snap["feed"] = [self.feed_msg(o, c.profile) for o in self.feed if visible_to(o, c.profile["amount"])]
        if host_token:
            snap["host_token"] = host_token
        return snap

    async def deliver_snapshot(self, c: Client, host_token: str | None = None):
        c.outbox.clear()
        c.frame = None
        await self.send(c, self.snapshot(c, host_token))
        if c.role == "app":
            for a in self.analyses:
                if visible_to(a, c.profile["amount"]):
                    self.request_text(a, c.profile)

    def meters_view(self, o: dict, role: str) -> dict:
        if role == "tv":
            return {**o, "type": "meters"}
        return {"type": "meters", "clock": o["clock"], "score": o["score"],
                "atmosphere": o["atmosphere"], "momentum": o["momentum"]}

    def state(self, role: str = "app") -> dict:
        m = self.replay.model
        return {"type": "state", "room": self.name, "seed": self.seed, "match_id": self.match.meta["match_id"], "t": round(self.replay.now, 2),
                "duration": self.match.duration if role == "tv" else None, "playing": self.playing, "speed": self.speed,
                "clock": m.clock, "period": m.period, "score": m.score,
                "teams": {s: {k: v for k, v in tm.items() if k != "players"} for s, tm in self.match.meta["teams"].items()},
                "chapters": chapters(self.match) if role == "tv" else [], "agents": "foundry" if _client else "local",
                "model": _model_name, "demo_seed": DEMO_SEED}

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
                await self.flush_held()
                if self.replay.done:
                    self.playing = False
                    await self.broadcast_state()
            tvs = [c for c in self.clients if c.role == "tv"]
            if tvs:
                frame = self.tracker.frame(self.replay.now)
                for c in tvs:
                    self.queue_frame(c, frame)

    async def broadcast_state(self):
        for c in self.clients:
            await self.send(c, self.state(c.role))

    async def seek(self, t: float):
        t = float(t)
        if not math.isfinite(t):
            raise ValueError("seek time must be a finite number")
        t = min(max(t, 0.0), self.match.duration)
        if t < self.replay.now:
            self.reset(match=self.match)
        else:
            self.new_run()
        outs = self.replay.advance(t)
        for o in outs:
            self.trace(o)
        self.recent = self.recent[-12:]
        # a jump replays history silently: keep feed and analyses, drop transient banners
        await self.route([o for o in outs if o["kind"] in ("feed", "analysis")], live=False, traced=True)
        meters = [o for o in outs if o["kind"] == "meters"]
        self.clock_marks += [(o["t"], o["clock"]) for o in meters]
        if meters:
            self.last_meters = meters[-1]
        for c in self.clients:
            await self.deliver_snapshot(c)

    async def new_match(self, seed: int):
        self.match_request += 1
        request, run = self.match_request, self.run
        match = await prepare_match(seed)
        if request != self.match_request or run != self.run:
            return  # A newer request, seek or room expiry superseded this load.
        self.reset(seed, match=match)
        self.playing = False
        for c in self.clients:
            await self.deliver_snapshot(c)

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
                self.clock_marks.append((o["t"], o["clock"]))
                self.counts["in"] = self.replay.engine.n_in
                await self.to_role("tv", {"type": "trace", "counts": self.counts, "recent": self.recent[-12:]})
                self.recent.clear()
                await self.to_role("tv", self.meters_view(o, "tv"))
                await self.to_role("app", self.meters_view(o, "app"))
            elif k == "feed":
                old = next((i for i, item in enumerate(self.feed) if item["cue_id"] == o["cue_id"]), None)
                if old is None:
                    o["delivered"] = o.get("at", self.replay.now)
                    self.feed.append(o)
                else:
                    o["delivered"] = self.feed[old]["delivered"]  # an enrichment doesn't make the item new
                    self.feed[old] = o
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
                "text": chat_line(o, profile["depth"]), "evidence": o["evidence"], "tier": o["tier"],
                "update": o.get("update", False), "delivered": o["delivered"],
                "speaker": o.get("speaker", "commentator"), "reply_to": o.get("reply_to")}

    def request_text(self, a: dict, profile: dict, notify: bool = True):
        key = (a["cue_id"], profile["depth"], profile.get("team"))
        shared = (self.seed, a["moment"], a["t"], key[1], key[2])
        if key not in self.texts and shared in _text_cache:
            self.texts[key] = _text_cache[shared]
        if key in self.texts:
            if notify:
                asyncio.create_task(self.push_analysis(a, key, self.run))
            return
        if key in self.pending:
            return
        self.pending[key] = asyncio.create_task(self._generate(a, key, self.run))

    async def _generate(self, a: dict, key: tuple, run: int):
        res = await self.explainer.write(a["factpack"], key[1], key[2])
        if run != self.run:
            return  # written for a run that a seek or a new match has replaced: never published
        self.texts[key] = res
        _text_cache[(self.seed, a["moment"], a["t"], key[1], key[2])] = res
        self.pending.pop(key, None)
        if self.replay.model.ball_in_play:
            # Written too late: play has restarted. Hold it for the next stoppage instead of
            # inviting the viewer to look away during live play.
            self.held.append((a, key, run))
            return
        await self.push_analysis(a, key, run)

    async def flush_held(self):
        """Publish held explanations once the ball is out of play again (still for this run only)."""
        if not self.held or self.replay.model.ball_in_play:
            return
        held, self.held = self.held, []
        for a, key, run in held:
            await self.push_analysis(a, key, run)

    async def push_analysis(self, a: dict, key: tuple, run: int):
        if run != self.run or key not in self.texts:
            return
        res = self.texts[key]
        msg = {"type": "analysis", "cue_id": a["cue_id"], "clock": a["clock"], "t": a["t"], "moment": a["moment"],
               "speaker": "analyst", "reply_to": a.get("reply_to"),
               "followup": kai_followup(a["cue_id"], a["factpack"]),
               "text": res["text"], "sentences": res["sentences"], "receipts": {
                   "source": res["source"], "model": res["model"], "latency_ms": res["latency_ms"],
                   "validation": res["validation"], "rejected": res.get("rejected")},
               "facts": a["factpack"]["facts"] + a["factpack"].get("deep_context", [])}
        for c in self.clients:
            if c.role == "app" and (c.profile["depth"], c.profile.get("team")) == key[1:] \
                    and visible_to(a, c.profile["amount"]):
                await self.send(c, msg)

    def catch_up(self, profile: dict, since_t: float | None) -> dict:
        m = self.replay.model
        line = f"Score: {m.team_name('home')} {m.score['home']}–{m.score['away']} {m.team_name('away')}."
        return catchup.summary(self.feed, self.clock_marks, since_t, self.replay.now, profile, line)

    async def send_backlog(self, c: Client):
        items = [self.feed_msg(o, c.profile) for o in self.feed if visible_to(o, c.profile["amount"])]
        await self.send(c, {"type": "backlog", "feed": items})
        for a in self.analyses:
            if visible_to(a, c.profile["amount"]):
                self.request_text(a, c.profile)


rooms: dict[str, Room] = {}


async def warm_demo(seed: int = DEMO_SEED):
    """Write every analysis of the demo match ahead of time, for all profiles."""
    match = await prepare_match(seed)
    room = Room("_warm", seed, match=match)

    def scan():
        return [o for o in Replay(match).advance(match.duration) if o["kind"] == "analysis"]

    analyses = await asyncio.get_running_loop().run_in_executor(_match_worker, scan)
    for a in analyses:
        for depth in ("basic", "deep"):
            for team in (None, "home", "away"):
                key = (seed, a["moment"], a["t"], depth, team)
                if key not in _text_cache:
                    _text_cache[key] = await room.explainer.write(a["factpack"], depth, team)
    log.info("warmed %d analysis texts for seed %d", len(_text_cache), seed)


# One question per answer path: the routed agents and the meaning analyst.
WARM_QUESTIONS = ("What's the score?", "Who is in control?")


async def warm_foundry(seed: int = DEMO_SEED) -> list[str]:
    """Ask the model once per answer path at startup, before any viewer does.

    The first calls of a fresh process fetch the identity token and open the
    connections and agents; that can exceed the answer time limit, so a viewer's
    first question would fall back to written-by-code text. Results are discarded.
    """
    if _client is None:
        return []
    match = await prepare_match(seed)
    room = Room("_warm_ai", seed, match=match)
    sources = []
    for question in WARM_QUESTIONS:
        res = await room.assistant.answer(question)
        sources.append(res.get("source", "?"))
    log.info("warmed Foundry answer paths: %s", ", ".join(sources))
    return sources


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


def claim_host(room: Room, role: str, token: str | None) -> tuple[bool, str | None]:
    """(is_host, token to hand out). Phones are never hosts. A match screen presenting the
    room's token is the host; if no connected client holds the host role, the screen
    becomes the host with a fresh token (the old one stops working)."""
    if role != "tv":
        return False, None
    if room.host_token and token and secrets.compare_digest(token, room.host_token):
        return True, None
    if not any(c.is_host for c in room.clients):
        room.host_token = secrets.token_urlsafe(18)
        return True, room.host_token
    return False, None


def drop_room_if_empty(name: str):
    room = rooms.get(name)
    if room is None or room.clients:
        return
    room.new_run()  # cancels pending analysis work
    if room.task:
        room.task.cancel()
    del rooms[name]


async def control(room: Room, cmd: str, msg: dict):
    if cmd == "play":
        room.playing = True
        await room.broadcast_state()
    elif cmd == "pause":
        room.playing = False
        await room.broadcast_state()
    elif cmd == "speed":
        if isinstance(msg.get("value"), bool) or msg.get("value") not in SPEEDS:
            raise ValueError("invalid speed")
        room.speed = msg["value"]
        await room.broadcast_state()
    elif cmd == "seek":
        if isinstance(msg.get("t"), bool):
            raise ValueError("invalid seek time")
        await room.seek(float(msg.get("t", 0)))
    elif cmd == "new_match":
        if isinstance(msg.get("seed"), bool):
            raise ValueError("invalid seed")
        await room.new_match(int(msg.get("seed", DEMO_SEED)))


@app.websocket("/ws/{room_name}")
async def ws(websocket: WebSocket, room_name: str, role: Literal["tv", "app"] = "tv", seed: int | None = None,
             host: str | None = None):
    await websocket.accept()
    room_name = room_name[:40]
    room = rooms.get(room_name)
    if room is None:
        if len(rooms) >= MAX_ROOMS:
            await websocket.close(code=1013, reason="too many rooms; try again later")
            return
        room_seed = new_room_seed(seed)
        try:
            match = await prepare_match(room_seed)
        except MatchLoadBusy:
            await websocket.close(code=1013, reason="match preparation busy; try again later")
            return
        # Other connections can join this name or fill the room limit while loading.
        room = rooms.get(room_name)
        if room is None:
            if len(rooms) >= MAX_ROOMS:
                await websocket.close(code=1013, reason="too many rooms; try again later")
                return
            room = rooms[room_name] = Room(room_name, room_seed, match=match)
    if room.expiry:
        room.expiry.cancel()
        room.expiry = None
    c = Client(websocket, "app" if role == "app" else "tv")
    c.is_host, new_token = claim_host(room, c.role, host)
    room.clients.append(c)
    c.writer = asyncio.create_task(room.writer(c))
    room.ensure_loop()
    await room.deliver_snapshot(c, new_token)
    try:
        while True:
            try:
                msg = decode_command(await websocket.receive_text())
            except ValueError:
                await room.send(c, {"type": "error", "code": "bad_command", "message": "Invalid command."})
                continue
            cmd = msg["cmd"]
            if cmd in CONTROL_COMMANDS:
                if not c.is_host:
                    await room.send(c, {"type": "error", "code": "not_host",
                                        "message": "Only the match screen that hosts this room controls playback."})
                    continue
                try:
                    await control(room, cmd, msg)
                except MatchLoadBusy:
                    await room.send(c, {"type": "error", "code": "match_busy",
                                        "message": "Match preparation is busy. Try again shortly."})
                except (TypeError, ValueError, OverflowError):
                    await room.send(c, {"type": "error", "code": "bad_command", "message": f"Invalid {cmd} command."})
            elif cmd == "catch_up":
                try:
                    res = room.catch_up(c.profile, msg.get("since_t"))
                except ValueError:
                    await room.send(c, {"type": "error", "code": "bad_command", "message": "Invalid catch_up command."})
                    continue
                await room.send(c, {"type": "catch_up", "id": msg.get("id"), **res})
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
                run, assistant = room.run, room.assistant
                res = await assistant.answer(q, c.profile)
                if run != room.run:  # the match jumped while answering: the answer belongs to an old run
                    await room.send(c, {"type": "answer_discarded", "id": msg.get("id"), "reason": "run_changed"})
                else:
                    await room.send(c, {"type": "answer", "id": msg.get("id"), "q": q, **res,
                                        "clock": res.get("snapshot_clock") or room.replay.model.clock})
    except WebSocketDisconnect:
        pass
    finally:
        if c.writer:
            c.writer.cancel()
        room.clients.remove(c)
        if not room.clients:
            room.playing = False
            room.expiry = asyncio.get_running_loop().call_later(ROOM_GRACE_S, drop_room_if_empty, room.name)
