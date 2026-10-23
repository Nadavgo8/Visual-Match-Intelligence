"""Replay clock: delivers the four streams in the order a live system would receive them."""

from __future__ import annotations

import heapq
from collections.abc import Iterator

from ..generator.match import Match
from ..generator.tracking import Tracker
from .attention import AttentionEngine
from .atmosphere import Atmosphere
from .model import MatchModel

STATE_LATENCY = 0.4
TRACKING_LATENCY = 0.05
TRACKING_HZ = 20


def delivery_stream(match: Match) -> list[tuple[float, int, dict]]:
    """(deliver_at, order, record) sorted by delivery time."""
    items: list[tuple[float, int, dict]] = []
    n = 0
    for e in match.events:
        items.append((e["delivered_t"], n, e)); n += 1
    for c in match.crowd:
        items.append((c["t"] + 0.05, n, c)); n += 1
    for s in match.match_state:
        items.append((s["t"] + STATE_LATENCY, n, s)); n += 1
    heapq.heapify(items)
    return [heapq.heappop(items) for _ in range(len(items))]


class Replay:
    """Steps a match forward in match time and returns the engine's outputs."""

    def __init__(self, match: Match, atmosphere_mode: str = "combined"):
        self.match = match
        self.stream = delivery_stream(match)
        self.i = 0
        self.model = MatchModel(match.meta)
        self.engine = AttentionEngine(self.model, atmosphere=Atmosphere(mode=atmosphere_mode))
        self.now = 0.0
        self.next_tick = 0.0
        self.tracker = Tracker(match)
        self.tracking_index = 0

    @property
    def done(self) -> bool:
        return self.now >= self.match.duration

    def advance(self, to_t: float) -> list[dict]:
        out: list[dict] = []
        to_t = min(to_t, self.match.duration)
        while True:
            next_rec = self.stream[self.i][0] if self.i < len(self.stream) else float("inf")
            sample_t = self.tracking_index / TRACKING_HZ
            next_tracking = sample_t + TRACKING_LATENCY if sample_t <= self.match.duration else float("inf")
            expiry = self.engine.next_meter_expiry()
            analysis_due = self.engine.next_analysis_due()
            whistle_due = self.engine.next_whistle_due()
            if min(next_rec, next_tracking, self.next_tick, expiry, analysis_due, whistle_due) > to_t:
                break
            if expiry < min(next_rec, next_tracking, self.next_tick, analysis_due, whistle_due):
                out += self.engine.poll_meters(expiry)
            elif analysis_due < min(next_rec, next_tracking, self.next_tick, whistle_due):
                out += self.engine.release_analysis(analysis_due)
            elif whistle_due < min(next_rec, next_tracking, self.next_tick):
                out += self.engine.poll_whistles(whistle_due)
            elif next_tracking <= min(next_rec, self.next_tick):
                self.tracking_index += 1
                out += self.engine.ingest(self.tracker.observation(sample_t), next_tracking)
            elif next_rec <= self.next_tick:
                at, _, rec = self.stream[self.i]
                self.i += 1
                out += self.engine.ingest(rec, at)
            else:
                out += self.engine.tick(self.next_tick)
                self.next_tick += 1.0
        self.now = to_t
        return out


def run_all(match: Match) -> Iterator[dict]:
    r = Replay(match)
    yield from r.advance(match.duration)
