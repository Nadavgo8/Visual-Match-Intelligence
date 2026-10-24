""""What did I miss?" (D2-04): a short, deterministic summary of what reached the viewer.

The window opens where the viewer last saw the top of the feed or last got a summary
(`since_t`), or 5 minutes back on first use (from kick-off if less has been played), and
closes at the moment of the request. Items count by when they were delivered, not when
they happened: an event that happened before the checkpoint but arrived after it is still
something the viewer missed. Which items go in is decided here, in code; any wording by a
model later has to keep to these items.
"""

from __future__ import annotations

import bisect
import math

from ..engine.attention import visible_to

FIRST_WINDOW_S = 300.0
MAX_ITEMS = 6


def window(since_t: float | None, now_t: float) -> tuple[float, float]:
    """(start, end] in simulation seconds. A checkpoint after now (a stale client) gives an empty window."""
    if since_t is None:
        return max(0.0, now_t - FIRST_WINDOW_S), now_t
    if isinstance(since_t, bool) or not isinstance(since_t, (int, float)) or not math.isfinite(since_t):
        raise ValueError("since_t must be a finite number or null")
    return min(max(float(since_t), 0.0), now_t), now_t


def select(feed: list[dict], start: float, end: float, amount: str) -> list[dict]:
    """The most important items delivered inside the window, oldest first."""
    inside = [o for o in feed if start < o["delivered"] <= end and visible_to(o, amount)]
    top = sorted(inside, key=lambda o: (o["tier"], -o["delivered"]))[:MAX_ITEMS]
    return sorted(top, key=lambda o: (o["delivered"], o["t"]))


def clock_at(marks: list[tuple[float, str]], t: float) -> str:
    """The match clock shown at simulation time t, from the clocks the room has seen."""
    i = bisect.bisect_right(marks, (t, "￿")) - 1
    return marks[i][1] if i >= 0 else "0:00"


def summary(feed: list[dict], marks: list[tuple[float, str]], since_t: float | None, now_t: float,
            profile: dict, score_line: str) -> dict:
    start, end = window(since_t, now_t)
    items = select(feed, start, end, profile.get("amount", "balanced"))
    span = f"{clock_at(marks, start)} to {clock_at(marks, end)}"
    if items:
        text = f"From {span}: " + " ".join(o["text"][profile.get("depth", "basic")] for o in items) + f" {score_line}"
    else:
        text = f"Nothing important happened from {span}. {score_line}"
    return {"from_t": round(start, 2), "to_t": round(end, 2), "from_clock": clock_at(marks, start),
            "to_clock": clock_at(marks, end), "items": [o["cue_id"] for o in items], "text": text,
            "answer_kind": "template", "first_use": since_t is None}
